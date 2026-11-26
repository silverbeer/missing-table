"""MatchDAO.get_season_results (SB-1781): filtered in the database, paged under max_rows.

A league-wide season at one age group is more than PostgREST's 1000-row cap, so a
single read silently truncates. This pins the paging and the filters with a
mocked client; the `!inner` embed and `or` filters were checked against local Supabase.
"""

from unittest.mock import MagicMock

import pytest

import dao.match_dao as match_dao
from dao.base_dao import MATCHES_READ_RELATION
from dao.match_dao import MatchDAO

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]


def raw(match_id: int) -> dict:
    """A matches_with_test row with its embeds, as PostgREST returns it."""
    return {
        "id": match_id,
        "match_date": "2026-10-01",
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team": {"id": 1, "name": "IFA", "club": None},
        "away_team": {"id": 2, "name": "NEFC", "club": None},
        "home_score": 2,
        "away_score": 1,
        "home_penalty_score": None,
        "away_penalty_score": None,
        "season_id": 7,
        "season": {"id": 7, "name": "2026-2027", "start_date": "2026-08-01"},
        "age_group_id": 3,
        "age_group": {"id": 3, "name": "U15"},
        "match_type_id": 1,
        "match_type": {"id": 1, "name": "League"},
        "division_id": 1,
        "division": {"id": 1, "name": "Northeast", "league_id": 1, "leagues": {"id": 1, "name": "Homegrown"}},
        "match_status": "completed",
        "created_at": "2026-10-01T00:00:00Z",
        "updated_at": "2026-10-01T00:00:00Z",
    }


def _dao(pages: list[list[dict]] | Exception):
    dao = MatchDAO.__new__(MatchDAO)
    dao.connection_holder = MagicMock()
    query = MagicMock()
    for method in ("select", "eq", "in_", "or_", "order", "range"):
        getattr(query, method).return_value = query
    if isinstance(pages, Exception):
        query.execute.side_effect = pages
    else:
        query.execute.side_effect = [MagicMock(data=p) for p in pages]
    client = MagicMock()
    client.table.return_value = query
    dao.client = client
    return dao, client, query


class TestGetSeasonResults:
    def test_pages_until_an_empty_page(self, monkeypatch):
        monkeypatch.setattr(match_dao, "_SEASON_PAGE", 2)
        dao, _, query = _dao([[raw(1), raw(2)], [raw(3), raw(4)], [raw(5)], []])

        rows = dao.get_season_results(7, 3, [1, 290], [1, 5])

        assert [r["id"] for r in rows] == [1, 2, 3, 4, 5]
        assert [c.args for c in query.range.call_args_list] == [(0, 1), (2, 3), (4, 5), (5, 6)]

    def test_a_short_page_is_not_the_end(self, monkeypatch):
        """A server whose max_rows is below the page size returns short pages mid-season."""
        monkeypatch.setattr(match_dao, "_SEASON_PAGE", 1000)
        dao, _, query = _dao([[raw(1), raw(2)], [raw(3)], []])

        assert [r["id"] for r in dao.get_season_results(7, 3, [1], [1])] == [1, 2, 3]
        assert [c.args for c in query.range.call_args_list] == [(0, 999), (2, 1001), (3, 1002)]

    def test_filters_are_in_the_query(self):
        dao, client, query = _dao([[raw(1)], []])

        dao.get_season_results(7, 3, [1, 290], [11, 15])

        client.table.assert_called_with(MATCHES_READ_RELATION)
        assert "divisions!inner" in query.select.call_args.args[0]
        eqs = {c.args for c in query.eq.call_args_list}
        assert {("season_id", 7), ("is_test", False)} <= eqs
        ins = {c.args[0]: c.args[1] for c in query.in_.call_args_list}
        assert ins == {
            "division.league_id": [1, 290],
            "match_type_id": [11, 15],
            "match_status": ["completed", "forfeit"],
        }

    def test_a_side_playing_up_into_another_age_group_is_read(self):
        """The match's age group, or either side's own (SB-1444); tally decides per side."""
        dao, _, query = _dao([[raw(1)], []])

        dao.get_season_results(7, 3, [1], [1])

        assert query.or_.call_args.args == ("age_group_id.eq.3,home_age_group_id.eq.3,away_age_group_id.eq.3",)
        assert ("age_group_id", 3) not in {c.args for c in query.eq.call_args_list}

    def test_the_age_group_is_coerced_so_nothing_is_spliced_into_the_filter(self):
        dao, _, _ = _dao([[], []])
        with pytest.raises(ValueError):
            dao.get_season_results(7, "3,is_test.eq.true", [1], [1])

    def test_a_test_viewer_reads_test_matches(self):
        dao, _, query = _dao([[raw(1)], []])
        dao.get_season_results(7, 3, [1], [1], include_test=True)
        assert ("is_test", False) not in {c.args for c in query.eq.call_args_list}

    def test_rows_are_in_get_all_matches_shape(self):
        dao, _, _ = _dao([[raw(1)], []])
        row = dao.get_season_results(7, 3, [1], [1])[0]
        assert row["home_team_name"] == "IFA"
        assert row["league_id"] == 1
        assert row["division_name"] == "Northeast"
        assert row["match_type_name"] == "League"
        assert "home_penalty_score" in row
        assert "home_age_group_id" in row

    def test_a_failed_read_raises(self):
        dao, _, _ = _dao(RuntimeError("PostgREST down"))
        with pytest.raises(RuntimeError):
            dao.get_season_results(7, 3, [1], [1])

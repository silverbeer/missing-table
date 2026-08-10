"""Unit tests for SeasonDAO.get_match_counts_by_season (SB-61).

Uses a mocked Supabase client. The DAO's value is the data-shape parsing of
PostgREST's embedded-count response + the N+1 fallback when the embedded
path fails.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dao.base_dao import MATCHES_READ_RELATION
from dao.season_dao import SeasonDAO

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]


def _make_dao() -> tuple[SeasonDAO, MagicMock]:
    """Build a SeasonDAO whose `client.table(...)` is a chainable mock."""
    client_mock = MagicMock()
    connection_holder = MagicMock()
    connection_holder.get_client.return_value = client_mock

    dao = SeasonDAO.__new__(SeasonDAO)
    dao.connection_holder = connection_holder
    dao.client = client_mock
    return dao, client_mock


class TestEmbeddedCountPath:
    # SB-591: the embed targets the matches_with_test view and, for a non-test
    # viewer, adds `.eq("<view>.is_test", False)` before execute — so the mocked
    # chain is table -> select -> eq -> execute.
    def test_parses_postgrest_embedded_count_into_flat_rows(self):
        dao, client = _make_dao()
        client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {"id": 1, MATCHES_READ_RELATION: [{"count": 1437}]},
                {"id": 2, MATCHES_READ_RELATION: [{"count": 980}]},
                {"id": 3, MATCHES_READ_RELATION: [{"count": 0}]},
            ]
        )

        counts = dao.get_match_counts_by_season()

        assert counts == [
            {"season_id": 1, "match_count": 1437},
            {"season_id": 2, "match_count": 980},
            {"season_id": 3, "match_count": 0},
        ]
        client.table.assert_called_with("seasons")

    def test_filters_test_matches_out_of_the_embedded_count(self):
        """A non-test viewer must constrain the embedded resource, not just the outer row."""
        dao, client = _make_dao()
        select_mock = client.table.return_value.select.return_value
        select_mock.eq.return_value.execute.return_value = MagicMock(data=[])

        dao.get_match_counts_by_season()

        select_mock.eq.assert_called_once_with(f"{MATCHES_READ_RELATION}.is_test", False)

    def test_admin_viewer_does_not_filter_the_embedded_count(self):
        dao, client = _make_dao()
        select_mock = client.table.return_value.select.return_value
        select_mock.execute.return_value = MagicMock(data=[])

        dao.get_match_counts_by_season(include_test=True)

        select_mock.eq.assert_not_called()

    def test_treats_missing_matches_array_as_zero(self):
        dao, client = _make_dao()
        client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {"id": 1, MATCHES_READ_RELATION: []},
                {"id": 2},  # field omitted entirely
                {"id": 3, MATCHES_READ_RELATION: [{}]},  # count missing on the inner dict
            ]
        )

        counts = dao.get_match_counts_by_season()

        assert counts == [
            {"season_id": 1, "match_count": 0},
            {"season_id": 2, "match_count": 0},
            {"season_id": 3, "match_count": 0},
        ]

    def test_empty_response_returns_empty_list(self):
        dao, client = _make_dao()
        client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        assert dao.get_match_counts_by_season() == []


class TestFallbackPath:
    def test_falls_back_to_per_season_count_when_embedded_fails(self):
        dao, client = _make_dao()

        # SB-591 chain shapes for a non-test viewer:
        #   embedded: seasons.select(...).eq("<view>.is_test", False).execute()
        #   fallback: seasons.select("id").execute()
        #             <view>.select("id", count="exact")
        #                   .eq("season_id", N).eq("is_test", False).limit(0).execute()
        matches_mock_1 = MagicMock()
        c1 = MagicMock()
        c1.count = 1437
        matches_mock_1.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = c1

        matches_mock_2 = MagicMock()
        c2 = MagicMock()
        c2.count = 980
        matches_mock_2.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = c2

        seasons_after_fallback = MagicMock()
        seasons_after_fallback.select.return_value.execute.return_value = MagicMock(
            data=[{"id": 1}, {"id": 2}]
        )

        # client.table call sequence:
        # 1. table("seasons") for the embedded path (raises on execute)
        # 2. table("seasons") for the fallback list
        # 3. table(<view>) for season 1's count
        # 4. table(<view>) for season 2's count
        first_seasons = MagicMock()
        first_seasons.select.return_value.eq.return_value.execute.side_effect = RuntimeError("nope")

        client.table.side_effect = [
            first_seasons,
            seasons_after_fallback,
            matches_mock_1,
            matches_mock_2,
        ]

        counts = dao.get_match_counts_by_season()

        assert counts == [
            {"season_id": 1, "match_count": 1437},
            {"season_id": 2, "match_count": 980},
        ]
        # The fallback must read the view, not the base table, or it would
        # count test fixtures for a real viewer.
        assert client.table.call_args_list[2].args[0] == MATCHES_READ_RELATION
        assert client.table.call_args_list[3].args[0] == MATCHES_READ_RELATION

    def test_returns_empty_list_if_both_paths_fail(self):
        dao, client = _make_dao()
        # Embedded path raises; fallback seasons select also raises.
        first_seasons = MagicMock()
        first_seasons.select.return_value.eq.return_value.execute.side_effect = RuntimeError("a")
        fallback_seasons = MagicMock()
        fallback_seasons.select.return_value.execute.side_effect = RuntimeError("b")
        client.table.side_effect = [first_seasons, fallback_seasons]

        assert dao.get_match_counts_by_season() == []

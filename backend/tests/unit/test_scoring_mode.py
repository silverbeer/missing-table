"""Live-scored vs merely under way (SB-910).

Setting a match live meant two things at once: the ball is rolling, and someone
is driving the live-scoring clock. Most matches are the first without the
second — a parent marks the match in progress and types in the score their
partner texts from the touchline. Those matches then appeared on the LIVE tab
with no clock and no event feed behind them.

The fix is one status axis plus an explicit `scoring_mode`, not a second status
value: `match_status` still goes scheduled -> live -> completed, so stats,
standings and the playoff guard keep working untouched.
"""

from unittest.mock import MagicMock, patch

import pytest


def _make_match_dao():
    from dao.match_dao import MatchDAO

    dao = object.__new__(MatchDAO)
    dao.connection_holder = MagicMock()
    dao.client = MagicMock()
    return dao


@pytest.mark.unit
class TestClockStartsLiveScoring:
    """MatchDAO.update_match_clock()."""

    def _chain(self, dao):
        chain = MagicMock()
        dao.client.table.return_value = chain
        chain.update.return_value = chain
        chain.eq.return_value = chain
        chain.execute.return_value = MagicMock(data=[{"id": 1}])
        return chain

    def test_start_first_half_declares_live_scoring(self):
        dao = _make_match_dao()
        chain = self._chain(dao)

        with patch.object(dao, "get_live_match_state", return_value={"id": 1}):
            dao.update_match_clock(1, "start_first_half")

        written = chain.update.call_args[0][0]
        assert written["match_status"] == "live"
        assert written["scoring_mode"] == "live"

    def test_a_later_clock_action_does_not_restate_it(self):
        """Only the kickoff declares the mode; halftime is not a second claim."""
        dao = _make_match_dao()
        chain = self._chain(dao)

        with patch.object(dao, "get_live_match_state", return_value={"id": 1}):
            dao.update_match_clock(1, "start_halftime")

        written = chain.update.call_args[0][0]
        assert "scoring_mode" not in written


@pytest.mark.unit
class TestLiveMatchesQuery:
    """MatchDAO.get_live_matches()."""

    def _query(self, dao):
        query = MagicMock()
        dao.client.table.return_value = query
        query.select.return_value = query
        query.eq.return_value = query
        query.execute.return_value = MagicMock(data=[])
        return query

    def _eq_filters(self, query):
        return {call.args[0]: call.args[1] for call in query.eq.call_args_list}

    def test_the_live_tab_asks_for_live_scored_matches_only(self):
        dao = _make_match_dao()
        query = self._query(dao)

        dao.get_live_matches()

        filters = self._eq_filters(query)
        assert filters["match_status"] == "live"
        assert filters["scoring_mode"] == "live"

    def test_every_match_under_way_when_asked_for(self):
        dao = _make_match_dao()
        query = self._query(dao)

        dao.get_live_matches(live_scored_only=False)

        filters = self._eq_filters(query)
        assert filters["match_status"] == "live"
        assert "scoring_mode" not in filters

    def test_the_test_partition_is_still_gated(self):
        dao = _make_match_dao()
        query = self._query(dao)

        dao.get_live_matches()

        assert self._eq_filters(query)["is_test"] is False

    def test_the_mode_is_returned_with_each_row(self):
        dao = _make_match_dao()
        query = self._query(dao)
        query.execute.return_value = MagicMock(
            data=[
                {
                    "id": 3853,
                    "match_status": "live",
                    "scoring_mode": "live",
                    "match_date": "2026-08-29",
                    "home_score": 0,
                    "away_score": 0,
                    "home_team": {"name": "IFA"},
                    "away_team": {"name": "Northern Virginia Alliance"},
                }
            ]
        )

        rows = dao.get_live_matches()

        assert rows[0]["scoring_mode"] == "live"

    def test_a_row_from_before_the_column_existed_reads_as_manual(self):
        """Absent is not live: never claim a feed we cannot confirm."""
        dao = _make_match_dao()
        query = self._query(dao)
        query.execute.return_value = MagicMock(
            data=[
                {
                    "id": 1,
                    "match_status": "live",
                    "match_date": "2026-08-29",
                    "home_score": None,
                    "away_score": None,
                    "home_team": {"name": "IFA"},
                    "away_team": {"name": "NVA"},
                }
            ]
        )

        rows = dao.get_live_matches()

        assert rows[0]["scoring_mode"] == "manual"

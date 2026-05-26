"""Unit tests for TournamentDAO.update_tournament_match team-id updates.

Specifically covers the TBD-resolution path: matches loaded with a
placeholder team can have their home_team_id / away_team_id replaced
when the real team is announced.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def dao():
    from dao.tournament_dao import TournamentDAO

    # Bypass BaseDAO's connection-holder isinstance check — we never hit a
    # real DB, just assert what gets staged into the update dict.
    d = TournamentDAO.__new__(TournamentDAO)
    d.connection_holder = MagicMock()
    d.client = MagicMock()
    return d


def _capture_update_payload(dao):
    """Stub out the supabase client's `.update()` and return the dict it received."""
    captured = {}
    table = MagicMock()

    def update(updates):
        captured["updates"] = updates
        chain = MagicMock()
        chain.eq.return_value.execute.return_value.data = [{"id": 1, **updates}]
        return chain

    table.update.side_effect = update
    dao.client.table.return_value = table
    return captured


class TestUpdateMatchTeamIds:
    def test_home_team_id_sets_field(self, dao):
        captured = _capture_update_payload(dao)
        dao.update_tournament_match(match_id=1, home_team_id=42)
        assert captured["updates"] == {"home_team_id": 42}

    def test_away_team_id_sets_field(self, dao):
        captured = _capture_update_payload(dao)
        dao.update_tournament_match(match_id=1, away_team_id=42)
        assert captured["updates"] == {"away_team_id": 42}

    def test_both_team_ids_in_one_update(self, dao):
        """Common TBD-resolution case: both sides revealed at once."""
        captured = _capture_update_payload(dao)
        dao.update_tournament_match(match_id=1, home_team_id=10, away_team_id=20)
        assert captured["updates"] == {"home_team_id": 10, "away_team_id": 20}

    def test_team_id_change_combines_with_score_update(self, dao):
        """Resolving a TBD + entering its score should be one atomic call."""
        captured = _capture_update_payload(dao)
        dao.update_tournament_match(
            match_id=1,
            home_team_id=10,
            home_score=3,
            away_score=2,
            match_status="completed",
        )
        assert captured["updates"] == {
            "home_team_id": 10,
            "home_score": 3,
            "away_score": 2,
            "match_status": "completed",
        }

    def test_swap_home_away_conflicts_with_explicit_team_id(self, dao):
        """The two flag families are mutually exclusive — refusing the
        combination prevents an ambiguous write where the swap might
        clobber the explicit set or vice-versa."""
        with pytest.raises(ValueError, match="mutually exclusive"):
            dao.update_tournament_match(
                match_id=1, swap_home_away=True, home_team_id=42
            )
        with pytest.raises(ValueError, match="mutually exclusive"):
            dao.update_tournament_match(
                match_id=1, swap_home_away=True, away_team_id=42
            )

    def test_no_team_id_update_when_none(self, dao):
        """Don't include team_id keys in the update payload when not passed —
        we don't want to accidentally write nulls into a NOT NULL column."""
        captured = _capture_update_payload(dao)
        dao.update_tournament_match(match_id=1, home_score=2)
        assert "home_team_id" not in captured["updates"]
        assert "away_team_id" not in captured["updates"]

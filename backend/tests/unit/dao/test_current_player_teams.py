"""Unit tests for current-team selection (SB-441).

`is_current` rows accumulate across seasons because nothing clears the flag when
a player moves on, so My Club could show a team from a previous season. These
cover the read-side selection rule and the write-side flag cleanup.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dao.player_dao import PlayerDAO, select_current_teams

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]


def _row(row_id: int, season_id: int, start_date: str | None, team: str) -> dict:
    return {
        "id": row_id,
        "season_id": season_id,
        "is_current": True,
        "season": {"id": season_id, "name": f"season-{season_id}", "start_date": start_date},
        "team": {"id": row_id * 10, "name": team},
    }


# Gabe's actual prod rows (SB-441): two stale 2025-2026 entries plus the real one.
FUTSAL = _row(27, 3, "2025-09-01", "IFA Elite Futsal 2012 White")
OLD_IFA = _row(28, 3, "2025-09-01", "IFA")
CURRENT_IFA = _row(81, 184, "2026-08-01", "IFA")


class TestSelectCurrentTeams:
    def test_keeps_only_the_current_seasons_rows(self):
        result = select_current_teams([FUTSAL, OLD_IFA, CURRENT_IFA], current_season_id=184)

        assert [r["id"] for r in result] == [81]

    def test_order_of_input_does_not_matter(self):
        forward = select_current_teams([FUTSAL, OLD_IFA, CURRENT_IFA], 184)
        reverse = select_current_teams([CURRENT_IFA, OLD_IFA, FUTSAL], 184)

        assert [r["id"] for r in forward] == [r["id"] for r in reverse] == [81]

    def test_keeps_multiple_teams_within_the_current_season(self):
        futsal_now = _row(90, 184, "2026-08-01", "IFA Elite Futsal 2013 White")

        result = select_current_teams([CURRENT_IFA, futsal_now], 184)

        assert {r["id"] for r in result} == {81, 90}

    def test_falls_back_to_newest_season_when_none_are_current(self):
        # Player hasn't been rostered for the new season yet — show their last
        # team rather than "No Team Assigned".
        result = select_current_teams([FUTSAL, OLD_IFA], current_season_id=184)

        assert {r["id"] for r in result} == {27, 28}

    def test_fallback_picks_the_newest_season_only(self):
        older = _row(10, 2, "2024-09-01", "IFA U13")

        result = select_current_teams([older, FUTSAL, OLD_IFA], current_season_id=184)

        assert {r["id"] for r in result} == {27, 28}

    def test_newest_season_first(self):
        older = _row(10, 2, "2024-09-01", "IFA U13")

        result = select_current_teams([older, FUTSAL, CURRENT_IFA], current_season_id=None)

        assert result[0]["id"] == 81

    def test_rows_without_a_season_date_do_not_win(self):
        undated = _row(99, 999, None, "Mystery FC")

        result = select_current_teams([undated, CURRENT_IFA], current_season_id=None)

        assert [r["id"] for r in result] == [81]

    def test_empty_input(self):
        assert select_current_teams([], 184) == []

    def test_unresolvable_current_season_still_returns_newest(self):
        result = select_current_teams([FUTSAL, OLD_IFA, CURRENT_IFA], current_season_id=None)

        assert [r["id"] for r in result] == [81]


def _make_dao() -> tuple[PlayerDAO, MagicMock]:
    client_mock = MagicMock()
    dao = PlayerDAO.__new__(PlayerDAO)
    dao.connection_holder = MagicMock()
    dao.client = client_mock
    return dao, client_mock


class TestClearCurrentInOtherSeasons:
    def test_targets_the_players_other_seasons_only(self):
        dao, client = _make_dao()

        dao._clear_current_in_other_seasons("player-1", 184)

        update = client.table.return_value.update
        update.assert_called_once()
        assert update.call_args[0][0]["is_current"] is False

        chain = update.return_value
        chain.eq.assert_any_call("player_id", "player-1")
        chain.eq.return_value.eq.assert_called_once_with("is_current", True)
        chain.eq.return_value.eq.return_value.neq.assert_called_once_with("season_id", 184)

    def test_swallows_db_errors(self):
        dao, client = _make_dao()
        client.table.side_effect = RuntimeError("connection lost")

        # Must not raise — the write that triggered it already succeeded.
        dao._clear_current_in_other_seasons("player-1", 184)

"""Unit tests for season-scoping the team roster (SB-442).

`get_team_players` filtered on team + is_current only, so a player carrying the
flag on rows for the same team in two seasons was listed once per row — the
duplicate Gabe on the IFA roster.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dao.player_dao import PlayerDAO
from dao.season_dao import PLAYERS_CACHE_PATTERN, SEASONS_CACHE_PATTERN, SeasonDAO

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]

CURRENT_SEASON = 184
LAST_SEASON = 3


def _history_row(row_id: int, season_id: int, start_date: str, jersey: int, name: str) -> dict:
    return {
        "id": row_id,
        "player_id": f"player-{name}",
        "jersey_number": jersey,
        "positions": ["CB"],
        "season_id": season_id,
        "season": {"id": season_id, "start_date": start_date},
        "user_profiles": {"id": f"player-{name}", "display_name": name, "player_number": 0},
    }


def _build_dao(rows: list[dict], current_season_id: int | None = CURRENT_SEASON):
    client_mock = MagicMock()
    execute_mock = MagicMock()
    execute_mock.data = rows
    eq_mock = MagicMock()
    eq_mock.execute.return_value = execute_mock
    eq_mock.eq.return_value = eq_mock
    client_mock.table.return_value.select.return_value.eq.return_value = eq_mock

    dao = PlayerDAO.__new__(PlayerDAO)
    dao.connection_holder = MagicMock()
    dao.client = client_mock
    patcher = patch.object(PlayerDAO, "_current_season_id", return_value=current_season_id)
    patcher.start()
    return dao, patcher


class TestGetTeamPlayersSeasonScope:
    def test_player_with_rows_in_two_seasons_appears_once(self):
        # Gabe's actual rows: same player, same team, U14 last season and U15 now.
        rows = [
            _history_row(28, LAST_SEASON, "2025-09-01", 35, "Gabe"),
            _history_row(81, CURRENT_SEASON, "2026-08-01", 35, "Gabe"),
        ]
        dao, patcher = _build_dao(rows)
        try:
            players = dao.get_team_players(team_id=19)
        finally:
            patcher.stop()

        assert len(players) == 1
        assert players[0]["display_name"] == "Gabe"

    def test_keeps_every_player_on_the_current_seasons_roster(self):
        rows = [
            _history_row(81, CURRENT_SEASON, "2026-08-01", 35, "Gabe"),
            _history_row(82, CURRENT_SEASON, "2026-08-01", 7, "Sam"),
            _history_row(28, LAST_SEASON, "2025-09-01", 9, "Alex"),
        ]
        dao, patcher = _build_dao(rows)
        try:
            players = dao.get_team_players(team_id=19)
        finally:
            patcher.stop()

        # Alex has no current-season row — no longer on this roster.
        assert [p["display_name"] for p in players] == ["Sam", "Gabe"]  # sorted by number

    def test_falls_back_to_last_season_when_roster_not_rebuilt_yet(self):
        # Pre-season: nobody has a current-season row. Showing last season's
        # squad beats showing an empty team page.
        rows = [
            _history_row(28, LAST_SEASON, "2025-09-01", 35, "Gabe"),
            _history_row(29, LAST_SEASON, "2025-09-01", 7, "Sam"),
        ]
        dao, patcher = _build_dao(rows)
        try:
            players = dao.get_team_players(team_id=19)
        finally:
            patcher.stop()

        assert {p["display_name"] for p in players} == {"Gabe", "Sam"}

    def test_jersey_and_positions_still_come_from_the_history_row(self):
        rows = [_history_row(81, CURRENT_SEASON, "2026-08-01", 35, "Gabe")]
        dao, patcher = _build_dao(rows)
        try:
            players = dao.get_team_players(team_id=19)
        finally:
            patcher.stop()

        assert players[0]["player_number"] == 35
        assert players[0]["positions"] == ["CB"]

    def test_unresolvable_current_season_still_returns_newest(self):
        rows = [
            _history_row(28, LAST_SEASON, "2025-09-01", 35, "Gabe"),
            _history_row(81, CURRENT_SEASON, "2026-08-01", 35, "Gabe"),
        ]
        dao, patcher = _build_dao(rows, current_season_id=None)
        try:
            players = dao.get_team_players(team_id=19)
        finally:
            patcher.stop()

        assert len(players) == 1


class TestSetCurrentSeasonInvalidatesRosters:
    def test_clears_players_cache_too(self):
        """Rosters resolve against the current season but their cache keys have
        no season component, so the flip has to clear them."""
        dao = SeasonDAO.__new__(SeasonDAO)
        dao.connection_holder = MagicMock()
        dao.client = MagicMock()
        dao.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": CURRENT_SEASON, "name": "2026-2027"}]
        )

        with patch("dao.base_dao.clear_cache") as clear_cache:
            dao.set_current_season(CURRENT_SEASON)

        cleared = {c.args[0] for c in clear_cache.call_args_list}
        assert SEASONS_CACHE_PATTERN in cleared
        assert PLAYERS_CACHE_PATTERN in cleared

"""Goals leaderboard across several match types (SB-1594).

The Leaders tab's "League + Flex" chip sends match_type_id twice. Goals and
games from both competitions must total per player; a single id must behave
exactly as before.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dao.player_stats_dao import PlayerStatsDAO

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]

LEAGUE, FLEX, FRIENDLY = 1, 2, 3


def _stat(player_id: int, match_type_id: int, goals: int) -> dict:
    return {
        "player_id": player_id,
        "goals": goals,
        "started": True,
        "played": True,
        "match": {
            "id": 1000 + match_type_id,
            "season_id": 9,
            "match_status": "completed",
            "match_type_id": match_type_id,
            "tournament_id": None,
            "division_id": 5,
            "age_group_id": 3,
            "is_test": False,
            "division": {"id": 5, "league_id": 1},
        },
        "player": {
            "id": player_id,
            "jersey_number": player_id,
            "first_name": f"P{player_id}",
            "last_name": "X",
            "team_id": 77,
            "team": {"id": 77, "name": "IFA"},
        },
    }


ROWS = [
    _stat(10, LEAGUE, 3),
    _stat(10, FLEX, 2),
    _stat(10, FRIENDLY, 9),
    _stat(20, LEAGUE, 4),
    _stat(30, FLEX, 1),
]


def _dao() -> PlayerStatsDAO:
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=ROWS)
    dao = PlayerStatsDAO.__new__(PlayerStatsDAO)
    dao.connection_holder = MagicMock()
    dao.client = client
    return dao


def _goals(result: list[dict]) -> dict[int, tuple[int, int]]:
    return {r["player_id"]: (r["goals"], r["games_played"]) for r in result}


def test_league_plus_flex_totals_per_player():
    result = _dao().get_goals_leaderboard(season_id=9, match_type_id=[LEAGUE, FLEX])
    assert _goals(result) == {10: (5, 2), 20: (4, 1), 30: (1, 1)}
    assert [r["player_id"] for r in result] == [10, 20, 30]
    assert [r["rank"] for r in result] == [1, 2, 3]


def test_single_id_unchanged():
    assert _goals(_dao().get_goals_leaderboard(season_id=9, match_type_id=LEAGUE)) == {10: (3, 1), 20: (4, 1)}


def test_single_id_as_list_matches_scalar():
    dao = _dao()
    assert dao.get_goals_leaderboard(season_id=9, match_type_id=[FLEX]) == dao.get_goals_leaderboard(
        season_id=9, match_type_id=FLEX
    )


def test_no_filter_pools_everything():
    assert _goals(_dao().get_goals_leaderboard(season_id=9)) == {10: (14, 3), 20: (4, 1), 30: (1, 1)}

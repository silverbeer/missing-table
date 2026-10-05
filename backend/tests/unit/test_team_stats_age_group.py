"""SB-1258: team stats can be narrowed to one age group.

A Homegrown squad is one team row mapped to several age groups, so its Golden
Boot board mixes every age group's players. The filter uses the same rule as
the roster (SB-68) — `players.age_group_id` — so the board lists exactly the
players on the Roster tab beside it.

The cache key matters as much as the filter: a U15 request must never be served
a cached all-age-groups board.
"""

import inspect
from unittest.mock import MagicMock

import pytest

from dao.player_stats_dao import PlayerStatsDAO

U15 = 21

STATS = {
    "games_played": 3,
    "games_started": 2,
    "total_minutes": 200,
    "total_goals": 4,
    "total_assists": 1,
    "total_yellow_cards": 0,
    "total_red_cards": 0,
}


def _dao_with(players):
    """PlayerStatsDAO whose players query returns `players`, with or without the extra filter."""
    client = MagicMock()
    base = client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value
    base.execute.return_value = MagicMock(data=players)
    base.eq.return_value.execute.return_value = MagicMock(data=players)
    dao = PlayerStatsDAO.__new__(PlayerStatsDAO)
    dao.client = client
    dao.get_player_season_stats = MagicMock(return_value=STATS)
    return dao, base


@pytest.mark.unit
class TestAgeGroupFilter:
    def test_no_age_group_does_not_filter_the_squad(self):
        dao, base = _dao_with([{"id": 1, "jersey_number": 9}])

        result = dao.get_team_stats(5, 7)

        base.eq.assert_not_called()
        assert [p["player_id"] for p in result] == [1]

    def test_age_group_filters_on_the_player_row(self):
        dao, base = _dao_with([{"id": 1, "jersey_number": 9}])

        dao.get_team_stats(5, 7, age_group_id=U15)

        base.eq.assert_called_once_with("age_group_id", U15)

    def test_an_age_group_with_no_roster_is_an_empty_board_not_an_error(self):
        """The default team has no user data; absent is [] and the endpoint stays 200."""
        dao, _ = _dao_with([])

        assert dao.get_team_stats(5, 7, age_group_id=U15) == []
        dao.get_player_season_stats.assert_not_called()

    def test_composes_with_match_type(self):
        dao, base = _dao_with([{"id": 1, "jersey_number": 9}])

        dao.get_team_stats(5, 7, match_type_id=1, age_group_id=U15)

        base.eq.assert_called_once_with("age_group_id", U15)
        assert dao.get_player_season_stats.call_args.kwargs["match_type_id"] == 1


@pytest.mark.unit
def test_cache_key_is_keyed_on_age_group():
    source = inspect.getsource(PlayerStatsDAO)
    before_fn = source.split("def get_team_stats(")[0]
    decorator = [line for line in before_fn.splitlines() if "@dao_cache" in line][-1]

    assert "age_group_id" in decorator, (
        "get_team_stats takes age_group_id but its cache key ignores it, "
        "so a U15 request can be served an all-age-groups board"
    )

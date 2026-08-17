"""SB-433: season stats can be narrowed to one competition.

The Golden Boot board defaults to league games. Folding friendlies and
tournaments into the same total makes it incomparable with the league table
beside it, so the filter has to reach the aggregation rather than being applied
in the UI after the fact.

The cache key matters as much as the filter: `get_player_season_stats` and
`get_team_stats` are both cached on their arguments, so a league-only request
would otherwise be served a previously-cached all-competitions total.
"""

import inspect

import pytest

from dao.player_stats_dao import PlayerStatsDAO

LEAGUE = 1
FRIENDLY = 2
TOURNAMENT = 3


def _row(goals, assists, match_type_id, is_test=False):
    return {
        "played": True,
        "started": True,
        "minutes_played": 90,
        "goals": goals,
        "assists": assists,
        "yellow_cards": 0,
        "red_cards": 0,
        "match": {
            "id": 1,
            "season_id": 7,
            "is_test": is_test,
            "match_type_id": match_type_id,
        },
    }


ROWS = [
    _row(2, 1, LEAGUE),
    _row(1, 0, LEAGUE),
    _row(3, 2, FRIENDLY),
    _row(4, 1, TOURNAMENT),
]


def _dao_with(rows):
    """PlayerStatsDAO whose client returns `rows` from player_match_stats."""
    from unittest.mock import MagicMock

    client = MagicMock()
    chain = client.table.return_value.select.return_value.eq.return_value.eq.return_value
    chain.execute.return_value = MagicMock(data=rows)
    dao = PlayerStatsDAO.__new__(PlayerStatsDAO)
    dao.client = client
    return dao


@pytest.mark.unit
class TestMatchTypeFilter:
    def test_no_filter_counts_every_competition(self):
        stats = _dao_with(ROWS).get_player_season_stats(1, 7)

        assert stats["total_goals"] == 10
        assert stats["total_assists"] == 4
        assert stats["games_played"] == 4

    def test_league_only(self):
        stats = _dao_with(ROWS).get_player_season_stats(1, 7, match_type_id=LEAGUE)

        assert stats["total_goals"] == 3
        assert stats["total_assists"] == 1
        assert stats["games_played"] == 2

    def test_friendly_only(self):
        stats = _dao_with(ROWS).get_player_season_stats(1, 7, match_type_id=FRIENDLY)

        assert stats["total_goals"] == 3
        assert stats["games_played"] == 1

    def test_a_competition_with_no_matches_is_zero_not_an_error(self):
        stats = _dao_with([_row(2, 1, LEAGUE)]).get_player_season_stats(1, 7, match_type_id=TOURNAMENT)

        assert stats["total_goals"] == 0
        assert stats["games_played"] == 0

    def test_the_test_partition_still_applies_within_a_competition(self):
        """SB-591's gate and this filter have to compose, not override."""
        rows = [_row(2, 0, LEAGUE), _row(9, 9, LEAGUE, is_test=True)]

        real = _dao_with(rows).get_player_season_stats(1, 7, match_type_id=LEAGUE)
        assert real["total_goals"] == 2

        with_test = _dao_with(rows).get_player_season_stats(1, 7, include_test=True, match_type_id=LEAGUE)
        assert with_test["total_goals"] == 11

    def test_match_type_is_selected_from_the_joined_match(self):
        """The filter is worthless if the column is not in the select."""
        dao = _dao_with(ROWS)
        dao.get_player_season_stats(1, 7, match_type_id=LEAGUE)

        selected = dao.client.table.return_value.select.call_args.args[0]
        assert "match_type_id" in selected


@pytest.mark.unit
class TestCacheKeysIncludeMatchType:
    """A filtered request must not be served an unfiltered cached total."""

    @pytest.mark.parametrize("fn_name", ["get_player_season_stats", "get_team_stats"])
    def test_cache_key_is_keyed_on_match_type(self, fn_name):
        source = inspect.getsource(PlayerStatsDAO)
        # The decorator sits directly above the function it caches.
        before_fn = source.split(f"def {fn_name}(")[0]
        decorator = [line for line in before_fn.splitlines() if "@dao_cache" in line][-1]

        assert "match_type_id" in decorator, (
            f"{fn_name} takes match_type_id but its cache key ignores it, "
            "so a league-only request can be served an all-competitions total"
        )

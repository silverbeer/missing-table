"""SB-433: season aggregation sums assists and cards, not just goals.

player_match_stats has carried assists, yellow_cards and red_cards all along,
but get_player_season_stats only summed minutes and goals — so the team page
and player profiles had no way to show them. These pin the full set.
"""

from unittest.mock import MagicMock

import pytest

from dao.player_stats_dao import PlayerStatsDAO


def _dao_with(rows):
    """PlayerStatsDAO whose client returns `rows` from player_match_stats."""
    client = MagicMock()
    chain = client.table.return_value.select.return_value.eq.return_value.eq.return_value
    chain.execute.return_value = MagicMock(data=rows)
    dao = PlayerStatsDAO.__new__(PlayerStatsDAO)
    dao.client = client
    return dao


# SB-671 filters on match status, so every fixture row carries a played match.
PLAYED_MATCH = {"id": 1, "season_id": 1, "is_test": False, "match_status": "completed"}

MATCHES = [
    # started, full 90, scored twice, one assist, booked
    {
        "played": True,
        "started": True,
        "minutes_played": 90,
        "goals": 2,
        "assists": 1,
        "yellow_cards": 1,
        "red_cards": 0,
        "match": PLAYED_MATCH,
    },
    # off the bench, one assist
    {
        "played": True,
        "started": False,
        "minutes_played": 25,
        "goals": 0,
        "assists": 1,
        "yellow_cards": 0,
        "red_cards": 0,
        "match": PLAYED_MATCH,
    },
    # sent off
    {
        "played": True,
        "started": True,
        "minutes_played": 40,
        "goals": 1,
        "assists": 0,
        "yellow_cards": 0,
        "red_cards": 1,
        "match": PLAYED_MATCH,
    },
    # unused sub — must not count as an appearance
    {
        "played": False,
        "started": False,
        "minutes_played": 0,
        "goals": 0,
        "assists": 0,
        "yellow_cards": 0,
        "red_cards": 0,
        "match": PLAYED_MATCH,
    },
]


class TestSeasonAggregation:
    def test_sums_assists_and_cards_alongside_goals(self):
        stats = _dao_with(MATCHES).get_player_season_stats(player_id=10, season_id=1)

        assert stats["total_goals"] == 3
        assert stats["total_assists"] == 2
        assert stats["total_yellow_cards"] == 1
        assert stats["total_red_cards"] == 1

    def test_appearances_ignore_unused_subs(self):
        stats = _dao_with(MATCHES).get_player_season_stats(player_id=10, season_id=1)

        assert stats["games_played"] == 3  # not 4 — one was an unused sub
        assert stats["games_started"] == 2
        assert stats["total_minutes"] == 155

    def test_missing_columns_default_to_zero(self):
        """Older rows predate some columns; absence must not raise."""
        stats = _dao_with(
            [{"played": True, "started": True, "minutes_played": 90, "goals": 1}]
        ).get_player_season_stats(player_id=10, season_id=1)

        assert stats["total_assists"] == 0
        assert stats["total_yellow_cards"] == 0
        assert stats["total_red_cards"] == 0

    def test_no_matches_returns_zeroes_not_none(self):
        stats = _dao_with([]).get_player_season_stats(player_id=10, season_id=1)

        assert stats["games_played"] == 0
        assert stats["total_goals"] == 0
        assert stats["total_assists"] == 0


@pytest.mark.parametrize(
    "field",
    ["total_goals", "total_assists", "total_yellow_cards", "total_red_cards", "total_minutes"],
)
def test_every_headline_stat_is_present(field):
    """Guards the contract the team page and player profile read."""
    stats = _dao_with(MATCHES).get_player_season_stats(player_id=10, season_id=1)
    assert field in stats

"""SB-671: appearances only count matches that were actually played.

Two paths conspired to overstate GP. Saving a lineup called
`set_started(..., True)` for every listed player, so a squad's games-played rose
the moment a future lineup was entered. And the season aggregation joined
matches on season, test partition and competition — but never on status — so a
match reverted to `scheduled` kept contributing forever, since nothing cleans up
`player_match_stats` on a revert.

The fix asks the match whether it happened rather than trusting the rows to be
tidy, which also repairs data already written.
"""

from unittest.mock import MagicMock

import pytest

from dao.player_stats_dao import PLAYED_STATUSES, PlayerStatsDAO


def _row(status, goals=0, started=True, played=True):
    return {
        "played": played,
        "started": started,
        "minutes_played": 90,
        "goals": goals,
        "assists": 0,
        "yellow_cards": 0,
        "red_cards": 0,
        "match": {
            "id": 1,
            "season_id": 7,
            "is_test": False,
            "match_type_id": 1,
            "match_status": status,
        },
    }


def _dao_with(rows):
    client = MagicMock()
    chain = client.table.return_value.select.return_value.eq.return_value.eq.return_value
    chain.execute.return_value = MagicMock(data=rows)
    dao = PlayerStatsDAO.__new__(PlayerStatsDAO)
    dao.client = client
    return dao


@pytest.mark.unit
class TestOnlyPlayedMatchesCount:
    def test_a_scheduled_match_contributes_nothing(self):
        """The reported bug: a lineup saved, or a start reverted, must not count."""
        stats = _dao_with([_row("scheduled", goals=2)]).get_player_season_stats(1, 7)

        assert stats["games_played"] == 0
        assert stats["games_started"] == 0
        assert stats["total_goals"] == 0

    @pytest.mark.parametrize("status", ["scheduled", "postponed", "cancelled"])
    def test_matches_that_never_happened_are_excluded(self, status):
        stats = _dao_with([_row(status)]).get_player_season_stats(1, 7)

        assert stats["games_played"] == 0

    @pytest.mark.parametrize("status", PLAYED_STATUSES)
    def test_played_matches_are_counted(self, status):
        stats = _dao_with([_row(status)]).get_player_season_stats(1, 7)

        assert stats["games_played"] == 1
        assert stats["games_started"] == 1

    def test_a_live_match_counts_immediately(self):
        """Recording starters at kickoff is pointless if the board waits for full time."""
        stats = _dao_with([_row("live")]).get_player_season_stats(1, 7)

        assert stats["games_started"] == 1

    def test_two_friendlies_and_a_reverted_third_read_as_two(self):
        """The exact shape reported: 3 rows, 2 real games."""
        rows = [_row("completed"), _row("completed"), _row("scheduled")]

        stats = _dao_with(rows).get_player_season_stats(1, 7)

        assert stats["games_played"] == 2

    def test_status_is_selected_from_the_joined_match(self):
        """The filter is worthless if the column is not in the select."""
        dao = _dao_with([_row("completed")])
        dao.get_player_season_stats(1, 7)

        assert "match_status" in dao.client.table.return_value.select.call_args.args[0]

    def test_the_competition_filter_still_composes(self):
        rows = [_row("completed"), _row("completed")]
        rows[1]["match"]["match_type_id"] = 2

        stats = _dao_with(rows).get_player_season_stats(1, 7, match_type_id=1)

        assert stats["games_played"] == 1

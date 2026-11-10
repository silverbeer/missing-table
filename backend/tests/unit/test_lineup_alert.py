"""Saving a lineup tells the squad's player channel (SB-1610).

Once per match and team (the ledger event key), never for an empty lineup or a
match already played, and never for a team that is not in the match.
"""

from unittest.mock import MagicMock, patch

import pytest

from models import LineupSave

pytestmark = pytest.mark.unit

MATCH = {"id": 5, "home_team_id": 10, "away_team_id": 20, "match_status": "scheduled"}
MANAGER = {"role": "team-manager", "username": "m"}


def _lineup(n=11):
    return LineupSave(formation_name="4-3-3", positions=[{"player_id": i + 1, "position": "CM"} for i in range(n)])


def _run(lineup, match=MATCH, team_id=10):
    import app as app_module

    tasks = MagicMock()
    with patch.object(app_module.match_dao, "get_match_by_id", return_value=match):
        app_module._maybe_notify_lineup(tasks, 5, team_id, lineup, MANAGER)
    return tasks


def test_a_saved_lineup_queues_one_keyed_alert_for_that_team():
    tasks = _run(_lineup())
    fn, event, match_id, extra, key = tasks.add_task.call_args.args
    assert (event, match_id, key) == ("lineup", 5, "match:5:lineup:10")
    assert extra == {"team_id": 10, "formation": "4-3-3", "player_count": 11}


@pytest.mark.parametrize(
    "lineup,match,team_id",
    [
        (_lineup(0), MATCH, 10),  # empty: no players, no post
        (_lineup(), {**MATCH, "match_status": "completed"}, 10),  # already played
        (_lineup(), None, 10),  # match not visible
        (_lineup(), MATCH, 99),  # not one of the teams
    ],
)
def test_nothing_is_queued(lineup, match, team_id):
    assert not _run(lineup, match, team_id).add_task.called

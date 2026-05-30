"""Dispatcher push-fan-out-without-club-channels tests (SB-77).

Regression guard for the bug where `Notifier.notify()` returned early when a
match's clubs had no notification channels — silently skipping the Web Push
fan-out to team followers. Tournament teams typically have no club channels,
so this was the whole gap behind "notify followers when a match is scored".

The fix: club-channel sends and the push fan-out are independent; a match with
no channels must still push to followers.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from notifications.dispatcher import Notifier
from notifications.preferences import DEFAULT_PREFERENCES
from notifications.web_push_sender import SendResult

pytestmark = [pytest.mark.unit, pytest.mark.backend]


def _send_ok(_sub, _payload):
    return SendResult(status="sent", http_status=201)


# A fulltime match for two teams whose clubs have NO notification channels.
_MATCH = {
    "id": 555,
    "home_team_id": 10,
    "away_team_id": 20,
    "home_team_name": "Houston Rangers",
    "away_team_name": "Cedar Stars Academy Bergen",
    "home_score": 0,
    "away_score": 1,
    "home_team_club": None,
    "away_team_club": None,
}


@pytest.fixture(autouse=True)
def _push_configured(monkeypatch):
    monkeypatch.setattr("notifications.dispatcher.push_is_configured", lambda: True)


def _notifier_with_follower():
    """Notifier whose match lookup returns _MATCH, no club channels, and one
    follower with one device. DB-touching DAOs are mocked."""
    push_send_fn = MagicMock(side_effect=_send_ok)
    notifier = Notifier(send_fn=MagicMock(), push_send_fn=push_send_fn)

    notifier._match_dao = MagicMock()
    notifier._match_dao.get_match_by_id.return_value = _MATCH

    # No club channels for either club.
    notifier._notif_dao = MagicMock()
    notifier._notif_dao.list_by_club.return_value = []

    # Timezone lookup hits connection.get_client(); stub the whole connection.
    notifier._connection = MagicMock()

    # One follower, one device.
    notifier._team_follow_dao = MagicMock()
    notifier._team_follow_dao.list_subscriptions_for_team_ids.return_value = [
        {"id": "sub-1", "user_id": "u-follower", "endpoint": "https://push/x",
         "p256dh_key": "k", "auth_key": "a"},
    ]
    notifier._prefs_dao = MagicMock()
    notifier._prefs_dao.get_preferences_batch.return_value = {
        "u-follower": dict(DEFAULT_PREFERENCES)
    }
    notifier._push_log_dao = MagicMock()
    notifier._push_sub_dao = MagicMock()

    return notifier, push_send_fn


def test_fulltime_pushes_to_follower_with_no_club_channels():
    notifier, push_send_fn = _notifier_with_follower()

    notifier.notify("fulltime", _MATCH["id"], None)

    # The whole point: a no-channel match still pushes to the follower.
    push_send_fn.assert_called_once()
    sent_sub = push_send_fn.call_args.args[0]
    assert sent_sub["id"] == "sub-1"
    # And the send was logged.
    notifier._push_log_dao.log.assert_called_once()


def test_club_send_not_attempted_when_no_channels():
    notifier, _ = _notifier_with_follower()
    notifier.notify("fulltime", _MATCH["id"], None)
    # No club channels resolved → outbound club sender never called.
    notifier.send_fn.assert_not_called()


def test_no_followers_means_no_push_but_no_error():
    notifier, push_send_fn = _notifier_with_follower()
    notifier._team_follow_dao.list_subscriptions_for_team_ids.return_value = []

    notifier.notify("fulltime", _MATCH["id"], None)

    push_send_fn.assert_not_called()
    notifier._push_log_dao.log.assert_not_called()

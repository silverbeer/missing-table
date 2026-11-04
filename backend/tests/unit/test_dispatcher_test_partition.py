"""Dispatcher and the SB-591 test partition (SB-1534).

The dispatcher used to load the match with get_match_by_id's default
include_test=False, so every TSC rehearsal match was "not found" and no event
on one was ever sent. Now a test match is loaded, but it reaches only
followers who may see test content (admins and is_test users), and never a
club channel. Real matches are unchanged.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from notifications.dispatcher import Notifier
from notifications.preferences import DEFAULT_PREFERENCES
from notifications.web_push_sender import SendResult

pytestmark = [pytest.mark.unit, pytest.mark.backend]

_REAL = {
    "id": 777,
    "home_team_id": 10,
    "away_team_id": 20,
    "home_team_name": "TSC B-Team",
    "away_team_name": "TSC A-Team",
    "home_score": 1,
    "away_score": 0,
    "home_team_club": {"id": 1},
    "away_team_club": {"id": 2},
    "is_test": False,
}
_TEST = {**_REAL, "is_test": True}

# u-admin is an admin, u-tester an is_test user, u-real a real user.
_PROFILES = [
    {"id": "u-admin", "role": "admin", "is_test": False},
    {"id": "u-tester", "role": "team-fan", "is_test": True},
    {"id": "u-real", "role": "team-fan", "is_test": False},
]
_FOLLOWERS = ["u-admin", "u-real", "u-tester"]


def _ok(*_args):
    return SendResult(status="sent", http_status=200)


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr("notifications.dispatcher.push_is_configured", lambda: True)
    monkeypatch.setattr("notifications.dispatcher.apns_is_configured", lambda: True)
    monkeypatch.setattr("notifications.dispatcher.fcm_is_configured", lambda: True)
    monkeypatch.setattr(
        "notifications.dispatcher.resolve_destinations",
        lambda *_a: [("telegram", "chat-1")],
    )


def _notifier(match, profiles=_PROFILES, profile_error=None):
    send_fn = MagicMock()
    push_fn = MagicMock(side_effect=_ok)
    apns_fn = MagicMock(side_effect=_ok)
    fcm_fn = MagicMock(side_effect=_ok)
    n = Notifier(send_fn=send_fn, push_send_fn=push_fn, apns_send_fn=apns_fn, fcm_send_fn=fcm_fn)

    n._match_dao = MagicMock()
    n._match_dao.get_match_by_id.return_value = match
    n._notif_dao = MagicMock()

    query = MagicMock()
    query.select.return_value.in_.return_value.execute.return_value = MagicMock(data=profiles)
    if profile_error:
        query.select.return_value.in_.return_value.execute.side_effect = profile_error
    client = MagicMock()
    client.table.return_value = query
    n._connection = MagicMock()
    n._connection.get_client.return_value = client

    n._team_follow_dao = MagicMock()
    n._team_follow_dao.list_subscriptions_for_team_ids.return_value = [
        {"id": f"sub-{u}", "user_id": u, "endpoint": f"https://push/{u}", "p256dh_key": "k", "auth_key": "a"}
        for u in _FOLLOWERS
    ]
    n._team_follow_dao.list_user_ids_for_team_ids.return_value = list(_FOLLOWERS)
    n._bracket_follow_dao = MagicMock()
    n._bracket_follow_dao.list_subscriptions_for_bracket.return_value = []
    n._bracket_follow_dao.list_user_ids_for_bracket.return_value = []

    n._apns_device_dao = MagicMock()
    n._apns_device_dao.list_for_user_ids.side_effect = lambda ids: [
        {"id": f"a-{u}", "user_id": u, "device_token": "aa" * 32, "environment": "production"} for u in ids
    ]
    n._fcm_device_dao = MagicMock()
    n._fcm_device_dao.list_for_user_ids.side_effect = lambda ids: [
        {"id": f"f-{u}", "user_id": u, "fid": f"fid-{u}"} for u in ids
    ]
    n._prefs_dao = MagicMock()
    n._prefs_dao.get_preferences_batch.side_effect = lambda ids: {u: dict(DEFAULT_PREFERENCES) for u in ids}
    n._push_log_dao = MagicMock()
    n._push_sub_dao = MagicMock()
    return n, send_fn, push_fn, apns_fn, fcm_fn


def _users(send_fn):
    return sorted(call.args[0]["user_id"] for call in send_fn.call_args_list)


def test_match_is_loaded_including_test_partition():
    n, *_ = _notifier(_TEST)
    n.notify("goal", 777, {"team": "home", "player_name": "Smith", "minute": 12})
    n._match_dao.get_match_by_id.assert_called_once_with(777, include_test=True)


def test_test_match_reaches_only_test_content_viewers():
    n, _, push_fn, apns_fn, fcm_fn = _notifier(_TEST)
    n.notify("goal", 777, {"team": "home", "player_name": "Smith", "minute": 12})

    assert _users(push_fn) == ["u-admin", "u-tester"]
    assert _users(apns_fn) == ["u-admin", "u-tester"]
    assert _users(fcm_fn) == ["u-admin", "u-tester"]


def test_test_match_never_reaches_club_channels():
    n, send_fn, *_ = _notifier(_TEST)
    n.notify("goal", 777, {"team": "home", "player_name": "Smith", "minute": 12})
    send_fn.assert_not_called()


def test_test_match_preferences_still_apply():
    n, _, _, _, fcm_fn = _notifier(_TEST)
    n._prefs_dao.get_preferences_batch.side_effect = lambda ids: {
        u: {**DEFAULT_PREFERENCES, "goal": u != "u-admin"} for u in ids
    }
    n.notify("goal", 777, {"team": "home", "player_name": "Smith", "minute": 12})
    assert _users(fcm_fn) == ["u-tester"]


def test_profile_lookup_failure_fails_closed():
    n, _, push_fn, apns_fn, fcm_fn = _notifier(_TEST, profile_error=RuntimeError("db down"))
    n.notify("goal", 777, {"team": "home", "player_name": "Smith", "minute": 12})

    push_fn.assert_not_called()
    apns_fn.assert_not_called()
    fcm_fn.assert_not_called()


def test_real_match_is_unchanged():
    n, send_fn, push_fn, apns_fn, fcm_fn = _notifier(_REAL)
    n.notify("goal", 777, {"team": "home", "player_name": "Smith", "minute": 12})

    send_fn.assert_called_once()
    assert _users(push_fn) == _FOLLOWERS
    assert _users(apns_fn) == _FOLLOWERS
    assert _users(fcm_fn) == _FOLLOWERS
    # No profile lookup for a real match: the hot path stays one query lighter.
    tables = [c.args[0] for c in n._connection.get_client.return_value.table.call_args_list]
    assert "user_profiles" not in tables

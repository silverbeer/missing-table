"""Dispatcher APNs fan-out tests (SB-1236).

The native iOS fan-out reaches the same followers as Web Push, through the
same preference gate and bracket rule, and leaves the web path untouched.
DB-touching DAOs are mocked; senders are injected.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from notifications.dispatcher import Notifier
from notifications.preferences import DEFAULT_PREFERENCES
from notifications.web_push_sender import SendResult

pytestmark = [pytest.mark.unit, pytest.mark.backend]

_MATCH = {
    "id": 555,
    "home_team_id": 10,
    "away_team_id": 20,
    "home_team_name": "IFA",
    "away_team_name": "NEFC",
    "home_score": 1,
    "away_score": 0,
    "home_team_club": None,
    "away_team_club": None,
}

_WEB_SUB = {"id": "sub-1", "user_id": "u-1", "endpoint": "https://push/x", "p256dh_key": "k", "auth_key": "a"}


def _dev(dev_id, user_id, token=None):
    return {
        "id": dev_id,
        "user_id": user_id,
        "device_token": token or (dev_id * 32)[:64],
        "environment": "production",
        "bundle_id": "com.missingtable",
    }


def _ok(*_args):
    return SendResult(status="sent", http_status=200)


@pytest.fixture
def configured(monkeypatch):
    def _set(web=True, apns=True):
        monkeypatch.setattr("notifications.dispatcher.push_is_configured", lambda: web)
        monkeypatch.setattr("notifications.dispatcher.apns_is_configured", lambda: apns)

    _set()
    return _set


def _notifier(match=None, follower_ids=("u-1",), devices=None, prefs=None, web_subs=(_WEB_SUB,), apns_fn=None):
    push_send_fn = MagicMock(side_effect=_ok)
    apns_send_fn = apns_fn or MagicMock(side_effect=_ok)
    notifier = Notifier(send_fn=MagicMock(), push_send_fn=push_send_fn, apns_send_fn=apns_send_fn)

    notifier._match_dao = MagicMock()
    notifier._match_dao.get_match_by_id.return_value = match or _MATCH
    notifier._notif_dao = MagicMock()
    notifier._notif_dao.list_by_club.return_value = []
    notifier._connection = MagicMock()

    notifier._team_follow_dao = MagicMock()
    notifier._team_follow_dao.list_subscriptions_for_team_ids.return_value = list(web_subs)
    notifier._team_follow_dao.list_user_ids_for_team_ids.return_value = list(follower_ids)
    notifier._bracket_follow_dao = MagicMock()
    notifier._bracket_follow_dao.list_subscriptions_for_bracket.return_value = []
    notifier._bracket_follow_dao.list_user_ids_for_bracket.return_value = []

    notifier._apns_device_dao = MagicMock()
    notifier._apns_device_dao.list_for_user_ids.return_value = [_dev("d1", "u-1")] if devices is None else devices
    notifier._prefs_dao = MagicMock()
    notifier._prefs_dao.get_preferences_batch.return_value = prefs or {"u-1": dict(DEFAULT_PREFERENCES)}
    notifier._push_log_dao = MagicMock()
    notifier._push_sub_dao = MagicMock()
    return notifier, push_send_fn, apns_send_fn


def _apns_log_calls(notifier):
    return [c for c in notifier._push_log_dao.log.call_args_list if c.kwargs.get("platform") == "apns"]


def _web_log_calls(notifier):
    return [c for c in notifier._push_log_dao.log.call_args_list if c.kwargs.get("platform") != "apns"]


class TestApnsFanout:
    def test_goal_reaches_follower_device(self, configured):
        notifier, _, apns_fn = _notifier()
        notifier.notify("goal", 555, {"team": "home", "player_name": "Smith", "minute": 12})

        apns_fn.assert_called_once()
        device, payload = apns_fn.call_args.args
        assert device["id"] == "d1"
        assert payload["data"]["matchId"] == 555
        assert payload["data"]["eventType"] == "goal"
        assert payload["tag"] == "match-555-goal"
        notifier._team_follow_dao.list_user_ids_for_team_ids.assert_called_once_with([10, 20])
        notifier._apns_device_dao.list_for_user_ids.assert_called_once_with(["u-1"])

    def test_send_is_logged_as_apns(self, configured):
        notifier, _, _ = _notifier()
        notifier.notify("fulltime", 555, None)

        [call] = _apns_log_calls(notifier)
        assert call.kwargs["subscription_id"] is None
        assert call.kwargs["apns_device_id"] == "d1"
        assert call.kwargs["user_id"] == "u-1"
        assert call.kwargs["match_id"] == 555
        assert call.kwargs["event_type"] == "fulltime"
        assert call.kwargs["status"] == "sent"

    def test_each_device_of_each_follower_gets_one_push(self, configured):
        devices = [_dev("d1", "u-1"), _dev("d2", "u-1"), _dev("d3", "u-2")]
        prefs = {"u-1": dict(DEFAULT_PREFERENCES), "u-2": dict(DEFAULT_PREFERENCES)}
        notifier, _, apns_fn = _notifier(follower_ids=["u-2", "u-1"], devices=devices, prefs=prefs)
        notifier.notify("kickoff", 555, None)

        assert [c.args[0]["id"] for c in apns_fn.call_args_list] == ["d1", "d2", "d3"]
        notifier._apns_device_dao.list_for_user_ids.assert_called_once_with(["u-1", "u-2"])

    def test_opted_out_event_is_skipped(self, configured):
        prefs = {"u-1": {**DEFAULT_PREFERENCES, "goal": False}}
        notifier, _, apns_fn = _notifier(prefs=prefs)
        notifier.notify("goal", 555, {"team": "home"})

        apns_fn.assert_not_called()
        assert _apns_log_calls(notifier) == []

    def test_cards_default_off(self, configured):
        notifier, _, apns_fn = _notifier(prefs={})
        notifier.notify("yellow_card", 555, {"team": "home", "player_name": "Smith"})
        apns_fn.assert_not_called()

    def test_cards_sent_when_opted_in(self, configured):
        prefs = {"u-1": {**DEFAULT_PREFERENCES, "red_card": True}}
        notifier, _, apns_fn = _notifier(prefs=prefs)
        notifier.notify("red_card", 555, {"team": "home", "player_name": "Smith"})
        apns_fn.assert_called_once()

    def test_expired_token_is_deleted(self, configured):
        apns_fn = MagicMock(return_value=SendResult(status="expired", http_status=410, error="Unregistered"))
        notifier, _, _ = _notifier(devices=[_dev("d1", "u-1", token="ff" * 32)], apns_fn=apns_fn)
        notifier.notify("goal", 555, {"team": "home"})

        notifier._apns_device_dao.delete_by_token.assert_called_once_with("ff" * 32)
        [call] = _apns_log_calls(notifier)
        assert call.kwargs["status"] == "expired"
        assert call.kwargs["http_status"] == 410

    def test_failed_send_keeps_the_device(self, configured):
        apns_fn = MagicMock(return_value=SendResult(status="failed", http_status=500, error="HTTP 500"))
        notifier, _, _ = _notifier(apns_fn=apns_fn)
        notifier.notify("goal", 555, {"team": "home"})
        notifier._apns_device_dao.delete_by_token.assert_not_called()

    def test_not_configured_is_a_no_op(self, configured):
        configured(apns=False)
        notifier, push_fn, apns_fn = _notifier()
        notifier.notify("goal", 555, {"team": "home"})

        apns_fn.assert_not_called()
        notifier._apns_device_dao.list_for_user_ids.assert_not_called()
        notifier._team_follow_dao.list_user_ids_for_team_ids.assert_not_called()
        push_fn.assert_called_once()  # web unaffected

    def test_runs_without_web_push_configured(self, configured):
        configured(web=False)
        notifier, push_fn, apns_fn = _notifier()
        notifier.notify("goal", 555, {"team": "home"})
        push_fn.assert_not_called()
        apns_fn.assert_called_once()

    def test_no_followers_skips_device_lookup(self, configured):
        notifier, _, apns_fn = _notifier(follower_ids=[])
        notifier.notify("goal", 555, {"team": "home"})
        notifier._apns_device_dao.list_for_user_ids.assert_not_called()
        apns_fn.assert_not_called()

    def test_followers_without_devices_send_nothing(self, configured):
        notifier, _, apns_fn = _notifier(devices=[])
        notifier.notify("goal", 555, {"team": "home"})
        apns_fn.assert_not_called()

    def test_apns_failure_does_not_raise(self, configured):
        notifier, _, _ = _notifier()
        notifier._apns_device_dao.list_for_user_ids.side_effect = RuntimeError("boom")
        notifier.notify("goal", 555, {"team": "home"})  # must not raise


class TestBracketFollowers:
    _BRACKET_MATCH = {**_MATCH, "tournament_id": 7, "tournament_group": "Bracket A", "age_group_id": 3}

    def test_fulltime_adds_bracket_followers_deduped(self, configured):
        notifier, _, apns_fn = _notifier(
            match=self._BRACKET_MATCH,
            devices=[_dev("d1", "u-1"), _dev("d9", "u-9")],
            prefs={"u-1": dict(DEFAULT_PREFERENCES), "u-9": dict(DEFAULT_PREFERENCES)},
        )
        notifier._bracket_follow_dao.list_user_ids_for_bracket.return_value = ["u-9", "u-1"]
        notifier.notify("fulltime", 555, None)

        notifier._bracket_follow_dao.list_user_ids_for_bracket.assert_called_once_with(7, "Bracket A", 3)
        notifier._apns_device_dao.list_for_user_ids.assert_called_once_with(["u-1", "u-9"])
        assert apns_fn.call_count == 2

    def test_bracket_followers_not_used_before_fulltime(self, configured):
        notifier, _, _ = _notifier(match=self._BRACKET_MATCH)
        notifier.notify("goal", 555, {"team": "home"})
        notifier._bracket_follow_dao.list_user_ids_for_bracket.assert_not_called()


class TestWebPathUnchanged:
    def test_web_send_and_log_are_as_before(self, configured):
        notifier, push_fn, _ = _notifier()
        notifier.notify("goal", 555, {"team": "home"})

        push_fn.assert_called_once()
        assert push_fn.call_args.args[0] == _WEB_SUB
        [call] = _web_log_calls(notifier)
        # Exactly the pre-SB-1236 keyword set — no platform/apns fields.
        assert set(call.kwargs) == {
            "subscription_id",
            "user_id",
            "match_id",
            "event_type",
            "status",
            "http_status",
            "error",
        }
        assert call.kwargs["subscription_id"] == "sub-1"

    def test_web_and_apns_get_the_same_payload(self, configured):
        notifier, push_fn, apns_fn = _notifier()
        notifier.notify("halftime", 555, None)
        assert push_fn.call_args.args[1] == apns_fn.call_args.args[1]

    def test_web_expiry_still_deletes_subscription(self, configured):
        notifier, push_fn, _ = _notifier()
        push_fn.side_effect = None
        push_fn.return_value = SendResult(status="expired", http_status=410)
        notifier.notify("goal", 555, {"team": "home"})
        notifier._push_sub_dao.delete_by_endpoint.assert_called_once_with("https://push/x")
        notifier._apns_device_dao.delete_by_token.assert_not_called()

"""Dispatcher FCM fan-out tests (SB-1463).

The native Android fan-out reaches the same followers as APNs, through the
same preference gate and bracket rule, and leaves the web and APNs paths
untouched. DB-touching DAOs are mocked; senders are injected.
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


def _dev(dev_id, user_id, fid=None):
    return {"id": dev_id, "user_id": user_id, "fid": fid or f"fid-{dev_id}"}


def _apns_dev(dev_id, user_id):
    return {"id": dev_id, "user_id": user_id, "device_token": "aa" * 32, "environment": "production"}


def _ok(*_args):
    return SendResult(status="sent", http_status=200)


@pytest.fixture
def configured(monkeypatch):
    def _set(web=True, apns=True, fcm=True):
        monkeypatch.setattr("notifications.dispatcher.push_is_configured", lambda: web)
        monkeypatch.setattr("notifications.dispatcher.apns_is_configured", lambda: apns)
        monkeypatch.setattr("notifications.dispatcher.fcm_is_configured", lambda: fcm)

    _set()
    return _set


def _notifier(match=None, follower_ids=("u-1",), devices=None, prefs=None, fcm_fn=None):
    push_send_fn = MagicMock(side_effect=_ok)
    apns_send_fn = MagicMock(side_effect=_ok)
    fcm_send_fn = fcm_fn or MagicMock(side_effect=_ok)
    notifier = Notifier(
        send_fn=MagicMock(),
        push_send_fn=push_send_fn,
        apns_send_fn=apns_send_fn,
        fcm_send_fn=fcm_send_fn,
    )

    notifier._match_dao = MagicMock()
    notifier._match_dao.get_match_by_id.return_value = match or _MATCH
    notifier._notif_dao = MagicMock()
    notifier._notif_dao.list_by_club.return_value = []
    notifier._connection = MagicMock()

    notifier._team_follow_dao = MagicMock()
    notifier._team_follow_dao.list_subscriptions_for_team_ids.return_value = [_WEB_SUB]
    notifier._team_follow_dao.list_user_ids_for_team_ids.return_value = list(follower_ids)
    notifier._bracket_follow_dao = MagicMock()
    notifier._bracket_follow_dao.list_subscriptions_for_bracket.return_value = []
    notifier._bracket_follow_dao.list_user_ids_for_bracket.return_value = []

    notifier._apns_device_dao = MagicMock()
    notifier._apns_device_dao.list_for_user_ids.return_value = [_apns_dev("a1", "u-1")]
    notifier._fcm_device_dao = MagicMock()
    notifier._fcm_device_dao.list_for_user_ids.return_value = [_dev("f1", "u-1")] if devices is None else devices
    notifier._prefs_dao = MagicMock()
    notifier._prefs_dao.get_preferences_batch.return_value = prefs or {"u-1": dict(DEFAULT_PREFERENCES)}
    notifier._push_log_dao = MagicMock()
    notifier._push_sub_dao = MagicMock()
    return notifier, push_send_fn, apns_send_fn, fcm_send_fn


def _log_calls(notifier, platform):
    return [c for c in notifier._push_log_dao.log.call_args_list if c.kwargs.get("platform") == platform]


class TestFcmFanout:
    def test_goal_reaches_follower_device(self, configured):
        notifier, _, _, fcm_fn = _notifier()
        notifier.notify("goal", 555, {"team": "home", "player_name": "Smith", "minute": 12})

        fcm_fn.assert_called_once()
        device, payload = fcm_fn.call_args.args
        assert device["id"] == "f1"
        assert payload["data"]["matchId"] == 555
        assert payload["data"]["eventType"] == "goal"
        assert payload["tag"] == "match-555-goal"
        notifier._fcm_device_dao.list_for_user_ids.assert_called_once_with(["u-1"])

    def test_send_is_logged_as_fcm(self, configured):
        notifier, _, _, _ = _notifier()
        notifier.notify("fulltime", 555, None)

        [call] = _log_calls(notifier, "fcm")
        assert call.kwargs["subscription_id"] is None
        assert call.kwargs["fcm_device_id"] == "f1"
        assert "apns_device_id" not in call.kwargs
        assert call.kwargs["user_id"] == "u-1"
        assert call.kwargs["match_id"] == 555
        assert call.kwargs["event_type"] == "fulltime"
        assert call.kwargs["status"] == "sent"

    def test_each_device_of_each_follower_gets_one_push(self, configured):
        devices = [_dev("f1", "u-1"), _dev("f2", "u-1"), _dev("f3", "u-2")]
        prefs = {"u-1": dict(DEFAULT_PREFERENCES), "u-2": dict(DEFAULT_PREFERENCES)}
        notifier, _, _, fcm_fn = _notifier(follower_ids=["u-2", "u-1"], devices=devices, prefs=prefs)
        notifier.notify("kickoff", 555, None)

        assert [c.args[0]["id"] for c in fcm_fn.call_args_list] == ["f1", "f2", "f3"]
        notifier._fcm_device_dao.list_for_user_ids.assert_called_once_with(["u-1", "u-2"])

    def test_opted_out_event_is_skipped(self, configured):
        prefs = {"u-1": {**DEFAULT_PREFERENCES, "goal": False}}
        notifier, _, _, fcm_fn = _notifier(prefs=prefs)
        notifier.notify("goal", 555, {"team": "home"})

        fcm_fn.assert_not_called()
        assert _log_calls(notifier, "fcm") == []

    def test_cards_default_off(self, configured):
        notifier, _, _, fcm_fn = _notifier(prefs={})
        notifier.notify("yellow_card", 555, {"team": "home", "player_name": "Smith"})
        fcm_fn.assert_not_called()

    def test_cards_sent_when_opted_in(self, configured):
        prefs = {"u-1": {**DEFAULT_PREFERENCES, "red_card": True}}
        notifier, _, _, fcm_fn = _notifier(prefs=prefs)
        notifier.notify("red_card", 555, {"team": "home", "player_name": "Smith"})
        fcm_fn.assert_called_once()

    def test_expired_installation_is_deleted(self, configured):
        fcm_fn = MagicMock(return_value=SendResult(status="expired", http_status=404, error="UNREGISTERED"))
        notifier, _, _, _ = _notifier(devices=[_dev("f1", "u-1", fid="dead-fid")], fcm_fn=fcm_fn)
        notifier.notify("goal", 555, {"team": "home"})

        notifier._fcm_device_dao.delete_by_fid.assert_called_once_with("dead-fid")
        notifier._apns_device_dao.delete_by_token.assert_not_called()
        [call] = _log_calls(notifier, "fcm")
        assert call.kwargs["status"] == "expired"
        assert call.kwargs["http_status"] == 404

    def test_failed_send_keeps_the_device(self, configured):
        fcm_fn = MagicMock(return_value=SendResult(status="failed", http_status=503, error="HTTP 503"))
        notifier, _, _, _ = _notifier(fcm_fn=fcm_fn)
        notifier.notify("goal", 555, {"team": "home"})
        notifier._fcm_device_dao.delete_by_fid.assert_not_called()

    def test_not_configured_is_a_silent_no_op(self, configured, monkeypatch):
        configured(fcm=False)
        log = MagicMock()
        monkeypatch.setattr("notifications.dispatcher.logger", log)
        notifier, push_fn, apns_fn, fcm_fn = _notifier()
        notifier.notify("goal", 555, {"team": "home"})

        fcm_fn.assert_not_called()
        notifier._fcm_device_dao.list_for_user_ids.assert_not_called()
        assert _log_calls(notifier, "fcm") == []
        push_fn.assert_called_once()  # web unaffected
        apns_fn.assert_called_once()  # APNs unaffected
        events = [c.args[0] for m in (log.info, log.warning, log.error) for c in m.call_args_list]
        assert not [e for e in events if "fcm" in e]

    def test_runs_when_fcm_is_the_only_channel(self, configured):
        configured(web=False, apns=False)
        notifier, push_fn, apns_fn, fcm_fn = _notifier()
        notifier.notify("goal", 555, {"team": "home"})
        push_fn.assert_not_called()
        apns_fn.assert_not_called()
        fcm_fn.assert_called_once()

    def test_no_followers_skips_device_lookup(self, configured):
        notifier, _, _, fcm_fn = _notifier(follower_ids=[])
        notifier.notify("goal", 555, {"team": "home"})
        notifier._fcm_device_dao.list_for_user_ids.assert_not_called()
        fcm_fn.assert_not_called()

    def test_followers_without_devices_send_nothing(self, configured):
        notifier, _, _, fcm_fn = _notifier(devices=[])
        notifier.notify("goal", 555, {"team": "home"})
        fcm_fn.assert_not_called()

    def test_fcm_failure_does_not_raise_or_affect_apns(self, configured):
        notifier, _, apns_fn, _ = _notifier()
        notifier._fcm_device_dao.list_for_user_ids.side_effect = RuntimeError("boom")
        notifier.notify("goal", 555, {"team": "home"})  # must not raise
        apns_fn.assert_called_once()

    def test_apns_failure_does_not_block_fcm(self, configured):
        notifier, _, _, fcm_fn = _notifier()
        notifier._apns_device_dao.list_for_user_ids.side_effect = RuntimeError("boom")
        notifier.notify("goal", 555, {"team": "home"})
        fcm_fn.assert_called_once()


class TestMassExpiryGuard:
    _EXPIRED = SendResult(status="expired", http_status=404, error="UNREGISTERED")

    def _three(self):
        devices = [_dev("f1", "u-1"), _dev("f2", "u-1"), _dev("f3", "u-2")]
        prefs = {"u-1": dict(DEFAULT_PREFERENCES), "u-2": dict(DEFAULT_PREFERENCES)}
        return devices, prefs

    def test_all_expired_in_a_fanout_of_three_prunes_nothing(self, configured, monkeypatch):
        log = MagicMock()
        monkeypatch.setattr("notifications.dispatcher.logger", log)
        devices, prefs = self._three()
        fcm_fn = MagicMock(return_value=self._EXPIRED)
        notifier, _, _, _ = _notifier(follower_ids=["u-1", "u-2"], devices=devices, prefs=prefs, fcm_fn=fcm_fn)
        notifier.notify("goal", 555, {"team": "home"})

        notifier._fcm_device_dao.delete_by_fid.assert_not_called()
        warned = [c for c in log.warning.call_args_list if c.args[0] == "notifications.fcm_mass_expiry_suspected"]
        assert len(warned) == 1
        assert warned[0].kwargs["expired"] == 3
        # Every send is still logged as expired.
        assert [c.kwargs["status"] for c in _log_calls(notifier, "fcm")] == ["expired"] * 3

    def test_partial_expiry_in_a_large_fanout_still_prunes(self, configured):
        devices, prefs = self._three()
        fcm_fn = MagicMock(side_effect=[self._EXPIRED, _ok(), self._EXPIRED])
        notifier, _, _, _ = _notifier(follower_ids=["u-1", "u-2"], devices=devices, prefs=prefs, fcm_fn=fcm_fn)
        notifier.notify("goal", 555, {"team": "home"})

        deleted = [c.args[0] for c in notifier._fcm_device_dao.delete_by_fid.call_args_list]
        assert deleted == ["fid-f1", "fid-f3"]

    def test_all_expired_in_a_small_fanout_prunes(self, configured):
        devices = [_dev("f1", "u-1"), _dev("f2", "u-1")]
        fcm_fn = MagicMock(return_value=self._EXPIRED)
        notifier, _, _, _ = _notifier(devices=devices, fcm_fn=fcm_fn)
        notifier.notify("goal", 555, {"team": "home"})
        assert notifier._fcm_device_dao.delete_by_fid.call_count == 2


class TestSharedAudience:
    def test_follow_and_prefs_lookups_run_once_for_both_native_channels(self, configured):
        configured(web=False)  # web push has its own prefs batch; isolate the native path
        notifier, _, apns_fn, fcm_fn = _notifier()
        notifier.notify("goal", 555, {"team": "home"})

        apns_fn.assert_called_once()
        fcm_fn.assert_called_once()
        notifier._team_follow_dao.list_user_ids_for_team_ids.assert_called_once_with([10, 20])
        notifier._prefs_dao.get_preferences_batch.assert_called_once()

    def test_bracket_lookup_runs_once_at_fulltime(self, configured):
        match = {**_MATCH, "tournament_id": 7, "tournament_group": "Bracket A", "age_group_id": 3}
        notifier, _, _, _ = _notifier(match=match)
        notifier.notify("fulltime", 555, None)
        notifier._bracket_follow_dao.list_user_ids_for_bracket.assert_called_once_with(7, "Bracket A", 3)

    def test_neither_native_channel_skips_the_lookup(self, configured):
        configured(apns=False, fcm=False)
        notifier, push_fn, _, _ = _notifier()
        notifier.notify("goal", 555, {"team": "home"})
        notifier._team_follow_dao.list_user_ids_for_team_ids.assert_not_called()
        push_fn.assert_called_once()


class TestBracketFollowers:
    _BRACKET_MATCH = {**_MATCH, "tournament_id": 7, "tournament_group": "Bracket A", "age_group_id": 3}

    def test_fulltime_adds_bracket_followers_deduped(self, configured):
        configured(apns=False)
        notifier, _, _, fcm_fn = _notifier(
            match=self._BRACKET_MATCH,
            devices=[_dev("f1", "u-1"), _dev("f9", "u-9")],
            prefs={"u-1": dict(DEFAULT_PREFERENCES), "u-9": dict(DEFAULT_PREFERENCES)},
        )
        notifier._bracket_follow_dao.list_user_ids_for_bracket.return_value = ["u-9", "u-1"]
        notifier.notify("fulltime", 555, None)

        notifier._bracket_follow_dao.list_user_ids_for_bracket.assert_called_once_with(7, "Bracket A", 3)
        notifier._fcm_device_dao.list_for_user_ids.assert_called_once_with(["u-1", "u-9"])
        assert fcm_fn.call_count == 2

    def test_bracket_followers_not_used_before_fulltime(self, configured):
        notifier, _, _, _ = _notifier(match=self._BRACKET_MATCH)
        notifier.notify("goal", 555, {"team": "home"})
        notifier._bracket_follow_dao.list_user_ids_for_bracket.assert_not_called()


class TestOtherPathsUnchanged:
    def test_all_three_channels_get_the_same_payload(self, configured):
        notifier, push_fn, apns_fn, fcm_fn = _notifier()
        notifier.notify("halftime", 555, None)
        assert push_fn.call_args.args[1] == apns_fn.call_args.args[1] == fcm_fn.call_args.args[1]

    def test_apns_log_has_no_fcm_fields(self, configured):
        notifier, _, _, _ = _notifier()
        notifier.notify("goal", 555, {"team": "home"})
        [call] = _log_calls(notifier, "apns")
        assert "fcm_device_id" not in call.kwargs
        assert call.kwargs["apns_device_id"] == "a1"

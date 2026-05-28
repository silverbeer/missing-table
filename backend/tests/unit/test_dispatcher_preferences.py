"""Dispatcher preference-filter tests (SB-57).

Verifies that `Notifier._send_push_fanout` respects per-user opt-in flags:
  - Cards default OFF → no push for users with no prefs row.
  - Cards opted ON → push sent.
  - Goal opted OFF → push skipped even though it's a default-on event.
  - The hard-coded yellow/red short-circuit is gone — every event type
    flows through the same prefs gate.
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


def _make_notifier(
    subscriptions: list[dict], prefs_by_user: dict[str, dict[str, bool]]
) -> tuple[Notifier, MagicMock]:
    """Wire up a Notifier whose resolve_user_push_subscriptions returns
    the given list and whose prefs_dao.get_preferences_batch returns the
    given dict. push_log_dao + push_sub_dao are mocked so nothing hits
    the DB.
    """
    push_send_fn = MagicMock(side_effect=_send_ok)
    notifier = Notifier(push_send_fn=push_send_fn)

    # Stub out the bits that would hit the DB or env.
    notifier._prefs_dao = MagicMock()
    notifier._prefs_dao.get_preferences_batch.return_value = prefs_by_user
    notifier._push_log_dao = MagicMock()
    notifier._push_sub_dao = MagicMock()
    notifier._team_follow_dao = MagicMock()

    return notifier, push_send_fn


@pytest.fixture
def match_payload() -> dict:
    return {
        "id": 12345,
        "home_team_id": 1,
        "away_team_id": 2,
    }


@pytest.fixture(autouse=True)
def _force_push_configured(monkeypatch):
    """Pretend VAPID is configured so the fanout doesn't short-circuit."""
    monkeypatch.setattr(
        "notifications.dispatcher.push_is_configured", lambda: True
    )


def _patch_resolver(monkeypatch, subs):
    monkeypatch.setattr(
        "notifications.dispatcher.resolve_user_push_subscriptions",
        lambda *_args, **_kwargs: subs,
    )


class TestCardsRespectPreferences:
    def test_yellow_card_skipped_for_user_with_defaults(
        self, monkeypatch, match_payload
    ):
        subs = [
            {"id": "sub-1", "user_id": "u-default", "endpoint": "https://x", "p256dh_key": "k", "auth_key": "a"},
        ]
        _patch_resolver(monkeypatch, subs)
        notifier, push_send_fn = _make_notifier(
            subs, {"u-default": dict(DEFAULT_PREFERENCES)}
        )

        notifier._send_push_fanout("yellow_card", match_payload, "Yellow card!\nFoo Bar")

        # Default has yellow_card=False → no send.
        push_send_fn.assert_not_called()

    def test_yellow_card_sent_when_opted_in(self, monkeypatch, match_payload):
        subs = [
            {"id": "sub-1", "user_id": "u-yes", "endpoint": "https://x", "p256dh_key": "k", "auth_key": "a"},
        ]
        _patch_resolver(monkeypatch, subs)
        notifier, push_send_fn = _make_notifier(
            subs, {"u-yes": {**DEFAULT_PREFERENCES, "yellow_card": True}}
        )

        notifier._send_push_fanout("yellow_card", match_payload, "Yellow card!\nFoo Bar")

        push_send_fn.assert_called_once()

    def test_red_card_treated_the_same(self, monkeypatch, match_payload):
        subs = [
            {"id": "sub-1", "user_id": "u-red", "endpoint": "https://x", "p256dh_key": "k", "auth_key": "a"},
        ]
        _patch_resolver(monkeypatch, subs)
        notifier, push_send_fn = _make_notifier(
            subs, {"u-red": {**DEFAULT_PREFERENCES, "red_card": True}}
        )

        notifier._send_push_fanout("red_card", match_payload, "Red card!\nFoo Bar")

        push_send_fn.assert_called_once()


class TestDefaultOnEventsRespectOptOut:
    def test_goal_skipped_when_user_opted_out(self, monkeypatch, match_payload):
        subs = [
            {"id": "sub-1", "user_id": "u-noisy", "endpoint": "https://x", "p256dh_key": "k", "auth_key": "a"},
        ]
        _patch_resolver(monkeypatch, subs)
        notifier, push_send_fn = _make_notifier(
            subs, {"u-noisy": {**DEFAULT_PREFERENCES, "goal": False}}
        )

        notifier._send_push_fanout("goal", match_payload, "GOAL!\nFoo Bar")

        push_send_fn.assert_not_called()

    def test_kickoff_fires_with_defaults(self, monkeypatch, match_payload):
        subs = [
            {"id": "sub-1", "user_id": "u-default", "endpoint": "https://x", "p256dh_key": "k", "auth_key": "a"},
        ]
        _patch_resolver(monkeypatch, subs)
        notifier, push_send_fn = _make_notifier(
            subs, {"u-default": dict(DEFAULT_PREFERENCES)}
        )

        notifier._send_push_fanout("kickoff", match_payload, "KICKOFF\nFoo Bar")

        push_send_fn.assert_called_once()


class TestMixedFanout:
    def test_two_users_one_opted_out(self, monkeypatch, match_payload):
        subs = [
            {"id": "sub-A", "user_id": "u-on", "endpoint": "https://a", "p256dh_key": "k", "auth_key": "a"},
            {"id": "sub-B", "user_id": "u-off", "endpoint": "https://b", "p256dh_key": "k", "auth_key": "a"},
        ]
        _patch_resolver(monkeypatch, subs)
        notifier, push_send_fn = _make_notifier(
            subs,
            {
                "u-on": dict(DEFAULT_PREFERENCES),
                "u-off": {**DEFAULT_PREFERENCES, "goal": False},
            },
        )

        notifier._send_push_fanout("goal", match_payload, "GOAL!\nFoo")

        assert push_send_fn.call_count == 1
        sent_sub = push_send_fn.call_args.args[0]
        assert sent_sub["id"] == "sub-A"

    def test_user_with_no_prefs_row_uses_defaults(
        self, monkeypatch, match_payload
    ):
        """A user who never touched prefs should keep current behavior — goal
        fires, cards don't. The dispatcher gets DEFAULT_PREFERENCES back from
        the DAO for unknown users."""
        subs = [
            {"id": "sub-new", "user_id": "u-new", "endpoint": "https://x", "p256dh_key": "k", "auth_key": "a"},
        ]
        _patch_resolver(monkeypatch, subs)
        # Simulate the batch DAO behavior: missing user → defaults filled in.
        notifier, push_send_fn = _make_notifier(
            subs, {"u-new": dict(DEFAULT_PREFERENCES)}
        )

        notifier._send_push_fanout("fulltime", match_payload, "FT\nFoo")
        assert push_send_fn.call_count == 1

        push_send_fn.reset_mock()
        notifier._send_push_fanout("red_card", match_payload, "Red\nFoo")
        push_send_fn.assert_not_called()


class TestNoFanoutWhenPushUnconfigured:
    def test_short_circuits_when_vapid_unset(
        self, monkeypatch, match_payload
    ):
        monkeypatch.setattr(
            "notifications.dispatcher.push_is_configured", lambda: False
        )
        subs = [
            {"id": "sub", "user_id": "u", "endpoint": "x", "p256dh_key": "k", "auth_key": "a"},
        ]
        _patch_resolver(monkeypatch, subs)
        notifier, push_send_fn = _make_notifier(
            subs, {"u": dict(DEFAULT_PREFERENCES)}
        )

        notifier._send_push_fanout("goal", match_payload, "GOAL\nFoo")
        push_send_fn.assert_not_called()
        # And no batch query when nothing's getting sent.
        notifier._prefs_dao.get_preferences_batch.assert_not_called()

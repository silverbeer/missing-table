"""One post per channel per event (SB-1603)."""

from unittest.mock import MagicMock

import pytest

from dao.notification_deliveries_dao import DeliveryLedgerError
from notifications.adapters.base import DeliveryError, DeliveryResult
from notifications.channel_resolver import ResolvedChannel
from notifications.dispatcher import Notifier
from notifications.event_keys import clock_event_key, fulltime_event_key, recorded_event_key

DESTINATION = "chat-private-1"
CHANNEL = ResolvedChannel("discord", DESTINATION, 7)


class FakeLedger:
    def __init__(self):
        self.keys = set()
        self.sent = {}
        self.failed = {}
        self.retry = {}
        self.content = {}

    def claim(self, channel_id, event_key, content=None, match_id=None, event_type=None):
        if (channel_id, event_key) in self.keys:
            return None
        self.keys.add((channel_id, event_key))
        self.content[len(self.keys)] = (content, match_id, event_type)
        return len(self.keys)

    def mark_retry(self, delivery_id, error, next_attempt_at):
        self.retry[delivery_id] = (error, next_attempt_at)

    def mark_sent(self, delivery_id, message_ref):
        self.sent[delivery_id] = message_ref

    def mark_failed(self, delivery_id, error):
        self.failed[delivery_id] = error


def notifier(send, ledger):
    n = Notifier(connection=MagicMock(), send_fn=send)
    n._delivery_dao = ledger
    return n


def post(n, key="match:1:kickoff"):
    return n._post_to_channel(CHANNEL, "hello", key, 1, "kickoff")


class TestEventKeys:
    def test_recorded_events_are_distinct(self):
        assert recorded_event_key(1, 10) != recorded_event_key(1, 11)

    def test_clock_event_is_stable(self):
        assert clock_event_key(1, "kickoff") == clock_event_key(1, "kickoff")

    def test_same_final_score_shares_a_key(self):
        assert fulltime_event_key(1, 2, 1) == fulltime_event_key(1, 2, 1)

    def test_corrected_score_is_a_new_key(self):
        assert fulltime_event_key(1, 2, 1) != fulltime_event_key(1, 2, 2)

    def test_null_scores_are_nil_nil(self):
        assert fulltime_event_key(1, None, None) == fulltime_event_key(1, 0, 0)


class TestPostToChannel:
    def test_records_the_provider_message_ref(self):
        ledger = FakeLedger()
        assert post(notifier(MagicMock(return_value=DeliveryResult("m1")), ledger)) == "sent"
        assert ledger.sent == {1: "m1"}

    def test_a_resent_event_posts_once(self):
        send = MagicMock(return_value=DeliveryResult())
        n = notifier(send, FakeLedger())
        assert post(n) == "sent"
        assert post(n) == "duplicate"
        send.assert_called_once()

    def test_a_different_event_still_posts(self):
        send = MagicMock(return_value=DeliveryResult())
        n = notifier(send, FakeLedger())
        post(n, "match:1:kickoff")
        assert post(n, "match:1:halftime") == "sent"
        assert send.call_count == 2

    def test_failure_is_recorded_and_not_reposted(self):
        send = MagicMock(side_effect=DeliveryError("discord send failed: HTTP 403"))
        ledger = FakeLedger()
        n = notifier(send, ledger)
        assert post(n) == "failed"
        assert ledger.failed == {1: "discord send failed: HTTP 403"}
        assert post(n) == "duplicate"

    def test_the_claim_keeps_the_message_for_a_retry(self):
        ledger = FakeLedger()
        post(notifier(MagicMock(return_value=DeliveryResult()), ledger))
        assert ledger.content[1] == ("hello", 1, "kickoff")

    def test_a_retryable_failure_is_left_for_the_worker(self):
        """SB-1604: a rate limit is retried later, not lost."""
        send = MagicMock(side_effect=DeliveryError("discord send failed: HTTP 429", retryable=True, retry_after=90))
        ledger = FakeLedger()
        assert post(notifier(send, ledger)) == "retrying"
        assert ledger.failed == {}
        error, next_at = ledger.retry[1]
        assert error == "discord send failed: HTTP 429"
        assert next_at  # ISO time, at least the provider's 90 s away

    def test_unknown_errors_store_only_their_type(self):
        ledger = FakeLedger()
        post(notifier(MagicMock(side_effect=RuntimeError(DESTINATION)), ledger))
        assert ledger.failed == {1: "RuntimeError"}

    def test_ledger_outage_does_not_lose_the_post(self):
        ledger = MagicMock()
        ledger.claim.side_effect = DeliveryLedgerError("down")
        send = MagicMock(return_value=DeliveryResult())
        assert post(notifier(send, ledger)) == "sent"
        send.assert_called_once()
        ledger.mark_sent.assert_not_called()

    def test_no_key_posts_without_the_ledger(self):
        ledger = MagicMock()
        send = MagicMock(return_value=DeliveryResult())
        assert post(notifier(send, ledger), None) == "sent"
        ledger.claim.assert_not_called()


def test_destination_is_not_passed_to_the_ledger():
    ledger = MagicMock()
    ledger.claim.return_value = 1
    post(notifier(MagicMock(return_value=DeliveryResult("m1")), ledger))
    recorded = repr(ledger.mock_calls)
    assert DESTINATION not in recorded


@pytest.mark.parametrize("ref", [None, "m1"])
def test_message_ref_is_optional(ref):
    ledger = FakeLedger()
    post(notifier(MagicMock(return_value=DeliveryResult(ref)), ledger))
    assert ledger.sent == {1: ref}

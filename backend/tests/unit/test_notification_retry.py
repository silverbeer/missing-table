"""Retrying chat posts (SB-1604): which failures retry, when, and the worker. No I/O."""

import random
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from notifications.adapters.base import DeliveryError, DeliveryResult, classify_failure
from notifications.retry_policy import MAX_ATTEMPTS, MAX_DELAY_SECONDS, next_attempt, retry_delay
from notifications.retry_worker import process_due

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 10, 12, tzinfo=UTC)


def _status_error(code, headers=None, body=None):
    request = httpx.Request("POST", "https://example.invalid/x")
    response = httpx.Response(code, headers=headers or {}, json=body if body is not None else {}, request=request)
    return httpx.HTTPStatusError("x", request=request, response=response)


class ProviderError(Exception):
    def __init__(self, response):
        super().__init__("provider")
        self.response = response


class TestClassify:
    def test_rate_limit_with_retry_after_header(self):
        assert classify_failure(_status_error(429, {"Retry-After": "12"})) == (True, 12.0)

    def test_telegram_rate_limit_in_the_body(self):
        assert classify_failure(_status_error(429, body={"parameters": {"retry_after": 7}})) == (True, 7.0)

    def test_discord_rate_limit_error_body(self):
        assert classify_failure(ProviderError({"message": "rate limited", "retry_after": 0.5})) == (True, 0.5)

    @pytest.mark.parametrize("code", [500, 502, 503])
    def test_server_errors_retry(self, code):
        assert classify_failure(_status_error(code))[0] is True

    @pytest.mark.parametrize("code", [400, 401, 403, 404])
    def test_client_errors_are_final(self, code):
        assert classify_failure(_status_error(code)) == (False, None)

    def test_network_errors_retry(self):
        assert classify_failure(httpx.ConnectTimeout("slow")) == (True, None)

    def test_unknown_errors_are_final(self):
        assert classify_failure(RuntimeError("?")) == (False, None)
        assert classify_failure(ProviderError({"message": "Unknown Webhook", "code": 10015})) == (False, None)


class TestPolicy:
    def test_backoff_doubles_and_is_capped(self):
        rand = random.Random(0)
        delays = [retry_delay(a, rand=rand) for a in range(1, 8)]
        assert delays[0] >= 30 and delays[1] >= 60 and delays[2] >= 120
        assert max(delays) <= MAX_DELAY_SECONDS * 1.1

    def test_retry_after_is_a_floor(self):
        assert retry_delay(1, retry_after=600, rand=random.Random(0)) == 600

    def test_gives_up_after_the_last_attempt(self):
        assert next_attempt(MAX_ATTEMPTS, True, None, NOW) is None
        assert next_attempt(MAX_ATTEMPTS - 1, True, None, NOW) > NOW

    def test_final_errors_never_retry(self):
        assert next_attempt(1, False, None, NOW) is None


# --- worker ---------------------------------------------------------------------


class Ledger:
    def __init__(self, rows):
        self.rows = rows
        self.sent, self.failed, self.retry = {}, {}, {}

    def claim_due(self, limit, lease, stale):
        rows, self.rows = self.rows, []
        return rows

    def mark_sent(self, i, ref):
        self.sent[i] = ref

    def mark_failed(self, i, error):
        self.failed[i] = error

    def mark_retry(self, i, error, at):
        self.retry[i] = (error, at)


class Channels:
    def __init__(self, channels):
        self.channels = channels

    def get_by_id(self, channel_id):
        return self.channels.get(channel_id)


def _row(i, channel_id=1, attempts=2):
    return {"id": i, "channel_id": channel_id, "content": f"post {i}", "attempts": attempts}


CHANNEL = {"platform": "discord", "destination": "https://discord.com/api/webhooks/1/x", "enabled": True}


def _run(rows, send, channels=None):
    ledger = Ledger(rows)
    with ThreadPoolExecutor(max_workers=4) as pool:
        started = process_due(ledger, Channels(channels or {1: CHANNEL}), send, pool, now_fn=lambda: NOW)
    return ledger, started  # leaving the with-block waits for every send


class TestWorker:
    def test_sends_and_records_each(self):
        sent = []

        def send(platform, destination, content):
            sent.append(content)
            return DeliveryResult(message_ref=f"m-{content}")

        ledger, started = _run([_row(1), _row(2)], send)
        assert started == 2
        assert sorted(sent) == ["post 1", "post 2"]
        assert ledger.sent == {1: "m-post 1", 2: "m-post 2"}

    def test_a_transient_failure_is_rescheduled(self):
        def send(*_):
            raise DeliveryError("discord send failed: HTTP 503", retryable=True)

        ledger, _ = _run([_row(1, attempts=2)], send)
        error, at = ledger.retry[1]
        assert error == "discord send failed: HTTP 503"
        assert datetime.fromisoformat(at) > NOW + timedelta(seconds=59)

    def test_the_last_attempt_fails_for_good(self):
        def send(*_):
            raise DeliveryError("discord send failed: HTTP 503", retryable=True)

        ledger, _ = _run([_row(1, attempts=MAX_ATTEMPTS)], send)
        assert ledger.failed == {1: "discord send failed: HTTP 503"}
        assert ledger.retry == {}

    def test_a_removed_or_paused_channel_is_not_posted_to(self):
        calls = []
        channels = {2: {**CHANNEL, "enabled": False}}
        ledger, started = _run([_row(1, channel_id=1), _row(2, channel_id=2)], lambda *a: calls.append(a), channels)
        assert started == 0 and calls == []
        assert set(ledger.failed) == {1, 2}

    def test_one_slow_destination_does_not_hold_up_the_others(self):
        import threading

        release = threading.Event()
        done = []

        def send(platform, destination, content):
            if content == "post 1":
                release.wait(2)  # the slow one
            done.append(content)
            return DeliveryResult()

        ledger = Ledger([_row(1), _row(2), _row(3)])
        pool = ThreadPoolExecutor(max_workers=4)
        process_due(ledger, Channels({1: CHANNEL}), send, pool, now_fn=lambda: NOW)
        deadline = datetime.now() + timedelta(seconds=2)
        while len(ledger.sent) < 2 and datetime.now() < deadline:
            pass
        assert set(ledger.sent) == {2, 3}  # recorded while post 1 is still sending
        release.set()
        pool.shutdown(wait=True)
        assert set(ledger.sent) == {1, 2, 3}

"""Match threads (SB-1606): one thread per match per channel. No I/O."""

from unittest.mock import MagicMock, patch

import pytest

from dao.notification_threads_dao import ThreadStoreError
from notifications.adapters.base import Capability, DeliveryError, DeliveryResult
from notifications.adapters.discord import DiscordAdapter
from notifications.formatters import thread_title
from notifications.threads import deliver_to_thread, send

pytestmark = pytest.mark.unit

DEST = "https://discord.com/api/webhooks/1/abc"


class Threads:
    """In-memory notification_threads with the unique (channel, match) lock."""

    def __init__(self):
        self.rows = {}
        self.released = []
        self.stale = set()

    def claim(self, channel_id, match_id, name):
        key = (channel_id, match_id)
        if key in self.rows:
            return False, self.rows[key]
        self.rows[key] = {"id": len(self.rows) + 1, "thread_name": name, "thread_ref": None, "key": key}
        return True, self.rows[key]

    def _by_id(self, i):
        return next(r for r in self.rows.values() if r["id"] == i)

    def take_over(self, i):
        row = self._by_id(i)
        return row if (i in self.stale and row["thread_ref"] is None) else None

    def set_ref(self, i, ref):
        self._by_id(i)["thread_ref"] = ref

    def release(self, i):
        self.released.append(i)
        self.stale.add(i)


def _adapter(results):
    adapter = MagicMock()
    adapter.capabilities = frozenset({Capability.THREADS})
    adapter.send_in_thread.side_effect = results
    return adapter


def _deliver(adapter, threads, name="IFA vs NEFC"):
    with patch("notifications.threads.get_adapter", return_value=adapter):
        return deliver_to_thread("discord", DEST, "⚽ GOAL", 7, 99, name, threads)


class TestDeliverToThread:
    def test_first_post_creates_the_thread_and_later_ones_reply(self):
        threads = Threads()
        adapter = _adapter([DeliveryResult("m1", "t-55"), DeliveryResult("m2", "t-55")])
        _deliver(adapter, threads)
        _deliver(adapter, threads)
        first, second = adapter.send_in_thread.call_args_list
        assert first.args == (DEST, "⚽ GOAL", None, "IFA vs NEFC")
        assert second.args == (DEST, "⚽ GOAL", "t-55", None)
        assert threads.rows[(7, 99)]["thread_ref"] == "t-55"

    def test_a_post_while_the_thread_is_being_created_waits(self):
        threads = Threads()
        threads.claim(7, 99, "IFA vs NEFC")  # someone else is creating it
        adapter = _adapter([])
        with pytest.raises(DeliveryError) as err:
            _deliver(adapter, threads)
        assert err.value.retryable and err.value.retry_after == 5
        adapter.send_in_thread.assert_not_called()

    def test_a_failed_creation_is_released_and_taken_over(self):
        threads = Threads()
        adapter = _adapter([DeliveryError("discord send failed: HTTP 503", retryable=True), DeliveryResult("m", "t-9")])
        with pytest.raises(DeliveryError):
            _deliver(adapter, threads)
        assert threads.released == [1]
        _deliver(adapter, threads)  # the retry takes over and creates it
        assert threads.rows[(7, 99)]["thread_ref"] == "t-9"
        assert adapter.send_in_thread.call_args.args[3] == "IFA vs NEFC"

    def test_no_thread_id_back_lets_the_next_post_start_one(self):
        threads = Threads()
        _deliver(_adapter([DeliveryResult("m", None)]), threads)
        assert threads.released == [1]

    def test_thread_store_down_still_posts(self):
        threads = MagicMock()
        threads.claim.side_effect = ThreadStoreError("down")
        adapter = _adapter([DeliveryResult("m", "t")])
        _deliver(adapter, threads)
        assert adapter.send_in_thread.call_args.args == (DEST, "⚽ GOAL", None, "IFA vs NEFC")


class TestSendDegrades:
    def _send(self, platform="discord", post_as_threads=True, match_id=99):
        flat = MagicMock(return_value=DeliveryResult())
        threads = Threads()
        with patch("notifications.threads.deliver_to_thread", return_value=DeliveryResult()) as threaded:
            send(
                flat,
                platform,
                DEST,
                "x",
                post_as_threads=post_as_threads,
                channel_id=1,
                match_id=match_id,
                thread_name="n",
                threads=threads,
            )
        return flat, threaded

    def test_threaded_channel_uses_threads(self):
        flat, threaded = self._send()
        threaded.assert_called_once()
        flat.assert_not_called()

    @pytest.mark.parametrize(
        "kwargs", [{"post_as_threads": False}, {"platform": "slack"}, {"platform": "telegram"}, {"match_id": None}]
    )
    def test_otherwise_flat(self, kwargs):
        flat, threaded = self._send(**kwargs)
        flat.assert_called_once()
        threaded.assert_not_called()


class TestDiscordThreadCall:
    def _post(self, json_body, thread_ref=None, name="IFA vs NEFC"):
        response = MagicMock(content=b"{}", status_code=200)
        response.json.return_value = json_body
        with patch("notifications.adapters.discord.httpx.post", return_value=response) as post:
            result = DiscordAdapter().send_in_thread(DEST, "hi", thread_ref, name)
        return post, result

    def test_new_post_sends_thread_name_and_waits(self):
        post, result = self._post({"id": "500", "channel_id": "777"})
        assert post.call_args.kwargs["params"] == {"wait": "true"}
        assert post.call_args.kwargs["json"] == {"content": "hi", "thread_name": "IFA vs NEFC"}
        assert (result.message_ref, result.thread_ref) == ("500", "777")

    def test_follow_up_targets_the_thread(self):
        post, result = self._post({"id": "501", "channel_id": "777"}, thread_ref="777", name=None)
        assert post.call_args.kwargs["params"] == {"wait": "true", "thread_id": "777"}
        assert "thread_name" not in post.call_args.kwargs["json"]
        assert result.thread_ref == "777"

    def test_discord_declares_threads(self):
        assert Capability.THREADS in DiscordAdapter.capabilities


def test_thread_title():
    from zoneinfo import ZoneInfo

    match = {
        "home_team_name": "IFA",
        "away_team_name": "NEFC",
        "age_group_name": "U15",
        "scheduled_kickoff": "2026-11-14T15:00:00+00:00",
    }
    assert thread_title(match, ZoneInfo("America/New_York")) == "IFA vs NEFC · U15 · Sat Nov 14"

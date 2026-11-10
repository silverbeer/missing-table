"""Deliver pending chat posts the live path could not finish (SB-1604).

The live path (Notifier._post_to_channel) sends each post once. A post that hit
a rate limit, a server error or a network failure is left `pending` in the
delivery ledger with a `next_attempt_at`; a post whose pod died mid-send is left
`pending` with none. This worker picks both up:

- `claim_due_notification_deliveries` hands out due rows atomically, counts the
  attempt and leases the row, so two pods never send the same post and a worker
  that dies mid-send leaves it to be retried.
- Sends run concurrently and each finishes on its own (a done-callback records
  it), so one slow destination cannot hold up the others.
- Backoff and the attempt limit come from retry_policy; after the last attempt
  the row is `failed` for good, which "Last post" shows to managers and admins.
- A channel removed or paused since the first try is not posted to.

It runs in a background thread of the backend process, never on a request, and
only when NOTIFICATION_RETRY_WORKER is on, so tests and local runs stay quiet.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from notifications.retry_policy import next_attempt

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)

BATCH_SIZE = 25
LEASE_SECONDS = 120  # longer than any one send can take
STALE_SECONDS = 120  # a first send this old never finished
INTERVAL_SECONDS = 15
MAX_CONCURRENT_SENDS = 8


def _safe_error(exc: BaseException) -> str:
    from notifications.dispatcher import _safe_error as safe

    return safe(exc)  # type: ignore[arg-type]


def _record(deliveries, row: dict, future: Future, now_fn: Callable[[], datetime]) -> None:
    """Write the outcome of one send. Called when its future completes."""
    delivery_id = row["id"]
    exc = future.exception()
    if exc is None:
        result = future.result()
        deliveries.mark_sent(delivery_id, getattr(result, "message_ref", None))
        logger.info("notifications.retry_sent", delivery_id=delivery_id, attempt=row.get("attempts"))
        return
    error = _safe_error(exc)
    retry_at = next_attempt(
        int(row.get("attempts") or 1),
        bool(getattr(exc, "retryable", False)),
        getattr(exc, "retry_after", None),
        now_fn(),
    )
    if retry_at is None:
        deliveries.mark_failed(delivery_id, error)
        logger.warning("notifications.retry_gave_up", delivery_id=delivery_id, attempt=row.get("attempts"), error=error)
    else:
        deliveries.mark_retry(delivery_id, error, retry_at.isoformat())
        logger.info("notifications.retry_scheduled", delivery_id=delivery_id, attempt=row.get("attempts"))


def process_due(
    deliveries,
    channels,
    send_fn: Callable,
    executor: ThreadPoolExecutor,
    now_fn: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    """Claim due posts and start sending them. Returns how many were started.

    Does not wait for the sends: each records its own outcome when it finishes.
    """
    rows = deliveries.claim_due(BATCH_SIZE, LEASE_SECONDS, STALE_SECONDS)
    started = 0
    for row in rows:
        channel = channels.get_by_id(row["channel_id"])
        if channel is None or not channel.get("enabled"):
            deliveries.mark_failed(row["id"], "Channel removed or paused before it could be sent")
            continue
        future = executor.submit(send_fn, channel["platform"], channel["destination"], row["content"])
        future.add_done_callback(lambda f, r=row: _record(deliveries, r, f, now_fn))
        started += 1
    return started


def enabled() -> bool:
    return os.getenv("NOTIFICATION_RETRY_WORKER", "off").lower() in {"1", "true", "on", "yes"}


class RetryWorker:
    """A daemon thread that calls process_due every INTERVAL_SECONDS."""

    def __init__(self, deliveries, channels, send_fn: Callable, interval: float = INTERVAL_SECONDS):
        self._deliveries = deliveries
        self._channels = channels
        self._send_fn = send_fn
        self._interval = interval
        self._stop = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SENDS, thread_name_prefix="notify-retry")
        self._thread = threading.Thread(target=self._run, name="notify-retry-worker", daemon=True)

    def start(self) -> None:
        self._thread.start()
        logger.info("notifications.retry_worker_started", interval=self._interval)

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self) -> None:
        from api.club_notifications import is_notifications_enabled

        while not self._stop.wait(self._interval):
            if not is_notifications_enabled():
                continue
            try:
                process_due(self._deliveries, self._channels, self._send_fn, self._executor)
            except Exception as exc:  # never let the loop die
                logger.warning("notifications.retry_worker_error", error_type=type(exc).__name__)


@asynccontextmanager
async def retry_worker_lifespan():
    """Start the worker with the app when NOTIFICATION_RETRY_WORKER is on."""
    if not enabled():
        yield
        return
    from dao.match_dao import SupabaseConnection
    from dao.notification_channels_dao import NotificationChannelsDAO
    from dao.notification_deliveries_dao import NotificationDeliveriesDAO
    from notifications.senders import send_to

    conn = SupabaseConnection()
    worker = RetryWorker(NotificationDeliveriesDAO(conn), NotificationChannelsDAO(conn), send_to)
    worker.start()
    try:
        yield
    finally:
        worker.stop()

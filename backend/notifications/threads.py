"""Post a match's updates into one thread per channel (SB-1606).

Used by the live path (Notifier._post_to_channel) and the retry worker, so a
thread is created once whoever gets there first:

- The first post for a match claims its notification_threads row (the unique
  (channel_id, match_id) is the lock), creates the thread named after the
  match, and stores the thread id.
- Later posts go into that thread.
- A post that arrives while another is still creating the thread fails
  retryably (a few seconds) and the retry worker posts it into the thread.
- A creator that died or failed leaves a claim the next sender takes over.

A channel not marked post_as_threads, a platform without threads, or a post
with no match goes out flat, as before.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dao.notification_threads_dao import ThreadStoreError
from notifications.adapters.base import Capability, DeliveryError, DeliveryResult
from notifications.registry import get_adapter

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)

# How long a post waits for a thread another sender is still creating.
WAIT_FOR_THREAD_SECONDS = 5


def threads_apply(platform: str, post_as_threads: bool, match_id: int | None) -> bool:
    if not post_as_threads or match_id is None:
        return False
    return Capability.THREADS in get_adapter(platform).capabilities


def deliver_to_thread(
    platform: str,
    destination: str,
    content: str,
    channel_id: int,
    match_id: int,
    thread_name: str,
    threads,
) -> DeliveryResult:
    """Post into the match's thread on this channel, creating it if this caller won the claim."""
    adapter = get_adapter(platform)
    try:
        mine, row = threads.claim(channel_id, match_id, thread_name)
    except ThreadStoreError:
        # Without the table, posting a fresh thread beats losing the update.
        logger.warning("notifications.thread_store_unavailable", channel_id=channel_id, match_id=match_id)
        return adapter.send_in_thread(destination, content, None, thread_name)

    if not mine:
        if row.get("thread_ref"):
            return adapter.send_in_thread(destination, content, row["thread_ref"], None)
        taken = threads.take_over(row["id"])
        if taken is None:
            raise DeliveryError(
                f"{platform} send failed: match thread is being created",
                retryable=True,
                retry_after=WAIT_FOR_THREAD_SECONDS,
            )
        row = taken

    try:
        result = adapter.send_in_thread(destination, content, None, row.get("thread_name") or thread_name)
    except Exception:
        threads.release(row["id"])
        raise
    if result.thread_ref:
        threads.set_ref(row["id"], result.thread_ref)
    else:
        # Posted, but follow-ups could not find it: let the next post start one.
        threads.release(row["id"])
        logger.warning("notifications.thread_ref_missing", channel_id=channel_id, match_id=match_id)
    return result


def send(
    send_fn: Callable,
    platform: str,
    destination: str,
    content: str,
    *,
    post_as_threads: bool,
    channel_id: int,
    match_id: int | None,
    thread_name: str | None,
    threads,
):
    """Flat post through `send_fn`, or a match-thread post when the channel asks for one."""
    if threads is None or match_id is None or not threads_apply(platform, post_as_threads, match_id):
        return send_fn(platform, destination, content)
    return deliver_to_thread(
        platform, destination, content, channel_id, match_id, thread_name or f"Match {match_id}", threads
    )

"""The retry worker against the real ledger (SB-1604).

Proves the claim function, the DAO and the worker together: a due post is sent
once and recorded, a failing one is rescheduled, a later one is left alone, and
a second worker run right after claims nothing (the lease).

Requires local Supabase with the 20261113120000 migration. Skips otherwise.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from dao.match_dao import SupabaseConnection
from dao.notification_channels_dao import NotificationChannelsDAO
from dao.notification_deliveries_dao import NotificationDeliveriesDAO
from notifications.adapters.base import DeliveryError, DeliveryResult
from notifications.retry_worker import process_due

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]


@pytest.fixture
def world():
    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:55321")
    if not ("127.0.0.1" in url or "localhost" in url):
        pytest.skip(f"Refusing to run against non-local Supabase: {url}")
    conn = SupabaseConnection()
    client = conn.get_client()
    try:
        client.rpc(
            "claim_due_notification_deliveries", {"p_limit": 0, "p_lease_seconds": 1, "p_stale_seconds": 1}
        ).execute()
    except Exception:
        pytest.skip("claim_due_notification_deliveries missing: apply the SB-1604 migration")
    club = client.table("clubs").insert({"name": f"Retry-{uuid.uuid4().hex[:8]}"}).execute().data[0]
    channel = (
        client.table("notification_channels")
        .insert(
            {
                "scope_type": "club",
                "club_id": club["id"],
                "platform": "discord",
                "destination": f"https://discord.com/api/webhooks/1/{uuid.uuid4().hex}",
                "audience": "fans",
                "enabled": True,
            }
        )
        .execute()
        .data[0]
    )
    yield {"conn": conn, "client": client, "channel": channel["id"]}
    client.table("notification_deliveries").delete().eq("channel_id", channel["id"]).execute()
    client.table("notification_channels").delete().eq("id", channel["id"]).execute()
    client.table("clubs").delete().eq("id", club["id"]).execute()


def _row(w, key, due_in_seconds, content="hello"):
    at = (datetime.now(UTC) + timedelta(seconds=due_in_seconds)).isoformat()
    return (
        w["client"]
        .table("notification_deliveries")
        .insert({"channel_id": w["channel"], "event_key": key, "content": content, "next_attempt_at": at})
        .execute()
        .data[0]["id"]
    )


def _status(w, delivery_id):
    return (
        w["client"]
        .table("notification_deliveries")
        .select("status, attempts, error")
        .eq("id", delivery_id)
        .execute()
        .data[0]
    )


def _run(w, send):
    with ThreadPoolExecutor(max_workers=4) as pool:
        return process_due(NotificationDeliveriesDAO(w["conn"]), NotificationChannelsDAO(w["conn"]), send, pool)


def test_retry_worker_end_to_end(world):
    """One test, run in order: the claim is global by design (any due row), so
    separate tests in parallel workers would claim each other's rows."""
    due = _row(world, f"t:{uuid.uuid4().hex}", -5)
    later = _row(world, f"t:{uuid.uuid4().hex}", 3600)
    sent = []

    def send(platform, destination, content):
        sent.append(content)
        return DeliveryResult(message_ref="m1")

    assert _run(world, send) >= 1
    assert _status(world, due)["status"] == "sent"
    assert _status(world, due)["attempts"] == 2
    assert _status(world, later)["status"] == "pending"
    assert _run(world, send) == 0  # nothing due any more

    failing = _row(world, f"t:{uuid.uuid4().hex}", -5)

    def fail(*_):
        raise DeliveryError("discord send failed: HTTP 503", retryable=True)

    _run(world, fail)
    row = _status(world, failing)
    assert row["status"] == "pending"
    assert row["error"] == "discord send failed: HTTP 503"
    assert _run(world, fail) == 0  # rescheduled for later, not retried straight away

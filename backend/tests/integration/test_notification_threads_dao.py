"""Match thread claims against the real table (SB-1606).

The unique (channel_id, match_id) is the lock that stops simultaneous goals
creating two threads; take_over and release are atomic updates.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from dao.match_dao import SupabaseConnection
from dao.notification_threads_dao import NotificationThreadsDAO

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]


@pytest.fixture
def world():
    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:55321")
    if not ("127.0.0.1" in url or "localhost" in url):
        pytest.skip(f"Refusing to run against non-local Supabase: {url}")
    conn = SupabaseConnection()
    client = conn.get_client()
    try:
        client.table("notification_threads").select("id").limit(1).execute()
    except Exception:
        pytest.skip("notification_threads missing: apply the SB-1606 migration")
    match = client.table("matches").select("id").limit(1).execute().data
    if not match:
        pytest.skip("Need a match")
    club = client.table("clubs").insert({"name": f"Threads-{uuid.uuid4().hex[:8]}"}).execute().data[0]
    channel = (
        client.table("notification_channels")
        .insert(
            {
                "scope_type": "club",
                "club_id": club["id"],
                "platform": "discord",
                "destination": f"https://discord.com/api/webhooks/1/{uuid.uuid4().hex}",
                "audience": "fans",
                "post_as_threads": True,
            }
        )
        .execute()
        .data[0]
    )
    yield {"dao": NotificationThreadsDAO(conn), "channel": channel["id"], "match": match[0]["id"]}
    client.table("notification_threads").delete().eq("channel_id", channel["id"]).execute()
    client.table("notification_channels").delete().eq("id", channel["id"]).execute()
    client.table("clubs").delete().eq("id", club["id"]).execute()


def test_only_the_first_claim_creates_the_thread(world):
    dao, channel, match = world["dao"], world["channel"], world["match"]
    mine, row = dao.claim(channel, match, "IFA vs NEFC")
    again, same = dao.claim(channel, match, "IFA vs NEFC")
    assert mine is True and again is False
    assert same["id"] == row["id"] and same["thread_ref"] is None


def test_ref_is_stored_for_follow_ups(world):
    dao = world["dao"]
    _, row = dao.claim(world["channel"], world["match"], "n")
    dao.set_ref(row["id"], "777")
    _, again = dao.claim(world["channel"], world["match"], "n")
    assert again["thread_ref"] == "777"


def test_a_fresh_claim_cannot_be_taken_over_but_a_released_one_can(world):
    dao = world["dao"]
    _, row = dao.claim(world["channel"], world["match"], "n")
    assert dao.take_over(row["id"]) is None  # its creator is still working
    dao.release(row["id"])
    taken = dao.take_over(row["id"])
    assert taken is not None and taken["id"] == row["id"]
    assert dao.take_over(row["id"]) is None  # and now it is held again


def test_a_stale_claim_can_be_taken_over(world):
    dao = world["dao"]
    _, row = dao.claim(world["channel"], world["match"], "n")
    later = datetime.now(UTC) + timedelta(seconds=200)
    assert dao.take_over(row["id"], now=later) is not None

"""The ledger's unique constraint against a real database (SB-1603)."""

import uuid

import pytest

from dao.match_dao import SupabaseConnection
from dao.notification_deliveries_dao import NotificationDeliveriesDAO

pytestmark = pytest.mark.integration


@pytest.fixture
def conn():
    return SupabaseConnection()


@pytest.fixture
def dao(conn):
    return NotificationDeliveriesDAO(conn)


@pytest.fixture
def channel_id(conn):
    # Disabled, so a concurrent dispatch test cannot post to it.
    row = (
        conn.get_client()
        .table("notification_channels")
        .insert(
            {
                "scope_type": "global",
                "platform": "discord",
                "destination": f"test-{uuid.uuid4().hex}",
                "enabled": False,
            }
        )
        .execute()
        .data[0]
    )
    yield row["id"]
    conn.get_client().table("notification_channels").delete().eq("id", row["id"]).execute()


def fetch(dao, delivery_id):
    return dao.client.table("notification_deliveries").select("*").eq("id", delivery_id).execute().data[0]


def test_second_claim_for_the_same_event_is_refused(dao, channel_id):
    assert dao.claim(channel_id, "match:1:kickoff") is not None
    assert dao.claim(channel_id, "match:1:kickoff") is None


def test_a_different_event_can_be_claimed(dao, channel_id):
    assert dao.claim(channel_id, "match:1:kickoff") is not None
    assert dao.claim(channel_id, "match:1:halftime") is not None


def test_mark_sent_records_the_ref(dao, channel_id):
    delivery_id = dao.claim(channel_id, "match:1:kickoff")
    dao.mark_sent(delivery_id, "m1")
    row = fetch(dao, delivery_id)
    assert (row["status"], row["provider_message_ref"], row["attempts"]) == ("sent", "m1", 1)


def test_mark_failed_records_the_error(dao, channel_id):
    delivery_id = dao.claim(channel_id, "match:1:kickoff")
    dao.mark_failed(delivery_id, "discord send failed: HTTP 403")
    row = fetch(dao, delivery_id)
    assert (row["status"], row["error"]) == ("failed", "discord send failed: HTTP 403")

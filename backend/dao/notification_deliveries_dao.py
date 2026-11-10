"""
Notification Deliveries Data Access Object (SB-1603).

One row per (channel, match event). Claiming the row before posting is what
stops a resent event from posting twice.

Holds no destination. Errors are logged by type only.
"""

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

TABLE = "notification_deliveries"
_UNIQUE_VIOLATION = "23505"
_MAX_ERROR_LENGTH = 500


class DeliveryLedgerError(Exception):
    """The ledger could not be read or written. Safe to log."""


class NotificationDeliveriesDAO(BaseDAO):
    """Data access for the notification delivery ledger."""

    def claim(self, channel_id: int, event_key: str) -> int | None:
        """Reserve this event on this channel.

        Returns the new delivery id, or None if it was already claimed.
        Raises DeliveryLedgerError if the ledger cannot answer.
        """
        try:
            row = {"channel_id": channel_id, "event_key": event_key}
            return self.client.table(TABLE).insert(row).execute().data[0]["id"]
        except Exception as exc:
            if _UNIQUE_VIOLATION in str(exc):
                return None
            logger.error("dao_notification_deliveries_claim_failed", error_type=type(exc).__name__)
            raise DeliveryLedgerError("Could not claim notification delivery") from None

    def latest_for(self, channel_ids: list[int]) -> dict[int, dict] | None:
        """Each channel's most recent delivery, keyed by channel id.

        A channel with none is absent from the result. None means the ledger
        could not be read, which is not the same as "nothing delivered yet".
        One indexed query per channel: a scope holds a handful.
        """
        latest: dict[int, dict] = {}
        try:
            for channel_id in channel_ids:
                rows = (
                    self.client.table(TABLE)
                    .select("channel_id, status, error, created_at, updated_at")
                    .eq("channel_id", channel_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                    .data
                )
                if rows:
                    latest[channel_id] = rows[0]
        except Exception as exc:
            logger.error("dao_notification_deliveries_read_failed", error_type=type(exc).__name__)
            return None
        return latest

    def mark_sent(self, delivery_id: int, message_ref: str | None) -> None:
        """Record a successful post."""
        self._finish(delivery_id, {"status": "sent", "provider_message_ref": message_ref})

    def mark_failed(self, delivery_id: int, error: str) -> None:
        """Record a failed post. `error` must already be safe to store."""
        self._finish(delivery_id, {"status": "failed", "error": error[:_MAX_ERROR_LENGTH]})

    def _finish(self, delivery_id: int, fields: dict) -> None:
        """Best-effort: the message outcome is already decided by this point."""
        try:
            self.client.table(TABLE).update(fields).eq("id", delivery_id).execute()
        except Exception as exc:
            logger.error("dao_notification_deliveries_update_failed", error_type=type(exc).__name__)

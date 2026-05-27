"""Push Subscription DAO.

One row per (user, device). Endpoint is the URL returned by the browser's
PushManager.subscribe(); it uniquely identifies a browser+device combination
to the push service.

Idempotency: re-registering an existing endpoint updates the user_id and
metadata in place (handles "user signs into MT on a phone someone else
already used to follow another account").
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

TABLE = "push_subscriptions"


class PushSubscriptionDAO(BaseDAO):
    """Data access for Web Push subscriptions."""

    def upsert(
        self,
        user_id: str,
        endpoint: str,
        p256dh_key: str,
        auth_key: str,
        device_label: str | None = None,
        user_agent: str | None = None,
    ) -> dict | None:
        """Create or update a subscription by endpoint.

        On endpoint collision, updates user_id + label + keys + last_seen_at.
        Returns the row on success, None on error.
        """
        now = datetime.now(UTC).isoformat()
        payload = {
            "user_id": user_id,
            "endpoint": endpoint,
            "p256dh_key": p256dh_key,
            "auth_key": auth_key,
            "device_label": device_label,
            "user_agent": user_agent,
            "last_seen_at": now,
        }
        try:
            existing = self.get_by_endpoint(endpoint)
            if existing:
                response = (
                    self.client.table(TABLE)
                    .update(payload)
                    .eq("endpoint", endpoint)
                    .execute()
                )
                return response.data[0] if response.data else None
            response = self.client.table(TABLE).insert(payload).execute()
            return response.data[0] if response.data else None
        except Exception:
            logger.exception("push_subscription_upsert_failed", user_id=user_id)
            return None

    def get_by_endpoint(self, endpoint: str) -> dict | None:
        try:
            response = (
                self.client.table(TABLE)
                .select("*")
                .eq("endpoint", endpoint)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception:
            logger.exception("push_subscription_get_failed")
            return None

    def list_by_user(self, user_id: str) -> list[dict]:
        try:
            response = (
                self.client.table(TABLE)
                .select("id, device_label, user_agent, created_at, last_seen_at")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data or []
        except Exception:
            logger.exception("push_subscription_list_failed", user_id=user_id)
            return []

    def delete_by_id(self, user_id: str, subscription_id: str) -> bool:
        """Delete a subscription. Filters by user_id for defense-in-depth.

        Returns True if a row was deleted, False otherwise.
        """
        try:
            response = (
                self.client.table(TABLE)
                .delete()
                .eq("id", subscription_id)
                .eq("user_id", user_id)
                .execute()
            )
            return bool(response.data)
        except Exception:
            logger.exception(
                "push_subscription_delete_failed",
                user_id=user_id,
                subscription_id=subscription_id,
            )
            return False

    def delete_by_endpoint(self, endpoint: str) -> bool:
        """Used when the push service returns 404/410 (subscription expired).

        Returns True if a row was deleted.
        """
        try:
            response = (
                self.client.table(TABLE).delete().eq("endpoint", endpoint).execute()
            )
            return bool(response.data)
        except Exception:
            logger.exception("push_subscription_delete_by_endpoint_failed")
            return False

    def touch_last_seen(self, subscription_id: str) -> None:
        try:
            self.client.table(TABLE).update(
                {"last_seen_at": datetime.now(UTC).isoformat()}
            ).eq("id", subscription_id).execute()
        except Exception:
            logger.exception(
                "push_subscription_touch_failed", subscription_id=subscription_id
            )

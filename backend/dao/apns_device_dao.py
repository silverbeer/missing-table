"""APNs Device DAO (SB-1236).

One row per native iOS install. device_token is the hex token the app gets
from registerForRemoteNotifications(); it identifies (device, app,
environment) to APNs and is unique here.

Idempotency: re-registering an existing token updates user_id and metadata
in place, so a token signed into by a different user moves to that user
(mirrors PushSubscriptionDAO's endpoint handling).
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

TABLE = "apns_devices"

# Columns the API returns to the owner. The token itself is write-only.
_PUBLIC_COLUMNS = "id, environment, bundle_id, device_label, app_version, created_at, last_seen_at"

# Columns the sender needs.
_SEND_COLUMNS = "id, user_id, device_token, environment, bundle_id"


class ApnsDeviceDAO(BaseDAO):
    """Data access for APNs device registrations."""

    def upsert(
        self,
        user_id: str,
        device_token: str,
        environment: str,
        bundle_id: str | None = None,
        device_label: str | None = None,
        app_version: str | None = None,
    ) -> dict | None:
        """Create or update a device by device_token.

        On token collision, moves the row to user_id and refreshes metadata +
        last_seen_at; id and created_at are kept. Returns the row on success,
        None on error.
        """
        payload: dict[str, str | None] = {
            "user_id": user_id,
            "device_token": device_token,
            "environment": environment,
            "device_label": device_label,
            "app_version": app_version,
            "last_seen_at": datetime.now(UTC).isoformat(),
        }
        if bundle_id:
            payload["bundle_id"] = bundle_id
        try:
            response = self.client.table(TABLE).upsert(payload, on_conflict="device_token").execute()
            return response.data[0] if response.data else None
        except Exception:
            logger.exception("apns_device_upsert_failed", user_id=user_id)
            return None

    def list_by_user(self, user_id: str) -> list[dict]:
        """The user's devices, newest first, without tokens."""
        try:
            response = (
                self.client.table(TABLE)
                .select(_PUBLIC_COLUMNS)
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data or []
        except Exception:
            logger.exception("apns_device_list_failed", user_id=user_id)
            return []

    def list_for_user_ids(self, user_ids: list[str]) -> list[dict]:
        """Fan-out query: every device owned by any of these users, with tokens.

        One row per device (a user with two iPhones gets two). Returns [] on
        error — the dispatcher must never break on a lookup failure.
        """
        if not user_ids:
            return []
        try:
            response = self.client.table(TABLE).select(_SEND_COLUMNS).in_("user_id", user_ids).execute()
            return response.data or []
        except Exception:
            logger.exception("apns_device_list_for_users_failed", user_count=len(user_ids))
            return []

    def delete_for_user(self, user_id: str, device_id: str) -> bool:
        """Delete one of the user's devices. Filters by user_id for defense-in-depth.

        Returns True if a row was deleted, False otherwise.
        """
        try:
            response = self.client.table(TABLE).delete().eq("id", device_id).eq("user_id", user_id).execute()
            return bool(response.data)
        except Exception:
            logger.exception(
                "apns_device_delete_failed",
                user_id=user_id,
                device_id=device_id,
            )
            return False

    def delete_by_token(self, device_token: str) -> bool:
        """Used when APNs reports the token gone (410, BadDeviceToken, ...).

        Returns True if a row was deleted.
        """
        try:
            response = self.client.table(TABLE).delete().eq("device_token", device_token).execute()
            return bool(response.data)
        except Exception:
            logger.exception("apns_device_delete_by_token_failed")
            return False

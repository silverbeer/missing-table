"""FCM Device DAO (SB-1463).

One row per native Android install. fid is the Firebase Installation ID the
app gets from FirebaseInstallations.getId(); FCM HTTP v1 addresses a device
by it, and it is unique here.

Idempotency: re-registering an existing fid updates user_id and metadata in
place, so an fid signed into by a different user moves to that user (mirrors
ApnsDeviceDAO).
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

TABLE = "fcm_devices"

# Columns the API returns to the owner. The fid itself is write-only.
_PUBLIC_COLUMNS = "id, device_label, app_version, created_at, last_seen_at"

# Columns the sender needs.
_SEND_COLUMNS = "id, user_id, fid"


class FcmDeviceDAO(BaseDAO):
    """Data access for FCM device registrations."""

    def upsert(
        self,
        user_id: str,
        fid: str,
        device_label: str | None = None,
        app_version: str | None = None,
    ) -> dict | None:
        """Create or update a device by fid.

        On fid collision, moves the row to user_id and refreshes last_seen_at
        plus whichever metadata was given — an omitted label or version keeps
        the stored one. id and created_at are kept. Returns the row on
        success, None on error.
        """
        payload: dict[str, str] = {
            "user_id": user_id,
            "fid": fid,
            "last_seen_at": datetime.now(UTC).isoformat(),
        }
        if device_label is not None:
            payload["device_label"] = device_label
        if app_version is not None:
            payload["app_version"] = app_version
        try:
            response = self.client.table(TABLE).upsert(payload, on_conflict="fid").execute()
            return response.data[0] if response.data else None
        except Exception:
            logger.exception("fcm_device_upsert_failed", user_id=user_id)
            return None

    def list_by_user(self, user_id: str) -> list[dict]:
        """The user's devices, newest first, without fids."""
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
            logger.exception("fcm_device_list_failed", user_id=user_id)
            return []

    def list_for_user_ids(self, user_ids: list[str]) -> list[dict]:
        """Fan-out query: every device owned by any of these users, with fids.

        One row per device. Returns [] on error — the dispatcher must never
        break on a lookup failure.
        """
        if not user_ids:
            return []
        try:
            response = self.client.table(TABLE).select(_SEND_COLUMNS).in_("user_id", user_ids).execute()
            return response.data or []
        except Exception:
            logger.exception("fcm_device_list_for_users_failed", user_count=len(user_ids))
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
                "fcm_device_delete_failed",
                user_id=user_id,
                device_id=device_id,
            )
            return False

    def delete_by_fid(self, fid: str) -> bool:
        """Used when FCM reports the installation gone (UNREGISTERED, ...).

        Returns True if a row was deleted.
        """
        try:
            response = self.client.table(TABLE).delete().eq("fid", fid).execute()
            return bool(response.data)
        except Exception:
            logger.exception("fcm_device_delete_by_fid_failed")
            return False

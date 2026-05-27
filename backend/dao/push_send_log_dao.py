"""Push Send Log DAO.

Append-only log of every push send attempt. Used for delivery debugging
("I'm not getting notifications") and basic analytics. All writes go via
the backend service role; users have no direct access (RLS).

Writes are fire-and-forget — any logging failure must NOT bubble up and
break the push send flow.
"""

from __future__ import annotations

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

TABLE = "push_send_log"


class PushSendLogDAO(BaseDAO):
    """Append-only log of push send attempts."""

    def log(
        self,
        subscription_id: str | None,
        user_id: str | None,
        match_id: int | None,
        event_type: str,
        status: str,
        http_status: int | None = None,
        error: str | None = None,
    ) -> None:
        """Record a single send attempt. Never raises.

        status ∈ {'sent', 'failed', 'expired'}. 'expired' means the push
        service returned 404/410 and the subscription has been cleaned up.
        """
        try:
            self.client.table(TABLE).insert(
                {
                    "subscription_id": subscription_id,
                    "user_id": user_id,
                    "match_id": match_id,
                    "event_type": event_type,
                    "status": status,
                    "http_status": http_status,
                    "error": (error[:500] if error else None),
                }
            ).execute()
        except Exception as exc:
            # Don't bubble — logging is best-effort.
            logger.warning(
                "push_send_log_write_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )

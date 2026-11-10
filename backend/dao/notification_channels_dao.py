"""
Notification Channels Data Access Object (SB-1602).

Where match updates are posted: a squad, a club, or every match.

``destination`` is sensitive, and a Postgres unique-violation message quotes it,
so database errors here are logged by type only and never re-raised verbatim.
"""

import uuid

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

TABLE = "notification_channels"
_UNIQUE_VIOLATION = "23505"


class DuplicateChannelError(Exception):
    """This target already posts to that destination."""


class ChannelWriteError(Exception):
    """A channel could not be saved. Safe to log: carries no destination."""


def actor_id(user: dict) -> str | None:
    """The caller's profile id for `created_by`; None for a non-user (service) caller."""
    value = user.get("user_id") or user.get("id")
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        return None


class NotificationChannelsDAO(BaseDAO):
    """Data access for scoped notification channels."""

    def _select(self, description: str, build) -> list[dict]:
        """Run a read; a failure is logged and returns no rows.

        Delivery is best-effort, so one failed lookup must not cost the others.
        """
        try:
            return build(self.client.table(TABLE).select("*")).execute().data or []
        except Exception as exc:
            logger.error("dao_notification_channels_read_failed", query=description, error_type=type(exc).__name__)
            return []

    def list_for_match(
        self,
        club_ids: list[int],
        team_ids: list[int],
        age_group_id: int | None,
    ) -> list[dict]:
        """Every channel that could receive this match, clubs before squads before global."""
        rows: list[dict] = []
        if club_ids:
            rows += self._select(
                "club",
                lambda q: q.eq("scope_type", "club").in_("club_id", club_ids).order("id"),
            )
        if team_ids and age_group_id is not None:
            rows += self._select(
                "team",
                lambda q: q.eq("scope_type", "team")
                .in_("team_id", team_ids)
                .eq("age_group_id", age_group_id)
                .order("id"),
            )
        rows += self._select("global", lambda q: q.eq("scope_type", "global").order("id"))
        return rows

    def list_for_scope(
        self,
        scope_type: str,
        club_id: int | None = None,
        team_id: int | None = None,
        age_group_id: int | None = None,
    ) -> list[dict]:
        """Channels for one scope. An empty list is the normal state."""

        def build(query):
            query = query.eq("scope_type", scope_type)
            if club_id is not None:
                query = query.eq("club_id", club_id)
            if team_id is not None:
                query = query.eq("team_id", team_id)
            if age_group_id is not None:
                query = query.eq("age_group_id", age_group_id)
            return query.order("id")

        return self._select("scope", build)

    def get_by_id(self, channel_id: int) -> dict | None:
        rows = self._select("by_id", lambda q: q.eq("id", channel_id).limit(1))
        return rows[0] if rows else None

    def create(self, fields: dict) -> dict:
        """Insert a channel. Raises DuplicateChannelError or ChannelWriteError."""
        try:
            return self.client.table(TABLE).insert(fields).execute().data[0]
        except Exception as exc:
            raise self._write_error("create", exc) from None

    def update(self, channel_id: int, fields: dict) -> dict | None:
        """Update a channel; None if it no longer exists."""
        try:
            rows = self.client.table(TABLE).update(fields).eq("id", channel_id).execute().data
        except Exception as exc:
            raise self._write_error("update", exc) from None
        return rows[0] if rows else None

    def delete_by_id(self, channel_id: int) -> bool:
        """Remove a channel. Returns True if a row was deleted."""
        try:
            return bool(self.client.table(TABLE).delete().eq("id", channel_id).execute().data)
        except Exception as exc:
            raise self._write_error("delete", exc) from None

    @staticmethod
    def _write_error(operation: str, exc: Exception) -> Exception:
        if _UNIQUE_VIOLATION in str(exc):
            return DuplicateChannelError()
        logger.error("dao_notification_channels_write_failed", operation=operation, error_type=type(exc).__name__)
        return ChannelWriteError(f"Could not {operation} notification channel")

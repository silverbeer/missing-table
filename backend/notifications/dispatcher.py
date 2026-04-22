"""Live-match notification dispatcher.

Given a match event, resolve the channels that should receive it, format
the message in the home club's timezone, and best-effort deliver it to
each destination.

All failures are swallowed and logged — the notifier must never impact the
user-facing live-scoring flow.
"""

from __future__ import annotations

import os
from zoneinfo import ZoneInfo

import structlog

from dao.club_notifications_dao import ClubNotificationsDAO
from dao.match_dao import MatchDAO, SupabaseConnection
from notifications.channel_resolver import fetch_club_timezone, resolve_destinations
from notifications.formatters import format_event

logger = structlog.get_logger(__name__)


def is_notifications_enabled() -> bool:
    """Global kill switch — matches the one in api/club_notifications.py."""
    return os.getenv("NOTIFICATIONS_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


class Notifier:
    """Dispatcher wrapper with DI-friendly constructor for tests."""

    def __init__(
        self,
        connection: SupabaseConnection | None = None,
        send_fn=None,
    ):
        self._connection = connection
        self._match_dao: MatchDAO | None = None
        self._notif_dao: ClubNotificationsDAO | None = None
        # Lazy-imported default sender so tests can swap without importing httpx.
        self._send_fn = send_fn

    @property
    def connection(self) -> SupabaseConnection:
        if self._connection is None:
            self._connection = SupabaseConnection()
        return self._connection

    @property
    def match_dao(self) -> MatchDAO:
        if self._match_dao is None:
            self._match_dao = MatchDAO(self.connection)
        return self._match_dao

    @property
    def notif_dao(self) -> ClubNotificationsDAO:
        if self._notif_dao is None:
            self._notif_dao = ClubNotificationsDAO(self.connection)
        return self._notif_dao

    @property
    def send_fn(self):
        if self._send_fn is None:
            from notifications.senders import send_to

            self._send_fn = send_to
        return self._send_fn

    def notify(
        self,
        event_type: str,
        match_id: int,
        extra: dict | None = None,
    ) -> None:
        """Deliver a notification for a single match event.

        Best-effort: logs and returns on any failure, never raises.
        """
        if not is_notifications_enabled():
            logger.info(
                "notifications.skipped",
                reason="disabled",
                match_id=match_id,
                event_type=event_type,
            )
            return

        match = self.match_dao.get_match_by_id(match_id)
        if not match:
            logger.warning(
                "notifications.skipped",
                reason="match_not_found",
                match_id=match_id,
                event_type=event_type,
            )
            return

        home_club = match.get("home_team_club") or {}
        away_club = match.get("away_team_club") or {}
        home_club_id = home_club.get("id")
        away_club_id = away_club.get("id")

        destinations = resolve_destinations(home_club_id, away_club_id, self.notif_dao)
        if not destinations:
            logger.info(
                "notifications.skipped",
                reason="no_channels",
                match_id=match_id,
                event_type=event_type,
                home_club_id=home_club_id,
                away_club_id=away_club_id,
            )
            return

        tz_name = fetch_club_timezone(home_club_id, self.connection.get_client())
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("America/New_York")

        content = format_event(event_type, match, extra, tz)
        if not content:
            logger.warning(
                "notifications.skipped",
                reason="unknown_event_type",
                match_id=match_id,
                event_type=event_type,
            )
            return

        sent = 0
        failed = 0
        for platform, destination in destinations:
            try:
                self.send_fn(platform, destination, content)
                sent += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "notifications.send_failed",
                    platform=platform,
                    match_id=match_id,
                    event_type=event_type,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )

        logger.info(
            "notifications.dispatched",
            match_id=match_id,
            event_type=event_type,
            sent=sent,
            failed=failed,
        )


_default_notifier: Notifier | None = None


def get_notifier() -> Notifier:
    """Process-wide default notifier. Tests override via set_notifier()."""
    global _default_notifier
    if _default_notifier is None:
        _default_notifier = Notifier()
    return _default_notifier


def set_notifier(notifier: Notifier | None) -> None:
    """Install a custom notifier (for tests) or reset by passing None."""
    global _default_notifier
    _default_notifier = notifier

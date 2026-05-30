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
from dao.push_send_log_dao import PushSendLogDAO
from dao.push_subscription_dao import PushSubscriptionDAO
from dao.team_follow_dao import TeamFollowDAO
from notifications.channel_resolver import (
    fetch_club_timezone,
    resolve_destinations,
    resolve_user_push_subscriptions,
)
from notifications.formatters import format_event
from notifications.preferences import DEFAULT_PREFERENCES
from notifications.web_push_sender import is_configured as push_is_configured
from notifications.web_push_sender import send_push

# NotificationPreferencesDAO is imported lazily inside `prefs_dao` to break
# the circular import: notification_preferences_dao.py → notifications.preferences
# → notifications/__init__ → dispatcher → notification_preferences_dao.py.

logger = structlog.get_logger(__name__)


def is_notifications_enabled() -> bool:
    """Global kill switch — matches the one in api/club_notifications.py."""
    return os.getenv("NOTIFICATIONS_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _build_push_payload(event_type: str, match: dict, content: str) -> dict:
    """Construct the JSON payload the service worker will receive.

    title = first line of formatted content (the headline w/ emoji)
    body  = remaining lines

    `tag` collapses repeated events on the same match so the user sees
    one notification per (match, event_type) instead of a stack.
    """
    lines = content.split("\n", 1)
    title = lines[0]
    body = lines[1] if len(lines) > 1 else ""
    match_id = match.get("id")
    return {
        "title": title,
        "body": body,
        "icon": "/pwa/icon-192.png",
        "badge": "/pwa/icon-192.png",
        "tag": f"match-{match_id}-{event_type}",
        "data": {
            "url": f"/?tab=live&matchId={match_id}",
            "matchId": match_id,
            "eventType": event_type,
        },
    }


class Notifier:
    """Dispatcher wrapper with DI-friendly constructor for tests."""

    def __init__(
        self,
        connection: SupabaseConnection | None = None,
        send_fn=None,
        push_send_fn=None,
    ):
        self._connection = connection
        self._match_dao: MatchDAO | None = None
        self._notif_dao: ClubNotificationsDAO | None = None
        self._team_follow_dao: TeamFollowDAO | None = None
        self._push_sub_dao: PushSubscriptionDAO | None = None
        self._push_log_dao: PushSendLogDAO | None = None
        # NotificationPreferencesDAO; typed via local import to avoid the cycle.
        self._prefs_dao = None
        # Lazy-imported default sender so tests can swap without importing httpx.
        self._send_fn = send_fn
        # Push sender override for tests.
        self._push_send_fn = push_send_fn or send_push

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
    def team_follow_dao(self) -> TeamFollowDAO:
        if self._team_follow_dao is None:
            self._team_follow_dao = TeamFollowDAO(self.connection)
        return self._team_follow_dao

    @property
    def push_sub_dao(self) -> PushSubscriptionDAO:
        if self._push_sub_dao is None:
            self._push_sub_dao = PushSubscriptionDAO(self.connection)
        return self._push_sub_dao

    @property
    def push_log_dao(self) -> PushSendLogDAO:
        if self._push_log_dao is None:
            self._push_log_dao = PushSendLogDAO(self.connection)
        return self._push_log_dao

    @property
    def prefs_dao(self):
        if self._prefs_dao is None:
            from dao.notification_preferences_dao import (
                NotificationPreferencesDAO,
            )

            self._prefs_dao = NotificationPreferencesDAO(self.connection)
        return self._prefs_dao

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

        # Club notification channels (Telegram/Discord). A match may have none
        # — e.g. tournament teams whose clubs have no channel config — in which
        # case we skip the club sends but STILL run the Web Push fan-out below.
        # Push to team followers must not depend on the clubs having channels
        # (SB-77); previously a no-channels match returned here and followers
        # got nothing.
        destinations = resolve_destinations(home_club_id, away_club_id, self.notif_dao)
        if destinations:
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
        else:
            logger.info(
                "notifications.no_club_channels",
                match_id=match_id,
                event_type=event_type,
                home_club_id=home_club_id,
                away_club_id=away_club_id,
            )

        # --- Web Push fan-out -------------------------------------------------
        # Independent of club-channel sends above; failures don't affect each
        # other. Skipped entirely if VAPID isn't configured (dormant state
        # before the platform-bootstrap secrets land — see SB-50).
        self._send_push_fanout(event_type, match, content)

    def _send_push_fanout(
        self, event_type: str, match: dict, content: str
    ) -> None:
        """Push to every user following either team, gated by per-user preferences.

        Pre-SB-57, yellow_card/red_card were hard-skipped here; now they fire
        only for users who opted in. Defaults preserve prior behavior (cards
        off, everything else on) so existing followers see no change until
        they touch the prefs UI.
        """
        if not push_is_configured():
            return  # VAPID env unset — dormant; SB-50 activates this

        home_team_id = match.get("home_team_id")
        away_team_id = match.get("away_team_id")
        match_id = match.get("id")

        subscriptions = resolve_user_push_subscriptions(
            home_team_id, away_team_id, self.team_follow_dao
        )
        if not subscriptions:
            return

        # One batch query for the entire fanout instead of N per subscription.
        user_ids = sorted({sub.get("user_id") for sub in subscriptions if sub.get("user_id")})
        prefs_by_user = self.prefs_dao.get_preferences_batch(user_ids)

        payload = _build_push_payload(event_type, match, content)

        push_sent = 0
        push_failed = 0
        push_expired = 0
        push_skipped_pref = 0
        for sub in subscriptions:
            user_id = sub.get("user_id")
            user_prefs = prefs_by_user.get(user_id, DEFAULT_PREFERENCES)
            if not user_prefs.get(event_type, True):
                push_skipped_pref += 1
                continue
            result = self._push_send_fn(sub, payload)
            self.push_log_dao.log(
                subscription_id=sub.get("id"),
                user_id=user_id,
                match_id=match_id,
                event_type=event_type,
                status=result.status,
                http_status=result.http_status,
                error=result.error,
            )
            if result.ok:
                push_sent += 1
            elif result.expired:
                push_expired += 1
                # Subscription is dead — clean it up so we don't retry forever.
                self.push_sub_dao.delete_by_endpoint(sub["endpoint"])
            else:
                push_failed += 1

        logger.info(
            "notifications.push_dispatched",
            match_id=match_id,
            event_type=event_type,
            sent=push_sent,
            failed=push_failed,
            expired=push_expired,
            skipped_pref=push_skipped_pref,
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

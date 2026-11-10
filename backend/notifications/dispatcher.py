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

from dao.apns_device_dao import ApnsDeviceDAO
from dao.bracket_follow_dao import BracketFollowDAO
from dao.club_notifications_dao import ClubNotificationsDAO
from dao.fcm_device_dao import FcmDeviceDAO
from dao.match_dao import MatchDAO, SupabaseConnection
from dao.notification_deliveries_dao import DeliveryLedgerError, NotificationDeliveriesDAO
from dao.push_send_log_dao import PushSendLogDAO
from dao.push_subscription_dao import PushSubscriptionDAO
from dao.team_follow_dao import TeamFollowDAO
from notifications.adapters.base import DeliveryError, NotificationConfigError
from notifications.apns_sender import is_configured as apns_is_configured
from notifications.apns_sender import send_apns
from notifications.channel_resolver import (
    ResolvedChannel,
    fetch_club_timezone,
    resolve_destinations,
    resolve_user_push_subscriptions,
)
from notifications.fcm_sender import is_configured as fcm_is_configured
from notifications.fcm_sender import send_fcm
from notifications.formatters import format_event
from notifications.preferences import DEFAULT_PREFERENCES
from notifications.web_push_sender import is_configured as push_is_configured
from notifications.web_push_sender import send_push

# NotificationPreferencesDAO is imported lazily inside `prefs_dao` to break
# the circular import: notification_preferences_dao.py → notifications.preferences
# → notifications/__init__ → dispatcher → notification_preferences_dao.py.

logger = structlog.get_logger(__name__)

# An FCM fan-out of at least this many sends that comes back entirely expired
# is treated as a config problem, and nothing is pruned (SB-1463).
FCM_MASS_EXPIRY_MIN_SENDS = 3


def is_notifications_enabled() -> bool:
    """Global kill switch — matches the one in api/club_notifications.py."""
    return os.getenv("NOTIFICATIONS_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _safe_error(exc: Exception) -> str:
    """Text safe to log and store: only our own errors are free of URLs and tokens."""
    if isinstance(exc, DeliveryError | NotificationConfigError):
        return str(exc)
    return type(exc).__name__


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
            # Deep link to the match detail. The SPA reads ?matchId= on load and
            # opens MatchDetailView (works for completed matches too — unlike the
            # old ?tab=live link, which nothing read). See App.vue (SB-86).
            "url": f"/?matchId={match_id}",
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
        apns_send_fn=None,
        fcm_send_fn=None,
    ):
        self._connection = connection
        self._match_dao: MatchDAO | None = None
        self._notif_dao: ClubNotificationsDAO | None = None
        self._delivery_dao: NotificationDeliveriesDAO | None = None
        self._team_follow_dao: TeamFollowDAO | None = None
        self._bracket_follow_dao: BracketFollowDAO | None = None
        self._push_sub_dao: PushSubscriptionDAO | None = None
        self._push_log_dao: PushSendLogDAO | None = None
        self._apns_device_dao: ApnsDeviceDAO | None = None
        self._fcm_device_dao: FcmDeviceDAO | None = None
        # NotificationPreferencesDAO; typed via local import to avoid the cycle.
        self._prefs_dao = None
        # Lazy-imported default sender so tests can swap without importing httpx.
        self._send_fn = send_fn
        # Push sender override for tests.
        self._push_send_fn = push_send_fn or send_push
        # APNs sender override for tests (SB-1236).
        self._apns_send_fn = apns_send_fn or send_apns
        # FCM sender override for tests (SB-1463).
        self._fcm_send_fn = fcm_send_fn or send_fcm

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
    def delivery_dao(self) -> NotificationDeliveriesDAO:
        if self._delivery_dao is None:
            self._delivery_dao = NotificationDeliveriesDAO(self.connection)
        return self._delivery_dao

    @property
    def team_follow_dao(self) -> TeamFollowDAO:
        if self._team_follow_dao is None:
            self._team_follow_dao = TeamFollowDAO(self.connection)
        return self._team_follow_dao

    @property
    def bracket_follow_dao(self) -> BracketFollowDAO:
        if self._bracket_follow_dao is None:
            self._bracket_follow_dao = BracketFollowDAO(self.connection)
        return self._bracket_follow_dao

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
    def apns_device_dao(self) -> ApnsDeviceDAO:
        if self._apns_device_dao is None:
            self._apns_device_dao = ApnsDeviceDAO(self.connection)
        return self._apns_device_dao

    @property
    def fcm_device_dao(self) -> FcmDeviceDAO:
        if self._fcm_device_dao is None:
            self._fcm_device_dao = FcmDeviceDAO(self.connection)
        return self._fcm_device_dao

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
        event_key: str | None = None,
    ) -> None:
        """Deliver a notification for a single match event.

        `event_key` makes chat posts idempotent; see `_post_to_channel`.

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

        # include_test: a TSC rehearsal is a match too. Without it every test
        # match is "not found" and nothing is ever sent for one (SB-1534);
        # who may hear about it is narrowed below instead.
        match = self.match_dao.get_match_by_id(match_id, include_test=True)
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

        # Chat channels (club, squad, global). A match may have none
        # — e.g. tournament teams whose clubs have no channel config — in which
        # case we skip the club sends but STILL run the Web Push fan-out below.
        # Push to team followers must not depend on the clubs having channels
        # (SB-77); previously a no-channels match returned here and followers
        # got nothing.
        # A test match never reaches a club channel: those are public rooms,
        # and the SB-591 partition exists so a rehearsal stays out of them.
        is_test = bool(match.get("is_test"))
        destinations = [] if is_test else resolve_destinations(match, event_type, self.notif_dao)
        if destinations:
            outcomes = [
                self._post_to_channel(channel, content, event_key, match_id, event_type)
                for channel in destinations
            ]
            logger.info(
                "notifications.dispatched",
                match_id=match_id,
                event_type=event_type,
                sent=outcomes.count("sent"),
                failed=outcomes.count("failed"),
                duplicate=outcomes.count("duplicate"),
            )
        elif is_test:
            logger.info(
                "notifications.test_match_no_club_channels",
                match_id=match_id,
                event_type=event_type,
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

        # --- Native audience (APNs + FCM) -------------------------------------
        # Followers and their preferences are resolved once and shared by both
        # native fan-outs; skipped entirely when neither is configured.
        apns_on = apns_is_configured()
        fcm_on = fcm_is_configured()
        if not apns_on and not fcm_on:
            return
        try:
            user_ids, prefs_by_user = self._native_audience(event_type, match)
        except Exception as exc:
            logger.warning(
                "notifications.native_audience_failed",
                match_id=match_id,
                event_type=event_type,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return
        if not user_ids:
            return

        # --- APNs fan-out (native iOS, SB-1236) -------------------------------
        # Same followers, same preference gate, same bracket rule as Web Push
        # above, but its own device table and sender. Runs after — and
        # independently of — the web path; skipped if APNs isn't configured.
        try:
            if apns_on:
                self._send_apns_fanout(event_type, match, content, user_ids, prefs_by_user)
        except Exception as exc:
            logger.warning(
                "notifications.apns_fanout_failed",
                match_id=match_id,
                event_type=event_type,
                error_type=type(exc).__name__,
                error=str(exc),
            )

        # --- FCM fan-out (native Android, SB-1463) ----------------------------
        # Same followers, preferences and bracket rule as APNs; its own device
        # table and sender. Skipped if FCM isn't configured.
        try:
            if fcm_on:
                self._send_fcm_fanout(event_type, match, content, user_ids, prefs_by_user)
        except Exception as exc:
            logger.warning(
                "notifications.fcm_fanout_failed",
                match_id=match_id,
                event_type=event_type,
                error_type=type(exc).__name__,
                error=str(exc),
            )

    def _post_to_channel(
        self,
        channel: ResolvedChannel,
        content: str,
        event_key: str | None,
        match_id: int,
        event_type: str,
    ) -> str:
        """Post once to one channel. Returns "sent", "failed" or "duplicate".

        The ledger row is claimed before the post, so a crash mid-send leaves a
        missed message rather than a double one. If the ledger itself is down
        the post goes ahead unrecorded: losing a goal update is worse than the
        small chance of repeating one.
        """
        delivery_id = None
        if event_key:
            try:
                delivery_id = self.delivery_dao.claim(channel.channel_id, event_key)
                if delivery_id is None:
                    return "duplicate"
            except DeliveryLedgerError:
                logger.warning(
                    "notifications.ledger_unavailable",
                    platform=channel.platform,
                    match_id=match_id,
                    event_type=event_type,
                )

        try:
            result = self.send_fn(channel.platform, channel.destination, content)
        except Exception as exc:
            error = _safe_error(exc)
            logger.warning(
                "notifications.send_failed",
                platform=channel.platform,
                match_id=match_id,
                event_type=event_type,
                error_type=type(exc).__name__,
                error=error,
            )
            if delivery_id is not None:
                self.delivery_dao.mark_failed(delivery_id, error)
            return "failed"

        if delivery_id is not None:
            self.delivery_dao.mark_sent(delivery_id, getattr(result, "message_ref", None))
        return "sent"

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
            home_team_id, away_team_id, self.team_follow_dao, match.get("age_group_id")
        )

        # Bracket followers: users who follow this match's tournament bracket
        # (tournament_id + group + age_group). Fulltime only — bracket follows
        # are "tell me the final score", not play-by-play. Merged into the same
        # fan-out and deduped below so a user following both the team and the
        # bracket gets one push per device, not two.
        if event_type == "fulltime":
            tournament_id = match.get("tournament_id")
            tournament_group = match.get("tournament_group")
            age_group_id = match.get("age_group_id")
            if tournament_id and tournament_group and age_group_id:
                subscriptions = subscriptions + self.bracket_follow_dao.list_subscriptions_for_bracket(
                    tournament_id, tournament_group, age_group_id
                )

        # Dedupe by subscription id across the team + bracket sources.
        seen_sub_ids: set[str] = set()
        deduped: list[dict] = []
        for sub in subscriptions:
            sub_id = sub.get("id")
            if sub_id in seen_sub_ids:
                continue
            seen_sub_ids.add(sub_id)
            deduped.append(sub)
        subscriptions = deduped

        # A test match reaches only those who can see it (SB-1534).
        if subscriptions and match.get("is_test"):
            allowed = self._test_content_viewers(
                sorted({sub.get("user_id") for sub in subscriptions if sub.get("user_id")})
            )
            subscriptions = [sub for sub in subscriptions if sub.get("user_id") in allowed]

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

    def _native_audience(
        self, event_type: str, match: dict
    ) -> tuple[list[str], dict[str, dict[str, bool]]]:
        """Users who should hear about this event on a native app, sorted,
        plus their preferences — one follow lookup and one preferences batch
        shared by the APNs and FCM fan-outs.

        Mirrors _send_push_fanout's resolution: followers of either team at the
        match's age group (squad follows, SB-1608), plus bracket followers at
        fulltime, deduped by user.
        """
        home_team_id = match.get("home_team_id")
        away_team_id = match.get("away_team_id")

        team_ids = [t for t in (home_team_id, away_team_id) if t is not None]
        user_ids: set[str] = set(
            self.team_follow_dao.list_user_ids_for_team_ids(team_ids, match.get("age_group_id"))
        )

        # Bracket followers get the final score only, as on the web path.
        if event_type == "fulltime":
            tournament_id = match.get("tournament_id")
            tournament_group = match.get("tournament_group")
            age_group_id = match.get("age_group_id")
            if tournament_id and tournament_group and age_group_id:
                user_ids.update(
                    self.bracket_follow_dao.list_user_ids_for_bracket(
                        tournament_id, tournament_group, age_group_id
                    )
                )
        if user_ids and match.get("is_test"):
            user_ids &= self._test_content_viewers(sorted(user_ids))
        if not user_ids:
            return [], {}
        sorted_ids = sorted(user_ids)
        return sorted_ids, self.prefs_dao.get_preferences_batch(sorted_ids)

    def _test_content_viewers(self, user_ids: list[str]) -> set[str]:
        """Which of these users may see the SB-591 test partition — admins and
        flagged test users, the same rule as auth.viewer_sees_test_content.

        Fails closed: if the lookup breaks, nobody hears about a test match.
        """
        if not user_ids:
            return set()
        try:
            response = (
                self.connection.get_client()
                .table("user_profiles")
                .select("id, role, is_test")
                .in_("id", user_ids)
                .execute()
            )
        except Exception as exc:
            logger.warning(
                "notifications.test_viewer_lookup_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return set()
        return {
            row["id"]
            for row in response.data or []
            if row.get("role") == "admin" or row.get("is_test")
        }

    def _send_apns_fanout(
        self,
        event_type: str,
        match: dict,
        content: str,
        user_ids: list[str],
        prefs_by_user: dict[str, dict[str, bool]],
    ) -> None:
        """Push to the iOS devices of every user following either team.

        Followers and preferences come from _native_audience; per-user
        preferences decide each send.
        """
        if not apns_is_configured():
            return  # APNS_* env unset — dormant

        match_id = match.get("id")
        if not user_ids:
            return

        devices = self.apns_device_dao.list_for_user_ids(user_ids)
        if not devices:
            return

        payload = _build_push_payload(event_type, match, content)

        sent = 0
        failed = 0
        expired = 0
        skipped_pref = 0
        for device in devices:
            user_id = device.get("user_id")
            user_prefs = prefs_by_user.get(user_id, DEFAULT_PREFERENCES)
            if not user_prefs.get(event_type, True):
                skipped_pref += 1
                continue
            result = self._apns_send_fn(device, payload)
            self.push_log_dao.log(
                subscription_id=None,
                user_id=user_id,
                match_id=match_id,
                event_type=event_type,
                status=result.status,
                http_status=result.http_status,
                error=result.error,
                apns_device_id=device.get("id"),
                platform="apns",
            )
            if result.ok:
                sent += 1
            elif result.expired:
                expired += 1
                # APNs says the token is gone — drop it so we stop sending.
                self.apns_device_dao.delete_by_token(device["device_token"])
            else:
                failed += 1

        logger.info(
            "notifications.apns_dispatched",
            match_id=match_id,
            event_type=event_type,
            sent=sent,
            failed=failed,
            expired=expired,
            skipped_pref=skipped_pref,
        )

    def _send_fcm_fanout(
        self,
        event_type: str,
        match: dict,
        content: str,
        user_ids: list[str],
        prefs_by_user: dict[str, dict[str, bool]],
    ) -> None:
        """Push to the Android devices of every user following either team.

        Same shape as _send_apns_fanout, with one extra guard: if every send
        in a fan-out of FCM_MASS_EXPIRY_MIN_SENDS or more comes back expired,
        nothing is pruned. That pattern means a project/credential problem,
        not a crowd of uninstalls, and pruning would wipe every device.
        """
        if not fcm_is_configured():
            return  # FCM_SERVICE_ACCOUNT_* env unset — dormant

        match_id = match.get("id")
        if not user_ids:
            return

        devices = self.fcm_device_dao.list_for_user_ids(user_ids)
        if not devices:
            return

        payload = _build_push_payload(event_type, match, content)

        sent = 0
        failed = 0
        expired = 0
        skipped_pref = 0
        expired_fids: list[str] = []
        for device in devices:
            user_id = device.get("user_id")
            user_prefs = prefs_by_user.get(user_id, DEFAULT_PREFERENCES)
            if not user_prefs.get(event_type, True):
                skipped_pref += 1
                continue
            result = self._fcm_send_fn(device, payload)
            self.push_log_dao.log(
                subscription_id=None,
                user_id=user_id,
                match_id=match_id,
                event_type=event_type,
                status=result.status,
                http_status=result.http_status,
                error=result.error,
                fcm_device_id=device.get("id"),
                platform="fcm",
            )
            if result.ok:
                sent += 1
            elif result.expired:
                expired += 1
                expired_fids.append(device["fid"])
            else:
                failed += 1

        attempted = sent + failed + expired
        if expired_fids and attempted >= FCM_MASS_EXPIRY_MIN_SENDS and expired == attempted:
            logger.warning(
                "notifications.fcm_mass_expiry_suspected",
                match_id=match_id,
                event_type=event_type,
                expired=expired,
            )
        else:
            # FCM says these installations are gone — drop them so we stop sending.
            for fid in expired_fids:
                self.fcm_device_dao.delete_by_fid(fid)

        logger.info(
            "notifications.fcm_dispatched",
            match_id=match_id,
            event_type=event_type,
            sent=sent,
            failed=failed,
            expired=expired,
            skipped_pref=skipped_pref,
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

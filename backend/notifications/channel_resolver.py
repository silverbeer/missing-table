"""Resolve the set of (platform, destination) channels for a given match.

Club, squad and global channels are unioned and deduplicated. Home club's
timezone is always used for message timestamps, regardless of which club
owns a given destination.
"""

from __future__ import annotations

from typing import NamedTuple

import structlog

from dao.club_notifications_dao import ClubNotificationsDAO  # noqa: TC001 — used at runtime for type check
from notifications.audience import players_allowed_at

logger = structlog.get_logger(__name__)


class ResolvedChannel(NamedTuple):
    """Where one post goes. `channel_id` is the row the delivery is recorded against."""

    platform: str
    destination: str
    channel_id: int


def select_destinations(
    rows: list[dict], event_type: str, age_group_name: str | None
) -> list[ResolvedChannel]:
    """Filter candidate channels to one per (platform, destination).

    Pure, so the routing rules are testable without a database. `event_types`
    of None means every event; an empty list means none.
    """
    players_allowed = players_allowed_at(age_group_name)
    seen: set[tuple[str, str]] = set()
    ordered: list[ResolvedChannel] = []
    for row in rows:
        if not row.get("enabled"):
            continue
        if row.get("audience") == "players" and not players_allowed:
            continue
        event_types = row.get("event_types")
        if event_types is not None and event_type not in event_types:
            continue
        key = (row["platform"], row["destination"])
        if key not in seen:
            seen.add(key)
            ordered.append(ResolvedChannel(row["platform"], row["destination"], row["id"]))
    return ordered


def resolve_destinations(
    match: dict,
    event_type: str,
    dao: ClubNotificationsDAO,
) -> list[ResolvedChannel]:
    """The channels that should hear about this match event.

    Both clubs' channels, both squads' channels (the team row plus the match's
    age group), and global channels.
    """
    home_club = match.get("home_team_club") or {}
    away_club = match.get("away_team_club") or {}
    club_ids = [c for c in (home_club.get("id"), away_club.get("id")) if c is not None]
    team_ids = [t for t in (match.get("home_team_id"), match.get("away_team_id")) if t is not None]
    rows = dao.list_for_match(club_ids, team_ids, match.get("age_group_id"))
    return select_destinations(rows, event_type, match.get("age_group_name"))


def resolve_user_push_subscriptions(
    home_team_id: int | None,
    away_team_id: int | None,
    team_follow_dao,
    age_group_id: int | None,
) -> list[dict]:
    """Find push subscriptions for users following either team at this age group.

    Whole-team follows always match; squad follows only at their age group (SB-1608).

    Returns subscription rows (id, endpoint, p256dh_key, auth_key, user_id),
    deduplicated by subscription id. A user with two devices appears twice
    (one per device). A user following both home and away teams still gets
    one push per device, not two.
    """
    team_ids = [t for t in (home_team_id, away_team_id) if t is not None]
    if not team_ids:
        return []
    try:
        return team_follow_dao.list_subscriptions_for_team_ids(team_ids, age_group_id)
    except Exception as exc:
        logger.warning(
            "resolve_push_subscriptions_failed",
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            error=str(exc),
        )
        return []


def fetch_club_timezone(club_id: int | None, supabase_client) -> str:
    """Look up the IANA timezone for a club; fall back to America/New_York."""
    if club_id is None:
        return "America/New_York"
    try:
        resp = (
            supabase_client.table("clubs")
            .select("timezone")
            .eq("id", club_id)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0].get("timezone") or "America/New_York"
    except Exception as exc:
        logger.warning(
            "fetch_club_timezone_failed",
            club_id=club_id,
            error=str(exc),
        )
    return "America/New_York"

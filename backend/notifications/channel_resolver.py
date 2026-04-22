"""Resolve the set of (platform, destination) channels for a given match.

The home + away club configurations are unioned and deduplicated. Home
club's timezone is always used for message timestamps, regardless of
which club owns a given destination.
"""

from __future__ import annotations

import structlog

from dao.club_notifications_dao import ClubNotificationsDAO  # noqa: TC001 — used at runtime for type check

logger = structlog.get_logger(__name__)


def resolve_destinations(
    home_club_id: int | None,
    away_club_id: int | None,
    dao: ClubNotificationsDAO,
) -> list[tuple[str, str]]:
    """Return a de-duplicated list of (platform, destination) tuples.

    Rows are filtered to enabled=true. Order is stable (telegram first,
    then discord) within a given club.
    """
    seen: set[tuple[str, str]] = set()
    ordered: list[tuple[str, str]] = []

    for club_id in (home_club_id, away_club_id):
        if club_id is None:
            continue
        try:
            rows = dao.list_by_club(club_id)
        except Exception as exc:
            logger.warning(
                "resolve_destinations_lookup_failed",
                club_id=club_id,
                error=str(exc),
            )
            continue

        for row in rows:
            if not row.get("enabled"):
                continue
            key = (row["platform"], row["destination"])
            if key in seen:
                continue
            seen.add(key)
            ordered.append(key)

    return ordered


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

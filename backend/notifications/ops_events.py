"""Operator-channel events through sb-notify (SB-1849).

The follower push and club-channel fan-out (dispatcher.py) are product
notifications. This is the operator's feed: one routed sb-notify event per new
final score, so the owner sees results land without opening the app. Where it
goes is the routing config's call (`$SB_NOTIFY_CONFIG`), never this module's.

Dormant unless `SB_NOTIFY_CONFIG` is set. sb-notify reads its own destinations
from env, holds events overnight (quiet hours) and drops repeats of a
`dedupe_key`, using the state file at `$SB_NOTIFY_STATE`.

Never raises: it runs in a background task after the response is sent, and a
broken operator feed must not touch the fan-out that runs beside it.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog
from sb_notify import notify

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)

CONFIG_ENV = "SB_NOTIFY_CONFIG"
SOURCE = "mt-backend"
MATCH_FINAL_KIND = "mt.match_final"
# An en dash, as a score is typeset.
SCORE_DASH = "\u2013"

# The match DAO fills unknown joins with "Unknown"; that says nothing to a reader.
_ABSENT = {"", "unknown"}

_dormant_logged = False


def is_enabled() -> bool:
    return bool(os.getenv(CONFIG_ENV))


def _log_dormant_once() -> None:
    global _dormant_logged
    if not _dormant_logged:
        _dormant_logged = True
        logger.info("ops_events.dormant", reason=f"{CONFIG_ENV} is not set")


def _present(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in _ABSENT else text


def _match_date(match: dict) -> str | None:
    # A timestamp reads as its day; the time is the scheduled kickoff's business.
    date = _present(match.get("match_date"))
    return date[:10] if date else None


def build_match_final_event(match: dict) -> dict | None:
    """The notify() fields for a final score, or None if the row has no score.

    Team names are typed by people. They go through as plain text: each sink
    escapes and defangs for its own platform, so adding markup here would only
    break that.
    """
    match_id = match.get("id")
    home_score, away_score = match.get("home_score"), match.get("away_score")
    if match_id is None or home_score is None or away_score is None:
        return None

    home = _present(match.get("home_team_name")) or "Home team"
    away = _present(match.get("away_team_name")) or "Away team"

    competition = _present(match.get("tournament_name")) or _present(match.get("match_type_name"))
    details = [
        competition,
        _present(match.get("age_group_name")),
        _present(match.get("division_name")),
        _match_date(match),
    ]
    body = " · ".join(part for part in details if part) or None
    home_pens, away_pens = match.get("home_penalty_score"), match.get("away_penalty_score")
    if home_pens is not None and away_pens is not None:
        pens = f"Penalties {home_pens}{SCORE_DASH}{away_pens}"
        body = f"{body}\n{pens}" if body else pens

    tags = {
        "age_group": _present(match.get("age_group_name")),
        "match_type": _present(match.get("match_type_name")),
        # Who wrote the score: the scraper, or a person in the app.
        "match_source": _present(match.get("source")),
    }

    base_url = os.getenv("APP_BASE_URL", "https://missingtable.com").rstrip("/")
    return {
        "source": SOURCE,
        "kind": MATCH_FINAL_KIND,
        "level": "info",
        "title": f"{home} {home_score}{SCORE_DASH}{away_score} {away}",
        "body": body,
        # The SPA opens MatchDetailView from ?matchId= (see App.vue, SB-86).
        "links": [("Match", f"{base_url}/?matchId={match_id}")],
        "tags": {key: value for key, value in tags.items() if value},
        "dedupe_key": f"{MATCH_FINAL_KIND}:{match_id}:{home_score}-{away_score}",
    }


def emit_match_final(match: dict) -> None:
    """Send one `mt.match_final` event for a match that just got its final score."""
    if not is_enabled():
        _log_dormant_once()
        return
    match_id = (match or {}).get("id")
    try:
        if match.get("is_test"):
            # A TSC rehearsal is not a result (SB-591 keeps it out of every public room too).
            logger.info("ops_events.skipped", kind=MATCH_FINAL_KIND, match_id=match_id, reason="test_match")
            return
        fields = build_match_final_event(match)
        if fields is None:
            logger.info("ops_events.skipped", kind=MATCH_FINAL_KIND, match_id=match_id, reason="no_score")
            return
        result = notify(**fields)
        # Status and reason only: outcomes are safe too, but a destination never is.
        logger.info(
            "ops_events.sent",
            kind=MATCH_FINAL_KIND,
            match_id=match_id,
            status=str(result.status),
            reason=str(result.reason) if result.reason else None,
            held_until=result.held_until,
        )
    except Exception as exc:
        logger.warning(
            "ops_events.failed",
            kind=MATCH_FINAL_KIND,
            match_id=match_id,
            error_type=type(exc).__name__,
        )


def emit_match_final_by_id(match_id: int, load_match: Callable[[int], dict | None]) -> None:
    """Load the match, then `emit_match_final`. The read is skipped while dormant."""
    if not is_enabled():
        _log_dormant_once()
        return
    try:
        match = load_match(match_id)
    except Exception as exc:
        logger.warning(
            "ops_events.failed",
            kind=MATCH_FINAL_KIND,
            match_id=match_id,
            error_type=type(exc).__name__,
        )
        return
    if not match:
        logger.info("ops_events.skipped", kind=MATCH_FINAL_KIND, match_id=match_id, reason="match_not_found")
        return
    emit_match_final(match)

"""Telegram alerts for names the match ingest could not resolve (SB-829).

The point of this module is that a failed load should be *noticed*. Before it,
an unresolved name produced a `logger.error` in a worker pod, and the scraper's
own Telegram report showed the run as green — it counts RabbitMQ publish
errors, and publishing succeeds regardless of whether the match is accepted.

Two rules keep the alerting readable:

- **One message per distinct name, not per dropped match.** A season load that
  dies on seven spellings sends seven messages, however many hundreds of
  fixtures they cost. `ingest_failures.was_new` is what gates that.
- **A cap per window.** A brand-new season can arrive with dozens of unknown
  names, and a message each would be its own kind of unreadable. Past the cap
  one summary message points at the API and the rest stay silent — they are
  still recorded, so nothing is lost.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from notifications.senders import send_to

logger = structlog.get_logger()

# Where operator alerts go. Deliberately separate from club notification
# destinations: those are chosen by users, this one is the operator's.
CHAT_ID_ENV = "MT_ADMIN_TELEGRAM_CHAT_ID"

DEFAULT_MAX_ALERTS_PER_WINDOW = 10
WINDOW = timedelta(hours=1)

_KIND_LABEL = {
    "team": "Unknown team",
    "division": "Unknown division",
    "league": "Unknown league",
    "invalid": "Invalid match data",
}

# The fix for a bad team name is one CLI command (SB-822/SB-824). Putting it in
# the alert is the difference between a notification and a task.
_KIND_FIX = {
    "team": 'mt team alias add <team> "{raw_name}"',
    "division": "mt division create — or correct the feed's league mapping",
}


def _max_alerts_per_window() -> int:
    try:
        return int(os.getenv("MT_INGEST_ALERT_MAX_PER_HOUR", DEFAULT_MAX_ALERTS_PER_WINDOW))
    except ValueError:
        return DEFAULT_MAX_ALERTS_PER_WINDOW


def _format(kind: str, raw_name: str, league: str | None, sample: str | None, match_count: int) -> str:
    lines = [
        "⚠️ MT ingest blocked",
        f"{_KIND_LABEL.get(kind, kind)}: {raw_name}",
    ]
    context = " · ".join(p for p in (f"league: {league}" if league else None, sample) if p)
    if context:
        lines.append(context)
    lines.append(f"Matches dropped so far: {match_count}")
    fix = _KIND_FIX.get(kind)
    if fix:
        lines.append(f"Fix: {fix.format(raw_name=raw_name)}")
    return "\n".join(lines)


def alert_unresolved_name(
    ingest_dao: Any,
    *,
    kind: str,
    raw_name: str,
    league: str | None,
    sample: str | None,
    record: dict[str, Any] | None,
) -> bool:
    """Send one Telegram alert for a newly-seen unresolved name.

    `record` is the row returned by IngestFailuresDAO.record. Returns whether a
    message was sent.

    Never raises. Alerting is the diagnostic path; a diagnostic that can take
    down ingest is worse than no diagnostic, and the failure is already durable
    in `ingest_failures` by the time this runs.
    """
    try:
        if not record or not record.get("should_alert"):
            return False

        chat_id = os.getenv(CHAT_ID_ENV)
        if not chat_id:
            # Expected locally and in CI. The row is still recorded, and the
            # scraper's run report reads it over the API either way.
            logger.info("Ingest failure recorded but not alerted — %s is unset", CHAT_ID_ENV, raw_name=raw_name)
            return False

        window_start = (datetime.now(tz=UTC) - WINDOW).isoformat()
        already = ingest_dao.notified_since(window_start)
        cap = _max_alerts_per_window()

        if already > cap:
            return False
        if already == cap:
            # Exactly at the cap: say so once, then go quiet for the window.
            send_to(
                "telegram",
                chat_id,
                f"⚠️ MT ingest: more than {cap} unresolved names this hour. "
                "Further names are recorded but not alerted — "
                "see GET /api/admin/ingest-failures for the full list.",
            )
            ingest_dao.mark_notified([record["id"]])
            return True

        send_to("telegram", chat_id, _format(kind, raw_name, league, sample, record.get("match_count", 1)))
        ingest_dao.mark_notified([record["id"]])
        logger.info("Alerted on unresolved name", kind=kind, raw_name=raw_name)
        return True

    except Exception:
        logger.exception("Could not alert on unresolved name", kind=kind, raw_name=raw_name)
        return False

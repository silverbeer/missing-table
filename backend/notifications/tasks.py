"""BackgroundTasks-friendly entry point for the dispatcher.

FastAPI's BackgroundTasks runs these after the response is sent, so any
exception is captured silently — we swallow and log explicitly to avoid
surprising failures during high-traffic live matches.
"""

from __future__ import annotations

import structlog

from notifications.dispatcher import get_notifier
from notifications.ops_events import emit_match_final_by_id

logger = structlog.get_logger(__name__)


def notify_event_task(
    event_type: str,
    match_id: int,
    extra: dict | None = None,
    event_key: str | None = None,
) -> None:
    """Fire a notification without ever raising."""
    try:
        get_notifier().notify(event_type=event_type, match_id=match_id, extra=extra, event_key=event_key)
    except Exception as exc:
        logger.warning(
            "notifications.task_failed",
            event_type=event_type,
            match_id=match_id,
            error_type=type(exc).__name__,
            error=str(exc),
        )

    # Operator channel (SB-1849). Every new final score reaches the app as a
    # "fulltime" task: the admin/skill match write, the scraper's
    # final-score-alert call and live scoring's end_match. Hooking here, after
    # the fan-out and independent of it, means none of the three is missed.
    if event_type == "fulltime":
        emit_match_final_by_id(match_id, _load_match)


def _load_match(match_id: int) -> dict | None:
    return get_notifier().match_dao.get_match_by_id(match_id, include_test=True)

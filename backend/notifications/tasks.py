"""BackgroundTasks-friendly entry point for the dispatcher.

FastAPI's BackgroundTasks runs these after the response is sent, so any
exception is captured silently — we swallow and log explicitly to avoid
surprising failures during high-traffic live matches.
"""

from __future__ import annotations

import structlog

from notifications.dispatcher import get_notifier

logger = structlog.get_logger(__name__)


def notify_event_task(
    event_type: str,
    match_id: int,
    extra: dict | None = None,
) -> None:
    """Fire a notification without ever raising."""
    try:
        get_notifier().notify(event_type=event_type, match_id=match_id, extra=extra)
    except Exception as exc:
        logger.warning(
            "notifications.task_failed",
            event_type=event_type,
            match_id=match_id,
            error_type=type(exc).__name__,
            error=str(exc),
        )

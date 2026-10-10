"""Telegram alert to the operator when a chat message is reported (SB-1309).

App Store guideline 1.2 asks for a timely response to reports. A report that
only lands in a table is answered whenever someone next opens the admin
screen; this puts it in front of the operator straight away. The admin
attention badge counts the same reports, so nothing depends on the alert
arriving.

Same destination and the same per-window cap as the ingest alerts
(notifications/ingest_alerts.py): a burst of reports — one abusive user, a
dozen parents — sends at most the cap, then one summary, then silence for the
rest of the hour. Every report is still recorded.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from notifications.ingest_alerts import CHAT_ID_ENV
from notifications.senders import send_to

logger = structlog.get_logger()

DEFAULT_MAX_ALERTS_PER_WINDOW = 10
WINDOW = timedelta(hours=1)
_MESSAGE_PREVIEW = 200


def _max_alerts_per_window() -> int:
    try:
        return int(os.getenv("MT_REPORT_ALERT_MAX_PER_HOUR", DEFAULT_MAX_ALERTS_PER_WINDOW))
    except ValueError:
        return DEFAULT_MAX_ALERTS_PER_WINDOW


def _truncate(text: str) -> str:
    return text if len(text) <= _MESSAGE_PREVIEW else text[: _MESSAGE_PREVIEW - 1] + "…"


def _format(report: dict[str, Any], reporter_username: str | None) -> str:
    lines = [
        "🚩 MT chat message reported",
        f"Reason: {report.get('reason')}",
        f"Author: {report.get('reported_username') or 'unknown'}",
        f"Reported by: {reporter_username or 'unknown'}",
        f"Match: {report.get('match_id')}",
        f"Message: {_truncate(report.get('message_text') or '')}",
    ]
    if report.get("details"):
        lines.append(f"Details: {_truncate(report['details'])}")
    lines.append("Review: GET /api/admin/content-reports?status=pending")
    return "\n".join(lines)


def alert_content_report(moderation_dao: Any, report: dict[str, Any], reporter_username: str | None) -> bool:
    """Send one Telegram alert for a new report. Returns whether one was sent.

    Never raises: the report is already recorded, and a reporter must not see
    an error because the operator's alert channel is down or unconfigured.
    """
    try:
        chat_id = os.getenv(CHAT_ID_ENV)
        if not chat_id:
            logger.info(
                "Content report recorded but not alerted — %s is unset", CHAT_ID_ENV, report_id=report.get("id")
            )
            return False

        window_start = (datetime.now(tz=UTC) - WINDOW).isoformat()
        # Includes this report, which is already inserted.
        earlier = moderation_dao.count_reports_since(window_start) - 1
        cap = _max_alerts_per_window()

        if earlier > cap:
            return False
        if earlier == cap:
            send_to(
                "telegram",
                chat_id,
                f"🚩 MT chat: more than {cap} reports this hour. Further reports are recorded "
                "but not alerted — see GET /api/admin/content-reports?status=pending.",
            )
            return True

        send_to("telegram", chat_id, _format(report, reporter_username))
        logger.info("Alerted on content report", report_id=report.get("id"))
        return True

    except Exception:
        logger.exception("Could not alert on content report", report_id=report.get("id"))
        return False

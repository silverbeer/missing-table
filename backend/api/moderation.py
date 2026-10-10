"""
Live chat moderation API (SB-1309, App Store guideline 1.2).

Endpoints:
- POST   /api/matches/{match_id}/live/events/{event_id}/report — report a chat message
                                                                  (also blocks its author)
- POST   /api/users/{user_id}/block                              — block a user
- DELETE /api/users/{user_id}/block                              — unblock
- GET    /api/users/me/blocks                                    — who I have blocked
- GET    /api/admin/content-reports                              — review queue (admin)
- PATCH  /api/admin/content-reports/{report_id}                  — act on a report (admin)

The other halves live with the chat endpoints in app.py: the word filter and
the ban check on POST /live/message, and hiding blocked authors on the reads.
"""

from __future__ import annotations

from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from auth import get_current_user_required, require_admin
from dao.match_dao import SupabaseConnection
from dao.match_event_dao import MatchEventDAO
from dao.moderation_dao import ModerationDAO, UnknownUserError
from notifications.moderation_alerts import alert_content_report

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["moderation"])


# ---------------------------------------------------------------------------
# Lazy connection + DAO singletons
# ---------------------------------------------------------------------------

_connection: SupabaseConnection | None = None


def _conn() -> SupabaseConnection:
    global _connection
    if _connection is None:
        _connection = SupabaseConnection()
    return _connection


def _moderation_dao() -> ModerationDAO:
    return ModerationDAO(_conn())


def _event_dao() -> MatchEventDAO:
    return MatchEventDAO(_conn())


def _user_id(user: dict[str, Any]) -> str:
    """auth.py's current_user dict uses either 'user_id' or 'id'."""
    uid = user.get("user_id") or user.get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Missing user identity")
    return str(uid)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ReportIn(BaseModel):
    """Body of POST /api/matches/{match_id}/live/events/{event_id}/report."""

    reason: Literal["spam", "harassment", "hate", "sexual", "other"]
    details: str | None = Field(None, max_length=500)


class ReportActionIn(BaseModel):
    """Body of PATCH /api/admin/content-reports/{report_id}."""

    action: Literal["dismiss", "delete_message", "ban_user"]


# An action's resulting report status.
_ACTION_STATUS = {"dismiss": "dismissed", "delete_message": "actioned", "ban_user": "actioned"}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@router.post(
    "/matches/{match_id}/live/events/{event_id}/report",
    status_code=status.HTTP_201_CREATED,
)
def report_event(
    match_id: int,
    event_id: int,
    payload: ReportIn,
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> dict[str, Any]:
    """Report a chat message, and block its author for the reporter.

    Reporting the same message twice is not an error: the second call records
    nothing new, sends no alert, and answers the same way.
    """
    reporter_id = _user_id(current_user)

    event = _event_dao().get_event_by_id(event_id)
    if not event or event.get("match_id") != match_id:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.get("event_type") != "message":
        raise HTTPException(status_code=400, detail="Only chat messages can be reported")

    author_id = event.get("created_by")
    if author_id and str(author_id) == reporter_id:
        raise HTTPException(status_code=400, detail="You cannot report your own message")

    dao = _moderation_dao()
    report = dao.create_report(event=event, reporter_id=reporter_id, reason=payload.reason, details=payload.details)

    if author_id:
        try:
            dao.block_user(reporter_id, str(author_id))
        except UnknownUserError:
            # The author's account is gone; their messages go with it.
            logger.info("report_author_has_no_profile", event_id=event_id)

    if report:
        logger.info("content_reported", report_id=report.get("id"), event_id=event_id, reason=payload.reason)
        alert_content_report(dao, report, current_user.get("username"))

    return {"reported": True, "blocked_user_id": str(author_id) if author_id else None}


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


@router.post("/users/{user_id}/block", status_code=status.HTTP_204_NO_CONTENT)
def block_user(
    user_id: str,
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> Response:
    blocker_id = _user_id(current_user)
    if user_id == blocker_id:
        raise HTTPException(status_code=400, detail="You cannot block yourself")
    try:
        _moderation_dao().block_user(blocker_id, user_id)
    except UnknownUserError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/users/{user_id}/block", status_code=status.HTTP_204_NO_CONTENT)
def unblock_user(
    user_id: str,
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> Response:
    _moderation_dao().unblock_user(_user_id(current_user), user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/me/blocks")
def list_blocks(
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> list[dict[str, Any]]:
    return _moderation_dao().list_blocks(_user_id(current_user))


# ---------------------------------------------------------------------------
# Admin review
# ---------------------------------------------------------------------------


@router.get("/admin/content-reports")
def list_content_reports(
    status_filter: Literal["pending", "actioned", "dismissed"] | None = Query(None, alias="status"),
    _admin: dict[str, Any] = Depends(require_admin),
) -> list[dict[str, Any]]:
    return _moderation_dao().list_reports(status_filter)


@router.patch("/admin/content-reports/{report_id}")
def act_on_content_report(
    report_id: int,
    payload: ReportActionIn,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Dismiss a report, delete the message, or delete it and ban its author.

    The message may already be gone — expired, or deleted by its author or a
    manager — in which case deleting it is skipped and the report still
    resolves.
    """
    admin_id = _user_id(admin)
    dao = _moderation_dao()

    report = dao.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if payload.action == "ban_user" and not report.get("reported_user_id"):
        raise HTTPException(status_code=400, detail="The author's account no longer exists")

    if payload.action in ("delete_message", "ban_user") and report.get("event_id"):
        _event_dao().soft_delete_event(report["event_id"], deleted_by=admin_id)

    if payload.action == "ban_user":
        dao.ban_from_chat(report["reported_user_id"])

    updated = dao.resolve_report(
        report_id, status=_ACTION_STATUS[payload.action], action=payload.action, resolved_by=admin_id
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update report")

    logger.info("content_report_resolved", report_id=report_id, action=payload.action, admin_id=admin_id)
    return updated

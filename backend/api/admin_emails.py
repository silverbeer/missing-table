"""
Admin API for the Support Inbox (SB-35 Phase 2).

Exposes the JSON surface the Phase 3 admin UI will consume:

    GET    /api/admin/emails/threads               list w/ keyset pagination
    GET    /api/admin/emails/threads/{id_or_mt_n}  thread + messages
    POST   /api/admin/emails/threads/{id}/reply    send outbound + persist
    PATCH  /api/admin/emails/threads/{id}/status   manual status override
    PATCH  /api/admin/emails/threads/{id}/read     zero unread_count + stamp read_at
    GET    /api/admin/emails/unread-count          attention badge

All endpoints gated by `require_admin`. Admin operations use the service-role
client (same project pattern as backend/api/invites.py) so the auth dependency
is the trust gate.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from supabase import create_client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import require_admin
from dao.email_messages_dao import EmailMessagesDAO
from dao.email_threads_dao import EmailThreadsDAO
from dao.match_dao import SupabaseConnection as DbConnectionHolder
from services.email_outbound import send_admin_reply

logger = structlog.get_logger(__name__)

# Service-role connection for admin reads/writes. require_admin is the trust
# gate — same pattern as backend/api/invites.py.
_supabase_url = os.getenv("SUPABASE_URL", "")
_service_key = os.getenv("SUPABASE_SERVICE_KEY")
if _service_key:
    _service_client = create_client(_supabase_url, _service_key)
    _conn_holder = DbConnectionHolder()
    # Pin the DAO's client to the service-role client by reaching into the
    # holder. Mirrors how invites.py uses service_client directly but keeps
    # the DAOs' query surface.
    _conn_holder.client = _service_client
else:
    _conn_holder = DbConnectionHolder()

_threads_dao = EmailThreadsDAO(_conn_holder)
_messages_dao = EmailMessagesDAO(_conn_holder)

router = APIRouter(prefix="/api/admin/emails", tags=["admin-emails"])


# ── Constants ────────────────────────────────────────────────────────────────

_DEFAULT_STATUSES = ("new", "awaiting_admin")
_ALL_STATUSES = frozenset(
    {"new", "awaiting_admin", "awaiting_user", "resolved", "spam"}
)
_MT_PATH_RE = re.compile(r"^MT-(\d+)$", re.IGNORECASE)
_LIMIT_DEFAULT = 50
_LIMIT_MAX = 200


# ── Pydantic models ──────────────────────────────────────────────────────────


class ReplyRequest(BaseModel):
    body_text: str = Field(..., min_length=1)
    body_html: str | None = None


class StatusUpdateRequest(BaseModel):
    status: Literal["resolved", "spam", "awaiting_admin"]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _admin_user_id(current_user: dict[str, Any]) -> str:
    """Pluck the user id out of the auth payload. Different code paths populate
    different keys (id / user_id / sub) — same fallback chain as invites.py.
    """
    user_id = (
        current_user.get("id")
        or current_user.get("user_id")
        or current_user.get("sub")
    )
    if not user_id:
        raise HTTPException(status_code=400, detail="user id missing from auth payload")
    return user_id


def _resolve_thread_or_404(thread_id_or_case_number: str) -> dict[str, Any]:
    """Path-param resolver: accepts either a UUID or `MT-{n}` form."""
    mt_match = _MT_PATH_RE.match(thread_id_or_case_number)
    if mt_match:
        case_number = int(mt_match.group(1))
        thread = _threads_dao.get_by_case_number(case_number)
    else:
        thread = _threads_dao.get_thread_by_id(thread_id_or_case_number)

    if not thread:
        raise HTTPException(
            status_code=404, detail=f"thread {thread_id_or_case_number!r} not found"
        )
    return thread


def _parse_statuses(raw: str | None) -> list[str]:
    if not raw:
        return list(_DEFAULT_STATUSES)
    values = [v.strip() for v in raw.split(",") if v.strip()]
    invalid = [v for v in values if v not in _ALL_STATUSES]
    if invalid:
        raise HTTPException(
            status_code=400, detail=f"invalid status value(s): {invalid}"
        )
    return values


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/threads")
async def list_threads(
    status: str | None = Query(
        default=None,
        description="CSV of status values; default 'new,awaiting_admin'.",
    ),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=_LIMIT_DEFAULT, ge=1, le=_LIMIT_MAX),
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Paginated list of threads. Keyset cursor on (last_message_at, id)."""
    statuses = _parse_statuses(status)
    try:
        return _threads_dao.list_by_status(statuses, limit=limit, cursor=cursor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/unread-count")
async def get_unread_count(
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, int]:
    """Sum of unread_count across threads in (new, awaiting_admin)."""
    return {"count": _threads_dao.unread_count_for_attention()}


@router.get("/threads/{thread_id_or_case_number}")
async def get_thread(
    thread_id_or_case_number: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Thread + all messages in chronological order. Accepts UUID or `MT-{n}`."""
    # Resolve to UUID first, then fetch with embedded messages.
    thread = _resolve_thread_or_404(thread_id_or_case_number)
    full = _threads_dao.get_thread_with_messages(thread["id"])
    if not full:
        # Could only happen on a race with deletion.
        raise HTTPException(status_code=404, detail="thread not found")
    return full


@router.post("/threads/{thread_id}/reply")
async def reply_to_thread(
    thread_id: str,
    request: ReplyRequest,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Send an outbound reply on the thread.

    - Generates a fresh Message-ID and threads correctly via In-Reply-To/References.
    - Idempotently prefixes the subject with [MT-{n}].
    - Persists the outbound message and transitions the thread to awaiting_user.
    """
    thread = _resolve_thread_or_404(thread_id)
    admin_user_id = _admin_user_id(current_user)

    try:
        row = send_admin_reply(
            _threads_dao,
            _messages_dao,
            thread=thread,
            body_text=request.body_text,
            body_html=request.body_html,
            admin_user_id=admin_user_id,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return row


@router.patch("/threads/{thread_id}/status")
async def patch_status(
    thread_id: str,
    request: StatusUpdateRequest,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Manual status override (resolved / spam / awaiting_admin)."""
    thread = _resolve_thread_or_404(thread_id)
    try:
        updated = _threads_dao.set_status(thread["id"], request.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not updated:
        raise HTTPException(status_code=404, detail="thread not found")
    return updated


@router.patch("/threads/{thread_id}/read")
async def mark_read(
    thread_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Zero unread_count and stamp read_at on every unread message."""
    thread = _resolve_thread_or_404(thread_id)
    updated = _threads_dao.mark_all_read(thread["id"])
    return {"thread_id": thread["id"], "messages_marked_read": updated}

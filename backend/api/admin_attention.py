"""
Admin attention badge API (SB-4X).

Powers the red dot + hover tooltip on the global top-nav "Admin" link.
One endpoint, one round trip per poll — aggregates pending counts across
the Access sub-sections that actually have a request queue.

Live Match Notifications is excluded — it's a per-club config surface
with no pending state to count.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from supabase import create_client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import require_admin
from dao.admin_attention_dao import AdminAttentionDAO
from dao.match_dao import SupabaseConnection as DbConnectionHolder

logger = structlog.get_logger(__name__)

# Service-role connection — require_admin is the trust gate, same pattern
# as backend/api/admin_emails.py.
_supabase_url = os.getenv("SUPABASE_URL", "")
_service_key = os.getenv("SUPABASE_SERVICE_KEY")
if _service_key:
    _service_client = create_client(_supabase_url, _service_key)
    _conn_holder = DbConnectionHolder()
    _conn_holder.client = _service_client
else:
    _conn_holder = DbConnectionHolder()

_dao = AdminAttentionDAO(_conn_holder)

router = APIRouter(prefix="/api/admin/attention", tags=["admin-attention"])


class AttentionCounts(BaseModel):
    invite_requests: int
    channel_requests: int
    support_inbox: int
    total: int


@router.get("/counts", response_model=AttentionCounts)
async def get_attention_counts(
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, int]:
    """Per-queue pending counts for the admin nav badge.

    Cached 30s via Redis when CACHE_ENABLED — repeat polls from multiple
    admin sessions share one DB fan-out per window. With Redis off, every
    call hits the DB fresh (still cheap — three count queries).
    """
    return _dao.get_counts()

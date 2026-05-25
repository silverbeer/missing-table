"""
AdminAttentionDAO — single-shot aggregator for the admin nav badge.

Counts items across three "needs admin attention" queues:
- Invite Requests in 'pending' status
- Channel Requests with any platform in 'pending' (telegram or discord)
- Support Inbox threads with unread messages where status is 'new' or 'awaiting_admin'
  (delegates to EmailThreadsDAO.unread_count_for_attention)

Result is cached for 30s via @dao_cache when Redis is enabled; otherwise the
decorator no-ops and every call hits the DB (still fine — these are tiny
count queries).
"""

from __future__ import annotations

from typing import Any

import structlog

from dao.base_dao import BaseDAO, dao_cache
from dao.email_threads_dao import EmailThreadsDAO

logger = structlog.get_logger()

# 30s TTL: short enough that admins see updates promptly, long enough that
# multiple admin sessions share a single fan-out per 30s window.
_CACHE_TTL = 30


class AdminAttentionDAO(BaseDAO):
    """Aggregator for the admin top-nav attention badge."""

    @dao_cache("admin_attention:counts", ttl=_CACHE_TTL)
    def get_counts(self) -> dict[str, Any]:
        """Return per-queue pending counts plus a total.

        Shape:
            {
              "invite_requests": int,
              "channel_requests": int,
              "support_inbox": int,
              "total": int,
            }

        Each count is the number of items needing admin attention — not a
        full record count. invite_requests counts rows with status='pending';
        channel_requests counts distinct rows with either telegram_status
        or discord_status in 'pending'; support_inbox sums unread messages
        across threads in 'new' or 'awaiting_admin'.
        """
        invite_requests = self._count_pending_invite_requests()
        channel_requests = self._count_pending_channel_requests()
        support_inbox = EmailThreadsDAO(self.connection_holder).unread_count_for_attention()

        total = invite_requests + channel_requests + support_inbox
        return {
            "invite_requests": invite_requests,
            "channel_requests": channel_requests,
            "support_inbox": support_inbox,
            "total": total,
        }

    def _count_pending_invite_requests(self) -> int:
        response = (
            self.client.table("invite_requests")
            .select("id", count="exact")
            .eq("status", "pending")
            .execute()
        )
        return response.count or 0

    def _count_pending_channel_requests(self) -> int:
        """Count distinct channel-request rows with any platform pending.

        A single row tracks both Telegram and Discord status, and a request
        is "pending" if either side is in 'pending'. We count rows (not
        platform-pending instances) so the badge mirrors the inbox tab's
        notion of work-to-do.
        """
        # PostgREST `or` filter: telegram_status.eq.pending,discord_status.eq.pending
        response = (
            self.client.table("channel_requests")
            .select("id", count="exact")
            .or_("telegram_status.eq.pending,discord_status.eq.pending")
            .execute()
        )
        return response.count or 0

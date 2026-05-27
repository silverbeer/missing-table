"""Team Follow DAO.

Tracks which teams a user follows. Many-to-many. Cross-club by design:
a user can follow teams from any number of clubs (see
project_engagement_flywheel memory).

The list_subscriptions_for_team_ids method is the fan-out hot path —
called once per match event to find every push subscription that should
receive a notification.
"""

from __future__ import annotations

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

TABLE = "user_team_follows"


class TeamFollowDAO(BaseDAO):
    """Data access for user→team follow relationships."""

    def follow(self, user_id: str, team_id: int) -> bool:
        """Follow a team. Idempotent — re-following returns True silently."""
        try:
            # Check for existing first to keep idempotency clean.
            existing = (
                self.client.table(TABLE)
                .select("user_id")
                .eq("user_id", user_id)
                .eq("team_id", team_id)
                .limit(1)
                .execute()
            )
            if existing.data:
                return True
            self.client.table(TABLE).insert(
                {"user_id": user_id, "team_id": team_id}
            ).execute()
            return True
        except Exception:
            logger.exception(
                "team_follow_failed", user_id=user_id, team_id=team_id
            )
            return False

    def unfollow(self, user_id: str, team_id: int) -> bool:
        """Unfollow a team. Idempotent — returns True even if not following."""
        try:
            self.client.table(TABLE).delete().eq("user_id", user_id).eq(
                "team_id", team_id
            ).execute()
            return True
        except Exception:
            logger.exception(
                "team_unfollow_failed", user_id=user_id, team_id=team_id
            )
            return False

    def list_for_user(self, user_id: str) -> list[dict]:
        """Return teams the user follows, joined with club info for display."""
        try:
            response = (
                self.client.table(TABLE)
                .select(
                    "team_id, created_at, "
                    "team:teams!user_team_follows_team_id_fkey("
                    "id, name, age_group_id, "
                    "club:clubs(id, name)"
                    ")"
                )
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data or []
        except Exception:
            logger.exception("team_follow_list_failed", user_id=user_id)
            return []

    def list_subscriptions_for_team_ids(
        self, team_ids: list[int]
    ) -> list[dict]:
        """Fan-out query: every push subscription whose owner follows any of these teams.

        Returns deduplicated subscription rows (a user with multiple devices
        appears multiple times; that's intentional — each device gets its
        own push). Deduplication is by subscription.id, not user, so a user
        following both home and away teams still gets one push per device,
        not two.
        """
        if not team_ids:
            return []
        try:
            response = (
                self.client.table(TABLE)
                .select(
                    "user_id, "
                    "subscriptions:push_subscriptions!push_subscriptions_user_id_fkey("
                    "id, endpoint, p256dh_key, auth_key"
                    ")"
                )
                .in_("team_id", team_ids)
                .execute()
            )
            rows = response.data or []
            # Flatten and dedupe by subscription id
            seen_ids: set[str] = set()
            flat: list[dict] = []
            for row in rows:
                user_id = row.get("user_id")
                for sub in row.get("subscriptions") or []:
                    if sub["id"] in seen_ids:
                        continue
                    seen_ids.add(sub["id"])
                    flat.append({**sub, "user_id": user_id})
            return flat
        except Exception:
            logger.exception(
                "team_follow_list_subscriptions_failed", team_ids=team_ids
            )
            return []

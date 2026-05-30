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
        """Return teams the user follows, joined with club + division + league
        for display.

        SB-65: the original projection returned only `team.name` and
        `team.club.name`. For many MLS Next teams those two strings are
        identical (the team name IS the club name), making the "Teams you
        follow" list in the profile look like it's about clubs. Surfacing
        `team.division.name` and the division's league disambiguates each
        row (e.g. "IFA · Homegrown · Northeast").
        """
        try:
            response = (
                self.client.table(TABLE)
                .select(
                    "team_id, created_at, "
                    "team:teams!user_team_follows_team_id_fkey("
                    "id, name, age_group_id, "
                    "club:clubs(id, name), "
                    "division:divisions("
                    "id, name, "
                    "leagues!divisions_league_id_fkey(id, name)"
                    ")"
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

        Implemented as two plain `in_` queries rather than a PostgREST embed.
        `user_team_follows` and `push_subscriptions` have no direct foreign key
        between them (both only reference `user_profiles`), so PostgREST cannot
        embed one from the other — the embed form raises PGRST200, and since the
        DAO swallows exceptions, the dispatcher would silently deliver zero
        pushes. This is the fan-out that decides who actually gets notified
        (SB-77); see tests/integration/test_push_delivery_on_score.py.
        """
        if not team_ids:
            return []
        try:
            # Step 1: distinct users following any of these teams.
            follow_resp = (
                self.client.table(TABLE)
                .select("user_id")
                .in_("team_id", team_ids)
                .execute()
            )
            user_ids = list(
                {
                    row["user_id"]
                    for row in (follow_resp.data or [])
                    if row.get("user_id")
                }
            )
            if not user_ids:
                return []

            # Step 2: every push subscription owned by those users.
            sub_resp = (
                self.client.table("push_subscriptions")
                .select("id, endpoint, p256dh_key, auth_key, user_id")
                .in_("user_id", user_ids)
                .execute()
            )

            # Dedupe by subscription id (a user with 2 devices yields 2 rows —
            # intentional; each device gets its own push).
            seen_ids: set[str] = set()
            flat: list[dict] = []
            for sub in sub_resp.data or []:
                if sub["id"] in seen_ids:
                    continue
                seen_ids.add(sub["id"])
                flat.append(sub)
            return flat
        except Exception:
            logger.exception(
                "team_follow_list_subscriptions_failed", team_ids=team_ids
            )
            return []

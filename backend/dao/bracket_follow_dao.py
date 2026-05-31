"""Bracket Follow DAO.

Tracks which tournament brackets a user follows. A bracket is the tuple
(tournament_id, tournament_group, age_group_id) — e.g. "Bracket A · U14".
Following a bracket means: get a Web Push when any match in that bracket
reaches a final score (fulltime). See dispatcher._send_push_fanout.

list_subscriptions_for_bracket is the fan-out hot path — called once per
fulltime event to find every push subscription that should receive it.
Mirrors TeamFollowDAO (dao/team_follow_dao.py).
"""

from __future__ import annotations

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

TABLE = "user_bracket_follows"


class BracketFollowDAO(BaseDAO):
    """Data access for user→bracket follow relationships."""

    def follow(
        self,
        user_id: str,
        tournament_id: int,
        tournament_group: str,
        age_group_id: int,
    ) -> bool:
        """Follow a bracket. Idempotent — re-following returns True silently."""
        try:
            existing = (
                self.client.table(TABLE)
                .select("user_id")
                .eq("user_id", user_id)
                .eq("tournament_id", tournament_id)
                .eq("tournament_group", tournament_group)
                .eq("age_group_id", age_group_id)
                .limit(1)
                .execute()
            )
            if existing.data:
                return True
            self.client.table(TABLE).insert(
                {
                    "user_id": user_id,
                    "tournament_id": tournament_id,
                    "tournament_group": tournament_group,
                    "age_group_id": age_group_id,
                }
            ).execute()
            return True
        except Exception:
            logger.exception(
                "bracket_follow_failed",
                user_id=user_id,
                tournament_id=tournament_id,
                tournament_group=tournament_group,
                age_group_id=age_group_id,
            )
            return False

    def unfollow(
        self,
        user_id: str,
        tournament_id: int,
        tournament_group: str,
        age_group_id: int,
    ) -> bool:
        """Unfollow a bracket. Idempotent — returns True even if not following."""
        try:
            (
                self.client.table(TABLE)
                .delete()
                .eq("user_id", user_id)
                .eq("tournament_id", tournament_id)
                .eq("tournament_group", tournament_group)
                .eq("age_group_id", age_group_id)
                .execute()
            )
            return True
        except Exception:
            logger.exception(
                "bracket_unfollow_failed",
                user_id=user_id,
                tournament_id=tournament_id,
                tournament_group=tournament_group,
                age_group_id=age_group_id,
            )
            return False

    def list_for_user(self, user_id: str) -> list[dict]:
        """Return brackets the user follows, joined with tournament + age group
        names for display."""
        try:
            response = (
                self.client.table(TABLE)
                .select(
                    "tournament_id, tournament_group, age_group_id, created_at, "
                    "tournament:tournaments(id, name, logo_url), "
                    "age_group:age_groups(id, name)"
                )
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data or []
        except Exception:
            logger.exception("bracket_follow_list_failed", user_id=user_id)
            return []

    def list_subscriptions_for_bracket(
        self,
        tournament_id: int,
        tournament_group: str,
        age_group_id: int,
    ) -> list[dict]:
        """Fan-out query: every push subscription whose owner follows this bracket.

        Returns subscription rows (id, endpoint, p256dh_key, auth_key, user_id),
        deduplicated by subscription id (a user with multiple devices appears
        once per device — intentional, each device gets its own push).

        Two plain `in_`/`eq` queries rather than a PostgREST embed: as with
        user_team_follows, there is no FK between user_bracket_follows and
        push_subscriptions (both only reference user_profiles), so an embed
        raises PGRST200 and — since the DAO swallows exceptions — the dispatcher
        would silently deliver zero pushes. See dao/team_follow_dao.py:97.
        """
        try:
            # Step 1: distinct users following this exact bracket.
            follow_resp = (
                self.client.table(TABLE)
                .select("user_id")
                .eq("tournament_id", tournament_id)
                .eq("tournament_group", tournament_group)
                .eq("age_group_id", age_group_id)
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
                "bracket_follow_list_subscriptions_failed",
                tournament_id=tournament_id,
                tournament_group=tournament_group,
                age_group_id=age_group_id,
            )
            return []

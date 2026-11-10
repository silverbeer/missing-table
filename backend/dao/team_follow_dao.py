"""Team Follow DAO.

Tracks which teams, or squads, a user follows. Many-to-many. Cross-club by
design: a user can follow teams from any number of clubs (see
project_engagement_flywheel memory).

A team row spans several age groups, so a follow carries `age_group_id`
(SB-1608): NULL follows every age group of the team (what every follow meant
before squads existed), a value follows that squad only. A follow is for
alerts; it never grants channel access.

The list_subscriptions_for_team_ids method is the fan-out hot path —
called once per match event to find every push subscription that should
receive a notification.
"""

from __future__ import annotations

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

TABLE = "user_team_follows"


def follows_match(follow_age_group_id: int | None, match_age_group_id: int | None) -> bool:
    """Whether a follow row should hear about a match of its team.

    A whole-team follow (NULL) hears every match. A squad follow hears only
    matches in its age group, so a match with no age group reaches whole-team
    followers only: MT cannot say which squad played it.
    """
    if follow_age_group_id is None:
        return True
    return match_age_group_id is not None and follow_age_group_id == match_age_group_id


class TeamFollowDAO(BaseDAO):
    """Data access for user→team follow relationships."""

    def follow(self, user_id: str, team_id: int) -> bool:
        """Follow every age group of a team. Idempotent — re-following returns True silently."""
        try:
            # Check for existing first to keep idempotency clean.
            existing = (
                self.client.table(TABLE)
                .select("user_id")
                .eq("user_id", user_id)
                .eq("team_id", team_id)
                .is_("age_group_id", "null")
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

    def unfollow(self, user_id: str, team_id: int, age_group_id: int | None = None) -> bool:
        """Unfollow a team: every row for it, or with `age_group_id` just that squad.

        Idempotent — returns True even if not following.
        """
        try:
            query = self.client.table(TABLE).delete().eq("user_id", user_id).eq("team_id", team_id)
            if age_group_id is not None:
                query = query.eq("age_group_id", age_group_id)
            query.execute()
            return True
        except Exception:
            logger.exception(
                "team_unfollow_failed", user_id=user_id, team_id=team_id, age_group_id=age_group_id
            )
            return False

    def set_club_squads(
        self, user_id: str, club_team_ids: set[int], squads: set[tuple[int, int]]
    ) -> bool:
        """Make the user's follows of these teams exactly `squads` (team_id, age_group_id).

        Follows of teams outside `club_team_ids` are left alone. A whole-team
        follow of a club team is replaced by the squads chosen for it. New
        squads are added before old rows go, so a failure part-way leaves extra
        alerts, never missing ones.
        """
        if not club_team_ids:
            return True
        try:
            rows = (
                self.client.table(TABLE)
                .select("team_id, age_group_id")
                .eq("user_id", user_id)
                .in_("team_id", sorted(club_team_ids))
                .execute()
            ).data or []
            existing = {(r["team_id"], r.get("age_group_id")) for r in rows}
            to_add = sorted(squads - existing)
            if to_add:
                self.client.table(TABLE).insert(
                    [{"user_id": user_id, "team_id": t, "age_group_id": a} for t, a in to_add]
                ).execute()
            for team_id, age_group_id in sorted(existing - squads, key=lambda k: (k[0], k[1] or 0)):
                query = self.client.table(TABLE).delete().eq("user_id", user_id).eq("team_id", team_id)
                query = (
                    query.is_("age_group_id", "null")
                    if age_group_id is None
                    else query.eq("age_group_id", age_group_id)
                )
                query.execute()
            return True
        except Exception:
            logger.exception("team_follow_set_squads_failed", user_id=user_id)
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
                    "team_id, age_group_id, created_at, "
                    "age_group:age_groups(id, name), "
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

    def _follower_user_ids(self, team_ids: list[int], age_group_id: int | None) -> list[str]:
        """Distinct users following any of these teams at this match's age group.
        Raises on DB error.

        Shared by the Web Push, APNs and FCM fan-outs (SB-1236) so all resolve
        followers the same way; `follows_match` decides squad follows (SB-1608).
        """
        follow_resp = (
            self.client.table(TABLE)
            .select("user_id, age_group_id")
            .in_("team_id", team_ids)
            .execute()
        )
        return list(
            {
                row["user_id"]
                for row in (follow_resp.data or [])
                if row.get("user_id") and follows_match(row.get("age_group_id"), age_group_id)
            }
        )

    def list_user_ids_for_team_ids(
        self, team_ids: list[int], age_group_id: int | None
    ) -> list[str]:
        """Distinct users following any of these teams (APNs/FCM fan-out, SB-1236).

        Returns [] on error — same swallow-and-log contract as the
        subscriptions fan-out below.
        """
        if not team_ids:
            return []
        try:
            return self._follower_user_ids(team_ids, age_group_id)
        except Exception:
            logger.exception("team_follow_list_user_ids_failed", team_ids=team_ids)
            return []

    def list_subscriptions_for_team_ids(
        self, team_ids: list[int], age_group_id: int | None
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
            user_ids = self._follower_user_ids(team_ids, age_group_id)
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

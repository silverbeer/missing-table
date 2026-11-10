"""
Channel Members Data Access Object (SB-1607).

Grants to notification channels, and the facts the access rules need: a
channel's club, its age group's name, and the squads a player is on now.

Reads used to decide access fail closed: a failed lookup returns nothing, which
the rules read as "no access". Channel reads never select `destination`.
"""

import structlog

from dao.base_dao import BaseDAO
from mt_tools.my_team import Squad

logger = structlog.get_logger()

TABLE = "channel_members"
# Everything a member-facing read needs, and never `destination`.
CHANNEL_COLUMNS = "id, scope_type, club_id, team_id, age_group_id, audience, platform, invite_url, enabled"


class MemberWriteError(Exception):
    """A grant could not be saved. Safe to log."""


def _age_sort_key(name: str) -> tuple[int, str]:
    """U9 before U13: by the number in the name, then the name."""
    digits = "".join(ch for ch in name if ch.isdigit())
    return (int(digits) if digits else 999, name)


class ChannelMembersDAO(BaseDAO):
    """Data access for channel grants."""

    def _rows(self, description: str, build) -> list[dict]:
        try:
            return build().execute().data or []
        except Exception as exc:
            logger.error("dao_channel_members_read_failed", query=description, error_type=type(exc).__name__)
            return []

    # --- channels ---------------------------------------------------------------

    def team_club_id(self, team_id: int | None) -> int | None:
        if team_id is None:
            return None
        rows = self._rows("team_club", lambda: self.client.table("teams").select("club_id").eq("id", team_id).limit(1))
        return rows[0].get("club_id") if rows else None

    def channel(self, channel_id: int) -> dict | None:
        rows = self._rows(
            "channel",
            lambda: self.client.table("notification_channels").select(CHANNEL_COLUMNS).eq("id", channel_id).limit(1),
        )
        return rows[0] if rows else None

    def channels_for_team(self, team_id: int, club_id: int | None) -> list[dict]:
        """The team's squad channels and its club's channels, in id order."""
        rows = self._rows(
            "team_channels",
            lambda: self.client.table("notification_channels")
            .select(CHANNEL_COLUMNS)
            .eq("scope_type", "team")
            .eq("team_id", team_id)
            .order("id"),
        )
        if club_id is not None:
            rows += self._rows(
                "club_channels",
                lambda: self.client.table("notification_channels")
                .select(CHANNEL_COLUMNS)
                .eq("scope_type", "club")
                .eq("club_id", club_id)
                .order("id"),
            )
        return rows

    def age_group_names(self, age_group_ids: set[int]) -> dict[int, str]:
        if not age_group_ids:
            return {}
        rows = self._rows(
            "age_groups",
            lambda: self.client.table("age_groups").select("id, name").in_("id", sorted(age_group_ids)),
        )
        return {r["id"]: r["name"] for r in rows}

    # --- players ----------------------------------------------------------------

    def current_squads(self, user_id: str) -> list[Squad]:
        """The squads this user plays for now, from their current squad history."""
        rows = self._rows(
            "current_squads",
            lambda: self.client.table("player_team_history")
            .select("team_id, age_group_id, teams(club_id), age_groups(name)")
            .eq("player_id", user_id)
            .eq("is_current", True),
        )
        return [
            Squad(
                team_id=r["team_id"],
                age_group_id=r.get("age_group_id"),
                club_id=(r.get("teams") or {}).get("club_id"),
                age_group_name=(r.get("age_groups") or {}).get("name"),
            )
            for r in rows
        ]

    # --- grants -----------------------------------------------------------------

    def statuses(self, user_id: str, channel_ids: list[int]) -> dict[int, str]:
        if not channel_ids:
            return {}
        rows = self._rows(
            "statuses",
            lambda: self.client.table(TABLE)
            .select("channel_id, status")
            .eq("user_id", user_id)
            .in_("channel_id", channel_ids),
        )
        return {r["channel_id"]: r["status"] for r in rows}

    def get(self, channel_id: int, user_id: str) -> dict | None:
        rows = self._rows(
            "get",
            lambda: self.client.table(TABLE).select("*").eq("channel_id", channel_id).eq("user_id", user_id).limit(1),
        )
        return rows[0] if rows else None

    def save(self, channel_id: int, user_id: str, fields: dict) -> dict:
        """Create or update the grant for (channel, user). Raises MemberWriteError."""
        try:
            row = {"channel_id": channel_id, "user_id": user_id, **fields}
            return self.client.table(TABLE).upsert(row, on_conflict="channel_id,user_id").execute().data[0]
        except Exception as exc:
            logger.error("dao_channel_members_write_failed", error_type=type(exc).__name__)
            raise MemberWriteError("Could not save channel access") from None

    def delete(self, channel_id: int, user_id: str) -> None:
        try:
            self.client.table(TABLE).delete().eq("channel_id", channel_id).eq("user_id", user_id).execute()
        except Exception as exc:
            logger.error("dao_channel_members_write_failed", error_type=type(exc).__name__)
            raise MemberWriteError("Could not withdraw request") from None

    def requested(self, channel_ids: list[int]) -> list[dict]:
        """Pending requests on these channels, oldest first, with who asked."""
        if not channel_ids:
            return []
        return self._rows(
            "requested",
            lambda: self.client.table(TABLE)
            .select(
                "channel_id, user_id, created_at, user_profiles!channel_members_user_id_fkey(display_name, username)"
            )
            .in_("channel_id", channel_ids)
            .eq("status", "requested")
            .order("created_at"),
        )

    def channels_for_teams(self, team_ids: set[int], club_ids: set[int]) -> list[dict]:
        """Squad channels of these teams and club channels of these clubs, in id order."""
        rows: list[dict] = []
        if team_ids:
            rows += self._rows(
                "my_team_channels",
                lambda: self.client.table("notification_channels")
                .select(CHANNEL_COLUMNS)
                .eq("scope_type", "team")
                .in_("team_id", sorted(team_ids))
                .order("id"),
            )
        if club_ids:
            rows += self._rows(
                "my_club_channels",
                lambda: self.client.table("notification_channels")
                .select(CHANNEL_COLUMNS)
                .eq("scope_type", "club")
                .in_("club_id", sorted(club_ids))
                .order("id"),
            )
        return rows

    def team_age_groups(self, team_id: int) -> list[dict] | None:
        """The age groups a team is registered in (team_mappings), youngest first.

        Each is a squad that can have its own channels. None when the lookup
        failed, so "could not check" never reads as "registered in none".
        """
        try:
            rows = (
                self.client.table("team_mappings")
                .select("age_group_id, age_groups(name)")
                .eq("team_id", team_id)
                .execute()
                .data
                or []
            )
        except Exception as exc:
            logger.error("dao_channel_members_read_failed", query="team_age_groups", error_type=type(exc).__name__)
            return None
        names = {r["age_group_id"]: (r.get("age_groups") or {}).get("name") or "" for r in rows}
        return [{"id": i, "name": n} for i, n in sorted(names.items(), key=lambda kv: _age_sort_key(kv[1]))]

    def team_clubs(self, team_ids: set[int]) -> dict[int, int | None]:
        if not team_ids:
            return {}
        rows = self._rows(
            "team_clubs", lambda: self.client.table("teams").select("id, club_id").in_("id", sorted(team_ids))
        )
        return {r["id"]: r.get("club_id") for r in rows}

    def is_managed(self, team_ids: set[int], club_ids: set[int]) -> bool | None:
        """Whether anyone on MT manages these teams or clubs: the claimed/unclaimed split.

        None when the lookup failed, so "could not check" never reads as "unclaimed".
        """
        try:
            if team_ids:
                rows = (
                    self.client.table("user_profiles")
                    .select("id")
                    .in_("role", ["team-manager", "team_manager"])
                    .in_("team_id", sorted(team_ids))
                    .limit(1)
                    .execute()
                    .data
                )
                if rows:
                    return True
            if club_ids:
                rows = (
                    self.client.table("user_profiles")
                    .select("id")
                    .eq("role", "club_manager")
                    .in_("club_id", sorted(club_ids))
                    .limit(1)
                    .execute()
                    .data
                )
                if rows:
                    return True
        except Exception as exc:
            logger.error("dao_channel_members_read_failed", query="is_managed", error_type=type(exc).__name__)
            return None
        return False

    def profile(self, user_id: str) -> dict | None:
        """The fields channel access depends on, for someone other than the caller."""
        rows = self._rows(
            "profile",
            lambda: self.client.table("user_profiles").select("id, role, club_id, team_id").eq("id", user_id).limit(1),
        )
        return rows[0] if rows else None

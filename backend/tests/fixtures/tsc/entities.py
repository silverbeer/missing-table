"""
Entity Registry for TSC Journey Tests.

Tracks all created entities for cleanup in FK-safe order.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EntityRegistry:
    """
    Registry to track created entities during test journey.

    Entities are tracked in the order they should be deleted (FK-safe).
    Cleanup should delete in order: matches -> teams -> club -> invites -> division -> age_group -> season
    """

    # Reference data IDs
    season_id: int | None = None
    age_group_id: int | None = None
    division_id: int | None = None
    league_id: int | None = None  # If leagues are used

    # Club and teams
    club_id: int | None = None
    premier_team_id: int | None = None
    reserve_team_id: int | None = None

    # Additional teams created by club/team managers
    extra_team_ids: list[int] = field(default_factory=list)

    # Match IDs (created by various roles)
    match_ids: list[int] = field(default_factory=list)

    # Invite IDs and codes for tracking/cleanup
    invites: list[dict[str, Any]] = field(default_factory=list)
    # Format: {"id": str, "code": str, "type": str, "status": str}

    # User IDs created via invites (for reference, not auto-deleted)
    user_ids: list[str] = field(default_factory=list)

    def add_match(self, match_id: int) -> None:
        """Track a created match."""
        if match_id not in self.match_ids:
            self.match_ids.append(match_id)

    def add_team(self, team_id: int) -> None:
        """Track an extra team (not premier/reserve)."""
        if team_id not in self.extra_team_ids:
            self.extra_team_ids.append(team_id)

    def add_invite(self, invite_id: str, invite_code: str, invite_type: str, status: str = "pending") -> None:
        """Track a created invite."""
        self.invites.append({
            "id": invite_id,
            "code": invite_code,
            "type": invite_type,
            "status": status,
        })

    def add_user(self, user_id: str) -> None:
        """Track a user created via invite."""
        if user_id not in self.user_ids:
            self.user_ids.append(user_id)

    def get_all_team_ids(self) -> list[int]:
        """Get all team IDs in deletion order."""
        teams = []
        teams.extend(self.extra_team_ids)
        if self.reserve_team_id:
            teams.append(self.reserve_team_id)
        if self.premier_team_id:
            teams.append(self.premier_team_id)
        return teams

    def get_pending_invite_ids(self) -> list[str]:
        """Get IDs of pending invites for cancellation."""
        return [inv["id"] for inv in self.invites if inv["status"] == "pending"]

    def to_dict(self) -> dict[str, Any]:
        """Export registry to dict for persistence."""
        return {
            "season_id": self.season_id,
            "age_group_id": self.age_group_id,
            "division_id": self.division_id,
            "league_id": self.league_id,
            "club_id": self.club_id,
            "premier_team_id": self.premier_team_id,
            "reserve_team_id": self.reserve_team_id,
            "extra_team_ids": self.extra_team_ids,
            "match_ids": self.match_ids,
            "invites": self.invites,
            "user_ids": self.user_ids,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityRegistry":
        """Create registry from dict."""
        registry = cls()
        registry.season_id = data.get("season_id")
        registry.age_group_id = data.get("age_group_id")
        registry.division_id = data.get("division_id")
        registry.league_id = data.get("league_id")
        registry.club_id = data.get("club_id")
        registry.premier_team_id = data.get("premier_team_id")
        registry.reserve_team_id = data.get("reserve_team_id")
        registry.extra_team_ids = data.get("extra_team_ids", [])
        registry.match_ids = data.get("match_ids", [])
        registry.invites = data.get("invites", [])
        registry.user_ids = data.get("user_ids", [])
        return registry

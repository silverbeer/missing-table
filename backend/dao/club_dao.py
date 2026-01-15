"""
Club Data Access Object.

Handles all database operations related to clubs including:
- Club CRUD operations
- Club-team associations
- Club queries and filters
"""

from collections import Counter

import structlog

from dao.base_dao import BaseDAO, dao_cache, invalidates_cache

logger = structlog.get_logger()

# Cache pattern for invalidation
CLUBS_CACHE_PATTERN = "mt:dao:clubs:*"


class ClubDAO(BaseDAO):
    """Data access object for club operations."""

    # === Club Query Methods ===

    @dao_cache("clubs:all:{include_team_counts}")
    def get_all_clubs(self, include_team_counts: bool = True) -> list[dict]:
        """Get all clubs with their associated teams count.

        Args:
            include_team_counts: If True, include team_count field for each club

        Returns:
            List of clubs from the clubs table.
        """
        response = self.client.table("clubs").select("*").order("name").execute()
        clubs = response.data

        if include_team_counts:
            # Enrich with team counts (single query instead of N+1)
            teams_response = (
                self.client.table("teams")
                .select("club_id")
                .not_.is_("club_id", "null")
                .execute()
            )
            team_counts = Counter(
                team["club_id"] for team in teams_response.data if team.get("club_id")
            )
            for club in clubs:
                club["team_count"] = team_counts.get(club["id"], 0)

        return clubs

    @dao_cache("clubs:for_team:{team_id}")
    def get_club_for_team(self, team_id: int) -> dict | None:
        """Get the club for a team.

        Args:
            team_id: The team ID

        Returns:
            Club dict if team belongs to a club, None otherwise
        """
        # Get the team to find its club_id
        team_response = (
            self.client.table("teams").select("club_id").eq("id", team_id).execute()
        )
        if not team_response.data or len(team_response.data) == 0:
            return None

        club_id = team_response.data[0].get("club_id")
        if not club_id:
            return None

        # Get the club details
        club_response = (
            self.client.table("clubs").select("*").eq("id", club_id).execute()
        )
        if club_response.data and len(club_response.data) > 0:
            return club_response.data[0]
        return None

    # === Club CRUD Methods ===

    @invalidates_cache(CLUBS_CACHE_PATTERN)
    def create_club(
        self,
        name: str,
        city: str,
        website: str | None = None,
        description: str | None = None,
        logo_url: str | None = None,
        primary_color: str | None = None,
        secondary_color: str | None = None,
    ) -> dict:
        """Create a new club.

        Args:
            name: Club name
            city: Club city/location
            website: Optional website URL
            description: Optional description
            logo_url: Optional URL to club logo in Supabase Storage
            primary_color: Optional primary brand color (hex code)
            secondary_color: Optional secondary brand color (hex code)

        Returns:
            Created club dict

        Raises:
            ValueError: If club creation fails
        """
        club_data = {"name": name, "city": city}
        if website:
            club_data["website"] = website
        if description:
            club_data["description"] = description
        if logo_url:
            club_data["logo_url"] = logo_url
        if primary_color:
            club_data["primary_color"] = primary_color
        if secondary_color:
            club_data["secondary_color"] = secondary_color

        result = self.client.table("clubs").insert(club_data).execute()

        if not result.data or len(result.data) == 0:
            raise ValueError("Failed to create club")

        return result.data[0]

    @invalidates_cache(CLUBS_CACHE_PATTERN)
    def update_club(
        self,
        club_id: int,
        name: str | None = None,
        city: str | None = None,
        website: str | None = None,
        description: str | None = None,
        logo_url: str | None = None,
        primary_color: str | None = None,
        secondary_color: str | None = None,
    ) -> dict | None:
        """Update an existing club.

        Args:
            club_id: ID of club to update
            name: Optional new name
            city: Optional new city/location
            website: Optional new website URL
            description: Optional new description
            logo_url: Optional URL to club logo in Supabase Storage
            primary_color: Optional primary brand color (hex code)
            secondary_color: Optional secondary brand color (hex code)

        Returns:
            Updated club dict or None if not found
        """
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if city is not None:
            update_data["city"] = city
        if website is not None:
            update_data["website"] = website
        if description is not None:
            update_data["description"] = description
        if logo_url is not None:
            update_data["logo_url"] = logo_url
        if primary_color is not None:
            update_data["primary_color"] = primary_color
        if secondary_color is not None:
            update_data["secondary_color"] = secondary_color

        if not update_data:
            return None

        result = (
            self.client.table("clubs").update(update_data).eq("id", club_id).execute()
        )

        if not result.data or len(result.data) == 0:
            return None

        return result.data[0]

    @invalidates_cache(CLUBS_CACHE_PATTERN)
    def delete_club(self, club_id: int) -> bool:
        """Delete a club.

        Args:
            club_id: The club ID to delete

        Returns:
            True if deleted successfully

        Raises:
            Exception: If deletion fails

        Note:
            This will fail if there are teams still associated with this club
            due to ON DELETE RESTRICT constraint.
            Invitations referencing this club are deleted first.
        """
        # Delete invitations referencing this club first (FK constraint)
        self.client.table("invitations").delete().eq("club_id", club_id).execute()
        # Now delete the club
        self.client.table("clubs").delete().eq("id", club_id).execute()
        return True

    # === Team-Club Association Methods ===

    def update_team_club(self, team_id: int, club_id: int | None) -> dict:
        """Update the club for a team.

        Args:
            team_id: The team ID to update
            club_id: The club ID to assign (or None to remove club association)

        Returns:
            Updated team dict

        Raises:
            ValueError: If team update fails
        """
        result = (
            self.client.table("teams")
            .update({"club_id": club_id})
            .eq("id", team_id)
            .execute()
        )
        if not result.data or len(result.data) == 0:
            raise ValueError(f"Failed to update club for team {team_id}")
        return result.data[0]

    def get_all_parent_club_entities(self) -> list[dict]:
        """Get all parent club entities (teams with no club_id).

        This includes clubs that don't have children yet.
        Used for dropdowns where users need to select a parent club.
        """
        try:
            # Get all teams that could be parent clubs (no club_id)
            response = self.client.table("teams").select("*").is_("club_id", "null").execute()
            return response.data
        except Exception:
            logger.exception("Error querying parent club entities")
            return []

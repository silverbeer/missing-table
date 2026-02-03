"""
Player Data Access Object.

Handles all database operations related to players/user profiles including:
- User profile CRUD operations
- Team-player associations
- Player team history
- Admin player management
"""

import structlog

from dao.base_dao import BaseDAO, dao_cache, invalidates_cache

logger = structlog.get_logger()

# Cache patterns for invalidation
PLAYERS_CACHE_PATTERN = "mt:dao:players:*"


class PlayerDAO(BaseDAO):
    """Data access object for player/user profile operations."""

    # === User Profile Query Methods ===

    @dao_cache("players:profile:{user_id}")
    def get_user_profile_with_relationships(self, user_id: str) -> dict | None:
        """
        Get user profile with team relationship.

        Args:
            user_id: User ID to fetch profile for

        Returns:
            User profile dict with team data, or None if not found
        """
        try:
            response = (
                self.client.table("user_profiles")
                .select("""
                *,
                team:teams(id, name, city)
            """)
                .eq("id", user_id)
                .execute()
            )

            if response.data and len(response.data) > 0:
                profile = response.data[0]
                if len(response.data) > 1:
                    logger.warning(f"Multiple profiles found for user {user_id}, using first one")
                return profile
            return None
        except Exception as e:
            logger.error(f"Error fetching user profile: {e}")
            return None

    def get_user_profile_by_email(self, email: str, exclude_user_id: str | None = None) -> dict | None:
        """
        Get user profile by email, optionally excluding a specific user ID.

        Useful for checking if an email is already in use by another user.
        No caching - used for auth/validation.

        Args:
            email: Email address to search for
            exclude_user_id: Optional user ID to exclude from search

        Returns:
            User profile dict if found, None otherwise
        """
        try:
            query = self.client.table("user_profiles").select("id").eq("email", email)
            if exclude_user_id:
                query = query.neq("id", exclude_user_id)
            response = query.execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error checking user profile by email: {e}")
            return None

    def get_user_profile_by_username(self, username: str, exclude_user_id: str | None = None) -> dict | None:
        """
        Get user profile by username, optionally excluding a specific user ID.

        Useful for checking if a username is already taken.
        No caching - used for auth/validation.

        Args:
            username: Username to search for (will be lowercased)
            exclude_user_id: Optional user ID to exclude from search

        Returns:
            User profile dict if found, None otherwise
        """
        try:
            query = self.client.table("user_profiles").select("id").eq("username", username.lower())
            if exclude_user_id:
                query = query.neq("id", exclude_user_id)
            response = query.execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error checking user profile by username: {e}")
            return None

    @dao_cache("players:all")
    def get_all_user_profiles(self) -> list[dict]:
        """
        Get all user profiles with team relationships.

        Returns:
            List of user profile dicts
        """
        try:
            response = (
                self.client.table("user_profiles")
                .select("""
                *,
                team:teams(id, name, city)
            """)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all user profiles: {e}")
            return []

    # === User Profile CRUD Methods ===

    @invalidates_cache(PLAYERS_CACHE_PATTERN)
    def create_or_update_user_profile(self, profile_data: dict) -> dict | None:
        """
        Create or update a user profile.

        Args:
            profile_data: Dictionary containing user profile data

        Returns:
            Created/updated profile dict, or None on error
        """
        try:
            response = self.client.table("user_profiles").upsert(profile_data).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error creating/updating user profile: {e}")
            return None

    @invalidates_cache(PLAYERS_CACHE_PATTERN)
    def update_user_profile(self, user_id: str, update_data: dict) -> dict | None:
        """
        Update user profile fields.

        Args:
            user_id: User ID to update
            update_data: Dictionary of fields to update

        Returns:
            Updated profile dict, or None on error
        """
        try:
            response = self.client.table("user_profiles").update(update_data).eq("id", user_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            return None

    # === Team Players Methods ===

    @dao_cache("players:by_team:{team_id}")
    def get_team_players(self, team_id: int) -> list[dict]:
        """
        Get all players currently on a team for the team roster page.

        Uses player_team_history to support multi-team players.

        Returns player profiles with fields needed for player cards:
        - id, display_name, player_number, positions
        - photo_1_url, photo_2_url, photo_3_url, profile_photo_slot
        - overlay_style, primary_color, text_color, accent_color
        - instagram_handle, snapchat_handle, tiktok_handle

        Args:
            team_id: The team ID to get players for

        Returns:
            List of player profile dicts
        """
        try:
            # Query player_team_history for current team members
            response = (
                self.client.table("player_team_history")
                .select("""
                player_id,
                jersey_number,
                positions,
                user_profiles!player_team_history_player_id_fkey(
                    id,
                    display_name,
                    player_number,
                    positions,
                    photo_1_url,
                    photo_2_url,
                    photo_3_url,
                    profile_photo_slot,
                    overlay_style,
                    primary_color,
                    text_color,
                    accent_color,
                    instagram_handle,
                    snapchat_handle,
                    tiktok_handle
                )
            """)
                .eq("team_id", team_id)
                .eq("is_current", True)
                .execute()
            )

            # Flatten the results - extract user_profiles and merge with history data
            players = []
            for entry in response.data or []:
                profile = entry.get("user_profiles")
                if profile:
                    # Use jersey_number from history if available, fallback to profile
                    player = {**profile}
                    if entry.get("jersey_number") is not None:
                        player["player_number"] = entry["jersey_number"]
                    # Use positions from history if available, fallback to profile
                    if entry.get("positions"):
                        player["positions"] = entry["positions"]
                    players.append(player)

            # Sort by player_number
            players.sort(key=lambda p: p.get("player_number") or 999)
            return players
        except Exception as e:
            logger.error(f"Error fetching team players for team {team_id}: {e}")
            return []

    # === Player Team History Methods ===

    @dao_cache("players:history:{player_id}")
    def get_player_team_history(self, player_id: str) -> list[dict]:
        """
        Get complete team history for a player across all seasons.

        Returns history entries ordered by season (most recent first),
        with full team, season, age_group, league, and division details.

        Args:
            player_id: User ID of the player

        Returns:
            List of history entry dicts with related data
        """
        try:
            response = (
                self.client.table("player_team_history")
                .select("""
                *,
                team:teams(id, name, city,
                    club:clubs(id, name, primary_color, secondary_color)
                ),
                season:seasons(id, name, start_date, end_date),
                age_group:age_groups(id, name),
                league:leagues(id, name),
                division:divisions(id, name)
            """)
                .eq("player_id", player_id)
                .order("season_id", desc=True)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching player team history: {e}")
            return []

    def get_current_player_team_assignment(self, player_id: str) -> dict | None:
        """
        Get the current team assignment for a player (is_current=true).

        No caching - this is used for real-time checks.

        Args:
            player_id: User ID of the player

        Returns:
            Current history entry dict with related data, or None if not found
        """
        try:
            response = (
                self.client.table("player_team_history")
                .select("""
                *,
                team:teams(id, name, city,
                    club:clubs(id, name, primary_color, secondary_color)
                ),
                season:seasons(id, name, start_date, end_date),
                age_group:age_groups(id, name),
                league:leagues(id, name),
                division:divisions(id, name)
            """)
                .eq("player_id", player_id)
                .eq("is_current", True)
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching current player team assignment: {e}")
            return None

    def get_all_current_player_teams(self, player_id: str) -> list[dict]:
        """
        Get ALL current team assignments for a player (is_current=true).

        This supports players being on multiple teams simultaneously
        (e.g., for futsal/soccer leagues).
        No caching - this is used for real-time checks.

        Args:
            player_id: User ID of the player

        Returns:
            List of current history entries with related team and club data
        """
        try:
            response = (
                self.client.table("player_team_history")
                .select("""
                *,
                team:teams(id, name, city,
                    club:clubs(id, name, logo_url, primary_color, secondary_color),
                    age_group:age_groups(id, name),
                    league:leagues(id, name),
                    division:divisions(id, name)
                ),
                season:seasons(id, name, start_date, end_date),
                age_group:age_groups(id, name)
            """)
                .eq("player_id", player_id)
                .eq("is_current", True)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all current player teams: {e}")
            return []

    @invalidates_cache(PLAYERS_CACHE_PATTERN)
    def create_player_history_entry(
        self,
        player_id: str,
        team_id: int,
        season_id: int,
        jersey_number: int | None = None,
        positions: list[str] | None = None,
        notes: str | None = None,
        is_current: bool = False,
    ) -> dict | None:
        """
        Create or update a player team history entry.

        Uses UPSERT to handle the unique constraint on (player_id, team_id, season_id).
        If an entry already exists for the same player/team/season, it updates that
        entry instead of failing. This supports:
        - Re-adding a player to a team they were previously on
        - Updating is_current flag on existing entries
        - Players on multiple teams simultaneously (futsal use case)

        Args:
            player_id: User ID of the player
            team_id: Team ID
            season_id: Season ID
            jersey_number: Optional jersey number for that season
            positions: Optional list of positions played
            notes: Optional notes about the assignment
            is_current: Whether this is the current assignment

        Returns:
            Created/updated history entry dict, or None on error
        """
        try:
            # Get team details for age_group_id, league_id, division_id
            team_response = (
                self.client.table("teams").select("age_group_id, league_id, division_id").eq("id", team_id).execute()
            )

            team_data = team_response.data[0] if team_response.data else {}

            upsert_data = {
                "player_id": player_id,
                "team_id": team_id,
                "season_id": season_id,
                "age_group_id": team_data.get("age_group_id"),
                "league_id": team_data.get("league_id"),
                "division_id": team_data.get("division_id"),
                "jersey_number": jersey_number,
                "positions": positions,
                "is_current": is_current,
                "notes": notes,
            }

            # Use upsert to handle existing entries - if (player_id, team_id, season_id)
            # already exists, update it instead of failing
            response = (
                self.client.table("player_team_history")
                .upsert(upsert_data, on_conflict="player_id,team_id,season_id")
                .execute()
            )
            if response.data and len(response.data) > 0:
                return self.get_player_history_entry_by_id(response.data[0]["id"])
            return None
        except Exception as e:
            logger.error(f"Error creating/updating player history entry: {e}")
            return None

    def get_player_history_entry_by_id(self, history_id: int) -> dict | None:
        """
        Get a single player history entry by ID with related data.

        Args:
            history_id: History entry ID

        Returns:
            History entry dict with related data, or None if not found
        """
        try:
            response = (
                self.client.table("player_team_history")
                .select("""
                *,
                team:teams(id, name, city,
                    club:clubs(id, name, primary_color, secondary_color)
                ),
                season:seasons(id, name, start_date, end_date),
                age_group:age_groups(id, name),
                league:leagues(id, name),
                division:divisions(id, name)
            """)
                .eq("id", history_id)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching player history entry: {e}")
            return None

    @invalidates_cache(PLAYERS_CACHE_PATTERN)
    def update_player_history_entry(
        self,
        history_id: int,
        jersey_number: int | None = None,
        positions: list[str] | None = None,
        notes: str | None = None,
        is_current: bool | None = None,
    ) -> dict | None:
        """
        Update a player team history entry.

        Args:
            history_id: History entry ID to update
            jersey_number: Optional new jersey number
            positions: Optional new positions list
            notes: Optional new notes
            is_current: Optional new is_current flag

        Returns:
            Updated history entry dict, or None on error
        """
        try:
            update_data = {"updated_at": "now()"}

            if jersey_number is not None:
                update_data["jersey_number"] = jersey_number
            if positions is not None:
                update_data["positions"] = positions
            if notes is not None:
                update_data["notes"] = notes
            if is_current is not None:
                update_data["is_current"] = is_current
                # Note: We allow multiple current teams (for futsal/multi-league players)
                # So we don't automatically unset is_current on other entries

            response = self.client.table("player_team_history").update(update_data).eq("id", history_id).execute()

            if response.data and len(response.data) > 0:
                return self.get_player_history_entry_by_id(history_id)
            return None
        except Exception as e:
            logger.error(f"Error updating player history entry: {e}")
            return None

    @invalidates_cache(PLAYERS_CACHE_PATTERN)
    def delete_player_history_entry(self, history_id: int) -> bool:
        """
        Delete a player team history entry.

        Args:
            history_id: History entry ID to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            self.client.table("player_team_history").delete().eq("id", history_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting player history entry: {e}")
            return False

    # === Admin Player Management Methods ===

    def get_all_players_admin(
        self,
        search: str | None = None,
        club_id: int | None = None,
        team_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        Get all players with their current team assignments for admin management.
        No caching - admin queries should always be fresh.

        Args:
            search: Optional text search on display_name or email
            club_id: Optional filter by club ID
            team_id: Optional filter by team ID
            limit: Max number of results (default 50)
            offset: Offset for pagination (default 0)

        Returns:
            Dict with 'players' list and 'total' count
        """
        try:
            # Build the base query for players (team-player role)
            query = (
                self.client.table("user_profiles")
                .select(
                    """
                id,
                email,
                display_name,
                player_number,
                positions,
                photo_1_url,
                profile_photo_slot,
                team_id,
                created_at,
                team:teams(id, name, club_id)
                """,
                    count="exact",
                )
                .eq("role", "team-player")
            )

            # Apply text search filter
            if search:
                query = query.or_(f"display_name.ilike.%{search}%,email.ilike.%{search}%")

            # Apply team filter
            if team_id:
                query = query.eq("team_id", team_id)
            # Apply club filter (via team)
            elif club_id:
                # Need to get team IDs for this club first
                teams_response = self.client.table("teams").select("id").eq("club_id", club_id).execute()
                if teams_response.data:
                    team_ids = [t["id"] for t in teams_response.data]
                    query = query.in_("team_id", team_ids)

            # Apply pagination and ordering
            query = query.order("display_name").range(offset, offset + limit - 1)

            response = query.execute()

            players = response.data or []
            total = response.count or 0

            # Enrich with current team assignments from player_team_history
            for player in players:
                history_response = (
                    self.client.table("player_team_history")
                    .select(
                        """
                    id,
                    team_id,
                    season_id,
                    jersey_number,
                    is_current,
                    created_at,
                    team:teams(id, name, club:clubs(id, name)),
                    season:seasons(id, name)
                    """
                    )
                    .eq("player_id", player["id"])
                    .eq("is_current", True)
                    .execute()
                )
                player["current_teams"] = history_response.data or []

            return {"players": players, "total": total}

        except Exception as e:
            logger.error(f"Error fetching players for admin: {e}")
            return {"players": [], "total": 0}

    @invalidates_cache(PLAYERS_CACHE_PATTERN)
    def update_player_admin(
        self,
        player_id: str,
        display_name: str | None = None,
        player_number: int | None = None,
        positions: list[str] | None = None,
    ) -> dict | None:
        """
        Update player profile info (admin/manager operation).

        Args:
            player_id: User ID of the player
            display_name: Optional new display name
            player_number: Optional new jersey number
            positions: Optional new positions list

        Returns:
            Updated player profile dict, or None on error
        """
        try:
            update_data = {"updated_at": "now()"}

            if display_name is not None:
                update_data["display_name"] = display_name
            if player_number is not None:
                update_data["player_number"] = player_number
            if positions is not None:
                update_data["positions"] = positions

            response = self.client.table("user_profiles").update(update_data).eq("id", player_id).execute()

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"Error updating player admin: {e}")
            return None

    @invalidates_cache(PLAYERS_CACHE_PATTERN)
    def end_player_team_assignment(self, history_id: int) -> dict | None:
        """
        End a player's team assignment by setting is_current=false.

        Args:
            history_id: Player team history ID

        Returns:
            Updated history entry dict, or None on error
        """
        try:
            update_data = {"is_current": False, "updated_at": "now()"}

            response = self.client.table("player_team_history").update(update_data).eq("id", history_id).execute()

            if response.data and len(response.data) > 0:
                return self.get_player_history_entry_by_id(history_id)
            return None

        except Exception as e:
            logger.error(f"Error ending player team assignment: {e}")
            return None

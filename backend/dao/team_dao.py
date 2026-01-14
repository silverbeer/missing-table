"""
Team Data Access Object.

Handles all database operations related to teams including:
- Team CRUD operations
- Team-age group mappings
- Team-match type participations
- Team queries and filters
- Team-club associations
"""

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()


class TeamDAO(BaseDAO):
    """Data access object for team operations."""

    # === Team Query Methods ===

    def get_all_teams(self) -> list[dict]:
        """Get all teams with their age groups."""
        try:
            response = (
                self.client.table("teams")
                .select("""
                *,
                leagues!teams_league_id_fkey (
                    id,
                    name
                ),
                team_mappings (
                    age_groups (
                        id,
                        name
                    ),
                    divisions (
                        id,
                        name,
                        league_id,
                        leagues!divisions_league_id_fkey (
                            id,
                            name
                        )
                    )
                )
            """)
                .order("name")
                .execute()
            )

            # Flatten the age groups and divisions for each team
            teams = []
            for team in response.data:
                # Extract league_name from the joined leagues table
                if team.get("leagues"):
                    team["league_name"] = team["leagues"]["name"]

                age_groups = []
                divisions_by_age_group = {}
                if "team_mappings" in team:
                    for tag in team["team_mappings"]:
                        if tag.get("age_groups"):
                            age_group = tag["age_groups"]
                            age_groups.append(age_group)
                            if tag.get("divisions"):
                                division = tag["divisions"]
                                # Add league_name to division for easy access in frontend
                                if division.get("leagues"):
                                    division["league_name"] = division["leagues"]["name"]
                                divisions_by_age_group[age_group["id"]] = division
                team["age_groups"] = age_groups
                team["divisions_by_age_group"] = divisions_by_age_group
                teams.append(team)

            return teams
        except Exception:
            logger.exception("Error querying teams")
            return []

    def get_teams_by_match_type_and_age_group(
        self, match_type_id: int, age_group_id: int, division_id: int | None = None
    ) -> list[dict]:
        """Get teams that can participate in a specific match type and age group.

        Args:
            match_type_id: Filter by match type (e.g., League, Cup)
            age_group_id: Filter by age group (e.g., U14, U15)
            division_id: Optional - Filter by division (e.g., Bracket A for Futsal)
        """
        try:
            # Build the base query
            if division_id:
                # When filtering by division, use inner join on team_mappings
                # to only return teams in that specific division + age group
                query = (
                    self.client.table("teams")
                    .select("""
                    *,
                    team_mappings!inner (
                        age_group_id,
                        division_id,
                        age_groups (
                            id,
                            name
                        ),
                        divisions (
                            id,
                            name
                        )
                    ),
                    team_match_types!inner (
                        match_type_id,
                        age_group_id,
                        is_active
                    )
                """)
                    .eq("team_match_types.match_type_id", match_type_id)
                    .eq("team_match_types.age_group_id", age_group_id)
                    .eq("team_match_types.is_active", True)
                    .eq("team_mappings.age_group_id", age_group_id)
                    .eq("team_mappings.division_id", division_id)
                )
            else:
                # Without division filter, include all team_mappings
                query = (
                    self.client.table("teams")
                    .select("""
                    *,
                    team_mappings (
                        age_groups (
                            id,
                            name
                        ),
                        divisions (
                            id,
                            name
                        )
                    ),
                    team_match_types!inner (
                        match_type_id,
                        age_group_id,
                        is_active
                    )
                """)
                    .eq("team_match_types.match_type_id", match_type_id)
                    .eq("team_match_types.age_group_id", age_group_id)
                    .eq("team_match_types.is_active", True)
                )

            response = query.order("name").execute()

            # Flatten the age groups and divisions for each team
            teams = []
            for team in response.data:
                age_groups = []
                divisions_by_age_group = {}
                if "team_mappings" in team:
                    for tag in team["team_mappings"]:
                        if tag.get("age_groups"):
                            age_group = tag["age_groups"]
                            age_groups.append(age_group)
                            if tag.get("divisions"):
                                divisions_by_age_group[age_group["id"]] = tag["divisions"]
                team["age_groups"] = age_groups
                team["divisions_by_age_group"] = divisions_by_age_group
                teams.append(team)

            return teams
        except Exception:
            logger.exception("Error querying teams by match type and age group")
            return []

    def get_team_by_name(self, name: str) -> dict | None:
        """Get a team by name (case-insensitive exact match).

        Returns the first matching team with basic info (id, name, city).
        For match-scraper integration, this helps look up teams by name.
        """
        try:
            response = (
                self.client.table("teams")
                .select("id, name, city, academy_team")
                .ilike("name", name)  # Case-insensitive match
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception:
            logger.exception("Error getting team by name", team_name=name)
            return None

    def get_team_by_id(self, team_id: int) -> dict | None:
        """Get a team by ID.

        Returns team info (id, name, city, club_id).
        """
        try:
            response = (
                self.client.table("teams")
                .select("id, name, city, club_id")
                .eq("id", team_id)
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"Error getting team by id {team_id}: {e}")
            return None

    def get_team_with_details(self, team_id: int) -> dict | None:
        """Get a team with club, league, division, and age group details.

        Returns enriched team info for the team roster page header.
        """
        try:
            # Get team with club, division, and age_group (these have FK relationships)
            response = (
                self.client.table("teams")
                .select("""
                    id, name, city, academy_team, league_id,
                    club:clubs(id, name, logo_url, primary_color, secondary_color),
                    division:divisions(id, name),
                    age_group:age_groups(id, name)
                """)
                .eq("id", team_id)
                .limit(1)
                .execute()
            )

            if not response.data or len(response.data) == 0:
                return None

            team = response.data[0]
            result = {
                "id": team.get("id"),
                "name": team.get("name"),
                "city": team.get("city"),
                "academy_team": team.get("academy_team"),
                "club": team.get("club"),
                "league": None,
                "division": team.get("division"),
                "age_group": team.get("age_group"),
            }

            # Fetch league separately (no FK relationship)
            league_id = team.get("league_id")
            if league_id:
                league_response = (
                    self.client.table("match_types")
                    .select("id, name")
                    .eq("id", league_id)
                    .limit(1)
                    .execute()
                )
                if league_response.data and len(league_response.data) > 0:
                    result["league"] = league_response.data[0]

            return result

        except Exception as e:
            logger.error(f"Error getting team with details for id {team_id}: {e}")
            return None

    # === Team CRUD Methods ===

    def add_team(  # noqa: C901
        self,
        name: str,
        city: str,
        age_group_ids: list[int],
        match_type_ids: list[int] | None = None,
        division_id: int | None = None,
        club_id: int | None = None,
        academy_team: bool = False,
        client_ip: str | None = None,
    ) -> bool:
        """Add a new team with age groups, division, and optional club.

        Division represents location (e.g., Northeast Division for Homegrown,
        New England Conference for Academy). All age groups share the same division.
        For guest/tournament teams, division_id can be None.

        Args:
            name: Team name
            city: Team city
            age_group_ids: List of age group IDs (required, at least one)
            match_type_ids: List of match type IDs (optional, game types team participates in)
            division_id: Division ID (optional, only required for league teams)
            club_id: Optional club ID
            academy_team: Whether this is an academy team
            client_ip: Client IP address for security monitoring (optional)
        """
        logger.info(
            "Creating team",
            team_name=name,
            city=city,
            age_group_count=len(age_group_ids),
            match_type_count=len(match_type_ids) if match_type_ids else 0,
            division_id=division_id,
            club_id=club_id,
            academy_team=academy_team,
            client_ip=client_ip
        )

        try:
            # Validate required fields
            if not age_group_ids or len(age_group_ids) == 0:
                logger.warning("Team creation failed - no age groups provided", team_name=name)
                raise ValueError("Team must have at least one age group")

            # Get league_id from division (if division provided)
            league_id = None
            if division_id is not None:
                logger.debug(
                    "Looking up league for division",
                    division_id=division_id,
                    team_name=name
                )
                division_response = (
                    self.client.table("divisions")
                    .select("league_id")
                    .eq("id", division_id)
                    .execute()
                )
                if not division_response.data:
                    logger.error("Division not found", division_id=division_id, team_name=name)
                    raise ValueError(f"Division {division_id} not found")
                league_id = division_response.data[0]["league_id"]
                logger.debug(
                    "Found league for division",
                    league_id=league_id,
                    division_id=division_id
                )
            else:
                logger.debug(
                    "No division specified - creating guest/tournament team",
                    team_name=name
                )

            # Insert team with club, league, and division
            logger.debug("Inserting team record", team_name=name)
            team_data = {
                "name": name,
                "city": city,
                "academy_team": academy_team,
                "club_id": club_id,
                "league_id": league_id,
                "division_id": division_id
            }
            team_response = (
                self.client.table("teams")
                .insert(team_data)
                .execute()
            )

            if not team_response.data:
                logger.error("Team insert returned no data", team_name=name, team_data=team_data)
                return False

            team_id = team_response.data[0]["id"]
            logger.info("Team record created", team_id=team_id, team_name=name)

            # Add age group associations
            # For league teams: team_mappings with division_id
            # For guest/tournament teams: team_mappings with null division_id
            logger.debug(
                "Creating team_mappings",
                team_id=team_id,
                team_name=name,
                age_group_count=len(age_group_ids),
                division_id=division_id
            )
            for age_group_id in age_group_ids:
                data = {
                    "team_id": team_id,
                    "age_group_id": age_group_id,
                    "division_id": division_id  # null for guest teams, set for league teams
                }
                self.client.table("team_mappings").insert(data).execute()
            logger.info(
                "Team mappings created",
                team_id=team_id,
                team_name=name,
                mappings_created=len(age_group_ids)
            )

            # Add game type participations
            # Create team_match_types entries for each match_type + age_group combination
            if match_type_ids:
                total_entries = len(match_type_ids) * len(age_group_ids)
                logger.debug(
                    "Creating team_match_types",
                    team_id=team_id,
                    team_name=name,
                    match_type_count=len(match_type_ids),
                    age_group_count=len(age_group_ids),
                    total_entries=total_entries
                )
                for match_type_id in match_type_ids:
                    for age_group_id in age_group_ids:
                        match_type_data = {
                            "team_id": team_id,
                            "match_type_id": match_type_id,
                            "age_group_id": age_group_id,
                            "is_active": True
                        }
                        self.client.table("team_match_types").insert(match_type_data).execute()
                logger.info(
                    "Team match types created",
                    team_id=team_id,
                    team_name=name,
                    entries_created=total_entries
                )
            else:
                logger.warning(
                    "No match types provided for team - team will not appear in match scheduling",
                    team_id=team_id,
                    team_name=name
                )

            logger.info(
                "Team creation completed successfully",
                team_id=team_id,
                team_name=name,
                age_groups=len(age_group_ids),
                match_types=len(match_type_ids) if match_type_ids else 0
            )
            return True

        except Exception as e:
            error_str = str(e)
            logger.exception(
                "Error adding team",
                team_name=name,
                city=city,
                division_id=division_id,
                club_id=club_id,
                age_group_count=len(age_group_ids),
                match_type_count=len(match_type_ids) if match_type_ids else 0,
                error_type=type(e).__name__,
                error_message=error_str
            )

            # Re-raise validation errors (ValueError) so caller can handle them
            if isinstance(e, ValueError):
                raise

            # Re-raise duplicate key errors so API can handle them properly
            is_duplicate = (
                "teams_name_division_unique" in error_str
                or "teams_name_academy_unique" in error_str
                or "duplicate key value" in error_str.lower()
            )
            if is_duplicate:
                logger.warning(
                    "Duplicate team detected",
                    team_name=name,
                    division_id=division_id,
                    error=error_str
                )
                raise

            return False

    def update_team(
        self,
        team_id: int,
        name: str,
        city: str,
        academy_team: bool = False,
        club_id: int | None = None,
        _client_ip: str | None = None,
    ) -> dict | None:
        """Update a team."""
        try:
            update_data = {
                "name": name,
                "city": city,
                "academy_team": academy_team,
                "club_id": club_id
            }
            logger.debug("DAO update_team", team_id=team_id, update_data=update_data)

            result = (
                self.client.table("teams")
                .update(update_data)
                .eq("id", team_id)
                .execute()
            )

            logger.debug("DAO update result", data=result.data)
            return result.data[0] if result.data else None
        except Exception as e:
            logger.exception("Error updating team")
            raise e

    def delete_team(self, team_id: int) -> bool:
        """Delete a team and its related data.

        Cascades deletion of:
        - team_mappings (FK constraint)
        - team_match_types (FK constraint)
        - matches where team is home or away (FK constraint)
        """
        try:
            # Delete team_mappings first (FK constraint)
            self.client.table("team_mappings").delete().eq("team_id", team_id).execute()

            # Delete team_match_types (FK constraint)
            self.client.table("team_match_types").delete().eq("team_id", team_id).execute()

            # Delete matches where this team participates (FK constraint)
            self.client.table("matches").delete().eq("home_team_id", team_id).execute()
            self.client.table("matches").delete().eq("away_team_id", team_id).execute()

            # Now delete the team
            result = self.client.table("teams").delete().eq("id", team_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.exception("Error deleting team")
            raise e

    # === Team Mapping Methods ===

    def update_team_division(self, team_id: int, age_group_id: int, division_id: int) -> bool:
        """Update the division for a team in a specific age group."""
        try:
            response = (
                self.client.table("team_mappings")
                .update({"division_id": division_id})
                .eq("team_id", team_id)
                .eq("age_group_id", age_group_id)
                .execute()
            )

            return bool(response.data)

        except Exception:
            logger.exception("Error updating team division")
            return False

    def create_team_mapping(self, team_id: int, age_group_id: int, division_id: int) -> dict:
        """Create a team mapping, update team's league_id, and enable League match participation.

        When assigning a team to a division (which belongs to a league), this method:
        1. Updates the team's league_id to match the division's league
        2. Creates the team_mapping entry
        3. Auto-creates a team_match_types entry for League matches (match_type_id=1)
           This ensures teams can appear in League match dropdowns immediately.
        """
        try:
            # Get the league_id from the division
            division_response = (
                self.client.table("divisions")
                .select("league_id")
                .eq("id", division_id)
                .execute()
            )
            if division_response.data:
                league_id = division_response.data[0]["league_id"]
                # Update team's league_id and division_id to match the assignment
                # Note: division_id is needed for league table filtering to work correctly
                self.client.table("teams").update({
                    "league_id": league_id,
                    "division_id": division_id
                }).eq("id", team_id).execute()

            # Create the team mapping
            result = (
                self.client.table("team_mappings")
                .insert(
                    {"team_id": team_id, "age_group_id": age_group_id, "division_id": division_id}
                )
                .execute()
            )

            # Auto-create team_match_types entry for League matches (match_type_id=1)
            # This allows the team to appear in League match dropdowns
            LEAGUE_MATCH_TYPE_ID = 1
            existing = (
                self.client.table("team_match_types")
                .select("id")
                .eq("team_id", team_id)
                .eq("match_type_id", LEAGUE_MATCH_TYPE_ID)
                .eq("age_group_id", age_group_id)
                .execute()
            )
            if not existing.data:
                self.client.table("team_match_types").insert({
                    "team_id": team_id,
                    "match_type_id": LEAGUE_MATCH_TYPE_ID,
                    "age_group_id": age_group_id,
                    "is_active": True,
                }).execute()
                logger.info(
                    "Auto-created team_match_types entry for League",
                    team_id=team_id,
                    age_group_id=age_group_id
                )

            return result.data[0]
        except Exception as e:
            logger.exception("Error creating team mapping")
            raise e

    def delete_team_mapping(self, team_id: int, age_group_id: int, division_id: int) -> bool:
        """Delete a team mapping."""
        try:
            result = (
                self.client.table("team_mappings")
                .delete()
                .eq("team_id", team_id)
                .eq("age_group_id", age_group_id)
                .eq("division_id", division_id)
                .execute()
            )
            return len(result.data) > 0
        except Exception as e:
            logger.exception("Error deleting team mapping")
            raise e

    # === Team Match Type Participation Methods ===

    def add_team_match_type_participation(
        self, team_id: int, match_type_id: int, age_group_id: int
    ) -> bool:
        """Add a team's participation in a specific match type and age group."""
        try:
            self.client.table("team_match_types").insert(
                {
                    "team_id": team_id,
                    "match_type_id": match_type_id,
                    "age_group_id": age_group_id,
                    "is_active": True,
                }
            ).execute()
            return True
        except Exception:
            logger.exception("Error adding team match type participation")
            return False

    def remove_team_match_type_participation(
        self, team_id: int, match_type_id: int, age_group_id: int
    ) -> bool:
        """Remove a team's participation in a specific match type and age group."""
        try:
            self.client.table("team_match_types").update({"is_active": False}).eq(
                "team_id", team_id
            ).eq("match_type_id", match_type_id).eq("age_group_id", age_group_id).execute()
            return True
        except Exception:
            logger.exception("Error removing team match type participation")
            return False

    # === Club-Team Association Methods ===

    def get_teams_by_club_ids(self, club_ids: list[int]) -> list[dict]:
        """Get teams for multiple clubs without match/player counts.

        This is optimized for admin club listings that only need team details.
        """
        if not club_ids:
            return []

        try:
            response = (
                self.client.table("teams_with_league_badges")
                .select("id,name,club_id,league_id,league_name,mapping_league_names")
                .in_("club_id", club_ids)
                .order("name")
                .execute()
            )

            teams = []
            for team in response.data:
                teams.append({**team})

            return teams
        except Exception:
            logger.exception("Error querying teams by club ids")
            return []

    def get_club_teams_basic(self, club_id: int) -> list[dict]:
        """Get teams for a club without match/player counts."""
        try:
            response = (
                self.client.table("teams_with_league_badges")
                .select("id,name,club_id,league_id,league_name,mapping_league_names")
                .eq("club_id", club_id)
                .order("name")
                .execute()
            )
            return [*response.data]
        except Exception:
            logger.exception("Error querying basic club teams")
            return []

    def get_club_teams(self, club_id: int) -> list[dict]:  # noqa: C901
        """Get all teams for a club across all leagues.

        Args:
            club_id: The club ID from the clubs table

        Returns:
            List of teams belonging to this club with team_mappings included,
            plus match_count, player_count, age_group_name, and division_name
        """
        try:
            # Use the same query structure as get_all_teams but filter by club_id
            response = (
                self.client.table("teams")
                .select("""
                *,
                leagues!teams_league_id_fkey (
                    id,
                    name
                ),
                team_mappings (
                    age_groups (
                        id,
                        name
                    ),
                    divisions (
                        id,
                        name,
                        league_id,
                        leagues!divisions_league_id_fkey (
                            id,
                            name
                        )
                    )
                )
            """)
                .eq("club_id", club_id)
                .order("name")
                .execute()
            )

            # Get team IDs for batch counting
            team_ids = [team["id"] for team in response.data]

            # Get match counts for all teams in one query
            match_counts = {}
            if team_ids:
                # Count matches where team is home
                home_matches = (
                    self.client.table("matches")
                    .select("home_team_id")
                    .in_("home_team_id", team_ids)
                    .execute()
                )
                # Count matches where team is away
                away_matches = (
                    self.client.table("matches")
                    .select("away_team_id")
                    .in_("away_team_id", team_ids)
                    .execute()
                )
                # Aggregate counts
                for match in home_matches.data:
                    tid = match["home_team_id"]
                    match_counts[tid] = match_counts.get(tid, 0) + 1
                for match in away_matches.data:
                    tid = match["away_team_id"]
                    match_counts[tid] = match_counts.get(tid, 0) + 1

            # Get player counts for all teams in one query
            player_counts = {}
            if team_ids:
                players = (
                    self.client.table("user_profiles")
                    .select("team_id")
                    .in_("team_id", team_ids)
                    .execute()
                )
                for player in players.data:
                    tid = player["team_id"]
                    player_counts[tid] = player_counts.get(tid, 0) + 1

            # Process teams to add league_name and age_groups like get_all_teams does
            teams = []
            for team in response.data:
                team_data = {**team}
                # Extract league name
                if team.get("leagues"):
                    team_data["league_name"] = team["leagues"].get("name")
                else:
                    team_data["league_name"] = None

                # Extract age groups from team_mappings
                age_groups = []
                first_division_name = None
                if team.get("team_mappings"):
                    seen_age_groups = set()
                    for mapping in team["team_mappings"]:
                        if mapping.get("age_groups"):
                            ag_id = mapping["age_groups"]["id"]
                            if ag_id not in seen_age_groups:
                                age_groups.append(mapping["age_groups"])
                                seen_age_groups.add(ag_id)
                        # Get the first division name
                        if first_division_name is None and mapping.get("divisions"):
                            first_division_name = mapping["divisions"].get("name")
                team_data["age_groups"] = age_groups

                # Add first age_group_name and division_name for display
                team_data["age_group_name"] = age_groups[0]["name"] if age_groups else None
                team_data["division_name"] = first_division_name

                # Add match and player counts
                team_data["match_count"] = match_counts.get(team["id"], 0)
                team_data["player_count"] = player_counts.get(team["id"], 0)

                teams.append(team_data)

            return teams
        except Exception:
            logger.exception("Error querying club teams")
            return []

    def get_club_for_team(self, team_id: int) -> dict | None:
        """Get the club for a team.

        Args:
            team_id: The team ID

        Returns:
            Club dict if team belongs to a club, None otherwise
        """
        try:
            # Get the team to find its club_id
            team_response = self.client.table("teams").select("club_id").eq("id", team_id).execute()
            if not team_response.data or len(team_response.data) == 0:
                return None

            club_id = team_response.data[0].get('club_id')
            if not club_id:
                return None

            # Get the club details
            club_response = (
                self.client.table("clubs").select("*").eq("id", club_id).execute()
            )
            if club_response.data and len(club_response.data) > 0:
                return club_response.data[0]
            return None
        except Exception:
            logger.exception("Error querying club for team")
            return None

    def update_team_club(self, team_id: int, club_id: int | None) -> dict:
        """Update the club for a team.

        Args:
            team_id: The team ID to update
            club_id: The club ID to assign (or None to remove club association)

        Returns:
            Updated team dict
        """
        try:
            result = (
                self.client.table("teams")
                .update({"club_id": club_id})
                .eq("id", team_id)
                .execute()
            )
            if not result.data or len(result.data) == 0:
                raise ValueError(f"Failed to update club for team {team_id}")
            return result.data[0]
        except Exception as e:
            logger.exception("Error updating team club")
            raise e

    # === Team Statistics Methods ===

    def get_team_game_counts(self) -> dict[int, int]:
        """Get game counts for all teams in a single optimized query.

        Returns a dictionary mapping team_id → game_count.
        Uses SQL aggregation for performance - counts 100k+ games in milliseconds.
        """
        try:
            # Use PostgREST's aggregation to count games per team
            # This query is equivalent to:
            # SELECT home_team_id as team_id, COUNT(*) as count FROM matches GROUP BY home_team_id
            # UNION ALL
            # SELECT away_team_id as team_id, COUNT(*) as count FROM matches GROUP BY away_team_id

            response = self.client.rpc('get_team_game_counts').execute()

            # If RPC function doesn't exist, fall back to Python aggregation
            # This is slower but still better than client-side filtering
            if not response.data:
                # Get all matches with just team IDs
                matches = self.client.table("matches").select("home_team_id,away_team_id").execute()

                # Count games per team
                counts = {}
                for match in matches.data:
                    home_id = match['home_team_id']
                    away_id = match['away_team_id']
                    counts[home_id] = counts.get(home_id, 0) + 1
                    counts[away_id] = counts.get(away_id, 0) + 1

                return counts

            # Convert RPC result to dictionary
            return {row['team_id']: row['game_count'] for row in response.data}
        except Exception:
            logger.exception("Error getting team game counts")
            # Return empty dict on error - teams will show 0 games
            return {}

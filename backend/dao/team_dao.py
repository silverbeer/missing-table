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

from dao.base_dao import BaseDAO, dao_cache, invalidates_cache

logger = structlog.get_logger()

# Cache pattern for invalidation
TEAMS_CACHE_PATTERN = "mt:dao:teams:*"


class TeamDAO(BaseDAO):
    """Data access object for team operations."""

    # === Team Query Methods ===

    @dao_cache("teams:all")
    def get_all_teams(self) -> list[dict]:
        """Get all teams with their age groups."""
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

    @dao_cache("teams:by_match_type:{match_type_id}:{age_group_id}:{division_id}")
    def get_teams_by_match_type_and_age_group(
        self, match_type_id: int, age_group_id: int, division_id: int | None = None
    ) -> list[dict]:
        """Get teams that can participate in a specific match type and age group.

        Args:
            match_type_id: Filter by match type (e.g., League, Cup)
            age_group_id: Filter by age group (e.g., U14, U15)
            division_id: Optional - Filter by division (e.g., Bracket A for Futsal)

        Note: Due to PostgREST limitations with multiple inner joins, we query
        junction tables directly and intersect results when filtering by division.
        """
        # Get team IDs that have the required match type
        mt_response = (
            self.client.table("team_match_types")
            .select("team_id")
            .eq("match_type_id", match_type_id)
            .eq("age_group_id", age_group_id)
            .eq("is_active", True)
            .execute()
        )
        match_type_team_ids = {r["team_id"] for r in mt_response.data}

        if not match_type_team_ids:
            return []

        # If division filter is specified, intersect with division teams
        if division_id:
            div_response = (
                self.client.table("team_mappings")
                .select("team_id")
                .eq("age_group_id", age_group_id)
                .eq("division_id", division_id)
                .execute()
            )
            division_team_ids = {r["team_id"] for r in div_response.data}
            final_team_ids = match_type_team_ids & division_team_ids
        else:
            final_team_ids = match_type_team_ids

        if not final_team_ids:
            return []

        # Fetch full team data for the filtered IDs
        response = (
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
                )
            """)
            .in_("id", list(final_team_ids))
            .order("name")
            .execute()
        )

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

    @dao_cache("teams:by_name:{name}")
    def get_team_by_name(self, name: str) -> dict | None:
        """Get a team by name (case-insensitive exact match).

        Returns the first matching team with basic info (id, name, city).
        For match-scraper integration, this helps look up teams by name.
        """
        response = (
            self.client.table("teams").select("id, name, city, academy_team").ilike("name", name).limit(1).execute()
        )

        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    @dao_cache("teams:by_id:{team_id}")
    def get_team_by_id(self, team_id: int) -> dict | None:
        """Get a team by ID.

        Returns team info (id, name, city, club_id).
        """
        response = self.client.table("teams").select("id, name, city, club_id").eq("id", team_id).limit(1).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    @dao_cache("teams:with_details:{team_id}")
    def get_team_with_details(self, team_id: int) -> dict | None:
        """Get a team with club, league, division, and age group details.

        Returns enriched team info for the team roster page header.
        """
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
            league_response = self.client.table("match_types").select("id, name").eq("id", league_id).limit(1).execute()
            if league_response.data and len(league_response.data) > 0:
                result["league"] = league_response.data[0]

        return result

    @dao_cache("teams:club_basic:{club_id}")
    def get_club_teams_basic(self, club_id: int) -> list[dict]:
        """Get teams for a club without match/player counts."""
        response = (
            self.client.table("teams_with_league_badges")
            .select("id,name,club_id,league_id,league_name,mapping_league_names")
            .eq("club_id", club_id)
            .order("name")
            .execute()
        )
        return [*response.data]

    @dao_cache("teams:club:{club_id}")
    def get_club_teams(self, club_id: int) -> list[dict]:
        """Get all teams for a club across all leagues.

        Args:
            club_id: The club ID from the clubs table

        Returns:
            List of teams belonging to this club with team_mappings included,
            plus match_count, player_count, age_group_name, and division_name
        """
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
            home_matches = self.client.table("matches").select("home_team_id").in_("home_team_id", team_ids).execute()
            away_matches = self.client.table("matches").select("away_team_id").in_("away_team_id", team_ids).execute()
            for match in home_matches.data:
                tid = match["home_team_id"]
                match_counts[tid] = match_counts.get(tid, 0) + 1
            for match in away_matches.data:
                tid = match["away_team_id"]
                match_counts[tid] = match_counts.get(tid, 0) + 1

        # Get player counts for all teams in one query
        player_counts = {}
        if team_ids:
            players = self.client.table("user_profiles").select("team_id").in_("team_id", team_ids).execute()
            for player in players.data:
                tid = player["team_id"]
                player_counts[tid] = player_counts.get(tid, 0) + 1

        # Process teams to add league_name and age_groups
        teams = []
        for team in response.data:
            team_data = {**team}
            if team.get("leagues"):
                team_data["league_name"] = team["leagues"].get("name")
            else:
                team_data["league_name"] = None

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
                    if first_division_name is None and mapping.get("divisions"):
                        first_division_name = mapping["divisions"].get("name")
            team_data["age_groups"] = age_groups
            team_data["age_group_name"] = age_groups[0]["name"] if age_groups else None
            team_data["division_name"] = first_division_name
            team_data["match_count"] = match_counts.get(team["id"], 0)
            team_data["player_count"] = player_counts.get(team["id"], 0)

            teams.append(team_data)

        return teams

    # === Team CRUD Methods ===

    @invalidates_cache(TEAMS_CACHE_PATTERN)
    def add_team(
        self,
        name: str,
        city: str,
        age_group_ids: list[int],
        match_type_ids: list[int] | None = None,
        division_id: int | None = None,
        club_id: int | None = None,
        academy_team: bool = False,
    ) -> bool:
        """Add a new team with age groups, division, and optional club.

        Args:
            name: Team name
            city: Team city
            age_group_ids: List of age group IDs (required, at least one)
            match_type_ids: List of match type IDs (optional)
            division_id: Division ID (optional, only required for league teams)
            club_id: Optional club ID
            academy_team: Whether this is an academy team
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
        )

        # Validate required fields
        if not age_group_ids or len(age_group_ids) == 0:
            raise ValueError("Team must have at least one age group")

        # Get league_id from division (if division provided)
        league_id = None
        if division_id is not None:
            division_response = self.client.table("divisions").select("league_id").eq("id", division_id).execute()
            if not division_response.data:
                raise ValueError(f"Division {division_id} not found")
            league_id = division_response.data[0]["league_id"]

        # Insert team
        team_data = {
            "name": name,
            "city": city,
            "academy_team": academy_team,
            "club_id": club_id,
            "league_id": league_id,
            "division_id": division_id,
        }
        team_response = self.client.table("teams").insert(team_data).execute()

        if not team_response.data:
            return False

        team_id = team_response.data[0]["id"]
        logger.info("Team record created", team_id=team_id, team_name=name)

        # Add age group associations
        for age_group_id in age_group_ids:
            data = {
                "team_id": team_id,
                "age_group_id": age_group_id,
                "division_id": division_id,
            }
            self.client.table("team_mappings").insert(data).execute()

        # Add game type participations
        if match_type_ids:
            for match_type_id in match_type_ids:
                for age_group_id in age_group_ids:
                    match_type_data = {
                        "team_id": team_id,
                        "match_type_id": match_type_id,
                        "age_group_id": age_group_id,
                        "is_active": True,
                    }
                    self.client.table("team_match_types").insert(match_type_data).execute()

        logger.info(
            "Team creation completed",
            team_id=team_id,
            team_name=name,
            age_groups=len(age_group_ids),
            match_types=len(match_type_ids) if match_type_ids else 0,
        )
        return True

    @invalidates_cache(TEAMS_CACHE_PATTERN)
    def update_team(
        self,
        team_id: int,
        name: str,
        city: str,
        academy_team: bool = False,
        club_id: int | None = None,
    ) -> dict | None:
        """Update a team."""
        update_data = {
            "name": name,
            "city": city,
            "academy_team": academy_team,
            "club_id": club_id,
        }
        logger.debug("DAO update_team", team_id=team_id, update_data=update_data)

        result = self.client.table("teams").update(update_data).eq("id", team_id).execute()

        return result.data[0] if result.data else None

    @invalidates_cache(TEAMS_CACHE_PATTERN)
    def delete_team(self, team_id: int) -> bool:
        """Delete a team and its related data.

        Cascades deletion of:
        - team_mappings (FK constraint)
        - team_match_types (FK constraint)
        - matches where team is home or away (FK constraint)
        """
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

    # === Team Mapping Methods ===

    @invalidates_cache(TEAMS_CACHE_PATTERN)
    def update_team_division(self, team_id: int, age_group_id: int, division_id: int) -> bool:
        """Update the division for a team in a specific age group."""
        response = (
            self.client.table("team_mappings")
            .update({"division_id": division_id})
            .eq("team_id", team_id)
            .eq("age_group_id", age_group_id)
            .execute()
        )
        return bool(response.data)

    @invalidates_cache(TEAMS_CACHE_PATTERN)
    def create_team_mapping(self, team_id: int, age_group_id: int, division_id: int) -> dict:
        """Create a team mapping, update team's league_id, and enable League match participation.

        When assigning a team to a division (which belongs to a league), this method:
        1. Updates the team's league_id to match the division's league
        2. Creates the team_mapping entry
        3. Auto-creates a team_match_types entry for League matches (match_type_id=1)
        """
        # Get the league_id from the division
        division_response = self.client.table("divisions").select("league_id").eq("id", division_id).execute()
        if division_response.data:
            league_id = division_response.data[0]["league_id"]
            self.client.table("teams").update(
                {
                    "league_id": league_id,
                    "division_id": division_id,
                }
            ).eq("id", team_id).execute()

        # Create the team mapping
        result = (
            self.client.table("team_mappings")
            .insert(
                {
                    "team_id": team_id,
                    "age_group_id": age_group_id,
                    "division_id": division_id,
                }
            )
            .execute()
        )

        # Auto-create team_match_types entry for League matches
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
            self.client.table("team_match_types").insert(
                {
                    "team_id": team_id,
                    "match_type_id": LEAGUE_MATCH_TYPE_ID,
                    "age_group_id": age_group_id,
                    "is_active": True,
                }
            ).execute()
            logger.info(
                "Auto-created team_match_types entry for League",
                team_id=team_id,
                age_group_id=age_group_id,
            )

        return result.data[0]

    @invalidates_cache(TEAMS_CACHE_PATTERN)
    def delete_team_mapping(self, team_id: int, age_group_id: int, division_id: int) -> bool:
        """Delete a team mapping."""
        result = (
            self.client.table("team_mappings")
            .delete()
            .eq("team_id", team_id)
            .eq("age_group_id", age_group_id)
            .eq("division_id", division_id)
            .execute()
        )
        return len(result.data) > 0

    @invalidates_cache(TEAMS_CACHE_PATTERN)
    def update_team_club(self, team_id: int, club_id: int | None) -> dict:
        """Update the club for a team.

        Args:
            team_id: The team ID to update
            club_id: The club ID to assign (or None to remove club association)

        Returns:
            Updated team dict
        """
        result = self.client.table("teams").update({"club_id": club_id}).eq("id", team_id).execute()
        if not result.data or len(result.data) == 0:
            raise ValueError(f"Failed to update club for team {team_id}")
        return result.data[0]

    # === Team Match Type Participation Methods ===

    def add_team_match_type_participation(self, team_id: int, match_type_id: int, age_group_id: int) -> bool:
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

    def remove_team_match_type_participation(self, team_id: int, match_type_id: int, age_group_id: int) -> bool:
        """Remove a team's participation in a specific match type and age group."""
        try:
            self.client.table("team_match_types").update({"is_active": False}).eq("team_id", team_id).eq(
                "match_type_id", match_type_id
            ).eq("age_group_id", age_group_id).execute()
            return True
        except Exception:
            logger.exception("Error removing team match type participation")
            return False

    # === Other Query Methods (not cached) ===

    def get_teams_by_club_ids(self, club_ids: list[int]) -> list[dict]:
        """Get teams for multiple clubs without match/player counts.

        This is optimized for admin club listings that only need team details.
        """
        if not club_ids:
            return []

        response = (
            self.client.table("teams_with_league_badges")
            .select("id,name,club_id,league_id,league_name,mapping_league_names")
            .in_("club_id", club_ids)
            .order("name")
            .execute()
        )

        return [{**team} for team in response.data]

    def get_club_for_team(self, team_id: int) -> dict | None:
        """Get the club for a team.

        Args:
            team_id: The team ID

        Returns:
            Club dict if team belongs to a club, None otherwise
        """
        team_response = self.client.table("teams").select("club_id").eq("id", team_id).execute()
        if not team_response.data or len(team_response.data) == 0:
            return None

        club_id = team_response.data[0].get("club_id")
        if not club_id:
            return None

        club_response = self.client.table("clubs").select("*").eq("id", club_id).execute()
        if club_response.data and len(club_response.data) > 0:
            return club_response.data[0]
        return None

    def get_team_game_counts(self) -> dict[int, int]:
        """Get game counts for all teams in a single optimized query.

        Returns a dictionary mapping team_id -> game_count.
        """
        try:
            response = self.client.rpc("get_team_game_counts").execute()

            if not response.data:
                # Fallback to Python aggregation
                matches = self.client.table("matches").select("home_team_id,away_team_id").execute()
                counts = {}
                for match in matches.data:
                    home_id = match["home_team_id"]
                    away_id = match["away_team_id"]
                    counts[home_id] = counts.get(home_id, 0) + 1
                    counts[away_id] = counts.get(away_id, 0) + 1
                return counts

            return {row["team_id"]: row["game_count"] for row in response.data}
        except Exception:
            logger.exception("Error getting team game counts")
            return {}

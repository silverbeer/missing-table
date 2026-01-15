"""
Match data access layer for MissingTable.

Provides data access objects for matches, teams, leagues, divisions, seasons,
and related soccer/futbol data using Supabase.
"""

import os

import httpx
import structlog
from dotenv import load_dotenv

from dao.standings import (
    calculate_standings,
    filter_by_match_type,
    filter_completed_matches,
    filter_same_division_matches,
)
from supabase import create_client

logger = structlog.get_logger()

# Load environment variables with environment-specific support
def load_environment():
    """Load environment variables based on APP_ENV or default to local."""
    # First load base .env file
    load_dotenv()

    # Determine which environment to use
    app_env = os.getenv('APP_ENV', 'local')  # Default to local

    # Load environment-specific file
    env_file = f".env.{app_env}"
    if os.path.exists(env_file):
        load_dotenv(env_file, override=True)
    else:
        # Fallback to .env.local for backwards compatibility
        if os.path.exists(".env.local"):
            load_dotenv(".env.local", override=True)

load_environment()


class SupabaseConnection:
    """Manage the connection to Supabase with SSL workaround."""

    def __init__(self):
        """Initialize Supabase client with custom SSL configuration."""
        self.url = os.getenv("SUPABASE_URL")
        # Backend should always use SERVICE_KEY for administrative operations
        service_key = os.getenv("SUPABASE_SERVICE_KEY")
        anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.key = service_key or anon_key

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_SERVICE_KEY) must be set in .env file")

        # Debug output - check what keys are actually set
        key_type = 'SERVICE_KEY' if service_key and self.key == service_key else 'ANON_KEY'
        logger.debug("Connecting to Supabase", url=self.url, key_type=key_type,
                     service_key_present=bool(service_key), anon_key_present=bool(anon_key))

        try:
            # Try with custom httpx client
            transport = httpx.HTTPTransport(retries=3)
            timeout = httpx.Timeout(30.0, connect=10.0)

            # Create custom client with extended timeout and retries
            http_client = httpx.Client(transport=transport, timeout=timeout, follow_redirects=True)

            # Create Supabase client with custom HTTP client
            self.client = create_client(self.url, self.key, options={"httpx_client": http_client})
            logger.debug("Connection to Supabase established")

        except Exception:
            # Fallback to standard client
            self.client = create_client(self.url, self.key)
            logger.debug("Connection to Supabase established (fallback client)")

    def get_client(self):
        """Get the Supabase client instance."""
        return self.client


class MatchDAO:
    """Data Access Object for match and league data using normalized schema."""

    def __init__(self, connection_holder):
        """Initialize with a SupabaseConnection."""
        if not isinstance(connection_holder, SupabaseConnection):
            raise TypeError("connection_holder must be a SupabaseConnection instance")
        self.connection_holder = connection_holder
        self.client = connection_holder.get_client()

    # === Reference Data Methods ===

    def get_all_age_groups(self) -> list[dict]:
        """Get all age groups."""
        try:
            response = self.client.table("age_groups").select("*").order("name").execute()
            return response.data
        except Exception:
            logger.exception("Error querying age groups")
            return []

    def get_all_seasons(self) -> list[dict]:
        """Get all seasons."""
        try:
            response = (
                self.client.table("seasons").select("*").order("start_date", desc=True).execute()
            )
            return response.data
        except Exception:
            logger.exception("Error querying seasons")
            return []

    def get_current_season(self) -> dict | None:
        """Get the current active season based on today's date."""
        try:
            from datetime import date

            today = date.today().isoformat()

            response = (
                self.client.table("seasons")
                .select("*")
                .lte("start_date", today)
                .gte("end_date", today)
                .single()
                .execute()
            )

            return response.data
        except Exception as e:
            logger.info("No current season found", error=str(e))
            return None

    def get_active_seasons(self) -> list[dict]:
        """Get active seasons (current and future) for scheduling new matches."""
        try:
            from datetime import date

            today = date.today().isoformat()

            response = (
                self.client.table("seasons")
                .select("*")
                .gte("end_date", today)
                .order("start_date", desc=False)
                .execute()
            )

            return response.data
        except Exception:
            logger.exception("Error querying active seasons")
            return []

    def get_all_match_types(self) -> list[dict]:
        """Get all match types."""
        try:
            response = self.client.table("match_types").select("*").order("name").execute()
            return response.data
        except Exception:
            logger.exception("Error querying match types")
            return []

    def get_match_type_by_id(self, match_type_id: int) -> dict | None:
        """Get match type by ID."""
        try:
            response = self.client.table("match_types").select("*").eq("id", match_type_id).execute()
            return response.data[0] if response.data else None
        except Exception:
            logger.exception("Error querying match type")
            return None

    # === League Methods ===

    def get_all_leagues(self) -> list[dict]:
        """Get all leagues ordered by name."""
        try:
            response = self.client.table("leagues").select("*").order("name").execute()
            return response.data
        except Exception:
            logger.exception("Error querying leagues")
            return []

    def get_league_by_id(self, league_id: int) -> dict | None:
        """Get league by ID."""
        try:
            response = (
                self.client.table("leagues")
                .select("*")
                .eq("id", league_id)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception:
            logger.exception("Error querying league", league_id=league_id)
            return None

    def create_league(self, league_data: dict) -> dict:
        """Create new league."""
        try:
            response = self.client.table("leagues").insert(league_data).execute()
            return response.data[0]
        except Exception:
            logger.exception("Error creating league")
            raise

    def update_league(self, league_id: int, league_data: dict) -> dict:
        """Update league."""
        try:
            response = (
                self.client.table("leagues")
                .update(league_data)
                .eq("id", league_id)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception:
            logger.exception("Error updating league", league_id=league_id)
            raise

    def delete_league(self, league_id: int) -> bool:
        """Delete league (will fail if divisions exist due to FK constraint)."""
        try:
            self.client.table("leagues").delete().eq("id", league_id).execute()
            return True
        except Exception:
            logger.exception("Error deleting league", league_id=league_id)
            raise

    # === Division Methods ===

    def get_all_divisions(self) -> list[dict]:
        """Get all divisions with league info."""
        try:
            response = (
                self.client.table("divisions")
                .select("*, leagues!divisions_league_id_fkey(id, name, description, is_active)")
                .order("name")
                .execute()
            )
            return response.data
        except Exception:
            logger.exception("Error querying divisions")
            return []

    def get_divisions_by_league(self, league_id: int) -> list[dict]:
        """Get divisions filtered by league."""
        try:
            response = (
                self.client.table("divisions")
                .select("*, leagues!divisions_league_id_fkey(id, name, description)")
                .eq("league_id", league_id)
                .order("name")
                .execute()
            )
            return response.data
        except Exception:
            logger.exception("Error querying divisions for league", league_id=league_id)
            return []

    # === Team Methods ===

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

    def add_team(
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
                logger.debug("Looking up league for division", division_id=division_id, team_name=name)
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
                logger.debug("Found league for division", league_id=league_id, division_id=division_id)
            else:
                logger.debug("No division specified - creating guest/tournament team", team_name=name)

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

            # Re-raise duplicate key errors so API can handle them properly
            if "teams_name_division_unique" in error_str or "teams_name_academy_unique" in error_str or "duplicate key value" in error_str.lower():
                logger.warning(
                    "Duplicate team detected",
                    team_name=name,
                    division_id=division_id,
                    error=error_str
                )
                raise

            return False

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

    def get_age_group_by_name(self, name: str) -> dict | None:
        """Get an age group by name (case-insensitive exact match).

        Returns the age group record (id, name).
        For match-scraper integration, this helps look up age groups by name.
        """
        try:
            response = (
                self.client.table("age_groups")
                .select("id, name")
                .ilike("name", name)  # Case-insensitive match
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception:
            logger.exception("Error getting age group by name", age_group_name=name)
            return None

    def get_division_by_name(self, name: str) -> dict | None:
        """Get a division by name (case-insensitive exact match).

        Returns the division record (id, name).
        For match-scraper integration, this helps look up divisions by name.
        """
        try:
            response = (
                self.client.table("divisions")
                .select("id, name")
                .ilike("name", name)  # Case-insensitive match
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception:
            logger.exception("Error getting division by name", division_name=name)
            return None

    def get_match_by_external_id(self, external_match_id: str) -> dict | None:
        """Get a match by its external match_id (from match-scraper).

        This is used for deduplication - checking if a match from match-scraper
        already exists in the database.

        Returns:
            Match dict with flattened structure, or None if not found
        """
        try:
            response = (
                self.client.table("matches")
                .select("""
                    *,
                    home_team:teams!matches_home_team_id_fkey(id, name),
                    away_team:teams!matches_away_team_id_fkey(id, name),
                    season:seasons(id, name),
                    age_group:age_groups(id, name),
                    match_type:match_types(id, name),
                    division:divisions(id, name)
                """)
                .eq("match_id", external_match_id)
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                match = response.data[0]
                # Flatten to match format from get_match_by_id
                flat_match = {
                    "id": match["id"],
                    "match_date": match["match_date"],
                    "home_team_id": match["home_team_id"],
                    "away_team_id": match["away_team_id"],
                    "home_team_name": match["home_team"]["name"] if match.get("home_team") else "Unknown",
                    "away_team_name": match["away_team"]["name"] if match.get("away_team") else "Unknown",
                    "home_score": match["home_score"],
                    "away_score": match["away_score"],
                    "season_id": match["season_id"],
                    "season_name": match["season"]["name"] if match.get("season") else "Unknown",
                    "age_group_id": match["age_group_id"],
                    "age_group_name": match["age_group"]["name"] if match.get("age_group") else "Unknown",
                    "match_type_id": match["match_type_id"],
                    "match_type_name": match["match_type"]["name"] if match.get("match_type") else "Unknown",
                    "division_id": match.get("division_id"),
                    "division_name": match["division"]["name"] if match.get("division") else "Unknown",
                    "match_status": match.get("match_status"),
                    "created_by": match.get("created_by"),
                    "updated_by": match.get("updated_by"),
                    "source": match.get("source", "manual"),
                    "match_id": match.get("match_id"),
                    "created_at": match["created_at"],
                    "updated_at": match["updated_at"],
                }
                return flat_match
            return None

        except Exception:
            logger.exception("Error getting match by external ID", external_match_id=external_match_id)
            return None

    def get_match_by_teams_and_date(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        age_group_id: int | None = None
    ) -> dict | None:
        """Get a match by home/away teams, date, and optionally age group.

        This is used as a fallback for deduplication when match_id is not populated
        (e.g., manually-entered matches without external match IDs).

        Args:
            home_team_id: Database ID of home team
            away_team_id: Database ID of away team
            match_date: ISO format date string (YYYY-MM-DD)
            age_group_id: Optional database ID of age group (recommended to avoid false matches)

        Returns:
            Match dict with flattened structure, or None if not found
        """
        try:
            query = (
                self.client.table("matches")
                .select("""
                    *,
                    home_team:teams!matches_home_team_id_fkey(id, name),
                    away_team:teams!matches_away_team_id_fkey(id, name),
                    season:seasons(id, name),
                    age_group:age_groups(id, name),
                    match_type:match_types(id, name),
                    division:divisions(id, name)
                """)
                .eq("home_team_id", home_team_id)
                .eq("away_team_id", away_team_id)
                .eq("match_date", match_date)
            )

            # Add age_group filter if provided (prevents matching different age groups)
            if age_group_id is not None:
                query = query.eq("age_group_id", age_group_id)

            response = query.limit(1).execute()

            if response.data and len(response.data) > 0:
                match = response.data[0]
                # Flatten to match format from get_match_by_id
                flat_match = {
                    "id": match["id"],
                    "match_date": match["match_date"],
                    "home_team_id": match["home_team_id"],
                    "away_team_id": match["away_team_id"],
                    "home_team_name": match["home_team"]["name"] if match.get("home_team") else "Unknown",
                    "away_team_name": match["away_team"]["name"] if match.get("away_team") else "Unknown",
                    "home_score": match["home_score"],
                    "away_score": match["away_score"],
                    "season_id": match["season_id"],
                    "season_name": match["season"]["name"] if match.get("season") else "Unknown",
                    "age_group_id": match["age_group_id"],
                    "age_group_name": match["age_group"]["name"] if match.get("age_group") else "Unknown",
                    "match_type_id": match["match_type_id"],
                    "match_type_name": match["match_type"]["name"] if match.get("match_type") else "Unknown",
                    "division_id": match.get("division_id"),
                    "division_name": match["division"]["name"] if match.get("division") else "Unknown",
                    "match_status": match.get("match_status"),
                    "created_by": match.get("created_by"),
                    "updated_by": match.get("updated_by"),
                    "source": match.get("source", "manual"),
                    "match_id": match.get("match_id"),
                    "created_at": match["created_at"],
                    "updated_at": match["updated_at"],
                }
                return flat_match
            return None

        except Exception:
            logger.exception("Error getting match by teams and date")
            return None

    def update_match_external_id(self, match_id: int, external_match_id: str) -> bool:
        """Update only the external match_id field on an existing match.

        This is used when a manually-entered match is matched with a scraped match,
        allowing future scrapes to use the external_match_id for deduplication.

        Args:
            match_id: Database ID of the match to update
            external_match_id: External match ID from match-scraper (e.g., "98966")

        Returns:
            True if update successful, False otherwise
        """
        try:
            response = (
                self.client.table("matches")
                .update({
                    "match_id": external_match_id,
                    "source": "match-scraper",  # Update source to indicate scraper now manages this
                })
                .eq("id", match_id)
                .execute()
            )

            if response.data:
                logger.info("Updated match with external match_id", match_id=match_id, external_match_id=external_match_id)
                return True
            return False

        except Exception:
            logger.exception("Error updating match external_id")
            return False

    def create_match(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        season: str,
        home_score: int | None = None,
        away_score: int | None = None,
        match_status: str = "scheduled",
        location: str | None = None,
        source: str = "manual",
        match_id: str | None = None,
        age_group: str | None = None,
        division: str | None = None,
    ) -> int | None:
        """Create a new match with simplified parameters.

        This is a convenience method for match-scraper integration that accepts
        team IDs directly and minimal required fields.

        Args:
            home_team_id: Database ID of home team
            away_team_id: Database ID of away team
            match_date: ISO format date string
            season: Season name (e.g., "2025-26")
            home_score: Home team score (optional)
            away_score: Away team score (optional)
            match_status: Match status (scheduled, live, completed, etc.)
            location: Match location (optional)
            source: Data source (default: "manual", use "match-scraper" for external)
            match_id: External match ID for deduplication (optional)
            age_group: Age group name (e.g., "U14", "U13") - will be looked up in database
            division: Division name (e.g., "Northeast") - will be looked up in database

        Returns:
            Created match ID, or None on failure
        """
        try:
            # Get current season as fallback
            current_season = self.get_current_season()
            season_id = current_season['id'] if current_season else 1  # Fallback to ID 1

            # Look up age_group_id from age_group name
            age_group_id = 1  # Default fallback
            if age_group:
                age_group_record = self.get_age_group_by_name(age_group)
                if age_group_record:
                    age_group_id = age_group_record['id']
                    logger.debug(f"Mapped age_group '{age_group}' to ID {age_group_id}")
                else:
                    logger.warning(f"Age group '{age_group}' not found in database, using default ID {age_group_id}")

            # Look up division_id from division name
            division_id = None
            if division:
                division_record = self.get_division_by_name(division)
                if division_record:
                    division_id = division_record['id']
                    logger.debug(f"Mapped division '{division}' to ID {division_id}")
                else:
                    logger.error(f"Division '{division}' not found in database")
                    if source == "match-scraper":
                        raise ValueError(f"Division '{division}' is required for match-scraper but not found in database")
            elif source == "match-scraper":
                # Division is required for match-scraper sourced games
                logger.error("Division is required for match-scraper sourced matches but was not provided")
                raise ValueError("Division is required for match-scraper sourced matches")

            match_type_id = 1  # Default League

            data = {
                "match_date": match_date,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_score": home_score,
                "away_score": away_score,
                "season_id": season_id,
                "age_group_id": age_group_id,
                "match_type_id": match_type_id,
                "division_id": division_id,
                "match_status": match_status,
                "source": source,
            }

            if match_id:
                data["match_id"] = match_id

            response = self.client.table("matches").insert(data).execute()

            if response.data and len(response.data) > 0:
                return response.data[0]["id"]
            return None

        except Exception:
            logger.exception("Error creating match")
            return None

    # === Match Methods ===

    def get_all_matches(
        self,
        client_ip: str | None = None,
        season_id: int | None = None,
        age_group_id: int | None = None,
        division_id: int | None = None,
        team_id: int | None = None,
        match_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """Get all matches with optional filters.

        Args:
            client_ip: Client IP address for logging/security (unused in query)
            season_id: Filter by season ID
            age_group_id: Filter by age group ID
            division_id: Filter by division ID
            team_id: Filter by team ID (home or away)
            match_type: Filter by match type name
            start_date: Filter by start date (YYYY-MM-DD)
            end_date: Filter by end date (YYYY-MM-DD)
        """
        try:
            query = self.client.table("matches").select("""
                *,
                home_team:teams!matches_home_team_id_fkey(id, name),
                away_team:teams!matches_away_team_id_fkey(id, name),
                season:seasons(id, name),
                age_group:age_groups(id, name),
                match_type:match_types(id, name),
                division:divisions(id, name, league_id, leagues!divisions_league_id_fkey(id, name))
            """)

            # Apply filters
            if season_id:
                query = query.eq("season_id", season_id)
            if age_group_id:
                query = query.eq("age_group_id", age_group_id)
            if division_id:
                query = query.eq("division_id", division_id)

            # Date range filters
            if start_date:
                query = query.gte("match_date", start_date)
            if end_date:
                query = query.lte("match_date", end_date)

            # For team_id, we need to match either home_team_id OR away_team_id
            if team_id:
                query = query.or_(f"home_team_id.eq.{team_id},away_team_id.eq.{team_id}")

            response = query.order("match_date", desc=True).execute()

            # Filter by match_type name if specified (post-query filtering)
            filtered_matches = response.data
            if match_type:
                filtered_matches = [
                    match
                    for match in response.data
                    if match.get("match_type", {}).get("name") == match_type
                ]

            # Flatten the response for easier use
            matches = []
            for match in filtered_matches:
                flat_match = {
                    "id": match["id"],
                    "match_date": match["match_date"],
                    "home_team_id": match["home_team_id"],
                    "away_team_id": match["away_team_id"],
                    "home_team_name": match["home_team"]["name"]
                    if match.get("home_team")
                    else "Unknown",
                    "away_team_name": match["away_team"]["name"]
                    if match.get("away_team")
                    else "Unknown",
                    "home_score": match["home_score"],
                    "away_score": match["away_score"],
                    "season_id": match["season_id"],
                    "season_name": match["season"]["name"] if match.get("season") else "Unknown",
                    "age_group_id": match["age_group_id"],
                    "age_group_name": match["age_group"]["name"]
                    if match.get("age_group")
                    else "Unknown",
                    "match_type_id": match["match_type_id"],
                    "match_type_name": match["match_type"]["name"]
                    if match.get("match_type")
                    else "Unknown",
                    "division_id": match.get("division_id"),
                    "division_name": match["division"]["name"]
                    if match.get("division")
                    else "Unknown",
                    "league_id": match["division"]["league_id"]
                    if match.get("division")
                    else None,
                    "league_name": match["division"]["leagues"]["name"]
                    if match.get("division") and match["division"].get("leagues")
                    else "Unknown",
                    "division": match.get("division"),  # Include full division object with leagues
                    "match_status": match.get("match_status"),
                    "created_by": match.get("created_by"),
                    "updated_by": match.get("updated_by"),
                    "source": match.get("source", "manual"),
                    "match_id": match.get("match_id"),  # External match identifier
                    "created_at": match["created_at"],
                    "updated_at": match["updated_at"],
                }
                matches.append(flat_match)

            return matches

        except Exception:
            logger.exception("Error querying matches")
            return []

    def get_matches_by_team(self, team_id: int, season_id: int | None = None, age_group_id: int | None = None) -> list[dict]:
        """Get all matches for a specific team."""
        try:
            query = (
                self.client.table("matches")
                .select("""
                *,
                home_team:teams!matches_home_team_id_fkey(id, name),
                away_team:teams!matches_away_team_id_fkey(id, name),
                season:seasons(id, name),
                age_group:age_groups(id, name),
                match_type:match_types(id, name),
                division:divisions(id, name)
            """)
                .or_(f"home_team_id.eq.{team_id},away_team_id.eq.{team_id}")
            )

            if season_id:
                query = query.eq("season_id", season_id)

            if age_group_id:
                query = query.eq("age_group_id", age_group_id)

            response = query.order("match_date", desc=True).execute()

            # Flatten response (same as get_all_matches)
            matches = []
            for match in response.data:
                flat_match = {
                    "id": match["id"],
                    "match_date": match["match_date"],
                    "home_team_id": match["home_team_id"],
                    "away_team_id": match["away_team_id"],
                    "home_team_name": match["home_team"]["name"]
                    if match.get("home_team")
                    else "Unknown",
                    "away_team_name": match["away_team"]["name"]
                    if match.get("away_team")
                    else "Unknown",
                    "home_score": match["home_score"],
                    "away_score": match["away_score"],
                    "season_id": match["season_id"],
                    "season_name": match["season"]["name"] if match.get("season") else "Unknown",
                    "age_group_id": match["age_group_id"],
                    "age_group_name": match["age_group"]["name"]
                    if match.get("age_group")
                    else "Unknown",
                    "match_type_id": match["match_type_id"],
                    "match_type_name": match["match_type"]["name"]
                    if match.get("match_type")
                    else "Unknown",
                    "division_id": match.get("division_id"),
                    "division_name": match["division"]["name"]
                    if match.get("division")
                    else "Unknown",
                    "division": match.get("division"),  # Include full division object with leagues
                    "match_status": match.get("match_status"),
                    "created_by": match.get("created_by"),
                    "updated_by": match.get("updated_by"),
                    "source": match.get("source", "manual"),
                    "match_id": match.get("match_id"),  # External match identifier
                    "created_at": match.get("created_at"),
                    "updated_at": match.get("updated_at"),
                }
                matches.append(flat_match)

            return matches

        except Exception:
            logger.exception("Error querying matches by team")
            return []

    def add_match(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        home_score: int,
        away_score: int,
        season_id: int,
        age_group_id: int,
        match_type_id: int,
        division_id: int | None = None,
        status: str | None = "scheduled",
        created_by: str | None = None,
        source: str = "manual",
        external_match_id: str | None = None,
    ) -> bool:
        """Add a new match with audit trail and optional external match_id."""
        try:
            data = {
                "match_date": match_date,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_score": home_score,
                "away_score": away_score,
                "season_id": season_id,
                "age_group_id": age_group_id,
                "match_type_id": match_type_id,
                "source": source,
            }

            # Add optional fields
            if division_id:
                data["division_id"] = division_id
            if status:
                data["match_status"] = status  # Map status to match_status column
            if created_by:
                data["created_by"] = created_by
            if external_match_id:
                data["match_id"] = external_match_id

            response = self.client.table("matches").insert(data).execute()

            return bool(response.data)

        except Exception:
            logger.exception("Error adding match")
            return False

    def add_match_with_external_id(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        home_score: int,
        away_score: int,
        season_id: int,
        age_group_id: int,
        match_type_id: int,
        external_match_id: str,
        division_id: int | None = None,
        created_by: str | None = None,
        source: str = "match-scraper",
    ) -> bool:
        """Add a new match with external match_id and audit trail.

        This is a convenience wrapper around add_match() for backwards compatibility.
        Consider using add_match() directly with external_match_id parameter.
        """
        return self.add_match(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            match_date=match_date,
            home_score=home_score,
            away_score=away_score,
            season_id=season_id,
            age_group_id=age_group_id,
            match_type_id=match_type_id,
            division_id=division_id,
            created_by=created_by,
            source=source,
            external_match_id=external_match_id,
        )

    def update_match(
        self,
        match_id: int,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        home_score: int,
        away_score: int,
        season_id: int,
        age_group_id: int,
        match_type_id: int,
        division_id: int | None = None,
        status: str | None = None,
        updated_by: str | None = None,
        external_match_id: str | None = None,
    ) -> dict | None:
        """Update an existing match with audit trail and optional external match_id.

        Returns the updated match data to avoid read-after-write consistency issues.
        """
        try:
            data = {
                "match_date": match_date,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_score": home_score,
                "away_score": away_score,
                "season_id": season_id,
                "age_group_id": age_group_id,
                "match_type_id": match_type_id,
                "division_id": division_id,
            }

            # Add optional fields
            if status:
                data["match_status"] = status
            if updated_by:
                data["updated_by"] = updated_by
            if external_match_id is not None:  # Allow explicit None to clear match_id
                data["match_id"] = external_match_id

            # Execute update
            response = (
                self.client.table("matches")
                .update(data)
                .eq("id", match_id)
                .execute()
            )

            # Check if update actually affected any rows
            if not response.data or len(response.data) == 0:
                logger.warning("Update match failed - no rows affected", match_id=match_id)
                # Return None to signal failure
                return None

            # Delay to allow Supabase cache to update (read-after-write consistency)
            import time
            time.sleep(0.3)  # 300ms delay - increased for reliable read-after-write

            # Get the updated match to return with full relations
            return self.get_match_by_id(match_id)

        except Exception:
            logger.exception("Error updating match")
            return None

    def get_match_by_id(self, match_id: int) -> dict | None:
        """Get a single match by ID with all related data."""
        try:
            response = (
                self.client.table("matches")
                .select("""
                    *,
                    home_team:teams!matches_home_team_id_fkey(
                        id, name,
                        club:clubs(id, name, logo_url, primary_color, secondary_color)
                    ),
                    away_team:teams!matches_away_team_id_fkey(
                        id, name,
                        club:clubs(id, name, logo_url, primary_color, secondary_color)
                    ),
                    season:seasons(id, name),
                    age_group:age_groups(id, name),
                    match_type:match_types(id, name),
                    division:divisions(id, name, leagues(id, name))
                """)
                .eq("id", match_id)
                .execute()
            )

            if response.data and len(response.data) > 0:
                match = response.data[0]
                # Flatten the response to match the format from get_all_matches
                flat_match = {
                    "id": match["id"],
                    "match_date": match["match_date"],
                    "home_team_id": match["home_team_id"],
                    "away_team_id": match["away_team_id"],
                    "home_team_name": match["home_team"]["name"]
                    if match.get("home_team")
                    else "Unknown",
                    "away_team_name": match["away_team"]["name"]
                    if match.get("away_team")
                    else "Unknown",
                    "home_team_club": match["home_team"].get("club")
                    if match.get("home_team")
                    else None,
                    "away_team_club": match["away_team"].get("club")
                    if match.get("away_team")
                    else None,
                    "home_score": match["home_score"],
                    "away_score": match["away_score"],
                    "season_id": match["season_id"],
                    "season_name": match["season"]["name"] if match.get("season") else "Unknown",
                    "age_group_id": match["age_group_id"],
                    "age_group_name": match["age_group"]["name"]
                    if match.get("age_group")
                    else "Unknown",
                    "match_type_id": match["match_type_id"],
                    "match_type_name": match["match_type"]["name"]
                    if match.get("match_type")
                    else "Unknown",
                    "division_id": match.get("division_id"),
                    "division_name": match["division"]["name"]
                    if match.get("division")
                    else "Unknown",
                    "division": match.get("division"),  # Include full division object with leagues
                    "match_status": match.get("match_status"),
                    "created_by": match.get("created_by"),
                    "updated_by": match.get("updated_by"),
                    "source": match.get("source", "manual"),
                    "match_id": match.get("match_id"),  # External match identifier
                    "created_at": match["created_at"],
                    "updated_at": match["updated_at"],
                }
                return flat_match
            else:
                return None

        except Exception:
            logger.exception("Error retrieving match by ID")
            return None

    def delete_match(self, match_id: int) -> bool:
        """Delete a match."""
        try:
            response = self.client.table("matches").delete().eq("id", match_id).execute()

            return True  # Supabase delete returns empty data even on success

        except Exception:
            logger.exception("Error deleting match")
            return False

    def get_league_table(
        self,
        season_id: int | None = None,
        age_group_id: int | None = None,
        division_id: int | None = None,
        match_type: str = "League",
    ) -> list[dict]:
        """
        Generate league table with optional filters.

        This method fetches matches from the database and delegates
        the standings calculation to pure functions in dao/standings.py.

        Args:
            season_id: Filter by season
            age_group_id: Filter by age group
            division_id: Filter by division
            match_type: Filter by match type name (default: "League")

        Returns:
            List of team standings sorted by points, goal difference, goals scored
        """
        try:
            # Fetch matches from database
            matches = self._fetch_matches_for_standings(season_id, age_group_id, division_id)

            # Apply filters using pure functions
            matches = filter_by_match_type(matches, match_type)
            if division_id:
                matches = filter_same_division_matches(matches, division_id)
            matches = filter_completed_matches(matches)

            # Calculate standings using pure function
            return calculate_standings(matches)

        except Exception:
            logger.exception("Error generating league table")
            return []

    def _fetch_matches_for_standings(
        self,
        season_id: int | None = None,
        age_group_id: int | None = None,
        division_id: int | None = None,
    ) -> list[dict]:
        """
        Fetch matches from database for standings calculation.

        This is a thin data access method that only handles the query.
        All business logic is in pure functions.

        Args:
            season_id: Filter by season
            age_group_id: Filter by age group
            division_id: Filter by division

        Returns:
            List of match dictionaries from database
        """
        query = self.client.table("matches").select("""
            *,
            home_team:teams!matches_home_team_id_fkey(id, name, division_id),
            away_team:teams!matches_away_team_id_fkey(id, name, division_id),
            match_type:match_types(id, name)
        """)

        # Apply database-level filters
        if season_id:
            query = query.eq("season_id", season_id)
        if age_group_id:
            query = query.eq("age_group_id", age_group_id)
        if division_id:
            query = query.eq("division_id", division_id)

        response = query.execute()
        return response.data

    # === Admin CRUD Methods ===

    def create_age_group(self, name: str) -> dict:
        """Create a new age group."""
        try:
            result = self.client.table("age_groups").insert({"name": name}).execute()
            return result.data[0]
        except Exception as e:
            logger.exception("Error creating age group")
            raise e

    def update_age_group(self, age_group_id: int, name: str) -> dict | None:
        """Update an age group."""
        try:
            result = (
                self.client.table("age_groups")
                .update({"name": name})
                .eq("id", age_group_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            logger.exception("Error updating age group")
            raise e

    def delete_age_group(self, age_group_id: int) -> bool:
        """Delete an age group."""
        try:
            result = self.client.table("age_groups").delete().eq("id", age_group_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.exception("Error deleting age group")
            raise e

    def create_season(self, name: str, start_date: str, end_date: str) -> dict:
        """Create a new season."""
        try:
            result = (
                self.client.table("seasons")
                .insert({"name": name, "start_date": start_date, "end_date": end_date})
                .execute()
            )
            return result.data[0]
        except Exception as e:
            logger.exception("Error creating season")
            raise e

    def update_season(
        self, season_id: int, name: str, start_date: str, end_date: str
    ) -> dict | None:
        """Update a season."""
        try:
            result = (
                self.client.table("seasons")
                .update({"name": name, "start_date": start_date, "end_date": end_date})
                .eq("id", season_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            logger.exception("Error updating season")
            raise e

    def delete_season(self, season_id: int) -> bool:
        """Delete a season."""
        try:
            result = self.client.table("seasons").delete().eq("id", season_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.exception("Error deleting season")
            raise e

    def create_division(self, division_data: dict) -> dict:
        """Create a new division.

        Args:
            division_data: Dict with keys: name, description (optional), league_id (required)
        """
        try:
            logger.debug("Creating division", division_data=division_data)
            result = self.client.table("divisions").insert(division_data).execute()
            logger.debug("Division created successfully", division=result.data[0])
            return result.data[0]
        except Exception as e:
            logger.exception("Error creating division")
            raise e

    def update_division(self, division_id: int, division_data: dict) -> dict | None:
        """Update a division.

        Args:
            division_id: Division ID to update
            division_data: Dict with any of: name, description, league_id
        """
        try:
            result = self.client.table("divisions").update(division_data).eq("id", division_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.exception("Error updating division")
            raise e

    def delete_division(self, division_id: int) -> bool:
        """Delete a division."""
        try:
            result = self.client.table("divisions").delete().eq("id", division_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.exception("Error deleting division")
            raise e

    def update_team(
        self, team_id: int, name: str, city: str, academy_team: bool = False, club_id: int | None = None, client_ip: str | None = None
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

    # === Club/Parent Club Methods ===

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

    # === User Profile Methods ===

    def get_user_profile_with_relationships(self, user_id: str) -> dict | None:
        """
        Get user profile with team, club, and age group relationships.

        Args:
            user_id: User ID to fetch profile for

        Returns:
            User profile dict with team, club, and age_group data, or None if not found
        """
        try:
            response = self.client.table('user_profiles').select('''
                *,
                team:teams(id, name, city, club_id, league_id, division_id, age_group_id,
                    age_group:age_groups(id, name),
                    league:leagues(id, name),
                    division:divisions(id, name),
                    club:clubs(id, name, city, logo_url, primary_color, secondary_color)
                ),
                club:clubs(id, name, city, logo_url, primary_color, secondary_color)
            ''').eq('id', user_id).execute()

            if response.data and len(response.data) > 0:
                profile = response.data[0]
                if len(response.data) > 1:
                    logger.warning(f"Multiple profiles found for user {user_id}, using first one")
                return profile
            return None
        except Exception as e:
            logger.error(f"Error fetching user profile: {e}")
            return None

    def create_or_update_user_profile(self, profile_data: dict) -> dict | None:
        """
        Create or update a user profile.

        Args:
            profile_data: Dictionary containing user profile data

        Returns:
            Created/updated profile dict, or None on error
        """
        try:
            response = self.client.table('user_profiles').upsert(profile_data).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error creating/updating user profile: {e}")
            return None

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
            response = self.client.table('user_profiles').update(update_data).eq('id', user_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            return None

    def get_user_profile_by_email(self, email: str, exclude_user_id: str | None = None) -> dict | None:
        """
        Get user profile by email, optionally excluding a specific user ID.

        Useful for checking if an email is already in use by another user.

        Args:
            email: Email address to search for
            exclude_user_id: Optional user ID to exclude from search

        Returns:
            User profile dict if found, None otherwise
        """
        try:
            query = self.client.table('user_profiles').select('id').eq('email', email)
            if exclude_user_id:
                query = query.neq('id', exclude_user_id)
            response = query.execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error checking user profile by email: {e}")
            return None

    def get_all_user_profiles(self) -> list[dict]:
        """
        Get all user profiles with team relationships.

        Returns:
            List of user profile dicts
        """
        try:
            response = self.client.table('user_profiles').select('''
                *,
                team:teams(id, name, city)
            ''').order('created_at', desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all user profiles: {e}")
            return []

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
            response = self.client.table('player_team_history').select('''
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
            ''').eq('team_id', team_id).eq('is_current', True).execute()

            # Flatten the results - extract user_profiles and merge with history data
            players = []
            for entry in response.data or []:
                profile = entry.get('user_profiles')
                if profile:
                    # Use jersey_number from history if available, fallback to profile
                    player = {**profile}
                    if entry.get('jersey_number') is not None:
                        player['player_number'] = entry['jersey_number']
                    # Use positions from history if available, fallback to profile
                    if entry.get('positions'):
                        player['positions'] = entry['positions']
                    players.append(player)

            # Sort by player_number
            players.sort(key=lambda p: p.get('player_number') or 999)
            return players
        except Exception as e:
            logger.error(f"Error fetching team players for team {team_id}: {e}")
            return []

    def get_user_profile_by_username(self, username: str, exclude_user_id: str | None = None) -> dict | None:
        """
        Get user profile by username, optionally excluding a specific user ID.

        Useful for checking if a username is already taken.

        Args:
            username: Username to search for (will be lowercased)
            exclude_user_id: Optional user ID to exclude from search

        Returns:
            User profile dict if found, None otherwise
        """
        try:
            query = self.client.table('user_profiles').select('id').eq('username', username.lower())
            if exclude_user_id:
                query = query.neq('id', exclude_user_id)
            response = query.execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error checking user profile by username: {e}")
            return None

    # === Player Team History Methods ===

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
            response = self.client.table('player_team_history').select('''
                *,
                team:teams(id, name, city,
                    club:clubs(id, name, primary_color, secondary_color)
                ),
                season:seasons(id, name, start_date, end_date),
                age_group:age_groups(id, name),
                league:leagues(id, name),
                division:divisions(id, name)
            ''').eq('player_id', player_id).order('season_id', desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching player team history: {e}")
            return []

    def get_current_player_team_assignment(self, player_id: str) -> dict | None:
        """
        Get the current team assignment for a player (is_current=true).

        Args:
            player_id: User ID of the player

        Returns:
            Current history entry dict with related data, or None if not found
        """
        try:
            response = self.client.table('player_team_history').select('''
                *,
                team:teams(id, name, city,
                    club:clubs(id, name, primary_color, secondary_color)
                ),
                season:seasons(id, name, start_date, end_date),
                age_group:age_groups(id, name),
                league:leagues(id, name),
                division:divisions(id, name)
            ''').eq('player_id', player_id).eq('is_current', True).limit(1).execute()

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

        Args:
            player_id: User ID of the player

        Returns:
            List of current history entries with related team and club data
        """
        try:
            response = self.client.table('player_team_history').select('''
                *,
                team:teams(id, name, city,
                    club:clubs(id, name, logo_url, primary_color, secondary_color),
                    age_group:age_groups(id, name),
                    league:leagues(id, name),
                    division:divisions(id, name)
                ),
                season:seasons(id, name, start_date, end_date),
                age_group:age_groups(id, name)
            ''').eq('player_id', player_id).eq('is_current', True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all current player teams: {e}")
            return []

    def create_player_history_entry(
        self,
        player_id: str,
        team_id: int,
        season_id: int,
        jersey_number: int | None = None,
        positions: list[str] | None = None,
        notes: str | None = None,
        is_current: bool = False
    ) -> dict | None:
        """
        Create a new player team history entry.

        Uses the database function to handle:
        - Auto-populating age_group_id, league_id, division_id from team
        - Marking previous entries as not current if is_current=True

        Args:
            player_id: User ID of the player
            team_id: Team ID
            season_id: Season ID
            jersey_number: Optional jersey number for that season
            positions: Optional list of positions played
            notes: Optional notes about the assignment
            is_current: Whether this is the current assignment

        Returns:
            Created history entry dict, or None on error
        """
        try:
            # Note: We use direct insert instead of RPC because the RPC function
            # automatically unsets is_current on all other entries, which prevents
            # players from being on multiple teams simultaneously (futsal use case)

            # Get team details for age_group_id, league_id, division_id
            team_response = self.client.table('teams').select(
                'age_group_id, league_id, division_id'
            ).eq('id', team_id).execute()

            team_data = team_response.data[0] if team_response.data else {}

            insert_data = {
                'player_id': player_id,
                'team_id': team_id,
                'season_id': season_id,
                'age_group_id': team_data.get('age_group_id'),
                'league_id': team_data.get('league_id'),
                'division_id': team_data.get('division_id'),
                'jersey_number': jersey_number,
                'positions': positions,
                'is_current': is_current,
                'notes': notes
            }

            response = self.client.table('player_team_history').insert(insert_data).execute()
            if response.data and len(response.data) > 0:
                return self.get_player_history_entry_by_id(response.data[0]['id'])
            return None
        except Exception as e:
            logger.error(f"Error creating player history entry: {e}")
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
            response = self.client.table('player_team_history').select('''
                *,
                team:teams(id, name, city,
                    club:clubs(id, name, primary_color, secondary_color)
                ),
                season:seasons(id, name, start_date, end_date),
                age_group:age_groups(id, name),
                league:leagues(id, name),
                division:divisions(id, name)
            ''').eq('id', history_id).execute()

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching player history entry: {e}")
            return None

    def update_player_history_entry(
        self,
        history_id: int,
        jersey_number: int | None = None,
        positions: list[str] | None = None,
        notes: str | None = None,
        is_current: bool | None = None
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
            update_data = {'updated_at': 'now()'}

            if jersey_number is not None:
                update_data['jersey_number'] = jersey_number
            if positions is not None:
                update_data['positions'] = positions
            if notes is not None:
                update_data['notes'] = notes
            if is_current is not None:
                update_data['is_current'] = is_current
                # Note: We allow multiple current teams (for futsal/multi-league players)
                # So we don't automatically unset is_current on other entries

            response = self.client.table('player_team_history').update(update_data).eq('id', history_id).execute()

            if response.data and len(response.data) > 0:
                return self.get_player_history_entry_by_id(history_id)
            return None
        except Exception as e:
            logger.error(f"Error updating player history entry: {e}")
            return None

    def delete_player_history_entry(self, history_id: int) -> bool:
        """
        Delete a player team history entry.

        Args:
            history_id: History entry ID to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            self.client.table('player_team_history').delete().eq('id', history_id).execute()
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
        offset: int = 0
    ) -> dict:
        """
        Get all players with their current team assignments for admin management.

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
            query = self.client.table('user_profiles').select(
                '''
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
                ''',
                count='exact'
            ).eq('role', 'team-player')

            # Apply text search filter
            if search:
                query = query.or_(f"display_name.ilike.%{search}%,email.ilike.%{search}%")

            # Apply team filter
            if team_id:
                query = query.eq('team_id', team_id)
            # Apply club filter (via team)
            elif club_id:
                # Need to get team IDs for this club first
                teams_response = self.client.table('teams').select('id').eq('club_id', club_id).execute()
                if teams_response.data:
                    team_ids = [t['id'] for t in teams_response.data]
                    query = query.in_('team_id', team_ids)

            # Apply pagination and ordering
            query = query.order('display_name').range(offset, offset + limit - 1)

            response = query.execute()

            players = response.data or []
            total = response.count or 0

            # Enrich with current team assignments from player_team_history
            for player in players:
                history_response = self.client.table('player_team_history').select(
                    '''
                    id,
                    team_id,
                    season_id,
                    jersey_number,
                    is_current,
                    created_at,
                    team:teams(id, name, club:clubs(id, name)),
                    season:seasons(id, name)
                    '''
                ).eq('player_id', player['id']).eq('is_current', True).execute()
                player['current_teams'] = history_response.data or []

            return {'players': players, 'total': total}

        except Exception as e:
            logger.error(f"Error fetching players for admin: {e}")
            return {'players': [], 'total': 0}

    def update_player_admin(
        self,
        player_id: str,
        display_name: str | None = None,
        player_number: int | None = None,
        positions: list[str] | None = None
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
            update_data = {'updated_at': 'now()'}

            if display_name is not None:
                update_data['display_name'] = display_name
            if player_number is not None:
                update_data['player_number'] = player_number
            if positions is not None:
                update_data['positions'] = positions

            response = self.client.table('user_profiles').update(update_data).eq('id', player_id).execute()

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"Error updating player admin: {e}")
            return None

    def end_player_team_assignment(self, history_id: int) -> dict | None:
        """
        End a player's team assignment by setting is_current=false.

        Args:
            history_id: Player team history ID

        Returns:
            Updated history entry dict, or None on error
        """
        try:
            update_data = {
                'is_current': False,
                'updated_at': 'now()'
            }

            response = self.client.table('player_team_history').update(update_data).eq('id', history_id).execute()

            if response.data and len(response.data) > 0:
                return self.get_player_history_entry_by_id(history_id)
            return None

        except Exception as e:
            logger.error(f"Error ending player team assignment: {e}")
            return None

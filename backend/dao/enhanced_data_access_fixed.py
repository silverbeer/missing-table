"""
Enhanced Supabase data access layer with SSL fix.
"""

import os
import structlog

import httpx
from dotenv import load_dotenv
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
        self.key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_SERVICE_KEY) must be set in .env file")
        
        # Debug output
        print(f"DEBUG: Connecting to Supabase URL: {self.url}")
        print(f"DEBUG: Using key type: {'SERVICE_KEY' if 'SUPABASE_SERVICE_KEY' in os.environ and self.key == os.getenv('SUPABASE_SERVICE_KEY') else 'ANON_KEY'}")
        
        try:
            # Try with custom httpx client
            transport = httpx.HTTPTransport(retries=3)
            timeout = httpx.Timeout(30.0, connect=10.0)

            # Create custom client with extended timeout and retries
            http_client = httpx.Client(transport=transport, timeout=timeout, follow_redirects=True)

            # Create Supabase client with custom HTTP client
            self.client = create_client(self.url, self.key, options={"httpx_client": http_client})
            print("Connection to Supabase established.")

        except Exception:
            # Fallback to standard client
            self.client = create_client(self.url, self.key)
            print("Connection to Supabase established.")

    def get_client(self):
        """Get the Supabase client instance."""
        return self.client


class EnhancedSportsDAO:
    """Enhanced Data Access Object for sports data using new normalized schema."""

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
        except Exception as e:
            print(f"Error querying age groups: {e}")
            return []

    def get_all_seasons(self) -> list[dict]:
        """Get all seasons."""
        try:
            response = (
                self.client.table("seasons").select("*").order("start_date", desc=True).execute()
            )
            return response.data
        except Exception as e:
            print(f"Error querying seasons: {e}")
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
            print(f"No current season found: {e}")
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
        except Exception as e:
            print(f"Error querying active seasons: {e}")
            return []

    def get_all_match_types(self) -> list[dict]:
        """Get all match types."""
        try:
            response = self.client.table("match_types").select("*").order("name").execute()
            return response.data
        except Exception as e:
            print(f"Error querying match types: {e}")
            return []

    def get_match_type_by_id(self, match_type_id: int) -> dict | None:
        """Get match type by ID."""
        try:
            response = self.client.table("match_types").select("*").eq("id", match_type_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error querying match type: {e}")
            return None

    # === League Methods ===

    def get_all_leagues(self) -> list[dict]:
        """Get all leagues ordered by name."""
        try:
            response = self.client.table("leagues").select("*").order("name").execute()
            return response.data
        except Exception as e:
            print(f"Error querying leagues: {e}")
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
        except Exception as e:
            print(f"Error querying league {league_id}: {e}")
            return None

    def create_league(self, league_data: dict) -> dict:
        """Create new league."""
        try:
            response = self.client.table("leagues").insert(league_data).execute()
            return response.data[0]
        except Exception as e:
            print(f"Error creating league: {e}")
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
        except Exception as e:
            print(f"Error updating league {league_id}: {e}")
            raise

    def delete_league(self, league_id: int) -> bool:
        """Delete league (will fail if divisions exist due to FK constraint)."""
        try:
            self.client.table("leagues").delete().eq("id", league_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting league {league_id}: {e}")
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
        except Exception as e:
            print(f"Error querying divisions: {e}")
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
        except Exception as e:
            print(f"Error querying divisions for league {league_id}: {e}")
            return []

    # === Team Methods ===

    def get_all_teams(self) -> list[dict]:
        """Get all teams with their age groups."""
        try:
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
        except Exception as e:
            print(f"Error querying teams: {e}")
            return []

    def get_teams_by_match_type_and_age_group(
        self, match_type_id: int, age_group_id: int
    ) -> list[dict]:
        """Get teams that can participate in a specific match type and age group."""
        try:
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
        except Exception as e:
            print(f"Error querying teams by match type and age group: {e}")
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
        except Exception as e:
            print(f"Error adding team match type participation: {e}")
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
        except Exception as e:
            print(f"Error removing team match type participation: {e}")
            return False

    def add_team(
        self,
        name: str,
        city: str,
        age_group_ids: list[int],
        division_id: int,
        club_id: int | None = None,
        academy_team: bool = False,
        client_ip: str | None = None,
    ) -> bool:
        """Add a new team with age groups, division, and optional club.

        Division represents location (e.g., Northeast Division for Homegrown,
        New England Conference for Academy). All age groups share the same division.

        Args:
            name: Team name
            city: Team city
            age_group_ids: List of age group IDs (required, at least one)
            division_id: Division ID (required, applies to all age groups)
            club_id: Optional club ID
            academy_team: Whether this is an academy team
            client_ip: Client IP address for security monitoring (optional)
        """
        try:
            # Validate required fields
            if not age_group_ids or len(age_group_ids) == 0:
                raise ValueError("Team must have at least one age group")

            # Get league_id from division
            division_response = (
                self.client.table("divisions")
                .select("league_id")
                .eq("id", division_id)
                .execute()
            )
            if not division_response.data:
                raise ValueError(f"Division {division_id} not found")
            league_id = division_response.data[0]["league_id"]

            # Insert team with club, league, and division
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
                return False

            team_id = team_response.data[0]["id"]

            # Add age group associations with the same division for all
            for age_group_id in age_group_ids:
                data = {
                    "team_id": team_id,
                    "age_group_id": age_group_id,
                    "division_id": division_id  # Same division for all age groups
                }
                self.client.table("team_mappings").insert(data).execute()

            return True

        except Exception as e:
            error_str = str(e)
            print(f"Error adding team: {e}")

            # Re-raise duplicate key errors so API can handle them properly
            if "teams_name_division_unique" in error_str or "teams_name_academy_unique" in error_str or "duplicate key value" in error_str.lower():
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

        except Exception as e:
            print(f"Error updating team division: {e}")
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

        except Exception as e:
            print(f"Error getting team by name '{name}': {e}")
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

        except Exception as e:
            print(f"Error getting age group by name '{name}': {e}")
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

        except Exception as e:
            print(f"Error getting division by name '{name}': {e}")
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

        except Exception as e:
            print(f"Error getting match by external ID '{external_match_id}': {e}")
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

        except Exception as e:
            print(f"Error getting match by teams and date: {e}")
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
                print(f"Updated match {match_id} with external match_id: {external_match_id}")
                return True
            return False

        except Exception as e:
            print(f"Error updating match external_id: {e}")
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

        except Exception as e:
            print(f"Error creating match: {e}")
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

        except Exception as e:
            print(f"Error querying matches: {e}")
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

        except Exception as e:
            print(f"Error querying matches by team: {e}")
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

        except Exception as e:
            print(f"Error adding match: {e}")
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
                print(f"WARNING: Update match {match_id} failed - no rows affected")
                # Return None to signal failure
                return None

            # Delay to allow Supabase cache to update (read-after-write consistency)
            import time
            time.sleep(0.3)  # 300ms delay - increased for reliable read-after-write

            # Get the updated match to return with full relations
            return self.get_match_by_id(match_id)

        except Exception as e:
            print(f"Error updating match: {e}")
            return None

    def get_match_by_id(self, match_id: int) -> dict | None:
        """Get a single match by ID with all related data."""
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

        except Exception as e:
            print(f"Error retrieving match by ID: {e}")
            return None

    def delete_match(self, match_id: int) -> bool:
        """Delete a match."""
        try:
            response = self.client.table("matches").delete().eq("id", match_id).execute()

            return True  # Supabase delete returns empty data even on success

        except Exception as e:
            print(f"Error deleting match: {e}")
            return False

    def get_league_table(
        self,
        season_id: int | None = None,
        age_group_id: int | None = None,
        division_id: int | None = None,
        match_type: str = "League",
    ) -> list[dict]:
        """Generate league table with optional filters."""
        try:
            # Build query - include team division_id to filter cross-division matches
            query = self.client.table("matches").select("""
                *,
                home_team:teams!matches_home_team_id_fkey(id, name, division_id),
                away_team:teams!matches_away_team_id_fkey(id, name, division_id),
                match_type:match_types(id, name)
            """)

            # Apply filters
            if season_id:
                query = query.eq("season_id", season_id)
            if age_group_id:
                query = query.eq("age_group_id", age_group_id)
            if division_id:
                query = query.eq("division_id", division_id)

            # Get matches
            response = query.execute()

            # Filter by match type name and status
            matches = [m for m in response.data if m.get("match_type", {}).get("name") == match_type]

            # Filter out cross-division matches for league standings
            # Only include matches where BOTH teams belong to the requested division
            if division_id:
                same_division_matches = []
                for match in matches:
                    home_div_id = match.get("home_team", {}).get("division_id")
                    away_div_id = match.get("away_team", {}).get("division_id")

                    # Only include if both teams are in the requested division
                    if home_div_id == division_id and away_div_id == division_id:
                        same_division_matches.append(match)

                matches = same_division_matches

            # Filter to only include completed matches (exclude scheduled/postponed/cancelled)
            # Use match_status field if available, otherwise fallback to date-based logic for backwards compatibility
            played_matches = []
            for match in matches:
                match_status = match.get("match_status")
                if match_status:
                    # Use match_status field if available
                    if match_status == "completed":
                        played_matches.append(match)
                else:
                    # Fallback to date-based logic for backwards compatibility
                    from datetime import date
                    match_date = date.fromisoformat(match["match_date"])
                    if match_date <= date.today():
                        played_matches.append(match)

            # Calculate standings
            from collections import defaultdict

            standings = defaultdict(
                lambda: {
                    "played": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "goal_difference": 0,
                    "points": 0,
                }
            )

            for match in played_matches:
                home_team = match["home_team"]["name"]
                away_team = match["away_team"]["name"]
                home_score = match["home_score"]
                away_score = match["away_score"]

                # Skip matches without scores
                if home_score is None or away_score is None:
                    continue

                # Update stats
                standings[home_team]["played"] += 1
                standings[away_team]["played"] += 1
                standings[home_team]["goals_for"] += home_score
                standings[home_team]["goals_against"] += away_score
                standings[away_team]["goals_for"] += away_score
                standings[away_team]["goals_against"] += home_score

                if home_score > away_score:
                    standings[home_team]["wins"] += 1
                    standings[home_team]["points"] += 3
                    standings[away_team]["losses"] += 1
                elif away_score > home_score:
                    standings[away_team]["wins"] += 1
                    standings[away_team]["points"] += 3
                    standings[home_team]["losses"] += 1
                else:
                    standings[home_team]["draws"] += 1
                    standings[away_team]["draws"] += 1
                    standings[home_team]["points"] += 1
                    standings[away_team]["points"] += 1

            # Convert to list and calculate goal difference
            table = []
            for team, stats in standings.items():
                stats["goal_difference"] = stats["goals_for"] - stats["goals_against"]
                stats["team"] = team
                table.append(stats)

            # Sort by points, goal difference, goals scored
            table.sort(
                key=lambda x: (x["points"], x["goal_difference"], x["goals_for"]), reverse=True
            )

            return table

        except Exception as e:
            print(f"Error generating league table: {e}")
            return []

    # === Admin CRUD Methods ===

    def create_age_group(self, name: str) -> dict:
        """Create a new age group."""
        try:
            result = self.client.table("age_groups").insert({"name": name}).execute()
            return result.data[0]
        except Exception as e:
            print(f"Error creating age group: {e}")
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
            print(f"Error updating age group: {e}")
            raise e

    def delete_age_group(self, age_group_id: int) -> bool:
        """Delete an age group."""
        try:
            result = self.client.table("age_groups").delete().eq("id", age_group_id).execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"Error deleting age group: {e}")
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
            print(f"Error creating season: {e}")
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
            print(f"Error updating season: {e}")
            raise e

    def delete_season(self, season_id: int) -> bool:
        """Delete a season."""
        try:
            result = self.client.table("seasons").delete().eq("id", season_id).execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"Error deleting season: {e}")
            raise e

    def create_division(self, division_data: dict) -> dict:
        """Create a new division.

        Args:
            division_data: Dict with keys: name, description (optional), league_id (required)
        """
        try:
            print(f"Creating division with data: {division_data}")
            result = self.client.table("divisions").insert(division_data).execute()
            print(f"Division created successfully: {result.data[0]}")
            return result.data[0]
        except Exception as e:
            print(f"Error creating division: {e}")
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
            print(f"Error updating division: {e}")
            raise e

    def delete_division(self, division_id: int) -> bool:
        """Delete a division."""
        try:
            result = self.client.table("divisions").delete().eq("id", division_id).execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"Error deleting division: {e}")
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
            print(f"DEBUG DAO update_team: team_id={team_id}, update_data={update_data}")

            result = (
                self.client.table("teams")
                .update(update_data)
                .eq("id", team_id)
                .execute()
            )

            print(f"DEBUG DAO update result: {result.data}")
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error updating team: {e}")
            raise e

    def delete_team(self, team_id: int) -> bool:
        """Delete a team."""
        try:
            result = self.client.table("teams").delete().eq("id", team_id).execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"Error deleting team: {e}")
            raise e

    def create_team_mapping(self, team_id: int, age_group_id: int, division_id: int) -> dict:
        """Create a team mapping."""
        try:
            result = (
                self.client.table("team_mappings")
                .insert(
                    {"team_id": team_id, "age_group_id": age_group_id, "division_id": division_id}
                )
                .execute()
            )
            return result.data[0]
        except Exception as e:
            print(f"Error creating team mapping: {e}")
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
            print(f"Error deleting team mapping: {e}")
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
        except Exception as e:
            print(f"Error querying parent club entities: {e}")
            return []

    def get_all_clubs(self) -> list[dict]:
        """Get all clubs with their associated teams count.

        Returns list of clubs from the clubs table.
        Use get_club_teams(club_id) to get teams for a specific club.
        """
        try:
            # Query clubs table directly
            response = self.client.table("clubs").select("*").order("name").execute()
            clubs = response.data

            # Enrich with team counts (optimized - single query instead of N+1)
            # Get all teams with club_id in one query
            teams_response = (
                self.client.table("teams")
                .select("club_id")
                .not_.is_("club_id", "null")
                .execute()
            )

            # Count teams per club
            from collections import Counter
            team_counts = Counter(team["club_id"] for team in teams_response.data if team.get("club_id"))

            # Enrich clubs with counts
            for club in clubs:
                club["team_count"] = team_counts.get(club["id"], 0)

            return clubs
        except Exception as e:
            print(f"Error querying clubs: {e}")
            return []

    def get_club_teams(self, club_id: int) -> list[dict]:
        """Get all teams for a club across all leagues.

        Args:
            club_id: The club ID from the clubs table

        Returns:
            List of teams belonging to this club
        """
        try:
            # Use the database function get_club_teams (updated in migration)
            response = self.client.rpc('get_club_teams', {'p_club_id': club_id}).execute()
            return response.data
        except Exception as e:
            print(f"Error querying club teams: {e}")
            # Fallback to manual query
            try:
                teams_response = self.client.table("teams").select("*").eq("club_id", club_id).execute()
                return teams_response.data
            except Exception as fallback_error:
                print(f"Error in fallback query: {fallback_error}")
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
            club_response = self.client.table("clubs").select("*").eq("id", club_id).execute()
            return club_response.data[0] if club_response.data and len(club_response.data) > 0 else None
        except Exception as e:
            print(f"Error querying club for team: {e}")
            return None

    def create_club(self, name: str, city: str, website: str = None, description: str = None) -> dict:
        """Create a new club.

        Args:
            name: Club name
            city: Club city/location
            website: Optional website URL
            description: Optional description

        Returns:
            Created club dict
        """
        try:
            club_data = {"name": name, "city": city}
            if website:
                club_data["website"] = website
            if description:
                club_data["description"] = description

            result = self.client.table("clubs").insert(club_data).execute()

            if not result.data or len(result.data) == 0:
                raise ValueError("Failed to create club")
            return result.data[0]
        except Exception as e:
            print(f"Error creating club: {e}")
            raise e

    def update_club(self, club_id: int, name: str = None, city: str = None, website: str = None, description: str = None) -> dict | None:
        """Update an existing club.

        Args:
            club_id: ID of club to update
            name: Optional new name
            city: Optional new city/location
            website: Optional new website URL
            description: Optional new description

        Returns:
            Updated club dict or None if not found
        """
        try:
            update_data = {}
            if name is not None:
                update_data["name"] = name
            if city is not None:
                update_data["city"] = city
            if website is not None:
                update_data["website"] = website
            if description is not None:
                update_data["description"] = description

            if not update_data:
                # Nothing to update
                return None

            result = self.client.table("clubs").update(update_data).eq("id", club_id).execute()

            if not result.data or len(result.data) == 0:
                return None
            return result.data[0]
        except Exception as e:
            print(f"Error updating club: {e}")
            raise e

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
            print(f"Error updating team club: {e}")
            raise e

    def delete_club(self, club_id: int) -> bool:
        """Delete a club.

        Args:
            club_id: The club ID to delete

        Returns:
            True if deleted successfully

        Note:
            This will fail if there are teams still associated with this club
            due to ON DELETE RESTRICT constraint.
        """
        try:
            self.client.table("clubs").delete().eq("id", club_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting club: {e}")
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
        except Exception as e:
            print(f"Error getting team game counts: {e}")
            # Return empty dict on error - teams will show 0 games
            return {}

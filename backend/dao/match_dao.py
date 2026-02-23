"""
Match data access layer for MissingTable.

Provides data access objects for matches, teams, leagues, divisions, seasons,
and related soccer/futbol data using Supabase.
"""

import os
from datetime import UTC

import httpx
import structlog
from dotenv import load_dotenv
from postgrest.exceptions import APIError

from dao.base_dao import BaseDAO, clear_cache, dao_cache, invalidates_cache
from dao.exceptions import DuplicateRecordError
from dao.standings import (
    calculate_standings,
    filter_by_match_type,
    filter_completed_matches,
    filter_same_division_matches,
)
from supabase import create_client

logger = structlog.get_logger()

# Cache patterns for invalidation
MATCHES_CACHE_PATTERN = "mt:dao:matches:*"
PLAYOFF_CACHE_PATTERN = "mt:dao:playoffs:*"


# Load environment variables with environment-specific support
def load_environment():
    """Load environment variables based on APP_ENV or default to local."""
    # First load base .env file
    load_dotenv()

    # Determine which environment to use
    app_env = os.getenv("APP_ENV", "local")  # Default to local

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
        key_type = "SERVICE_KEY" if service_key and self.key == service_key else "ANON_KEY"
        logger.info(f"DEBUG SupabaseConnection: key_type={key_type}, service_key_present={bool(service_key)}")

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


class MatchDAO(BaseDAO):
    """Data Access Object for match and league data using normalized schema."""

    # === Core Match Methods ===

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
                    "scheduled_kickoff": match.get("scheduled_kickoff"),
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
        self, home_team_id: int, away_team_id: int, match_date: str, age_group_id: int | None = None
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
                    "scheduled_kickoff": match.get("scheduled_kickoff"),
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

    @invalidates_cache(MATCHES_CACHE_PATTERN)
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
                .update(
                    {
                        "match_id": external_match_id,
                        "source": "match-scraper",  # Update source to indicate scraper now manages this
                    }
                )
                .eq("id", match_id)
                .execute()
            )

            if response.data:
                logger.info(
                    "Updated match with external match_id",
                    match_id=match_id,
                    external_match_id=external_match_id,
                )
                return True
            return False

        except Exception:
            logger.exception("Error updating match external_id")
            return False

    @invalidates_cache(MATCHES_CACHE_PATTERN)
    def create_match(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        season_id: int,
        home_score: int | None = None,
        away_score: int | None = None,
        match_status: str = "scheduled",
        source: str = "manual",
        match_id: str | None = None,
        age_group_id: int = 1,
        division_id: int | None = None,
        match_time: str | None = None,
    ) -> int | None:
        """Create a new match with pre-resolved IDs.

        Callers are responsible for resolving names to IDs before calling this
        method. The Celery task and API layer both do this already.

        Args:
            home_team_id: Database ID of home team
            away_team_id: Database ID of away team
            match_date: ISO format date string
            season_id: Database ID of season
            home_score: Home team score (optional)
            away_score: Away team score (optional)
            match_status: Match status (scheduled, live, completed, etc.)
            source: Data source (default: "manual", use "match-scraper" for external)
            match_id: External match ID for deduplication (optional)
            age_group_id: Database ID of age group (default: 1)
            division_id: Database ID of division (optional)

        Returns:
            Created match ID, or None on failure
        """
        try:
            # Validate division for match-scraper sourced matches
            if source == "match-scraper" and division_id is None:
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
            if match_time:
                data["match_time"] = match_time

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
                    match for match in response.data if match.get("match_type", {}).get("name") == match_type
                ]

            # Flatten the response for easier use
            matches = []
            for match in filtered_matches:
                flat_match = {
                    "id": match["id"],
                    "match_date": match["match_date"],
                    "scheduled_kickoff": match.get("scheduled_kickoff"),
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
                    "league_id": match["division"]["league_id"] if match.get("division") else None,
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

    def get_matches_by_team(
        self, team_id: int, season_id: int | None = None, age_group_id: int | None = None
    ) -> list[dict]:
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
                    "scheduled_kickoff": match.get("scheduled_kickoff"),
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

    @invalidates_cache(MATCHES_CACHE_PATTERN)
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
        scheduled_kickoff: str | None = None,
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
            if scheduled_kickoff:
                data["scheduled_kickoff"] = scheduled_kickoff

            response = self.client.table("matches").insert(data).execute()

            return bool(response.data)

        except APIError as e:
            error_dict = e.args[0] if e.args else {}
            if error_dict.get("code") == "23505":
                # Duplicate key violation
                logger.warning(
                    "Duplicate match detected",
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    match_date=match_date,
                    details=error_dict.get("details"),
                )
                raise DuplicateRecordError(
                    message="A match with these teams on this date already exists",
                    details=error_dict.get("details"),
                ) from e
            logger.exception("Error adding match")
            return False
        except Exception:
            logger.exception("Error adding match")
            return False

    @invalidates_cache(MATCHES_CACHE_PATTERN)
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

    @invalidates_cache(MATCHES_CACHE_PATTERN, PLAYOFF_CACHE_PATTERN)
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
        scheduled_kickoff: str | None = None,
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
            if scheduled_kickoff is not None:  # Allow explicit None to clear scheduled_kickoff
                data["scheduled_kickoff"] = scheduled_kickoff

            # Execute update
            response = self.client.table("matches").update(data).eq("id", match_id).execute()

            # Check if update actually affected any rows
            if not response.data or len(response.data) == 0:
                logger.warning("Update match failed - no rows affected", match_id=match_id)
                # Return None to signal failure
                return None

            # Clear cache BEFORE re-fetch to avoid returning stale cached data.
            # The @invalidates_cache decorator clears AFTER the function returns,
            # but get_match_by_id uses @dao_cache and would hit stale cache.
            clear_cache(MATCHES_CACHE_PATTERN)
            clear_cache(PLAYOFF_CACHE_PATTERN)

            # Get the updated match to return with full relations
            return self.get_match_by_id(match_id)

        except Exception:
            logger.exception("Error updating match")
            return None

    @dao_cache("matches:by_id:{match_id}")
    def get_match_by_id(self, match_id: int) -> dict | None:
        """Get a single match by ID with all related data."""
        try:
            response = (
                self.client.table("matches")
                .select("""
                    *,
                    home_team:teams!matches_home_team_id_fkey(
                        id, name,
                        club:clubs(id, name, logo_url, primary_color, secondary_color),
                        division:divisions(id, leagues(sport_type))
                    ),
                    away_team:teams!matches_away_team_id_fkey(
                        id, name,
                        club:clubs(id, name, logo_url, primary_color, secondary_color)
                    ),
                    season:seasons(id, name),
                    age_group:age_groups(id, name),
                    match_type:match_types(id, name),
                    division:divisions(id, name, leagues(id, name, sport_type))
                """)
                .eq("id", match_id)
                .execute()
            )

            if response.data and len(response.data) > 0:
                match = response.data[0]
                # Extract sport_type from division -> leagues (match division)
                division = match.get("division") or {}
                league = division.get("leagues") or {}
                sport_type = league.get("sport_type")

                # Fallback: get sport_type from home team's division -> league
                if not sport_type:
                    home_team = match.get("home_team") or {}
                    team_div = home_team.get("division") or {}
                    team_league = team_div.get("leagues") or {}
                    sport_type = team_league.get("sport_type", "soccer")

                # Flatten the response to match the format from get_all_matches
                flat_match = {
                    "id": match["id"],
                    "match_date": match["match_date"],
                    "scheduled_kickoff": match.get("scheduled_kickoff"),
                    "home_team_id": match["home_team_id"],
                    "away_team_id": match["away_team_id"],
                    "home_team_name": match["home_team"]["name"] if match.get("home_team") else "Unknown",
                    "away_team_name": match["away_team"]["name"] if match.get("away_team") else "Unknown",
                    "home_team_club": match["home_team"].get("club") if match.get("home_team") else None,
                    "away_team_club": match["away_team"].get("club") if match.get("away_team") else None,
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
                    "division": match.get("division"),  # Include full division object with leagues
                    "sport_type": sport_type,
                    "match_status": match.get("match_status"),
                    "created_by": match.get("created_by"),
                    "updated_by": match.get("updated_by"),
                    "source": match.get("source", "manual"),
                    "match_id": match.get("match_id"),  # External match identifier
                    "created_at": match["created_at"],
                    "updated_at": match["updated_at"],
                    # Live match clock fields
                    "kickoff_time": match.get("kickoff_time"),
                    "halftime_start": match.get("halftime_start"),
                    "second_half_start": match.get("second_half_start"),
                    "match_end_time": match.get("match_end_time"),
                    "half_duration": match.get("half_duration", 45),
                }
                return flat_match
            else:
                return None

        except Exception:
            logger.exception("Error retrieving match by ID")
            return None

    @invalidates_cache(MATCHES_CACHE_PATTERN)
    def delete_match(self, match_id: int) -> bool:
        """Delete a match."""
        try:
            self.client.table("matches").delete().eq("id", match_id).execute()

            return True  # Supabase delete returns empty data even on success

        except Exception:
            logger.exception("Error deleting match")
            return False

    @dao_cache("matches:table:{season_id}:{age_group_id}:{division_id}:{match_type}")
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
            logger.info(
                "generating league table from database",
                season_id=season_id,
                age_group_id=age_group_id,
                division_id=division_id,
                match_type=match_type,
            )
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
        logger.info(
            "fetching matches for standings calculation from database",
            season_id=season_id,
            age_group_id=age_group_id,
            division_id=division_id,
        )
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

    # === Live Match Methods ===

    def get_live_matches(self) -> list[dict]:
        """Get all matches with status 'live'.

        Returns minimal data for the LIVE tab polling.
        """
        try:
            response = (
                self.client.table("matches")
                .select("""
                    id,
                    match_status,
                    match_date,
                    home_score,
                    away_score,
                    kickoff_time,
                    home_team:teams!matches_home_team_id_fkey(id, name),
                    away_team:teams!matches_away_team_id_fkey(id, name)
                """)
                .eq("match_status", "live")
                .execute()
            )

            # Flatten the response
            result = []
            for match in response.data or []:
                result.append(
                    {
                        "match_id": match["id"],
                        "match_status": match["match_status"],
                        "match_date": match["match_date"],
                        "home_score": match["home_score"],
                        "away_score": match["away_score"],
                        "kickoff_time": match.get("kickoff_time"),
                        "home_team_name": match["home_team"]["name"] if match.get("home_team") else "Unknown",
                        "away_team_name": match["away_team"]["name"] if match.get("away_team") else "Unknown",
                    }
                )
            return result

        except Exception:
            logger.exception("Error getting live matches")
            return []

    def get_live_match_state(self, match_id: int) -> dict | None:
        """Get full live match state including clock timestamps.

        Returns match data with clock fields for the live match view.
        """
        try:
            response = (
                self.client.table("matches")
                .select("""
                    *,
                    home_team:teams!matches_home_team_id_fkey(
                        id, name,
                        club:clubs(id, logo_url),
                        division:divisions(id, leagues(sport_type))
                    ),
                    away_team:teams!matches_away_team_id_fkey(id, name, club:clubs(id, logo_url)),
                    age_group:age_groups(id, name),
                    match_type:match_types(id, name),
                    division:divisions(id, name, leagues(id, name, sport_type))
                """)
                .eq("id", match_id)
                .single()
                .execute()
            )

            if not response.data:
                return None

            match = response.data
            # Extract club logo URLs from nested team -> club relationships
            home_team = match.get("home_team") or {}
            away_team = match.get("away_team") or {}
            home_club = home_team.get("club") or {}
            away_club = away_team.get("club") or {}

            # Extract sport_type from division -> leagues
            division = match.get("division") or {}
            league = division.get("leagues") or {}
            sport_type = league.get("sport_type")

            # Fallback: get sport_type from home team's division -> league
            if not sport_type:
                team_div = home_team.get("division") or {}
                team_league = team_div.get("leagues") or {}
                sport_type = team_league.get("sport_type", "soccer")

            return {
                "match_id": match["id"],
                "match_status": match.get("match_status"),
                "match_date": match["match_date"],
                "scheduled_kickoff": match.get("scheduled_kickoff"),
                "home_score": match["home_score"],
                "away_score": match["away_score"],
                "kickoff_time": match.get("kickoff_time"),
                "halftime_start": match.get("halftime_start"),
                "second_half_start": match.get("second_half_start"),
                "match_end_time": match.get("match_end_time"),
                "half_duration": match.get("half_duration", 45),
                "season_id": match.get("season_id"),
                "home_team_id": match["home_team_id"],
                "home_team_name": home_team.get("name", "Unknown"),
                "home_team_logo": home_club.get("logo_url"),
                "away_team_id": match["away_team_id"],
                "away_team_name": away_team.get("name", "Unknown"),
                "away_team_logo": away_club.get("logo_url"),
                "age_group_name": match["age_group"]["name"] if match.get("age_group") else None,
                "match_type_name": match["match_type"]["name"] if match.get("match_type") else None,
                "division_name": match["division"]["name"] if match.get("division") else None,
                "sport_type": sport_type,
            }

        except Exception:
            logger.exception("Error getting live match state", match_id=match_id)
            return None

    @invalidates_cache(MATCHES_CACHE_PATTERN)
    def update_match_clock(
        self,
        match_id: int,
        action: str,
        updated_by: str | None = None,
        half_duration: int | None = None,
    ) -> dict | None:
        """Update match clock based on action.

        Args:
            match_id: The match to update
            action: Clock action - 'start_first_half', 'start_halftime',
                    'start_second_half', 'end_match'
            updated_by: UUID of user performing the action
            half_duration: Duration of each half in minutes (only for start_first_half)

        Returns:
            Updated match state or None on error
        """
        from datetime import datetime

        try:
            now = datetime.now(UTC).isoformat()
            data: dict = {"updated_by": updated_by} if updated_by else {}

            if action == "start_first_half":
                # Start the match - set kickoff time and status to live
                data["kickoff_time"] = now
                data["match_status"] = "live"
                # Set half duration if provided (default is 45)
                if half_duration:
                    data["half_duration"] = half_duration
            elif action == "start_halftime":
                # Mark halftime started
                data["halftime_start"] = now
            elif action == "start_second_half":
                # Start second half
                data["second_half_start"] = now
            elif action == "end_match":
                # End the match
                data["match_end_time"] = now
                data["match_status"] = "completed"
            else:
                logger.warning("Invalid clock action", action=action)
                return None

            response = self.client.table("matches").update(data).eq("id", match_id).execute()

            if not response.data:
                logger.warning("Clock update failed - no rows affected", match_id=match_id)
                return None

            logger.info(
                "match_clock_updated",
                match_id=match_id,
                action=action,
            )

            # Return updated state
            return self.get_live_match_state(match_id)

        except Exception:
            logger.exception("Error updating match clock", match_id=match_id, action=action)
            return None

    @invalidates_cache(MATCHES_CACHE_PATTERN)
    def update_match_score(
        self,
        match_id: int,
        home_score: int,
        away_score: int,
        updated_by: str | None = None,
    ) -> dict | None:
        """Update match score (used when posting a goal).

        Args:
            match_id: The match to update
            home_score: New home team score
            away_score: New away team score
            updated_by: UUID of user performing the action

        Returns:
            Updated match state or None on error
        """
        try:
            data = {
                "home_score": home_score,
                "away_score": away_score,
            }
            if updated_by:
                data["updated_by"] = updated_by

            response = self.client.table("matches").update(data).eq("id", match_id).execute()

            if not response.data:
                logger.warning("Score update failed - no rows affected", match_id=match_id)
                return None

            logger.info(
                "match_score_updated",
                match_id=match_id,
                home_score=home_score,
                away_score=away_score,
            )

            return self.get_live_match_state(match_id)

        except Exception:
            logger.exception("Error updating match score", match_id=match_id)
            return None

    # Admin CRUD methods for reference data have been moved to:
    # - SeasonDAO (seasons, age_groups)
    # - LeagueDAO (leagues, divisions)
    # - MatchTypeDAO (match_types)
    # Team methods moved to TeamDAO - see dao/team_dao.py
    # Club methods moved to ClubDAO - see dao/club_dao.py
    # User profile and player methods moved to PlayerDAO - see dao/player_dao.py

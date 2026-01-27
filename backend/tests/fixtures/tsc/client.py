"""
TSC Client Wrapper.

Wraps MissingTableClient with TSC-specific entity tracking and helper methods.
Provides idempotent "get or create" operations for all entities.
"""

import logging
from typing import Any

from api_client import MissingTableClient
from api_client.exceptions import APIError
from api_client.models import (
    AgeGroupCreate,
    BulkRosterCreate,
    BulkRosterPlayer,
    DivisionCreate,
    EnhancedGame,
    GamePatch,
    GoalEvent,
    RosterPlayerCreate,
    SeasonCreate,
    Team,
)

from .config import TSCConfig
from .entities import EntityRegistry

logger = logging.getLogger(__name__)


class TSCClient:
    """
    TSC-specific API client wrapper.

    Wraps MissingTableClient with:
    - Automatic entity tracking for cleanup
    - TSC-specific helper methods
    - Prefix management from config
    """

    def __init__(self, config: TSCConfig, registry: EntityRegistry | None = None):
        """
        Initialize TSC client.

        Args:
            config: TSC configuration with prefixes and names
            registry: Entity registry for tracking (creates new if None)
        """
        self.config = config
        self.registry = registry or EntityRegistry()
        self._client = MissingTableClient(base_url=config.base_url)

    def __enter__(self) -> "TSCClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    @property
    def client(self) -> MissingTableClient:
        """Access the underlying API client."""
        return self._client

    # Authentication

    def login(self, username: str, password: str) -> dict[str, Any]:
        """Login and return session data."""
        return self._client.login(username, password)

    def login_admin(self) -> dict[str, Any]:
        """Login as the TSC admin user."""
        return self.login(self.config.full_admin_username, self.config.admin_password)

    def login_club_manager(self) -> dict[str, Any]:
        """Login as the TSC club manager."""
        return self.login(self.config.full_club_manager_username, self.config.club_manager_password)

    def login_team_manager(self) -> dict[str, Any]:
        """Login as the TSC team manager."""
        return self.login(self.config.full_team_manager_username, self.config.team_manager_password)

    def login_player(self) -> dict[str, Any]:
        """Login as the TSC player."""
        return self.login(self.config.full_player_username, self.config.player_password)

    def login_club_fan(self) -> dict[str, Any]:
        """Login as the TSC club fan."""
        return self.login(self.config.full_club_fan_username, self.config.club_fan_password)

    def login_team_fan(self) -> dict[str, Any]:
        """Login as the TSC team fan."""
        return self.login(self.config.full_team_fan_username, self.config.team_fan_password)

    def signup_with_invite(
        self,
        username: str,
        password: str,
        invite_code: str,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Sign up a new user with an invite code (idempotent - handles existing users)."""
        try:
            result = self._client.signup(
                username=username,
                password=password,
                display_name=display_name or username,
                invite_code=invite_code,
            )
            logger.info(f"Signed up user: {username}")
            # Track user if ID is returned
            if "user" in result and result["user"].get("id"):
                self.registry.add_user(result["user"]["id"])
            return result
        except (APIError, Exception) as e:
            error_str = str(e).lower()
            # If user already exists, try to login instead
            if "already" in error_str or "exists" in error_str or "registered" in error_str or "duplicate" in error_str:
                logger.info(f"User already exists, logging in: {username}")
                # Login and return a similar structure
                login_result = self._client.login(username, password)
                # Get profile to return user info
                profile = self._client.get_profile()
                return {
                    "user": profile,
                    "session": login_result,
                    "already_existed": True,
                }
            raise

    def get_profile(self) -> dict[str, Any]:
        """Get current user profile."""
        return self._client.get_profile()

    def update_profile(self, display_name: str | None = None, team_id: int | None = None) -> dict[str, Any]:
        """Update current user profile."""
        return self._client.update_profile(display_name=display_name, team_id=team_id)

    # Reference Data Creation (with tracking) - Idempotent get-or-create

    def _find_by_name(self, items: list[dict], name: str) -> dict | None:
        """Find an item by name in a list."""
        for item in items:
            if item.get("name") == name:
                return item
        return None

    def create_season(
        self, name: str | None = None, start_date: str = "2025-01-01", end_date: str = "2025-12-31"
    ) -> dict[str, Any]:
        """Create a season or return existing one if it exists (idempotent)."""
        season_name = name or self.config.full_season_name

        # Check if already exists
        existing = self._find_by_name(self._client.get_seasons(), season_name)
        if existing:
            logger.info(f"Season already exists: {season_name} (ID: {existing['id']})")
            self.registry.season_id = existing["id"]
            return existing

        # Try to create
        try:
            season = SeasonCreate(name=season_name, start_date=start_date, end_date=end_date)
            result = self._client.create_season(season)
            logger.info(f"Created season: {season_name} (ID: {result['id']})")
            self.registry.season_id = result["id"]
            return result
        except (APIError, Exception) as e:
            # On duplicate error, look up existing
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                existing = self._find_by_name(self._client.get_seasons(), season_name)
                if existing:
                    logger.info(f"Season exists (found after error): {season_name} (ID: {existing['id']})")
                    self.registry.season_id = existing["id"]
                    return existing
            raise

    def create_age_group(self, name: str | None = None) -> dict[str, Any]:
        """Create an age group or return existing one if it exists (idempotent)."""
        ag_name = name or self.config.full_age_group_name

        # Check if already exists
        existing = self._find_by_name(self._client.get_age_groups(), ag_name)
        if existing:
            logger.info(f"Age group already exists: {ag_name} (ID: {existing['id']})")
            self.registry.age_group_id = existing["id"]
            return existing

        # Try to create
        try:
            age_group = AgeGroupCreate(name=ag_name)
            result = self._client.create_age_group(age_group)
            logger.info(f"Created age group: {ag_name} (ID: {result['id']})")
            self.registry.age_group_id = result["id"]
            return result
        except (APIError, Exception) as e:
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                existing = self._find_by_name(self._client.get_age_groups(), ag_name)
                if existing:
                    logger.info(f"Age group exists (found after error): {ag_name} (ID: {existing['id']})")
                    self.registry.age_group_id = existing["id"]
                    return existing
            raise

    def create_league(self, name: str | None = None, description: str | None = None) -> dict[str, Any]:
        """Create a league or return existing one if it exists (idempotent)."""
        league_name = name or self.config.prefixed("league")

        # Check if already exists
        existing = self._find_by_name(self._client.get_leagues(), league_name)
        if existing:
            logger.info(f"League already exists: {league_name} (ID: {existing['id']})")
            self.registry.league_id = existing["id"]
            return existing

        # Try to create
        try:
            result = self._client.create_league(name=league_name, description=description)
            logger.info(f"Created league: {league_name} (ID: {result['id']})")
            self.registry.league_id = result["id"]
            return result
        except (APIError, Exception) as e:
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                existing = self._find_by_name(self._client.get_leagues(), league_name)
                if existing:
                    logger.info(f"League exists (found after error): {league_name} (ID: {existing['id']})")
                    self.registry.league_id = existing["id"]
                    return existing
            raise

    def create_division(
        self, name: str | None = None, league_id: int | None = None, description: str | None = None
    ) -> dict[str, Any]:
        """Create a division or return existing one if it exists (idempotent)."""
        div_name = name or self.config.full_division_name
        # Use tracked league_id if not provided
        lid = league_id or self.registry.league_id
        if lid is None:
            raise ValueError("league_id is required for division creation - create a league first")

        # Check if already exists
        existing = self._find_by_name(self._client.get_divisions(), div_name)
        if existing:
            logger.info(f"Division already exists: {div_name} (ID: {existing['id']})")
            self.registry.division_id = existing["id"]
            return existing

        # Try to create
        try:
            division = DivisionCreate(name=div_name, league_id=lid, description=description)
            result = self._client.create_division(division)
            logger.info(f"Created division: {div_name} (ID: {result['id']})")
            self.registry.division_id = result["id"]
            return result
        except (APIError, Exception) as e:
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                existing = self._find_by_name(self._client.get_divisions(), div_name)
                if existing:
                    logger.info(f"Division exists (found after error): {div_name} (ID: {existing['id']})")
                    self.registry.division_id = existing["id"]
                    return existing
            raise

    # Club and Team Creation (with tracking) - Idempotent get-or-create

    def _find_club_by_name(self, name: str) -> dict | None:
        """Find a club by name."""
        try:
            clubs = self._client.get_clubs()
            for club in clubs:
                if club.get("name") == name:
                    return club
        except Exception:
            pass
        return None

    def _find_team_by_name(self, name: str) -> dict | None:
        """Find a team by name."""
        try:
            teams = self._client.get_teams()
            for team in teams:
                if team.get("name") == name:
                    return team
        except Exception:
            pass
        return None

    def create_club(self, name: str | None = None, city: str = "Test City") -> dict[str, Any]:
        """Create a club or return existing one if it exists (idempotent)."""
        club_name = name or self.config.full_club_name

        # Check if already exists
        existing = self._find_club_by_name(club_name)
        if existing:
            logger.info(f"Club already exists: {club_name} (ID: {existing['id']})")
            self.registry.club_id = existing["id"]
            return existing

        # Try to create
        try:
            result = self._client.create_club(name=club_name, city=city)
            logger.info(f"Created club: {club_name} (ID: {result['id']})")
            self.registry.club_id = result["id"]
            return result
        except (APIError, Exception) as e:
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                existing = self._find_club_by_name(club_name)
                if existing:
                    logger.info(f"Club exists (found after error): {club_name} (ID: {existing['id']})")
                    self.registry.club_id = existing["id"]
                    return existing
            raise

    def create_premier_team(self, name: str | None = None, city: str = "Test City") -> dict[str, Any]:
        """Create the premier team or return existing one if it exists (idempotent)."""
        team_name = name or self.config.full_premier_team_name

        # Check if already exists
        existing = self._find_team_by_name(team_name)
        if existing:
            logger.info(f"Premier team already exists: {team_name} (ID: {existing['id']})")
            self.registry.premier_team_id = existing["id"]
            return existing

        # Try to create
        try:
            if not self.registry.division_id:
                raise ValueError("division_id is required for team creation - create a division first")
            team = Team(
                name=team_name,
                city=city,
                age_group_ids=[self.registry.age_group_id] if self.registry.age_group_id else [],
                division_id=self.registry.division_id,
            )
            self._client.create_team(team)

            # API only returns {"message": "..."}, so look up the team we just created
            created_team = self._find_team_by_name(team_name)
            if created_team:
                logger.info(f"Created premier team: {team_name} (ID: {created_team['id']})")
                self.registry.premier_team_id = created_team["id"]
                return created_team
            else:
                logger.warning(f"Created premier team but couldn't find it: {team_name}")
                return {"name": team_name, "message": "Team created but ID not available"}
        except (APIError, Exception) as e:
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                existing = self._find_team_by_name(team_name)
                if existing:
                    logger.info(f"Premier team exists (found after error): {team_name} (ID: {existing['id']})")
                    self.registry.premier_team_id = existing["id"]
                    return existing
            raise

    def create_reserve_team(self, name: str | None = None, city: str = "Test City") -> dict[str, Any]:
        """Create the reserve team or return existing one if it exists (idempotent)."""
        team_name = name or self.config.full_reserve_team_name

        # Check if already exists
        existing = self._find_team_by_name(team_name)
        if existing:
            logger.info(f"Reserve team already exists: {team_name} (ID: {existing['id']})")
            self.registry.reserve_team_id = existing["id"]
            return existing

        # Try to create
        try:
            if not self.registry.division_id:
                raise ValueError("division_id is required for team creation - create a division first")
            team = Team(
                name=team_name,
                city=city,
                age_group_ids=[self.registry.age_group_id] if self.registry.age_group_id else [],
                division_id=self.registry.division_id,
            )
            self._client.create_team(team)

            # API only returns {"message": "..."}, so look up the team we just created
            created_team = self._find_team_by_name(team_name)
            if created_team:
                logger.info(f"Created reserve team: {team_name} (ID: {created_team['id']})")
                self.registry.reserve_team_id = created_team["id"]
                return created_team
            else:
                logger.warning(f"Created reserve team but couldn't find it: {team_name}")
                return {"name": team_name, "message": "Team created but ID not available"}
        except (APIError, Exception) as e:
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                existing = self._find_team_by_name(team_name)
                if existing:
                    logger.info(f"Reserve team exists (found after error): {team_name} (ID: {existing['id']})")
                    self.registry.reserve_team_id = existing["id"]
                    return existing
            raise

    def create_team(self, name: str, city: str = "Test City") -> dict[str, Any]:
        """Create an additional team or return existing one if it exists (idempotent)."""
        # Check if already exists
        existing = self._find_team_by_name(name)
        if existing:
            logger.info(f"Team already exists: {name} (ID: {existing['id']})")
            self.registry.add_team(existing["id"])
            return existing

        # Try to create
        try:
            if not self.registry.division_id:
                raise ValueError("division_id is required for team creation - create a division first")
            team = Team(
                name=name,
                city=city,
                age_group_ids=[self.registry.age_group_id] if self.registry.age_group_id else [],
                division_id=self.registry.division_id,
            )
            self._client.create_team(team)

            # API only returns {"message": "..."}, so look up the team we just created
            created_team = self._find_team_by_name(name)
            if created_team:
                logger.info(f"Created team: {name} (ID: {created_team['id']})")
                self.registry.add_team(created_team["id"])
                return created_team
            else:
                logger.warning(f"Created team but couldn't find it: {name}")
                return {"name": name, "message": "Team created but ID not available"}
        except (APIError, Exception) as e:
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                existing = self._find_team_by_name(name)
                if existing:
                    logger.info(f"Team exists (found after error): {name} (ID: {existing['id']})")
                    self.registry.add_team(existing["id"])
                    return existing
            raise

    # Match Creation (with tracking) - Idempotent get-or-create

    def _find_match(self, home_team_id: int, away_team_id: int, match_date: str) -> dict | None:
        """Find an existing match by teams and date."""
        try:
            matches = self._client.get_games(
                season_id=self.registry.season_id,
                age_group_id=self.registry.age_group_id,
            )
            for match in matches:
                if (
                    match.get("home_team_id") == home_team_id
                    and match.get("away_team_id") == away_team_id
                    and match.get("match_date") == match_date
                ):
                    return match
        except Exception:
            pass
        return None

    def create_match(
        self,
        home_team_id: int,
        away_team_id: int,
        game_date: str,
        home_score: int = 0,
        away_score: int = 0,
        status: str = "scheduled",
    ) -> dict[str, Any]:
        """Create a match or return existing one if it exists (idempotent)."""
        if not self.registry.season_id or not self.registry.age_group_id:
            raise ValueError("Season and age group must be created first")

        # Check if match already exists
        existing = self._find_match(home_team_id, away_team_id, game_date)
        if existing:
            logger.info(f"Match already exists: {home_team_id} vs {away_team_id} on {game_date} (ID: {existing['id']})")
            self.registry.add_match(existing["id"])
            return existing

        # Create new match
        game = EnhancedGame(
            match_date=game_date,  # API expects match_date
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_score=home_score,
            away_score=away_score,
            season_id=self.registry.season_id,
            age_group_id=self.registry.age_group_id,
            match_type_id=1,  # Default match type (API expects match_type_id)
            division_id=self.registry.division_id,
            status=status,
        )
        result = self._client.create_game(game)

        # API only returns {"message": "..."}, so look up the match we just created
        created_match = self._find_match(home_team_id, away_team_id, game_date)
        if created_match:
            logger.info(f"Created match: {home_team_id} vs {away_team_id} on {game_date} (ID: {created_match['id']})")
            self.registry.add_match(created_match["id"])
            return created_match
        else:
            # Return API response if we can't find the match (shouldn't happen)
            logger.warning(f"Created match but couldn't find it: {home_team_id} vs {away_team_id} on {game_date}")
            return result

    def update_match_score(
        self, match_id: int, home_score: int, away_score: int, match_status: str = "completed"
    ) -> dict[str, Any]:
        """Update match score and status."""
        patch = GamePatch(home_score=home_score, away_score=away_score, match_status=match_status)
        return self._client.patch_game(match_id, patch)

    def set_match_live(self, match_id: int) -> dict[str, Any]:
        """Set a match status to live."""
        patch = GamePatch(match_status="live")
        return self._client.patch_game(match_id, patch)

    # Invite Creation (with tracking)

    def create_club_manager_invite(self, email: str | None = None) -> dict[str, Any]:
        """Create a club manager invite and track it."""
        if not self.registry.club_id:
            raise ValueError("Club must be created first")
        result = self._client.create_club_manager_invite(self.registry.club_id, email)
        self.registry.add_invite(result["id"], result["invite_code"], "club_manager")
        return result

    def create_team_manager_invite(self, team_id: int | None = None, email: str | None = None) -> dict[str, Any]:
        """Create a team manager invite and track it."""
        if not self.registry.age_group_id:
            raise ValueError("Age group must be created first")
        tid = team_id or self.registry.premier_team_id
        if not tid:
            raise ValueError("Team ID required")
        result = self._client.create_team_manager_invite(tid, self.registry.age_group_id, email)
        self.registry.add_invite(result["id"], result["invite_code"], "team_manager")
        return result

    def create_club_fan_invite(self, email: str | None = None) -> dict[str, Any]:
        """Create a club fan invite and track it (club manager endpoint)."""
        if not self.registry.club_id:
            raise ValueError("Club must be created first")
        result = self._client.create_club_fan_invite(self.registry.club_id, email)
        self.registry.add_invite(result["id"], result["invite_code"], "club_fan")
        return result

    def create_team_player_invite(self, team_id: int | None = None, email: str | None = None) -> dict[str, Any]:
        """Create a team player invite and track it (team manager endpoint)."""
        if not self.registry.age_group_id:
            raise ValueError("Age group must be created first")
        tid = team_id or self.registry.premier_team_id
        if not tid:
            raise ValueError("Team ID required")
        result = self._client.create_team_player_invite(tid, self.registry.age_group_id, email)
        self.registry.add_invite(result["id"], result["invite_code"], "team_player")
        return result

    def create_team_fan_invite(self, team_id: int | None = None, email: str | None = None) -> dict[str, Any]:
        """Create a team fan invite and track it (team manager endpoint)."""
        if not self.registry.age_group_id:
            raise ValueError("Age group must be created first")
        tid = team_id or self.registry.premier_team_id
        if not tid:
            raise ValueError("Team ID required")
        result = self._client.create_team_fan_invite(tid, self.registry.age_group_id, email)
        self.registry.add_invite(result["id"], result["invite_code"], "team_fan")
        return result

    def create_team_player_invite_admin(self, team_id: int | None = None, email: str | None = None) -> dict[str, Any]:
        """Create a team player invite and track it (admin endpoint)."""
        if not self.registry.age_group_id:
            raise ValueError("Age group must be created first")
        tid = team_id or self.registry.premier_team_id
        if not tid:
            raise ValueError("Team ID required")
        result = self._client.create_team_player_invite_admin(tid, self.registry.age_group_id, email)
        self.registry.add_invite(result["id"], result["invite_code"], "team_player")
        return result

    def create_team_fan_invite_admin(self, team_id: int | None = None, email: str | None = None) -> dict[str, Any]:
        """Create a team fan invite and track it (admin endpoint)."""
        if not self.registry.age_group_id:
            raise ValueError("Age group must be created first")
        tid = team_id or self.registry.premier_team_id
        if not tid:
            raise ValueError("Team ID required")
        result = self._client.create_team_fan_invite_admin(tid, self.registry.age_group_id, email)
        self.registry.add_invite(result["id"], result["invite_code"], "team_fan")
        return result

    def validate_invite(self, invite_code: str) -> dict[str, Any]:
        """Validate an invite code."""
        return self._client.validate_invite(invite_code)

    # Roster Management (with tracking)

    def create_roster_entry(
        self,
        team_id: int,
        jersey_number: int,
        first_name: str | None = None,
        last_name: str | None = None,
        season_id: int | None = None,
    ) -> dict[str, Any]:
        """Create a roster entry and track it."""
        sid = season_id or self.registry.season_id
        if not sid:
            raise ValueError("Season ID required - create a season first")
        entry = RosterPlayerCreate(
            jersey_number=jersey_number,
            first_name=first_name,
            last_name=last_name,
            season_id=sid,
        )
        result = self._client.create_roster_entry(team_id, entry)
        # API returns {"success": True, "player": {...}}
        player = result.get("player", result)
        self.registry.add_roster_entry(player["id"], team_id, jersey_number)
        logger.info(f"Created roster entry: #{jersey_number} on team {team_id}")
        return player

    def bulk_create_roster(
        self,
        team_id: int,
        players: list[dict[str, Any]],
        season_id: int | None = None,
    ) -> dict[str, Any]:
        """Bulk create roster entries and track them."""
        sid = season_id or self.registry.season_id
        if not sid:
            raise ValueError("Season ID required - create a season first")
        bulk = BulkRosterCreate(
            season_id=sid,
            players=[BulkRosterPlayer(**p) for p in players],
        )
        result = self._client.bulk_create_roster(team_id, bulk)
        for entry in result.get("players", []):
            self.registry.add_roster_entry(entry["id"], team_id, entry["jersey_number"])
        logger.info(f"Bulk created {len(result.get('players', []))} roster entries on team {team_id}")
        return result

    def get_roster(self, team_id: int, season_id: int | None = None) -> list[dict[str, Any]]:
        """Get team roster for a season."""
        sid = season_id or self.registry.season_id
        if not sid:
            raise ValueError("Season ID required - create a season first")
        result = self._client.get_team_roster(team_id, season_id=sid)
        # API returns {"success": True, "roster": [...]}
        return result.get("roster", result)

    def create_team_player_invite_with_roster(
        self,
        team_id: int,
        player_id: int,
        email: str | None = None,
    ) -> dict[str, Any]:
        """Create player invite linked to roster entry."""
        if not self.registry.age_group_id:
            raise ValueError("Age group must be created first")
        logger.info(
            f"Creating team_player invite with: team_id={team_id}, "
            f"age_group_id={self.registry.age_group_id}, player_id={player_id}"
        )
        result = self._client.create_team_player_invite(
            team_id=team_id,
            age_group_id=self.registry.age_group_id,
            email=email,
            player_id=player_id,
        )
        logger.info(f"Created invite result: team_id={result.get('team_id')}, player_id={result.get('player_id')}")
        self.registry.add_invite(result["id"], result["invite_code"], "team_player")
        logger.info(f"Created roster-linked invite for player {player_id}")
        return result

    # Player Stats

    def get_player_stats(self, player_id: int, season_id: int | None = None) -> dict[str, Any]:
        """Get player stats for a season."""
        sid = season_id or self.registry.season_id
        if not sid:
            raise ValueError("Season ID required - create a season first")
        return self._client.get_roster_player_stats(player_id, season_id=sid)

    def get_team_stats(self, team_id: int, season_id: int | None = None) -> dict[str, Any]:
        """Get team stats for a season."""
        sid = season_id or self.registry.season_id
        if not sid:
            raise ValueError("Season ID required - create a season first")
        return self._client.get_team_stats(team_id, season_id=sid)

    def post_goal_with_player(
        self,
        match_id: int,
        team_id: int,
        player_id: int,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Post a goal with player_id (updates player stats)."""
        goal = GoalEvent(team_id=team_id, player_id=player_id, message=message)
        return self._client.post_goal(match_id, goal)

    # Read Operations (no tracking needed)

    def get_teams(self) -> list[dict[str, Any]]:
        """Get all teams."""
        return self._client.get_teams()

    def get_matches(self, **filters: Any) -> list[dict[str, Any]]:
        """Get matches with optional filters."""
        return self._client.get_games(**filters)

    def get_table(self, **filters: Any) -> list[dict[str, Any]]:
        """Get league standings table."""
        return self._client.get_table(**filters)

    def get_club(self, club_id: int | None = None) -> dict[str, Any]:
        """Get club details."""
        cid = club_id or self.registry.club_id
        if not cid:
            raise ValueError("Club ID required")
        return self._client.get_club(cid)

    def get_club_teams(self, club_id: int | None = None) -> list[dict[str, Any]]:
        """Get teams for a club."""
        cid = club_id or self.registry.club_id
        if not cid:
            raise ValueError("Club ID required")
        return self._client.get_club_teams(cid)

    def get_team_manager_assignments(self) -> list[dict[str, Any]]:
        """Get current user's team manager assignments."""
        return self._client.get_team_manager_assignments()

    def get_clubs(self) -> list[dict[str, Any]]:
        """Get all clubs."""
        return self._client.get_clubs(include_teams=False)

    def get_divisions(self) -> list[dict[str, Any]]:
        """Get all divisions."""
        return self._client.get_divisions()

    def get_leagues(self) -> list[dict[str, Any]]:
        """Get all leagues."""
        return self._client.get_leagues()

    def get_age_groups(self) -> list[dict[str, Any]]:
        """Get all age groups."""
        return self._client.get_age_groups()

    def get_seasons(self) -> list[dict[str, Any]]:
        """Get all seasons."""
        return self._client.get_seasons()

    # Cleanup Operations

    def delete_match(self, match_id: int) -> dict[str, Any]:
        """Delete a match."""
        return self._client.delete_game(match_id)

    def delete_team(self, team_id: int) -> dict[str, Any]:
        """Delete a team."""
        return self._client.delete_team(team_id)

    def delete_club(self, club_id: int) -> dict[str, Any]:
        """Delete a club."""
        return self._client.delete_club(club_id)

    def delete_division(self, division_id: int) -> dict[str, Any]:
        """Delete a division."""
        return self._client.delete_division(division_id)

    def delete_age_group(self, age_group_id: int) -> dict[str, Any]:
        """Delete an age group."""
        return self._client.delete_age_group(age_group_id)

    def delete_season(self, season_id: int) -> dict[str, Any]:
        """Delete a season."""
        return self._client.delete_season(season_id)

    def cancel_invite(self, invite_id: str) -> dict[str, Any]:
        """Cancel a pending invite."""
        return self._client.cancel_invite(invite_id)

    def delete_league(self, league_id: int) -> dict[str, Any]:
        """Delete a league."""
        return self._client.delete_league(league_id)

    # User management (admin only)

    def get_users(self) -> list[dict[str, Any]]:
        """Get all users (admin only)."""
        return self._client.get_users()

    def delete_user(self, user_id: str) -> dict[str, Any]:
        """Delete a user (admin only)."""
        return self._client.delete_user(user_id)

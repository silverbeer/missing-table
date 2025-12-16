"""
TSC Client Wrapper.

Wraps MissingTableClient with TSC-specific entity tracking and helper methods.
"""

from typing import Any

from api_client import MissingTableClient
from api_client.models import (
    AgeGroupCreate,
    DivisionCreate,
    EnhancedGame,
    GamePatch,
    SeasonCreate,
    Team,
)

from .config import TSCConfig
from .entities import EntityRegistry


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
        """Sign up a new user with an invite code."""
        result = self._client.signup(
            username=username,
            password=password,
            display_name=display_name or username,
            invite_code=invite_code,
        )
        # Track user if ID is returned
        if "user" in result and result["user"].get("id"):
            self.registry.add_user(result["user"]["id"])
        return result

    def get_profile(self) -> dict[str, Any]:
        """Get current user profile."""
        return self._client.get_profile()

    def update_profile(self, display_name: str | None = None, team_id: int | None = None) -> dict[str, Any]:
        """Update current user profile."""
        return self._client.update_profile(display_name=display_name, team_id=team_id)

    # Reference Data Creation (with tracking)

    def create_season(self, name: str | None = None, start_date: str = "2025-01-01", end_date: str = "2025-12-31") -> dict[str, Any]:
        """Create a season and track it."""
        season_name = name or self.config.full_season_name
        season = SeasonCreate(name=season_name, start_date=start_date, end_date=end_date)
        result = self._client.create_season(season)
        self.registry.season_id = result["id"]
        return result

    def create_age_group(self, name: str | None = None) -> dict[str, Any]:
        """Create an age group and track it."""
        ag_name = name or self.config.full_age_group_name
        age_group = AgeGroupCreate(name=ag_name)
        result = self._client.create_age_group(age_group)
        self.registry.age_group_id = result["id"]
        return result

    def create_league(self, name: str | None = None, description: str | None = None) -> dict[str, Any]:
        """Create a league and track it."""
        league_name = name or self.config.prefixed("league")
        result = self._client.create_league(name=league_name, description=description)
        self.registry.league_id = result["id"]
        return result

    def create_division(self, name: str | None = None, league_id: int | None = None, description: str | None = None) -> dict[str, Any]:
        """Create a division and track it."""
        div_name = name or self.config.full_division_name
        # Use tracked league_id if not provided
        lid = league_id or self.registry.league_id
        if lid is None:
            raise ValueError("league_id is required for division creation - create a league first")
        division = DivisionCreate(name=div_name, league_id=lid, description=description)
        result = self._client.create_division(division)
        self.registry.division_id = result["id"]
        return result

    # Club and Team Creation (with tracking)

    def create_club(self, name: str | None = None, city: str = "Test City") -> dict[str, Any]:
        """Create a club and track it."""
        club_name = name or self.config.full_club_name
        result = self._client.create_club(name=club_name, city=city)
        self.registry.club_id = result["id"]
        return result

    def create_premier_team(self, name: str | None = None, city: str = "Test City") -> dict[str, Any]:
        """Create the premier team and track it."""
        team_name = name or self.config.full_premier_team_name
        team = Team(
            name=team_name,
            city=city,
            age_group_ids=[self.registry.age_group_id] if self.registry.age_group_id else [],
            division_ids=[self.registry.division_id] if self.registry.division_id else None,
        )
        result = self._client.create_team(team)
        self.registry.premier_team_id = result["id"]
        return result

    def create_reserve_team(self, name: str | None = None, city: str = "Test City") -> dict[str, Any]:
        """Create the reserve team and track it."""
        team_name = name or self.config.full_reserve_team_name
        team = Team(
            name=team_name,
            city=city,
            age_group_ids=[self.registry.age_group_id] if self.registry.age_group_id else [],
            division_ids=[self.registry.division_id] if self.registry.division_id else None,
        )
        result = self._client.create_team(team)
        self.registry.reserve_team_id = result["id"]
        return result

    def create_team(self, name: str, city: str = "Test City") -> dict[str, Any]:
        """Create an additional team and track it."""
        team = Team(
            name=name,
            city=city,
            age_group_ids=[self.registry.age_group_id] if self.registry.age_group_id else [],
            division_ids=[self.registry.division_id] if self.registry.division_id else None,
        )
        result = self._client.create_team(team)
        self.registry.add_team(result["id"])
        return result

    # Match Creation (with tracking)

    def create_match(
        self,
        home_team_id: int,
        away_team_id: int,
        game_date: str,
        home_score: int = 0,
        away_score: int = 0,
        status: str = "scheduled",
    ) -> dict[str, Any]:
        """Create a match and track it."""
        if not self.registry.season_id or not self.registry.age_group_id:
            raise ValueError("Season and age group must be created first")

        game = EnhancedGame(
            game_date=game_date,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_score=home_score,
            away_score=away_score,
            season_id=self.registry.season_id,
            age_group_id=self.registry.age_group_id,
            game_type_id=1,  # Default match type
            division_id=self.registry.division_id,
            status=status,
        )
        result = self._client.create_game(game)
        self.registry.add_match(result["id"])
        return result

    def update_match_score(self, match_id: int, home_score: int, away_score: int, match_status: str = "completed") -> dict[str, Any]:
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

    def validate_invite(self, invite_code: str) -> dict[str, Any]:
        """Validate an invite code."""
        return self._client.validate_invite(invite_code)

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

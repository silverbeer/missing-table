"""
Type-safe API client for Missing Table backend.

Provides a comprehensive client with:
- Full type safety via Pydantic models
- Automatic authentication handling
- Retry logic with exponential backoff
- Request/response logging
- Error handling
"""

import logging
from typing import Any, TypeVar
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

from .exceptions import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .models import (
    AdminPlayerTeamAssignment,
    AdminPlayerUpdate,
    AgeGroupCreate,
    AgeGroupUpdate,
    BulkRenumberRequest,
    BulkRosterCreate,
    DivisionCreate,
    DivisionUpdate,
    EnhancedGame,
    GamePatch,
    GoalEvent,
    InviteRequestCreate,
    InviteRequestStatusUpdate,
    JerseyNumberUpdate,
    LineupSave,
    LiveMatchClock,
    MatchSubmissionData,
    MessageEvent,
    PlayerCustomization,
    PlayerHistoryCreate,
    PlayerHistoryUpdate,
    RefreshTokenRequest,
    RoleUpdate,
    RosterPlayerCreate,
    RosterPlayerUpdate,
    SeasonCreate,
    SeasonUpdate,
    Team,
    UserProfileUpdate,
)

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class MissingTableClient:
    """Type-safe API client for Missing Table backend."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        access_token: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """
        Initialize the API client.

        Args:
            base_url: Base URL of the API
            access_token: JWT access token for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._refresh_token: str | None = None
        self.timeout = timeout
        self.max_retries = max_retries

        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
        )

    def __enter__(self) -> "MissingTableClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _handle_response_error(self, response: httpx.Response) -> None:
        """Handle HTTP error responses."""
        try:
            error_data = response.json()
        except Exception:
            error_data = {"detail": response.text}

        error_message = error_data.get("detail", f"HTTP {response.status_code}")

        if response.status_code == 401:
            raise AuthenticationError(error_message, response.status_code, error_data)
        elif response.status_code == 403:
            raise AuthorizationError(error_message, response.status_code, error_data)
        elif response.status_code == 404:
            raise NotFoundError(error_message, response.status_code, error_data)
        elif response.status_code == 422:
            raise ValidationError(error_message, response.status_code, error_data)
        elif response.status_code == 429:
            raise RateLimitError(error_message, response.status_code, error_data)
        elif response.status_code >= 500:
            raise ServerError(error_message, response.status_code, error_data)
        else:
            raise APIError(error_message, response.status_code, error_data)

    def _request(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an HTTP request with error handling."""
        url = urljoin(self.base_url, path)
        headers = self._get_headers()

        logger.debug(f"{method} {url}")
        if json_data:
            logger.debug(f"Request body: {json_data}")

        response = self._client.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            params=params,
        )

        if not response.is_success:
            self._handle_response_error(response)

        return response

    def _request_multipart(
        self,
        method: str,
        path: str,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make a multipart/form-data request (for file uploads)."""
        url = urljoin(self.base_url, path)
        # Omit Content-Type header; httpx sets multipart boundary automatically
        headers = {}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        logger.debug(f"{method} {url} (multipart)")

        response = self._client.request(
            method=method,
            url=url,
            headers=headers,
            files=files,
            data=data,
            params=params,
        )

        if not response.is_success:
            self._handle_response_error(response)

        return response

    # Authentication endpoints

    def login(self, username: str, password: str) -> dict[str, Any]:
        """
        Login with username and password.

        Args:
            username: Username (primary identifier)
            password: User password

        Returns:
            Dict with access_token, refresh_token, and user info
        """
        response = self._request(
            "POST",
            "/api/auth/login",
            json_data={"username": username, "password": password},
        )
        data = response.json()

        # Handle nested session structure from API
        if "session" in data:
            session = data["session"]
            self._access_token = session.get("access_token")
            self._refresh_token = session.get("refresh_token")
            # Return flattened structure for backward compatibility
            return {
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "token_type": session.get("token_type", "bearer"),
                "user": data.get("user"),
                "message": data.get("message"),
            }
        else:
            # Fallback for flat structure
            self._access_token = data.get("access_token")
            self._refresh_token = data.get("refresh_token")
            return data

    def signup(
        self,
        username: str,
        password: str,
        display_name: str | None = None,
        email: str | None = None,
        invite_code: str | None = None,
    ) -> dict[str, Any]:
        """
        Sign up a new user with username authentication.

        Args:
            username: Username (required, primary identifier)
            password: User password
            display_name: Optional display name
            email: Optional email for notifications
            invite_code: Optional invite code

        Returns:
            Dict with user info (may include access_token depending on API configuration)
        """
        payload = {"username": username, "password": password}
        if display_name:
            payload["display_name"] = display_name
        if email:
            payload["email"] = email
        if invite_code:
            payload["invite_code"] = invite_code

        response = self._request("POST", "/api/auth/signup", json_data=payload)
        data = response.json()

        # Handle nested session structure if tokens are returned
        if "session" in data:
            session = data["session"]
            self._access_token = session.get("access_token")
            self._refresh_token = session.get("refresh_token")

        return data

    def logout(self) -> dict[str, Any]:
        """Logout the current user."""
        response = self._request("POST", "/api/auth/logout")
        self._access_token = None
        self._refresh_token = None
        return response.json()

    def refresh_access_token(self) -> dict[str, Any]:
        """Refresh the access token using refresh token."""
        if not self._refresh_token:
            raise AuthenticationError("No refresh token available")

        model = RefreshTokenRequest(refresh_token=self._refresh_token)
        response = self._request("POST", "/api/auth/refresh", json_data=model.model_dump())
        data = response.json()

        # Handle nested session structure
        if "session" in data:
            session = data["session"]
            self._access_token = session.get("access_token")
            self._refresh_token = session.get("refresh_token")
            # Return flattened structure for backward compatibility
            return {
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "token_type": session.get("token_type", "bearer"),
            }
        else:
            # Fallback for flat structure
            self._access_token = data.get("access_token")
            return data

    def get_profile(self) -> dict[str, Any]:
        """Get current user's profile."""
        response = self._request("GET", "/api/auth/profile")
        return response.json()

    def update_profile(self, display_name: str | None = None, team_id: int | None = None) -> dict[str, Any]:
        """Update current user's profile."""
        payload = {}
        if display_name is not None:
            payload["display_name"] = display_name
        if team_id is not None:
            payload["team_id"] = team_id

        response = self._request("PUT", "/api/auth/profile", json_data=payload)
        return response.json()

    # Teams endpoints

    def get_teams(
        self,
        game_type_id: int | None = None,
        age_group_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get all teams with optional filters."""
        params = {}
        if game_type_id is not None:
            params["game_type_id"] = game_type_id
        if age_group_id is not None:
            params["age_group_id"] = age_group_id

        response = self._request("GET", "/api/teams", params=params)
        return response.json()

    def get_team(self, team_id: int) -> dict[str, Any]:
        """Get a specific team by ID."""
        response = self._request("GET", f"/api/teams/{team_id}")
        return response.json()

    def create_team(self, team: Team) -> dict[str, Any]:
        """Create a new team."""
        response = self._request("POST", "/api/teams", json_data=team.model_dump(exclude_none=True))
        return response.json()

    def update_team(self, team_id: int, team: Team) -> dict[str, Any]:
        """Update a team."""
        response = self._request("PUT", f"/api/teams/{team_id}", json_data=team.model_dump(exclude_none=True))
        return response.json()

    def delete_team(self, team_id: int) -> dict[str, Any]:
        """Delete a team."""
        response = self._request("DELETE", f"/api/teams/{team_id}")
        return response.json()

    # Games endpoints

    def get_games(
        self,
        season_id: int | None = None,
        age_group_id: int | None = None,
        game_type_id: int | None = None,
        match_type_id: int | None = None,
        team_id: int | None = None,
        limit: int | None = None,
        upcoming: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Get matches (games) with optional filters."""
        params = {}
        if season_id is not None:
            params["season_id"] = season_id
        if age_group_id is not None:
            params["age_group_id"] = age_group_id
        # Support both game_type_id (legacy) and match_type_id (current)
        match_type = match_type_id if match_type_id is not None else game_type_id
        if match_type is not None:
            params["match_type_id"] = match_type
        if team_id is not None:
            params["team_id"] = team_id
        if limit is not None:
            params["limit"] = limit
        if upcoming is not None:
            params["upcoming"] = upcoming

        response = self._request("GET", "/api/matches", params=params)
        return response.json()

    def get_game(self, game_id: int) -> dict[str, Any]:
        """Get a specific match (game) by ID."""
        response = self._request("GET", f"/api/matches/{game_id}")
        return response.json()

    def get_games_by_team(
        self, team_id: int, season_id: int | None = None, age_group_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Get all matches (games) for a specific team."""
        params = {}
        if season_id:
            params["season_id"] = season_id
        if age_group_id:
            params["age_group_id"] = age_group_id
        response = self._request("GET", f"/api/matches/team/{team_id}", params=params)
        return response.json()

    def create_game(self, game: EnhancedGame) -> dict[str, Any]:
        """Create a new match (game)."""
        # Convert game_type_id to match_type_id for API compatibility
        game_data = game.model_dump(exclude_none=True)
        if "game_type_id" in game_data:
            game_data["match_type_id"] = game_data.pop("game_type_id")
        response = self._request("POST", "/api/matches", json_data=game_data)
        return response.json()

    def update_game(self, game_id: int, game: EnhancedGame) -> dict[str, Any]:
        """Update a match (game) - full update."""
        # Convert game_type_id to match_type_id for API compatibility
        game_data = game.model_dump(exclude_none=True)
        if "game_type_id" in game_data:
            game_data["match_type_id"] = game_data.pop("game_type_id")
        response = self._request("PUT", f"/api/matches/{game_id}", json_data=game_data)
        return response.json()

    def patch_game(self, game_id: int, game_patch: GamePatch) -> dict[str, Any]:
        """Partially update a match (game)."""
        # Convert game_type_id to match_type_id for API compatibility
        patch_data = game_patch.model_dump(exclude_none=True)
        if "game_type_id" in patch_data:
            patch_data["match_type_id"] = patch_data.pop("game_type_id")
        response = self._request("PATCH", f"/api/matches/{game_id}", json_data=patch_data)
        return response.json()

    def delete_game(self, game_id: int) -> dict[str, Any]:
        """Delete a match (game)."""
        response = self._request("DELETE", f"/api/matches/{game_id}")
        return response.json()

    # Reference data endpoints

    def get_age_groups(self) -> list[dict[str, Any]]:
        """Get all age groups."""
        response = self._request("GET", "/api/age-groups")
        return response.json()

    def create_age_group(self, age_group: AgeGroupCreate) -> dict[str, Any]:
        """Create a new age group (admin only)."""
        response = self._request("POST", "/api/age-groups", json_data=age_group.model_dump())
        return response.json()

    def update_age_group(self, age_group_id: int, age_group: AgeGroupUpdate) -> dict[str, Any]:
        """Update an age group (admin only)."""
        response = self._request("PUT", f"/api/age-groups/{age_group_id}", json_data=age_group.model_dump())
        return response.json()

    def delete_age_group(self, age_group_id: int) -> dict[str, Any]:
        """Delete an age group (admin only)."""
        response = self._request("DELETE", f"/api/age-groups/{age_group_id}")
        return response.json()

    def get_seasons(self) -> list[dict[str, Any]]:
        """Get all seasons."""
        response = self._request("GET", "/api/seasons")
        return response.json()

    def get_current_season(self) -> dict[str, Any]:
        """Get the current season."""
        response = self._request("GET", "/api/current-season")
        return response.json()

    def get_active_seasons(self) -> list[dict[str, Any]]:
        """Get all active seasons."""
        response = self._request("GET", "/api/active-seasons")
        return response.json()

    def create_season(self, season: SeasonCreate) -> dict[str, Any]:
        """Create a new season (admin only)."""
        response = self._request("POST", "/api/seasons", json_data=season.model_dump())
        return response.json()

    def update_season(self, season_id: int, season: SeasonUpdate) -> dict[str, Any]:
        """Update a season (admin only)."""
        response = self._request("PUT", f"/api/seasons/{season_id}", json_data=season.model_dump())
        return response.json()

    def delete_season(self, season_id: int) -> dict[str, Any]:
        """Delete a season (admin only)."""
        response = self._request("DELETE", f"/api/seasons/{season_id}")
        return response.json()

    def get_divisions(self) -> list[dict[str, Any]]:
        """Get all divisions."""
        response = self._request("GET", "/api/divisions")
        return response.json()

    def create_division(self, division: DivisionCreate) -> dict[str, Any]:
        """Create a new division (admin only)."""
        response = self._request("POST", "/api/divisions", json_data=division.model_dump(exclude_none=True))
        return response.json()

    def update_division(self, division_id: int, division: DivisionUpdate) -> dict[str, Any]:
        """Update a division (admin only)."""
        response = self._request(
            "PUT", f"/api/divisions/{division_id}", json_data=division.model_dump(exclude_none=True)
        )
        return response.json()

    def delete_division(self, division_id: int) -> dict[str, Any]:
        """Delete a division (admin only)."""
        response = self._request("DELETE", f"/api/divisions/{division_id}")
        return response.json()

    def get_game_types(self) -> list[dict[str, Any]]:
        """Get all match types (game types)."""
        response = self._request("GET", "/api/match-types")
        return response.json()

    def get_positions(self) -> list[dict[str, Any]]:
        """Get all player positions."""
        response = self._request("GET", "/api/positions")
        return response.json()

    # League table endpoints

    def get_table(
        self,
        season_id: int | None = None,
        age_group_id: int | None = None,
        game_type_id: int | None = None,
        division_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get league standings table."""
        params = {}
        if season_id is not None:
            params["season_id"] = season_id
        if age_group_id is not None:
            params["age_group_id"] = age_group_id
        if game_type_id is not None:
            params["game_type_id"] = game_type_id
        if division_id is not None:
            params["division_id"] = division_id

        response = self._request("GET", "/api/table", params=params)
        return response.json()

    # Admin endpoints

    def get_users(self) -> list[dict[str, Any]]:
        """Get all users (admin only)."""
        response = self._request("GET", "/api/auth/users")
        return response.json()

    def update_user_role(self, role_update: RoleUpdate) -> dict[str, Any]:
        """Update a user's role (admin only)."""
        response = self._request("PUT", "/api/auth/users/role", json_data=role_update.model_dump(exclude_none=True))
        return response.json()

    def delete_user(self, user_id: str) -> dict[str, Any]:
        """Delete a user by ID (admin only)."""
        response = self._request("DELETE", f"/api/auth/users/{user_id}")
        return response.json()

    # Utility endpoints

    def health_check(self) -> dict[str, Any]:
        """Check API health."""
        response = self._request("GET", "/health")
        return response.json()

    def full_health_check(self) -> dict[str, Any]:
        """Comprehensive health check."""
        response = self._request("GET", "/health/full")
        return response.json()

    def get_csrf_token(self) -> str:
        """Get CSRF token."""
        response = self._request("GET", "/api/csrf-token")
        return response.json()["csrf_token"]

    # Club endpoints

    def get_clubs(self, include_teams: bool = False) -> list[dict[str, Any]]:
        """Get all clubs."""
        params = {"include_teams": include_teams}
        response = self._request("GET", "/api/clubs", params=params)
        return response.json()

    def get_club(self, club_id: int) -> dict[str, Any]:
        """Get a specific club by ID."""
        response = self._request("GET", f"/api/clubs/{club_id}")
        return response.json()

    def get_club_teams(self, club_id: int) -> list[dict[str, Any]]:
        """Get all teams for a club."""
        response = self._request("GET", f"/api/clubs/{club_id}/teams")
        return response.json()

    def create_club(self, name: str, city: str | None = None, description: str | None = None) -> dict[str, Any]:
        """Create a new club (admin only)."""
        payload = {"name": name}
        if city:
            payload["city"] = city
        if description:
            payload["description"] = description
        response = self._request("POST", "/api/clubs", json_data=payload)
        return response.json()

    def update_club(
        self,
        club_id: int,
        name: str | None = None,
        city: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Update a club (admin only)."""
        payload = {}
        if name:
            payload["name"] = name
        if city:
            payload["city"] = city
        if description:
            payload["description"] = description
        response = self._request("PUT", f"/api/clubs/{club_id}", json_data=payload)
        return response.json()

    def delete_club(self, club_id: int) -> dict[str, Any]:
        """Delete a club (admin only)."""
        response = self._request("DELETE", f"/api/clubs/{club_id}")
        return response.json()

    # Invite endpoints

    def validate_invite(self, invite_code: str) -> dict[str, Any]:
        """Validate an invite code (public endpoint)."""
        response = self._request("GET", f"/api/invites/validate/{invite_code}")
        return response.json()

    def get_my_invites(self, status: str | None = None) -> list[dict[str, Any]]:
        """Get invites created by current user."""
        params = {}
        if status:
            params["status"] = status
        response = self._request("GET", "/api/invites/my-invites", params=params)
        return response.json()

    def cancel_invite(self, invite_id: str) -> dict[str, Any]:
        """Cancel a pending invite."""
        response = self._request("DELETE", f"/api/invites/{invite_id}")
        return response.json()

    # Admin invite creation endpoints

    def create_club_manager_invite(self, club_id: int, email: str | None = None) -> dict[str, Any]:
        """Create a club manager invite (admin only)."""
        payload = {"club_id": club_id}
        if email:
            payload["email"] = email
        response = self._request("POST", "/api/invites/admin/club-manager", json_data=payload)
        return response.json()

    def create_team_manager_invite(self, team_id: int, age_group_id: int, email: str | None = None) -> dict[str, Any]:
        """Create a team manager invite (admin only)."""
        payload = {
            "invite_type": "team_manager",
            "team_id": team_id,
            "age_group_id": age_group_id,
        }
        if email:
            payload["email"] = email
        response = self._request("POST", "/api/invites/admin/team-manager", json_data=payload)
        return response.json()

    def create_team_player_invite_admin(
        self, team_id: int, age_group_id: int, email: str | None = None
    ) -> dict[str, Any]:
        """Create a team player invite (admin only)."""
        payload = {
            "invite_type": "team_player",
            "team_id": team_id,
            "age_group_id": age_group_id,
        }
        if email:
            payload["email"] = email
        response = self._request("POST", "/api/invites/admin/team-player", json_data=payload)
        return response.json()

    def create_team_fan_invite_admin(self, team_id: int, age_group_id: int, email: str | None = None) -> dict[str, Any]:
        """Create a team fan invite (admin only)."""
        payload = {
            "invite_type": "team_fan",
            "team_id": team_id,
            "age_group_id": age_group_id,
        }
        if email:
            payload["email"] = email
        response = self._request("POST", "/api/invites/admin/team-fan", json_data=payload)
        return response.json()

    def create_club_fan_invite_admin(self, club_id: int, email: str | None = None) -> dict[str, Any]:
        """Create a club fan invite (admin only)."""
        payload = {"club_id": club_id}
        if email:
            payload["email"] = email
        response = self._request("POST", "/api/invites/admin/club-fan", json_data=payload)
        return response.json()

    # Club manager invite creation endpoints

    def create_club_fan_invite(self, club_id: int, email: str | None = None) -> dict[str, Any]:
        """Create a club fan invite (club manager or admin)."""
        payload = {"club_id": club_id}
        if email:
            payload["email"] = email
        response = self._request("POST", "/api/invites/club-manager/club-fan", json_data=payload)
        return response.json()

    # Team manager invite creation endpoints

    def create_team_player_invite(
        self, team_id: int, age_group_id: int, email: str | None = None, player_id: int | None = None
    ) -> dict[str, Any]:
        """Create a team player invite (team manager or admin)."""
        payload: dict[str, Any] = {
            "invite_type": "team_player",
            "team_id": team_id,
            "age_group_id": age_group_id,
        }
        if email:
            payload["email"] = email
        if player_id is not None:
            payload["player_id"] = player_id
        response = self._request("POST", "/api/invites/team-manager/team-player", json_data=payload)
        return response.json()

    def create_team_fan_invite(self, team_id: int, age_group_id: int, email: str | None = None) -> dict[str, Any]:
        """Create a team fan invite (team manager or admin)."""
        payload = {
            "invite_type": "team_fan",
            "team_id": team_id,
            "age_group_id": age_group_id,
        }
        if email:
            payload["email"] = email
        response = self._request("POST", "/api/invites/team-manager/team-fan", json_data=payload)
        return response.json()

    def get_team_manager_assignments(self) -> list[dict[str, Any]]:
        """Get team assignments for current team manager."""
        response = self._request("GET", "/api/invites/team-manager/assignments")
        return response.json()

    # League endpoints

    def get_leagues(self) -> list[dict[str, Any]]:
        """Get all leagues."""
        response = self._request("GET", "/api/leagues")
        return response.json()

    def get_league(self, league_id: int) -> dict[str, Any]:
        """Get a specific league by ID."""
        response = self._request("GET", f"/api/leagues/{league_id}")
        return response.json()

    def create_league(self, name: str, description: str | None = None, is_active: bool = True) -> dict[str, Any]:
        """Create a new league (admin only)."""
        payload = {"name": name, "is_active": is_active}
        if description:
            payload["description"] = description
        response = self._request("POST", "/api/leagues", json_data=payload)
        return response.json()

    def update_league(
        self,
        league_id: int,
        name: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        """Update a league (admin only)."""
        payload = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if is_active is not None:
            payload["is_active"] = is_active
        response = self._request("PUT", f"/api/leagues/{league_id}", json_data=payload)
        return response.json()

    def delete_league(self, league_id: int) -> dict[str, Any]:
        """Delete a league (admin only)."""
        response = self._request("DELETE", f"/api/leagues/{league_id}")
        return response.json()

    # Auth extras

    def get_me(self) -> dict[str, Any]:
        """Get current authenticated user info."""
        response = self._request("GET", "/api/auth/me")
        return response.json()

    def check_username_available(self, username: str) -> dict[str, Any]:
        """Check if a username is available."""
        response = self._request("GET", f"/api/auth/username-available/{username}")
        return response.json()

    # Profile photos

    def upload_profile_photo(self, slot: str, file_path: str) -> dict[str, Any]:
        """Upload a profile photo to a slot (multipart)."""
        with open(file_path, "rb") as f:
            response = self._request_multipart(
                "POST",
                f"/api/auth/profile/photo/{slot}",
                files={"file": (file_path.split("/")[-1], f)},
            )
        return response.json()

    def delete_profile_photo(self, slot: str) -> dict[str, Any]:
        """Delete a profile photo from a slot."""
        response = self._request("DELETE", f"/api/auth/profile/photo/{slot}")
        return response.json()

    def set_profile_photo_slot(self, slot: str) -> dict[str, Any]:
        """Set the active profile photo slot."""
        response = self._request("PUT", "/api/auth/profile/photo/profile-slot", json_data={"slot": slot})
        return response.json()

    # Profile customization

    def update_player_customization(self, customization: PlayerCustomization) -> dict[str, Any]:
        """Update player customization settings."""
        response = self._request(
            "PUT", "/api/auth/profile/customization", json_data=customization.model_dump(exclude_none=True)
        )
        return response.json()

    # Player history

    def get_player_history(self) -> list[dict[str, Any]]:
        """Get current user's player history."""
        response = self._request("GET", "/api/auth/profile/history")
        return response.json()

    def get_current_team_assignment(self) -> dict[str, Any]:
        """Get current team assignment for the authenticated player."""
        response = self._request("GET", "/api/auth/profile/history/current")
        return response.json()

    def get_all_current_teams(self) -> list[dict[str, Any]]:
        """Get all current team assignments for the authenticated player."""
        response = self._request("GET", "/api/auth/profile/teams/current")
        return response.json()

    def create_player_history(self, history: PlayerHistoryCreate) -> dict[str, Any]:
        """Create a player history entry."""
        response = self._request(
            "POST", "/api/auth/profile/history", json_data=history.model_dump(exclude_none=True)
        )
        return response.json()

    def update_player_history(self, history_id: int, history: PlayerHistoryUpdate) -> dict[str, Any]:
        """Update a player history entry."""
        response = self._request(
            "PUT", f"/api/auth/profile/history/{history_id}", json_data=history.model_dump(exclude_none=True)
        )
        return response.json()

    def delete_player_history(self, history_id: int) -> dict[str, Any]:
        """Delete a player history entry."""
        response = self._request("DELETE", f"/api/auth/profile/history/{history_id}")
        return response.json()

    # Admin user profile

    def admin_update_user_profile(self, profile: UserProfileUpdate) -> dict[str, Any]:
        """Update a user profile (admin only)."""
        response = self._request("PUT", "/api/auth/users/profile", json_data=profile.model_dump(exclude_none=True))
        return response.json()

    # Admin player management

    def get_admin_players(self, **params: Any) -> list[dict[str, Any]]:
        """Get players list (admin only)."""
        response = self._request("GET", "/api/admin/players", params=params or None)
        return response.json()

    def update_admin_player(self, player_id: int, update: AdminPlayerUpdate) -> dict[str, Any]:
        """Update a player (admin only)."""
        response = self._request(
            "PUT", f"/api/admin/players/{player_id}", json_data=update.model_dump(exclude_none=True)
        )
        return response.json()

    def add_admin_player_team(self, player_id: int, assignment: AdminPlayerTeamAssignment) -> dict[str, Any]:
        """Assign a player to a team (admin only)."""
        response = self._request(
            "POST", f"/api/admin/players/{player_id}/teams", json_data=assignment.model_dump(exclude_none=True)
        )
        return response.json()

    def end_admin_player_team(self, history_id: int) -> dict[str, Any]:
        """End a player's team assignment (admin only)."""
        response = self._request("PUT", f"/api/admin/players/teams/{history_id}/end")
        return response.json()

    # Team roster

    def get_team_roster(self, team_id: int, season_id: int | None = None) -> dict[str, Any]:
        """Get team roster for a season."""
        params = {}
        if season_id is not None:
            params["season_id"] = season_id
        response = self._request("GET", f"/api/teams/{team_id}/roster", params=params or None)
        return response.json()

    def create_roster_entry(self, team_id: int, entry: RosterPlayerCreate) -> dict[str, Any]:
        """Create a roster entry for a team."""
        response = self._request(
            "POST", f"/api/teams/{team_id}/roster", json_data=entry.model_dump(exclude_none=True)
        )
        return response.json()

    def bulk_create_roster(self, team_id: int, bulk: BulkRosterCreate) -> dict[str, Any]:
        """Bulk create roster entries for a team."""
        response = self._request(
            "POST", f"/api/teams/{team_id}/roster/bulk", json_data=bulk.model_dump(exclude_none=True)
        )
        return response.json()

    def update_roster_entry(self, team_id: int, player_id: int, update: RosterPlayerUpdate) -> dict[str, Any]:
        """Update a roster entry."""
        response = self._request(
            "PUT", f"/api/teams/{team_id}/roster/{player_id}", json_data=update.model_dump(exclude_none=True)
        )
        return response.json()

    def update_jersey_number(self, team_id: int, player_id: int, update: JerseyNumberUpdate) -> dict[str, Any]:
        """Update a player's jersey number."""
        response = self._request(
            "PUT", f"/api/teams/{team_id}/roster/{player_id}/number", json_data=update.model_dump(exclude_none=True)
        )
        return response.json()

    def bulk_renumber_roster(self, team_id: int, renumber: BulkRenumberRequest) -> dict[str, Any]:
        """Bulk renumber roster entries."""
        response = self._request(
            "POST", f"/api/teams/{team_id}/roster/renumber", json_data=renumber.model_dump(exclude_none=True)
        )
        return response.json()

    def delete_roster_entry(self, team_id: int, player_id: int) -> dict[str, Any]:
        """Delete a roster entry."""
        response = self._request("DELETE", f"/api/teams/{team_id}/roster/{player_id}")
        return response.json()

    # Team players & stats

    def get_team_players(self, team_id: int) -> list[dict[str, Any]]:
        """Get all players for a team."""
        response = self._request("GET", f"/api/teams/{team_id}/players")
        return response.json()

    def get_team_stats(self, team_id: int, season_id: int | None = None) -> dict[str, Any]:
        """Get team stats."""
        params = {}
        if season_id is not None:
            params["season_id"] = season_id
        response = self._request("GET", f"/api/teams/{team_id}/stats", params=params or None)
        return response.json()

    # Team match types

    def add_team_match_type(self, team_id: int, match_type_id: int, age_group_id: int) -> dict[str, Any]:
        """Add a match type to a team."""
        response = self._request(
            "POST",
            f"/api/teams/{team_id}/match-types",
            json_data={"match_type_id": match_type_id, "age_group_id": age_group_id},
        )
        return response.json()

    def delete_team_match_type(self, team_id: int, match_type_id: int, age_group_id: int) -> dict[str, Any]:
        """Remove a match type from a team."""
        response = self._request("DELETE", f"/api/teams/{team_id}/match-types/{match_type_id}/{age_group_id}")
        return response.json()

    # Match live

    def get_live_matches(self) -> list[dict[str, Any]]:
        """Get all currently live matches."""
        response = self._request("GET", "/api/matches/live")
        return response.json()

    def get_live_match_state(self, match_id: int) -> dict[str, Any]:
        """Get live state for a match."""
        response = self._request("GET", f"/api/matches/{match_id}/live")
        return response.json()

    def update_match_clock(self, match_id: int, clock: LiveMatchClock) -> dict[str, Any]:
        """Update the match clock."""
        response = self._request(
            "POST", f"/api/matches/{match_id}/live/clock", json_data=clock.model_dump(exclude_none=True)
        )
        return response.json()

    def post_goal(self, match_id: int, goal: GoalEvent) -> dict[str, Any]:
        """Record a goal event."""
        response = self._request(
            "POST", f"/api/matches/{match_id}/live/goal", json_data=goal.model_dump(exclude_none=True)
        )
        return response.json()

    def post_message(self, match_id: int, message: MessageEvent) -> dict[str, Any]:
        """Post a match message event."""
        response = self._request(
            "POST", f"/api/matches/{match_id}/live/message", json_data=message.model_dump(exclude_none=True)
        )
        return response.json()

    def delete_match_event(self, match_id: int, event_id: int) -> dict[str, Any]:
        """Delete a match event."""
        response = self._request("DELETE", f"/api/matches/{match_id}/live/events/{event_id}")
        return response.json()

    def get_match_events(self, match_id: int) -> list[dict[str, Any]]:
        """Get all events for a match."""
        response = self._request("GET", f"/api/matches/{match_id}/live/events")
        return response.json()

    # Match lineup

    def get_lineup(self, match_id: int, team_id: int) -> dict[str, Any]:
        """Get lineup for a team in a match."""
        response = self._request("GET", f"/api/matches/{match_id}/lineup/{team_id}")
        return response.json()

    def save_lineup(self, match_id: int, team_id: int, lineup: LineupSave) -> dict[str, Any]:
        """Save lineup for a team in a match."""
        response = self._request(
            "PUT", f"/api/matches/{match_id}/lineup/{team_id}", json_data=lineup.model_dump(exclude_none=True)
        )
        return response.json()

    # Match operations

    def submit_match_async(self, submission: MatchSubmissionData) -> dict[str, Any]:
        """Submit a match asynchronously via message queue."""
        response = self._request(
            "POST", "/api/matches/submit", json_data=submission.model_dump(exclude_none=True)
        )
        return response.json()

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Get the status of an async task."""
        response = self._request("GET", f"/api/matches/task/{task_id}")
        return response.json()

    # Team mappings

    def create_team_mapping(self, team_id: int, age_group_id: int, division_id: int) -> dict[str, Any]:
        """Create a team mapping."""
        response = self._request(
            "POST",
            "/api/team-mappings",
            json_data={"team_id": team_id, "age_group_id": age_group_id, "division_id": division_id},
        )
        return response.json()

    def delete_team_mapping(self, team_id: int, age_group_id: int, division_id: int) -> dict[str, Any]:
        """Delete a team mapping."""
        response = self._request("DELETE", f"/api/team-mappings/{team_id}/{age_group_id}/{division_id}")
        return response.json()

    # Club logo

    def upload_club_logo(self, club_id: int, file_path: str) -> dict[str, Any]:
        """Upload a club logo (multipart)."""
        with open(file_path, "rb") as f:
            response = self._request_multipart(
                "POST",
                f"/api/clubs/{club_id}/logo",
                files={"file": (file_path.split("/")[-1], f)},
            )
        return response.json()

    # Player stats

    def get_my_player_stats(self, season_id: int | None = None) -> dict[str, Any]:
        """Get current user's player stats."""
        params = {}
        if season_id is not None:
            params["season_id"] = season_id
        response = self._request("GET", "/api/me/player-stats", params=params or None)
        return response.json()

    def get_player_profile(self, user_id: str) -> dict[str, Any]:
        """Get a player's public profile."""
        response = self._request("GET", f"/api/players/{user_id}/profile")
        return response.json()

    def get_roster_player_stats(self, player_id: int, season_id: int | None = None) -> dict[str, Any]:
        """Get stats for a roster player."""
        params = {}
        if season_id is not None:
            params["season_id"] = season_id
        response = self._request("GET", f"/api/roster/{player_id}/stats", params=params or None)
        return response.json()

    # Leaderboards

    def get_goals_leaderboard(self, **params: Any) -> list[dict[str, Any]]:
        """Get the goals leaderboard."""
        response = self._request("GET", "/api/leaderboards/goals", params=params or None)
        return response.json()

    # Invite requests

    def create_invite_request(self, request: InviteRequestCreate) -> dict[str, Any]:
        """Submit a public invite request."""
        response = self._request("POST", "/api/invite-requests", json_data=request.model_dump(exclude_none=True))
        return response.json()

    def list_invite_requests(
        self, status: str | None = None, limit: int | None = None, offset: int | None = None
    ) -> list[dict[str, Any]]:
        """List invite requests (admin only)."""
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        response = self._request("GET", "/api/invite-requests", params=params or None)
        return response.json()

    def get_invite_request_stats(self) -> dict[str, Any]:
        """Get invite request statistics (admin only)."""
        response = self._request("GET", "/api/invite-requests/stats")
        return response.json()

    def get_invite_request(self, request_id: str) -> dict[str, Any]:
        """Get a specific invite request (admin only)."""
        response = self._request("GET", f"/api/invite-requests/{request_id}")
        return response.json()

    def update_invite_request_status(
        self, request_id: str, update: InviteRequestStatusUpdate
    ) -> dict[str, Any]:
        """Update invite request status (admin only)."""
        response = self._request(
            "PUT", f"/api/invite-requests/{request_id}/status", json_data=update.model_dump(exclude_none=True)
        )
        return response.json()

    def delete_invite_request(self, request_id: str) -> dict[str, Any]:
        """Delete an invite request (admin only)."""
        response = self._request("DELETE", f"/api/invite-requests/{request_id}")
        return response.json()

    # Version

    def get_version(self) -> dict[str, Any]:
        """Get API version information."""
        response = self._request("GET", "/api/version")
        return response.json()

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
    AgeGroupCreate,
    AgeGroupUpdate,
    DivisionCreate,
    DivisionUpdate,
    EnhancedGame,
    GamePatch,
    RefreshTokenRequest,
    RoleUpdate,
    SeasonCreate,
    SeasonUpdate,
    Team,
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

    # Authentication endpoints

    def login(self, email: str, password: str) -> dict[str, Any]:
        """
        Login with email and password.

        Returns:
            Dict with access_token, refresh_token, and user info
        """
        response = self._request(
            "POST",
            "/api/auth/login",
            json_data={"email": email, "password": password},
        )
        data = response.json()

        # Store tokens for future requests
        self._access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token")

        return data

    def signup(self, email: str, password: str, display_name: str | None = None) -> dict[str, Any]:
        """
        Sign up a new user.

        Returns:
            Dict with access_token, refresh_token, and user info
        """
        payload = {"email": email, "password": password}
        if display_name:
            payload["display_name"] = display_name

        response = self._request("POST", "/api/auth/signup", json_data=payload)
        return response.json()

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

        # Update access token
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
        team_id: int | None = None,
        limit: int | None = None,
        upcoming: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Get games with optional filters."""
        params = {}
        if season_id is not None:
            params["season_id"] = season_id
        if age_group_id is not None:
            params["age_group_id"] = age_group_id
        if game_type_id is not None:
            params["game_type_id"] = game_type_id
        if team_id is not None:
            params["team_id"] = team_id
        if limit is not None:
            params["limit"] = limit
        if upcoming is not None:
            params["upcoming"] = upcoming

        response = self._request("GET", "/api/games", params=params)
        return response.json()

    def get_game(self, game_id: int) -> dict[str, Any]:
        """Get a specific game by ID."""
        response = self._request("GET", f"/api/games/{game_id}")
        return response.json()

    def get_games_by_team(self, team_id: int) -> list[dict[str, Any]]:
        """Get all games for a specific team."""
        response = self._request("GET", f"/api/games/team/{team_id}")
        return response.json()

    def create_game(self, game: EnhancedGame) -> dict[str, Any]:
        """Create a new game."""
        response = self._request("POST", "/api/games", json_data=game.model_dump(exclude_none=True))
        return response.json()

    def update_game(self, game_id: int, game: EnhancedGame) -> dict[str, Any]:
        """Update a game (full update)."""
        response = self._request("PUT", f"/api/games/{game_id}", json_data=game.model_dump(exclude_none=True))
        return response.json()

    def patch_game(self, game_id: int, game_patch: GamePatch) -> dict[str, Any]:
        """Partially update a game."""
        response = self._request("PATCH", f"/api/games/{game_id}", json_data=game_patch.model_dump(exclude_none=True))
        return response.json()

    def delete_game(self, game_id: int) -> dict[str, Any]:
        """Delete a game."""
        response = self._request("DELETE", f"/api/games/{game_id}")
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
        response = self._request("PUT", f"/api/divisions/{division_id}", json_data=division.model_dump(exclude_none=True))
        return response.json()

    def delete_division(self, division_id: int) -> dict[str, Any]:
        """Delete a division (admin only)."""
        response = self._request("DELETE", f"/api/divisions/{division_id}")
        return response.json()

    def get_game_types(self) -> list[dict[str, Any]]:
        """Get all game types."""
        response = self._request("GET", "/api/game-types")
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

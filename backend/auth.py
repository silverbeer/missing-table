"""
Authentication and authorization utilities for the sports league backend.
"""

import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from supabase import Client

load_dotenv()

# JWKS client for ES256 token verification (cached)
_jwks_client: PyJWKClient | None = None

logger = logging.getLogger(__name__)
security = HTTPBearer()


# ============================================================================
# Username Authentication Helper Functions
# ============================================================================

def username_to_internal_email(username: str) -> str:
    """
    Convert username to internal email format for Supabase Auth.

    Example: gabe_ifa_35 -> gabe_ifa_35@missingtable.local
    """
    return f"{username.lower()}@missingtable.local"


def internal_email_to_username(email: str) -> str | None:
    """
    Extract username from internal email format.

    Example: gabe_ifa_35@missingtable.local -> gabe_ifa_35
    Returns None if not an internal email.
    """
    if email.endswith('@missingtable.local'):
        return email.replace('@missingtable.local', '')
    return None


def is_internal_email(email: str) -> bool:
    """Check if email is an internal format."""
    return email.endswith('@missingtable.local')


async def check_username_available(supabase_client: Client, username: str) -> bool:
    """
    Check if username is available.

    Returns True if username is available, False if taken.
    """
    try:
        result = supabase_client.table('user_profiles')\
            .select('id')\
            .eq('username', username.lower())\
            .execute()

        return len(result.data) == 0
    except Exception as e:
        logger.error(f"Error checking username availability: {e}")
        raise


class AuthManager:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        self.service_account_secret = os.getenv("SERVICE_ACCOUNT_SECRET", secrets.token_urlsafe(32))

        if not self.jwt_secret:
            raise ValueError(
                "SUPABASE_JWT_SECRET environment variable is required. "
                "Please set it in your .env file."
            )

    def verify_token(self, token: str) -> dict[str, Any] | None:
        """Verify JWT token and return user data."""
        global _jwks_client
        try:
            # Check token header to determine algorithm
            unverified_header = jwt.get_unverified_header(token)
            alg = unverified_header.get("alg", "HS256")

            if alg == "ES256":
                # Use JWKS for ES256 tokens (new Supabase CLI)
                supabase_url = os.getenv("SUPABASE_URL", "http://127.0.0.1:54331")
                jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"

                if _jwks_client is None:
                    _jwks_client = PyJWKClient(jwks_url)

                signing_key = _jwks_client.get_signing_key_from_jwt(token)
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["ES256"],
                    audience="authenticated",
                )
            else:
                # Use symmetric secret for HS256 tokens (legacy/cloud)
                payload = jwt.decode(
                    token,
                    self.jwt_secret,
                    algorithms=["HS256"],
                    audience="authenticated",
                )

            user_id = payload.get("sub")
            if not user_id:
                return None

            # Get user profile with role
            logger.debug(f"Querying user_profiles for user_id: {user_id}")
            profile_response = (
                self.supabase.table("user_profiles").select("*").eq("id", user_id).execute()
            )

            if not profile_response.data or len(profile_response.data) == 0:
                logger.warning(f"No profile found for user {user_id}")
                return None

            # If multiple profiles exist, take the first one (should be fixed by cleanup script)
            profile = profile_response.data[0]
            if len(profile_response.data) > 1:
                logger.warning(f"Multiple profiles found for user {user_id}, using first one")

            # Extract username from profile (primary identifier)
            username = profile.get("username")

            # Get email from JWT payload (might be internal email format)
            jwt_email = payload.get("email")

            # Distinguish between internal email (username@missingtable.local) and real email
            # Real email is stored in profile.email, internal email is in JWT
            if jwt_email and is_internal_email(jwt_email):
                # This is an internal email, extract username if not in profile
                if not username:
                    username = internal_email_to_username(jwt_email)
                real_email = profile.get("email")  # Optional real email from profile
            else:
                # Legacy user with real email in JWT
                real_email = jwt_email

            return {
                "user_id": user_id,
                "username": username,  # Primary identifier for username auth users
                "email": real_email,  # Real email (optional, for notifications)
                "role": profile["role"],
                "team_id": profile.get("team_id"),
                "club_id": profile.get("club_id"),  # For club managers
                "display_name": profile.get("display_name"),
            }

        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return None

    def create_service_account_token(self, service_name: str, permissions: list[str], expires_days: int = 365) -> str:
        """Create a service account JWT token for automated systems."""
        expiration = datetime.now(UTC) + timedelta(days=expires_days)

        payload = {
            "sub": f"service-{service_name}",
            "iss": "missing-table",
            "aud": "service-account",
            "exp": int(expiration.timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
            "service_name": service_name,
            "permissions": permissions,
            "role": "service_account"
        }

        return jwt.encode(payload, self.service_account_secret, algorithm="HS256")

    def verify_service_account_token(self, token: str) -> dict[str, Any] | None:
        """Verify service account JWT token and return service data."""
        try:
            payload = jwt.decode(
                token, self.service_account_secret,
                algorithms=["HS256"],
                audience="service-account"
            )

            service_name = payload.get("service_name")
            permissions = payload.get("permissions", [])

            if not service_name:
                return None

            return {
                "service_id": payload.get("sub"),
                "service_name": service_name,
                "permissions": permissions,
                "role": "service_account",
                "is_service_account": True
            }

        except jwt.ExpiredSignatureError:
            logger.warning("Service account token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid service account token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error verifying service account token: {e}")
            return None

    def get_current_user(
        self, credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> dict[str, Any]:
        """FastAPI dependency to get current authenticated user or service account."""
        if not credentials:
            logger.warning("auth_failed: no_credentials")
            raise HTTPException(status_code=401, detail="Authentication required")

        # Try regular user token first
        user_data = self.verify_token(credentials.credentials)
        if user_data:
            logger.debug(f"auth_success: user={user_data.get('username')}")
            return user_data

        # Try service account token
        service_data = self.verify_service_account_token(credentials.credentials)
        if service_data:
            logger.debug(f"auth_success: service={service_data.get('service_name')}")
            return service_data

        logger.warning("auth_failed: invalid_token")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    def require_role(self, required_roles: list):
        """Decorator to require specific roles."""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Get current user from kwargs (injected by FastAPI dependency)
                current_user = None
                for key, value in kwargs.items():
                    if isinstance(value, dict) and "role" in value:
                        current_user = value
                        break

                if not current_user:
                    raise HTTPException(status_code=401, detail="Authentication required")

                user_role = current_user.get("role")
                if user_role not in required_roles:
                    raise HTTPException(
                        status_code=403, detail=f"Access denied. Required roles: {required_roles}"
                    )

                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def can_manage_team(self, user_data: dict[str, Any], team_id: int) -> bool:
        """Check if user can manage a specific team."""
        role = user_data.get("role")
        user_team_id = user_data.get("team_id")
        user_club_id = user_data.get("club_id")

        # Admins can manage any team
        if role == "admin":
            return True

        # Team managers can only manage their own team
        if role == "team-manager" and user_team_id == team_id:
            return True

        # Club managers can manage any team in their club
        if role == "club_manager" and user_club_id:
            team_club_id = self._get_team_club_id(team_id)
            if team_club_id and team_club_id == user_club_id:
                return True

        return False

    def _get_team_club_id(self, team_id: int) -> int | None:
        """Get the club_id for a team."""
        try:
            result = self.supabase.table("teams").select("club_id").eq("id", team_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0].get("club_id")
            return None
        except Exception as e:
            logger.error(f"Error getting team club_id: {e}")
            return None

    def can_edit_match(
        self, user_data: dict[str, Any], home_team_id: int, away_team_id: int
    ) -> bool:
        """Check if user can edit a match between specific teams."""
        role = user_data.get("role")
        user_team_id = user_data.get("team_id")
        user_club_id = user_data.get("club_id")

        # Admins can edit any match
        if role == "admin":
            return True

        # Service accounts with manage_matches permission can edit any match
        if role == "service_account":
            permissions = user_data.get("permissions", [])
            if "manage_matches" in permissions:
                return True

        # Team managers can edit matches involving their team
        if role == "team-manager" and user_team_id in [home_team_id, away_team_id]:
            return True

        # Club managers can edit matches involving any team in their club
        if role == "club_manager" and user_club_id:
            home_club_id = self._get_team_club_id(home_team_id)
            away_club_id = self._get_team_club_id(away_team_id)
            if user_club_id in [home_club_id, away_club_id]:
                return True

        return False


# Auth dependency functions for FastAPI
def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
) -> dict[str, Any] | None:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None

    # This will be injected by the main app
    from app import auth_manager

    return auth_manager.verify_token(credentials.credentials)


def get_current_user_required(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """Get current user, raise exception if not authenticated."""
    # This will be injected by the main app
    from app import auth_manager

    return auth_manager.get_current_user(credentials)


def require_admin(
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> dict[str, Any]:
    """Require admin role."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_team_manager_or_admin(
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> dict[str, Any]:
    """Require team-manager, club_manager, or admin role."""
    role = current_user.get("role")
    if role not in ["admin", "club_manager", "team-manager"]:
        raise HTTPException(status_code=403, detail="Team manager, club manager, or admin access required")
    return current_user


def require_admin_or_service_account(
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> dict[str, Any]:
    """Require admin role or service account with appropriate permissions."""
    role = current_user.get("role")

    # Allow admin users
    if role == "admin":
        return current_user

    # Allow service accounts with match management permissions
    if role == "service_account":
        permissions = current_user.get("permissions", [])
        if "manage_matches" in permissions:
            return current_user
        else:
            raise HTTPException(
                status_code=403,
                detail="Service account requires 'manage_matches' permission"
            )

    raise HTTPException(status_code=403, detail="Admin or authorized service account access required")


def require_match_management_permission(
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> dict[str, Any]:
    """Require permission to manage matches (admin, club_manager, team-manager, or service account)."""
    import logging
    logger = logging.getLogger(__name__)

    role = current_user.get("role")
    # Use username for regular users, service_name for service accounts
    user_identifier = current_user.get("username") or current_user.get("service_name", "unknown")

    logger.info(f"Match management permission check - User: {user_identifier}, Role: {role}, User data: {current_user}")

    # Allow admin, club managers, and team managers
    if role in ["admin", "club_manager", "team-manager"]:
        logger.info(f"Access granted - User {user_identifier} has role {role}")
        return current_user

    # Allow service accounts with match management permissions
    if role == "service_account":
        permissions = current_user.get("permissions", [])
        if "manage_matches" in permissions:
            logger.info(f"Access granted - Service account {user_identifier} has manage_matches permission")
            return current_user
        else:
            logger.warning(f"Access denied - Service account {user_identifier} missing manage_matches permission. Has: {permissions}")
            raise HTTPException(
                status_code=403,
                detail="Service account requires 'manage_matches' permission"
            )

    logger.warning(f"Access denied - User {user_identifier} has insufficient role: {role}")
    raise HTTPException(
        status_code=403,
        detail="Admin, club manager, team manager, or authorized service account access required"
    )

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.invite_requests import router as invite_requests_router
from api.invites import router as invites_router
from auth import (
    AuthManager,
    get_current_user_required,
    require_admin,
    require_match_management_permission,
    require_team_manager_or_admin,
)
from constants import PLAYER_POSITIONS
from csrf_protection import provide_csrf_token
from middleware import TraceMiddleware
from models import (
    AdminPlayerTeamAssignment,
    AdminPlayerUpdate,
    AgeGroupCreate,
    AgeGroupUpdate,
    BulkRenumberRequest,
    BulkRosterCreate,
    Club,
    DivisionCreate,
    DivisionUpdate,
    EnhancedMatch,
    GoalEvent,
    JerseyNumberUpdate,
    LeagueCreate,
    LeagueUpdate,
    LineupSave,
    LiveMatchClock,
    MatchPatch,
    MatchSubmissionData,
    MessageEvent,
    PlayerCustomization,
    PlayerHistoryCreate,
    PlayerHistoryUpdate,
    ProfilePhotoSlot,
    RefreshTokenRequest,
    RoleUpdate,
    RosterPlayerCreate,
    RosterPlayerUpdate,
    SeasonCreate,
    SeasonUpdate,
    Team,
    TeamMappingCreate,
    TeamMatchTypeMapping,
    TeamUpdate,
    UserLogin,
    UserProfile,
    UserProfileUpdate,
    UserSignup,
)
from services import InviteService

# Legacy flag kept for backwards compatibility so existing envs keep working.
DISABLE_SECURITY = os.getenv("DISABLE_SECURITY", "false").lower() == "true"

from dao.club_dao import ClubDAO
from dao.exceptions import DuplicateRecordError
from dao.league_dao import LeagueDAO
from dao.lineup_dao import LineupDAO
from dao.match_dao import MatchDAO
from dao.match_dao import SupabaseConnection as DbConnectionHolder
from dao.match_event_dao import MatchEventDAO
from dao.match_type_dao import MatchTypeDAO
from dao.player_dao import PlayerDAO
from dao.player_stats_dao import PlayerStatsDAO
from dao.roster_dao import RosterDAO
from dao.season_dao import SeasonDAO
from dao.team_dao import TeamDAO


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

# Configure structured logging with JSON output for Loki
from logging_config import get_logger, setup_logging

setup_logging(service_name="backend")
logger = get_logger(__name__)

app = FastAPI(title="Enhanced Sports League API", version="2.0.0")

# Setup Prometheus metrics - exposes /metrics endpoint for Grafana
from metrics_config import setup_metrics

setup_metrics(app)
logger.info("prometheus_metrics_enabled", endpoint="/metrics")

# Configure Rate Limiting
# TODO: Fix middleware order issue
# limiter = create_rate_limit_middleware(app)

# Add CSRF Protection Middleware
# TODO: Fix middleware order issue
# app.middleware("http")(csrf_middleware)


# Configure CORS
def get_cors_origins():
    """Get CORS origins based on environment"""
    local_origins = [
        "http://localhost:8080",
        "http://localhost:8081",
        "http://192.168.1.2:8080",
        "http://192.168.1.2:8081",
    ]

    # Production origins (HTTPS only - HTTP redirects to HTTPS via Ingress)
    # After deprecating dev.missingtable.com (2025-11-19), only production domains remain
    production_origins = [
        "https://missingtable.com",
        "https://www.missingtable.com",
    ]

    # Allow additional CORS origins from environment variable
    extra_origins_str = os.getenv("CORS_ORIGINS", "")
    extra_origins = [origin.strip() for origin in extra_origins_str.split(",") if origin.strip()]

    # Get environment-specific origins
    environment = os.getenv("ENVIRONMENT", "development")

    # All production domains point to the same namespace (missing-table-dev)
    all_cloud_origins = production_origins

    # In production, only allow production origins (security best practice)
    # In development/dev, allow both local and cloud origins for flexibility
    if environment == "production":
        return all_cloud_origins + extra_origins
    else:
        # Development/dev environment: allow local origins + cloud origins (consolidated architecture)
        return local_origins + all_cloud_origins + extra_origins


origins = get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trace middleware for distributed logging (session_id, request_id)
app.add_middleware(TraceMiddleware)

# Initialize Supabase connection - use CLI for local development
supabase_url = os.getenv("SUPABASE_URL", "")
logger.debug(
    "Supabase URL configuration",
    url=supabase_url,
    is_local="localhost" in supabase_url or "127.0.0.1" in supabase_url,
)
if "localhost" in supabase_url or "127.0.0.1" in supabase_url:
    logger.info("Using Supabase CLI local development", url=supabase_url)
else:
    logger.info("Using enhanced Supabase connection")

# Initialize all DAOs with shared connection
db_conn_holder_obj = DbConnectionHolder()
match_dao = MatchDAO(db_conn_holder_obj)
match_event_dao = MatchEventDAO(db_conn_holder_obj)
team_dao = TeamDAO(db_conn_holder_obj)
club_dao = ClubDAO(db_conn_holder_obj)
player_dao = PlayerDAO(db_conn_holder_obj)
roster_dao = RosterDAO(db_conn_holder_obj)
player_stats_dao = PlayerStatsDAO(db_conn_holder_obj)
lineup_dao = LineupDAO(db_conn_holder_obj)
season_dao = SeasonDAO(db_conn_holder_obj)
league_dao = LeagueDAO(db_conn_holder_obj)
match_type_dao = MatchTypeDAO(db_conn_holder_obj)


# === Simple Redis Caching ===
# Initialize Authentication Manager with a dedicated service client
# This prevents login operations from modifying the client used for profile lookups
from supabase import create_client

auth_service_client = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY", ""),
)
auth_manager = AuthManager(auth_service_client)

# Create a separate client for auth operations (login/signup/logout)
# This prevents auth operations from modifying the client used by match_dao
auth_ops_client = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_ANON_KEY", ""),  # Auth operations use anon key
)


def get_client_ip(request: Request) -> str:
    """Best-effort client IP resolving for logging/auditing."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


# === Include API Routers ===
app.include_router(invites_router)
app.include_router(invite_requests_router)

# Version endpoint
import contextlib

from endpoints.version import router as version_router

app.include_router(version_router)

# === Authentication Endpoints ===


async def _update_existing_user_role(user_data, invite_info, audit_logger):
    """Helper to update an existing user's role when they re-signup with an invite code.

    This handles the case where a user already exists (e.g., created as team-fan)
    but is now signing up with an invite code to get a different role (e.g., team-manager).
    """
    from auth import username_to_internal_email

    try:
        logger.info(f"Updating existing user {user_data.username} role via invite code")

        # Get the user's ID from user_profiles
        existing_profile = player_dao.get_user_profile_by_username(user_data.username)
        if not existing_profile:
            # Try to find by internal email in auth.users
            internal_email = username_to_internal_email(user_data.username)
            auth_response = auth_service_client.auth.admin.list_users()
            existing_user = None
            for user in auth_response:
                if user.email == internal_email:
                    existing_user = user
                    break

            if not existing_user:
                raise HTTPException(status_code=400, detail=f"User {user_data.username} not found")
            user_id = existing_user.id
        else:
            user_id = existing_profile["id"]

        # Map invite type to user role
        role_mapping = {
            "club_manager": "club_manager",
            "club_fan": "club-fan",
            "team_manager": "team-manager",
            "team_player": "team-player",
            "team_fan": "team-fan",
        }
        new_role = role_mapping.get(invite_info["invite_type"], "team-fan")

        # Update user profile with new role and invite info
        update_data = {
            "username": user_data.username.lower(),
            "role": new_role,
            "team_id": invite_info.get("team_id"),
            "club_id": invite_info.get("club_id"),
        }
        player_dao.update_user_profile(user_id, update_data)

        # Redeem the invitation
        invite_service = InviteService(db_conn_holder_obj.client)
        invite_service.redeem_invitation(user_data.invite_code, user_id)

        logger.info(f"Updated existing user {user_id} role to {new_role} via invite code")
        audit_logger.info("auth_role_update_success", user_id=user_id, new_role=new_role)

        role_display = invite_info["invite_type"].replace("_", " ")
        return {
            "message": f"Welcome back, {user_data.username}! Your role has been updated to {role_display}.",
            "user_id": user_id,
            "username": user_data.username,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update existing user role: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/auth/signup")
# @rate_limit("3 per hour")
async def signup(request: Request, user_data: UserSignup):
    """User signup endpoint with username authentication."""
    from auth import check_username_available, username_to_internal_email

    client_ip = get_client_ip(request)
    audit_logger = logger.bind(flow="auth_signup", username=user_data.username, client_ip=client_ip)

    try:
        # Validate invite code if provided (do this FIRST)
        invite_info = None
        if user_data.invite_code:
            invite_service = InviteService(db_conn_holder_obj.client)
            invite_info = invite_service.validate_invite_code(user_data.invite_code)
            if not invite_info:
                raise HTTPException(status_code=400, detail="Invalid or expired invite code")

            # If invite has email specified, verify it matches (if user provided email)
            if invite_info.get("email") and user_data.email:
                if invite_info["email"] != user_data.email:
                    raise HTTPException(
                        status_code=400,
                        detail=f"This invite code is for {invite_info['email']}. Please use that email address.",
                    )

        # Validate username availability
        username_available = await check_username_available(db_conn_holder_obj.client, user_data.username)
        if not username_available:
            # If user has invite code, allow them to "re-signup" to update their role
            if invite_info:
                logger.info(f"User {user_data.username} exists but has invite code - will update role")
                # Redirect to the role update flow
                return await _update_existing_user_role(user_data, invite_info, audit_logger)
            raise HTTPException(status_code=400, detail=f"Username '{user_data.username}' is already taken")

        if invite_info:
            logger.info(f"Valid invite code for {invite_info['invite_type']}: {user_data.invite_code}")

        # Convert username to internal email for Supabase Auth
        internal_email = username_to_internal_email(user_data.username)

        # Create Supabase Auth user with internal email
        # Use auth_ops_client to avoid modifying the match_dao client
        response = auth_ops_client.auth.sign_up(
            {
                "email": internal_email,
                "password": user_data.password,
                "options": {
                    "data": {
                        "username": user_data.username,
                        "display_name": user_data.display_name or user_data.username,
                        "is_username_auth": True,
                    }
                },
            }
        )

        if response.user:
            # Create/update user profile with username and optional contact info
            # Convert empty strings to None for optional fields
            profile_data = {
                "id": response.user.id,
                "username": user_data.username,
                "email": user_data.email if user_data.email else None,  # Optional real email
                "phone_number": user_data.phone_number if user_data.phone_number else None,  # Optional phone
                "display_name": user_data.display_name or user_data.username,
                "role": "team-fan",  # Default role
            }

            # If signup with invite code, override role and team
            if invite_info:
                # Map invite type to user role
                role_mapping = {
                    "club_manager": "club_manager",
                    "club_fan": "club-fan",
                    "team_manager": "team-manager",
                    "team_player": "team-player",
                    "team_fan": "team-fan",
                }
                profile_data["role"] = role_mapping.get(invite_info["invite_type"], "team-fan")
                profile_data["team_id"] = invite_info.get("team_id")
                profile_data["club_id"] = invite_info.get("club_id")

            # Insert user profile
            player_dao.create_or_update_user_profile(profile_data)

            # Redeem invitation if used
            if invite_info:
                invite_service.redeem_invitation(user_data.invite_code, response.user.id)
                logger.info(f"User {response.user.id} assigned role {profile_data['role']} via invite code")

            audit_logger.info(
                "auth_signup_success",
                user_id=response.user.id,
                used_invite=bool(user_data.invite_code),
            )

            message = f"Account created successfully! Welcome, {user_data.username}!"
            if invite_info:
                invite_type_display = invite_info["invite_type"].replace("_", " ")
                if invite_info.get("club_name"):
                    message += f" You have been assigned to {invite_info['club_name']} as a {invite_type_display}."
                elif invite_info.get("team_name"):
                    message += f" You have been assigned to {invite_info['team_name']} as a {invite_type_display}."

            return {"message": message, "user_id": response.user.id, "username": user_data.username}
        else:
            audit_logger.warning("auth_signup_failed", reason="supabase_user_missing")
            raise HTTPException(status_code=400, detail="Failed to create user")

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        # Handle "User already registered" case - update role if invite code is valid
        logger.info(f"Signup exception handler: error='{error_msg}', invite_info={invite_info is not None}")
        if "User already registered" in error_msg and invite_info:
            try:
                logger.info(f"Attempting to update existing user {user_data.username} role via invite")
                # Get existing user by internal email from auth.users
                from auth import username_to_internal_email

                internal_email = username_to_internal_email(user_data.username)
                # Query auth.users to get user_id
                auth_response = auth_service_client.auth.admin.list_users()
                existing_user = None
                for user in auth_response:
                    if user.email == internal_email:
                        existing_user = user
                        break
                logger.info(f"Found existing auth user: {existing_user.id if existing_user else None}")
                if existing_user:
                    # Map invite type to user role
                    role_mapping = {
                        "club_manager": "club_manager",
                        "club_fan": "club-fan",
                        "team_manager": "team-manager",
                        "team_player": "team-player",
                        "team_fan": "team-fan",
                    }
                    new_role = role_mapping.get(invite_info["invite_type"], "team-fan")

                    # Update user profile with new role, username, and invite info
                    update_data = {
                        "username": user_data.username.lower(),  # Fix missing username
                        "role": new_role,
                        "team_id": invite_info.get("team_id"),
                        "club_id": invite_info.get("club_id"),
                    }
                    player_dao.update_user_profile(existing_user.id, update_data)

                    # Redeem the invitation
                    invite_service = InviteService(db_conn_holder_obj.client)
                    invite_service.redeem_invitation(user_data.invite_code, existing_user.id)

                    logger.info(f"Updated existing user {existing_user.id} role to {new_role} via invite code")
                    role_display = invite_info["invite_type"].replace("_", " ")
                    return {
                        "message": f"Welcome back! Your role has been updated to {role_display}.",
                        "user_id": existing_user.id,
                        "username": user_data.username,
                    }
            except Exception as update_error:
                logger.error(f"Failed to update existing user role: {update_error}", exc_info=True)

        audit_logger.error("auth_signup_error", error=error_msg, email=user_data.email)
        logger.error(f"Signup error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=error_msg) from e


@app.post("/api/auth/login")
# @rate_limit("5 per minute")
async def login(request: Request, user_data: UserLogin):
    """User login endpoint with username authentication."""
    from auth import username_to_internal_email

    client_ip = get_client_ip(request)
    auth_logger = logger.bind(flow="auth_login", username=user_data.username, client_ip=client_ip)

    try:
        # Convert username to internal email for Supabase Auth
        internal_email = username_to_internal_email(user_data.username)

        # Authenticate with Supabase using internal email
        # Use auth_ops_client to avoid modifying the match_dao client
        response = auth_ops_client.auth.sign_in_with_password({"email": internal_email, "password": user_data.password})

        if response.user and response.session:
            # Get user profile with username, team, AND club info
            profile = player_dao.get_user_profile_with_relationships(response.user.id)
            if not profile:
                profile = {"username": user_data.username}  # Fallback

            auth_logger.info("auth_login_success", user_id=response.user.id)

            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "user": {
                    "id": response.user.id,
                    "username": profile.get("username"),
                    "email": profile.get("email"),  # Real email if provided
                    "display_name": profile.get("display_name"),
                    "role": profile.get("role"),
                    "team_id": profile.get("team_id"),
                    "club_id": profile.get("club_id"),
                    "team": profile.get("team"),
                    "club": profile.get("club"),
                    "created_at": profile.get("created_at"),
                    "updated_at": profile.get("updated_at"),
                },
            }
        else:
            auth_logger.warning("auth_login_failed", reason="invalid_credentials")
            raise HTTPException(status_code=401, detail="Invalid username or password")

    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error("auth_login_error", error=str(e))
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid credentials") from e


@app.get("/api/auth/username-available/{username}")
async def check_username_availability(username: str):
    """
    Check if a username is available.

    Returns:
    - available: boolean
    - suggestions: list of alternative usernames if taken
    """
    import re

    from auth import check_username_available

    try:
        # Validate username format
        if not re.match(r"^[a-zA-Z0-9_]{3,50}$", username):
            return {
                "available": False,
                "message": "Username must be 3-50 characters (letters, numbers, underscores only)",
            }

        # Check availability
        available = await check_username_available(db_conn_holder_obj.client, username)

        if available:
            return {"available": True, "message": f"Username '{username}' is available!"}
        else:
            # Generate suggestions
            import hashlib

            hash_suffix = int(hashlib.md5(username.encode()).hexdigest(), 16) % 100
            suggestions = [
                f"{username}_1",
                f"{username}_2",
                f"{username}_{hash_suffix}",
            ]

            return {
                "available": False,
                "message": f"Username '{username}' is taken",
                "suggestions": suggestions,
            }

    except Exception as e:
        logger.error(f"Error checking username: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error checking username availability") from e


@app.post("/api/auth/logout")
async def logout(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """User logout endpoint."""
    try:
        # Use auth_ops_client to avoid modifying the match_dao client
        auth_ops_client.auth.sign_out()
        return {"success": True, "message": "Logged out successfully"}
    except Exception as e:
        logger.error(f"Logout error: {e}", exc_info=True)
        return {
            "success": True,  # Return success even on error since logout should be client-side primarily
            "message": "Logged out successfully",
        }


class OAuthCallbackData(BaseModel):
    """OAuth callback data from frontend."""

    access_token: str
    refresh_token: str | None = None
    provider: str = "google"
    invite_code: str | None = None  # Optional - required for signup, not required for login
    display_name: str | None = None  # Optional - user's custom display name from signup form


@app.post("/api/auth/oauth/callback")
async def oauth_callback(callback_data: OAuthCallbackData, request: Request):
    """
    Handle OAuth callback from frontend.

    After Supabase OAuth flow completes, the frontend sends the tokens here
    to verify and get/create the user profile.

    TWO FLOWS:
    1. LOGIN (no invite_code): For returning users who already have an account
    2. SIGNUP (with invite_code): For new users, invite determines role/team/club
    """
    from services.invite_service import InviteService

    client_ip = get_client_ip(request)
    is_login_flow = callback_data.invite_code is None
    oauth_logger = logger.bind(
        flow="auth_oauth_callback",
        provider=callback_data.provider,
        client_ip=client_ip,
        is_login_flow=is_login_flow,
    )

    try:
        # Verify the token by getting user info from Supabase FIRST
        # This is needed for both login and signup flows
        from supabase import create_client

        temp_client = create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_ANON_KEY", ""))
        temp_client.auth.set_session(callback_data.access_token, callback_data.refresh_token or "")
        user_response = temp_client.auth.get_user()

        if not user_response or not user_response.user:
            oauth_logger.warning("oauth_callback_failed", reason="invalid_token")
            raise HTTPException(status_code=401, detail="Invalid OAuth token")

        supabase_user = user_response.user
        user_id = supabase_user.id
        email = supabase_user.email
        user_metadata = supabase_user.user_metadata or {}

        oauth_logger = oauth_logger.bind(user_id=user_id, email=email)

        # Check if user profile exists by email or user_id
        email_profile_response = (
            db_conn_holder_obj.client.table("user_profiles").select("*").eq("email", email).execute()
        )
        existing_by_email = email_profile_response.data[0] if email_profile_response.data else None

        profile_response = db_conn_holder_obj.client.table("user_profiles").select("*").eq("id", user_id).execute()
        existing_by_id = profile_response.data[0] if profile_response.data else None

        # Check if it's a trigger stub (incomplete profile)
        is_trigger_stub = (
            existing_by_id
            and existing_by_id.get("username") is None
            and existing_by_id.get("auth_provider") == "password"
        )

        # Determine existing profile (prefer email match, then id match)
        existing_profile = existing_by_email or (existing_by_id if not is_trigger_stub else None)

        # ===== LOGIN FLOW (no invite code) =====
        if is_login_flow:
            if not existing_profile:
                oauth_logger.warning("oauth_login_failed", reason="no_account")
                # Sign out of Supabase to clean up the session
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(temp_client.auth.sign_out)
                raise HTTPException(
                    status_code=400,
                    detail="No account found with this Google account. Please sign up with an invite code first.",
                )

            # Verify auth_provider is google (not password user trying to use OAuth)
            if existing_profile.get("auth_provider") == "password":
                oauth_logger.warning("oauth_login_failed", reason="wrong_auth_provider")
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(temp_client.auth.sign_out)
                raise HTTPException(
                    status_code=400,
                    detail="This account was created with username/password. Please use the login form instead.",
                )

            oauth_logger.info("oauth_login_success", username=existing_profile.get("username"))
            return {"message": "Login successful", "user": existing_profile}

        # ===== SIGNUP FLOW (with invite code) =====
        # Validate the invite code
        invite_service = InviteService(db_conn_holder_obj.client)
        invite_info = invite_service.validate_invite_code(callback_data.invite_code)

        if not invite_info:
            oauth_logger.warning("oauth_callback_failed", reason="invalid_invite_code")
            raise HTTPException(status_code=400, detail="Invalid or expired invite code")

        oauth_logger = oauth_logger.bind(invite_type=invite_info.get("invite_type"))

        # Extract user info for signup
        display_name = (
            callback_data.display_name
            or user_metadata.get("full_name")
            or user_metadata.get("name")
            or email.split("@")[0]
        )
        avatar_url = user_metadata.get("avatar_url") or user_metadata.get("picture")

        # For signup, reject if account already exists
        if existing_profile:
            oauth_logger.warning(
                "oauth_callback_failed",
                reason="email_already_exists",
                existing_username=existing_profile.get("username"),
            )
            username = existing_profile.get("username")
            raise HTTPException(
                status_code=400,
                detail=f"An account with this email already exists (username: {username}). Please login instead.",
            )

        # Either new user OR trigger-created stub that needs to be completed
        # Map invite_type to role
        invite_type_to_role = {
            "club_manager": "club_manager",
            "club_fan": "club_fan",
            "team_manager": "team-manager",
            "team_player": "team-player",
            "team_fan": "team-fan",
        }
        role = invite_type_to_role.get(invite_info.get("invite_type"), "team-fan")

        # Generate a unique username from email
        base_username = email.split("@")[0].replace(".", "_").replace("-", "_")[:40]
        username = base_username

        # Check if username exists and make unique if needed
        from auth import check_username_available

        counter = 1
        while not await check_username_available(db_conn_holder_obj.client, username):
            username = f"{base_username}_{counter}"
            counter += 1
            if counter > 100:
                # Fallback to UUID suffix
                import uuid

                username = f"{base_username}_{str(uuid.uuid4())[:8]}"
                break

        # Profile data with invite-based role and team/club
        profile_data = {
            "username": username,
            "display_name": display_name,
            "email": email,
            "role": role,
            "team_id": invite_info.get("team_id"),
            "club_id": invite_info.get("club_id"),
            "profile_photo_url": avatar_url,
            "auth_provider": callback_data.provider,
            "updated_at": datetime.utcnow().isoformat(),
        }

        if is_trigger_stub:
            # Update the stub profile created by Supabase trigger
            oauth_logger.info("oauth_updating_trigger_stub", user_id=user_id)
            db_conn_holder_obj.client.table("user_profiles").update(profile_data).eq("id", user_id).execute()
        else:
            # Create new profile (shouldn't happen if trigger exists, but handle it)
            profile_data["id"] = user_id
            profile_data["created_at"] = datetime.utcnow().isoformat()
            db_conn_holder_obj.client.table("user_profiles").insert(profile_data).execute()

        # Redeem the invite (marks as used) - do this for both update and insert
        invite_service.redeem_invitation(callback_data.invite_code, user_id)

        oauth_logger.info("oauth_signup_success", username=username, role=role)

        return {
            "success": True,
            "user": {
                "id": user_id,
                "email": email,
                "username": username,
                "display_name": display_name,
                "role": role,
                "team_id": invite_info.get("team_id"),
                "club_id": invite_info.get("club_id"),
                "profile_photo_url": avatar_url,
                "auth_provider": callback_data.provider,
                "is_new_user": True,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        oauth_logger.error("oauth_callback_error", error=str(e))
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="OAuth authentication failed") from e


@app.get("/api/auth/profile")
async def get_profile(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get current user's profile."""
    try:
        profile = player_dao.get_user_profile_with_relationships(current_user["user_id"])
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {
            "id": profile["id"],
            "username": profile.get("username"),
            "email": profile.get("email"),
            "role": profile["role"],
            "team_id": profile.get("team_id"),
            "club_id": profile.get("club_id"),
            "team": profile.get("team"),
            "club": profile.get("club"),
            "display_name": profile.get("display_name"),
            "player_number": profile.get("player_number"),
            "positions": profile.get("positions", []),
            "created_at": profile.get("created_at"),
            "updated_at": profile.get("updated_at"),
            # Photo fields
            "photo_1_url": profile.get("photo_1_url"),
            "photo_2_url": profile.get("photo_2_url"),
            "photo_3_url": profile.get("photo_3_url"),
            "profile_photo_slot": profile.get("profile_photo_slot"),
            "overlay_style": profile.get("overlay_style"),
            "primary_color": profile.get("primary_color"),
            "text_color": profile.get("text_color"),
            "accent_color": profile.get("accent_color"),
            # Social media handles
            "instagram_handle": profile.get("instagram_handle"),
            "snapchat_handle": profile.get("snapchat_handle"),
            "tiktok_handle": profile.get("tiktok_handle"),
            # Personal info
            "first_name": profile.get("first_name"),
            "last_name": profile.get("last_name"),
            "hometown": profile.get("hometown"),
        }

    except Exception as e:
        logger.error(f"Get profile error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get profile") from e


@app.put("/api/auth/profile")
async def update_profile(profile_data: UserProfile, current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Update current user's profile."""
    try:
        update_data = {}
        if profile_data.display_name is not None:
            update_data["display_name"] = profile_data.display_name

        # Email update with validation
        if profile_data.email is not None:
            # Basic email format validation
            import re

            email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if profile_data.email.strip() and not re.match(email_pattern, profile_data.email):
                raise HTTPException(status_code=400, detail="Invalid email format")

            # Check for email uniqueness (if not empty)
            if profile_data.email.strip():
                existing = player_dao.get_user_profile_by_email(
                    profile_data.email, exclude_user_id=current_user["user_id"]
                )
                if existing:
                    raise HTTPException(status_code=409, detail="Email already in use")

            update_data["email"] = profile_data.email if profile_data.email.strip() else None

        if profile_data.team_id is not None:
            update_data["team_id"] = profile_data.team_id
        if profile_data.player_number is not None:
            update_data["player_number"] = profile_data.player_number
        if profile_data.positions is not None:
            update_data["positions"] = profile_data.positions

        # Customization fields (overlay style and colors)
        if profile_data.overlay_style is not None:
            if profile_data.overlay_style not in ("badge", "jersey", "caption", "none"):
                raise HTTPException(status_code=400, detail="Invalid overlay_style")
            update_data["overlay_style"] = profile_data.overlay_style
        if profile_data.primary_color is not None:
            update_data["primary_color"] = profile_data.primary_color
        if profile_data.text_color is not None:
            update_data["text_color"] = profile_data.text_color
        if profile_data.accent_color is not None:
            update_data["accent_color"] = profile_data.accent_color

        # Only allow role updates by admins
        if profile_data.role is not None:
            if current_user.get("role") != "admin":
                raise HTTPException(status_code=403, detail="Only admins can change roles")
            update_data["role"] = profile_data.role

        if update_data:
            from datetime import datetime

            update_data["updated_at"] = datetime.now(UTC).isoformat()
            player_dao.update_user_profile(current_user["user_id"], update_data)

        return {"message": "Profile updated successfully"}

    except Exception as e:
        logger.error(f"Update profile error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update profile") from e


# =============================================================================
# PLAYER PROFILE PHOTO ENDPOINTS
# =============================================================================

MAX_PHOTO_SIZE = 500 * 1024  # 500KB
ALLOWED_PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"]


class StorageHelper:
    """Helper for direct Supabase Storage API calls (bypasses RLS issues with client)."""

    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.service_key = os.getenv("SUPABASE_SERVICE_KEY")

    def upload(self, bucket: str, file_path: str, content: bytes, content_type: str) -> dict:
        """Upload a file to storage using direct HTTP API."""
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        response = httpx.post(
            f"{self.url}/storage/v1/object/{bucket}/{file_path}",
            content=content,
            headers=headers,
            timeout=30.0,
        )
        if response.status_code not in (200, 201):
            raise Exception(f"Storage upload failed: {response.text}")
        return response.json()

    def delete(self, bucket: str, file_paths: list[str]) -> dict:
        """Delete files from storage using direct HTTP API."""
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }
        response = httpx.delete(
            f"{self.url}/storage/v1/object/{bucket}",
            json={"prefixes": file_paths},
            headers=headers,
            timeout=30.0,
        )
        if response.status_code not in (200, 204):
            # Ignore 404s - file might already be gone
            if response.status_code != 404:
                raise Exception(f"Storage delete failed: {response.text}")
        return {"deleted": file_paths}

    def get_public_url(self, bucket: str, file_path: str) -> str:
        """Get the public URL for a file."""
        return f"{self.url}/storage/v1/object/public/{bucket}/{file_path}"


storage_helper = StorageHelper()


def require_player_role(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Dependency that requires team-player role."""
    if current_user.get("role") != "team-player":
        raise HTTPException(status_code=403, detail="This feature is only available for players")
    return current_user


@app.post("/api/auth/profile/photo/{slot}")
async def upload_player_photo(
    slot: int,
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(require_player_role),
):
    """Upload a profile photo to a slot (1, 2, or 3). Players only.

    Uploads the image to Supabase Storage and updates the user profile.
    Accepted formats: PNG, JPG/JPEG, WebP. Max size: 500KB.
    """
    # Validate slot
    if slot not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="Slot must be 1, 2, or 3")

    # Validate file type
    if file.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: JPG, PNG, WebP. Got: {file.content_type}",
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_PHOTO_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is 500KB. Got: {len(content) / 1024:.1f}KB",
        )

    # Determine file extension
    ext_map = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
    ext = ext_map.get(file.content_type, "jpg")
    user_id = current_user["user_id"]
    file_path = f"{user_id}/photo_{slot}.{ext}"

    try:
        # Upload to player-photos bucket using direct HTTP API
        storage_helper.upload("player-photos", file_path, content, file.content_type)

        # Get public URL
        public_url = storage_helper.get_public_url("player-photos", file_path)

        # Update user profile with the photo URL
        from datetime import datetime

        photo_column = f"photo_{slot}_url"
        update_data = {photo_column: public_url, "updated_at": datetime.now(UTC).isoformat()}

        # If no profile photo is set, set this as the profile photo
        profile = player_dao.get_user_profile_with_relationships(user_id)
        if not profile.get("profile_photo_slot"):
            update_data["profile_photo_slot"] = slot

        player_dao.update_user_profile(user_id, update_data)

        # Return updated profile
        updated_profile = player_dao.get_user_profile_with_relationships(user_id)
        return {
            "message": f"Photo uploaded to slot {slot}",
            "photo_url": public_url,
            "profile": updated_profile,
        }

    except Exception as e:
        logger.error(f"Error uploading player photo: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/auth/profile/photo/{slot}")
async def delete_player_photo(slot: int, current_user: dict[str, Any] = Depends(require_player_role)):
    """Delete a profile photo from a slot (1, 2, or 3). Players only.

    If this was the profile photo, auto-selects the next available photo.
    """
    # Validate slot
    if slot not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="Slot must be 1, 2, or 3")

    user_id = current_user["user_id"]

    try:
        # Get current profile
        profile = player_dao.get_user_profile_with_relationships(user_id)
        photo_column = f"photo_{slot}_url"
        current_url = profile.get(photo_column)

        if not current_url:
            raise HTTPException(status_code=404, detail=f"No photo in slot {slot}")

        # Delete from storage - try all extensions
        file_path = f"{user_id}/photo_{slot}"
        for ext in ["jpg", "png", "webp"]:
            try:
                storage_helper.delete("player-photos", [f"{file_path}.{ext}"])
            except Exception:
                pass  # File might not exist with this extension

        # Update profile to remove URL
        from datetime import datetime

        update_data = {photo_column: None, "updated_at": datetime.now(UTC).isoformat()}

        # If this was the profile photo, find next available
        if profile.get("profile_photo_slot") == slot:
            new_profile_slot = None
            for check_slot in [1, 2, 3]:
                if check_slot != slot and profile.get(f"photo_{check_slot}_url"):
                    new_profile_slot = check_slot
                    break
            update_data["profile_photo_slot"] = new_profile_slot

        player_dao.update_user_profile(user_id, update_data)

        # Return updated profile
        updated_profile = player_dao.get_user_profile_with_relationships(user_id)
        return {"message": f"Photo deleted from slot {slot}", "profile": updated_profile}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting player photo: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.put("/api/auth/profile/photo/profile-slot")
async def set_profile_photo_slot(
    slot_data: ProfilePhotoSlot, current_user: dict[str, Any] = Depends(require_player_role)
):
    """Set which photo slot is the profile picture. Players only.

    The specified slot must have a photo uploaded.
    """
    slot = slot_data.slot
    user_id = current_user["user_id"]

    try:
        # Get current profile
        profile = player_dao.get_user_profile_with_relationships(user_id)
        photo_url = profile.get(f"photo_{slot}_url")

        if not photo_url:
            raise HTTPException(status_code=400, detail=f"No photo in slot {slot}. Upload a photo first.")

        # Update profile photo slot
        from datetime import datetime

        player_dao.update_user_profile(
            user_id, {"profile_photo_slot": slot, "updated_at": datetime.now(UTC).isoformat()}
        )

        # Return updated profile
        updated_profile = player_dao.get_user_profile_with_relationships(user_id)
        return {"message": f"Profile photo set to slot {slot}", "profile": updated_profile}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting profile photo slot: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.put("/api/auth/profile/customization")
async def update_player_customization(
    customization: PlayerCustomization, current_user: dict[str, Any] = Depends(require_player_role)
):
    """Update player profile customization (colors, style). Players only.

    This is a convenience endpoint for updating multiple customization
    fields at once. All fields are optional.
    """
    user_id = current_user["user_id"]

    try:
        from datetime import datetime

        update_data = {"updated_at": datetime.now(UTC).isoformat()}

        # Personal info
        if customization.first_name is not None:
            update_data["first_name"] = customization.first_name
        if customization.last_name is not None:
            update_data["last_name"] = customization.last_name
        if customization.hometown is not None:
            update_data["hometown"] = customization.hometown
        # Visual customization
        if customization.overlay_style is not None:
            update_data["overlay_style"] = customization.overlay_style
        if customization.primary_color is not None:
            update_data["primary_color"] = customization.primary_color
        if customization.text_color is not None:
            update_data["text_color"] = customization.text_color
        if customization.accent_color is not None:
            update_data["accent_color"] = customization.accent_color
        if customization.player_number is not None:
            update_data["player_number"] = customization.player_number
        if customization.positions is not None:
            update_data["positions"] = customization.positions
        # Social media handles
        if customization.instagram_handle is not None:
            update_data["instagram_handle"] = customization.instagram_handle
        if customization.snapchat_handle is not None:
            update_data["snapchat_handle"] = customization.snapchat_handle
        if customization.tiktok_handle is not None:
            update_data["tiktok_handle"] = customization.tiktok_handle

        if len(update_data) > 1:  # More than just updated_at
            player_dao.update_user_profile(user_id, update_data)

        # Return updated profile
        updated_profile = player_dao.get_user_profile_with_relationships(user_id)
        return {"message": "Customization updated", "profile": updated_profile}

    except Exception as e:
        logger.error(f"Error updating player customization: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Player Team History Endpoints ===


@app.get("/api/auth/profile/history")
async def get_player_history(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get player's team history across all seasons.

    Returns history entries ordered by season (most recent first),
    with full team, season, age_group, league, and division details.
    """
    user_id = current_user["user_id"]

    try:
        history = player_dao.get_player_team_history(user_id)
        return {"success": True, "history": history}
    except Exception as e:
        logger.error(f"Error getting player history: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/auth/profile/history/current")
async def get_current_team_assignment(
    current_user: dict[str, Any] = Depends(get_current_user_required),
):
    """Get player's current team assignment (is_current=true).

    Returns the current history entry with full related data,
    or null if no current assignment exists.
    """
    user_id = current_user["user_id"]

    try:
        current = player_dao.get_current_player_team_assignment(user_id)
        return {"success": True, "current": current}
    except Exception as e:
        logger.error(f"Error getting current team assignment: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/auth/profile/teams/current")
async def get_all_current_teams(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get ALL current team assignments for a player.

    Returns all team assignments where is_current=true.
    This supports players being on multiple teams simultaneously
    (e.g., for futsal/soccer leagues).

    Returns:
        List of current teams with club info for team selector UI.
    """
    user_id = current_user["user_id"]

    try:
        teams = player_dao.get_all_current_player_teams(user_id)
        return {"success": True, "teams": teams}
    except Exception as e:
        logger.error(f"Error getting all current teams: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/auth/profile/history")
async def create_player_history(
    history_data: PlayerHistoryCreate,
    current_user: dict[str, Any] = Depends(get_current_user_required),
):
    """Create a new player team history entry.

    Players can add their own history entries for different seasons.
    The entry will automatically capture age_group, league, and division
    from the team's current configuration.
    """
    user_id = current_user["user_id"]

    try:
        entry = player_dao.create_player_history_entry(
            player_id=user_id,
            team_id=history_data.team_id,
            season_id=history_data.season_id,
            jersey_number=history_data.jersey_number,
            positions=history_data.positions,
            notes=history_data.notes,
            is_current=history_data.is_current,
        )

        if entry:
            return {"success": True, "entry": entry}
        else:
            raise HTTPException(status_code=500, detail="Failed to create history entry")

    except Exception as e:
        logger.error(f"Error creating player history entry: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.put("/api/auth/profile/history/{history_id}")
async def update_player_history(
    history_id: int,
    history_data: PlayerHistoryUpdate,
    current_user: dict[str, Any] = Depends(get_current_user_required),
):
    """Update a player team history entry.

    Players can only update their own history entries.
    """
    user_id = current_user["user_id"]

    try:
        # Verify this entry belongs to the user
        existing = player_dao.get_player_history_entry_by_id(history_id)
        if not existing:
            raise HTTPException(status_code=404, detail="History entry not found")
        if existing.get("player_id") != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to update this entry")

        entry = player_dao.update_player_history_entry(
            history_id=history_id,
            jersey_number=history_data.jersey_number,
            positions=history_data.positions,
            notes=history_data.notes,
            is_current=history_data.is_current,
        )

        if entry:
            return {"success": True, "entry": entry}
        else:
            raise HTTPException(status_code=500, detail="Failed to update history entry")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating player history entry: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/auth/profile/history/{history_id}")
async def delete_player_history(history_id: int, current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Delete a player team history entry.

    Players can only delete their own history entries.
    """
    user_id = current_user["user_id"]

    try:
        # Verify this entry belongs to the user
        existing = player_dao.get_player_history_entry_by_id(history_id)
        if not existing:
            raise HTTPException(status_code=404, detail="History entry not found")
        if existing.get("player_id") != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this entry")

        success = player_dao.delete_player_history_entry(history_id)

        if success:
            return {"success": True, "message": "History entry deleted"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete history entry")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting player history entry: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Admin Player Management Endpoints ===


@app.get("/api/admin/players")
async def get_admin_players(
    search: str | None = None,
    club_id: int | None = None,
    team_id: int | None = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin),
):
    """Get all players with team assignments for admin management.

    Supports filtering by search text, club, and team.
    Returns paginated results with current team assignments.
    """
    try:
        result = player_dao.get_all_players_admin(
            search=search, club_id=club_id, team_id=team_id, limit=limit, offset=offset
        )
        return result

    except Exception as e:
        logger.error(f"Error getting admin players: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.put("/api/admin/players/{player_id}")
async def update_admin_player(
    player_id: str,
    data: AdminPlayerUpdate,
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin),
):
    """Update a player's profile info (admin/manager operation).

    Allows updating display_name, player_number, and positions.
    """
    try:
        result = player_dao.update_player_admin(
            player_id=player_id,
            display_name=data.display_name,
            player_number=data.player_number,
            positions=data.positions,
        )

        if result:
            return {"success": True, "player": result}
        else:
            raise HTTPException(status_code=404, detail="Player not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating admin player: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/admin/players/{player_id}/teams")
async def add_admin_player_team(
    player_id: str,
    data: AdminPlayerTeamAssignment,
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin),
):
    """Assign a player to a team (admin/manager operation).

    Creates a player_team_history entry for the assignment.
    """
    try:
        # Use the existing create_player_history_entry method
        entry = player_dao.create_player_history_entry(
            player_id=player_id,
            team_id=data.team_id,
            season_id=data.season_id,
            jersey_number=data.jersey_number,
            is_current=data.is_current,
        )

        if entry:
            return {"success": True, "assignment": entry}
        else:
            raise HTTPException(status_code=500, detail="Failed to create team assignment")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding admin player team: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.put("/api/admin/players/teams/{history_id}/end")
async def end_admin_player_team(
    history_id: int,
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin),
):
    """End a player's team assignment (admin/manager operation).

    Sets is_current=false on the player_team_history entry.
    """
    try:
        result = player_dao.end_player_team_assignment(history_id=history_id)

        if result:
            return {"success": True, "assignment": result}
        else:
            raise HTTPException(status_code=404, detail="Assignment not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending admin player team: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/auth/users")
async def get_users(current_user: dict[str, Any] = Depends(require_admin)):
    """Get all users (admin only)."""
    try:
        return player_dao.get_all_user_profiles()

    except Exception as e:
        logger.error(f"Get users error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get users") from e


@app.post("/api/auth/refresh")
async def refresh_token(request: Request, refresh_data: RefreshTokenRequest):
    """Refresh JWT token using refresh token."""
    refresh_logger = logger.bind(flow="auth_refresh", client_ip=get_client_ip(request))
    try:
        # Use auth_ops_client to avoid modifying the match_dao client
        response = auth_ops_client.auth.refresh_session(refresh_data.refresh_token)

        if response.session:
            refresh_logger.info("auth_refresh_success")
            return {
                "success": True,
                "session": {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at,
                    "token_type": "bearer",
                },
            }
        else:
            refresh_logger.warning("auth_refresh_failed", reason="no_session")
            raise HTTPException(status_code=401, detail="Failed to refresh token")

    except Exception as e:
        refresh_logger.error("auth_refresh_error", error=str(e))
        logger.error(f"Token refresh error: {e}", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid refresh token") from e


@app.get("/api/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user_required)):
    """Get current user info for frontend auth state."""
    try:
        # Get fresh profile data with team AND club info
        profile = player_dao.get_user_profile_with_relationships(current_user["user_id"]) or {}

        return {
            "success": True,
            "user": {
                "id": current_user["user_id"],
                "email": current_user["email"],
                "profile": {
                    "username": profile.get("username"),
                    "email": profile.get("email"),
                    "role": profile.get("role", "team-fan"),
                    "team_id": profile.get("team_id"),
                    "club_id": profile.get("club_id"),
                    "display_name": profile.get("display_name"),
                    "name": profile.get("name"),
                    "player_number": profile.get("player_number"),
                    "positions": profile.get("positions"),
                    "team": profile.get("team"),
                    "club": profile.get("club"),
                    "created_at": profile.get("created_at"),
                    "updated_at": profile.get("updated_at"),
                    # Photo fields
                    "photo_1_url": profile.get("photo_1_url"),
                    "photo_2_url": profile.get("photo_2_url"),
                    "photo_3_url": profile.get("photo_3_url"),
                    "profile_photo_slot": profile.get("profile_photo_slot"),
                    "overlay_style": profile.get("overlay_style"),
                    "primary_color": profile.get("primary_color"),
                    "text_color": profile.get("text_color"),
                    "accent_color": profile.get("accent_color"),
                    # Social media handles
                    "instagram_handle": profile.get("instagram_handle"),
                    "snapchat_handle": profile.get("snapchat_handle"),
                    "tiktok_handle": profile.get("tiktok_handle"),
                    # Personal info
                    "first_name": profile.get("first_name"),
                    "last_name": profile.get("last_name"),
                    "hometown": profile.get("hometown"),
                },
            },
        }

    except Exception as e:
        logger.error(f"Get user info error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get user info") from e


@app.get("/api/positions")
async def get_positions(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get all available player positions."""
    return PLAYER_POSITIONS


@app.put("/api/auth/users/role")
async def update_user_role(role_data: RoleUpdate, current_user: dict[str, Any] = Depends(require_admin)):
    """Update user role (admin only)."""
    try:
        from datetime import datetime

        update_data = {"role": role_data.role, "updated_at": datetime.now(UTC).isoformat()}

        if role_data.team_id:
            update_data["team_id"] = role_data.team_id

        player_dao.update_user_profile(role_data.user_id, update_data)

        return {"message": "User role updated successfully"}

    except Exception as e:
        logger.error(f"Update user role error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update user role") from e


@app.put("/api/auth/users/profile")
async def update_user_profile(
    profile_data: UserProfileUpdate,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Update user profile information (admin only)."""
    import re

    try:
        update_data = {}

        # Validate and handle username update
        if profile_data.username is not None:
            username = profile_data.username.strip()

            # Validate username format
            if username and not re.match(r"^[a-zA-Z0-9_]{3,50}$", username):
                raise HTTPException(
                    status_code=400,
                    detail="Username must be 3-50 characters (letters, numbers, underscores only)",
                )

            # Check if username is already taken by another user
            if username:
                existing = player_dao.get_user_profile_by_username(username, exclude_user_id=profile_data.user_id)
                if existing:
                    raise HTTPException(status_code=409, detail=f"Username '{username}' is already taken")

                update_data["username"] = username.lower()

                # Update auth.users email to internal format
                # Use auth_service_client for admin operations (requires service key)
                internal_email = f"{username.lower()}@missingtable.local"
                try:
                    auth_service_client.auth.admin.update_user_by_id(
                        profile_data.user_id,
                        {
                            "email": internal_email,
                            "user_metadata": {
                                "username": username.lower(),
                                "is_username_auth": True,
                            },
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to update auth.users email: {e}")

        # Handle display name update
        if profile_data.display_name is not None:
            update_data["display_name"] = profile_data.display_name.strip()

        # Handle email update (real email for notifications)
        if profile_data.email is not None:
            email = profile_data.email.strip()
            if email:
                # Basic email validation
                if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                    raise HTTPException(status_code=400, detail="Invalid email format")
            update_data["email"] = email

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Update user_profiles
        player_dao.update_user_profile(profile_data.user_id, update_data)

        return {"message": "User profile updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user profile error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update user profile: {e!s}") from e


@app.delete("/api/auth/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """
    Delete a user (admin only).

    Deletes from both auth.users and user_profiles table.
    user_profiles must be deleted explicitly (no FK cascade exists).
    """
    try:
        profile = auth_service_client.table("user_profiles").select("*").eq("id", user_id).execute()
        if not profile.data:
            raise HTTPException(status_code=404, detail="User not found")

        # Delete from auth.users
        try:
            auth_service_client.auth.admin.delete_user(user_id)
        except Exception as auth_err:
            # Auth user may already be gone (orphaned profile)
            logger.warning(f"Auth user {user_id} not in auth.users, continuing: {auth_err}")

        # Explicitly delete from user_profiles (no FK cascade exists)
        auth_service_client.table("user_profiles").delete().eq("id", user_id).execute()

        logger.info(f"User {user_id} deleted by admin {current_user.get('user_id')}")
        return {"message": "User deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete user error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {e!s}") from e


# === CSRF Token Endpoint ===


@app.get("/api/csrf-token")
async def get_csrf_token_endpoint(request: Request, response: Response):
    """Get CSRF token for the session."""
    return await provide_csrf_token(request, response)


# === Reference Data Endpoints ===


@app.get("/api/age-groups")
async def get_age_groups(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get all age groups."""
    try:
        logger.info(f"age-groups endpoint - current_user: {current_user}")
        age_groups = season_dao.get_all_age_groups()
        logger.info(f"age-groups endpoint - returning {len(age_groups)} groups")
        return age_groups
    except Exception as e:
        logger.error(f"Error retrieving age groups: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=503, detail="Database connection failed. Please check Supabase connection."
        ) from e


@app.get("/api/seasons")
async def get_seasons(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get all seasons."""
    try:
        seasons = season_dao.get_all_seasons()
        return seasons
    except Exception as e:
        logger.error(f"Error retrieving seasons: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=503, detail="Database connection failed. Please check Supabase connection."
        ) from e


@app.get("/api/current-season")
async def get_current_season(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get the current active season."""
    try:
        current_season = season_dao.get_current_season()
        if not current_season:
            # Default to 2024-2025 season if no current season found
            seasons = season_dao.get_all_seasons()
            current_season = next((s for s in seasons if s["name"] == "2024-2025"), seasons[0] if seasons else None)
        return current_season
    except Exception as e:
        logger.error(f"Error retrieving current season: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/active-seasons")
async def get_active_seasons(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get active seasons (current and future) for scheduling new matches."""
    try:
        active_seasons = season_dao.get_active_seasons()
        return active_seasons
    except Exception as e:
        logger.error(f"Error retrieving active seasons: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/match-types")
async def get_match_types(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get all match types."""
    try:
        match_types = match_type_dao.get_all_match_types()
        return match_types
    except Exception as e:
        logger.error(f"Error retrieving match types: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/divisions")
async def get_divisions(
    current_user: dict[str, Any] = Depends(get_current_user_required), league_id: int | None = None
):
    """Get all divisions, optionally filtered by league."""
    try:
        divisions = league_dao.get_divisions_by_league(league_id) if league_id else league_dao.get_all_divisions()
        return divisions
    except Exception as e:
        logger.error(f"Error retrieving divisions: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Enhanced Team Endpoints ===


@app.get("/api/teams")
async def get_teams(
    current_user: dict[str, Any] = Depends(get_current_user_required),
    match_type_id: int | None = None,
    age_group_id: int | None = None,
    division_id: int | None = None,
    include_parent: bool = False,
    include_game_count: bool = False,
    club_id: int | None = None,
    for_match_edit: bool = False,
):
    """
    Get teams, optionally filtered by match type, age group, division, or club.

    Args:
        match_type_id: Filter by match type
        age_group_id: Filter by age group (requires match_type_id)
        division_id: Filter by division (e.g., Bracket A for Futsal, Northeast for Homegrown)
        include_parent: If true, include parent club information
        include_game_count: If true, include count of games for each team (performance optimized)
        club_id: Filter to only teams belonging to this parent club
        for_match_edit: If true, return all teams (for match editing dropdowns)

    Note: Club managers automatically see only their club's teams unless for_match_edit=true.
    """
    try:
        # Club managers should only see their club's teams (unless editing matches)
        user_role = current_user.get("role")
        user_club_id = current_user.get("club_id")

        if user_role == "club_manager" and user_club_id and not for_match_edit:
            # Override any club_id filter - club managers only see their own club
            club_id = user_club_id

        # Get teams based on filters
        if match_type_id and age_group_id:
            teams = team_dao.get_teams_by_match_type_and_age_group(match_type_id, age_group_id, division_id=division_id)
        elif club_id:
            teams = team_dao.get_club_teams(club_id)
        else:
            teams = team_dao.get_all_teams()

        # Enrich teams with additional data if requested
        if include_parent or include_game_count:
            enriched_teams = []

            # Get game counts for all teams in one query (performance optimization)
            game_counts = {}
            if include_game_count:
                game_counts = team_dao.get_team_game_counts()

            # Pre-fetch clubs once (not inside loop!) for parent club lookup
            clubs_by_id = {}
            if include_parent:
                clubs = club_dao.get_all_clubs()
                clubs_by_id = {c["id"]: c for c in clubs}

            for team in teams:
                team_data = {**team}

                # Add parent club info if requested
                if include_parent:
                    if team.get("club_id"):
                        team_data["parent_club"] = clubs_by_id.get(team["club_id"])
                    else:
                        team_data["parent_club"] = None

                    # Check if this team is itself a parent club
                    if hasattr(team_dao, "is_parent_club"):
                        team_data["is_parent_club"] = team_dao.is_parent_club(team["id"])
                    else:
                        team_data["is_parent_club"] = False

                # Add game count if requested
                if include_game_count:
                    team_data["game_count"] = game_counts.get(team["id"], 0)

                enriched_teams.append(team_data)

            return enriched_teams

        return teams
    except Exception as e:
        logger.error(f"Error retrieving teams: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=503, detail="Database connection failed. Please check Supabase connection."
        ) from e


@app.post("/api/teams")
async def add_team(
    request: Request,
    team: Team,
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin),
):
    """Add a new team with age groups, division, and optional parent club.

    Division represents location (e.g., Northeast Division for Homegrown, New England Conference for Academy).
    All age groups for a team share the same division.

    Club managers can only add teams to their assigned club.
    """
    try:
        user_role = current_user.get("role")
        user_club_id = current_user.get("club_id")

        # Team managers cannot create teams (only manage existing ones)
        if user_role == "team-manager":
            raise HTTPException(status_code=403, detail="Team managers cannot create teams")

        # Club managers can only add teams to their assigned club
        if user_role == "club_manager":
            if not user_club_id:
                raise HTTPException(status_code=403, detail="Club manager must have a club assigned")
            # Force team to be created in the club manager's club
            if team.club_id and team.club_id != user_club_id:
                raise HTTPException(status_code=403, detail="Can only create teams for your assigned club")
            # Auto-assign club_id if not provided
            team.club_id = user_club_id

        # Call add_team with keyword arguments
        success = team_dao.add_team(
            name=team.name,
            city=team.city,
            age_group_ids=team.age_group_ids,
            match_type_ids=team.match_type_ids,
            division_id=team.division_id,
            club_id=team.club_id,
            academy_team=team.academy_team,
        )
        if success:
            return {"message": "Team added successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add team")
    except Exception as e:
        error_str = str(e)
        logger.error(f"Error adding team: {error_str}", exc_info=True)

        # Check for duplicate team constraint violation
        if (
            "teams_name_division_unique" in error_str
            or "teams_name_academy_unique" in error_str
            or "duplicate key value" in error_str.lower()
        ):
            raise HTTPException(status_code=409, detail="Team with this name already exists in this division") from e

        raise HTTPException(status_code=500, detail=error_str) from e


# === Enhanced Match Endpoints ===


@app.get("/api/matches")
async def get_matches(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user_required),
    season_id: int | None = Query(None, description="Filter by season ID"),
    age_group_id: int | None = Query(None, description="Filter by age group ID"),
    division_id: int | None = Query(None, description="Filter by division ID"),
    team_id: int | None = Query(None, description="Filter by team ID (home or away)"),
    match_type: str | None = Query(None, description="Filter by match type name"),
    start_date: str | None = Query(None, description="Filter by start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="Filter by end date (YYYY-MM-DD)"),
):
    """Get all matches with optional filters (requires authentication).

    Note: Club managers only see matches involving their club's teams.
    """
    try:
        matches = match_dao.get_all_matches(
            season_id=season_id,
            age_group_id=age_group_id,
            division_id=division_id,
            team_id=team_id,
            match_type=match_type,
            start_date=start_date,
            end_date=end_date,
        )

        # Club managers only see matches involving their club's teams
        user_role = current_user.get("role")
        user_club_id = current_user.get("club_id")

        if user_role == "club_manager" and user_club_id:
            # Get the team IDs for this club
            club_teams = team_dao.get_club_teams(user_club_id)
            club_team_ids = {team["id"] for team in club_teams}

            # Filter matches to only those involving club's teams
            matches = [
                m for m in matches if m.get("home_team_id") in club_team_ids or m.get("away_team_id") in club_team_ids
            ]

        return matches
    except Exception as e:
        logger.error(f"Error retrieving matches: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=503, detail="Database connection failed. Please check Supabase connection."
        ) from e


@app.get("/api/matches/live")
async def get_live_matches(
    current_user: dict[str, Any] = Depends(get_current_user_required),
):
    """Get all currently live matches.

    Used for the LIVE tab to check if there are active live matches.
    Returns minimal data for efficient polling.
    """
    try:
        live_matches = match_dao.get_live_matches()
        return live_matches
    except Exception as e:
        logger.error(f"Error getting live matches: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/matches/{match_id}")
async def get_match(
    request: Request,
    match_id: int,
    current_user: dict[str, Any] = Depends(get_current_user_required),
):
    """Get a specific match by ID (requires authentication)."""
    try:
        # Use get_match_by_id for efficient single-match lookup with club data
        match = match_dao.get_match_by_id(match_id)

        if not match:
            raise HTTPException(status_code=404, detail=f"Match with ID {match_id} not found")

        return match
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving match {match_id}: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=503, detail="Database connection failed. Please check Supabase connection."
        ) from e


@app.post("/api/matches")
async def add_match(
    request: Request,
    match: EnhancedMatch,
    current_user: dict[str, Any] = Depends(require_match_management_permission),
):
    """Add a new match (requires admin, team manager, or service account with manage_matches permission)."""
    try:
        # Use username for regular users, service_name for service accounts
        user_identifier = current_user.get("username") or current_user.get("service_name", "unknown")
        logger.info(f"POST /api/matches - User: {user_identifier}, Role: {current_user.get('role', 'unknown')}")
        logger.info(f"POST /api/matches - Match data: {match.model_dump()}")

        # Validate division_id for League matches
        match_type = match_type_dao.get_match_type_by_id(match.match_type_id)
        if match_type and match_type.get("name") == "League" and match.division_id is None:
            raise HTTPException(status_code=422, detail="division_id is required for League matches")

        success = match_dao.add_match(
            home_team_id=match.home_team_id,
            away_team_id=match.away_team_id,
            match_date=match.match_date,
            home_score=match.home_score,
            away_score=match.away_score,
            season_id=match.season_id,
            age_group_id=match.age_group_id,
            match_type_id=match.match_type_id,
            division_id=match.division_id,
            status=match.status,
            created_by=current_user.get("user_id"),  # Track who created the match
            source=match.source,  # Track source (manual, match-scraper, etc.)
            external_match_id=match.external_match_id,  # Store external match identifier if provided
            scheduled_kickoff=match.scheduled_kickoff.isoformat() if match.scheduled_kickoff else None,
        )
        if success:
            return {"message": "Match added successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add match")
    except DuplicateRecordError as e:
        logger.warning(f"Duplicate match: {e.message}", details=e.details)
        raise HTTPException(status_code=409, detail=e.message) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding match: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.put("/api/matches/{match_id}")
async def update_match(
    match_id: int,
    match: EnhancedMatch,
    current_user: dict[str, Any] = Depends(require_match_management_permission),
):
    """Update an existing match (requires admin, team manager, or service account with manage_matches)."""
    try:
        # Get current match to check permissions
        current_match = match_dao.get_match_by_id(match_id)
        if not current_match:
            raise HTTPException(status_code=404, detail="Match not found")

        # Check if user can edit this match
        if not auth_manager.can_edit_match(current_user, current_match["home_team_id"], current_match["away_team_id"]):
            raise HTTPException(status_code=403, detail="You don't have permission to edit this match")

        # Validate division_id for League matches
        match_type = match_type_dao.get_match_type_by_id(match.match_type_id)
        if match_type and match_type.get("name") == "League" and match.division_id is None:
            raise HTTPException(status_code=422, detail="division_id is required for League matches")

        updated_match = match_dao.update_match(
            match_id=match_id,
            home_team_id=match.home_team_id,
            away_team_id=match.away_team_id,
            match_date=match.match_date,
            home_score=match.home_score,
            away_score=match.away_score,
            season_id=match.season_id,
            age_group_id=match.age_group_id,
            match_type_id=match.match_type_id,
            division_id=match.division_id,
            status=match.status,
            updated_by=current_user.get("user_id"),  # Track who updated the match
            external_match_id=match.external_match_id,  # Update external_match_id if provided
            scheduled_kickoff=match.scheduled_kickoff.isoformat() if match.scheduled_kickoff else None,
        )
        if updated_match:
            return {"message": "Match updated successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update match")
    except Exception as e:
        logger.error(f"Error updating match: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.patch("/api/matches/{match_id}")
async def patch_match(
    match_id: int,
    match_patch: MatchPatch,
    current_user: dict[str, Any] = Depends(require_match_management_permission),
):
    """Partially update a match (requires manage_matches permission).

    This endpoint allows updating specific fields without requiring all fields.
    Commonly used for score updates from match-scraper.
    """
    try:
        # Get current match to check permissions and get existing values
        current_match = match_dao.get_match_by_id(match_id)
        if not current_match:
            raise HTTPException(status_code=404, detail="Match not found")

        # Check if user can edit this match
        if not auth_manager.can_edit_match(current_user, current_match["home_team_id"], current_match["away_team_id"]):
            raise HTTPException(status_code=403, detail="You don't have permission to edit this match")

        # Validate scores if provided
        if match_patch.home_score is not None and match_patch.home_score < 0:
            raise HTTPException(status_code=400, detail="home_score must be non-negative")
        if match_patch.away_score is not None and match_patch.away_score < 0:
            raise HTTPException(status_code=400, detail="away_score must be non-negative")

        # Validate match_status if provided (must match database CHECK constraint)
        valid_statuses = ["scheduled", "live", "completed", "postponed", "cancelled"]
        status_to_check = match_patch.match_status or match_patch.status
        if status_to_check is not None and status_to_check not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"status must be one of: {', '.join(valid_statuses)}")

        # Build update data, using existing values for fields not provided
        update_data = {
            "match_id": match_id,
            "home_team_id": match_patch.home_team_id
            if match_patch.home_team_id is not None
            else current_match["home_team_id"],
            "away_team_id": match_patch.away_team_id
            if match_patch.away_team_id is not None
            else current_match["away_team_id"],
            "match_date": match_patch.match_date if match_patch.match_date is not None else current_match["match_date"],
            "home_score": match_patch.home_score if match_patch.home_score is not None else current_match["home_score"],
            "away_score": match_patch.away_score if match_patch.away_score is not None else current_match["away_score"],
            "season_id": match_patch.season_id if match_patch.season_id is not None else current_match["season_id"],
            "age_group_id": match_patch.age_group_id
            if match_patch.age_group_id is not None
            else current_match["age_group_id"],
            "match_type_id": match_patch.match_type_id
            if match_patch.match_type_id is not None
            else current_match["match_type_id"],
            "division_id": match_patch.division_id
            if match_patch.division_id is not None
            else current_match.get("division_id"),
            "status": match_patch.match_status
            if match_patch.match_status is not None
            else (
                match_patch.status if match_patch.status is not None else current_match.get("match_status", "scheduled")
            ),
            "external_match_id": match_patch.external_match_id
            if match_patch.external_match_id is not None
            else current_match.get("external_match_id"),
            "scheduled_kickoff": match_patch.scheduled_kickoff.isoformat()
            if match_patch.scheduled_kickoff is not None
            else current_match.get("scheduled_kickoff"),
            "updated_by": current_user.get("user_id"),
        }

        # Validate division_id for League matches (after building final update data)
        final_match_type_id = update_data["match_type_id"]
        final_division_id = update_data["division_id"]
        match_type = match_type_dao.get_match_type_by_id(final_match_type_id)
        if match_type and match_type.get("name") == "League" and final_division_id is None:
            raise HTTPException(status_code=422, detail="division_id is required for League matches")

        logger.info(f"PATCH /api/matches/{match_id} - Calling update_match with: {update_data}")
        updated_match = match_dao.update_match(**update_data)
        logger.info(f"PATCH /api/matches/{match_id} - Update success: {bool(updated_match)}")

        if updated_match:
            # Return the updated match data directly from update_match
            # This avoids read-after-write consistency issues
            logger.info(f"PATCH /api/matches/{match_id} - Returning updated match: {updated_match}")
            return updated_match
        else:
            logger.error(f"PATCH /api/matches/{match_id} - update_match returned None!")
            raise HTTPException(status_code=500, detail="Failed to update match")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error patching match: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/matches/{match_id}")
async def delete_match(match_id: int, current_user: dict[str, Any] = Depends(require_team_manager_or_admin)):
    """Delete a match (admin or team manager only)."""
    try:
        # Get current match to check permissions
        current_match = match_dao.get_match_by_id(match_id)
        if not current_match:
            raise HTTPException(status_code=404, detail="Match not found")

        # Check if user can edit this match
        if not auth_manager.can_edit_match(current_user, current_match["home_team_id"], current_match["away_team_id"]):
            raise HTTPException(status_code=403, detail="You don't have permission to delete this match")

        success = match_dao.delete_match(match_id)
        if success:
            return {"message": "Match deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete match")
    except Exception as e:
        logger.error(f"Error deleting match: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/matches/team/{team_id}")
async def get_matches_by_team(
    team_id: int,
    current_user: dict[str, Any] = Depends(get_current_user_required),
    season_id: int | None = Query(None, description="Filter by season ID"),
    age_group_id: int | None = Query(None, description="Filter by age group ID"),
):
    """Get matches for a specific team."""
    try:
        matches = match_dao.get_matches_by_team(team_id, season_id=season_id, age_group_id=age_group_id)
        # Return empty array if no matches found - this is not an error condition
        return matches if matches else []
    except Exception as e:
        logger.error(f"Error retrieving matches for team '{team_id}': {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Live Match Endpoints ===


def calculate_match_minute(match: dict) -> tuple[int | None, int | None]:
    """Calculate the current match minute based on timestamps.

    Args:
        match: Match dict with kickoff_time, halftime_start, second_half_start, half_duration

    Returns:
        Tuple of (match_minute, extra_time) where:
        - match_minute: The base minute (1-45 for first half, 46-90 for second half)
        - extra_time: Stoppage time minutes if applicable (e.g., 5 for "45+5")
    """
    from datetime import datetime

    kickoff_time = match.get("kickoff_time")
    halftime_start = match.get("halftime_start")
    second_half_start = match.get("second_half_start")
    half_duration = match.get("half_duration") or 45

    if not kickoff_time:
        return None, None

    now = datetime.now(UTC)

    # Parse kickoff time
    if isinstance(kickoff_time, str):
        kickoff_time = datetime.fromisoformat(kickoff_time.replace("Z", "+00:00"))

    # In second half
    if second_half_start:
        if isinstance(second_half_start, str):
            second_half_start = datetime.fromisoformat(second_half_start.replace("Z", "+00:00"))
        elapsed_seconds = (now - second_half_start).total_seconds()
        elapsed_minutes = int(elapsed_seconds / 60) + 1  # Round up to current minute
        total_minute = half_duration + elapsed_minutes

        # Check for stoppage time (beyond 90 for 45-min halves)
        full_time = half_duration * 2
        if total_minute > full_time:
            return full_time, total_minute - full_time
        return total_minute, None

    # At halftime - return end of first half
    if halftime_start:
        return half_duration, None

    # In first half
    elapsed_seconds = (now - kickoff_time).total_seconds()
    elapsed_minutes = int(elapsed_seconds / 60) + 1  # Round up to current minute

    # Check for stoppage time (beyond 45 for 45-min halves)
    if elapsed_minutes > half_duration:
        return half_duration, elapsed_minutes - half_duration
    return elapsed_minutes, None


@app.get("/api/matches/{match_id}/live")
async def get_live_match_state(
    match_id: int,
    current_user: dict[str, Any] = Depends(get_current_user_required),
):
    """Get full live match state including clock timestamps and recent events.

    Returns match data with clock fields for the live match view.
    """
    try:
        match_state = match_dao.get_live_match_state(match_id)
        if not match_state:
            raise HTTPException(status_code=404, detail="Match not found")

        # Get recent events
        events = match_event_dao.get_events(match_id, limit=50)
        match_state["recent_events"] = events

        return match_state
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting live match state: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/matches/{match_id}/live/clock")
async def update_match_clock(
    match_id: int,
    clock: LiveMatchClock,
    current_user: dict[str, Any] = Depends(require_match_management_permission),
):
    """Update match clock (start match, halftime, second half, end match).

    Only accessible by admins, club managers, and team managers who can edit this match.
    """
    try:
        # Get current match to check permissions
        current_match = match_dao.get_match_by_id(match_id)
        if not current_match:
            raise HTTPException(status_code=404, detail="Match not found")

        # Check if user can edit this match
        if not auth_manager.can_edit_match(current_user, current_match["home_team_id"], current_match["away_team_id"]):
            raise HTTPException(status_code=403, detail="You don't have permission to manage this match")

        # Validate action
        valid_actions = [
            "start_first_half",
            "start_halftime",
            "start_second_half",
            "end_match",
        ]
        if clock.action not in valid_actions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action. Must be one of: {', '.join(valid_actions)}",
            )

        # Update the clock
        user_id = current_user.get("user_id") or current_user.get("id")
        result = match_dao.update_match_clock(
            match_id, clock.action, updated_by=user_id, half_duration=clock.half_duration
        )
        if not result:
            raise HTTPException(status_code=500, detail="Failed to update match clock")

        # Create status change event
        action_messages = {
            "start_first_half": "Match kicked off",
            "start_halftime": "Halftime",
            "start_second_half": "Second half started",
            "end_match": "Full time",
        }
        match_event_dao.create_event(
            match_id=match_id,
            event_type="status_change",
            message=action_messages.get(clock.action, clock.action),
            created_by=user_id,
            created_by_username=current_user.get("username"),
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating match clock: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/matches/{match_id}/live/goal")
async def post_goal(
    match_id: int,
    goal: GoalEvent,
    current_user: dict[str, Any] = Depends(require_match_management_permission),
):
    """Post a goal event and update the match score.

    Only accessible by admins, club managers, and team managers who can edit this match.

    Accepts either player_id (preferred, from roster) or player_name (legacy).
    When player_id is provided, the goal is tracked in player_match_stats.
    """
    try:
        # Get current match to check permissions and current scores
        current_match = match_dao.get_match_by_id(match_id)
        if not current_match:
            raise HTTPException(status_code=404, detail="Match not found")

        # Check if user can edit this match
        if not auth_manager.can_edit_match(current_user, current_match["home_team_id"], current_match["away_team_id"]):
            raise HTTPException(status_code=403, detail="You don't have permission to manage this match")

        # Validate team_id is one of the match teams
        if goal.team_id not in [
            current_match["home_team_id"],
            current_match["away_team_id"],
        ]:
            raise HTTPException(status_code=400, detail="Team must be one of the match participants")

        # Resolve player name - either from player_id or from the request
        player_name = goal.player_name
        player_id = goal.player_id

        if player_id:
            # Validate player exists and is on the scoring team
            player = roster_dao.get_player_by_id(player_id)
            if not player:
                raise HTTPException(status_code=400, detail="Player not found")
            if player["team_id"] != goal.team_id:
                raise HTTPException(status_code=400, detail="Player must be on the scoring team")
            # Use player display name from roster
            player_name = player.get("display_name", f"#{player['jersey_number']}")

        # Require at least one identifier
        if not player_name and not player_id:
            raise HTTPException(status_code=400, detail="Either player_id or player_name is required")

        # Calculate new scores
        home_score = current_match.get("home_score") or 0
        away_score = current_match.get("away_score") or 0

        if goal.team_id == current_match["home_team_id"]:
            home_score += 1
            team_name = current_match.get("home_team_name", "Home")
        else:
            away_score += 1
            team_name = current_match.get("away_team_name", "Away")

        # Update the score
        user_id = current_user.get("user_id") or current_user.get("id")
        result = match_dao.update_match_score(match_id, home_score, away_score, updated_by=user_id)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to update match score")

        # Calculate match minute for the goal
        match_minute, extra_time = calculate_match_minute(current_match)

        # Create goal event
        goal_message = f"GOAL! {team_name} - {player_name}"
        if goal.message:
            goal_message += f" ({goal.message})"

        match_event_dao.create_event(
            match_id=match_id,
            event_type="goal",
            message=goal_message,
            created_by=user_id,
            created_by_username=current_user.get("username"),
            team_id=goal.team_id,
            player_name=player_name,
            player_id=player_id,
            match_minute=match_minute,
            extra_time=extra_time,
        )

        # Update player stats if player_id is provided
        if player_id:
            player_stats_dao.increment_goals(player_id, match_id)

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error posting goal: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/matches/{match_id}/live/message")
async def post_message(
    match_id: int,
    message: MessageEvent,
    current_user: dict[str, Any] = Depends(get_current_user_required),
):
    """Post a chat message to the live match stream.

    Any authenticated user can post messages.
    """
    try:
        # Verify match exists
        current_match = match_dao.get_match_by_id(match_id)
        if not current_match:
            raise HTTPException(status_code=404, detail="Match not found")

        # Create message event
        user_id = current_user.get("user_id") or current_user.get("id")
        event = match_event_dao.create_event(
            match_id=match_id,
            event_type="message",
            message=message.message,
            created_by=user_id,
            created_by_username=current_user.get("username"),
        )

        if not event:
            raise HTTPException(status_code=500, detail="Failed to post message")

        return event
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error posting message: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/matches/{match_id}/live/events/{event_id}")
async def delete_event(
    match_id: int,
    event_id: int,
    current_user: dict[str, Any] = Depends(require_match_management_permission),
):
    """Soft delete a match event (for moderation).

    Only accessible by admins, club managers, and team managers who can edit this match.
    """
    try:
        # Get current match to check permissions
        current_match = match_dao.get_match_by_id(match_id)
        if not current_match:
            raise HTTPException(status_code=404, detail="Match not found")

        # Check if user can edit this match
        if not auth_manager.can_edit_match(current_user, current_match["home_team_id"], current_match["away_team_id"]):
            raise HTTPException(status_code=403, detail="You don't have permission to moderate this match")

        # Verify the event belongs to this match
        event = match_event_dao.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        if event.get("match_id") != match_id:
            raise HTTPException(status_code=400, detail="Event does not belong to this match")

        # Soft delete the event
        user_id = current_user.get("user_id") or current_user.get("id")
        success = match_event_dao.soft_delete_event(event_id, deleted_by=user_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete event")

        # If it was a goal, decrement the score
        if event.get("event_type") == "goal":
            team_id = event.get("team_id")
            home_score = current_match.get("home_score") or 0
            away_score = current_match.get("away_score") or 0

            if team_id == current_match["home_team_id"] and home_score > 0:
                home_score -= 1
            elif team_id == current_match["away_team_id"] and away_score > 0:
                away_score -= 1

            match_dao.update_match_score(match_id, home_score, away_score, updated_by=user_id)

        return {"message": "Event deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting event: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/matches/{match_id}/live/events")
async def get_match_events(
    match_id: int,
    current_user: dict[str, Any] = Depends(get_current_user_required),
    limit: int = Query(50, le=100, description="Maximum events to return"),
    before_id: int | None = Query(None, description="Return events before this ID"),
):
    """Get paginated events for a match.

    Used for loading more events in the activity stream.
    """
    try:
        events = match_event_dao.get_events(match_id, limit=limit, before_id=before_id)
        return events
    except Exception as e:
        logger.error(f"Error getting match events: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Match Lineup Endpoints ===


@app.get("/api/matches/{match_id}/lineup/{team_id}")
async def get_lineup(
    match_id: int,
    team_id: int,
    current_user: dict[str, Any] = Depends(get_current_user_required),
):
    """Get lineup for a team in a specific match.

    Returns lineup with formation name and player-position assignments,
    enriched with player details (jersey number, name).
    """
    try:
        lineup = lineup_dao.get_lineup(match_id, team_id)
        return lineup
    except Exception as e:
        logger.error(f"Error getting lineup: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.put("/api/matches/{match_id}/lineup/{team_id}")
async def save_lineup(
    match_id: int,
    team_id: int,
    lineup: LineupSave,
    current_user: dict[str, Any] = Depends(require_match_management_permission),
):
    """Save or update lineup for a team in a match.

    Only accessible by admins, club managers, and team managers who can edit this match.
    When lineup is saved, also marks all assigned players as started in player_match_stats.
    """
    try:
        # Get user ID from current user
        user_id = current_user.get("id")

        # Convert Pydantic models to dicts for storage
        positions_data = [{"player_id": p.player_id, "position": p.position} for p in lineup.positions]

        # Save the lineup
        saved_lineup = lineup_dao.save_lineup(
            match_id=match_id,
            team_id=team_id,
            formation_name=lineup.formation_name,
            positions=positions_data,
            user_id=user_id,
        )

        if not saved_lineup:
            raise HTTPException(status_code=500, detail="Failed to save lineup")

        # Mark all players in lineup as started
        for position in lineup.positions:
            player_stats_dao.set_started(position.player_id, match_id, started=True)

        logger.info(
            "Lineup saved",
            match_id=match_id,
            team_id=team_id,
            formation=lineup.formation_name,
            player_count=len(lineup.positions),
        )

        return saved_lineup
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving lineup: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Enhanced League Table Endpoint ===


@app.get("/api/table")
async def get_table(
    current_user: dict[str, Any] = Depends(get_current_user_required),
    season_id: int | None = Query(None, description="Filter by season ID"),
    age_group_id: int | None = Query(None, description="Filter by age group ID"),
    division_id: int | None = Query(None, description="Filter by division ID"),
    match_type: str | None = Query("League", description="Match type (League, Tournament, etc.)"),
):
    """Get league table with enhanced filtering."""
    try:
        # If no season specified, use current season (or most recent as fallback)
        if not season_id:
            current_season = season_dao.get_current_season()
            if current_season:
                season_id = current_season["id"]
            else:
                # Fallback to most recent season (sorted by start_date desc)
                seasons = season_dao.get_all_seasons()
                if seasons:
                    season_id = seasons[0]["id"]

        table = match_dao.get_league_table(
            season_id=season_id,
            age_group_id=age_group_id,
            division_id=division_id,
            match_type=match_type,
        )

        logger.info(
            "League table query",
            season_id=season_id,
            age_group_id=age_group_id,
            division_id=division_id,
            match_type=match_type,
            rows_returned=len(table) if isinstance(table, list) else "N/A",
        )

        return table
    except Exception as e:
        logger.error(f"Error generating league table: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/leaderboards/goals")
async def get_goals_leaderboard(
    current_user: dict[str, Any] = Depends(get_current_user_required),
    season_id: int = Query(..., description="Season ID (required)"),
    league_id: int | None = Query(None, description="Filter by league ID"),
    division_id: int | None = Query(None, description="Filter by division ID"),
    age_group_id: int | None = Query(None, description="Filter by age group ID"),
    limit: int = Query(50, description="Maximum results", ge=1, le=100),
):
    """Get goals leaderboard - top scorers filtered by season/league/division/age group."""
    try:
        leaderboard = player_stats_dao.get_goals_leaderboard(
            season_id=season_id,
            league_id=league_id,
            division_id=division_id,
            age_group_id=age_group_id,
            limit=limit,
        )

        logger.info(
            "Goals leaderboard query",
            season_id=season_id,
            league_id=league_id,
            division_id=division_id,
            age_group_id=age_group_id,
            limit=limit,
            rows_returned=len(leaderboard),
        )

        return leaderboard
    except Exception as e:
        logger.error(f"Error generating goals leaderboard: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Admin CRUD Endpoints ===


# Age Groups CRUD
@app.post("/api/age-groups")
async def create_age_group(age_group: AgeGroupCreate, current_user: dict[str, Any] = Depends(require_admin)):
    """Create a new age group (admin only)."""
    try:
        result = season_dao.create_age_group(age_group.name)
        return result
    except Exception as e:
        logger.error(f"Error creating age group: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.put("/api/age-groups/{age_group_id}")
async def update_age_group(
    age_group_id: int,
    age_group: AgeGroupUpdate,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Update an age group (admin only)."""
    try:
        result = season_dao.update_age_group(age_group_id, age_group.name)
        if not result:
            raise HTTPException(status_code=404, detail="Age group not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating age group: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/age-groups/{age_group_id}")
async def delete_age_group(age_group_id: int, current_user: dict[str, Any] = Depends(require_admin)):
    """Delete an age group (admin only)."""
    try:
        result = season_dao.delete_age_group(age_group_id)
        if not result:
            raise HTTPException(status_code=404, detail="Age group not found")
        return {"message": "Age group deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting age group: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# Seasons CRUD
@app.post("/api/seasons")
async def create_season(season: SeasonCreate, current_user: dict[str, Any] = Depends(require_admin)):
    """Create a new season (admin only)."""
    try:
        result = season_dao.create_season(season.name, season.start_date, season.end_date)
        return result
    except Exception as e:
        logger.error(f"Error creating season: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.put("/api/seasons/{season_id}")
async def update_season(season_id: int, season: SeasonUpdate, current_user: dict[str, Any] = Depends(require_admin)):
    """Update a season (admin only)."""
    try:
        result = season_dao.update_season(season_id, season.name, season.start_date, season.end_date)
        if not result:
            raise HTTPException(status_code=404, detail="Season not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating season: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/seasons/{season_id}")
async def delete_season(season_id: int, current_user: dict[str, Any] = Depends(require_admin)):
    """Delete a season (admin only)."""
    try:
        result = season_dao.delete_season(season_id)
        if not result:
            raise HTTPException(status_code=404, detail="Season not found")
        return {"message": "Season deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting season: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# Leagues CRUD
@app.get("/api/leagues")
async def get_leagues():
    """Get all leagues (public access)."""
    try:
        leagues = league_dao.get_all_leagues()
        return leagues
    except Exception as e:
        logger.error(f"Error fetching leagues: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/leagues/{league_id}")
async def get_league(league_id: int):
    """Get league by ID (public access)."""
    try:
        league = league_dao.get_league_by_id(league_id)
        if not league:
            raise HTTPException(status_code=404, detail="League not found")
        return league
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching league {league_id}: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/leagues")
async def create_league(league: LeagueCreate, current_user: dict[str, Any] = Depends(require_admin)):
    """Create a new league (admin only)."""
    try:
        league_data = league.model_dump()
        result = league_dao.create_league(league_data)
        return result
    except Exception as e:
        logger.error(f"Error creating league: {e!s}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.put("/api/leagues/{league_id}")
async def update_league(
    league_id: int,
    league: LeagueUpdate,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Update a league (admin only)."""
    try:
        # Only include fields that were actually provided
        league_data = league.model_dump(exclude_unset=True)
        result = league_dao.update_league(league_id, league_data)
        if not result:
            raise HTTPException(status_code=404, detail="League not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating league: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/leagues/{league_id}")
async def delete_league(league_id: int, current_user: dict[str, Any] = Depends(require_admin)):
    """Delete a league (admin only). Will fail if divisions exist."""
    try:
        league_dao.delete_league(league_id)
        return {"message": "League deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting league: {e!s}", exc_info=True)
        if "foreign key" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail="Cannot delete league with existing divisions. Delete divisions first.",
            ) from e
        raise HTTPException(status_code=500, detail=str(e)) from e


# Divisions CRUD
@app.post("/api/divisions")
async def create_division(division: DivisionCreate, current_user: dict[str, Any] = Depends(require_admin)):
    """Create a new division (admin only)."""
    try:
        division_data = division.model_dump()
        result = league_dao.create_division(division_data)
        return result
    except Exception as e:
        logger.error(f"Error creating division: {e!s}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.put("/api/divisions/{division_id}")
async def update_division(
    request: Request,
    division_id: int,
    division: DivisionUpdate,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Update a division (admin only)."""
    try:
        division_data = division.model_dump(exclude_unset=True)
        result = league_dao.update_division(division_id, division_data)
        if not result:
            raise HTTPException(status_code=404, detail="Division not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating division: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/divisions/{division_id}")
async def delete_division(division_id: int, current_user: dict[str, Any] = Depends(require_admin)):
    """Delete a division (admin only)."""
    try:
        result = league_dao.delete_division(division_id)
        if not result:
            raise HTTPException(status_code=404, detail="Division not found")
        return {"message": "Division deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting division: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# Teams CRUD (update existing)
@app.put("/api/teams/{team_id}")
async def update_team(
    request: Request,
    team_id: int,
    team: TeamUpdate,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Update a team (admin only)."""
    try:
        logger.info(f"Updating team {team_id}: name={team.name}, club_id={team.club_id}")
        result = team_dao.update_team(team_id, team.name, team.city, team.academy_team, team.club_id)
        if not result:
            raise HTTPException(status_code=404, detail="Team not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating team: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/teams/{team_id}")
async def delete_team(team_id: int, current_user: dict[str, Any] = Depends(require_admin)):
    """Delete a team (admin only)."""
    try:
        result = team_dao.delete_team(team_id)
        if not result:
            raise HTTPException(status_code=404, detail="Team not found")
        return {"message": "Team deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting team: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/teams/{team_id}/match-types")
async def add_team_match_type_participation(
    team_id: int,
    mapping: TeamMatchTypeMapping,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Add a team's participation in a specific match type and age group (admin only)."""
    try:
        success = team_dao.add_team_match_type_participation(team_id, mapping.match_type_id, mapping.age_group_id)
        if success:
            return {"message": "Team match type participation added successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add team match type participation")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding team match type participation: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/teams/{team_id}/match-types/{match_type_id}/{age_group_id}")
async def remove_team_match_type_participation(
    team_id: int,
    match_type_id: int,
    age_group_id: int,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Remove a team's participation in a specific match type and age group (admin only)."""
    try:
        success = team_dao.remove_team_match_type_participation(team_id, match_type_id, age_group_id)
        if success:
            return {"message": "Team match type participation removed successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to remove team match type participation")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing team match type participation: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Club Endpoints ===


@app.get("/api/clubs")
async def get_clubs(include_teams: bool = True, current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get all clubs.

    Args:
        include_teams: If true, enriches clubs with their teams list (default: true)

    Returns:
        List of clubs with optional team details
    """
    try:
        # Get all clubs from clubs table
        logger.info(f"/api/clubs: Calling get_all_clubs DAO with include_team_counts: {not include_teams}")
        clubs = club_dao.get_all_clubs(include_team_counts=not include_teams)
        logger.info(f"/api/clubs: Fetched {len(clubs)} clubs")

        if not include_teams:
            # Return clubs without team details (faster for dropdowns)
            return clubs

        # Enrich with team details if requested (batched)
        club_ids = [club["id"] for club in clubs]
        teams = team_dao.get_teams_by_club_ids(club_ids)
        teams_by_club_id: dict[int, list[dict]] = {}
        for team in teams:
            club_id = team.get("club_id")
            if club_id is None:
                continue
            teams_by_club_id.setdefault(club_id, []).append(team)

        enriched_clubs = []
        for club in clubs:
            club_teams = teams_by_club_id.get(club["id"], [])
            enriched_club = {
                **club,
                "teams": club_teams,
                "team_count": len(club_teams),
            }
            enriched_clubs.append(enriched_club)
            logger.debug(f"Club '{club.get('name')}' has {len(club_teams)} teams")

        return enriched_clubs
    except Exception as e:
        logger.error(f"Error fetching clubs: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/clubs/{club_id}")
async def get_club(club_id: int, current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get a single club by ID."""
    try:
        clubs = club_dao.get_all_clubs()
        club = next((c for c in clubs if c["id"] == club_id), None)
        if not club:
            raise HTTPException(status_code=404, detail=f"Club with id {club_id} not found")
        return club
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching club: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/clubs/{club_id}/teams")
async def get_club_teams(
    club_id: int,
    include_stats: bool = True,
    current_user: dict[str, Any] = Depends(get_current_user_required),
):
    """Get all teams for a specific club."""
    try:
        teams = team_dao.get_club_teams(club_id) if include_stats else team_dao.get_club_teams_basic(club_id)
        if not teams:
            raise HTTPException(status_code=404, detail=f"Club with id {club_id} not found")

        return teams
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching club teams: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/clubs")
async def create_club(club: Club, current_user: dict[str, Any] = Depends(require_admin)):
    """Create a new club (admin only)."""
    try:
        new_club = club_dao.create_club(
            name=club.name,
            city=club.city,
            website=club.website,
            description=club.description,
            logo_url=club.logo_url,
            primary_color=club.primary_color,
            secondary_color=club.secondary_color,
        )
        logger.info(f"Created new club: {new_club['name']}")
        return new_club
    except Exception as e:
        error_str = str(e)
        logger.error(f"Error creating club: {error_str}", exc_info=True)

        # Check for duplicate key constraint violation
        if "duplicate key value violates unique constraint" in error_str.lower():
            if "clubs_name_unique" in error_str.lower() or "clubs_name_key" in error_str.lower():
                raise HTTPException(
                    status_code=409,
                    detail=f"A club with the name '{club.name}' already exists. Please use a different name.",
                ) from e
            else:
                raise HTTPException(status_code=409, detail="A club with this information already exists.") from e

        # For any other unexpected errors, return 500
        raise HTTPException(status_code=500, detail="An unexpected error occurred while creating the club.") from e


@app.put("/api/clubs/{club_id}")
async def update_club(club_id: int, club: Club, current_user: dict[str, Any] = Depends(require_admin)):
    """Update a club (admin only)."""
    try:
        updated_club = club_dao.update_club(
            club_id=club_id,
            name=club.name,
            city=club.city,
            website=club.website,
            description=club.description,
            logo_url=club.logo_url,
            primary_color=club.primary_color,
            secondary_color=club.secondary_color,
        )
        if not updated_club:
            raise HTTPException(status_code=404, detail=f"Club with id {club_id} not found")
        logger.info(f"Updated club: {updated_club['name']}")
        return updated_club
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating club: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/clubs/{club_id}/logo")
async def upload_club_logo(
    club_id: int,
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Upload a logo image for a club (admin only).

    Uploads the image to Supabase Storage and returns the public URL.
    Accepted formats: PNG, JPG/JPEG. Max size: 2MB.
    """
    # Validate file type
    allowed_types = ["image/png", "image/jpeg", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: PNG, JPG. Got: {file.content_type}",
        )

    # Read file content
    content = await file.read()

    # Validate file size (2MB max)
    max_size = 2 * 1024 * 1024  # 2MB
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is 2MB. Got: {len(content) / 1024 / 1024:.2f}MB",
        )

    # Determine file extension
    ext = "png" if file.content_type == "image/png" else "jpg"
    file_path = f"{club_id}.{ext}"

    try:
        # Get the Supabase client from the DAO
        storage = match_dao.client.storage

        # Upload to club-logos bucket (upsert to overwrite existing)
        storage.from_("club-logos").upload(
            file_path, content, file_options={"content-type": file.content_type, "upsert": "true"}
        )

        # Get public URL
        public_url = storage.from_("club-logos").get_public_url(file_path)

        # Update the club with the new logo URL
        updated_club = club_dao.update_club(club_id=club_id, logo_url=public_url)

        if not updated_club:
            raise HTTPException(status_code=404, detail=f"Club with id {club_id} not found")

        logger.info(f"Uploaded logo for club {club_id}: {public_url}")
        return {"logo_url": public_url, "club": updated_club}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading club logo: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload logo: {e!s}") from e


@app.delete("/api/clubs/{club_id}")
async def delete_club(club_id: int, current_user: dict[str, Any] = Depends(require_admin)):
    """Delete a club (admin only).

    Note: This will fail if there are teams still associated with this club.
    """
    try:
        success = club_dao.delete_club(club_id)
        if success:
            logger.info(f"Deleted club with id {club_id}")
            return {"message": "Club deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Club with id {club_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        logger.error(f"Error deleting club: {error_str}", exc_info=True)

        # Check if it's a foreign key constraint violation
        if "foreign key constraint" in error_str.lower() or "violates" in error_str.lower():
            raise HTTPException(
                status_code=409,
                detail="Cannot delete club because it has teams associated with it. Remove team associations first.",
            ) from e

        raise HTTPException(status_code=500, detail="An unexpected error occurred while deleting the club.") from e


# Team Mappings CRUD
@app.post("/api/team-mappings")
async def create_team_mapping(
    mapping: TeamMappingCreate,
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin),
):
    """Create a team mapping (admin or club_manager for their club's teams)."""
    try:
        user_role = current_user.get("role")
        user_club_id = current_user.get("club_id")

        # Club managers can only add mappings to their own club's teams
        if user_role == "club_manager":
            team = team_dao.get_team_by_id(mapping.team_id)
            if not team or team.get("club_id") != user_club_id:
                raise HTTPException(status_code=403, detail="You can only manage teams in your club")

        result = team_dao.create_team_mapping(mapping.team_id, mapping.age_group_id, mapping.division_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating team mapping: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/team-mappings/{team_id}/{age_group_id}/{division_id}")
async def delete_team_mapping(
    team_id: int,
    age_group_id: int,
    division_id: int,
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin),
):
    """Delete a team mapping (admin or club_manager for their club's teams)."""
    try:
        user_role = current_user.get("role")
        user_club_id = current_user.get("club_id")

        # Club managers can only delete mappings from their own club's teams
        if user_role == "club_manager":
            team = team_dao.get_team_by_id(team_id)
            if not team or team.get("club_id") != user_club_id:
                raise HTTPException(status_code=403, detail="You can only manage teams in your club")

        result = team_dao.delete_team_mapping(team_id, age_group_id, division_id)
        if not result:
            raise HTTPException(status_code=404, detail="Team mapping not found")
        return {"message": "Team mapping deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting team mapping: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Match-Scraper Integration Endpoints ===


@app.post("/api/matches/submit")
async def submit_match_async(
    match_data: MatchSubmissionData,
    current_user: dict[str, Any] = Depends(require_match_management_permission),
):
    """
    Submit match data for async processing via Celery.

    This endpoint queues match data to Celery workers for:
    - Validation
    - Team lookup
    - Duplicate detection
    - Database insertion

    Returns a task ID for tracking the processing status.

    Requires: admin, team-manager, or service account with manage_matches permission
    """
    try:
        # Import Celery task
        from celery_tasks.match_tasks import process_match_data

        # Log the submission
        user_identifier = current_user.get("username") or current_user.get("service_name", "unknown")
        logger.info(f"POST /api/matches/submit - User: {user_identifier}")
        logger.info(f"POST /api/matches/submit - Match: {match_data.home_team} vs {match_data.away_team}")

        # Convert Pydantic model to dict for Celery
        match_dict = match_data.model_dump()

        # Queue the task to Celery
        task = process_match_data.delay(match_dict)

        logger.info(f"Queued match processing task: {task.id}")

        return {
            "success": True,
            "message": "Match data queued for processing",
            "task_id": task.id,
            "status_url": f"/api/matches/task/{task.id}",
            "match": {
                "home_team": match_data.home_team,
                "away_team": match_data.away_team,
                "match_date": match_data.match_date,
            },
        }

    except Exception as e:
        logger.error(f"Error submitting match for async processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to queue match: {e!s}") from e


@app.get("/api/matches/task/{task_id}")
async def get_task_status(task_id: str, current_user: dict[str, Any] = Depends(require_match_management_permission)):
    """
    Get the status of a queued match processing task.

    Returns:
    - state: PENDING, STARTED, SUCCESS, FAILURE, RETRY
    - result: Task result if completed successfully
    - error: Error message if failed
    """
    try:
        from celery.result import AsyncResult

        task = AsyncResult(task_id)

        response = {
            "task_id": task_id,
            "state": task.state,
            "ready": task.ready(),
        }

        if task.ready():
            if task.successful():
                response["result"] = task.result
                response["message"] = "Task completed successfully"
            else:
                response["error"] = str(task.info)
                response["message"] = "Task failed"
        else:
            response["message"] = "Task is still processing"

        return response

    except Exception as e:
        logger.error(f"Error retrieving task status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {e!s}") from e


@app.post("/api/match-scraper/matches")
async def add_or_update_scraped_match(
    request: Request,
    match: EnhancedMatch,
    external_match_id: str,
    current_user: dict[str, Any] = Depends(require_match_management_permission),
):
    """Add or update a match from match-scraper with intelligent duplicate handling."""
    try:
        logger.info(f"POST /api/match-scraper/matches - External Match ID: {external_match_id}")
        logger.info(f"POST /api/match-scraper/matches - Match data: {match.model_dump()}")

        # Validate division_id for League matches
        match_type = match_type_dao.get_match_type_by_id(match.match_type_id)
        if match_type and match_type.get("name") == "League" and match.division_id is None:
            raise HTTPException(status_code=422, detail="division_id is required for League matches")

        # Check if match already exists by external_match_id
        existing_match_response = await check_match(
            date=match.match_date,
            homeTeam=str(match.home_team_id),
            awayTeam=str(match.away_team_id),
            season_id=match.season_id,
            age_group_id=match.age_group_id,
            match_type_id=match.match_type_id,
            division_id=match.division_id,
            external_match_id=external_match_id,
        )

        if existing_match_response["exists"]:
            existing_match_id = existing_match_response["match_id"]
            logger.info(f"Updating existing match {existing_match_id} with external_match_id {external_match_id}")

            # Update existing match
            updated_match = match_dao.update_match(
                match_id=existing_match_id,
                home_team_id=match.home_team_id,
                away_team_id=match.away_team_id,
                match_date=match.match_date,
                home_score=match.home_score,
                away_score=match.away_score,
                season_id=match.season_id,
                age_group_id=match.age_group_id,
                match_type_id=match.match_type_id,
                division_id=match.division_id,
                updated_by=current_user.get("user_id"),  # Track scraper updates
            )

            if updated_match:
                return {
                    "message": "Match updated successfully",
                    "action": "updated",
                    "match_id": existing_match_id,
                    "external_match_id": external_match_id,
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to update match")
        else:
            logger.info(f"Creating new match with external_match_id {external_match_id}")

            # Create new match with external_match_id
            success = match_dao.add_match_with_external_id(
                home_team_id=match.home_team_id,
                away_team_id=match.away_team_id,
                match_date=match.match_date,
                home_score=match.home_score,
                away_score=match.away_score,
                season_id=match.season_id,
                age_group_id=match.age_group_id,
                match_type_id=match.match_type_id,
                division_id=match.division_id,
                external_match_id=external_match_id,
                created_by=current_user.get("user_id"),  # Track scraper creation
                source="match-scraper",  # Mark as scraped data
            )

            if success:
                return {
                    "message": "Match created successfully",
                    "action": "created",
                    "external_match_id": external_match_id,
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to create match")

    except Exception as e:
        logger.error(f"Error in match-scraper match endpoint: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Backward Compatibility Endpoints ===


@app.get("/api/check-match")
async def check_match(
    current_user: dict[str, Any] = Depends(get_current_user_required),
    date: str = Query(..., description="Match date"),
    homeTeam: str = Query(..., description="Home team name"),
    awayTeam: str = Query(..., description="Away team name"),
    season_id: int | None = None,
    age_group_id: int | None = None,
    match_type_id: int | None = None,
    division_id: int | None = None,
    external_match_id: str | None = None,
):
    """Enhanced match existence check with comprehensive duplicate detection."""
    try:
        # First check by external_match_id if provided (for external systems like match-scraper)
        if external_match_id:
            matches = match_dao.get_all_matches()
            for match in matches:
                if match.get("external_match_id") == external_match_id:
                    return {
                        "exists": True,
                        "match_id": match.get("id"),
                        "match": match,
                        "match_type": "external_match_id",
                    }

        # Check for duplicate based on comprehensive match context
        matches = match_dao.get_all_matches()
        for match in matches:
            # Basic match: date and teams
            basic_match = (
                str(match.get("match_date")) == date
                and str(match.get("home_team_id")) == homeTeam
                and str(match.get("away_team_id")) == awayTeam
            )

            if basic_match:
                # Enhanced match: include season, age group, match type, division if provided
                enhanced_match = True

                if season_id and match.get("season_id") != season_id:
                    enhanced_match = False
                if age_group_id and match.get("age_group_id") != age_group_id:
                    enhanced_match = False
                if match_type_id and match.get("match_type_id") != match_type_id:
                    enhanced_match = False
                if division_id and match.get("division_id") != division_id:
                    enhanced_match = False

                return {
                    "exists": True,
                    "match_id": match.get("id"),
                    "match": match,
                    "match_type": "enhanced_context" if enhanced_match else "basic_context",
                    "enhanced_match": enhanced_match,
                }

        return {"exists": False}
    except Exception as e:
        logger.error(f"Error checking match: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Team Roster & Player Profile Endpoints ===


@app.get("/api/teams/{team_id}/players")
async def get_team_players(team_id: int, current_user: dict[str, Any] = Depends(get_current_user_required)):
    """
    Get all players on a team for the team roster page.

    Players can view rosters for any team within their club.
    This allows browsing teammates across different age groups.

    Returns player data needed for player cards:
    - id, display_name, player_number, positions
    - photo fields (photo_1_url, etc.)
    - customization fields (overlay_style, colors)
    - social media handles
    """
    try:
        # Get the requested team's club_id
        requested_team = team_dao.get_team_by_id(team_id)
        if not requested_team:
            raise HTTPException(status_code=404, detail="Team not found")
        requested_club_id = requested_team.get("club_id")

        # Get user's club_id from their profile's team_id or club_id
        user_club_ids = set()

        # Check user's direct club_id (for club managers/fans)
        if current_user.get("club_id"):
            user_club_ids.add(current_user["club_id"])

        # Check user's team's club_id (for team players/managers/fans)
        if current_user.get("team_id"):
            user_team = team_dao.get_team_by_id(current_user["team_id"])
            if user_team and user_team.get("club_id"):
                user_club_ids.add(user_team["club_id"])

        # Authorization: user must belong to a team in the same club
        if requested_club_id not in user_club_ids:
            raise HTTPException(status_code=403, detail="You can only view rosters for teams in your club")

        # Get team info with relationships
        team = team_dao.get_team_with_details(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Get players
        players = player_dao.get_team_players(team_id)

        return {"success": True, "team": team, "players": players}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting team players: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get team players") from e


# === Roster Management Endpoints (new players table) ===


@app.get("/api/teams/{team_id}/roster")
async def get_team_roster(
    team_id: int,
    season_id: int = Query(..., description="Season ID"),
    current_user: dict[str, Any] = Depends(get_current_user_required),
):
    """
    Get team roster from the players table.

    Returns roster entries with jersey numbers, names, and account status.
    Managers can view any team's roster for stat entry purposes.
    """
    try:
        # Verify team exists
        team = team_dao.get_team_by_id(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Get roster from players table
        roster = roster_dao.get_team_roster(team_id, season_id)

        return {"success": True, "team_id": team_id, "season_id": season_id, "roster": roster}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting team roster: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get team roster") from e


@app.post("/api/teams/{team_id}/roster")
async def create_roster_entry(
    team_id: int,
    player: RosterPlayerCreate,
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin),
):
    """
    Add a single player to the team roster.

    Requires admin or team_manager role.
    Jersey number must be unique within the team/season.
    """
    try:
        # Verify team exists
        team = team_dao.get_team_by_id(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Check if jersey number is already taken
        existing = roster_dao.get_player_by_jersey(team_id, player.season_id, player.jersey_number)
        if existing:
            raise HTTPException(status_code=409, detail=f"Jersey number {player.jersey_number} is already taken")

        # Create roster entry
        created = roster_dao.create_player(
            team_id=team_id,
            season_id=player.season_id,
            jersey_number=player.jersey_number,
            first_name=player.first_name,
            last_name=player.last_name,
            positions=player.positions,
            created_by=current_user["user_id"],
        )

        if not created:
            raise HTTPException(status_code=500, detail="Failed to create roster entry")

        return {"success": True, "player": created}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating roster entry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create roster entry") from e


@app.post("/api/teams/{team_id}/roster/bulk")
async def bulk_create_roster(
    team_id: int,
    data: BulkRosterCreate,
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin),
):
    """
    Bulk create roster entries.

    Requires admin or team_manager role.
    Skips duplicates (existing jersey numbers).
    """
    try:
        # Verify team exists
        team = team_dao.get_team_by_id(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Get existing roster to filter duplicates
        existing_roster = roster_dao.get_team_roster(team_id, data.season_id)
        existing_numbers = {p["jersey_number"] for p in existing_roster}

        # Filter out duplicates
        new_players = [p.model_dump() for p in data.players if p.jersey_number not in existing_numbers]

        if not new_players:
            return {
                "success": True,
                "created": [],
                "skipped": len(data.players),
                "message": "All jersey numbers already exist",
            }

        # Bulk create
        created = roster_dao.bulk_create_players(
            team_id=team_id,
            season_id=data.season_id,
            players=new_players,
            created_by=current_user["user_id"],
        )

        return {
            "success": True,
            "created": created,
            "created_count": len(created),
            "skipped_count": len(data.players) - len(new_players),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk creating roster: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to bulk create roster") from e


@app.put("/api/teams/{team_id}/roster/{player_id}")
async def update_roster_entry(
    team_id: int,
    player_id: int,
    data: RosterPlayerUpdate,
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin),
):
    """
    Update a roster entry's name or positions.

    Requires admin or team_manager role.
    """
    try:
        # Verify player exists and belongs to team
        player = roster_dao.get_player_by_id(player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        if player["team_id"] != team_id:
            raise HTTPException(status_code=404, detail="Player not on this team")

        # Update
        updated = roster_dao.update_player(
            player_id=player_id,
            first_name=data.first_name,
            last_name=data.last_name,
            positions=data.positions,
        )

        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update roster entry")

        return {"success": True, "player": updated}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating roster entry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update roster entry") from e


@app.put("/api/teams/{team_id}/roster/{player_id}/number")
async def update_jersey_number(
    team_id: int,
    player_id: int,
    data: JerseyNumberUpdate,
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin),
):
    """
    Change a player's jersey number.

    Requires admin or team_manager role.
    New number must not already be taken.
    """
    try:
        # Verify player exists and belongs to team
        player = roster_dao.get_player_by_id(player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        if player["team_id"] != team_id:
            raise HTTPException(status_code=404, detail="Player not on this team")

        # Check if new number is available
        existing = roster_dao.get_player_by_jersey(team_id, player["season_id"], data.new_number)
        if existing and existing["id"] != player_id:
            raise HTTPException(status_code=409, detail=f"Jersey number {data.new_number} is already taken")

        # Update number
        updated = roster_dao.update_jersey_number(player_id, data.new_number)

        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update jersey number")

        return {"success": True, "player": updated}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating jersey number: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update jersey number") from e


@app.post("/api/teams/{team_id}/roster/renumber")
async def bulk_renumber_roster(
    team_id: int,
    data: BulkRenumberRequest,
    season_id: int = Query(..., description="Season ID"),
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin),
):
    """
    Bulk renumber players (for roster reshuffles).

    Requires admin or team_manager role.
    Handles swaps without constraint violations.
    """
    try:
        # Verify team exists
        team = team_dao.get_team_by_id(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Verify all players exist and belong to team
        for change in data.changes:
            player = roster_dao.get_player_by_id(change.player_id)
            if not player:
                raise HTTPException(status_code=404, detail=f"Player {change.player_id} not found")
            if player["team_id"] != team_id:
                raise HTTPException(status_code=400, detail=f"Player {change.player_id} not on this team")

        # Perform bulk renumber
        success = roster_dao.bulk_renumber(
            team_id=team_id, season_id=season_id, changes=[c.model_dump() for c in data.changes]
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to renumber roster")

        # Return updated roster
        roster = roster_dao.get_team_roster(team_id, season_id)

        return {"success": True, "roster": roster}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renumbering roster: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to renumber roster") from e


@app.delete("/api/teams/{team_id}/roster/{player_id}")
async def delete_roster_entry(
    team_id: int,
    player_id: int,
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin),
):
    """
    Remove a player from the roster (soft delete).

    Requires admin or team_manager role.
    """
    try:
        # Verify player exists and belongs to team
        player = roster_dao.get_player_by_id(player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        if player["team_id"] != team_id:
            raise HTTPException(status_code=404, detail="Player not on this team")

        # Soft delete
        success = roster_dao.delete_player(player_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete roster entry")

        return {"success": True, "message": "Player removed from roster"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting roster entry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete roster entry") from e


# =============================================================================
# Player Stats Endpoints
# =============================================================================


@app.get("/api/roster/{player_id}/stats")
async def get_player_stats(
    player_id: int,
    season_id: int = Query(..., description="Season ID for stats"),
):
    """
    Get aggregated stats for a roster player in a season.

    Returns games_played, games_started, total_minutes, total_goals.
    Public endpoint - stats are visible to everyone.
    """
    try:
        # Verify player exists
        player = roster_dao.get_player_by_id(player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")

        # Get season stats
        stats = player_stats_dao.get_player_season_stats(player_id, season_id)

        return {
            "player_id": player_id,
            "jersey_number": player.get("jersey_number"),
            "display_name": player.get("display_name"),
            "season_id": season_id,
            "stats": stats
            or {
                "games_played": 0,
                "games_started": 0,
                "total_minutes": 0,
                "total_goals": 0,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting player stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get player stats") from e


@app.get("/api/teams/{team_id}/stats")
async def get_team_stats(
    team_id: int,
    season_id: int = Query(..., description="Season ID for stats"),
):
    """
    Get aggregated stats for all players on a team in a season.

    Returns list of players with their stats, sorted by goals (descending).
    Public endpoint - stats are visible to everyone.
    """
    try:
        # Verify team exists
        team = team_dao.get_team_by_id(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Get team stats
        stats = player_stats_dao.get_team_stats(team_id, season_id)

        return {
            "team_id": team_id,
            "team_name": team.get("name"),
            "season_id": season_id,
            "players": stats,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting team stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get team stats") from e


@app.get("/api/me/player-stats")
async def get_my_player_stats(
    season_id: int = Query(..., description="Season ID for stats"),
    current_user: dict[str, Any] = Depends(get_current_user_required),
):
    """
    Get the current user's individual player stats for a season.

    Looks up the player record linked to the user's profile
    and returns their aggregated stats for the specified season.

    Returns:
        - player_id: The roster entry ID
        - jersey_number: Player's jersey number
        - season_id: The season these stats are for
        - stats: games_played, games_started, total_minutes, total_goals
        - linked: Whether the user has a linked player record
    """
    try:
        user_id = current_user["user_id"]

        # Find player record linked to this user
        player = roster_dao.get_player_by_user_profile_id(user_id)

        if not player:
            # User has no linked player record - return empty stats
            return {
                "player_id": None,
                "jersey_number": None,
                "display_name": None,
                "season_id": season_id,
                "stats": {
                    "games_played": 0,
                    "games_started": 0,
                    "total_minutes": 0,
                    "total_goals": 0,
                },
                "linked": False,
            }

        player_id = player["id"]

        # Get season stats
        stats = player_stats_dao.get_player_season_stats(player_id, season_id)

        return {
            "player_id": player_id,
            "jersey_number": player.get("jersey_number"),
            "display_name": player.get("display_name"),
            "season_id": season_id,
            "stats": stats
            or {
                "games_played": 0,
                "games_started": 0,
                "total_minutes": 0,
                "total_goals": 0,
            },
            "linked": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting my player stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get player stats") from e


@app.get("/api/players/{user_id}/profile")
async def get_player_profile(user_id: str, current_user: dict[str, Any] = Depends(get_current_user_required)):
    """
    Get a specific player's full profile for the player detail view.

    Players can view profiles of anyone in their club.
    This allows browsing teammates across different age groups.

    Returns full profile data including:
    - Profile info (display_name, number, positions)
    - Photos and customization
    - Social media handles
    - Team info
    - Recent games (player's team matches)
    """
    try:
        # Get the target player's profile first
        target_profile = player_dao.get_user_profile_with_relationships(user_id)
        if not target_profile:
            raise HTTPException(status_code=404, detail="Player not found")

        # Allow viewing own profile
        if user_id == current_user["user_id"]:
            pass  # No authorization check needed
        else:
            # Get target player's teams and club IDs
            target_teams = player_dao.get_all_current_player_teams(user_id)
            target_club_ids = set()
            for team_entry in target_teams:
                team_data = team_entry.get("team", {})
                club_data = team_data.get("club", {})
                if club_data and club_data.get("id"):
                    target_club_ids.add(club_data["id"])

            # Get current user's teams and club IDs
            user_teams = player_dao.get_all_current_player_teams(current_user["user_id"])
            user_club_ids = set()
            for team_entry in user_teams:
                team_data = team_entry.get("team", {})
                club_data = team_data.get("club", {})
                if club_data and club_data.get("id"):
                    user_club_ids.add(club_data["id"])

            # Authorization: must share at least one club
            if not (user_club_ids & target_club_ids):
                raise HTTPException(status_code=403, detail="You can only view profiles of players in your club")

        target_team_id = target_profile.get("team_id")

        # Get recent games for the player's team (if they have a team)
        recent_games = []
        if target_team_id:
            try:
                # Get matches for the team (already sorted by date desc, take first 5)
                matches = match_dao.get_matches_by_team(target_team_id)[:5]
                for match in matches:
                    recent_games.append(
                        {
                            "id": match.get("id"),
                            "match_date": match.get("match_date"),
                            "home_team": match.get("home_team"),
                            "away_team": match.get("away_team"),
                            "home_score": match.get("home_score"),
                            "away_score": match.get("away_score"),
                            "status": match.get("status"),
                        }
                    )
            except Exception as e:
                logger.warning(f"Could not fetch recent games: {e}")

        return {
            "success": True,
            "player": {
                "id": target_profile.get("id"),
                "display_name": target_profile.get("display_name"),
                "player_number": target_profile.get("player_number"),
                "positions": target_profile.get("positions"),
                # Photo fields
                "photo_1_url": target_profile.get("photo_1_url"),
                "photo_2_url": target_profile.get("photo_2_url"),
                "photo_3_url": target_profile.get("photo_3_url"),
                "profile_photo_slot": target_profile.get("profile_photo_slot"),
                # Customization
                "overlay_style": target_profile.get("overlay_style"),
                "primary_color": target_profile.get("primary_color"),
                "text_color": target_profile.get("text_color"),
                "accent_color": target_profile.get("accent_color"),
                # Social media
                "instagram_handle": target_profile.get("instagram_handle"),
                "snapchat_handle": target_profile.get("snapchat_handle"),
                "tiktok_handle": target_profile.get("tiktok_handle"),
                # Team info
                "team": target_profile.get("team"),
                "club": target_profile.get("club"),
            },
            "recent_games": recent_games,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting player profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get player profile") from e


# Health check
@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "version": "2.0.0", "schema": "enhanced"}


@app.get("/health/full")
async def full_health_check():
    """Comprehensive health check including database connectivity."""
    health_status = {
        "status": "healthy",
        "version": "2.0.0",
        "schema": "enhanced",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
    }

    overall_healthy = True

    # Check basic API
    health_status["checks"]["api"] = {"status": "healthy", "message": "API is responding"}

    # Check database connectivity
    try:
        # Simple database connectivity test
        test_response = season_dao.get_all_age_groups()
        if isinstance(test_response, list):
            health_status["checks"]["database"] = {
                "status": "healthy",
                "message": "Database connection successful",
                "age_groups_count": len(test_response),
            }
        else:
            raise Exception("Unexpected response from database")

    except Exception as e:
        overall_healthy = False
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {e!s}",
        }

    # Check reference data availability
    try:
        seasons = season_dao.get_all_seasons()
        match_types = match_type_dao.get_all_match_types()

        health_status["checks"]["reference_data"] = {
            "status": "healthy",
            "message": "Reference data available",
            "seasons_count": len(seasons) if isinstance(seasons, list) else 0,
            "match_types_count": len(match_types) if isinstance(match_types, list) else 0,
        }

        # Check if we have essential reference data
        if not seasons or not match_types:
            health_status["checks"]["reference_data"]["status"] = "warning"
            health_status["checks"]["reference_data"]["message"] = "Some reference data missing"

    except Exception as e:
        health_status["checks"]["reference_data"] = {
            "status": "unhealthy",
            "message": f"Reference data check failed: {e!s}",
        }

    # Check authentication system
    try:
        if auth_manager and hasattr(auth_manager, "supabase"):
            health_status["checks"]["auth"] = {
                "status": "healthy",
                "message": "Authentication system operational",
            }
        else:
            health_status["checks"]["auth"] = {
                "status": "warning",
                "message": "Authentication manager not properly initialized",
            }
    except Exception as e:
        health_status["checks"]["auth"] = {
            "status": "unhealthy",
            "message": f"Authentication system error: {e!s}",
        }

    # Set overall status
    check_statuses = [check.get("status", "unknown") for check in health_status["checks"].values()]

    if "unhealthy" in check_statuses:
        health_status["status"] = "unhealthy"
        overall_healthy = False
    elif "warning" in check_statuses:
        health_status["status"] = "degraded"

    # Log health check outcome
    logger.info(
        "health_check_performed",
        status=health_status["status"],
        database_healthy="database" in health_status["checks"]
        and health_status["checks"]["database"]["status"] == "healthy",
        auth_healthy="auth" in health_status["checks"] and health_status["checks"]["auth"]["status"] == "healthy",
    )

    # Return appropriate HTTP status code
    if overall_healthy:
        return health_status
    else:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=health_status)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)

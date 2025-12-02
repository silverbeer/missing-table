import os
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from api.invites import router as invites_router
from api.invite_requests import router as invite_requests_router
from auth import (
    AuthManager,
    get_current_user_required,
    require_admin,
    require_admin_or_service_account,
    require_match_management_permission,
    require_team_manager_or_admin,
)
from csrf_protection import provide_csrf_token
from models import (
    AgeGroupCreate,
    AgeGroupUpdate,
    Club,
    ClubWithTeams,
    DivisionCreate,
    DivisionUpdate,
    EnhancedMatch,
    League,
    LeagueCreate,
    LeagueUpdate,
    MatchPatch,
    MatchSubmissionData,
    PlayerCustomization,
    PlayerHistoryCreate,
    PlayerHistoryUpdate,
    ProfilePhotoSlot,
    RefreshTokenRequest,
    RoleUpdate,
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
DISABLE_SECURITY = os.getenv('DISABLE_SECURITY', 'false').lower() == 'true'

from dao.match_dao import MatchDAO
from dao.match_dao import SupabaseConnection as DbConnectionHolder


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
        print(f"Loading environment: {app_env} from {env_file}")
        load_dotenv(env_file, override=True)
    else:
        print(f"Environment file {env_file} not found, using default configuration")
        # Fallback to .env.local for backwards compatibility
        if os.path.exists(".env.local"):
            print("Falling back to .env.local")
            load_dotenv(".env.local", override=True)

load_environment()

# Configure structured logging with JSON output for Loki
from logging_config import get_logger, setup_logging

setup_logging(service_name="backend")
logger = get_logger(__name__)

app = FastAPI(title="Enhanced Sports League API", version="2.0.0")

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
    extra_origins_str = os.getenv('CORS_ORIGINS', '')
    extra_origins = [origin.strip() for origin in extra_origins_str.split(',') if origin.strip()]

    # Get environment-specific origins
    environment = os.getenv('ENVIRONMENT', 'development')

    # All production domains point to the same namespace (missing-table-dev)
    all_cloud_origins = production_origins

    if environment == 'production':
        # In production, allow both local (for development) and all cloud origins
        return local_origins + all_cloud_origins + extra_origins
    else:
        # In development/dev environment, also allow all cloud origins (consolidated architecture)
        return local_origins + all_cloud_origins + extra_origins

origins = get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase connection - use CLI for local development
supabase_url = os.getenv('SUPABASE_URL', '')
print(f"DEBUG: Raw SUPABASE_URL from env: {supabase_url}")
print(f"DEBUG: Contains localhost? {'localhost' in supabase_url}")
print(f"DEBUG: Contains 127.0.0.1? {'127.0.0.1' in supabase_url}")
if 'localhost' in supabase_url or '127.0.0.1' in supabase_url:
    print("Using Supabase CLI local development: " + supabase_url)
    # Use the regular connection for Supabase CLI
    db_conn_holder_obj = DbConnectionHolder()
    match_dao = MatchDAO(db_conn_holder_obj)
else:
    logger.info("Using enhanced Supabase connection")
    db_conn_holder_obj = DbConnectionHolder()
    match_dao = MatchDAO(db_conn_holder_obj)

# Initialize Authentication Manager
auth_manager = AuthManager(db_conn_holder_obj.client)


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
from endpoints.version import router as version_router

app.include_router(version_router)

# === Authentication Endpoints ===


@app.post("/api/auth/signup")
# @rate_limit("3 per hour")
async def signup(request: Request, user_data: UserSignup):
    """User signup endpoint with username authentication."""
    from auth import check_username_available, username_to_internal_email

    client_ip = get_client_ip(request)
    audit_logger = logger.bind(flow="auth_signup", username=user_data.username, client_ip=client_ip)

    try:
            # Validate username availability
            username_available = await check_username_available(
                db_conn_holder_obj.client,
                user_data.username
            )
            if not username_available:
                raise HTTPException(
                    status_code=400,
                    detail=f"Username '{user_data.username}' is already taken"
                )

            # Validate invite code if provided
            invite_info = None
            if user_data.invite_code:
                invite_service = InviteService(db_conn_holder_obj.client)
                invite_info = invite_service.validate_invite_code(user_data.invite_code)
                if not invite_info:
                    raise HTTPException(status_code=400, detail="Invalid or expired invite code")

                # If invite has email specified, verify it matches (if user provided email)
                if invite_info.get('email') and user_data.email:
                    if invite_info['email'] != user_data.email:
                        raise HTTPException(
                            status_code=400,
                            detail=f"This invite code is for {invite_info['email']}. Please use that email address."
                        )

                logger.info(f"Valid invite code for {invite_info['invite_type']}: {user_data.invite_code}")

            # Convert username to internal email for Supabase Auth
            internal_email = username_to_internal_email(user_data.username)

            # Create Supabase Auth user with internal email
            response = db_conn_holder_obj.client.auth.sign_up({
                "email": internal_email,
                "password": user_data.password,
                "options": {
                    "data": {
                        "username": user_data.username,
                        "display_name": user_data.display_name or user_data.username,
                        "is_username_auth": True
                    }
                }
            })

            if response.user:
                # Create/update user profile with username and optional contact info
                # Convert empty strings to None for optional fields
                profile_data = {
                    'id': response.user.id,
                    'username': user_data.username,
                    'email': user_data.email if user_data.email else None,  # Optional real email
                    'phone_number': user_data.phone_number if user_data.phone_number else None,  # Optional phone
                    'display_name': user_data.display_name or user_data.username,
                    'role': 'team-fan'  # Default role
                }

                # If signup with invite code, override role and team
                if invite_info:
                    # Map invite type to user role
                    role_mapping = {
                        'club_manager': 'club_manager',
                        'club_fan': 'club-fan',
                        'team_manager': 'team-manager',
                        'team_player': 'team-player',
                        'team_fan': 'team-fan'
                    }
                    profile_data['role'] = role_mapping.get(invite_info['invite_type'], 'team-fan')
                    profile_data['team_id'] = invite_info.get('team_id')
                    profile_data['club_id'] = invite_info.get('club_id')

                # Insert user profile
                match_dao.create_or_update_user_profile(profile_data)

                # Redeem invitation if used
                if invite_info:
                    invite_service.redeem_invitation(user_data.invite_code, response.user.id)
                    logger.info(f"User {response.user.id} assigned role {profile_data['role']} via invite code")

                audit_logger.info(
                    "auth_signup_success",
                    user_id=response.user.id,
                    used_invite=bool(user_data.invite_code)
                )

                message = f"Account created successfully! Welcome, {user_data.username}!"
                if invite_info:
                    invite_type_display = invite_info['invite_type'].replace('_', ' ')
                    if invite_info.get('club_name'):
                        message += f" You have been assigned to {invite_info['club_name']} as a {invite_type_display}."
                    elif invite_info.get('team_name'):
                        message += f" You have been assigned to {invite_info['team_name']} as a {invite_type_display}."

                return {
                    "message": message,
                    "user_id": response.user.id,
                    "username": user_data.username
                }
            else:
                audit_logger.warning("auth_signup_failed", reason="supabase_user_missing")
                raise HTTPException(status_code=400, detail="Failed to create user")

    except HTTPException:
        raise
    except Exception as e:
        audit_logger.error("auth_signup_error", error=str(e), email=user_data.email)
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

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
        response = db_conn_holder_obj.client.auth.sign_in_with_password({
            "email": internal_email,
            "password": user_data.password
        })

        if response.user and response.session:
            # Get user profile with username, team, AND club info
            profile = match_dao.get_user_profile_with_relationships(response.user.id)
            if not profile:
                profile = {'username': user_data.username}  # Fallback

            auth_logger.info("auth_login_success", user_id=response.user.id)

            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "user": {
                    "id": response.user.id,
                    "username": profile.get('username'),
                    "email": profile.get('email'),  # Real email if provided
                    "display_name": profile.get('display_name'),
                    "role": profile.get('role'),
                    "team_id": profile.get('team_id'),
                    "club_id": profile.get('club_id'),
                    "team": profile.get('team'),
                    "club": profile.get('club'),
                    "created_at": profile.get('created_at'),
                    "updated_at": profile.get('updated_at')
                }
            }
        else:
            auth_logger.warning("auth_login_failed", reason="invalid_credentials")
            raise HTTPException(status_code=401, detail="Invalid username or password")

    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error("auth_login_error", error=str(e))
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")


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
        if not re.match(r'^[a-zA-Z0-9_]{3,50}$', username):
            return {
                "available": False,
                "message": "Username must be 3-50 characters (letters, numbers, underscores only)"
            }

        # Check availability
        available = await check_username_available(db_conn_holder_obj.client, username)

        if available:
            return {
                "available": True,
                "message": f"Username '{username}' is available!"
            }
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
                "suggestions": suggestions
            }

    except Exception as e:
        logger.error(f"Error checking username: {e}")
        raise HTTPException(status_code=500, detail="Error checking username availability")


@app.post("/api/auth/logout")
async def logout(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """User logout endpoint."""
    try:
        db_conn_holder_obj.client.auth.sign_out()
        return {
            "success": True,
            "message": "Logged out successfully"
        }
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return {
            "success": True,  # Return success even on error since logout should be client-side primarily
            "message": "Logged out successfully"
        }


@app.get("/api/auth/profile")
async def get_profile(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get current user's profile."""
    try:
        profile = match_dao.get_user_profile_with_relationships(current_user["user_id"])
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
        logger.error(f"Get profile error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get profile")


@app.put("/api/auth/profile")
async def update_profile(
    profile_data: UserProfile, current_user: dict[str, Any] = Depends(get_current_user_required)
):
    """Update current user's profile."""
    try:
        update_data = {}
        if profile_data.display_name is not None:
            update_data["display_name"] = profile_data.display_name

        # Email update with validation
        if profile_data.email is not None:
            # Basic email format validation
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if profile_data.email.strip() and not re.match(email_pattern, profile_data.email):
                raise HTTPException(status_code=400, detail="Invalid email format")

            # Check for email uniqueness (if not empty)
            if profile_data.email.strip():
                existing = match_dao.get_user_profile_by_email(profile_data.email, exclude_user_id=current_user["user_id"])
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
            if profile_data.overlay_style not in ('badge', 'jersey', 'caption', 'none'):
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
            from datetime import datetime, timezone
            update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            match_dao.update_user_profile(current_user["user_id"], update_data)

        return {"message": "Profile updated successfully"}

    except Exception as e:
        logger.error(f"Update profile error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")


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
            "x-upsert": "true"
        }
        response = httpx.post(
            f"{self.url}/storage/v1/object/{bucket}/{file_path}",
            content=content,
            headers=headers,
            timeout=30.0
        )
        if response.status_code not in (200, 201):
            raise Exception(f"Storage upload failed: {response.text}")
        return response.json()

    def delete(self, bucket: str, file_paths: list[str]) -> dict:
        """Delete files from storage using direct HTTP API."""
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json"
        }
        response = httpx.delete(
            f"{self.url}/storage/v1/object/{bucket}",
            json={"prefixes": file_paths},
            headers=headers,
            timeout=30.0
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
        raise HTTPException(
            status_code=403,
            detail="This feature is only available for players"
        )
    return current_user


@app.post("/api/auth/profile/photo/{slot}")
async def upload_player_photo(
    slot: int,
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(require_player_role)
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
            detail=f"Invalid file type. Allowed: JPG, PNG, WebP. Got: {file.content_type}"
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_PHOTO_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is 500KB. Got: {len(content) / 1024:.1f}KB"
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
        from datetime import datetime, timezone
        photo_column = f"photo_{slot}_url"
        update_data = {photo_column: public_url, "updated_at": datetime.now(timezone.utc).isoformat()}

        # If no profile photo is set, set this as the profile photo
        profile = match_dao.get_user_profile_with_relationships(user_id)
        if not profile.get("profile_photo_slot"):
            update_data["profile_photo_slot"] = slot

        match_dao.update_user_profile(user_id, update_data)

        # Return updated profile
        updated_profile = match_dao.get_user_profile_with_relationships(user_id)
        return {
            "message": f"Photo uploaded to slot {slot}",
            "photo_url": public_url,
            "profile": updated_profile
        }

    except Exception as e:
        logger.error(f"Error uploading player photo: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/auth/profile/photo/{slot}")
async def delete_player_photo(
    slot: int,
    current_user: dict[str, Any] = Depends(require_player_role)
):
    """Delete a profile photo from a slot (1, 2, or 3). Players only.

    If this was the profile photo, auto-selects the next available photo.
    """
    # Validate slot
    if slot not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="Slot must be 1, 2, or 3")

    user_id = current_user["user_id"]

    try:
        # Get current profile
        profile = match_dao.get_user_profile_with_relationships(user_id)
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
        from datetime import datetime, timezone
        update_data = {photo_column: None, "updated_at": datetime.now(timezone.utc).isoformat()}

        # If this was the profile photo, find next available
        if profile.get("profile_photo_slot") == slot:
            new_profile_slot = None
            for check_slot in [1, 2, 3]:
                if check_slot != slot and profile.get(f"photo_{check_slot}_url"):
                    new_profile_slot = check_slot
                    break
            update_data["profile_photo_slot"] = new_profile_slot

        match_dao.update_user_profile(user_id, update_data)

        # Return updated profile
        updated_profile = match_dao.get_user_profile_with_relationships(user_id)
        return {
            "message": f"Photo deleted from slot {slot}",
            "profile": updated_profile
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting player photo: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/auth/profile/photo/profile-slot")
async def set_profile_photo_slot(
    slot_data: ProfilePhotoSlot,
    current_user: dict[str, Any] = Depends(require_player_role)
):
    """Set which photo slot is the profile picture. Players only.

    The specified slot must have a photo uploaded.
    """
    slot = slot_data.slot
    user_id = current_user["user_id"]

    try:
        # Get current profile
        profile = match_dao.get_user_profile_with_relationships(user_id)
        photo_url = profile.get(f"photo_{slot}_url")

        if not photo_url:
            raise HTTPException(
                status_code=400,
                detail=f"No photo in slot {slot}. Upload a photo first."
            )

        # Update profile photo slot
        from datetime import datetime, timezone
        match_dao.update_user_profile(user_id, {
            "profile_photo_slot": slot,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })

        # Return updated profile
        updated_profile = match_dao.get_user_profile_with_relationships(user_id)
        return {
            "message": f"Profile photo set to slot {slot}",
            "profile": updated_profile
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting profile photo slot: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/auth/profile/customization")
async def update_player_customization(
    customization: PlayerCustomization,
    current_user: dict[str, Any] = Depends(require_player_role)
):
    """Update player profile customization (colors, style). Players only.

    This is a convenience endpoint for updating multiple customization
    fields at once. All fields are optional.
    """
    user_id = current_user["user_id"]

    try:
        from datetime import datetime, timezone
        update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}

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
            match_dao.update_user_profile(user_id, update_data)

        # Return updated profile
        updated_profile = match_dao.get_user_profile_with_relationships(user_id)
        return {
            "message": "Customization updated",
            "profile": updated_profile
        }

    except Exception as e:
        logger.error(f"Error updating player customization: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# === Player Team History Endpoints ===


@app.get("/api/auth/profile/history")
async def get_player_history(
    current_user: dict[str, Any] = Depends(get_current_user_required)
):
    """Get player's team history across all seasons.

    Returns history entries ordered by season (most recent first),
    with full team, season, age_group, league, and division details.
    """
    user_id = current_user["user_id"]

    try:
        history = match_dao.get_player_team_history(user_id)
        return {
            "success": True,
            "history": history
        }
    except Exception as e:
        logger.error(f"Error getting player history: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/profile/history/current")
async def get_current_team_assignment(
    current_user: dict[str, Any] = Depends(get_current_user_required)
):
    """Get player's current team assignment (is_current=true).

    Returns the current history entry with full related data,
    or null if no current assignment exists.
    """
    user_id = current_user["user_id"]

    try:
        current = match_dao.get_current_player_team_assignment(user_id)
        return {
            "success": True,
            "current": current
        }
    except Exception as e:
        logger.error(f"Error getting current team assignment: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/profile/teams/current")
async def get_all_current_teams(
    current_user: dict[str, Any] = Depends(get_current_user_required)
):
    """Get ALL current team assignments for a player.

    Returns all team assignments where is_current=true.
    This supports players being on multiple teams simultaneously
    (e.g., for futsal/soccer leagues).

    Returns:
        List of current teams with club info for team selector UI.
    """
    user_id = current_user["user_id"]

    try:
        teams = match_dao.get_all_current_player_teams(user_id)
        return {
            "success": True,
            "teams": teams
        }
    except Exception as e:
        logger.error(f"Error getting all current teams: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/profile/history")
async def create_player_history(
    history_data: PlayerHistoryCreate,
    current_user: dict[str, Any] = Depends(get_current_user_required)
):
    """Create a new player team history entry.

    Players can add their own history entries for different seasons.
    The entry will automatically capture age_group, league, and division
    from the team's current configuration.
    """
    user_id = current_user["user_id"]

    try:
        entry = match_dao.create_player_history_entry(
            player_id=user_id,
            team_id=history_data.team_id,
            season_id=history_data.season_id,
            jersey_number=history_data.jersey_number,
            positions=history_data.positions,
            notes=history_data.notes,
            is_current=history_data.is_current
        )

        if entry:
            return {
                "success": True,
                "entry": entry
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create history entry")

    except Exception as e:
        logger.error(f"Error creating player history entry: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/auth/profile/history/{history_id}")
async def update_player_history(
    history_id: int,
    history_data: PlayerHistoryUpdate,
    current_user: dict[str, Any] = Depends(get_current_user_required)
):
    """Update a player team history entry.

    Players can only update their own history entries.
    """
    user_id = current_user["user_id"]

    try:
        # Verify this entry belongs to the user
        existing = match_dao.get_player_history_entry_by_id(history_id)
        if not existing:
            raise HTTPException(status_code=404, detail="History entry not found")
        if existing.get("player_id") != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to update this entry")

        entry = match_dao.update_player_history_entry(
            history_id=history_id,
            jersey_number=history_data.jersey_number,
            positions=history_data.positions,
            notes=history_data.notes,
            is_current=history_data.is_current
        )

        if entry:
            return {
                "success": True,
                "entry": entry
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update history entry")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating player history entry: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/auth/profile/history/{history_id}")
async def delete_player_history(
    history_id: int,
    current_user: dict[str, Any] = Depends(get_current_user_required)
):
    """Delete a player team history entry.

    Players can only delete their own history entries.
    """
    user_id = current_user["user_id"]

    try:
        # Verify this entry belongs to the user
        existing = match_dao.get_player_history_entry_by_id(history_id)
        if not existing:
            raise HTTPException(status_code=404, detail="History entry not found")
        if existing.get("player_id") != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this entry")

        success = match_dao.delete_player_history_entry(history_id)

        if success:
            return {
                "success": True,
                "message": "History entry deleted"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to delete history entry")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting player history entry: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/users")
async def get_users(current_user: dict[str, Any] = Depends(require_admin)):
    """Get all users (admin only)."""
    try:
        return match_dao.get_all_user_profiles()

    except Exception as e:
        logger.error(f"Get users error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get users")


@app.post("/api/auth/refresh")
async def refresh_token(request: Request, refresh_data: RefreshTokenRequest):
    """Refresh JWT token using refresh token."""
    refresh_logger = logger.bind(flow="auth_refresh", client_ip=get_client_ip(request))
    try:
        response = db_conn_holder_obj.client.auth.refresh_session(refresh_data.refresh_token)

        if response.session:
            refresh_logger.info("auth_refresh_success")
            return {
                "success": True,
                "session": {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at,
                    "token_type": "bearer"
                }
            }
        else:
            refresh_logger.warning("auth_refresh_failed", reason="no_session")
            raise HTTPException(status_code=401, detail="Failed to refresh token")

    except Exception as e:
        refresh_logger.error("auth_refresh_error", error=str(e))
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.get("/api/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user_required)):
    """Get current user info for frontend auth state."""
    try:
        # Get fresh profile data with team AND club info
        profile = match_dao.get_user_profile_with_relationships(current_user['user_id']) or {}

        return {
            "success": True,
            "user": {
                "id": current_user['user_id'],
                "email": current_user['email'],
                "profile": {
                    "username": profile.get('username'),
                    "email": profile.get('email'),
                    "role": profile.get('role', 'team-fan'),
                    "team_id": profile.get('team_id'),
                    "club_id": profile.get('club_id'),
                    "display_name": profile.get('display_name'),
                    "name": profile.get('name'),
                    "player_number": profile.get('player_number'),
                    "positions": profile.get('positions'),
                    "team": profile.get('team'),
                    "club": profile.get('club'),
                    "created_at": profile.get('created_at'),
                    "updated_at": profile.get('updated_at'),
                    # Photo fields
                    "photo_1_url": profile.get('photo_1_url'),
                    "photo_2_url": profile.get('photo_2_url'),
                    "photo_3_url": profile.get('photo_3_url'),
                    "profile_photo_slot": profile.get('profile_photo_slot'),
                    "overlay_style": profile.get('overlay_style'),
                    "primary_color": profile.get('primary_color'),
                    "text_color": profile.get('text_color'),
                    "accent_color": profile.get('accent_color'),
                    # Social media handles
                    "instagram_handle": profile.get('instagram_handle'),
                    "snapchat_handle": profile.get('snapchat_handle'),
                    "tiktok_handle": profile.get('tiktok_handle'),
                    # Personal info
                    "first_name": profile.get('first_name'),
                    "last_name": profile.get('last_name'),
                    "hometown": profile.get('hometown'),
                }
            }
        }

    except Exception as e:
        logger.error(f"Get user info error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user info")

@app.get("/api/positions")
async def get_positions(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get all available player positions."""
    positions = [
        {"full_name": "Goalkeeper", "abbreviation": "GK"},
        {"full_name": "Center Back", "abbreviation": "CB"},
        {"full_name": "Left Center Back", "abbreviation": "LCB"},
        {"full_name": "Right Center Back", "abbreviation": "RCB"},
        {"full_name": "Left Back", "abbreviation": "LB"},
        {"full_name": "Right Back", "abbreviation": "RB"},
        {"full_name": "Left Wing Back", "abbreviation": "LWB"},
        {"full_name": "Right Wing Back", "abbreviation": "RWB"},
        {"full_name": "Sweeper", "abbreviation": "SW"},
        {"full_name": "Central Midfielder", "abbreviation": "CM"},
        {"full_name": "Defensive Midfielder", "abbreviation": "CDM"},
        {"full_name": "Attacking Midfielder", "abbreviation": "CAM"},
        {"full_name": "Left Midfielder", "abbreviation": "LM"},
        {"full_name": "Right Midfielder", "abbreviation": "RM"},
        {"full_name": "Wide Midfielder", "abbreviation": "WM"},
        {"full_name": "Box-to-Box Midfielder", "abbreviation": "B2B"},
        {"full_name": "Holding Midfielder", "abbreviation": "HM"},
        {"full_name": "Striker", "abbreviation": "ST"},
        {"full_name": "Center Forward", "abbreviation": "CF"},
        {"full_name": "Second Striker", "abbreviation": "SS"},
        {"full_name": "Left Winger", "abbreviation": "LW"},
        {"full_name": "Right Winger", "abbreviation": "RW"},
        {"full_name": "Forward", "abbreviation": "FW"},
        {"full_name": "False Nine", "abbreviation": "F9"},
        {"full_name": "Target Forward", "abbreviation": "TF"},
    ]
    return positions


@app.put("/api/auth/users/role")
async def update_user_role(
    role_data: RoleUpdate, current_user: dict[str, Any] = Depends(require_admin)
):
    """Update user role (admin only)."""
    try:
        from datetime import datetime, timezone
        update_data = {"role": role_data.role, "updated_at": datetime.now(timezone.utc).isoformat()}

        if role_data.team_id:
            update_data["team_id"] = role_data.team_id

        match_dao.update_user_profile(role_data.user_id, update_data)

        return {"message": "User role updated successfully"}

    except Exception as e:
        logger.error(f"Update user role error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user role")


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
                existing = match_dao.get_user_profile_by_username(username, exclude_user_id=profile_data.user_id)
                if existing:
                    raise HTTPException(
                        status_code=409, detail=f"Username '{username}' is already taken"
                    )

                update_data["username"] = username.lower()

                # Update auth.users email to internal format
                internal_email = f"{username.lower()}@missingtable.local"
                try:
                    db_conn_holder_obj.client.auth.admin.update_user_by_id(
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
        match_dao.update_user_profile(profile_data.user_id, update_data)

        return {"message": "User profile updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user profile error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update user profile: {e!s}")


# === CSRF Token Endpoint ===


@app.get("/api/csrf-token")
async def get_csrf_token_endpoint(request: Request, response: Response):
    """Get CSRF token for the session."""
    return await provide_csrf_token(request, response)


# === Reference Data Endpoints ===


@app.get("/api/age-groups")
async def get_age_groups(
    current_user: dict[str, Any] = Depends(get_current_user_required)
):
    """Get all age groups."""
    try:
        logger.info(f"age-groups endpoint - current_user: {current_user}")
        age_groups = match_dao.get_all_age_groups()
        logger.info(f"age-groups endpoint - returning {len(age_groups)} groups")
        return age_groups
    except Exception as e:
        logger.error(f"Error retrieving age groups: {e!s}")
        raise HTTPException(
            status_code=503, detail="Database connection failed. Please check Supabase connection."
        )


@app.get("/api/seasons")
async def get_seasons(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get all seasons."""
    try:
        seasons = match_dao.get_all_seasons()
        return seasons
    except Exception as e:
        logger.error(f"Error retrieving seasons: {e!s}")
        raise HTTPException(
            status_code=503, detail="Database connection failed. Please check Supabase connection."
        )


@app.get("/api/current-season")
async def get_current_season(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get the current active season."""
    try:
        current_season = match_dao.get_current_season()
        if not current_season:
            # Default to 2024-2025 season if no current season found
            seasons = match_dao.get_all_seasons()
            current_season = next(
                (s for s in seasons if s["name"] == "2024-2025"), seasons[0] if seasons else None
            )
        return current_season
    except Exception as e:
        logger.error(f"Error retrieving current season: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/active-seasons")
async def get_active_seasons(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get active seasons (current and future) for scheduling new matches."""
    try:
        active_seasons = match_dao.get_active_seasons()
        return active_seasons
    except Exception as e:
        logger.error(f"Error retrieving active seasons: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/match-types")
async def get_match_types(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get all match types."""
    try:
        match_types = match_dao.get_all_match_types()
        return match_types
    except Exception as e:
        logger.error(f"Error retrieving match types: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/divisions")
async def get_divisions(
    current_user: dict[str, Any] = Depends(get_current_user_required),
    league_id: int | None = None
):
    """Get all divisions, optionally filtered by league."""
    try:
        if league_id:
            divisions = match_dao.get_divisions_by_league(league_id)
        else:
            divisions = match_dao.get_all_divisions()
        return divisions
    except Exception as e:
        logger.error(f"Error retrieving divisions: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# === Enhanced Team Endpoints ===


@app.get("/api/teams")
async def get_teams(
    current_user: dict[str, Any] = Depends(get_current_user_required),
    match_type_id: int | None = None,
    age_group_id: int | None = None,
    include_parent: bool = False,
    include_game_count: bool = False,
    club_id: int | None = None
):
    """
    Get teams, optionally filtered by match type, age group, or club.

    Args:
        match_type_id: Filter by match type
        age_group_id: Filter by age group (requires match_type_id)
        include_parent: If true, include parent club information
        include_game_count: If true, include count of games for each team (performance optimized)
        club_id: Filter to only teams belonging to this parent club
    """
    try:
        # Get teams based on filters
        if match_type_id and age_group_id:
            teams = match_dao.get_teams_by_match_type_and_age_group(match_type_id, age_group_id)
        elif club_id:
            teams = match_dao.get_club_teams(club_id)
        else:
            teams = match_dao.get_all_teams()

        # Enrich teams with additional data if requested
        if include_parent or include_game_count:
            enriched_teams = []

            # Get game counts for all teams in one query (performance optimization)
            game_counts = {}
            if include_game_count:
                game_counts = match_dao.get_team_game_counts()

            for team in teams:
                team_data = {**team}

                # Add parent club info if requested
                if include_parent:
                    if team.get('club_id'):
                        # Fetch the club directly using the club_id
                        try:
                            clubs = match_dao.get_all_clubs()
                            parent_club = next((c for c in clubs if c['id'] == team['club_id']), None)
                            team_data['parent_club'] = parent_club
                        except Exception:
                            team_data['parent_club'] = None
                    else:
                        team_data['parent_club'] = None

                    # Check if this team is itself a parent club
                    if hasattr(match_dao, 'is_parent_club'):
                        team_data['is_parent_club'] = match_dao.is_parent_club(team['id'])
                    else:
                        team_data['is_parent_club'] = False

                # Add game count if requested
                if include_game_count:
                    team_data['game_count'] = game_counts.get(team['id'], 0)

                enriched_teams.append(team_data)

            return enriched_teams

        return teams
    except Exception as e:
        logger.error(f"Error retrieving teams: {e!s}")
        raise HTTPException(
            status_code=503, detail="Database connection failed. Please check Supabase connection."
        )


@app.post("/api/teams")
async def add_team(
    request: Request,
    team: Team,
    current_user: dict[str, Any] = Depends(require_team_manager_or_admin)
):
    """Add a new team with age groups, division, and optional parent club.

    Division represents location (e.g., Northeast Division for Homegrown, New England Conference for Academy).
    All age groups for a team share the same division.

    Club managers can only add teams to their assigned club.
    """
    try:
        user_role = current_user.get('role')
        user_club_id = current_user.get('club_id')

        # Team managers cannot create teams (only manage existing ones)
        if user_role == 'team-manager':
            raise HTTPException(status_code=403, detail="Team managers cannot create teams")

        # Club managers can only add teams to their assigned club
        if user_role == 'club_manager':
            if not user_club_id:
                raise HTTPException(status_code=403, detail="Club manager must have a club assigned")
            # Force team to be created in the club manager's club
            if team.club_id and team.club_id != user_club_id:
                raise HTTPException(status_code=403, detail="Can only create teams for your assigned club")
            # Auto-assign club_id if not provided
            team.club_id = user_club_id
        client_ip = get_client_ip(request)

        # Call add_team with keyword arguments for SecureDAO compatibility
        success = match_dao.add_team(
            client_ip=client_ip,
            name=team.name,
            city=team.city,
            age_group_ids=team.age_group_ids,
            division_id=team.division_id,
            club_id=team.club_id,
            academy_team=team.academy_team
        )
        if success:
            return {"message": "Team added successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add team")
    except Exception as e:
        error_str = str(e)
        logger.error(f"Error adding team: {error_str}")

        # Check for duplicate team constraint violation
        if "teams_name_division_unique" in error_str or "teams_name_academy_unique" in error_str or "duplicate key value" in error_str.lower():
            raise HTTPException(status_code=409, detail="Team with this name already exists in this division")

        raise HTTPException(status_code=500, detail=error_str)


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
    end_date: str | None = Query(None, description="Filter by end date (YYYY-MM-DD)")
):
    """Get all matches with optional filters (requires authentication)."""
    try:
        client_ip = get_client_ip(request)
        matches = match_dao.get_all_matches(
            client_ip=client_ip,
            season_id=season_id,
            age_group_id=age_group_id,
            division_id=division_id,
            team_id=team_id,
            match_type=match_type,
            start_date=start_date,
            end_date=end_date
        )
        return matches
    except Exception as e:
        logger.error(f"Error retrieving matches: {e!s}")
        raise HTTPException(
            status_code=503, detail="Database connection failed. Please check Supabase connection."
        )


@app.get("/api/matches/{match_id}")
async def get_match(
    request: Request,
    match_id: int,
    current_user: dict[str, Any] = Depends(get_current_user_required)
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
        logger.error(f"Error retrieving match {match_id}: {e!s}")
        raise HTTPException(
            status_code=503, detail="Database connection failed. Please check Supabase connection."
        )


@app.delete("/api/matches/{match_id}")
async def delete_match(
    request: Request,
    match_id: int,
    current_user: dict[str, Any] = Depends(require_admin)
):
    """Delete a match by ID (requires admin permission)."""
    try:
        client_ip = get_client_ip(request)
        result = match_dao.delete_match(match_id, client_ip=client_ip)

        if result:
            return {"message": f"Match {match_id} deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Match with ID {match_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting match {match_id}: {e!s}")
        raise HTTPException(
            status_code=503, detail="Database connection failed. Please check Supabase connection."
        )


@app.post("/api/matches")
async def add_match(request: Request, match: EnhancedMatch, current_user: dict[str, Any] = Depends(require_match_management_permission)):
    """Add a new match with enhanced schema (requires admin, team manager, or service account with manage_matches permission)."""
    try:
        # Use username for regular users, service_name for service accounts
        user_identifier = current_user.get('username') or current_user.get('service_name', 'unknown')
        logger.info(f"POST /api/matches - User: {user_identifier}, Role: {current_user.get('role', 'unknown')}")
        logger.info(f"POST /api/matches - Match data: {match.model_dump()}")

        # Validate division_id for League matches
        match_type = match_dao.get_match_type_by_id(match.match_type_id)
        if match_type and match_type.get('name') == 'League' and match.division_id is None:
            raise HTTPException(
                status_code=422,
                detail="division_id is required for League matches"
            )

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
        )
        if success:
            return {"message": "Match added successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add match")
    except Exception as e:
        logger.error(f"Error adding match: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/matches/{match_id}")
async def update_match(
    match_id: int, match: EnhancedMatch, current_user: dict[str, Any] = Depends(require_match_management_permission)
):
    """Update an existing match (admin, club_manager, team-manager, or service account with manage_matches permission)."""
    try:
        # Get current match to check permissions
        current_match = match_dao.get_match_by_id(match_id)
        if not current_match:
            raise HTTPException(status_code=404, detail="Match not found")

        # Check if user can edit this match
        if not auth_manager.can_edit_match(current_user, current_match['home_team_id'], current_match['away_team_id']):
            raise HTTPException(status_code=403, detail="You don't have permission to edit this match")

        # Validate division_id for League matches
        match_type = match_dao.get_match_type_by_id(match.match_type_id)
        if match_type and match_type.get('name') == 'League' and match.division_id is None:
            raise HTTPException(
                status_code=422,
                detail="division_id is required for League matches"
            )

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
        )
        if updated_match:
            return {"message": "Match updated successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update match")
    except Exception as e:
        logger.error(f"Error updating match: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/matches/{match_id}")
async def patch_match(
    match_id: int,
    match_patch: MatchPatch,
    current_user: dict[str, Any] = Depends(require_match_management_permission)
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
        if not auth_manager.can_edit_match(current_user, current_match['home_team_id'], current_match['away_team_id']):
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
            raise HTTPException(
                status_code=400,
                detail=f"status must be one of: {', '.join(valid_statuses)}"
            )

        # Build update data, using existing values for fields not provided
        update_data = {
            "match_id": match_id,
            "home_team_id": match_patch.home_team_id if match_patch.home_team_id is not None else current_match['home_team_id'],
            "away_team_id": match_patch.away_team_id if match_patch.away_team_id is not None else current_match['away_team_id'],
            "match_date": match_patch.match_date if match_patch.match_date is not None else current_match['match_date'],
            "home_score": match_patch.home_score if match_patch.home_score is not None else current_match['home_score'],
            "away_score": match_patch.away_score if match_patch.away_score is not None else current_match['away_score'],
            "season_id": match_patch.season_id if match_patch.season_id is not None else current_match['season_id'],
            "age_group_id": match_patch.age_group_id if match_patch.age_group_id is not None else current_match['age_group_id'],
            "match_type_id": match_patch.match_type_id if match_patch.match_type_id is not None else current_match['match_type_id'],
            "division_id": match_patch.division_id if match_patch.division_id is not None else current_match.get('division_id'),
            "status": match_patch.match_status if match_patch.match_status is not None else (match_patch.status if match_patch.status is not None else current_match.get('match_status', 'scheduled')),
            "external_match_id": match_patch.external_match_id if match_patch.external_match_id is not None else current_match.get('external_match_id'),
            "updated_by": current_user.get("user_id"),
        }

        # Validate division_id for League matches (after building final update data)
        final_match_type_id = update_data['match_type_id']
        final_division_id = update_data['division_id']
        match_type = match_dao.get_match_type_by_id(final_match_type_id)
        if match_type and match_type.get('name') == 'League' and final_division_id is None:
            raise HTTPException(
                status_code=422,
                detail="division_id is required for League matches"
            )

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
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/matches/{match_id}")
async def delete_match(match_id: int, current_user: dict[str, Any] = Depends(require_team_manager_or_admin)):
    """Delete a match (admin or team manager only)."""
    try:
        # Get current match to check permissions
        current_match = match_dao.get_match_by_id(match_id)
        if not current_match:
            raise HTTPException(status_code=404, detail="Match not found")

        # Check if user can edit this match
        if not auth_manager.can_edit_match(current_user, current_match['home_team_id'], current_match['away_team_id']):
            raise HTTPException(status_code=403, detail="You don't have permission to delete this match")

        success = match_dao.delete_match(match_id)
        if success:
            return {"message": "Match deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete match")
    except Exception as e:
        logger.error(f"Error deleting match: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/matches/team/{team_id}")
async def get_matches_by_team(
    team_id: int,
    current_user: dict[str, Any] = Depends(get_current_user_required),
    season_id: int | None = Query(None, description="Filter by season ID"),
    age_group_id: int | None = Query(None, description="Filter by age group ID")
):
    """Get matches for a specific team."""
    try:
        matches = match_dao.get_matches_by_team(team_id, season_id=season_id, age_group_id=age_group_id)
        # Return empty array if no matches found - this is not an error condition
        return matches if matches else []
    except Exception as e:
        logger.error(f"Error retrieving matches for team '{team_id}': {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


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
        # If no season specified, use current/default season
        if not season_id:
            current_season = match_dao.get_current_season()
            if current_season:
                season_id = current_season["id"]
            else:
                # Default to 2024-2025 season
                seasons = match_dao.get_all_seasons()
                default_season = next(
                    (s for s in seasons if s["name"] == "2024-2025"),
                    seasons[0] if seasons else None,
                )
                if default_season:
                    season_id = default_season["id"]

        # If no age group specified, use U13
        if not age_group_id:
            age_groups = match_dao.get_all_age_groups()
            u13_age_group = next(
                (ag for ag in age_groups if ag["name"] == "U13"),
                age_groups[0] if age_groups else None,
            )
            if u13_age_group:
                age_group_id = u13_age_group["id"]

        table = match_dao.get_league_table(
            season_id=season_id,
            age_group_id=age_group_id,
            division_id=division_id,
            match_type=match_type,
        )

        return table
    except Exception as e:
        logger.error(f"Error generating league table: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# === Admin CRUD Endpoints ===


# Age Groups CRUD
@app.post("/api/age-groups")
async def create_age_group(
    age_group: AgeGroupCreate, current_user: dict[str, Any] = Depends(require_admin)
):
    """Create a new age group (admin only)."""
    try:
        result = match_dao.create_age_group(age_group.name)
        return result
    except Exception as e:
        logger.error(f"Error creating age group: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/age-groups/{age_group_id}")
async def update_age_group(
    age_group_id: int,
    age_group: AgeGroupUpdate,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Update an age group (admin only)."""
    try:
        result = match_dao.update_age_group(age_group_id, age_group.name)
        if not result:
            raise HTTPException(status_code=404, detail="Age group not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating age group: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/age-groups/{age_group_id}")
async def delete_age_group(
    age_group_id: int, current_user: dict[str, Any] = Depends(require_admin)
):
    """Delete an age group (admin only)."""
    try:
        result = match_dao.delete_age_group(age_group_id)
        if not result:
            raise HTTPException(status_code=404, detail="Age group not found")
        return {"message": "Age group deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting age group: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# Seasons CRUD
@app.post("/api/seasons")
async def create_season(
    season: SeasonCreate, current_user: dict[str, Any] = Depends(require_admin)
):
    """Create a new season (admin only)."""
    try:
        result = match_dao.create_season(season.name, season.start_date, season.end_date)
        return result
    except Exception as e:
        logger.error(f"Error creating season: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/seasons/{season_id}")
async def update_season(
    season_id: int, season: SeasonUpdate, current_user: dict[str, Any] = Depends(require_admin)
):
    """Update a season (admin only)."""
    try:
        result = match_dao.update_season(
            season_id, season.name, season.start_date, season.end_date
        )
        if not result:
            raise HTTPException(status_code=404, detail="Season not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating season: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/seasons/{season_id}")
async def delete_season(season_id: int, current_user: dict[str, Any] = Depends(require_admin)):
    """Delete a season (admin only)."""
    try:
        result = match_dao.delete_season(season_id)
        if not result:
            raise HTTPException(status_code=404, detail="Season not found")
        return {"message": "Season deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting season: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# Leagues CRUD
@app.get("/api/leagues")
async def get_leagues():
    """Get all leagues (public access)."""
    try:
        leagues = match_dao.get_all_leagues()
        return leagues
    except Exception as e:
        logger.error(f"Error fetching leagues: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/leagues/{league_id}")
async def get_league(league_id: int):
    """Get league by ID (public access)."""
    try:
        league = match_dao.get_league_by_id(league_id)
        if not league:
            raise HTTPException(status_code=404, detail="League not found")
        return league
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching league {league_id}: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/leagues")
async def create_league(
    league: LeagueCreate, current_user: dict[str, Any] = Depends(require_admin)
):
    """Create a new league (admin only)."""
    try:
        league_data = league.model_dump()
        result = match_dao.create_league(league_data)
        return result
    except Exception as e:
        logger.error(f"Error creating league: {e!s}")
        raise HTTPException(status_code=400, detail=str(e))


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
        result = match_dao.update_league(league_id, league_data)
        if not result:
            raise HTTPException(status_code=404, detail="League not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating league: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/leagues/{league_id}")
async def delete_league(
    league_id: int, current_user: dict[str, Any] = Depends(require_admin)
):
    """Delete a league (admin only). Will fail if divisions exist."""
    try:
        match_dao.delete_league(league_id)
        return {"message": "League deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting league: {e!s}")
        if "foreign key" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail="Cannot delete league with existing divisions. Delete divisions first.",
            )
        raise HTTPException(status_code=500, detail=str(e))


# Divisions CRUD
@app.post("/api/divisions")
async def create_division(
    request: Request,
    division: DivisionCreate,
    current_user: dict[str, Any] = Depends(require_admin)
):
    """Create a new division (admin only)."""
    try:
        client_ip = get_client_ip(request)
        division_data = division.model_dump()
        result = match_dao.create_division(division_data, client_ip=client_ip)
        return result
    except Exception as e:
        logger.error(f"Error creating division: {e!s}")
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/divisions/{division_id}")
async def update_division(
    request: Request,
    division_id: int,
    division: DivisionUpdate,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Update a division (admin only)."""
    try:
        client_ip = get_client_ip(request)
        division_data = division.model_dump(exclude_unset=True)
        result = match_dao.update_division(division_id, division_data, client_ip=client_ip)
        if not result:
            raise HTTPException(status_code=404, detail="Division not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating division: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/divisions/{division_id}")
async def delete_division(division_id: int, current_user: dict[str, Any] = Depends(require_admin)):
    """Delete a division (admin only)."""
    try:
        result = match_dao.delete_division(division_id)
        if not result:
            raise HTTPException(status_code=404, detail="Division not found")
        return {"message": "Division deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting division: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# Teams CRUD (update existing)
@app.put("/api/teams/{team_id}")
async def update_team(
    request: Request,
    team_id: int,
    team: TeamUpdate,
    current_user: dict[str, Any] = Depends(require_admin)
):
    """Update a team (admin only)."""
    try:
        client_ip = get_client_ip(request)
        logger.info(f"Updating team {team_id}: name={team.name}, club_id={team.club_id}")
        result = match_dao.update_team(
            team_id, team.name, team.city, team.academy_team, team.club_id, client_ip=client_ip
        )
        if not result:
            raise HTTPException(status_code=404, detail="Team not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating team: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/teams/{team_id}")
async def delete_team(team_id: int, current_user: dict[str, Any] = Depends(require_admin)):
    """Delete a team (admin only)."""
    try:
        result = match_dao.delete_team(team_id)
        if not result:
            raise HTTPException(status_code=404, detail="Team not found")
        return {"message": "Team deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting team: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/teams/{team_id}/match-types")
async def add_team_match_type_participation(
    team_id: int,
    mapping: TeamMatchTypeMapping,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Add a team's participation in a specific match type and age group (admin only)."""
    try:
        success = match_dao.add_team_match_type_participation(
            team_id, mapping.match_type_id, mapping.age_group_id
        )
        if success:
            return {"message": "Team match type participation added successfully"}
        else:
            raise HTTPException(
                status_code=500, detail="Failed to add team match type participation"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding team match type participation: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/teams/{team_id}/match-types/{match_type_id}/{age_group_id}")
async def remove_team_match_type_participation(
    team_id: int,
    match_type_id: int,
    age_group_id: int,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Remove a team's participation in a specific match type and age group (admin only)."""
    try:
        success = match_dao.remove_team_match_type_participation(
            team_id, match_type_id, age_group_id
        )
        if success:
            return {"message": "Team match type participation removed successfully"}
        else:
            raise HTTPException(
                status_code=500, detail="Failed to remove team match type participation"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing team match type participation: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# === Club Endpoints ===

@app.get("/api/clubs")
async def get_clubs(
    include_teams: bool = True,
    current_user: dict[str, Any] = Depends(get_current_user_required)
):
    """Get all clubs.

    Args:
        include_teams: If true, enriches clubs with their teams list (default: true)

    Returns:
        List of clubs with optional team details
    """
    try:
        # Get all clubs from clubs table (already includes team_count)
        clubs = match_dao.get_all_clubs()
        logger.info(f"/api/clubs: Fetched {len(clubs)} clubs")

        if not include_teams:
            # Return clubs without team details (faster for dropdowns)
            return clubs

        # Enrich with team details if requested
        enriched_clubs = []
        for club in clubs:
            club_teams = match_dao.get_club_teams(club['id'])
            enriched_club = {
                **club,
                'teams': club_teams,
                'team_count': len(club_teams)  # Overwrite with actual count
            }
            enriched_clubs.append(enriched_club)
            logger.debug(f"Club '{club.get('name')}' has {len(club_teams)} teams")

        return enriched_clubs
    except Exception as e:
        logger.error(f"Error fetching clubs: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/clubs/{club_id}/teams")
async def get_club_teams(
    club_id: int, current_user: dict[str, Any] = Depends(get_current_user_required)
):
    """Get all teams for a specific club."""
    try:
        teams = match_dao.get_club_teams(club_id)
        if not teams:
            raise HTTPException(status_code=404, detail=f"Club with id {club_id} not found")

        return teams
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching club teams: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clubs")
async def create_club(
    club: Club, current_user: dict[str, Any] = Depends(require_admin)
):
    """Create a new club (admin only)."""
    try:
        new_club = match_dao.create_club(
            name=club.name,
            city=club.city,
            website=club.website,
            description=club.description,
            logo_url=club.logo_url,
            primary_color=club.primary_color,
            secondary_color=club.secondary_color
        )
        logger.info(f"Created new club: {new_club['name']}")
        return new_club
    except Exception as e:
        error_str = str(e)
        logger.error(f"Error creating club: {error_str}")

        # Check for duplicate key constraint violation
        if 'duplicate key value violates unique constraint' in error_str.lower():
            if 'clubs_name_unique' in error_str.lower() or 'clubs_name_key' in error_str.lower():
                raise HTTPException(
                    status_code=409,
                    detail=f"A club with the name '{club.name}' already exists. Please use a different name."
                )
            else:
                raise HTTPException(
                    status_code=409,
                    detail="A club with this information already exists."
                )

        # For any other unexpected errors, return 500
        raise HTTPException(status_code=500, detail="An unexpected error occurred while creating the club.")


@app.put("/api/clubs/{club_id}")
async def update_club(
    club_id: int, club: Club, current_user: dict[str, Any] = Depends(require_admin)
):
    """Update a club (admin only)."""
    try:
        updated_club = match_dao.update_club(
            club_id=club_id,
            name=club.name,
            city=club.city,
            website=club.website,
            description=club.description,
            logo_url=club.logo_url,
            primary_color=club.primary_color,
            secondary_color=club.secondary_color
        )
        if not updated_club:
            raise HTTPException(status_code=404, detail=f"Club with id {club_id} not found")
        logger.info(f"Updated club: {updated_club['name']}")
        return updated_club
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating club: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clubs/{club_id}/logo")
async def upload_club_logo(
    club_id: int,
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(require_admin)
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
            detail=f"Invalid file type. Allowed types: PNG, JPG. Got: {file.content_type}"
        )

    # Read file content
    content = await file.read()

    # Validate file size (2MB max)
    max_size = 2 * 1024 * 1024  # 2MB
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is 2MB. Got: {len(content) / 1024 / 1024:.2f}MB"
        )

    # Determine file extension
    ext = "png" if file.content_type == "image/png" else "jpg"
    file_path = f"{club_id}.{ext}"

    try:
        # Get the Supabase client from the DAO
        storage = match_dao.client.storage

        # Upload to club-logos bucket (upsert to overwrite existing)
        result = storage.from_("club-logos").upload(
            file_path,
            content,
            file_options={"content-type": file.content_type, "upsert": "true"}
        )

        # Get public URL
        public_url = storage.from_("club-logos").get_public_url(file_path)

        # Update the club with the new logo URL
        updated_club = match_dao.update_club(club_id=club_id, logo_url=public_url)

        if not updated_club:
            raise HTTPException(status_code=404, detail=f"Club with id {club_id} not found")

        logger.info(f"Uploaded logo for club {club_id}: {public_url}")
        return {"logo_url": public_url, "club": updated_club}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading club logo: {e!s}")
        raise HTTPException(status_code=500, detail=f"Failed to upload logo: {str(e)}")


@app.delete("/api/clubs/{club_id}")
async def delete_club(
    club_id: int, current_user: dict[str, Any] = Depends(require_admin)
):
    """Delete a club (admin only).

    Note: This will fail if there are teams still associated with this club.
    """
    try:
        success = match_dao.delete_club(club_id)
        if success:
            logger.info(f"Deleted club with id {club_id}")
            return {"message": "Club deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Club with id {club_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        logger.error(f"Error deleting club: {error_str}")

        # Check if it's a foreign key constraint violation
        if 'foreign key constraint' in error_str.lower() or 'violates' in error_str.lower():
            raise HTTPException(
                status_code=409,
                detail="Cannot delete club because it has teams associated with it. Remove team associations first."
            )

        raise HTTPException(status_code=500, detail="An unexpected error occurred while deleting the club.")


# Team Mappings CRUD
@app.post("/api/team-mappings")
async def create_team_mapping(
    mapping: TeamMappingCreate, current_user: dict[str, Any] = Depends(require_admin)
):
    """Create a team mapping (admin only)."""
    try:
        result = match_dao.create_team_mapping(
            mapping.team_id, mapping.age_group_id, mapping.division_id
        )
        return result
    except Exception as e:
        logger.error(f"Error creating team mapping: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/team-mappings/{team_id}/{age_group_id}/{division_id}")
async def delete_team_mapping(
    team_id: int,
    age_group_id: int,
    division_id: int,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Delete a team mapping (admin only)."""
    try:
        result = match_dao.delete_team_mapping(team_id, age_group_id, division_id)
        if not result:
            raise HTTPException(status_code=404, detail="Team mapping not found")
        return {"message": "Team mapping deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting team mapping: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# === Match-Scraper Integration Endpoints ===

@app.post("/api/matches/submit")
async def submit_match_async(
    match_data: MatchSubmissionData,
    current_user: dict[str, Any] = Depends(require_match_management_permission)
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
        user_identifier = current_user.get('username') or current_user.get('service_name', 'unknown')
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
                "match_date": match_data.match_date
            }
        }

    except Exception as e:
        logger.error(f"Error submitting match for async processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to queue match: {e!s}")


@app.get("/api/matches/task/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: dict[str, Any] = Depends(require_match_management_permission)
):
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
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {e!s}")


@app.post("/api/match-scraper/matches")
async def add_or_update_scraped_match(
    request: Request,
    match: EnhancedMatch,
    external_match_id: str,
    current_user: dict[str, Any] = Depends(require_match_management_permission)
):
    """Add or update a match from match-scraper with intelligent duplicate handling."""
    try:
        logger.info(f"POST /api/match-scraper/matches - External Match ID: {external_match_id}")
        logger.info(f"POST /api/match-scraper/matches - Match data: {match.model_dump()}")

        # Validate division_id for League matches
        match_type = match_dao.get_match_type_by_id(match.match_type_id)
        if match_type and match_type.get('name') == 'League' and match.division_id is None:
            raise HTTPException(
                status_code=422,
                detail="division_id is required for League matches"
            )

        # Check if match already exists by external_match_id
        existing_match_response = await check_match(
            date=match.match_date,
            homeTeam=str(match.home_team_id),
            awayTeam=str(match.away_team_id),
            season_id=match.season_id,
            age_group_id=match.age_group_id,
            match_type_id=match.match_type_id,
            division_id=match.division_id,
            external_match_id=external_match_id
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
                    "external_match_id": external_match_id
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
                    "external_match_id": external_match_id
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to create match")

    except Exception as e:
        logger.error(f"Error in match-scraper match endpoint: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


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
    external_match_id: str | None = None
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
                        "match_type": "external_match_id"
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
                    "enhanced_match": enhanced_match
                }

        return {"exists": False}
    except Exception as e:
        logger.error(f"Error checking match: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# === Team Roster & Player Profile Endpoints ===


@app.get("/api/teams/{team_id}/players")
async def get_team_players(
    team_id: int,
    current_user: dict[str, Any] = Depends(get_current_user_required)
):
    """
    Get all players on a team for the team roster page.

    Only allows teammates to view roster (users must be on the same team).

    Returns player data needed for player cards:
    - id, display_name, player_number, positions
    - photo fields (photo_1_url, etc.)
    - customization fields (overlay_style, colors)
    - social media handles
    """
    try:
        # Get user's team_id from profile
        user_profile = match_dao.get_user_profile_with_relationships(current_user['user_id'])
        user_team_id = user_profile.get('team_id') if user_profile else None

        # Authorization: user must be on the same team
        if user_team_id != team_id:
            raise HTTPException(
                status_code=403,
                detail="You can only view your own team's roster"
            )

        # Get team info with relationships
        team = match_dao.get_team_with_details(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Get players
        players = match_dao.get_team_players(team_id)

        return {
            "success": True,
            "team": team,
            "players": players
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting team players: {e}")
        raise HTTPException(status_code=500, detail="Failed to get team players")


@app.get("/api/players/{user_id}/profile")
async def get_player_profile(
    user_id: str,
    current_user: dict[str, Any] = Depends(get_current_user_required)
):
    """
    Get a specific player's full profile for the player detail view.

    Only allows teammates to view profile (users must be on the same team).

    Returns full profile data including:
    - Profile info (display_name, number, positions)
    - Photos and customization
    - Social media handles
    - Team info
    - Recent games (player's team matches)
    """
    try:
        # Get current user's team_id
        current_user_profile = match_dao.get_user_profile_with_relationships(current_user['user_id'])
        current_user_team_id = current_user_profile.get('team_id') if current_user_profile else None

        # Get the target player's profile
        target_profile = match_dao.get_user_profile_with_relationships(user_id)
        if not target_profile:
            raise HTTPException(status_code=404, detail="Player not found")

        target_team_id = target_profile.get('team_id')

        # Authorization: users must be on the same team (or viewing own profile)
        if user_id != current_user['user_id'] and current_user_team_id != target_team_id:
            raise HTTPException(
                status_code=403,
                detail="You can only view profiles of your teammates"
            )

        # Get recent games for the player's team (if they have a team)
        recent_games = []
        if target_team_id:
            try:
                # Get matches for the team (already sorted by date desc, take first 5)
                matches = match_dao.get_matches_by_team(target_team_id)[:5]
                for match in matches:
                    recent_games.append({
                        "id": match.get("id"),
                        "match_date": match.get("match_date"),
                        "home_team": match.get("home_team"),
                        "away_team": match.get("away_team"),
                        "home_score": match.get("home_score"),
                        "away_score": match.get("away_score"),
                        "status": match.get("status")
                    })
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
                "club": target_profile.get("club")
            },
            "recent_games": recent_games
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting player profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to get player profile")


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
        "checks": {}
    }

    overall_healthy = True

    # Check basic API
    health_status["checks"]["api"] = {
        "status": "healthy",
        "message": "API is responding"
    }

    # Check database connectivity
    try:
        # Simple database connectivity test
        test_response = match_dao.get_all_age_groups()
        if isinstance(test_response, list):
            health_status["checks"]["database"] = {
                "status": "healthy",
                "message": "Database connection successful",
                "age_groups_count": len(test_response)
            }
        else:
            raise Exception("Unexpected response from database")

    except Exception as e:
        overall_healthy = False
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {e!s}"
        }

    # Check reference data availability
    try:
        seasons = match_dao.get_all_seasons()
        match_types = match_dao.get_all_match_types()

        health_status["checks"]["reference_data"] = {
            "status": "healthy",
            "message": "Reference data available",
            "seasons_count": len(seasons) if isinstance(seasons, list) else 0,
            "match_types_count": len(match_types) if isinstance(match_types, list) else 0
        }

        # Check if we have essential reference data
        if not seasons or not match_types:
            health_status["checks"]["reference_data"]["status"] = "warning"
            health_status["checks"]["reference_data"]["message"] = "Some reference data missing"

    except Exception as e:
        health_status["checks"]["reference_data"] = {
            "status": "unhealthy",
            "message": f"Reference data check failed: {e!s}"
        }

    # Check authentication system
    try:
        if auth_manager and hasattr(auth_manager, 'supabase'):
            health_status["checks"]["auth"] = {
                "status": "healthy",
                "message": "Authentication system operational"
            }
        else:
            health_status["checks"]["auth"] = {
                "status": "warning",
                "message": "Authentication manager not properly initialized"
            }
    except Exception as e:
        health_status["checks"]["auth"] = {
            "status": "unhealthy",
            "message": f"Authentication system error: {e!s}"
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
        database_healthy="database" in health_status["checks"] and health_status["checks"]["database"]["status"] == "healthy",
        auth_healthy="auth" in health_status["checks"] and health_status["checks"]["auth"]["status"] == "healthy"
    )

    # Return appropriate HTTP status code
    if overall_healthy:
        return health_status
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=health_status)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

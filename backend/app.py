import logging
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from auth import AuthManager, get_current_user_optional, get_current_user_required, require_admin, require_team_manager_or_admin, require_admin_or_service_account, require_match_management_permission
from rate_limiter import create_rate_limit_middleware, rate_limit
from csrf_protection import csrf_middleware, get_csrf_token, provide_csrf_token
from api.invites import router as invites_router
from services import InviteService

# Security monitoring imports (conditional)
DISABLE_SECURITY = os.getenv('DISABLE_SECURITY', 'false').lower() == 'true'

if not DISABLE_SECURITY:
    import logfire
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from security_middleware import SecurityMiddleware
    from security_monitoring import get_security_monitor, SecurityEventType, SecuritySeverity, SecurityEvent
    from auth_security import get_auth_security_monitor
    from dao_security_wrapper import create_secure_dao
else:
    # Mock logfire when security is disabled
    class MockLogfireSpan:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def set_attribute(self, key, value):
            pass
    
    class MockLogfire:
        def span(self, name):
            return MockLogfireSpan()
        def info(self, *args, **kwargs):
            pass
        def error(self, *args, **kwargs):
            pass
        def warn(self, *args, **kwargs):
            pass
        def debug(self, *args, **kwargs):
            pass

    # Mock security classes
    from enum import Enum

    class SecurityEventType(str, Enum):
        XSS_ATTEMPT = "xss_attempt"
        SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
        ANOMALOUS_BEHAVIOR = "anomalous_behavior"
        SUSPICIOUS_REQUEST = "suspicious_request"

    class SecuritySeverity(str, Enum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"

    class SecurityEvent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    logfire = MockLogfire()

from dao.enhanced_data_access_fixed import EnhancedSportsDAO
from dao.enhanced_data_access_fixed import SupabaseConnection as DbConnectionHolder

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
from logging_config import setup_logging, get_logger
setup_logging(service_name="backend")
logger = get_logger(__name__)

app = FastAPI(title="Enhanced Sports League API", version="2.0.0")

# Initialize Logfire and OpenTelemetry instrumentation
if not DISABLE_SECURITY and not os.getenv('DISABLE_LOGFIRE', 'false').lower() == 'true':
    logfire.configure(
        token=os.getenv('LOGFIRE_TOKEN'),
        project_name=os.getenv('LOGFIRE_PROJECT', 'missing-table'),
        environment=os.getenv('ENVIRONMENT', 'development'),
    )

# Instrument FastAPI and requests (only if security is enabled)
if not DISABLE_SECURITY:
    FastAPIInstrumentor.instrument_app(app)
    RequestsInstrumentor().instrument()

# Initialize security monitoring (only if security is enabled)
if not DISABLE_SECURITY:
    security_monitor = get_security_monitor()
    auth_security_monitor = get_auth_security_monitor()
    # Add Security Middleware (before CORS)
    app.add_middleware(SecurityMiddleware, security_monitor=security_monitor)
else:
    security_monitor = None
    auth_security_monitor = None

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

    # Add development cloud origins
    dev_origins = [
        "https://dev.missingtable.com",
    ]

    # Add production origins (HTTPS only - HTTP redirects to HTTPS via FrontendConfig)
    production_origins = [
        "https://missingtable.com",
        "https://www.missingtable.com",
    ]

    # Allow additional CORS origins from environment variable
    extra_origins_str = os.getenv('CORS_ORIGINS', '')
    extra_origins = [origin.strip() for origin in extra_origins_str.split(',') if origin.strip()]

    # Get environment-specific origins
    environment = os.getenv('ENVIRONMENT', 'development')
    if environment == 'production':
        # In production, allow both local (for development) and production origins
        return local_origins + production_origins + extra_origins
    else:
        # In development, allow local and dev cloud origins
        return local_origins + dev_origins + extra_origins

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
    base_sports_dao = EnhancedSportsDAO(db_conn_holder_obj)
else:
    logger.info("Using enhanced Supabase connection")
    db_conn_holder_obj = DbConnectionHolder()
    base_sports_dao = EnhancedSportsDAO(db_conn_holder_obj)

# Wrap the DAO with security monitoring (only if security is enabled)
if not DISABLE_SECURITY:
    sports_dao = create_secure_dao(base_sports_dao)
else:
    sports_dao = base_sports_dao

# Initialize Authentication Manager
auth_manager = AuthManager(db_conn_holder_obj.client)


# Enhanced Pydantic models
class EnhancedMatch(BaseModel):
    match_date: str
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int
    season_id: int
    age_group_id: int
    match_type_id: int
    division_id: int | None = None
    status: str | None = "scheduled"  # scheduled, played, postponed, cancelled (maps to match_status in DB)
    created_by: str | None = None  # User ID who created the match (for audit trail)
    updated_by: str | None = None  # User ID who last updated the match
    source: str = "manual"  # Source: manual, match-scraper, import
    external_match_id: str | None = None  # External match identifier (e.g., from match-scraper)


class Team(BaseModel):
    name: str
    city: str
    age_group_ids: list[int]
    division_ids: list[int] | None = None
    academy_team: bool | None = False


# Auth-related models
class UserSignup(BaseModel):
    username: str  # Primary login credential (e.g., gabe_ifa_35)
    password: str
    email: str | None = None  # Optional for notifications
    phone_number: str | None = None  # Optional for SMS
    display_name: str | None = None
    invite_code: str | None = None

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Validate username format: 3-50 chars, alphanumeric and underscores only."""
        import re
        if not re.match(r'^[a-zA-Z0-9_]{3,50}$', v):
            raise ValueError(
                'Username must be 3-50 characters long and contain only letters, numbers, and underscores'
            )
        return v.lower()  # Store usernames in lowercase for consistency

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Validate email format if provided."""
        # Convert empty string to None
        if v == '':
            return None
        if v is not None and '@' not in v:
            raise ValueError('Invalid email format')
        return v


class UserLogin(BaseModel):
    username: str  # Changed from email
    password: str

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Ensure username is lowercase for lookup."""
        return v.lower()


class UserProfile(BaseModel):
    display_name: str | None = None
    role: str | None = None
    team_id: int | None = None
    player_number: int | None = None
    positions: list[str] | None = None


class RoleUpdate(BaseModel):
    user_id: str
    role: str
    team_id: int | None = None


class UserProfileUpdate(BaseModel):
    user_id: str
    username: str | None = None
    display_name: str | None = None
    email: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str

# === Include API Routers ===
app.include_router(invites_router)

# Version endpoint
from endpoints.version import router as version_router
app.include_router(version_router)

# === Authentication Endpoints ===


@app.post("/api/auth/signup")
# @rate_limit("3 per hour")
async def signup(request: Request, user_data: UserSignup):
    """User signup endpoint with username authentication."""
    from auth import username_to_internal_email, check_username_available

    with logfire.span("auth_signup") as span:
        span.set_attribute("auth.username", user_data.username)
        client_ip = security_monitor.get_client_ip(request) if security_monitor else "unknown"
        span.set_attribute("auth.client_ip", client_ip)

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

            # Analyze signup request for threats
            payload = {
                "username": user_data.username,
                "email": user_data.email,
                "display_name": user_data.display_name
            }
            threat_events = security_monitor.analyze_request_for_threats(request, payload) if security_monitor else []

            # Log any threats detected during signup
            for event in threat_events:
                security_monitor.log_security_event(event) if security_monitor else None

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
                        'team_manager': 'team-manager',
                        'team_player': 'team-player',
                        'team_fan': 'team-fan'
                    }
                    profile_data['role'] = role_mapping.get(invite_info['invite_type'], 'team-fan')
                    profile_data['team_id'] = invite_info['team_id']

                # Insert user profile
                db_conn_holder_obj.client.table('user_profiles')\
                    .upsert(profile_data)\
                    .execute()

                # Redeem invitation if used
                if invite_info:
                    invite_service.redeem_invitation(user_data.invite_code, response.user.id)
                    logger.info(f"User {response.user.id} assigned role {profile_data['role']} via invite code")

                logfire.info(
                    "User signup successful",
                    username=user_data.username,
                    user_id=response.user.id,
                    client_ip=client_ip,
                    used_invite=bool(user_data.invite_code)
                )
                span.set_attribute("auth.success", True)
                span.set_attribute("auth.user_id", response.user.id)

                message = f"Account created successfully! Welcome, {user_data.username}!"
                if invite_info:
                    message += f" You have been assigned to {invite_info['team_name']} as a {invite_info['invite_type'].replace('_', ' ')}."

                return {
                    "message": message,
                    "user_id": response.user.id,
                    "username": user_data.username
                }
            else:
                span.set_attribute("auth.success", False)
                raise HTTPException(status_code=400, detail="Failed to create user")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Signup error: {e}")
            span.set_attribute("auth.success", False)
            span.set_attribute("auth.error", str(e))

            logfire.error(
                "User signup failed",
                email=user_data.email,
                error=str(e),
                client_ip=client_ip
            )
            raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/login")
# @rate_limit("5 per minute")
async def login(request: Request, user_data: UserLogin):
    """User login endpoint with username authentication."""
    from auth import username_to_internal_email

    with logfire.span("auth_login") as span:
        span.set_attribute("auth.username", user_data.username)
        client_ip = security_monitor.get_client_ip(request) if security_monitor else "unknown"
        span.set_attribute("auth.client_ip", client_ip)

        try:
            # Convert username to internal email for Supabase Auth
            internal_email = username_to_internal_email(user_data.username)

            # Analyze login request for threats
            payload = {"username": user_data.username}
            threat_events = security_monitor.analyze_request_for_threats(request, payload) if security_monitor else []

            # Log any threats detected during login
            for event in threat_events:
                security_monitor.log_security_event(event) if security_monitor else None

            # Authenticate with Supabase using internal email
            response = db_conn_holder_obj.client.auth.sign_in_with_password({
                "email": internal_email,
                "password": user_data.password
            })

            if response.user and response.session:
                # Get user profile with username
                profile_response = db_conn_holder_obj.client.table('user_profiles')\
                    .select('*')\
                    .eq('id', response.user.id)\
                    .execute()

                # Handle multiple or no profiles
                if profile_response.data and len(profile_response.data) > 0:
                    profile = profile_response.data[0]
                    if len(profile_response.data) > 1:
                        logger.warning(f"Multiple profiles found for user {response.user.id}, using first one")
                else:
                    profile = {'username': user_data.username}  # Fallback

                # Analyze successful login with security monitoring
                auth_attempt = auth_security_monitor.analyze_authentication_attempt(
                    request, user_data.username, True, response.user.id
                ) if auth_security_monitor else None

                span.set_attribute("auth.success", True)
                span.set_attribute("auth.user_id", response.user.id)
                span.set_attribute("auth.risk_score", auth_attempt.risk_score if auth_attempt else 0)

                logfire.info(
                    "User login successful",
                    username=user_data.username,
                    user_id=response.user.id,
                    client_ip=client_ip,
                    risk_score=auth_attempt.risk_score if auth_attempt else 0
                )

                return {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "user": {
                        "id": response.user.id,
                        "username": profile.get('username'),
                        "email": profile.get('email'),  # Real email if provided
                        "display_name": profile.get('display_name'),
                        "role": profile.get('role'),
                        "team_id": profile.get('team_id')
                    }
                }
            else:
                # Analyze failed login
                auth_attempt = auth_security_monitor.analyze_authentication_attempt(
                    request, user_data.username, False, failure_reason="invalid_credentials"
                ) if auth_security_monitor else None

                span.set_attribute("auth.success", False)
                span.set_attribute("auth.risk_score", auth_attempt.risk_score if auth_attempt else 0)

                raise HTTPException(status_code=401, detail="Invalid username or password")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Login error: {e}")

            # Analyze failed login
            auth_attempt = auth_security_monitor.analyze_authentication_attempt(
                request, user_data.username, False, failure_reason=str(e)
            ) if auth_security_monitor else None

            span.set_attribute("auth.success", False)
            span.set_attribute("auth.error", str(e))
            span.set_attribute("auth.risk_score", auth_attempt.risk_score if auth_attempt else 0)

            logfire.error(
                "User login failed",
                username=user_data.username,
                error=str(e),
                client_ip=client_ip,
                risk_score=auth_attempt.risk_score if auth_attempt else 0
            )
            
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
        profile_response = (
            db_conn_holder_obj.client.table("user_profiles")
            .select("""
            *,
            team:teams(id, name, city)
        """)
            .eq("id", current_user["user_id"])
            .execute()
        )

        if profile_response.data and len(profile_response.data) > 0:
            profile = profile_response.data[0]
            return {
                "id": profile["id"],
                "role": profile["role"],
                "team_id": profile.get("team_id"),
                "team": profile.get("team"),
                "display_name": profile.get("display_name"),
                "player_number": profile.get("player_number"),
                "positions": profile.get("positions", []),
                "created_at": profile.get("created_at"),
            }
        else:
            raise HTTPException(status_code=404, detail="Profile not found")

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
        if profile_data.team_id is not None:
            update_data["team_id"] = profile_data.team_id
        if profile_data.player_number is not None:
            update_data["player_number"] = profile_data.player_number
        if profile_data.positions is not None:
            update_data["positions"] = profile_data.positions

        # Only allow role updates by admins
        if profile_data.role is not None:
            if current_user.get("role") != "admin":
                raise HTTPException(status_code=403, detail="Only admins can change roles")
            update_data["role"] = profile_data.role

        if update_data:
            update_data["updated_at"] = "NOW()"
            db_conn_holder_obj.client.table("user_profiles").update(update_data).eq(
                "id", current_user["user_id"]
            ).execute()

        return {"message": "Profile updated successfully"}

    except Exception as e:
        logger.error(f"Update profile error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")


@app.get("/api/auth/users")
async def get_users(current_user: dict[str, Any] = Depends(require_admin)):
    """Get all users (admin only)."""
    try:
        response = (
            db_conn_holder_obj.client.table("user_profiles")
            .select("""
            *,
            team:teams(id, name, city)
        """)
            .order("created_at", desc=True)
            .execute()
        )

        return response.data

    except Exception as e:
        logger.error(f"Get users error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get users")


@app.post("/api/auth/refresh")
async def refresh_token(request: Request, refresh_data: RefreshTokenRequest):
    """Refresh JWT token using refresh token."""
    with logfire.span("auth_refresh") as span:
        try:
            response = db_conn_holder_obj.client.auth.refresh_session(refresh_data.refresh_token)
            
            if response.session:
                span.set_attribute("auth.success", True)
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
                span.set_attribute("auth.success", False)
                raise HTTPException(status_code=401, detail="Failed to refresh token")
                
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            span.set_attribute("auth.success", False)
            span.set_attribute("auth.error", str(e))
            raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.get("/api/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user_required)):
    """Get current user info for frontend auth state."""
    try:
        # Get fresh profile data
        profile_response = db_conn_holder_obj.client.table('user_profiles').select('''
            *,
            team:teams(id, name, city)
        ''').eq('id', current_user['user_id']).execute()
        
        profile = profile_response.data[0] if profile_response.data else {}
        
        return {
            "success": True,
            "user": {
                "id": current_user['user_id'],
                "email": current_user['email'],
                "profile": {
                    "role": profile.get('role', 'team-fan'),
                    "team_id": profile.get('team_id'),
                    "display_name": profile.get('display_name'),
                    "name": profile.get('name'),
                    "player_number": profile.get('player_number'),
                    "positions": profile.get('positions'),
                    "team": profile.get('team')
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
        update_data = {"role": role_data.role, "updated_at": "NOW()"}

        if role_data.team_id:
            update_data["team_id"] = role_data.team_id

        db_conn_holder_obj.client.table("user_profiles").update(update_data).eq(
            "id", role_data.user_id
        ).execute()

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
                existing = (
                    db_conn_holder_obj.client.table("user_profiles")
                    .select("id")
                    .eq("username", username.lower())
                    .execute()
                )

                if existing.data and existing.data[0]["id"] != profile_data.user_id:
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
        db_conn_holder_obj.client.table("user_profiles").update(update_data).eq(
            "id", profile_data.user_id
        ).execute()

        return {"message": "User profile updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user profile error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update user profile: {str(e)}")


# === CSRF Token Endpoint ===


@app.get("/api/csrf-token")
async def get_csrf_token_endpoint(request: Request, response: Response):
    """Get CSRF token for the session."""
    return await provide_csrf_token(request, response)


# === Reference Data Endpoints ===


@app.get("/api/age-groups")
async def get_age_groups(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user_required)
):
    """Get all age groups."""
    try:
        if security_monitor:
            client_ip = security_monitor.get_client_ip(request)
            age_groups = sports_dao.get_all_age_groups(client_ip=client_ip)
        else:
            age_groups = sports_dao.get_all_age_groups()
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
        seasons = sports_dao.get_all_seasons()
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
        current_season = sports_dao.get_current_season()
        if not current_season:
            # Default to 2024-2025 season if no current season found
            seasons = sports_dao.get_all_seasons()
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
        active_seasons = sports_dao.get_active_seasons()
        return active_seasons
    except Exception as e:
        logger.error(f"Error retrieving active seasons: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/match-types")
async def get_match_types(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get all match types."""
    try:
        match_types = sports_dao.get_all_match_types()
        return match_types
    except Exception as e:
        logger.error(f"Error retrieving match types: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/divisions")
async def get_divisions(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get all divisions."""
    try:
        divisions = sports_dao.get_all_divisions()
        return divisions
    except Exception as e:
        logger.error(f"Error retrieving divisions: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# === Enhanced Team Endpoints ===


@app.get("/api/teams")
async def get_teams(
    current_user: dict[str, Any] = Depends(get_current_user_required),
    match_type_id: int | None = None,
    age_group_id: int | None = None
):
    """Get teams, optionally filtered by match type and age group."""
    try:
        if match_type_id and age_group_id:
            teams = sports_dao.get_teams_by_match_type_and_age_group(match_type_id, age_group_id)
        else:
            teams = sports_dao.get_all_teams()
        return teams
    except Exception as e:
        logger.error(f"Error retrieving teams: {e!s}")
        raise HTTPException(
            status_code=503, detail="Database connection failed. Please check Supabase connection."
        )


@app.post("/api/teams")
async def add_team(team: Team):
    """Add a new team with age groups and optionally divisions."""
    try:
        success = sports_dao.add_team(
            team.name, team.city, team.age_group_ids, team.division_ids, team.academy_team
        )
        if success:
            return {"message": "Team added successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add team")
    except Exception as e:
        logger.error(f"Error adding team: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# === Enhanced Match Endpoints ===


@app.get("/api/matches")
async def get_matches(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user_required),
    season_id: Optional[int] = Query(None, description="Filter by season ID"),
    age_group_id: Optional[int] = Query(None, description="Filter by age group ID"),
    division_id: Optional[int] = Query(None, description="Filter by division ID"),
    team_id: Optional[int] = Query(None, description="Filter by team ID (home or away)"),
    match_type: Optional[str] = Query(None, description="Filter by match type name"),
    start_date: Optional[str] = Query(None, description="Filter by start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (YYYY-MM-DD)")
):
    """Get all matches with optional filters (requires authentication)."""
    try:
        if security_monitor:
            client_ip = security_monitor.get_client_ip(request)
            matches = sports_dao.get_all_matches(
                client_ip=client_ip,
                season_id=season_id,
                age_group_id=age_group_id,
                division_id=division_id,
                team_id=team_id,
                match_type=match_type,
                start_date=start_date,
                end_date=end_date
            )
        else:
            matches = sports_dao.get_all_matches(
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
        # Get all matches and filter by ID
        if security_monitor:
            client_ip = security_monitor.get_client_ip(request)
            matches = sports_dao.get_all_matches(client_ip=client_ip)
        else:
            matches = sports_dao.get_all_matches()

        # Find the match with matching ID
        match = next((m for m in matches if m.get("id") == match_id), None)

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
        if security_monitor:
            client_ip = security_monitor.get_client_ip(request)
            result = sports_dao.delete_match(match_id, client_ip=client_ip)
        else:
            result = sports_dao.delete_match(match_id)

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
        match_type = sports_dao.get_match_type_by_id(match.match_type_id)
        if match_type and match_type.get('name') == 'League' and match.division_id is None:
            raise HTTPException(
                status_code=422,
                detail="division_id is required for League matches"
            )

        success = sports_dao.add_match(
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
    match_id: int, match: EnhancedMatch, current_user: dict[str, Any] = Depends(require_admin_or_service_account)
):
    """Update an existing match (admin or service account with manage_matches permission)."""
    try:
        # Get current match to check permissions
        current_match = sports_dao.get_match_by_id(match_id)
        if not current_match:
            raise HTTPException(status_code=404, detail="Match not found")

        # Check if user can edit this match
        if not auth_manager.can_edit_match(current_user, current_match['home_team_id'], current_match['away_team_id']):
            raise HTTPException(status_code=403, detail="You don't have permission to edit this match")

        # Validate division_id for League matches
        match_type = sports_dao.get_match_type_by_id(match.match_type_id)
        if match_type and match_type.get('name') == 'League' and match.division_id is None:
            raise HTTPException(
                status_code=422,
                detail="division_id is required for League matches"
            )

        updated_match = sports_dao.update_match(
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


class MatchPatch(BaseModel):
    """Model for partial match updates."""
    home_score: int | None = None
    away_score: int | None = None
    match_status: str | None = None
    match_date: str | None = None
    home_team_id: int | None = None
    away_team_id: int | None = None
    season_id: int | None = None
    age_group_id: int | None = None
    match_type_id: int | None = None
    division_id: int | None = None
    status: str | None = None
    external_match_id: str | None = None  # External match identifier

    class Config:
        # Validation for scores
        @staticmethod
        def validate_score(v):
            if v is not None and v < 0:
                raise ValueError("Score must be non-negative")
            return v


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
        current_match = sports_dao.get_match_by_id(match_id)
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
        match_type = sports_dao.get_match_type_by_id(final_match_type_id)
        if match_type and match_type.get('name') == 'League' and final_division_id is None:
            raise HTTPException(
                status_code=422,
                detail="division_id is required for League matches"
            )

        logger.info(f"PATCH /api/matches/{match_id} - Calling update_match with: {update_data}")
        updated_match = sports_dao.update_match(**update_data)
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
        current_match = sports_dao.get_match_by_id(match_id)
        if not current_match:
            raise HTTPException(status_code=404, detail="Match not found")

        # Check if user can edit this match
        if not auth_manager.can_edit_match(current_user, current_match['home_team_id'], current_match['away_team_id']):
            raise HTTPException(status_code=403, detail="You don't have permission to delete this match")

        success = sports_dao.delete_match(match_id)
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
        matches = sports_dao.get_matches_by_team(team_id, season_id=season_id, age_group_id=age_group_id)
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
            current_season = sports_dao.get_current_season()
            if current_season:
                season_id = current_season["id"]
            else:
                # Default to 2024-2025 season
                seasons = sports_dao.get_all_seasons()
                default_season = next(
                    (s for s in seasons if s["name"] == "2024-2025"),
                    seasons[0] if seasons else None,
                )
                if default_season:
                    season_id = default_season["id"]

        # If no age group specified, use U13
        if not age_group_id:
            age_groups = sports_dao.get_all_age_groups()
            u13_age_group = next(
                (ag for ag in age_groups if ag["name"] == "U13"),
                age_groups[0] if age_groups else None,
            )
            if u13_age_group:
                age_group_id = u13_age_group["id"]

        table = sports_dao.get_league_table(
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
class AgeGroupCreate(BaseModel):
    name: str


class AgeGroupUpdate(BaseModel):
    name: str


@app.post("/api/age-groups")
async def create_age_group(
    age_group: AgeGroupCreate, current_user: dict[str, Any] = Depends(require_admin)
):
    """Create a new age group (admin only)."""
    try:
        result = sports_dao.create_age_group(age_group.name)
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
        result = sports_dao.update_age_group(age_group_id, age_group.name)
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
        result = sports_dao.delete_age_group(age_group_id)
        if not result:
            raise HTTPException(status_code=404, detail="Age group not found")
        return {"message": "Age group deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting age group: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# Seasons CRUD
class SeasonCreate(BaseModel):
    name: str
    start_date: str
    end_date: str


class SeasonUpdate(BaseModel):
    name: str
    start_date: str
    end_date: str


@app.post("/api/seasons")
async def create_season(
    season: SeasonCreate, current_user: dict[str, Any] = Depends(require_admin)
):
    """Create a new season (admin only)."""
    try:
        result = sports_dao.create_season(season.name, season.start_date, season.end_date)
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
        result = sports_dao.update_season(
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
        result = sports_dao.delete_season(season_id)
        if not result:
            raise HTTPException(status_code=404, detail="Season not found")
        return {"message": "Season deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting season: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# Divisions CRUD
class DivisionCreate(BaseModel):
    name: str
    description: str | None = None


class DivisionUpdate(BaseModel):
    name: str
    description: str | None = None


@app.post("/api/divisions")
async def create_division(
    division: DivisionCreate, current_user: dict[str, Any] = Depends(require_admin)
):
    """Create a new division (admin only)."""
    try:
        result = sports_dao.create_division(division.name, division.description)
        return result
    except Exception as e:
        logger.error(f"Error creating division: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/divisions/{division_id}")
async def update_division(
    division_id: int,
    division: DivisionUpdate,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Update a division (admin only)."""
    try:
        result = sports_dao.update_division(division_id, division.name, division.description)
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
        result = sports_dao.delete_division(division_id)
        if not result:
            raise HTTPException(status_code=404, detail="Division not found")
        return {"message": "Division deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting division: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# Teams CRUD (update existing)
class TeamUpdate(BaseModel):
    name: str
    city: str
    academy_team: bool | None = False


class TeamMatchTypeMapping(BaseModel):
    match_type_id: int
    age_group_id: int


@app.put("/api/teams/{team_id}")
async def update_team(
    team_id: int, team: TeamUpdate, current_user: dict[str, Any] = Depends(require_admin)
):
    """Update a team (admin only)."""
    try:
        result = sports_dao.update_team(team_id, team.name, team.city, team.academy_team)
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
        result = sports_dao.delete_team(team_id)
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
        success = sports_dao.add_team_match_type_participation(
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
        success = sports_dao.remove_team_match_type_participation(
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


# Team Mappings CRUD
class TeamMappingCreate(BaseModel):
    team_id: int
    age_group_id: int
    division_id: int


@app.post("/api/team-mappings")
async def create_team_mapping(
    mapping: TeamMappingCreate, current_user: dict[str, Any] = Depends(require_admin)
):
    """Create a team mapping (admin only)."""
    try:
        result = sports_dao.create_team_mapping(
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
        result = sports_dao.delete_team_mapping(team_id, age_group_id, division_id)
        if not result:
            raise HTTPException(status_code=404, detail="Team mapping not found")
        return {"message": "Team mapping deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting team mapping: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# === Match-Scraper Integration Endpoints ===

# Pydantic model for async match submission
class MatchSubmissionData(BaseModel):
    """
    Match data for async submission to Celery queue.
    This model accepts flexible data from match-scraper.
    """
    home_team: str  # Team name (will be looked up)
    away_team: str  # Team name (will be looked up)
    match_date: str  # ISO format date
    season: str  # Season name (e.g., "2024-25")
    age_group: str | None = None
    division: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    match_status: str = "scheduled"  # scheduled, live, played, postponed, cancelled
    match_type: str | None = None
    location: str | None = None
    external_match_id: str | None = None  # External identifier for deduplication


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
        raise HTTPException(status_code=500, detail=f"Failed to queue match: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


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
        match_type = sports_dao.get_match_type_by_id(match.match_type_id)
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
            updated_match = sports_dao.update_match(
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
            success = sports_dao.add_match_with_external_id(
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
            matches = sports_dao.get_all_matches()
            for match in matches:
                if match.get("external_match_id") == external_match_id:
                    return {
                        "exists": True,
                        "match_id": match.get("id"),
                        "match": match,
                        "match_type": "external_match_id"
                    }

        # Check for duplicate based on comprehensive match context
        matches = sports_dao.get_all_matches()
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


# === Security Analytics Endpoints ===

@app.get("/api/security/analytics")
async def get_security_analytics(
    hours: int = Query(24, description="Time period in hours"),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Get security analytics (admin only)."""
    try:
        analytics = security_monitor.get_security_analytics(hours) if security_monitor else {}
        
        logfire.info(
            "Security analytics requested",
            user_id=current_user.get('user_id'),
            hours=hours,
            total_events=analytics.get('total_events', 0)
        )
        
        return analytics
    except Exception as e:
        logger.error(f"Error retrieving security analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve security analytics")

@app.get("/api/security/user/{user_id}/summary")
async def get_user_security_summary(
    user_id: str,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Get security summary for a specific user (admin only)."""
    try:
        summary = auth_security_monitor.get_user_security_summary(user_id) if auth_security_monitor else {}
        
        logfire.info(
            "User security summary requested",
            admin_user_id=current_user.get('user_id'),
            target_user_id=user_id,
            active_sessions=summary.get('session_count', 0)
        )
        
        return summary
    except Exception as e:
        logger.error(f"Error retrieving user security summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve user security summary")

@app.post("/api/security/cleanup-sessions")
async def cleanup_expired_sessions(
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Cleanup expired sessions (admin only)."""
    try:
        auth_security_monitor.cleanup_expired_sessions() if auth_security_monitor else None
        
        logfire.info(
            "Session cleanup initiated",
            admin_user_id=current_user.get('user_id')
        )
        
        return {"message": "Expired sessions cleaned up successfully"}
    except Exception as e:
        logger.error(f"Error during session cleanup: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup sessions")

@app.post("/api/security/client-events")
async def receive_client_security_events(request: Request, event_data: Dict[str, Any]):
    """Receive security events from client-side monitoring."""
    try:
        client_ip = security_monitor.get_client_ip(request) if security_monitor else "unknown"
        events = event_data.get('events', [])
        session_id = event_data.get('sessionId', 'unknown')
        user_behavior = event_data.get('userBehaviorSummary', {})
        
        logfire.info(
            "Client security events received",
            event_count=len(events),
            session_id=session_id,
            client_ip=client_ip
        )
        
        # Process each client-side security event
        for event in events:
            event_type = event.get('type', 'unknown_client_event')
            severity = event.get('severity', 'low')
            details = event.get('details', {})
            
            # Map client-side event types to server-side types
            if event_type in ['xss_attempt', 'sql_injection_attempt']:
                server_event_type = SecurityEventType.XSS_ATTEMPT if 'xss' in event_type else SecurityEventType.SQL_INJECTION_ATTEMPT
                server_severity = SecuritySeverity.CRITICAL
            elif event_type == 'csp_violation':
                server_event_type = SecurityEventType.XSS_ATTEMPT
                server_severity = SecuritySeverity.HIGH
            elif event_type in ['click_bombing', 'robotic_clicking', 'suspicious_navigation']:
                server_event_type = SecurityEventType.ANOMALOUS_BEHAVIOR
                server_severity = SecuritySeverity.MEDIUM
            else:
                server_event_type = SecurityEventType.SUSPICIOUS_REQUEST
                server_severity = SecuritySeverity.LOW
            
            # Create server-side security event
            security_event = SecurityEvent(
                event_type=server_event_type,
                severity=server_severity,
                source_ip=client_ip,
                user_agent=request.headers.get("user-agent", ""),
                timestamp=datetime.utcnow(),
                endpoint=details.get('location', request.url.path),
                method="CLIENT_SIDE",
                additional_context={
                    "client_event_type": event_type,
                    "client_details": details,
                    "session_id": session_id,
                    "user_behavior": user_behavior,
                    "client_timestamp": event.get('timestamp')
                }
            )
            security_event.risk_score = security_monitor.calculate_risk_score(security_event) if security_monitor else 0
            
            # Log the security event
            security_monitor.log_security_event(security_event) if security_monitor else None
        
        return {"message": "Security events processed successfully", "processed_count": len(events)}
        
    except Exception as e:
        logger.error(f"Error processing client security events: {e}")
        raise HTTPException(status_code=500, detail="Failed to process security events")

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
        test_response = sports_dao.get_all_age_groups()
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
            "message": f"Database connection failed: {str(e)}"
        }
    
    # Check reference data availability
    try:
        seasons = sports_dao.get_all_seasons()
        match_types = sports_dao.get_all_match_types()

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
            "message": f"Reference data check failed: {str(e)}"
        }
    
    # Check authentication system (if not disabled)
    if not DISABLE_SECURITY:
        try:
            # Test that auth manager is working
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
                "message": f"Authentication system error: {str(e)}"
            }
    else:
        health_status["checks"]["auth"] = {
            "status": "disabled",
            "message": "Security features disabled"
        }
    
    # Check security monitoring (if enabled)
    if not DISABLE_SECURITY and security_monitor:
        try:
            health_status["checks"]["security"] = {
                "status": "healthy",
                "message": "Security monitoring active"
            }
        except Exception as e:
            health_status["checks"]["security"] = {
                "status": "warning",
                "message": f"Security monitoring issue: {str(e)}"
            }
    else:
        health_status["checks"]["security"] = {
            "status": "disabled",
            "message": "Security monitoring disabled"
        }
    
    # Set overall status
    check_statuses = [check.get("status", "unknown") for check in health_status["checks"].values()]
    
    if "unhealthy" in check_statuses:
        health_status["status"] = "unhealthy"
        overall_healthy = False
    elif "warning" in check_statuses:
        health_status["status"] = "degraded"
    
    # Log health check if monitoring is enabled
    if not DISABLE_SECURITY:
        logfire.info(
            "Health check performed",
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

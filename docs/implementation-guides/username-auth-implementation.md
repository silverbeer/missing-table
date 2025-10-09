# Username Authentication Implementation Guide

**Feature Branch**: `feature/username-auth-refactor`
**Implementation**: Option 1 (Hybrid Approach)
**Estimated Time**: 1-2 weeks
**Status**: In Progress

---

## Overview

Replace email-based login with username-based authentication while maintaining Supabase Auth infrastructure. Users login with usernames like `gabe_ifa_35`, and the system internally converts these to `gabe_ifa_35@missingtable.local` for Supabase Auth compatibility.

---

## Implementation Phases

### Phase 1: Database Schema Changes
### Phase 2: Backend Authentication Logic
### Phase 3: Frontend Components
### Phase 4: Testing & Migration
### Phase 5: Deployment

---

## Phase 1: Database Schema Changes

**Estimated Time**: 2-4 hours
**Risk Level**: Low

### Step 1.1: Create Migration File

Create: `supabase/migrations/20241009000017_add_username_auth.sql`

```sql
-- Add username column to user_profiles table
-- Note: user_profiles is created by Supabase Auth triggers, not in our migrations

-- First, check if user_profiles exists in public schema or if we need to create it
-- This migration assumes user_profiles exists from Supabase Auth

-- Add username column (nullable initially for existing users)
ALTER TABLE public.user_profiles
ADD COLUMN IF NOT EXISTS username VARCHAR(50) UNIQUE;

-- Add index for fast username lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_profiles_username
ON public.user_profiles(username);

-- Make email nullable (was previously required via Supabase Auth)
-- Email becomes optional for username-only accounts
ALTER TABLE public.user_profiles
ALTER COLUMN email DROP NOT NULL;

-- Add phone number for future SMS notifications (optional)
ALTER TABLE public.user_profiles
ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20);

-- Add created_at and updated_at if not exists
ALTER TABLE public.user_profiles
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE public.user_profiles
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_user_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS user_profiles_updated_at ON public.user_profiles;
CREATE TRIGGER user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_user_profiles_updated_at();

-- Add comments for documentation
COMMENT ON COLUMN public.user_profiles.username IS 'Unique username for login (e.g., gabe_ifa_35)';
COMMENT ON COLUMN public.user_profiles.email IS 'Optional email for notifications (parent email)';
COMMENT ON COLUMN public.user_profiles.phone_number IS 'Optional phone number for SMS notifications';
```

### Step 1.2: Create Rollback Migration (Optional)

Create: `supabase/migrations/20241009000017_add_username_auth_rollback.sql`

```sql
-- Rollback username authentication changes

-- Remove phone number column
ALTER TABLE public.user_profiles
DROP COLUMN IF EXISTS phone_number;

-- Make email required again (if rolling back)
-- Note: This will fail if any users have NULL emails
-- ALTER TABLE public.user_profiles
-- ALTER COLUMN email SET NOT NULL;

-- Remove username column
DROP INDEX IF EXISTS idx_user_profiles_username;
ALTER TABLE public.user_profiles
DROP COLUMN IF EXISTS username;

-- Remove trigger and function
DROP TRIGGER IF EXISTS user_profiles_updated_at ON public.user_profiles;
DROP FUNCTION IF EXISTS update_user_profiles_updated_at();
```

### Step 1.3: Apply Migration Locally

```bash
# Start local Supabase
supabase start

# Apply migration
supabase db push

# Verify migration
supabase db diff

# Check user_profiles table structure
psql $DATABASE_URL -c "\d user_profiles"
```

### Step 1.4: Verify Schema Changes

```bash
# Connect to database and verify
cd backend
uv run python -c "
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY'))

# Check if username column exists
result = client.table('user_profiles').select('*').limit(0).execute()
print('Columns:', result.data)
"
```

**✅ Phase 1 Complete Checklist:**
- [ ] Migration file created
- [ ] Rollback migration created
- [ ] Migration applied locally
- [ ] Schema verified in database
- [ ] No errors in Supabase logs

---

## Phase 2: Backend Authentication Logic

**Estimated Time**: 2-3 days
**Risk Level**: Medium-High

### Step 2.1: Update Pydantic Models

**File**: `backend/app.py` (around line 267)

```python
# Current models
class UserSignup(BaseModel):
    email: str
    password: str
    display_name: str | None = None
    invite_code: str | None = None

class UserLogin(BaseModel):
    email: str
    password: str
```

**Update to:**

```python
import re

class UserSignup(BaseModel):
    username: str  # Primary login credential
    password: str
    email: str | None = None  # Optional for notifications
    phone_number: str | None = None  # Optional for SMS
    display_name: str | None = None
    invite_code: str | None = None

    @validator('username')
    def validate_username(cls, v):
        """Validate username format: 3-50 chars, alphanumeric and underscores only."""
        if not re.match(r'^[a-zA-Z0-9_]{3,50}$', v):
            raise ValueError(
                'Username must be 3-50 characters long and contain only letters, numbers, and underscores'
            )
        return v.lower()  # Store usernames in lowercase for consistency

    @validator('email')
    def validate_email(cls, v):
        """Validate email format if provided."""
        if v is not None and '@' not in v:
            raise ValueError('Invalid email format')
        return v


class UserLogin(BaseModel):
    username: str  # Changed from email
    password: str

    @validator('username')
    def validate_username(cls, v):
        """Ensure username is lowercase for lookup."""
        return v.lower()
```

### Step 2.2: Create Username Helper Functions

**File**: `backend/auth.py` (add at top, around line 30)

```python
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
```

### Step 2.3: Update Signup Endpoint

**File**: `backend/app.py` (line 272-379)

```python
@app.post("/api/auth/signup")
# @rate_limit("3 per hour")
async def signup(request: Request, user_data: UserSignup):
    """User signup endpoint with username authentication."""
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
                profile_data = {
                    'id': response.user.id,
                    'username': user_data.username,
                    'email': user_data.email,  # Optional real email
                    'phone_number': user_data.phone_number,  # Optional phone
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
                username=user_data.username,
                error=str(e),
                client_ip=client_ip
            )
            raise HTTPException(status_code=400, detail=str(e))
```

### Step 2.4: Update Login Endpoint

**File**: `backend/app.py` (line 381-450)

```python
@app.post("/api/auth/login")
# @rate_limit("5 per minute")
async def login(request: Request, user_data: UserLogin):
    """User login endpoint with username authentication."""
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

                logfire.info(
                    "User login successful",
                    username=user_data.username,
                    user_id=response.user.id,
                    role=profile.get('role'),
                    client_ip=client_ip
                )
                span.set_attribute("auth.success", True)
                span.set_attribute("auth.user_id", response.user.id)
                span.set_attribute("auth.role", profile.get('role'))

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
                # Failed login - analyze with security monitoring
                auth_attempt = auth_security_monitor.analyze_authentication_attempt(
                    request, user_data.username, False, None
                ) if auth_security_monitor else None

                span.set_attribute("auth.success", False)
                raise HTTPException(status_code=401, detail="Invalid username or password")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Login error: {e}")
            span.set_attribute("auth.success", False)
            span.set_attribute("auth.error", str(e))

            # Analyze failed login
            auth_attempt = auth_security_monitor.analyze_authentication_attempt(
                request, user_data.username, False, None
            ) if auth_security_monitor else None

            logfire.error(
                "User login failed",
                username=user_data.username,
                error=str(e),
                client_ip=client_ip
            )
            raise HTTPException(status_code=401, detail="Invalid username or password")
```

### Step 2.5: Add Username Availability Check Endpoint

**File**: `backend/app.py` (add new endpoint)

```python
@app.get("/api/auth/username-available/{username}")
async def check_username_availability(username: str):
    """
    Check if a username is available.

    Returns:
    - available: boolean
    - suggestions: list of alternative usernames if taken
    """
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
            suggestions = [
                f"{username}_1",
                f"{username}_2",
                f"{username}_{hash(username) % 100}",
            ]

            return {
                "available": False,
                "message": f"Username '{username}' is taken",
                "suggestions": suggestions
            }

    except Exception as e:
        logger.error(f"Error checking username: {e}")
        raise HTTPException(status_code=500, detail="Error checking username availability")
```

### Step 2.6: Update AuthManager Token Verification

**File**: `backend/auth.py` (line 36-78)

Update the `verify_token` method to include username in user data:

```python
def verify_token(self, token: str) -> dict[str, Any] | None:
    """Verify JWT token and return user data."""
    try:
        # Decode JWT token
        payload = jwt.decode(
            token, self.jwt_secret, algorithms=["HS256"], audience="authenticated"
        )

        user_id = payload.get("sub")
        if not user_id:
            return None

        # Get user profile with role and username
        profile_response = (
            self.supabase.table("user_profiles").select("*").eq("id", user_id).execute()
        )

        if not profile_response.data or len(profile_response.data) == 0:
            logger.warning(f"No profile found for user {user_id}")
            return None

        profile = profile_response.data[0]
        if len(profile_response.data) > 1:
            logger.warning(f"Multiple profiles found for user {user_id}, using first one")

        # Extract email from payload (might be internal email)
        email = payload.get("email")

        # If internal email, extract username; otherwise use profile username
        if email and is_internal_email(email):
            username = internal_email_to_username(email)
        else:
            username = profile.get("username")

        return {
            "user_id": user_id,
            "username": username or profile.get("username"),  # Primary identifier
            "email": profile.get("email"),  # Real email (optional)
            "role": profile["role"],
            "team_id": profile.get("team_id"),
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
```

### Step 2.7: Update Logging References

**Throughout backend files**, update logging statements from:
```python
logger.info(f"User {user_data.get('email')} ...")
```

To:
```python
logger.info(f"User {user_data.get('username')} ...")
```

**Files to update:**
- `backend/app.py` - All authentication logs
- `backend/auth_security.py` - Authentication monitoring
- `backend/security_monitoring.py` - Security event logs

**✅ Phase 2 Complete Checklist:**
- [ ] Pydantic models updated
- [ ] Helper functions created
- [ ] Signup endpoint updated
- [ ] Login endpoint updated
- [ ] Username availability endpoint added
- [ ] AuthManager updated
- [ ] All logging references updated
- [ ] Imports added (re, validators)
- [ ] Backend tests passing

---

## Phase 3: Frontend Components

**Estimated Time**: 1-2 days
**Risk Level**: Medium

### Step 3.1: Update Auth Store

**File**: `frontend/src/stores/auth.js`

```javascript
// Update state to include username
const state = reactive({
  user: null,
  session: null,
  profile: null,
  loading: false,
  error: null,
});

// Update computed properties
const username = computed(() => state.profile?.username);

// Update signup method
const signup = async (username, password, displayName, email = null, phoneNumber = null) => {
  try {
    setLoading(true);
    clearError();

    const response = await fetch(`${API_URL}/api/auth/signup`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username,
        password,
        display_name: displayName || username,
        email,  // Optional
        phone_number: phoneNumber,  // Optional
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Signup failed');
    }

    const data = await response.json();
    return { success: true, message: data.message || 'Signup successful!' };
  } catch (error) {
    setError(error.message);
    return { success: false, error: error.message };
  } finally {
    setLoading(false);
  }
};

// Update signupWithInvite
const signupWithInvite = async (username, password, displayName, inviteCode, email = null) => {
  try {
    setLoading(true);
    clearError();

    const response = await fetch(`${API_URL}/api/auth/signup`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username,
        password,
        display_name: displayName || username,
        email,  // Optional
        invite_code: inviteCode,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Signup with invite failed');
    }

    const data = await response.json();
    return { success: true, message: data.message || 'Signup successful!' };
  } catch (error) {
    setError(error.message);
    return { success: false, error: error.message };
  } finally {
    setLoading(false);
  }
};

// Update login method
const login = async (username, password) => {
  try {
    setLoading(true);
    clearError();

    const response = await fetch(`${API_URL}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username,
        password,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Login failed');
    }

    const data = await response.json();

    // Set session and user data
    setSession({
      access_token: data.access_token,
      refresh_token: data.refresh_token,
    });
    setUser(data.user);
    setProfile(data.user);

    return { success: true, user: data.user };
  } catch (error) {
    setError(error.message);
    return { success: false, error: error.message };
  } finally {
    setLoading(false);
  }
};

// Add username availability check
const checkUsernameAvailable = async (username) => {
  try {
    const response = await fetch(
      `${API_URL}/api/auth/username-available/${username}`
    );
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error checking username:', error);
    return { available: false, message: 'Error checking username' };
  }
};

// Export new methods
export const useAuthStore = () => {
  return {
    state,
    isAuthenticated,
    isAdmin,
    isTeamManager,
    canManageTeam,
    userRole,
    userTeamId,
    username,  // New
    setLoading,
    setError,
    clearError,
    setUser,
    setSession,
    setProfile,
    signup,
    signupWithInvite,
    login,
    logout,
    checkUsernameAvailable,  // New
    // ... other methods
  };
};
```

### Step 3.2: Update LoginForm Component

**File**: `frontend/src/components/LoginForm.vue`

```vue
<template>
  <div class="login-form">
    <div class="form-container">
      <h2>{{ showInviteSignup ? 'Sign Up with Invite' : 'Login' }}</h2>

      <form @submit.prevent="handleSubmit" class="auth-form">
        <!-- USERNAME INPUT (was email) -->
        <div class="form-group">
          <label for="username">Username:</label>
          <input
            id="username"
            v-model="form.username"
            type="text"
            required
            :disabled="authStore.state.loading"
            placeholder="e.g., gabe_ifa_35"
            pattern="[a-zA-Z0-9_]{3,50}"
            @blur="checkUsername"
          />
          <small class="input-hint">
            3-50 characters: letters, numbers, and underscores only
          </small>

          <!-- Username availability indicator -->
          <div v-if="usernameStatus.checked && showInviteSignup" class="username-status">
            <span v-if="usernameStatus.available" class="status-available">
              ✓ Username available
            </span>
            <span v-else class="status-taken">
              ✗ Username taken
              <span v-if="usernameStatus.suggestions && usernameStatus.suggestions.length > 0">
                - Try:
                <button
                  v-for="suggestion in usernameStatus.suggestions"
                  :key="suggestion"
                  type="button"
                  @click="form.username = suggestion"
                  class="suggestion-btn"
                >
                  {{ suggestion }}
                </button>
              </span>
            </span>
          </div>
        </div>

        <div class="form-group">
          <label for="password">Password:</label>
          <input
            id="password"
            v-model="form.password"
            type="password"
            required
            :disabled="authStore.state.loading"
            placeholder="Enter your password"
            minlength="6"
          />
        </div>

        <!-- SIGNUP-ONLY FIELDS -->
        <div v-if="showInviteSignup">
          <div class="form-group">
            <label for="inviteCode">Invite Code:</label>
            <input
              id="inviteCode"
              v-model="form.inviteCode"
              type="text"
              required
              :disabled="authStore.state.loading"
              placeholder="Enter your invite code"
              @blur="validateInviteCode"
            />
            <div v-if="inviteInfo" class="invite-info">
              <p>
                ✓ Valid invite for <strong>{{ inviteInfo.team_name }}</strong>
              </p>
              <p>
                Role:
                <strong>{{ inviteInfo.invite_type.replace('_', ' ') }}</strong>
              </p>
            </div>
          </div>

          <div class="form-group">
            <label for="displayName">Display Name (optional):</label>
            <input
              id="displayName"
              v-model="form.displayName"
              type="text"
              :disabled="authStore.state.loading"
              placeholder="How should we display your name?"
            />
          </div>

          <!-- OPTIONAL CONTACT INFO (collapsed by default) -->
          <div class="optional-section">
            <button
              type="button"
              @click="showOptionalFields = !showOptionalFields"
              class="toggle-optional"
            >
              {{ showOptionalFields ? '▼' : '▶' }} Optional Contact Info
              <small>(for notifications)</small>
            </button>

            <div v-show="showOptionalFields" class="optional-fields">
              <div class="form-group">
                <label for="email">Email (optional):</label>
                <input
                  id="email"
                  v-model="form.email"
                  type="email"
                  :disabled="authStore.state.loading"
                  placeholder="parent@example.com"
                />
                <small class="input-hint">
                  For password reset and notifications
                </small>
              </div>

              <div class="form-group">
                <label for="phoneNumber">Phone Number (optional):</label>
                <input
                  id="phoneNumber"
                  v-model="form.phoneNumber"
                  type="tel"
                  :disabled="authStore.state.loading"
                  placeholder="(555) 123-4567"
                />
                <small class="input-hint">For SMS notifications (future)</small>
              </div>
            </div>
          </div>
        </div>

        <div v-if="authStore.state.error" class="error-message">
          {{ authStore.state.error }}
        </div>

        <div class="form-actions">
          <button
            type="submit"
            :disabled="authStore.state.loading || (showInviteSignup && !usernameStatus.available)"
            class="submit-btn"
          >
            {{
              authStore.state.loading
                ? 'Processing...'
                : isSignup
                  ? 'Sign Up'
                  : 'Login'
            }}
          </button>
        </div>
      </form>

      <div class="form-footer">
        <p v-if="!showInviteSignup">
          Have an invite code?
          <button @click="showInviteForm" class="link-btn">
            Click here to Sign Up
          </button>
        </p>
        <p v-if="showInviteSignup">
          Already have an account?
          <button @click="showLoginForm" class="link-btn">Login</button>
        </p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';

export default {
  name: 'LoginForm',
  emits: ['login-success'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const isSignup = ref(false);
    const showInviteSignup = ref(false);
    const showOptionalFields = ref(false);
    const inviteInfo = ref(null);
    const usernameStatus = ref({
      checked: false,
      available: false,
      suggestions: [],
    });

    const form = reactive({
      username: '',
      password: '',
      displayName: '',
      email: '',
      phoneNumber: '',
      inviteCode: '',
    });

    const showInviteForm = () => {
      showInviteSignup.value = true;
      isSignup.value = true;
      authStore.clearError();
      usernameStatus.value = { checked: false, available: false, suggestions: [] };
    };

    const showLoginForm = () => {
      showInviteSignup.value = false;
      isSignup.value = false;
      authStore.clearError();
      showOptionalFields.value = false;
      usernameStatus.value = { checked: false, available: false, suggestions: [] };
    };

    const checkUsername = async () => {
      if (!form.username || form.username.length < 3 || !showInviteSignup.value) {
        usernameStatus.value = { checked: false, available: false, suggestions: [] };
        return;
      }

      try {
        const result = await authStore.checkUsernameAvailable(form.username);
        usernameStatus.value = {
          checked: true,
          available: result.available,
          suggestions: result.suggestions || [],
        };
      } catch (error) {
        console.error('Error checking username:', error);
      }
    };

    const validateInviteCode = async () => {
      if (!form.inviteCode || form.inviteCode.length < 8) {
        inviteInfo.value = null;
        return;
      }

      try {
        const response = await fetch(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/invites/validate/${form.inviteCode}`
        );

        if (response.ok) {
          const data = await response.json();
          inviteInfo.value = data;
        } else {
          inviteInfo.value = null;
          authStore.setError('Invalid or expired invite code');
        }
      } catch (error) {
        console.error('Error validating invite:', error);
        inviteInfo.value = null;
      }
    };

    const handleSubmit = async () => {
      authStore.clearError();

      if (isSignup.value && showInviteSignup.value) {
        // Signup with invite
        const result = await authStore.signupWithInvite(
          form.username,
          form.password,
          form.displayName,
          form.inviteCode,
          form.email || null
        );
        if (result.success) {
          // Auto-login after signup
          const loginResult = await authStore.login(form.username, form.password);
          if (loginResult.success) {
            emit('login-success');
          }
        }
      } else {
        // Regular login
        const result = await authStore.login(form.username, form.password);
        if (result.success) {
          emit('login-success');
        }
      }
    };

    return {
      authStore,
      isSignup,
      showInviteSignup,
      showOptionalFields,
      form,
      inviteInfo,
      usernameStatus,
      showInviteForm,
      showLoginForm,
      checkUsername,
      validateInviteCode,
      handleSubmit,
    };
  },
};
</script>

<style scoped>
/* Existing styles + additions */

.input-hint {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.85rem;
  color: #666;
}

.username-status {
  margin-top: 0.5rem;
  font-size: 0.9rem;
}

.status-available {
  color: #28a745;
  font-weight: 600;
}

.status-taken {
  color: #dc3545;
  font-weight: 600;
}

.suggestion-btn {
  background: none;
  border: 1px solid #007bff;
  color: #007bff;
  padding: 0.25rem 0.5rem;
  margin-left: 0.5rem;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.85rem;
}

.suggestion-btn:hover {
  background-color: #007bff;
  color: white;
}

.optional-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #eee;
}

.toggle-optional {
  background: none;
  border: none;
  color: #007bff;
  cursor: pointer;
  font-size: 0.95rem;
  padding: 0.5rem 0;
  width: 100%;
  text-align: left;
}

.toggle-optional:hover {
  text-decoration: underline;
}

.toggle-optional small {
  color: #666;
  margin-left: 0.5rem;
}

.optional-fields {
  margin-top: 1rem;
  padding-left: 1rem;
}

/* ... rest of existing styles ... */
</style>
```

### Step 3.3: Update Profile Display Components

Update all components that display email to show username instead:

**Files to update:**
- `frontend/src/components/AuthNav.vue`
- `frontend/src/components/profiles/TeamManagerProfile.vue`
- `frontend/src/components/profiles/PlayerProfile.vue`
- `frontend/src/components/profiles/FanProfile.vue`
- `frontend/src/components/AdminPanel.vue`

**Example change** (`AuthNav.vue`):
```vue
<!-- Before -->
<span>{{ authStore.state.user?.email }}</span>

<!-- After -->
<span>{{ authStore.state.profile?.username }}</span>
```

**✅ Phase 3 Complete Checklist:**
- [ ] Auth store updated
- [ ] LoginForm component updated
- [ ] Username availability check working
- [ ] Optional fields (email/phone) working
- [ ] All profile components updated
- [ ] Frontend compiles without errors
- [ ] Login flow works end-to-end locally

---

## Phase 4: Testing & Migration

**Estimated Time**: 2-3 days
**Risk Level**: Medium

### Step 4.1: Create Data Migration Script

**File**: `backend/scripts/migrate_email_to_username.py`

```python
"""
Migrate existing email-based users to username-based authentication.

This script:
1. Generates usernames from existing emails
2. Updates user_profiles table
3. Handles username collisions
4. Logs all changes
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def generate_username_from_email(email: str) -> str:
    """Generate username from email address."""
    # Remove @domain
    username = email.split('@')[0]

    # Replace special chars with underscores
    username = ''.join(c if c.isalnum() or c == '_' else '_' for c in username)

    # Ensure valid length
    username = username[:50]

    return username.lower()


def migrate_users():
    """Migrate existing users to username authentication."""
    client = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_SERVICE_ROLE_KEY')  # Need service role for auth.users
    )

    print("🔄 Starting user migration to username authentication...")

    # Get all users from auth.users
    auth_users = client.auth.admin.list_users()

    migration_log = []
    errors = []

    for user in auth_users:
        email = user.email
        user_id = user.id

        try:
            # Check if user already has username
            profile = client.table('user_profiles')\
                .select('username')\
                .eq('id', user_id)\
                .execute()

            if profile.data and profile.data[0].get('username'):
                print(f"✓ User {email} already has username: {profile.data[0]['username']}")
                continue

            # Generate username
            base_username = generate_username_from_email(email)
            username = base_username
            counter = 1

            # Handle collisions
            while True:
                existing = client.table('user_profiles')\
                    .select('id')\
                    .eq('username', username)\
                    .execute()

                if not existing.data:
                    break

                username = f"{base_username}_{counter}"
                counter += 1

            # Update user_profiles
            client.table('user_profiles')\
                .update({'username': username})\
                .eq('id', user_id)\
                .execute()

            migration_log.append({
                'user_id': user_id,
                'email': email,
                'username': username,
                'migrated_at': datetime.now().isoformat()
            })

            print(f"✓ Migrated {email} -> {username}")

        except Exception as e:
            error_msg = f"✗ Failed to migrate {email}: {str(e)}"
            print(error_msg)
            errors.append({
                'email': email,
                'error': str(e)
            })

    # Save migration log
    log_file = f"migration_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    import json
    with open(log_file, 'w') as f:
        json.dump({
            'migrated': migration_log,
            'errors': errors,
            'total_migrated': len(migration_log),
            'total_errors': len(errors)
        }, f, indent=2)

    print(f"\n✅ Migration complete!")
    print(f"   Successfully migrated: {len(migration_log)} users")
    print(f"   Errors: {len(errors)}")
    print(f"   Log saved to: {log_file}")

    if errors:
        print("\n⚠️  Some users failed to migrate. Check the log file for details.")
        sys.exit(1)


if __name__ == "__main__":
    migrate_users()
```

### Step 4.2: Create Test Script

**File**: `backend/tests/test_username_auth.py`

```python
"""
Test username authentication functionality.
"""

import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_signup_with_username():
    """Test user signup with username."""
    response = client.post('/api/auth/signup', json={
        'username': 'test_player_99',
        'password': 'testpassword123',
        'display_name': 'Test Player'
    })

    assert response.status_code == 200
    data = response.json()
    assert 'user_id' in data
    assert data['username'] == 'test_player_99'


def test_signup_username_taken():
    """Test signup with duplicate username."""
    # First signup
    client.post('/api/auth/signup', json={
        'username': 'duplicate_user',
        'password': 'password123'
    })

    # Second signup with same username
    response = client.post('/api/auth/signup', json={
        'username': 'duplicate_user',
        'password': 'password456'
    })

    assert response.status_code == 400
    assert 'already taken' in response.json()['detail'].lower()


def test_login_with_username():
    """Test user login with username."""
    # First create user
    client.post('/api/auth/signup', json={
        'username': 'login_test_user',
        'password': 'testpassword123'
    })

    # Then login
    response = client.post('/api/auth/login', json={
        'username': 'login_test_user',
        'password': 'testpassword123'
    })

    assert response.status_code == 200
    data = response.json()
    assert 'access_token' in data
    assert data['user']['username'] == 'login_test_user'


def test_login_invalid_username():
    """Test login with non-existent username."""
    response = client.post('/api/auth/login', json={
        'username': 'nonexistent_user',
        'password': 'anypassword'
    })

    assert response.status_code == 401


def test_username_validation():
    """Test username format validation."""
    # Too short
    response = client.post('/api/auth/signup', json={
        'username': 'ab',
        'password': 'password123'
    })
    assert response.status_code == 400

    # Invalid characters
    response = client.post('/api/auth/signup', json={
        'username': 'user@name',
        'password': 'password123'
    })
    assert response.status_code == 400

    # Valid username
    response = client.post('/api/auth/signup', json={
        'username': 'valid_user_123',
        'password': 'password123'
    })
    assert response.status_code == 200


def test_username_availability_check():
    """Test username availability endpoint."""
    # Create a user
    client.post('/api/auth/signup', json={
        'username': 'taken_username',
        'password': 'password123'
    })

    # Check taken username
    response = client.get('/api/auth/username-available/taken_username')
    assert response.status_code == 200
    assert response.json()['available'] == False

    # Check available username
    response = client.get('/api/auth/username-available/available_username')
    assert response.status_code == 200
    assert response.json()['available'] == True


def test_signup_with_optional_email():
    """Test signup with optional email provided."""
    response = client.post('/api/auth/signup', json={
        'username': 'user_with_email',
        'password': 'password123',
        'email': 'parent@example.com'
    })

    assert response.status_code == 200

    # Login and verify email is stored
    login_response = client.post('/api/auth/login', json={
        'username': 'user_with_email',
        'password': 'password123'
    })

    assert login_response.json()['user']['email'] == 'parent@example.com'
```

### Step 4.3: Run Tests

```bash
# Backend tests
cd backend
uv run pytest tests/test_username_auth.py -v

# Frontend tests (if applicable)
cd frontend
npm run test:unit

# E2E tests
npm run test:e2e
```

### Step 4.4: Manual Testing Checklist

**Local Testing:**
- [ ] Start local environment: `./missing-table.sh dev`
- [ ] Test new user signup with username only
- [ ] Test new user signup with username + email
- [ ] Test username availability check (real-time)
- [ ] Test username suggestions when taken
- [ ] Test login with username
- [ ] Test invalid username formats rejected
- [ ] Test duplicate username rejected
- [ ] Verify JWT token contains username
- [ ] Verify profile displays username instead of email
- [ ] Test invite code signup with username
- [ ] Test all user roles (admin, team-manager, player, fan)

**Migration Testing:**
```bash
# Backup database first
./scripts/db_tools.sh backup

# Run migration script
cd backend
uv run python scripts/migrate_email_to_username.py

# Verify migrated users can login with new usernames
# Test both old email logins (should fail) and new username logins

# If issues, rollback
./scripts/db_tools.sh restore
```

**✅ Phase 4 Complete Checklist:**
- [ ] Migration script created and tested
- [ ] All automated tests passing
- [ ] Manual testing completed
- [ ] Migration tested on dev environment
- [ ] No regressions in existing functionality
- [ ] Documentation updated

---

## Phase 5: Deployment

**Estimated Time**: 1 day
**Risk Level**: High

### Step 5.1: Deploy to Dev Environment

```bash
# 1. Apply database migration
kubectl exec -it deployment/missing-table-backend -n missing-table-dev -- \
  psql $DATABASE_URL -f /app/supabase/migrations/20241009000017_add_username_auth.sql

# Or use Supabase dashboard to run migration

# 2. Build and deploy backend
./build-and-push.sh backend dev
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
kubectl rollout status deployment/missing-table-backend -n missing-table-dev

# 3. Build and deploy frontend
./build-and-push.sh frontend dev
kubectl rollout restart deployment/missing-table-frontend -n missing-table-dev
kubectl rollout status deployment/missing-table-frontend -n missing-table-dev

# 4. Run migration script
kubectl exec -it deployment/missing-table-backend -n missing-table-dev -- \
  python scripts/migrate_email_to_username.py

# 5. Verify deployment
curl https://dev.missingtable.com/api/auth/username-available/test_user
```

### Step 5.2: Test in Dev Environment

- [ ] Visit https://dev.missingtable.com
- [ ] Test signup with username
- [ ] Test login with username
- [ ] Test existing migrated users can login
- [ ] Check backend logs for errors
- [ ] Verify no Supabase Auth errors

### Step 5.3: Monitor and Validate

```bash
# Watch backend logs
kubectl logs -f deployment/missing-table-backend -n missing-table-dev

# Check for auth errors
kubectl logs deployment/missing-table-backend -n missing-table-dev | grep -i "auth\|username\|signup\|login"

# Verify database
kubectl exec -it deployment/missing-table-backend -n missing-table-dev -- \
  psql $DATABASE_URL -c "SELECT username, email, role FROM user_profiles LIMIT 10;"
```

### Step 5.4: Deploy to Production (After Dev Validation)

```bash
# Same steps as dev, but with prod namespace
./build-and-push.sh backend prod
./build-and-push.sh frontend prod

kubectl rollout restart deployment/missing-table-backend -n missing-table-prod
kubectl rollout restart deployment/missing-table-frontend -n missing-table-prod

# Run migration
kubectl exec -it deployment/missing-table-backend -n missing-table-prod -- \
  python scripts/migrate_email_to_username.py
```

**✅ Phase 5 Complete Checklist:**
- [ ] Deployed to dev environment
- [ ] Dev testing completed successfully
- [ ] Migration script run successfully
- [ ] No errors in production logs
- [ ] All users can authenticate
- [ ] Deployed to production
- [ ] Production validation completed

---

## Rollback Plan

If issues arise, follow this rollback procedure:

### Database Rollback
```bash
# Apply rollback migration
kubectl exec -it deployment/missing-table-backend -n missing-table-dev -- \
  psql $DATABASE_URL -f /app/supabase/migrations/20241009000017_add_username_auth_rollback.sql
```

### Code Rollback
```bash
# Checkout previous commit
git checkout main

# Redeploy previous version
./build-and-push.sh backend dev
./build-and-push.sh frontend dev

kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
kubectl rollout restart deployment/missing-table-frontend -n missing-table-dev
```

### Data Restore
```bash
# Restore from backup
./scripts/db_tools.sh restore backup_before_username_migration.json
```

---

## Success Criteria

✅ **Implementation is successful when:**

1. **New users can sign up with usernames** (no email required)
2. **Users can login with username + password**
3. **Username availability check works in real-time**
4. **Optional email/phone collection works**
5. **All existing users have been migrated to usernames**
6. **No Supabase Auth errors in logs**
7. **JWT tokens contain username data**
8. **All profile pages display usernames**
9. **Invite code flow works with usernames**
10. **No regressions in existing functionality**

---

## Future Enhancements (Post-Implementation)

### Phase 6: SMS Notifications (Future)
- [ ] Add SMS provider integration (Twilio, AWS SNS)
- [ ] Send invite codes via SMS
- [ ] Password reset via SMS verification
- [ ] Game reminders via SMS
- [ ] Team update notifications

### Phase 7: Username Management (Future)
- [ ] Allow users to change usernames
- [ ] Username history/audit log
- [ ] "Forgot username" lookup by team roster
- [ ] Display username prominently in profile

### Phase 8: Enhanced UX (Future)
- [ ] Smart username suggestions (team + position + number)
- [ ] Username reservation during invite flow
- [ ] Bulk username generation for team rosters
- [ ] QR code logins for youth players

---

## Troubleshooting

### Common Issues

**Issue**: "user_profiles table not found"
```sql
-- Create user_profiles table if missing
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username VARCHAR(50) UNIQUE,
    email VARCHAR(255),
    phone_number VARCHAR(20),
    display_name VARCHAR(100),
    role VARCHAR(50) DEFAULT 'team-fan',
    team_id INTEGER REFERENCES teams(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

**Issue**: "Username already taken" during migration
- Script automatically handles collisions by appending numbers
- Check migration log for conflicts

**Issue**: Supabase Auth rejects internal emails
- Verify email format: `username@missingtable.local`
- Check Supabase Auth settings allow this domain

**Issue**: Users can't login after migration
- Verify username was properly set in user_profiles
- Check that internal email matches: `SELECT * FROM auth.users WHERE email LIKE '%@missingtable.local'`

---

## Documentation Updates

After implementation, update these docs:
- [ ] README.md - Update authentication section
- [ ] docs/03-architecture/README.md - Update auth architecture
- [ ] docs/01-getting-started/local-development.md - Update signup instructions
- [ ] API documentation - Update /api/auth endpoints
- [ ] User guide - Create username authentication guide

---

## Contacts & Support

**Implementation Lead**: Claude
**Feature Branch**: `feature/username-auth-refactor`
**Tracking Issue**: TBD
**Slack Channel**: TBD

---

**Last Updated**: 2025-10-09
**Status**: Ready to implement
**Next Steps**: Begin Phase 1 - Database Schema Changes

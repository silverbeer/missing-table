# Username-Based Authentication Refactor Proposal

## Overview

Proposal to replace email-based login with username-based authentication for youth soccer players (e.g., `gabe_ifa_35`).

## Current Architecture

### Authentication Stack
- **Backend**: FastAPI with Supabase Auth
- **Database**: PostgreSQL via Supabase
- **Auth System**: Supabase Auth (email + password)
- **User Storage**: `auth.users` (Supabase managed) + `public.user_profiles` (application table)
- **JWT Tokens**: Supabase-generated with SUPABASE_JWT_SECRET

### Current Flow
1. User signs up with email + password
2. Supabase Auth creates user in `auth.users` table
3. Backend creates profile in `user_profiles` table (id, role, team_id, display_name)
4. Login uses email + password via Supabase Auth
5. JWT token contains user ID and email

### Files Involved
- **Backend**:
  - `backend/app.py` - Lines 272-419 (signup/login endpoints)
  - `backend/auth.py` - JWT verification, role checking
  - `backend/auth_security.py` - Security monitoring

- **Frontend**:
  - `frontend/src/components/LoginForm.vue` - Email/password form
  - `frontend/src/stores/auth.js` - Auth state management
  - Multiple profile components reference email

## Proposed Changes

### 🎯 Goal
Replace email as the primary login credential with a username (e.g., `gabe_ifa_35`).

## Implementation Options

### Option 1: Hybrid Approach (RECOMMENDED) ⭐
**Complexity**: Medium | **Time**: 1-2 weeks | **Risk**: Low

Keep Supabase Auth but use usernames as "fake emails" internally.

#### Architecture
```
User enters username: gabe_ifa_35
    ↓
Backend converts to: gabe_ifa_35@missingtable.local
    ↓
Supabase Auth validates: (internal email format)
    ↓
JWT token still contains user_id
```

#### Changes Required

**Database**:
```sql
-- Add username column to user_profiles
ALTER TABLE user_profiles
  ADD COLUMN username VARCHAR(50) UNIQUE NOT NULL;

-- Create index for fast lookups
CREATE UNIQUE INDEX idx_user_profiles_username ON user_profiles(username);

-- Optional: email becomes nullable for username-only accounts
ALTER TABLE user_profiles
  ALTER COLUMN email DROP NOT NULL;
```

**Backend** (`backend/app.py`):
- Modify `UserSignup` model:
  ```python
  class UserSignup(BaseModel):
      username: str  # New primary field
      email: str | None = None  # Optional
      password: str
      display_name: str | None = None
      invite_code: str | None = None
  ```

- Update signup endpoint (line 274):
  ```python
  async def signup(request: Request, user_data: UserSignup):
      # Convert username to internal email format
      internal_email = f"{user_data.username}@missingtable.local"

      # Validate username format (letters, numbers, underscores only)
      if not re.match(r'^[a-zA-Z0-9_]{3,50}$', user_data.username):
          raise HTTPException(400, "Invalid username format")

      # Check username uniqueness
      existing = db_conn_holder_obj.client.table('user_profiles')\\
          .select('id')\\
          .eq('username', user_data.username)\\
          .execute()

      if existing.data:
          raise HTTPException(400, "Username already taken")

      # Create Supabase auth user with internal email
      response = db_conn_holder_obj.client.auth.sign_up({
          "email": internal_email,
          "password": user_data.password,
          "options": {
              "data": {
                  "username": user_data.username,
                  "display_name": user_data.display_name or user_data.username
              }
          }
      })

      # Create user_profiles entry with username and optional real email
      db_conn_holder_obj.client.table('user_profiles')\\
          .insert({
              'id': response.user.id,
              'username': user_data.username,
              'email': user_data.email,  # Can be None
              'display_name': user_data.display_name or user_data.username
          })\\
          .execute()
  ```

- Update login endpoint (line 383):
  ```python
  class UserLogin(BaseModel):
      username: str  # Changed from email
      password: str

  async def login(request: Request, user_data: UserLogin):
      # Convert username to internal email
      internal_email = f"{user_data.username}@missingtable.local"

      # Authenticate with Supabase
      response = db_conn_holder_obj.client.auth.sign_in_with_password({
          "email": internal_email,
          "password": user_data.password
      })
  ```

**Frontend** (`frontend/src/components/LoginForm.vue`):
- Change form fields:
  ```vue
  <div class="form-group">
    <label for="username">Username:</label>
    <input
      id="username"
      v-model="form.username"
      type="text"
      required
      placeholder="e.g., gabe_ifa_35"
      pattern="[a-zA-Z0-9_]{3,50}"
    />
  </div>
  ```

- Update validation and submit logic

**Frontend Store** (`frontend/src/stores/auth.js`):
- Update signup/login methods to use username instead of email
- Modify profile state to include username

#### Pros
- ✅ Minimal disruption to existing Supabase Auth infrastructure
- ✅ Password reset can still work (if we capture real email)
- ✅ JWT token structure unchanged
- ✅ Can add real email capture later for parent notifications
- ✅ Backwards compatible with email-based accounts

#### Cons
- ⚠️ "Fake" internal emails feel hacky
- ⚠️ Password reset needs special handling
- ⚠️ Supabase dashboard shows internal emails

---

### Option 2: Custom Authentication
**Complexity**: High | **Time**: 3-4 weeks | **Risk**: High

Complete replacement of Supabase Auth with custom username/password system.

#### Architecture
```
User enters username + password
    ↓
Backend validates against user_profiles table
    ↓
Backend generates custom JWT token
    ↓
All auth logic handled by application
```

#### Changes Required
- Remove all Supabase Auth dependencies
- Implement password hashing (bcrypt/argon2)
- Custom JWT token generation/validation
- Session management
- Password reset flow (email or security questions)
- Account lockout after failed attempts
- Email verification (if collecting emails)
- 2FA support (future)

#### Pros
- ✅ Complete control over authentication
- ✅ Clean username-based system
- ✅ No workarounds needed
- ✅ Can optimize for youth users

#### Cons
- ❌ High security responsibility
- ❌ Must implement all auth features from scratch
- ❌ Password reset requires email system
- ❌ Longer development time
- ❌ More testing required
- ❌ Lose Supabase Auth benefits (email verification, rate limiting, etc.)

---

### Option 3: Supabase + Username Lookup Table
**Complexity**: Low | **Time**: 1 week | **Risk**: Very Low

Keep email auth but add username as alias with lookup table.

#### Architecture
```
User enters username: gabe_ifa_35
    ↓
Lookup table: username → email
    ↓
Supabase Auth validates email
```

#### Changes Required
- Add username column to user_profiles
- Backend login endpoint does username → email lookup before Supabase auth
- Frontend still sends username, backend translates

#### Pros
- ✅ Minimal changes to auth system
- ✅ Preserves all Supabase Auth benefits
- ✅ Very low risk

#### Cons
- ❌ Still requires real email addresses
- ❌ Doesn't solve the core problem (kids don't have emails)
- ❌ Parents must manage email accounts

---

## Complexity Analysis

### Database Changes: **Low-Medium**
- Add `username` column: 1 migration
- Update unique constraints
- Add indexes
- Estimated effort: 2-4 hours

### Backend Changes: **Medium-High**
- Modify 2 Pydantic models
- Update 2 main endpoints (signup/login)
- Update auth.py for username handling
- Add username validation
- Update security monitoring
- Estimated effort: 2-3 days

### Frontend Changes: **Medium**
- Update LoginForm.vue (1 component)
- Update auth store (1 file)
- Update all display references from email to username
- Estimated effort: 1-2 days

### Testing Required: **High**
- Unit tests for username validation
- Integration tests for signup/login flows
- E2E tests for auth workflows
- Security testing for username enumeration
- Password reset flow testing
- Estimated effort: 2-3 days

### Migration Strategy: **High Risk**
- Existing users have emails, not usernames
- Need migration script to:
  1. Generate default usernames from emails
  2. Allow users to customize usernames
  3. Handle collisions
- Estimated effort: 1-2 days

## Risk Assessment

### Security Risks
- **Username Enumeration**: Attackers can test if usernames exist
  - Mitigation: Same error message for "username not found" vs "wrong password"

- **Brute Force**: Easier to guess common usernames (gabe_ifa_35)
  - Mitigation: Rate limiting, account lockout, CAPTCHA

- **Password Reset**: Without email, how do users recover accounts?
  - Mitigation: Capture optional parent email, or manual admin reset

### UX Risks
- **Username Conflicts**: Popular names will be taken (gabe_ifa)
  - Mitigation: Suggest alternatives during signup

- **Forgotten Usernames**: Kids might forget their username
  - Mitigation: Display username on profile, allow lookup by team roster

## Recommended Approach

### 🎯 **Option 1: Hybrid Approach (Recommended)**

**Rationale**:
1. **Balances complexity with functionality** - Reuses Supabase Auth infrastructure
2. **Low risk** - Minimal changes to security-critical code
3. **Future-proof** - Can capture real emails for parent notifications
4. **Fast implementation** - 1-2 weeks vs 3-4 weeks for custom auth
5. **Incremental migration** - Can support both email and username logins during transition

### Implementation Phases

**Phase 1: Database & Backend (Week 1)**
- Add username column to user_profiles
- Update signup endpoint
- Update login endpoint
- Add username validation
- Update JWT payload

**Phase 2: Frontend (Week 1-2)**
- Update LoginForm component
- Update auth store
- Update all email references to username
- Add username suggestions during signup

**Phase 3: Migration & Testing (Week 2)**
- Create migration script for existing users
- Comprehensive testing
- Security review
- Deploy to dev environment

**Phase 4: Optional Enhancements (Future)**
- Capture optional parent email
- Email notifications for important events
- Username change functionality
- "Forgot username" lookup

## Alternative: Minimal MVP

If faster implementation is needed, consider **Option 3** as a temporary solution:
- Takes 1 week instead of 2
- Requires parents to create email accounts initially
- Can be upgraded to Option 1 later without breaking changes

## Questions to Answer

1. **Password Reset**: How should users recover accounts without email?
   - Admin manual reset?
   - Security questions?
   - Optional parent email?

2. **Migration**: Should existing email users be migrated?
   - Auto-generate usernames?
   - Force username selection on next login?
   - Support both login methods?

3. **Notifications**: How to notify parents about team updates?
   - Capture optional email during signup?
   - SMS notifications?
   - In-app only?

4. **Username Format**: What rules should apply?
   - Length: 3-50 characters?
   - Allowed characters: letters, numbers, underscores?
   - Suggestions: team name, position, number?

## Estimated Total Effort

- **Option 1 (Hybrid)**: 1-2 weeks (40-80 hours)
- **Option 2 (Custom)**: 3-4 weeks (120-160 hours)
- **Option 3 (Lookup)**: 1 week (40 hours)

## Recommendation Summary

✅ **Go with Option 1 (Hybrid Approach)**
- Reasonable 1-2 week timeline
- Low security risk
- Preserves Supabase Auth benefits
- Can iterate with additional features
- Good balance of complexity vs functionality

Start with username-only signup, optionally capture parent email for notifications, and implement account recovery through admin support initially.

---

**Last Updated**: 2025-10-09
**Status**: Proposal/Planning Phase

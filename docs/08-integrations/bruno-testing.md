# Bruno API Testing Guide

Quick reference for testing the Missing Table API with Bruno.

## Base URL

**Dev Environment:** `https://dev.missingtable.com`

---

## Public Endpoints (No Auth Required)

These endpoints don't require authentication:

### Get Seasons

```
GET https://dev.missingtable.com/api/seasons
```

**Headers:** None required

**Response:**
```json
[
  {
    "id": 1,
    "name": "2024-2025",
    "start_date": "2024-09-01",
    "end_date": "2025-06-30"
  }
]
```

### Get Teams

```
GET https://dev.missingtable.com/api/teams
```

**Headers:** None required

### Health Check

```
GET https://dev.missingtable.com/health
```

**Headers:** None required

---

## User Authentication Endpoints

### 1. Login (Get Token)

```
POST https://dev.missingtable.com/api/auth/login
```

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "email": "your-email@example.com",
  "password": "your-password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid-here",
    "email": "your-email@example.com",
    "role": "admin"
  }
}
```

**💡 Save the `access_token` - you'll need it for authenticated requests!**

### 2. Get User Profile (Authenticated)

```
GET https://dev.missingtable.com/api/auth/me
```

**Headers:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response:**
```json
{
  "user_id": "uuid-here",
  "email": "your-email@example.com",
  "role": "admin",
  "display_name": "Your Name"
}
```

---

## Service Account Authentication (for match-scraper)

### 1. Generate Service Account Token

First, generate a token (one-time setup):

```bash
cd backend
uv run python create_service_account_token.py \
  --service-name match-scraper \
  --permissions manage_games
```

**Output:**
```
Service Account Token created successfully!

Service Name: match-scraper
Permissions: manage_games
Expires: 2026-10-04

Token:
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzZXJ2aWNlLW1hdGNoLXNjcmFwZXIiLCJpc3MiOiJtaXNzaW5nLXRhYmxlIiwiYXVkIjoic2VydmljZS1hY2NvdW50IiwiZXhwIjoxNzU5NTg3MDAwLCJpYXQiOjE3Mjc5NjQwMDAsInNlcnZpY2VfbmFtZSI6Im1hdGNoLXNjcmFwZXIiLCJwZXJtaXNzaW9ucyI6WyJtYW5hZ2VfZ2FtZXMiXSwicm9sZSI6InNlcnZpY2VfYWNjb3VudCJ9.abc123...

Save this token securely - it won't be shown again!
```

**💾 Save this token - you'll use it in Bruno!**

### 2. Submit Match Data (Service Account)

```
POST https://dev.missingtable.com/api/matches
```

**Headers:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...(service account token)
Content-Type: application/json
```

**Body:**
```json
{
  "home_team_id": 1,
  "away_team_id": 2,
  "home_score": 3,
  "away_score": 1,
  "date": "2025-10-05",
  "season_id": 2,
  "match_type": "league",
  "match_id": "external-id-123"
}
```

---

## Bruno Collection Setup

### Environment Variables (Recommended)

Create a Bruno environment for dev:

**File:** `environments/dev.bru`

```
vars {
  base_url: https://dev.missingtable.com
  token: {{token}}
  service_token: {{service_token}}
}
```

**How to use:**
1. In Bruno, go to Environments → New Environment
2. Name it "Dev"
3. Add variables:
   - `base_url`: `https://dev.missingtable.com`
   - `token`: (leave empty, will be set after login)
   - `service_token`: (paste your service account token)

### Example Requests

#### Public Request (No Auth)

**File:** `Get Seasons.bru`

```
meta {
  name: Get Seasons
  type: http
  seq: 1
}

get {
  url: {{base_url}}/api/seasons
}
```

#### User Login

**File:** `Login.bru`

```
meta {
  name: Login
  type: http
  seq: 2
}

post {
  url: {{base_url}}/api/auth/login
  body: json
  auth: none
}

body:json {
  {
    "email": "your-email@example.com",
    "password": "your-password"
  }
}

script:post-response {
  if (res.body.access_token) {
    bru.setEnvVar("token", res.body.access_token);
  }
}
```

**💡 The post-response script automatically saves the token!**

#### Authenticated Request (User)

**File:** `Get Profile.bru`

```
meta {
  name: Get Profile
  type: http
  seq: 3
}

get {
  url: {{base_url}}/api/auth/me
}

headers {
  Authorization: Bearer {{token}}
}
```

#### Service Account Request

**File:** `Create Match (Service).bru`

```
meta {
  name: Create Match (Service Account)
  type: http
  seq: 4
}

post {
  url: {{base_url}}/api/matches
  body: json
}

headers {
  Authorization: Bearer {{service_token}}
  Content-Type: application/json
}

body:json {
  {
    "home_team_id": 1,
    "away_team_id": 2,
    "home_score": 3,
    "away_score": 1,
    "date": "2025-10-05",
    "season_id": 2,
    "match_type": "league",
    "match_id": "match-scraper-test-001"
  }
}
```

---

## Quick Reference

### Authentication Header Format

**User Token:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Service Account Token:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

(Same format, different tokens)

### Common Headers

**For JSON requests:**
```
Content-Type: application/json
Authorization: Bearer <token>
```

**For public endpoints:**
```
(no headers needed)
```

---

## Testing Workflow

### 1. Test Public Endpoints

Start with public endpoints to verify connectivity:
- ✅ `GET /api/seasons`
- ✅ `GET /api/teams`
- ✅ `GET /health`

### 2. Test User Authentication

1. **Login:** `POST /api/auth/login` → Save token
2. **Get Profile:** `GET /api/auth/me` with token
3. **Test CRUD:** Create/update/delete with token

### 3. Test Service Account

1. **Generate token:** Run `create_service_account_token.py`
2. **Save token:** Add to Bruno environment
3. **Submit data:** `POST /api/matches` with service token

---

## Troubleshooting

### 401 Unauthorized

**Problem:** `{"detail": "Not authenticated"}`

**Solutions:**
1. Check token is set: `Authorization: Bearer <token>`
2. Token might be expired - login again
3. Verify no extra spaces in header value
4. Check token is for correct environment

### 403 Forbidden

**Problem:** `{"detail": "Insufficient permissions"}`

**Solutions:**
1. User token: Check user role (admin/team_manager/user)
2. Service token: Check permissions include required scope
3. Endpoint requires specific role (e.g., admin only)

### Token Expired

**Problem:** `{"detail": "Token has expired"}`

**Solution:** Login again to get new token
- User tokens: Login via `/api/auth/login`
- Service tokens: Generate new token with script

### Invalid Token

**Problem:** `{"detail": "Invalid token"}`

**Solutions:**
1. Verify token format (should be JWT: `xxx.yyy.zzz`)
2. Check for copy/paste errors (no line breaks)
3. Regenerate token if corrupted

---

## Example: Complete Match-Scraper Test

### Step 1: Generate Service Token

```bash
cd backend
uv run python create_service_account_token.py \
  --service-name match-scraper \
  --permissions manage_matches
```

### Step 2: Save Token in Bruno

Environment → Dev → Add variable:
```
service_token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Step 3: Test Endpoints

**Get Teams (find IDs):**
```
GET {{base_url}}/api/teams
```

**Create Match:**
```
POST {{base_url}}/api/matches
Authorization: Bearer {{service_token}}

{
  "home_team_id": 123,
  "away_team_id": 456,
  "home_score": 2,
  "away_score": 1,
  "date": "2025-10-05",
  "season_id": 2,
  "match_type": "league",
  "match_id": "scraper-test-001"
}
```

**Verify Match Created:**
```
GET {{base_url}}/api/matches?season_id=2
```

---

## Related Documentation

- [Secret Management](./SECRET_MANAGEMENT.md)
- [Secret Runtime Loading](./SECRET_RUNTIME_LOADING.md)
- Backend `auth.py` - Authentication implementation

---

**Last Updated:** October 9, 2025

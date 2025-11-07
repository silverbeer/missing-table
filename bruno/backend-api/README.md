# Backend API Tests

Bruno API tests for the Missing Table backend.

## Setup

1. **Install Bruno** (if not already installed):
   ```bash
   brew install bruno
   # OR download from https://www.usebruno.com/downloads
   ```

2. **Open Collection**:
   - Open Bruno
   - Click "Open Collection"
   - Navigate to `bruno/backend-api/`
   - Select the folder

3. **Select Environment**:
   - In Bruno, select the "local" environment from the dropdown
   - This sets `api_url` to `http://localhost:8000`

## Running Tests

### Prerequisites
Ensure the backend is running:
```bash
./missing-table.sh start
```

### Test Execution Order

Tests are configured to run in a specific sequence using the `seq` field in each test file. This ensures **login always runs first** when you run the entire collection.

**Sequence Order:**
1. **Login** (seq: 1) - `auth/login.bru` - Gets JWT token, saves to environment
2. **Unauthenticated Tests** (seq: 10-19) - Health checks, docs
3. **Authenticated Tests** (seq: 20+) - All endpoints requiring JWT token

### Running Individual Tests

1. Click on a test in the sidebar
2. Click "Run" button or press `Cmd+Enter`
3. View response and test results in the right panel

**Note:** When running individual authenticated tests, make sure you've run `auth/login.bru` first to get a valid token.

### Running All Tests (Recommended)

**Bruno automatically runs login first** when you run the folder:

1. Right-click on "backend-api" folder
2. Select **"Run Folder"**
3. Tests execute in sequence order:
   - Login runs first (seq: 1) and saves token
   - All other tests use the saved `access_token`

**From Command Line:**
```bash
# Install Bruno CLI
npm install -g @usebruno/cli

# Run entire collection (login runs first automatically)
bru run bruno/backend-api --env local
```

## Test Structure

```
bruno/backend-api/
├── bruno.json              # Collection config
├── environments/
│   └── local.bru          # Local environment variables
├── auth/
│   └── login.bru          # Login and get JWT token
├── seasons/
│   └── get-seasons.bru    # Get all seasons (authenticated)
└── health.bru             # Health check (no auth)
```

## Environment Variables

The `local` environment provides:
- `api_url`: Backend API base URL (http://localhost:8000)
- `access_token`: JWT token (set automatically after login)

## Test Credentials

Default test user (from local environment):
- **Username**: `tom`
- **Password**: `admin123`
- **Role**: `admin`

## Writing New Tests

### Unauthenticated Endpoint

```bru
meta {
  name: My Test
  type: http
  seq: 1
}

get {
  url: {{api_url}}/api/endpoint
  body: none
  auth: none
}

assert {
  res.status: eq 200
}
```

### Authenticated Endpoint

```bru
meta {
  name: My Authenticated Test
  type: http
  seq: 2
}

get {
  url: {{api_url}}/api/endpoint
  body: none
  auth: bearer
}

auth:bearer {
  token: {{access_token}}
}

assert {
  res.status: eq 200
}
```

### With Request Body

```bru
post {
  url: {{api_url}}/api/endpoint
  body: json
  auth: bearer
}

auth:bearer {
  token: {{access_token}}
}

body:json {
  {
    "field": "value"
  }
}
```

## Tips

- **Always run `auth/login.bru` first** when starting a new test session
- **Token expires after 1 hour** - re-run login if you get 401 errors
- **Use "Run Folder"** to automatically run login before all other tests
- **Check assertions** in the "Tests" tab to see validation results
- **Use scripts** (`script:post-response`) to save response data to environment variables

### JWT Token Expiration

Access tokens expire after **1 hour (3600 seconds)**. After expiration:
- You'll receive `401 Unauthorized` errors
- Simply re-run `auth/login.bru` to get a fresh token
- The new token will be automatically saved to `access_token` environment variable

## Common Issues

### 401 Unauthorized
- Run the login test first to get a fresh token
- Check that `access_token` is set in environment variables

### Connection Refused
- Ensure backend is running: `./missing-table.sh status`
- Check backend URL in environment: `http://localhost:8000`

### Test Failures
- Check backend logs: `./missing-table.sh logs`
- Verify database has test data
- Ensure migrations are applied

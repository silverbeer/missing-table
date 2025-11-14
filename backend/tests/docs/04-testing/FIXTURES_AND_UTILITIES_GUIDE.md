# Test Fixtures & Utilities Guide

**Date**: 2025-11-11  
**Status**: ✅ Complete  
**Branch**: `tests-cleanup-refactor`

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Test Data Seeds](#test-data-seeds)
3. [Test Factories](#test-factories)
4. [Test Utilities](#test-utilities)
5. [Database Setup Scripts](#database-setup-scripts)
6. [Usage Examples](#usage-examples)
7. [Best Practices](#best-practices)

---

## Overview

The Missing Table test suite includes comprehensive fixtures, factories, and utilities to make tests:
- **Deterministic**: Reproducible with seeded Faker
- **Maintainable**: Centralized test data generation
- **Consistent**: Reusable assertions and clients
- **Isolated**: Per-layer database setup/teardown

---

## 📦 Test Data Seeds

### Location
```
backend/tests/fixtures/data/
├── reference_data.json   # Age groups, divisions, seasons, match types
├── teams.json            # Sample team data
└── users.json            # Test user accounts
```

### Loading Seed Data

```python
from tests.fixtures.factories import load_all_seed_data

# Load all seed data
seed_data = load_all_seed_data()
reference = seed_data["reference"]  # All reference data
teams = seed_data["teams"]          # Sample teams
users = seed_data["users"]          # Test users

# Access specific data
age_groups = reference["age_groups"]
divisions = reference["divisions"]
seasons = reference["seasons"]
```

### Seed Data Structure

**Reference Data** (`reference_data.json`):
- 6 age groups (U13 - U19)
- 4 divisions (Premier, Division 1-3)
- 2 seasons (2024-2025, 2023-2024)
- 4 match types (League, Cup, Friendly, Playoff)

**Teams** (`teams.json`):
- 4 sample teams with realistic data
- Different age groups and divisions
- Includes coach and contact info

**Users** (`users.json`):
- 3 test users (admin, team_manager, regular user)
- Consistent IDs for testing
- Predefined roles

---

## 🏭 Test Factories

### Location
```
backend/tests/fixtures/factories.py
```

### Available Factories

1. **ReferenceDataFactory**: Age groups, divisions, seasons, match types
2. **TeamFactory**: Team data generation
3. **MatchFactory**: Match data generation
4. **UserFactory**: User data generation
5. **AuthFactory**: Authentication data (tokens, credentials)
6. **StandingsFactory**: League table data

### Basic Usage

```python
from tests.fixtures.factories import TeamFactory, MatchFactory, UserFactory

# Create single entity
team = TeamFactory.create(name="Test FC", city="Boston, MA")

# Create multiple entities
teams = TeamFactory.create_batch(5)

# Build without persisting (for API payload testing)
team_data = TeamFactory.build(name="New Team")

# Load from seed file
seed_teams = TeamFactory.load_seeds()
```

### TeamFactory Examples

```python
from tests.fixtures.factories import TeamFactory

# Random team with defaults
team = TeamFactory.create()
# {
#     "id": 123,
#     "name": "Springfield Strikers",
#     "city": "Springfield, MA",
#     "age_group_id": 2,
#     "division_id": 1,
#     "season_id": 1,
#     "coach": "John Smith",
#     "contact_email": "coach@example.com"
# }

# Custom team
team = TeamFactory.create(
    name="Boston United",
    city="Boston, MA",
    age_group_id=3,
    division_id=1
)

# Multiple teams
teams = TeamFactory.create_batch(10, season_id=1)
```

### MatchFactory Examples

```python
from tests.fixtures.factories import MatchFactory

# Random match
match = MatchFactory.create()

# Upcoming match (no scores)
match = MatchFactory.upcoming(days=7, home_team_id=1, away_team_id=2)

# Completed match (with scores)
match = MatchFactory.completed(home_team_id=1, away_team_id=2)

# Multiple matches
matches = MatchFactory.create_batch(20)
```

### UserFactory Examples

```python
from tests.fixtures.factories import UserFactory

# Regular user
user = UserFactory.create()

# Admin user
admin = UserFactory.admin(email="admin@test.com")

# Team manager
manager = UserFactory.team_manager(email="manager@test.com")

# Load seed users
seed_users = UserFactory.load_seeds()
```

### AuthFactory Examples

```python
from tests.fixtures.factories import AuthFactory

# Generate credentials
creds = AuthFactory.credentials(email="user@test.com")
# {"email": "user@test.com", "password": "TestPassword123!"}

# Generate mock JWT token
token = AuthFactory.jwt_token()

# Generate auth headers
headers = AuthFactory.auth_headers(token="custom_token")
# {"Authorization": "Bearer custom_token"}
```

### StandingsFactory Examples

```python
from tests.fixtures.factories import StandingsFactory

# Single team stats
stats = StandingsFactory.team_stats(team="Boston FC", played=10, wins=7)

# Full league table
table = StandingsFactory.league_table(num_teams=8)
# Returns sorted list by points and goal difference
```

### Deterministic Testing

```python
from tests.fixtures.factories import reset_all_factories

# Reset seed for deterministic tests
reset_all_factories(seed=42)

# Now all factories will generate same data
team1 = TeamFactory.create()
team2 = TeamFactory.create()  # Different from team1 but predictable
```

---

## 🛠️ Test Utilities

### Assertions (`tests/utils/assertions.py`)

#### HTTP Response Assertions

```python
from tests.utils.assertions import assert_valid_response, assert_error_response

# Assert successful response
response = client.get("/api/teams")
assert_valid_response(response, status_code=200)

# Assert error response
response = client.get("/api/teams/9999")
assert_error_response(response, status_code=404, error_message="not found")
```

#### Data Structure Assertions

```python
from tests.utils.assertions import assert_has_keys, assert_is_list, assert_is_valid_id

# Assert required keys present
data = response.json()
assert_has_keys(data, ["id", "name", "city"])

# Assert list with length constraints
assert_is_list(data, min_length=1, max_length=100)

# Assert valid ID
assert_is_valid_id(team["id"])
```

#### Entity Validation Assertions

```python
from tests.utils.assertions import assert_valid_team, assert_valid_match, assert_valid_user

# Validate team structure
team = response.json()
assert_valid_team(team)  # Basic validation
assert_valid_team(team, strict=True)  # Require all fields

# Validate match structure
match = response.json()
assert_valid_match(match)

# Validate user structure
user = response.json()
assert_valid_user(user)
```

#### Authentication Assertions

```python
from tests.utils.assertions import assert_requires_auth, assert_forbidden, assert_unauthorized

# Assert endpoint requires authentication
response = client.get("/api/admin/users")
assert_requires_auth(response)  # 401 or 403

# Assert forbidden
assert_forbidden(response)  # 403

# Assert unauthorized
assert_unauthorized(response)  # 401
```

### Test Clients (`tests/fixtures/clients.py`)

#### Creating Test Clients

```python
from tests.fixtures.clients import (
    create_test_client,
    create_authenticated_client,
    create_admin_client,
    create_team_manager_client
)

# Basic client (no auth)
client = create_test_client()

# Disable security for testing
client = create_test_client(disable_security=True)

# Authenticated user client
client = create_authenticated_client(
    user_id="test-user-001",
    email="user@test.com",
    role="user"
)

# Admin client
admin_client = create_admin_client()

# Team manager client
manager_client = create_team_manager_client()
```

#### Managing Client Headers

```python
from tests.fixtures.clients import add_auth_headers, remove_auth_headers, create_client_with_headers

# Add auth headers to existing client
add_auth_headers(client, user_id="test-user", role="user")

# Remove auth headers
remove_auth_headers(client)

# Create client with custom headers
client = create_client_with_headers({
    "X-Custom-Header": "value",
    "User-Agent": "test-agent"
})
```

---

## 🗄️ Database Setup Scripts

### Script Location
```bash
scripts/test-db-setup.sh
```

### Usage

```bash
# Setup integration test database
./scripts/test-db-setup.sh integration

# Setup e2e test database (full data + users)
./scripts/test-db-setup.sh e2e

# Setup contract test database (minimal data)
./scripts/test-db-setup.sh contract

# Teardown (reset database)
./scripts/test-db-setup.sh teardown
```

### What Each Layer Sets Up

**Integration**:
- Reference data (age groups, divisions, seasons, match types)
- Sample teams (via db_tools.sh restore)

**E2E**:
- All integration data
- Test users (admin, manager, regular)
- Full match history
- Uses e2e-db-setup.sh + seed_test_users.sh

**Contract**:
- Minimal reference data only
- No users or test data

**Unit**:
- No database setup (tests should use mocks)

### In Test Files

```python
import pytest

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Setup test database before tests run."""
    import subprocess
    subprocess.run(["./scripts/test-db-setup.sh", "integration"], check=True)
    yield
    # Teardown happens automatically (persistent Supabase)
```

---

## 📚 Usage Examples

### Example 1: Integration Test with Factories

```python
from tests.fixtures.factories import TeamFactory, MatchFactory
from tests.utils.assertions import assert_valid_response, assert_valid_team

def test_create_team(test_client):
    """Test creating a team using factory."""
    # Build team data
    team_data = TeamFactory.build(
        name="Test United",
        city="Boston, MA",
        age_group_id=2
    )
    
    # Send request
    response = test_client.post("/api/teams", json=team_data)
    
    # Assert response
    assert_valid_response(response, status_code=201)
    
    # Validate created team
    team = response.json()
    assert_valid_team(team, strict=True)
    assert team["name"] == "Test United"
```

### Example 2: E2E Test with Multiple Factories

```python
from tests.fixtures.factories import TeamFactory, MatchFactory, UserFactory
from tests.fixtures.clients import create_authenticated_client
from tests.utils.assertions import assert_valid_match

def test_complete_match_workflow():
    """Test complete match creation and update workflow."""
    # Create client
    client = create_authenticated_client(role="admin")
    
    # Create teams
    home_team = TeamFactory.create(name="Home FC")
    away_team = TeamFactory.create(name="Away FC")
    
    # Create upcoming match
    match_data = MatchFactory.upcoming(
        home_team_id=home_team["id"],
        away_team_id=away_team["id"]
    )
    
    # Create match
    response = client.post("/api/matches", json=match_data)
    assert_valid_response(response, status_code=201)
    
    match = response.json()
    assert_valid_match(match)
    
    # Update with scores
    response = client.patch(
        f"/api/matches/{match['id']}",
        json={"home_score": 2, "away_score": 1}
    )
    assert_valid_response(response, status_code=200)
```

### Example 3: Contract Test with Seed Data

```python
from tests.fixtures.factories import load_all_seed_data
from tests.utils.assertions import assert_has_keys

def test_api_returns_reference_data(test_client):
    """Test that API returns all reference data."""
    # Load expected data
    seed_data = load_all_seed_data()
    expected_age_groups = seed_data["reference"]["age_groups"]
    
    # Get from API
    response = test_client.get("/api/age-groups")
    assert_valid_response(response)
    
    # Verify structure
    data = response.json()
    assert len(data) >= len(expected_age_groups)
    
    for age_group in data:
        assert_has_keys(age_group, ["id", "name", "description"])
```

### Example 4: Authentication Test

```python
from tests.fixtures.factories import UserFactory, AuthFactory
from tests.fixtures.clients import create_test_client, add_auth_headers
from tests.utils.assertions import assert_requires_auth, assert_valid_response

def test_protected_endpoint_requires_auth():
    """Test that protected endpoint requires authentication."""
    # Create client without auth
    client = create_test_client()
    
    # Try to access protected endpoint
    response = client.get("/api/protected")
    assert_requires_auth(response)
    
    # Add auth headers
    token = AuthFactory.jwt_token()
    add_auth_headers(client, token=token, role="user")
    
    # Try again with auth
    response = client.get("/api/protected")
    assert_valid_response(response, status_code=200)
```

---

## ✅ Best Practices

### 1. Use Factories for Test Data

**✅ Good**:
```python
team = TeamFactory.create(name="Test FC", city="Boston")
```

**❌ Bad**:
```python
team = {
    "id": 1,
    "name": "Test FC",
    "city": "Boston",
    "age_group_id": 2,
    "division_id": 1,
    "season_id": 1,
    "coach": "John Smith",
    "contact_email": "coach@test.com"
}
```

### 2. Use Custom Assertions

**✅ Good**:
```python
assert_valid_response(response, status_code=200)
assert_valid_team(team)
```

**❌ Bad**:
```python
assert response.status_code == 200
assert "id" in team
assert "name" in team
assert team["id"] > 0
```

### 3. Use Test Clients

**✅ Good**:
```python
admin_client = create_admin_client()
response = admin_client.post("/api/teams", json=team_data)
```

**❌ Bad**:
```python
client = TestClient(app)
client.headers["Authorization"] = "Bearer mock_token"
response = client.post("/api/teams", json=team_data)
```

### 4. Reset Factory Seed for Deterministic Tests

```python
from tests.fixtures.factories import reset_all_factories

@pytest.fixture(scope="function", autouse=True)
def reset_faker():
    """Reset Faker seed before each test."""
    reset_all_factories(seed=42)
```

### 5. Use Database Setup Scripts

```python
@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Setup test database once per session."""
    import subprocess
    subprocess.run(["./scripts/test-db-setup.sh", "integration"], check=True)
```

---

## 📝 Summary

### Created Infrastructure

| Component | Location | Purpose |
|-----------|----------|---------|
| **Seed Data** | `tests/fixtures/data/*.json` | Reference data, teams, users |
| **Factories** | `tests/fixtures/factories.py` | Deterministic test data generation |
| **Assertions** | `tests/utils/assertions.py` | Reusable test assertions |
| **Clients** | `tests/fixtures/clients.py` | Test client utilities |
| **DB Setup** | `scripts/test-db-setup.sh` | Per-layer database setup |

### Key Benefits

- ✅ **Deterministic**: Seeded Faker for reproducible tests
- ✅ **DRY**: Centralized test data generation
- ✅ **Maintainable**: Single source of truth for test data
- ✅ **Consistent**: Standardized assertions across all tests
- ✅ **Isolated**: Per-layer database setup

---

**Last Updated**: 2025-11-11  
**Maintained By**: Backend Team  
**Questions?** See [tests/README.md](../README.md)

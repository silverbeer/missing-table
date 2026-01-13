# DAO Refactoring - Technical Debt

**Status**: 🔴 High Priority
**Created**: 2026-01-13
**Estimated Effort**: 2-3 sprints
**Impact**: High - Improves maintainability, testing, and team collaboration

---

## Problem Statement

The `backend/dao/match_dao.py` file has grown into a **God Object anti-pattern** with **2,697 lines** of code containing unrelated responsibilities:

- Age group operations
- Season operations
- Match type operations
- League operations
- Division operations
- **Team operations** ← Doesn't belong in match_dao!
- Match operations (only these belong here!)
- Club operations
- Player operations
- User operations
- Standings/league table operations

**This violates**:
- Single Responsibility Principle (SRP)
- Separation of Concerns
- Domain-Driven Design principles

---

## Current Issues

### 1. **Maintainability**
- Hard to find specific functionality in a 2,697-line file
- Risk of unintended side effects when modifying code
- Difficult to understand the full scope of changes

### 2. **Testing**
- Cannot test domain operations in isolation
- Mocking requires the entire MatchDAO class
- Test setup is unnecessarily complex

### 3. **Team Collaboration**
- High risk of merge conflicts
- Multiple developers can't work on different domains simultaneously
- Code review is time-consuming

### 4. **Performance**
- Cannot optimize specific DAOs independently
- All operations share the same connection pool
- No domain-specific caching strategies

### 5. **Naming Confusion**
- "match_dao" contains team operations - misleading
- New developers struggle to find correct DAO
- API routes don't align with DAO structure

---

## Proposed Solution

### Phase 1: Extract Domain DAOs (Sprint 1)

Create focused, single-responsibility DAOs:

```
backend/dao/
├── __init__.py
├── base_dao.py              # Shared connection logic, base class
├── age_group_dao.py         # Age group CRUD operations
├── season_dao.py            # Season CRUD operations
├── match_type_dao.py        # Match type CRUD operations
├── league_dao.py            # League CRUD operations
├── division_dao.py          # Division CRUD operations
├── team_dao.py              # Team CRUD operations ⭐ NEW
├── match_dao.py             # Match operations ONLY (refactored)
├── club_dao.py              # Club CRUD operations
├── player_dao.py            # Player CRUD operations
└── standings_dao.py         # Standings/league table operations
```

### Phase 2: Update API Routes (Sprint 1-2)

Update `backend/app.py` to use appropriate DAOs:

```python
# Before
match_dao = MatchDAO(db_conn_holder)
team = match_dao.add_team(...)  # Wrong DAO!

# After
team_dao = TeamDAO(db_conn_holder)
team = team_dao.add_team(...)  # Correct DAO!
```

### Phase 3: Add Comprehensive Tests (Sprint 2)

Create focused test files:

```
backend/tests/dao/
├── test_team_dao.py
├── test_match_dao.py
├── test_league_dao.py
└── ...
```

### Phase 4: Update Documentation (Sprint 3)

- Update architecture diagrams
- Document DAO patterns and conventions
- Create migration guide for developers

---

## Detailed Refactoring Plan

### 1. Create `base_dao.py`

Extract common functionality:

```python
from supabase import Client

class BaseDAO:
    """Base DAO with shared connection logic."""

    def __init__(self, connection_holder):
        self.client: Client = connection_holder.get_client()

    def execute_query(self, query):
        """Common query execution with error handling."""
        try:
            return query.execute()
        except Exception as e:
            logger.exception("Database query failed")
            raise
```

### 2. Create `team_dao.py`

**Methods to move from `match_dao.py`**:

```python
class TeamDAO(BaseDAO):
    """Data access object for team operations."""

    # CRUD Operations
    def add_team(...)                              # Line 451 in match_dao.py
    def update_team_division(...)                  # Line 552
    def get_team_by_name(...)                      # Line 569
    def get_team_by_id(...)                        # Line 592
    def get_team_with_details(...)                 # Line 614
    def get_all_teams(...)                         # Line 267
    def get_teams_by_match_type_and_age_group(...) # Line 327
    def get_club_teams(...)                        # Find in match_dao.py
    def update_team(...)                           # Find in match_dao.py
    def delete_team(...)                           # Find in match_dao.py

    # Team Match Type Participation
    def add_team_match_type_participation(...)     # Line 420
    def remove_team_match_type_participation(...)  # Line 438
    def get_team_match_types(...)                  # Find in match_dao.py

    # Team Game Counts
    def get_team_game_counts(...)                  # Find in match_dao.py
```

### 3. Refactor `match_dao.py`

**Keep only match-related operations**:

```python
class MatchDAO(BaseDAO):
    """Data access object for match operations."""

    # Match CRUD
    def create_match(...)
    def get_match_by_id(...)
    def get_all_matches(...)
    def update_match(...)
    def delete_match(...)

    # Match Queries
    def get_match_by_external_id(...)
    def get_match_by_teams_and_date(...)
    def get_matches_by_team(...)

    # Match External ID
    def update_match_external_id(...)
    def add_match_with_external_id(...)
```

### 4. Create Other Domain DAOs

Follow the same pattern for:
- `age_group_dao.py`
- `season_dao.py`
- `match_type_dao.py`
- `league_dao.py`
- `division_dao.py`
- `club_dao.py`
- `player_dao.py`
- `standings_dao.py`

---

## Migration Strategy

### Approach: Gradual Migration (Recommended)

**Why**: Zero downtime, incremental testing, low risk

**Steps**:

1. **Create new DAOs** (Sprint 1, Week 1)
   - Copy methods to new DAO files
   - Keep original methods in `match_dao.py` (don't delete yet!)
   - Add `@deprecated` warnings

2. **Update API routes** (Sprint 1, Week 2)
   - Update `app.py` to use new DAOs
   - Test each endpoint thoroughly
   - Deploy to dev environment

3. **Update tests** (Sprint 2, Week 1-2)
   - Create focused DAO tests
   - Ensure 100% coverage for new DAOs
   - Test integration with API

4. **Remove old methods** (Sprint 2, Week 2)
   - Delete deprecated methods from `match_dao.py`
   - Update any remaining imports
   - Deploy to staging

5. **Documentation & cleanup** (Sprint 3)
   - Update architecture docs
   - Add inline code comments
   - Create developer guide

### Risk Mitigation

- ✅ Feature flags for new DAO usage
- ✅ Parallel run old + new DAOs initially
- ✅ Comprehensive integration tests
- ✅ Gradual rollout (dev → staging → prod)
- ✅ Easy rollback plan (keep old code until fully tested)

---

## Success Metrics

### Code Quality
- ✅ Each DAO file < 500 lines
- ✅ 100% test coverage for all DAOs
- ✅ No circular dependencies
- ✅ Zero linting errors

### Performance
- ✅ No regression in API response times
- ✅ Database query count unchanged
- ✅ Memory usage stable or improved

### Developer Experience
- ✅ Time to find specific DAO method < 30 seconds
- ✅ Merge conflicts reduced by 50%
- ✅ New developer onboarding time reduced

---

## Example: Team DAO Implementation

### File: `backend/dao/team_dao.py`

```python
"""
Team Data Access Object.

Handles all database operations related to teams including:
- Team CRUD operations
- Team-age group mappings
- Team-match type participations
- Team queries and filters
"""
from backend.dao.base_dao import BaseDAO
from backend.logging_config import get_logger

logger = get_logger(__name__)


class TeamDAO(BaseDAO):
    """Data access object for team operations."""

    def add_team(
        self,
        name: str,
        city: str,
        age_group_ids: list[int],
        match_type_ids: list[int] | None = None,
        division_id: int | None = None,
        club_id: int | None = None,
        academy_team: bool = False,
        client_ip: str | None = None,
    ) -> bool:
        """
        Add a new team with age groups, division, and match type participations.

        For guest/tournament teams, division_id can be None.

        Args:
            name: Team name
            city: Team city
            age_group_ids: List of age group IDs (required)
            match_type_ids: List of match type IDs (optional)
            division_id: Division ID (optional for guest teams)
            club_id: Optional club ID
            academy_team: Whether this is an academy team
            client_ip: Client IP for security monitoring

        Returns:
            bool: True if successful, False otherwise

        Raises:
            ValueError: If validation fails
        """
        logger.info(
            "Creating team",
            team_name=name,
            city=city,
            age_group_count=len(age_group_ids),
            match_type_count=len(match_type_ids) if match_type_ids else 0,
            division_id=division_id,
            club_id=club_id,
            academy_team=academy_team
        )

        # Implementation here...
        # (Use improved logging from the current add_team method)
```

---

## Next Steps

### Immediate (This Sprint)
1. ✅ Document this refactoring plan
2. ✅ Get team buy-in and approval
3. ⏳ Create GitHub issue for tracking
4. ⏳ Add to sprint backlog

### Short Term (Sprint 1)
1. Create `base_dao.py`
2. Create `team_dao.py` with all team operations
3. Update `app.py` to use `TeamDAO`
4. Write comprehensive tests

### Medium Term (Sprint 2-3)
1. Extract remaining domain DAOs
2. Refactor `match_dao.py` to only match operations
3. Update all API routes
4. Complete test coverage

---

## References

- **Current File**: `backend/dao/match_dao.py` (2,697 lines)
- **Example Issue**: Teams operations in match_dao (e.g., `add_team()` at line 451)
- **Related Docs**:
  - [Architecture Overview](../03-architecture/README.md)
  - [Testing Strategy](../04-testing/README.md)

---

**Questions? Contact**: @silverbeer or create an issue in GitHub

**Last Updated**: 2026-01-13

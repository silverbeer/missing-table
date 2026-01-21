# Player Stats Feature - Test Plan

**Parent checklist**: `docs/features/PLAYER_STATS.md`

## Overview

This document describes the testing strategy for the Player Stats feature. The implementation is divided into two parts:

1. **TSC Journey Tests** (End-to-End User Workflows) - Implemented
2. **Unit & Integration Tests** (Component-Level) - Deferred

---

## Part 1: TSC Journey Tests

TSC (Tom's Soccer Club) tests simulate complete user journeys through the invite system. The Player Stats feature integrates into these role-based workflows.

### Files Modified

| File | Changes |
|------|---------|
| `tests/fixtures/tsc/entities.py` | Add `roster_entries` tracking, `linked_player_id` field |
| `tests/fixtures/tsc/client.py` | Add 7 roster/stats methods |
| `tests/tsc/test_02_team_manager.py` | Add 4 tests for roster + goal recording |
| `tests/tsc/test_03_player.py` | Add/modify 3 tests for roster verification |

### Test Cases

#### Team Manager Journey (`test_02_team_manager.py`)

| Test | Description |
|------|-------------|
| `test_11a_create_roster_entries` | Team manager creates roster with jersey numbers 1, 7, 10, 11, 23 |
| `test_11b_verify_roster_display_names` | Verify display names and `has_account=False` before linking |
| `test_11c_record_goal_with_roster_player` | Record a goal using `player_id` and verify stats update |
| `test_12_create_player_invite_with_roster` | Create invite linked to roster entry (replaces legacy test) |

#### Player Journey (`test_03_player.py`)

| Test | Description |
|------|-------------|
| `test_01_validate_player_invite_with_roster_info` | Validate invite includes roster player info |
| `test_02a_verify_account_linked_to_roster` | After signup, verify `has_account=True` on roster entry |
| `test_09a_view_player_stats` | Player can view their stats |

### Running TSC Tests

```bash
# Full TSC journey (requires local Supabase running)
cd backend && uv run pytest tests/tsc/ -v

# Team Manager journey only
cd backend && uv run pytest tests/tsc/test_02_team_manager.py -v

# Player journey only
cd backend && uv run pytest tests/tsc/test_03_player.py -v

# Skip cleanup (for manual UI testing)
cd backend && uv run pytest tests/tsc/ -v --skip-cleanup
```

---

## Part 2: Unit & Integration Tests (Deferred)

The following tests are planned but not yet implemented.

### Test Strategy

| Component | Test Type | Location |
|-----------|-----------|----------|
| RosterDAO | Unit (mocks) | `tests/unit/dao/test_roster_dao.py` |
| PlayerStatsDAO | Unit (mocks) | `tests/unit/dao/test_player_stats_dao.py` |
| InviteService (player_id) | Unit (mocks) | `tests/unit/service_tests/test_invite_service.py` |
| Roster API endpoints | Integration | `tests/integration/api/test_roster_api.py` |
| Stats API endpoints | Integration | `tests/integration/api/test_player_stats_api.py` |
| Goal endpoint (player_id) | Integration | `tests/integration/api/test_live_match_api.py` |

### Planned Test Files

#### `tests/unit/dao/test_roster_dao.py` (17 tests)

- `test_get_team_roster_returns_players_with_display_name`
- `test_get_team_roster_empty_team_returns_empty_list`
- `test_get_player_by_id_found`
- `test_get_player_by_id_not_found_returns_none`
- `test_get_player_by_jersey_found`
- `test_get_player_by_jersey_not_found_returns_none`
- `test_create_player_success`
- `test_create_player_duplicate_jersey_fails`
- `test_bulk_create_players_success`
- `test_update_player_name_success`
- `test_update_jersey_number_success`
- `test_bulk_renumber_uses_temp_negative_values`
- `test_link_user_to_player_success`
- `test_delete_player_soft_delete`
- `test_add_display_name_with_linked_account`
- `test_add_display_name_with_roster_name`
- `test_add_display_name_jersey_number_only`

#### `tests/unit/dao/test_player_stats_dao.py` (14 tests)

- `test_get_match_stats_found`
- `test_get_match_stats_not_found_returns_none`
- `test_get_or_create_match_stats_creates_new`
- `test_get_or_create_match_stats_returns_existing`
- `test_increment_goals_success`
- `test_increment_goals_creates_record_if_missing`
- `test_decrement_goals_success`
- `test_decrement_goals_floors_at_zero`
- `test_set_started_true`
- `test_set_started_false`
- `test_update_minutes_success`
- `test_get_player_season_stats_aggregates_correctly`
- `test_get_team_stats_returns_sorted_by_goals`
- `test_record_match_appearance_sets_both_fields`

#### `tests/integration/api/test_roster_api.py` (11 tests)

- `test_get_team_roster_success`
- `test_get_team_roster_requires_season_id`
- `test_create_roster_entry_admin_success`
- `test_create_roster_entry_team_manager_success`
- `test_create_roster_entry_unauthorized`
- `test_create_roster_entry_duplicate_jersey_fails`
- `test_bulk_create_roster_success`
- `test_update_roster_entry_success`
- `test_change_jersey_number_success`
- `test_bulk_renumber_success`
- `test_delete_roster_entry_success`

#### `tests/integration/api/test_player_stats_api.py` (5 tests)

- `test_get_player_stats_success`
- `test_get_player_stats_player_not_found`
- `test_get_player_stats_no_stats_returns_zeros`
- `test_get_team_stats_success`
- `test_get_team_stats_team_not_found`

### Planned Factories (`tests/fixtures/factories.py`)

```python
class RosterFactory:
    """Factory for roster/player test data."""

    @classmethod
    def build(cls, **kwargs) -> dict:
        return {
            "id": kwargs.get("id", 1),
            "team_id": kwargs.get("team_id", 1),
            "season_id": kwargs.get("season_id", 1),
            "jersey_number": kwargs.get("jersey_number", 10),
            "first_name": kwargs.get("first_name"),
            "last_name": kwargs.get("last_name"),
            "user_profile_id": kwargs.get("user_profile_id"),
            "positions": kwargs.get("positions", []),
            "is_active": kwargs.get("is_active", True),
        }

    @classmethod
    def with_account(cls, **kwargs) -> dict:
        return cls.build(
            user_profile_id="user-123",
            first_name="Test",
            last_name="Player",
            **kwargs
        )

    @classmethod
    def jersey_only(cls, jersey_number: int, **kwargs) -> dict:
        return cls.build(jersey_number=jersey_number, **kwargs)


class PlayerStatsFactory:
    """Factory for player stats test data."""

    @classmethod
    def build(cls, **kwargs) -> dict:
        return {
            "id": kwargs.get("id", 1),
            "player_id": kwargs.get("player_id", 1),
            "match_id": kwargs.get("match_id", 1),
            "started": kwargs.get("started", False),
            "minutes_played": kwargs.get("minutes_played", 0),
            "goals": kwargs.get("goals", 0),
        }
```

---

## Related Files

### Backend Implementation (Already Complete)

| File | Description |
|------|-------------|
| `backend/dao/roster_dao.py` | Roster CRUD operations |
| `backend/dao/player_stats_dao.py` | Stats tracking |
| `backend/services/invite_service.py` | player_id support in invites |
| `backend/app.py` | Roster endpoints, modified goal endpoint |
| `backend/models/roster.py` | Pydantic models |
| `backend/dao/match_event_dao.py` | player_id support in events |

### Database Migrations

| File | Description |
|------|-------------|
| `supabase-local/migrations/20260117000001_create_players_table.sql` | Players table |
| `supabase-local/migrations/20260117000002_create_player_match_stats.sql` | Stats table |
| `supabase-local/migrations/20260117000003_add_player_id_to_invitations.sql` | Invite linking |
| `supabase-local/migrations/20260117000004_add_player_id_to_match_events.sql` | Event linking |

---

## Verification Checklist

After TSC test implementation:
- [ ] Run `cd backend && uv run pytest tests/tsc/ -v` - all pass
- [ ] Verify roster creation in team manager journey
- [ ] Verify roster-linked invite flow
- [ ] Verify account linking after player signup
- [ ] Update `docs/features/PLAYER_STATS.md` checklist

---

**Last Updated**: 2026-01-17

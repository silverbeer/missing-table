# Club Multi-League Implementation Plan

**Feature Branch:** `feature/add-league-layer`
**Schema Version:** 1.2.0 → 1.3.0
**Date:** 2025-10-30
**Status:** 🚧 In Progress

## Overview

This document outlines the implementation plan for enabling clubs to have teams in multiple leagues (Academy and Homegrown). The schema foundation is complete; this plan covers data migration, frontend updates, and deployment.

## Prerequisites ✅

- [x] Migration `20251030184100_add_parent_club_to_teams` applied
- [x] `parent_club_id` column added to teams table
- [x] Helper functions created (`get_club_teams`, `is_parent_club`, `get_parent_club`)
- [x] View `teams_with_parent` created
- [x] Schema version: 1.2.0

## Implementation Phases

### Phase 1: Data Analysis & Automated Migration Script
**Goal:** Identify clubs in multiple leagues and create automated migration

**Tasks:**
1. **Create analysis script** (`backend/scripts/analyze_multi_league_clubs.py`)
   - Query teams appearing in multiple leagues
   - Identify affected matches, team_mappings
   - Generate migration report (JSON + human-readable)
   - Estimate impact (# teams, matches, mappings affected)

2. **Create automated migration script** (`backend/scripts/migrate_club_data.py`)
   - Create parent club records
   - Create separate team records with naming convention
   - Update team_mappings to point to correct teams
   - Update matches (home_team_id, away_team_id)
   - Generate audit log of all changes
   - Support dry-run mode (preview without committing)
   - Support rollback capability

3. **Naming Convention Decision**
   - Decide on format: `"{Club} Academy"` vs `"{Club} - Academy"` vs `"{Club} (Academy)"`
   - Document in code and user-facing docs

4. **Validation**
   - Verify no orphaned team_mappings
   - Verify all matches reference valid teams
   - Verify parent_club_id relationships are correct
   - Run database integrity checks

**Success Criteria:**
- [ ] Analysis script identifies all multi-league clubs
- [ ] Migration script successfully runs in dry-run mode
- [ ] Migration script creates correct parent/child structure
- [ ] All team_mappings updated correctly
- [ ] All matches reference correct teams
- [ ] Validation passes with no errors
- [ ] Rollback capability tested and verified

**Deliverables:**
- `backend/scripts/analyze_multi_league_clubs.py`
- `backend/scripts/migrate_club_data.py`
- Migration report (JSON + markdown)
- Audit log of changes

---

### Phase 2: Backend API Updates
**Goal:** Update backend APIs to support club hierarchies

**Tasks:**
1. **Update Teams API** (`backend/api/teams.py`)
   - Add endpoint: `GET /api/teams/{id}/club-teams` - Get all teams for a club
   - Add endpoint: `GET /api/clubs` - List all parent clubs
   - Update `GET /api/teams` to include parent_club info
   - Add query parameter: `?include_parent=true`
   - Add query parameter: `?club_id={id}` for filtering

2. **Update Matches API** (`backend/api/matches.py`)
   - Update match queries to use teams_with_parent view
   - Add club-level match filtering
   - Ensure team names include league context

3. **Update Standings API** (`backend/api/standings.py`)
   - Ensure standings separate Academy vs Homegrown teams
   - Add club-level standings view (optional)

4. **Add Data Access Methods** (`backend/dao/`)
   - Add `get_club_teams(club_id)` method
   - Add `get_parent_club(team_id)` method
   - Add `is_parent_club(team_id)` method
   - Add `get_all_parent_clubs()` method

5. **Update Tests**
   - Add tests for new endpoints
   - Test parent/child relationship queries
   - Test club-level filtering

**Success Criteria:**
- [ ] All new endpoints return correct data
- [ ] Existing endpoints continue to work
- [ ] Tests pass for all API changes
- [ ] API documentation updated

**Deliverables:**
- Updated backend APIs
- New data access methods
- API tests
- API documentation updates

---

### Phase 3: Frontend Updates
**Goal:** Display club hierarchies in user interface

**Tasks:**
1. **Update Team Display Components**
   - **LeagueTable.vue**
     - Display team with parent club context (e.g., "IFA > IFA Academy")
     - Add club-level grouping/filtering option
     - Show clear distinction between Academy and Homegrown teams

   - **ScoresSchedule.vue**
     - Update team names to include league context
     - Add club filter dropdown
     - Group matches by club (optional)

   - **TeamSelector Component** (new or update existing)
     - Hierarchical dropdown (Club > Teams)
     - Clear visual distinction for parent clubs
     - Auto-expand when club selected

2. **Update Admin Panel**
   - **AdminPanel.vue**
     - Add section for managing club relationships
     - UI for creating parent clubs
     - UI for linking teams to parent clubs
     - Validation for parent_club_id updates

   - **Add ManageClubs.vue** (new component)
     - List all parent clubs
     - Show child teams for each club
     - Edit club information
     - Create/delete parent clubs
     - Assign teams to clubs

3. **Update Stores/State Management**
   - Update teams store to handle parent_club data
   - Add club-level filtering state
   - Cache parent club relationships

4. **Update Routing**
   - Add route: `/clubs` - List all clubs
   - Add route: `/clubs/:id` - Club detail with all teams
   - Add route: `/admin/clubs` - Manage clubs

**Success Criteria:**
- [ ] Teams display with clear league context
- [ ] Users can filter by club
- [ ] Admin can manage club relationships
- [ ] UI is intuitive and clear
- [ ] No breaking changes to existing views

**Deliverables:**
- Updated Vue components
- New ManageClubs component
- Updated routing
- Updated state management

---

### Phase 4: Testing & Validation
**Goal:** Comprehensive testing in local environment

**Tasks:**
1. **Local Environment Testing**
   - Run migration script on local database
   - Verify data migration correctness
   - Test all frontend components
   - Test all API endpoints
   - Test admin functionality

2. **Data Integrity Checks**
   - Run `inspect_db.py` to verify data
   - Check for orphaned records
   - Verify standings calculations
   - Verify match display

3. **User Acceptance Testing**
   - Test user workflows (viewing standings, matches)
   - Test admin workflows (managing teams, clubs)
   - Verify no confusion with team names
   - Verify clear league context

4. **Performance Testing**
   - Test query performance with club hierarchies
   - Verify no N+1 query issues
   - Test frontend rendering performance

**Success Criteria:**
- [ ] All tests pass
- [ ] No data integrity issues
- [ ] Performance is acceptable
- [ ] User workflows are clear and intuitive

**Deliverables:**
- Test results report
- Performance metrics
- Bug fixes (if any)

---

### Phase 5: Documentation Updates
**Goal:** Update all documentation to reflect club hierarchy

**Tasks:**
1. **Update Schema Documentation**
   - Update `docs/database-schema.md` with parent_club_id
   - Document club hierarchy functions and views
   - Add query examples

2. **Update Developer Documentation**
   - Update `docs/02-development/daily-workflow.md` with new scripts
   - Document migration script usage
   - Document new API endpoints

3. **Update Architecture Documentation**
   - Update `docs/03-architecture/database-design.md`
   - Add club hierarchy diagrams
   - Explain design decisions

4. **Update User Documentation**
   - Document club filtering features
   - Document admin club management
   - Add screenshots of new UI

5. **Update Migration Documentation**
   - Finalize `PARENT_CLUB_MIGRATION_GUIDE.md`
   - Add post-migration verification steps
   - Document rollback procedures

**Success Criteria:**
- [ ] All documentation is current
- [ ] Examples are tested and working
- [ ] Screenshots are up-to-date
- [ ] Migration guide is complete

**Deliverables:**
- Updated documentation files
- New diagrams (if needed)
- Screenshots

---

### Phase 6: Dev Environment Deployment
**Goal:** Deploy to dev environment and test with real data

**Tasks:**
1. **Pre-Deployment**
   - Backup dev database: `./scripts/db_tools.sh backup dev`
   - Review migration plan
   - Schedule deployment window

2. **Deploy to Dev**
   - Push feature branch to GitHub
   - Deploy backend to dev: `./build-and-push.sh backend dev`
   - Deploy frontend to dev: `./build-and-push.sh frontend dev`
   - Apply to GKE: `kubectl rollout restart deployment/missing-table-backend -n missing-table-dev`

3. **Run Migration**
   - SSH/exec into backend pod
   - Run analysis script: `python scripts/analyze_multi_league_clubs.py`
   - Review migration report
   - Run migration script: `python scripts/migrate_club_data.py --dry-run`
   - Review dry-run output
   - Run migration: `python scripts/migrate_club_data.py --execute`

4. **Post-Migration Validation**
   - Run database integrity checks
   - Test all frontend features on dev URL
   - Verify standings are correct
   - Verify matches display correctly
   - Test admin functionality

5. **Monitoring**
   - Monitor application logs
   - Monitor database performance
   - Check for any errors or issues
   - Collect user feedback (if any dev users)

**Success Criteria:**
- [ ] Migration completes successfully in dev
- [ ] All features work in dev environment
- [ ] No data corruption or errors
- [ ] Performance is acceptable
- [ ] Dev environment is stable

**Deliverables:**
- Migration execution log
- Post-migration validation report
- Any bug fixes needed

---

### Phase 7: Production Deployment
**Goal:** Deploy to production environment safely

**Tasks:**
1. **Pre-Production Checklist**
   - All dev testing complete and successful
   - All documentation updated
   - Production backup created
   - Rollback plan documented
   - Deployment window scheduled
   - Stakeholders notified

2. **Production Backup**
   - Create full production backup: `./scripts/db_tools.sh backup prod`
   - Export backup to safe location
   - Verify backup integrity
   - Document backup timestamp

3. **Merge to Main**
   - Create pull request from feature branch
   - Code review
   - Approval
   - Merge to main (triggers auto-deployment)

4. **Monitor Auto-Deployment**
   - Watch GitHub Actions: https://github.com/silverbeer/missing-table/actions
   - Monitor deployment progress
   - Verify health checks pass

5. **Run Production Migration**
   - SSH/exec into production backend pod
   - Run analysis script
   - Review migration report
   - Run migration in dry-run mode
   - Get final approval
   - Execute migration
   - Monitor execution

6. **Post-Deployment Validation**
   - Run health checks: `./scripts/health-check.sh prod`
   - Test all critical user workflows
   - Verify standings are correct
   - Verify matches display correctly
   - Check application logs
   - Monitor performance metrics

7. **Post-Deployment Monitoring**
   - Monitor for 24-48 hours
   - Watch for any user-reported issues
   - Monitor database performance
   - Be ready to rollback if needed

**Success Criteria:**
- [ ] Production deployment successful
- [ ] Migration completes without errors
- [ ] All production features working
- [ ] No user-facing issues
- [ ] Performance is acceptable
- [ ] System is stable

**Rollback Plan:**
- Restore production database from backup
- Rollback Helm deployment: `helm rollback missing-table -n missing-table-prod`
- Revert to previous git commit
- Re-deploy if needed

**Deliverables:**
- Production migration log
- Post-deployment report
- Lessons learned document

---

## Decision Log

### Decisions to Make (Phase 1)

1. **Naming Convention**
   - Option A: `"IFA Academy"` / `"IFA Homegrown"` ⭐ (Recommended)
   - Option B: `"IFA - Academy"` / `"IFA - Homegrown"`
   - Option C: `"IFA (Academy)"` / `"IFA (Homegrown)"`

   **Decision:** _Pending_

2. **League Names**
   - Confirm: "Homegrown" (existing)
   - Confirm: "Academy" (new)

   **Decision:** _Pending_

3. **Parent Club Creation**
   - Auto-create parent clubs for all multi-league teams?
   - Or leave parent_club_id NULL and just separate teams?

   **Decision:** _Pending_

4. **Migration Timing**
   - All at once?
   - Gradual (by club)?

   **Decision:** _Pending_

### Decisions Made

- [x] Schema approach: Option 2 (Separate Team Records) ✅
- [x] Use `parent_club_id` for club hierarchy ✅
- [x] Single-level hierarchy (no grandchildren) ✅

---

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| Data corruption during migration | High | Low | Comprehensive backups, dry-run mode, rollback capability |
| User confusion with new team names | Medium | Medium | Clear naming convention, documentation, tooltips in UI |
| Performance degradation | Medium | Low | Test queries, add indexes if needed, monitor performance |
| Breaking existing integrations | High | Low | Comprehensive testing, backward compatibility checks |
| Incomplete match/mapping updates | High | Low | Validation scripts, integrity checks, audit logs |

---

## Success Metrics

1. **Data Integrity**
   - 100% of teams in multiple leagues separated correctly
   - 100% of matches reference correct teams
   - 0 orphaned team_mappings
   - 0 data integrity errors

2. **User Experience**
   - Clear distinction between Academy and Homegrown teams
   - Intuitive club filtering
   - No user confusion reports

3. **Performance**
   - Page load times remain < 2 seconds
   - API response times < 500ms
   - No performance regressions

4. **Deployment**
   - Zero-downtime deployment
   - Successful migration in all environments
   - No rollbacks needed

---

## Timeline Estimate

- **Phase 1:** 1-2 days (scripts + testing)
- **Phase 2:** 1-2 days (backend APIs)
- **Phase 3:** 2-3 days (frontend updates)
- **Phase 4:** 1 day (testing)
- **Phase 5:** 1 day (documentation)
- **Phase 6:** 1 day (dev deployment)
- **Phase 7:** 1 day (production deployment)

**Total Estimate:** 8-12 days

---

## References

- [Parent Club Migration Guide](./PARENT_CLUB_MIGRATION_GUIDE.md)
- [Club League Analysis](./CLUB_LEAGUE_ANALYSIS.md)
- [Database Schema Documentation](./database-schema.md)
- [Migration Best Practices](./MIGRATION_BEST_PRACTICES.md)

---

**Last Updated:** 2025-10-30
**Document Owner:** silverbeer
**Status:** 🚧 Ready to start Phase 1

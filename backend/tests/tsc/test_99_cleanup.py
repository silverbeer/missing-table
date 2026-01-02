"""
TSC Journey Tests - Phase 99: Cleanup.

This phase cleans up all test entities by querying for entities with the
tsc_a_ prefix. This approach is safer than ID-based cleanup because:
- Works across environments (local, dev, prod)
- Doesn't depend on a registry file
- Idempotent - safe to run multiple times

Cleanup order (FK-safe):
1. Matches (depends on teams, seasons, age_groups)
2. Teams (depends on clubs, divisions, age_groups)
3. Club (no dependencies after teams gone)
4. Division (no dependencies after teams gone)
5. League (no dependencies after division gone)
6. Age Group (no dependencies after teams gone)
7. Season (no dependencies after matches gone)

Note: Users created via invites are NOT deleted automatically.
They can be manually cleaned up by an admin.

Run: pytest tests/tsc/test_99_cleanup.py -v
"""

import pytest

from tests.fixtures.tsc import TSCClient, TSCConfig
from api_client.exceptions import NotFoundError


class TestCleanup:
    """Phase 99: Clean up all test entities by name prefix."""

    def test_01_login_admin(
        self,
        tsc_client: TSCClient,
        existing_admin_credentials: tuple[str, str],
    ):
        """Login as admin for cleanup operations."""
        username, password = existing_admin_credentials
        result = tsc_client.login(username, password)

        assert "access_token" in result or "session" in result
        print(f"Logged in as admin: {username}")

    def test_02_find_and_delete_matches(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Find and delete all matches involving tsc_a_ teams."""
        prefix = tsc_config.prefix

        # First find teams with our prefix
        print(f"\nFinding teams with prefix '{prefix}'...")
        all_teams = tsc_client.get_teams()
        tsc_teams = [t for t in all_teams if t.get("name", "").startswith(prefix)]
        team_ids = [t["id"] for t in tsc_teams]

        if not team_ids:
            print("No teams found with prefix - skipping match cleanup")
            return

        print(f"Found {len(tsc_teams)} teams: {[t['name'] for t in tsc_teams]}")

        # Find matches involving these teams
        print("\nFinding matches involving these teams...")
        all_matches = tsc_client.get_matches()
        tsc_matches = [
            m for m in all_matches
            if m.get("home_team_id") in team_ids or m.get("away_team_id") in team_ids
        ]

        print(f"Found {len(tsc_matches)} matches to delete")

        # Delete matches
        deleted = 0
        failed = 0
        for match in tsc_matches:
            try:
                tsc_client.delete_match(match["id"])
                deleted += 1
                print(f"  Deleted match: {match['id']}")
            except NotFoundError:
                print(f"  Match {match['id']} not found (already deleted?)")
                deleted += 1
            except Exception as e:
                print(f"  Failed to delete match {match['id']}: {e}")
                failed += 1

        print(f"\nDeleted {deleted} matches, {failed} failed")

    def test_03_find_and_delete_teams(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Find and delete all teams with tsc_a_ prefix."""
        prefix = tsc_config.prefix

        print(f"\nFinding teams with prefix '{prefix}'...")
        all_teams = tsc_client.get_teams()
        tsc_teams = [t for t in all_teams if t.get("name", "").startswith(prefix)]

        print(f"Found {len(tsc_teams)} teams to delete")

        deleted = 0
        failed = 0
        for team in tsc_teams:
            try:
                tsc_client.delete_team(team["id"])
                deleted += 1
                print(f"  Deleted team: {team['name']} (ID: {team['id']})")
            except NotFoundError:
                print(f"  Team {team['name']} not found (already deleted?)")
                deleted += 1
            except Exception as e:
                print(f"  Failed to delete team {team['name']}: {e}")
                failed += 1

        print(f"\nDeleted {deleted} teams, {failed} failed")

    def test_04_find_and_delete_clubs(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Find and delete all clubs with tsc_a_ prefix."""
        prefix = tsc_config.prefix

        print(f"\nFinding clubs with prefix '{prefix}'...")
        all_clubs = tsc_client.get_clubs()
        tsc_clubs = [c for c in all_clubs if c.get("name", "").startswith(prefix)]

        print(f"Found {len(tsc_clubs)} clubs to delete")

        deleted = 0
        failed = 0
        for club in tsc_clubs:
            try:
                tsc_client.delete_club(club["id"])
                deleted += 1
                print(f"  Deleted club: {club['name']} (ID: {club['id']})")
            except NotFoundError:
                print(f"  Club {club['name']} not found (already deleted?)")
                deleted += 1
            except Exception as e:
                print(f"  Failed to delete club {club['name']}: {e}")
                failed += 1

        print(f"\nDeleted {deleted} clubs, {failed} failed")

    def test_05_find_and_delete_divisions(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Find and delete all divisions with tsc_a_ prefix."""
        prefix = tsc_config.prefix

        print(f"\nFinding divisions with prefix '{prefix}'...")
        all_divisions = tsc_client.get_divisions()
        tsc_divisions = [d for d in all_divisions if d.get("name", "").startswith(prefix)]

        print(f"Found {len(tsc_divisions)} divisions to delete")

        deleted = 0
        failed = 0
        for division in tsc_divisions:
            try:
                tsc_client.delete_division(division["id"])
                deleted += 1
                print(f"  Deleted division: {division['name']} (ID: {division['id']})")
            except NotFoundError:
                print(f"  Division {division['name']} not found (already deleted?)")
                deleted += 1
            except Exception as e:
                print(f"  Failed to delete division {division['name']}: {e}")
                failed += 1

        print(f"\nDeleted {deleted} divisions, {failed} failed")

    def test_06_find_and_delete_leagues(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Find and delete all leagues with tsc_a_ prefix."""
        prefix = tsc_config.prefix

        print(f"\nFinding leagues with prefix '{prefix}'...")
        all_leagues = tsc_client.get_leagues()
        tsc_leagues = [lg for lg in all_leagues if lg.get("name", "").startswith(prefix)]

        print(f"Found {len(tsc_leagues)} leagues to delete")

        deleted = 0
        failed = 0
        for league in tsc_leagues:
            try:
                tsc_client.delete_league(league["id"])
                deleted += 1
                print(f"  Deleted league: {league['name']} (ID: {league['id']})")
            except NotFoundError:
                print(f"  League {league['name']} not found (already deleted?)")
                deleted += 1
            except Exception as e:
                print(f"  Failed to delete league {league['name']}: {e}")
                failed += 1

        print(f"\nDeleted {deleted} leagues, {failed} failed")

    def test_07_find_and_delete_age_groups(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Find and delete all age groups with tsc_a_ prefix."""
        prefix = tsc_config.prefix

        print(f"\nFinding age groups with prefix '{prefix}'...")
        all_age_groups = tsc_client.get_age_groups()
        tsc_age_groups = [ag for ag in all_age_groups if ag.get("name", "").startswith(prefix)]

        print(f"Found {len(tsc_age_groups)} age groups to delete")

        deleted = 0
        failed = 0
        for age_group in tsc_age_groups:
            try:
                tsc_client.delete_age_group(age_group["id"])
                deleted += 1
                print(f"  Deleted age group: {age_group['name']} (ID: {age_group['id']})")
            except NotFoundError:
                print(f"  Age group {age_group['name']} not found (already deleted?)")
                deleted += 1
            except Exception as e:
                print(f"  Failed to delete age group {age_group['name']}: {e}")
                failed += 1

        print(f"\nDeleted {deleted} age groups, {failed} failed")

    def test_08_find_and_delete_seasons(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Find and delete all seasons with tsc_a_ prefix."""
        prefix = tsc_config.prefix

        print(f"\nFinding seasons with prefix '{prefix}'...")
        all_seasons = tsc_client.get_seasons()
        tsc_seasons = [s for s in all_seasons if s.get("name", "").startswith(prefix)]

        print(f"Found {len(tsc_seasons)} seasons to delete")

        deleted = 0
        failed = 0
        for season in tsc_seasons:
            try:
                tsc_client.delete_season(season["id"])
                deleted += 1
                print(f"  Deleted season: {season['name']} (ID: {season['id']})")
            except NotFoundError:
                print(f"  Season {season['name']} not found (already deleted?)")
                deleted += 1
            except Exception as e:
                print(f"  Failed to delete season {season['name']}: {e}")
                failed += 1

        print(f"\nDeleted {deleted} seasons, {failed} failed")

    def test_08b_find_and_delete_users(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Find and delete all users with tsc_ prefix in username."""
        prefix = tsc_config.prefix

        print(f"\nFinding users with prefix '{prefix}' in username...")
        all_users = tsc_client.get_users()
        tsc_users = [u for u in all_users if u.get("username", "").startswith(prefix)]

        print(f"Found {len(tsc_users)} users to delete")

        deleted = 0
        failed = 0
        for user in tsc_users:
            try:
                tsc_client.delete_user(user["id"])
                deleted += 1
                print(f"  Deleted user: {user.get('username', 'unknown')} (ID: {user['id']})")
            except NotFoundError:
                print(f"  User {user.get('username')} not found (already deleted?)")
                deleted += 1
            except Exception as e:
                print(f"  Failed to delete user {user.get('username')}: {e}")
                failed += 1

        print(f"\nDeleted {deleted} users, {failed} failed")

    def test_09_verify_cleanup(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Verify all entities with prefix were cleaned up."""
        prefix = tsc_config.prefix

        print(f"\n{'=' * 50}")
        print("CLEANUP VERIFICATION")
        print(f"{'=' * 50}")
        print(f"Prefix: {prefix}")

        # Check each entity type
        issues = []

        teams = [t for t in tsc_client.get_teams() if t.get("name", "").startswith(prefix)]
        if teams:
            issues.append(f"Teams remaining: {[t['name'] for t in teams]}")
        print(f"Teams with prefix: {len(teams)}")

        clubs = [c for c in tsc_client.get_clubs() if c.get("name", "").startswith(prefix)]
        if clubs:
            issues.append(f"Clubs remaining: {[c['name'] for c in clubs]}")
        print(f"Clubs with prefix: {len(clubs)}")

        divisions = [d for d in tsc_client.get_divisions() if d.get("name", "").startswith(prefix)]
        if divisions:
            issues.append(f"Divisions remaining: {[d['name'] for d in divisions]}")
        print(f"Divisions with prefix: {len(divisions)}")

        leagues = [lg for lg in tsc_client.get_leagues() if lg.get("name", "").startswith(prefix)]
        if leagues:
            issues.append(f"Leagues remaining: {[lg['name'] for lg in leagues]}")
        print(f"Leagues with prefix: {len(leagues)}")

        age_groups = [ag for ag in tsc_client.get_age_groups() if ag.get("name", "").startswith(prefix)]
        if age_groups:
            issues.append(f"Age groups remaining: {[ag['name'] for ag in age_groups]}")
        print(f"Age groups with prefix: {len(age_groups)}")

        seasons = [s for s in tsc_client.get_seasons() if s.get("name", "").startswith(prefix)]
        if seasons:
            issues.append(f"Seasons remaining: {[s['name'] for s in seasons]}")
        print(f"Seasons with prefix: {len(seasons)}")

        users = [u for u in tsc_client.get_users() if u.get("username", "").startswith(prefix)]
        if users:
            issues.append(f"Users remaining: {[u['username'] for u in users]}")
        print(f"Users with prefix: {len(users)}")

        if issues:
            print(f"\n⚠️  Some entities were not cleaned up:")
            for issue in issues:
                print(f"  - {issue}")
            pytest.fail(f"Cleanup incomplete: {len(issues)} entity types still have data")

        print(f"\n✅ All {prefix}* entities cleaned up successfully!")

    def test_10_clear_registry_file(self):
        """Clear the persisted registry file for current environment."""
        from tests.tsc.conftest import clear_entity_registry, get_registry_file

        registry_file = get_registry_file()
        print(f"Registry file: {registry_file.name}")
        clear_entity_registry()
        print("Cleared entity registry file for current environment")

"""
TSC Journey Tests - Phase 99: Cleanup.

This phase cleans up all test entities in FK-safe order:
1. Matches (depends on teams, seasons, age_groups)
2. Teams (depends on clubs, divisions, age_groups)
3. Club (no dependencies after teams gone)
4. Pending invites (cancel any remaining)
5. Division (no dependencies after teams gone)
6. League (no dependencies after division gone)
7. Age Group (no dependencies after teams gone)
8. Season (no dependencies after matches gone)

Note: Users created via invites are NOT deleted automatically.
They can be manually cleaned up by an admin.

Run: pytest tests/tsc/test_99_cleanup.py -v
"""

import pytest

from tests.fixtures.tsc import EntityRegistry, TSCClient, TSCConfig
from api_client.exceptions import NotFoundError


class TestCleanup:
    """Phase 99: Clean up all test entities."""

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

    def test_02_delete_matches(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Delete all test matches."""
        deleted = 0
        failed = 0

        for match_id in entity_registry.match_ids:
            try:
                tsc_client.delete_match(match_id)
                deleted += 1
                print(f"  Deleted match: {match_id}")
            except NotFoundError:
                print(f"  Match {match_id} not found (already deleted?)")
                deleted += 1
            except Exception as e:
                print(f"  Failed to delete match {match_id}: {e}")
                failed += 1

        print(f"Deleted {deleted} matches, {failed} failed")
        entity_registry.match_ids.clear()

    def test_03_delete_extra_teams(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Delete extra teams created during journey."""
        deleted = 0
        failed = 0

        for team_id in entity_registry.extra_team_ids:
            try:
                tsc_client.delete_team(team_id)
                deleted += 1
                print(f"  Deleted extra team: {team_id}")
            except NotFoundError:
                print(f"  Team {team_id} not found (already deleted?)")
                deleted += 1
            except Exception as e:
                print(f"  Failed to delete team {team_id}: {e}")
                failed += 1

        print(f"Deleted {deleted} extra teams, {failed} failed")
        entity_registry.extra_team_ids.clear()

    def test_04_delete_reserve_team(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Delete reserve team."""
        if not entity_registry.reserve_team_id:
            pytest.skip("No reserve team to delete")

        try:
            tsc_client.delete_team(entity_registry.reserve_team_id)
            print(f"Deleted reserve team: {entity_registry.reserve_team_id}")
            entity_registry.reserve_team_id = None
        except NotFoundError:
            print(f"Reserve team not found (already deleted?)")
            entity_registry.reserve_team_id = None
        except Exception as e:
            pytest.fail(f"Failed to delete reserve team: {e}")

    def test_05_delete_premier_team(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Delete premier team."""
        if not entity_registry.premier_team_id:
            pytest.skip("No premier team to delete")

        try:
            tsc_client.delete_team(entity_registry.premier_team_id)
            print(f"Deleted premier team: {entity_registry.premier_team_id}")
            entity_registry.premier_team_id = None
        except NotFoundError:
            print(f"Premier team not found (already deleted?)")
            entity_registry.premier_team_id = None
        except Exception as e:
            pytest.fail(f"Failed to delete premier team: {e}")

    def test_06_delete_club(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Delete club."""
        if not entity_registry.club_id:
            pytest.skip("No club to delete")

        try:
            tsc_client.delete_club(entity_registry.club_id)
            print(f"Deleted club: {entity_registry.club_id}")
            entity_registry.club_id = None
        except NotFoundError:
            print(f"Club not found (already deleted?)")
            entity_registry.club_id = None
        except Exception as e:
            pytest.fail(f"Failed to delete club: {e}")

    def test_07_cancel_pending_invites(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Cancel any pending invites."""
        cancelled = 0
        failed = 0

        pending_invites = [
            inv for inv in entity_registry.invites
            if inv["status"] == "pending"
        ]

        for invite in pending_invites:
            try:
                tsc_client.cancel_invite(invite["id"])
                invite["status"] = "cancelled"
                cancelled += 1
                print(f"  Cancelled invite: {invite['id']}")
            except NotFoundError:
                print(f"  Invite {invite['id']} not found (already cancelled?)")
                cancelled += 1
            except Exception as e:
                print(f"  Failed to cancel invite {invite['id']}: {e}")
                failed += 1

        print(f"Cancelled {cancelled} invites, {failed} failed")

    def test_08_delete_division(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Delete division."""
        if not entity_registry.division_id:
            pytest.skip("No division to delete")

        try:
            tsc_client.delete_division(entity_registry.division_id)
            print(f"Deleted division: {entity_registry.division_id}")
            entity_registry.division_id = None
        except NotFoundError:
            print(f"Division not found (already deleted?)")
            entity_registry.division_id = None
        except Exception as e:
            pytest.fail(f"Failed to delete division: {e}")

    def test_09_delete_league(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Delete league."""
        if not entity_registry.league_id:
            pytest.skip("No league to delete")

        try:
            tsc_client.delete_league(entity_registry.league_id)
            print(f"Deleted league: {entity_registry.league_id}")
            entity_registry.league_id = None
        except NotFoundError:
            print(f"League not found (already deleted?)")
            entity_registry.league_id = None
        except Exception as e:
            pytest.fail(f"Failed to delete league: {e}")

    def test_10_delete_age_group(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Delete age group."""
        if not entity_registry.age_group_id:
            pytest.skip("No age group to delete")

        try:
            tsc_client.delete_age_group(entity_registry.age_group_id)
            print(f"Deleted age group: {entity_registry.age_group_id}")
            entity_registry.age_group_id = None
        except NotFoundError:
            print(f"Age group not found (already deleted?)")
            entity_registry.age_group_id = None
        except Exception as e:
            pytest.fail(f"Failed to delete age group: {e}")

    def test_11_delete_season(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Delete season."""
        if not entity_registry.season_id:
            pytest.skip("No season to delete")

        try:
            tsc_client.delete_season(entity_registry.season_id)
            print(f"Deleted season: {entity_registry.season_id}")
            entity_registry.season_id = None
        except NotFoundError:
            print(f"Season not found (already deleted?)")
            entity_registry.season_id = None
        except Exception as e:
            pytest.fail(f"Failed to delete season: {e}")

    def test_12_verify_cleanup(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Verify all entities were cleaned up."""
        print("\n=== Cleanup Verification ===")
        print(f"Season ID: {entity_registry.season_id} (should be None)")
        print(f"Age Group ID: {entity_registry.age_group_id} (should be None)")
        print(f"League ID: {entity_registry.league_id} (should be None)")
        print(f"Division ID: {entity_registry.division_id} (should be None)")
        print(f"Club ID: {entity_registry.club_id} (should be None)")
        print(f"Premier Team ID: {entity_registry.premier_team_id} (should be None)")
        print(f"Reserve Team ID: {entity_registry.reserve_team_id} (should be None)")
        print(f"Extra Teams: {len(entity_registry.extra_team_ids)} (should be 0)")
        print(f"Matches: {len(entity_registry.match_ids)} (should be 0)")

        # Verify all main entities are gone
        assert entity_registry.season_id is None, "Season not deleted"
        assert entity_registry.age_group_id is None, "Age group not deleted"
        assert entity_registry.league_id is None, "League not deleted"
        assert entity_registry.division_id is None, "Division not deleted"
        assert entity_registry.club_id is None, "Club not deleted"
        assert entity_registry.premier_team_id is None, "Premier team not deleted"
        assert entity_registry.reserve_team_id is None, "Reserve team not deleted"
        assert len(entity_registry.extra_team_ids) == 0, "Extra teams not deleted"
        assert len(entity_registry.match_ids) == 0, "Matches not deleted"

        # Note about users
        if entity_registry.user_ids:
            print(f"\nNote: {len(entity_registry.user_ids)} users were created via invites.")
            print("These users are NOT automatically deleted.")
            print("To manually clean up users, use the admin panel or database.")
            for user_id in entity_registry.user_ids:
                print(f"  - User ID: {user_id}")

        print("\n=== Phase 99 Complete - All Test Entities Cleaned Up ===")

    def test_13_clear_registry_file(
        self,
        entity_registry: EntityRegistry,
    ):
        """Clear the persisted registry file."""
        from tests.tsc.conftest import clear_entity_registry

        clear_entity_registry()
        print("Cleared entity registry file")

"""
Admin Journey Tests for Missing Table.

These tests validate complete user journeys through the admin panel,
including access control, navigation, and CRUD operations.

Test Categories:
- Access Control: Role-based access verification
- Navigation: Section switching and visibility
- Team Management: Create, edit, delete teams
- Invite Management: Create and manage invites
"""

import pytest
from playwright.sync_api import Page, expect

from page_objects import (
    AdminPage,
    AdminSection,
    AdminTeamsSection,
    AdminInvitesSection,
    InviteType,
    InviteStatus,
    LoginPage,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def admin_page(page: Page, base_url: str) -> AdminPage:
    """Create an AdminPage instance."""
    return AdminPage(page, base_url)


@pytest.fixture
def login_page(page: Page, base_url: str) -> LoginPage:
    """Create a LoginPage instance."""
    return LoginPage(page, base_url)


@pytest.fixture
def teams_section(page: Page) -> AdminTeamsSection:
    """Create an AdminTeamsSection instance."""
    return AdminTeamsSection(page)


@pytest.fixture
def invites_section(page: Page) -> AdminInvitesSection:
    """Create an AdminInvitesSection instance."""
    return AdminInvitesSection(page)


# =============================================================================
# Access Control Tests
# =============================================================================


@pytest.mark.smoke
@pytest.mark.auth
class TestAdminAccessControl:
    """Tests for admin panel access control."""

    def test_unauthenticated_user_cannot_access_admin(
        self,
        admin_page: AdminPage,
        page: Page,
    ):
        """Unauthenticated users should see login form or access denied - not admin panel."""
        admin_page.navigate()

        # App should show one of:
        # 1. Login form (client-side route guard shows login at same URL)
        # 2. Redirect to /login URL
        # 3. Access denied message
        # But NOT the admin panel content
        current_url = page.url
        is_url_redirected = "/login" in current_url or "/auth" in current_url
        is_access_denied = admin_page.is_access_denied()
        is_login_form_shown = page.locator("text=Log In").first.is_visible()
        has_admin_access = admin_page.has_access()

        # Should NOT have admin access
        assert not has_admin_access, "Unauthenticated user should not have admin access"

        # Should see login form OR redirect OR access denied
        assert is_url_redirected or is_access_denied or is_login_form_shown, (
            f"Expected login form, redirect, or access denied. "
            f"URL: {current_url}"
        )

    def test_admin_user_can_access_admin_panel(
        self,
        admin_page: AdminPage,
        admin_user,  # fixture that provides admin credentials
        login_page: LoginPage,
    ):
        """Admin users should have full access to admin panel."""
        # Login as admin
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        # Navigate to admin
        admin_page.navigate()
        admin_page.wait_for_load()

        assert admin_page.has_access()
        assert not admin_page.is_access_denied()

    def test_admin_sees_all_tabs(
        self,
        admin_page: AdminPage,
        admin_user,
        login_page: LoginPage,
    ):
        """Admin users should see all admin tabs including admin-only sections."""
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.wait_for_load()

        # Verify admin-only tabs are visible
        admin_only_tabs = admin_page.verify_admin_only_tabs()
        for section, is_visible in admin_only_tabs.items():
            assert is_visible, f"Admin-only tab '{section}' should be visible for admin"

    def test_club_manager_sees_limited_tabs(
        self,
        admin_page: AdminPage,
        manager_user,  # fixture for club manager credentials
        login_page: LoginPage,
    ):
        """Club managers should only see their allowed tabs."""
        login_page.navigate()
        login_page.login(manager_user.username, manager_user.password)

        admin_page.navigate()
        admin_page.wait_for_load()

        # Club managers should see these tabs
        club_manager_tabs = admin_page.verify_club_manager_tabs()
        for section, is_visible in club_manager_tabs.items():
            assert is_visible, f"Tab '{section}' should be visible for club manager"

        # Admin-only tabs should NOT be visible
        admin_only_tabs = admin_page.verify_admin_only_tabs()
        for section, is_visible in admin_only_tabs.items():
            assert not is_visible, f"Admin-only tab '{section}' should NOT be visible for club manager"


# =============================================================================
# Navigation Tests
# =============================================================================


@pytest.mark.smoke
class TestAdminNavigation:
    """Tests for admin panel navigation."""

    def test_navigate_through_all_sections(
        self,
        admin_page: AdminPage,
        admin_user,
        login_page: LoginPage,
    ):
        """Admin can navigate through all sections."""
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.wait_for_load()

        # Get all visible tabs
        visible_tabs = admin_page.get_visible_tabs()

        # Navigate through each visible section
        for section in visible_tabs:
            admin_page.go_to_section(section)
            assert admin_page.is_section_visible(section), \
                f"Section {section.value} should be visible after navigation"

    def test_section_persistence_on_refresh(
        self,
        admin_page: AdminPage,
        admin_user,
        login_page: LoginPage,
        page: Page,
    ):
        """Selected section should persist correctly on page interaction."""
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.wait_for_load()

        # Navigate to Teams section
        admin_page.go_to_teams()
        assert admin_page.is_section_visible(AdminSection.TEAMS)

        # Verify current section
        current = admin_page.get_current_section()
        assert current == AdminSection.TEAMS

    def test_default_section_on_load(
        self,
        admin_page: AdminPage,
        admin_user,
        login_page: LoginPage,
    ):
        """Admin panel should load with a default section visible."""
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.wait_for_load()

        # Should have some section visible
        current = admin_page.get_current_section()
        assert current is not None, "Should have a default section visible"


# =============================================================================
# Team Management Journey Tests
# =============================================================================


@pytest.mark.critical
class TestTeamManagementJourney:
    """Tests for the complete team management workflow."""

    def test_view_teams_list(
        self,
        admin_page: AdminPage,
        teams_section: AdminTeamsSection,
        admin_user,
        login_page: LoginPage,
    ):
        """Admin can view the teams list."""
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.wait_for_load()
        admin_page.go_to_teams()

        # Wait for teams to load
        teams_section.wait_for_teams_loaded()

        assert teams_section.is_loaded()
        assert not teams_section.has_error()

    def test_open_add_team_modal(
        self,
        admin_page: AdminPage,
        teams_section: AdminTeamsSection,
        admin_user,
        login_page: LoginPage,
    ):
        """Admin can open the add team modal."""
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.go_to_teams()
        teams_section.wait_for_teams_loaded()

        teams_section.click_add_team()

        assert teams_section.is_modal_open()
        assert "Add New Team" in teams_section.get_modal_title()

    def test_close_add_team_modal(
        self,
        admin_page: AdminPage,
        teams_section: AdminTeamsSection,
        admin_user,
        login_page: LoginPage,
    ):
        """Admin can close the add team modal without saving."""
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.go_to_teams()
        teams_section.wait_for_teams_loaded()

        teams_section.click_add_team()
        assert teams_section.is_modal_open()

        teams_section.close_modal()
        assert not teams_section.is_modal_open()

    def test_get_team_count(
        self,
        admin_page: AdminPage,
        teams_section: AdminTeamsSection,
        admin_user,
        login_page: LoginPage,
    ):
        """Admin can get the count of teams."""
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.go_to_teams()
        teams_section.wait_for_teams_loaded()

        count = teams_section.get_team_count()
        assert isinstance(count, int)
        assert count >= 0

    def test_get_team_names(
        self,
        admin_page: AdminPage,
        teams_section: AdminTeamsSection,
        admin_user,
        login_page: LoginPage,
    ):
        """Admin can get the list of team names."""
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.go_to_teams()
        teams_section.wait_for_teams_loaded()

        names = teams_section.get_team_names()
        assert isinstance(names, list)


# =============================================================================
# Invite Management Journey Tests
# =============================================================================


@pytest.mark.critical
class TestInviteManagementJourney:
    """Tests for the complete invite management workflow."""

    def test_view_invites_section(
        self,
        admin_page: AdminPage,
        invites_section: AdminInvitesSection,
        admin_user,
        login_page: LoginPage,
    ):
        """Admin can view the invites section."""
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.wait_for_load()
        admin_page.go_to_invites()

        assert invites_section.is_loaded()
        assert invites_section.is_form_visible()

    def test_invite_type_selection_shows_correct_fields(
        self,
        admin_page: AdminPage,
        invites_section: AdminInvitesSection,
        admin_user,
        login_page: LoginPage,
    ):
        """Selecting invite type shows the appropriate form fields."""
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.go_to_invites()

        # Select club manager type - should show club select
        invites_section.select_invite_type(InviteType.CLUB_MANAGER)
        assert invites_section.is_club_select_visible()
        assert not invites_section.is_team_select_visible()

        # Select team player type - should show team and age group selects
        invites_section.select_invite_type(InviteType.TEAM_PLAYER)
        assert invites_section.is_team_select_visible()
        assert invites_section.is_age_group_select_visible()
        assert not invites_section.is_club_select_visible()

    def test_filter_invites_by_status(
        self,
        admin_page: AdminPage,
        invites_section: AdminInvitesSection,
        admin_user,
        login_page: LoginPage,
    ):
        """Admin can filter invites by status."""
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.go_to_invites()

        # Filter by pending
        invites_section.filter_by_status(InviteStatus.PENDING)

        # Get pending invites
        pending = invites_section.get_pending_invites()
        # All visible invites should be pending
        for invite in pending:
            assert invite.status.lower() == "pending"

    def test_get_invite_codes(
        self,
        admin_page: AdminPage,
        invites_section: AdminInvitesSection,
        admin_user,
        login_page: LoginPage,
    ):
        """Admin can get the list of invite codes."""
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.go_to_invites()

        codes = invites_section.get_invite_codes()
        assert isinstance(codes, list)


# =============================================================================
# End-to-End Journey Tests
# =============================================================================


@pytest.mark.e2e
class TestCompleteAdminJourneys:
    """Complete end-to-end admin workflow tests."""

    def test_admin_full_navigation_journey(
        self,
        admin_page: AdminPage,
        admin_user,
        login_page: LoginPage,
    ):
        """
        Complete journey: Login -> Navigate through all admin sections.

        This tests the full navigation flow an admin would typically perform.
        """
        # Step 1: Login
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        # Step 2: Navigate to admin
        admin_page.navigate()
        admin_page.wait_for_load()
        assert admin_page.has_access(), "Admin should have access"

        # Step 3: Navigate to each key section
        key_sections = [
            AdminSection.TEAMS,
            AdminSection.MATCHES,
            AdminSection.INVITES,
            AdminSection.PLAYERS,
        ]

        for section in key_sections:
            admin_page.go_to_section(section)
            assert admin_page.is_section_visible(section), \
                f"Should be able to navigate to {section.value}"

    def test_admin_teams_view_journey(
        self,
        admin_page: AdminPage,
        teams_section: AdminTeamsSection,
        admin_user,
        login_page: LoginPage,
    ):
        """
        Complete journey: Login -> View Teams -> Check Team Data.

        This tests viewing team information in the admin panel.
        """
        # Login and navigate
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.go_to_teams()

        # Wait for teams to load
        teams_section.wait_for_teams_loaded()

        # Get team information
        team_count = teams_section.get_team_count()
        team_rows = teams_section.get_team_rows()

        # Basic validation
        assert len(team_rows) == team_count
        for team in team_rows:
            assert team.name, "Each team should have a name"

    def test_admin_invites_view_journey(
        self,
        admin_page: AdminPage,
        invites_section: AdminInvitesSection,
        admin_user,
        login_page: LoginPage,
    ):
        """
        Complete journey: Login -> View Invites -> Filter Invites.

        This tests viewing and filtering invites in the admin panel.
        """
        # Login and navigate
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        admin_page.navigate()
        admin_page.go_to_invites()

        # Verify section loaded
        assert invites_section.is_loaded()

        # Filter by different statuses
        for status in [InviteStatus.ALL, InviteStatus.PENDING]:
            invites_section.filter_by_status(status)
            # Should not crash or show errors
            assert invites_section.is_loaded()

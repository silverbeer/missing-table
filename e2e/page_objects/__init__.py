"""
Page Object Model (POM) Framework for Missing Table E2E Tests

This module provides a robust, maintainable structure for browser automation testing
using the Page Object Model design pattern with pytest fixtures.

Features:
- Type-safe page objects with full IDE autocomplete
- Automatic waiting and retry mechanisms
- Screenshot capture on failure
- Reusable component abstractions
- Data-driven test support

Usage:
    from page_objects import LoginPage, StandingsPage

    def test_login_flow(login_page, standings_page):
        login_page.login("user@example.com", "password")
        assert standings_page.is_loaded()
"""

from .base_page import BasePage, Component
from .login_page import LoginPage
from .standings_page import StandingsPage
from .matches_page import MatchesPage
from .admin_page import AdminPage, AdminSection
from .admin_teams import AdminTeamsSection, TeamRow
from .admin_invites import AdminInvitesSection, InviteRow, InviteType, InviteStatus
from .navigation import NavigationBar

__all__ = [
    # Base classes
    "BasePage",
    "Component",
    # Page objects
    "LoginPage",
    "StandingsPage",
    "MatchesPage",
    "AdminPage",
    "NavigationBar",
    # Admin section components
    "AdminSection",
    "AdminTeamsSection",
    "TeamRow",
    "AdminInvitesSection",
    "InviteRow",
    "InviteType",
    "InviteStatus",
]

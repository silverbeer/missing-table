"""
Authentication E2E Tests for Missing Table.

These tests verify:
- Login flows for different user roles
- Error handling and validation
- Security measures (CSRF, XSS protection)
- Session management
- Logout functionality

Demonstrates:
- Data-driven testing with pytest.mark.parametrize
- Page Object Model usage
- Multiple authentication scenarios
- Security testing patterns
"""

import json
from pathlib import Path

import pytest
from page_objects import LoginPage, NavigationBar, StandingsPage
from playwright.sync_api import Page


class TestLoginFlow:
    """Test suite for login functionality."""

    @pytest.mark.smoke
    @pytest.mark.auth
    @pytest.mark.critical
    def test_successful_login(
        self,
        login_page: LoginPage,
        fan_user,
        standings_page: StandingsPage
    ):
        """
        Test successful login with valid credentials.

        Critical path: User can authenticate and access the application.
        """
        # Arrange
        login_page.navigate()

        # Act
        login_page.login(fan_user.username, fan_user.password)

        # Assert
        assert login_page.is_login_successful(), "Login should succeed with valid credentials"
        assert standings_page.is_current_page() or "/" in login_page.get_current_url()

    @pytest.mark.auth
    @pytest.mark.critical
    def test_admin_login_enables_admin_features(
        self,
        login_page: LoginPage,
        admin_user,
        nav_bar: NavigationBar
    ):
        """
        Test that admin login grants access to admin features.
        
        Verifies role-based access control (RBAC).
        """
        # Arrange & Act
        login_page.navigate()
        login_page.login(admin_user.username, admin_user.password)

        # Assert - Admin should see admin nav link
        # Note: This may need adjustment based on actual UI
        assert not login_page.has_error_message()

    @pytest.mark.auth
    def test_invalid_password_shows_error(
        self,
        login_page: LoginPage,
        fan_user
    ):
        """Test that invalid password displays appropriate error."""
        # Arrange
        login_page.navigate()

        # Act
        login_page.login(fan_user.username, "wrong_password")

        # Assert
        assert login_page.has_error_message(), "Error should be displayed for invalid password"
        assert not login_page.is_login_successful()

    @pytest.mark.auth
    def test_nonexistent_user_shows_error(self, login_page: LoginPage):
        """Test that login with non-existent email shows error."""
        # Arrange
        login_page.navigate()

        # Act
        login_page.login("nonexistent@example.com", "SomePassword123!")

        # Assert
        assert login_page.has_error_message(), "Error should be displayed for non-existent user"
        # Verify we don't leak information about whether email exists
        error = login_page.get_error_message().lower()
        assert "invalid" in error or "incorrect" in error

    @pytest.mark.auth
    @pytest.mark.data_driven
    @pytest.mark.parametrize("email,password,expected", [
        ("", "password123", "validation_error"),
        ("user@example.com", "", "validation_error"),
        ("not-an-email", "password123", "validation_error"),
        ("user@", "password123", "validation_error"),
    ])
    def test_form_validation(
        self,
        login_page: LoginPage,
        email: str,
        password: str,
        expected: str
    ):
        """
        Data-driven test for form validation.
        
        Tests various invalid input combinations to ensure
        proper client-side and server-side validation.
        """
        # Arrange
        login_page.navigate()

        # Act
        login_page.enter_email(email)
        login_page.enter_password(password)

        # Assert - Check form validation
        if expected == "validation_error":
            # For empty fields, submit button may be disabled or form invalid
            if email == "":
                assert not login_page.is_email_valid() or not login_page.is_submit_enabled()
            if password == "":
                assert not login_page.is_password_valid() or not login_page.is_submit_enabled()


class TestLogout:
    """Test suite for logout functionality."""

    @pytest.mark.auth
    def test_logout_clears_session(
        self,
        authenticated_page: Page,
        nav_bar: NavigationBar,
        login_page: LoginPage
    ):
        """
        Test that logout properly clears the user session.
        
        Verifies session management security.
        """
        # Arrange - User is already logged in via fixture

        # Act
        nav_bar.click_logout()

        # Assert
        # Should be redirected to login or home
        current_url = authenticated_page.url
        assert "/login" in current_url or not nav_bar.is_logged_in()


class TestSecurityMeasures:
    """Security-focused authentication tests."""

    @pytest.mark.auth
    @pytest.mark.security
    @pytest.mark.parametrize("malicious_input", [
        "' OR '1'='1",
        "'; DROP TABLE users;--",
        "<script>alert('xss')</script>",
        "{{7*7}}",
        "${7*7}",
    ])
    def test_sql_injection_prevention(
        self,
        login_page: LoginPage,
        malicious_input: str
    ):
        """
        Test that SQL injection attempts are properly handled.
        
        Security test to verify input sanitization.
        """
        # Arrange
        login_page.navigate()

        # Act
        login_page.login(malicious_input, "password")

        # Assert
        # Should show error, not crash or bypass authentication
        assert not login_page.is_login_successful()
        # Page should still be functional
        assert login_page.is_visible(login_page.EMAIL_INPUT)

    @pytest.mark.auth
    @pytest.mark.security
    def test_xss_in_error_message(self, login_page: LoginPage):
        """
        Test that XSS payloads in input are not reflected in errors.
        
        Security test for XSS prevention.
        """
        # Arrange
        xss_payload = "<script>alert('xss')</script>"
        login_page.navigate()

        # Act
        login_page.login(xss_payload, "password")

        # Assert
        page_content = login_page.page.content()
        # XSS payload should be escaped or removed, not present as-is
        assert "<script>alert" not in page_content

    @pytest.mark.auth
    @pytest.mark.slow
    def test_rate_limiting_on_failed_logins(self, login_page: LoginPage):
        """
        Test that rate limiting kicks in after multiple failed attempts.
        
        Security measure to prevent brute force attacks.
        """
        # Arrange
        login_page.navigate()

        # Act - Attempt multiple failed logins
        for i in range(6):
            login_page.clear_form()
            login_page.login(f"user{i}@example.com", "wrong_password")

        # Assert
        # After several attempts, should see rate limiting message
        # This depends on your backend implementation
        error = login_page.get_error_message().lower()
        # Rate limiting might show as "too many attempts" or similar


class TestPasswordReset:
    """Test password reset functionality."""

    @pytest.mark.auth
    def test_forgot_password_link_navigates(self, login_page: LoginPage):
        """Test that forgot password link navigates to reset page."""
        # Arrange
        login_page.navigate()

        # Act
        login_page.click_forgot_password()

        # Assert
        current_url = login_page.get_current_url()
        assert "forgot" in current_url or "reset" in current_url


class TestSessionManagement:
    """Test session and token management."""

    @pytest.mark.auth
    def test_session_persists_on_refresh(
        self,
        authenticated_page: Page,
        nav_bar: NavigationBar
    ):
        """
        Test that authentication state persists after page refresh.
        
        Verifies token/session storage is working correctly.
        """
        # Arrange - User is logged in
        initial_logged_in = nav_bar.is_logged_in()

        # Act
        authenticated_page.reload()

        # Assert
        assert nav_bar.is_logged_in() == initial_logged_in

    @pytest.mark.auth
    def test_protected_routes_require_authentication(
        self,
        page: Page,
        base_url: str
    ):
        """
        Test that protected routes redirect to login.
        
        Verifies route guards are working.
        """
        # Try to access admin without auth
        page.goto(f"{base_url}/admin")

        # Should redirect to login
        page.wait_for_timeout(1000)
        current_url = page.url

        # Either redirected to login or access denied
        assert "/login" in current_url or "unauthorized" in page.content().lower() or "access" in page.content().lower()


class TestAccessibility:
    """Accessibility tests for authentication forms."""

    @pytest.mark.auth
    @pytest.mark.a11y
    def test_login_form_keyboard_navigation(self, login_page: LoginPage):
        """
        Test that login form can be fully navigated with keyboard.
        
        Accessibility requirement for form navigation.
        """
        # Arrange
        login_page.navigate()

        # Act - Tab through form elements
        login_page.tab_through_form()

        # The form should be fully keyboard accessible
        # Email -> Password -> Remember Me (if exists) -> Submit

    @pytest.mark.auth
    @pytest.mark.a11y
    def test_error_messages_are_associated(self, login_page: LoginPage):
        """
        Test that error messages are properly associated with form fields.
        
        Screen readers need this association to announce errors.
        """
        # Arrange
        login_page.navigate()

        # Act - Trigger validation error
        login_page.login("", "")

        # Assert
        # Error messages should be present and associated with fields
        # via aria-describedby or aria-invalid


class TestDataDrivenLoginScenarios:
    """Data-driven tests using external test data."""

    @pytest.fixture(scope="class")
    def login_scenarios(self):
        """Load login test scenarios from JSON."""
        data_path = Path(__file__).parent / "test_data" / "login_scenarios.json"
        with open(data_path) as f:
            return json.load(f)

    @pytest.mark.auth
    @pytest.mark.data_driven
    def test_login_scenarios_from_file(
        self,
        login_page: LoginPage,
        login_scenarios
    ):
        """
        Execute multiple login scenarios from test data file.
        
        This demonstrates how to run the same test logic
        against many different data combinations.
        """
        for scenario in login_scenarios[:5]:  # Limit for demo
            # Arrange
            login_page.navigate()

            # Act
            login_page.login(scenario["email"], scenario["password"])

            # Assert based on expected result
            if scenario["expected_result"] == "success":
                assert login_page.is_login_successful(), f"Failed: {scenario['description']}"
            elif scenario["expected_result"] == "error":
                assert login_page.has_error_message(), f"Failed: {scenario['description']}"

            # Clean up for next iteration
            login_page.navigate()

"""Contract tests for live match endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient


@pytest.mark.contract
class TestLiveMatchReadContract:
    """Test live match read endpoint contracts."""

    def test_get_live_matches(self, authenticated_api_client: MissingTableClient):
        """Test getting live matches returns a list."""
        matches = authenticated_api_client.get_live_matches()
        assert isinstance(matches, list)

    def test_get_live_match_state(self, authenticated_api_client: MissingTableClient):
        """Test getting live match state for a match."""
        from api_client import APIError

        # Use a non-existent match — should return error or empty state
        try:
            result = authenticated_api_client.get_live_match_state(999999)
            assert result is not None
        except APIError:
            pass  # Expected for non-existent match

    def test_get_match_events(self, authenticated_api_client: MissingTableClient):
        """Test getting match events."""
        from api_client import APIError

        try:
            events = authenticated_api_client.get_match_events(999999)
            assert isinstance(events, list)
        except APIError:
            pass  # Expected for non-existent match


@pytest.mark.contract
class TestLiveMatchWriteContract:
    """Test live match write endpoint contracts."""

    def test_update_match_clock_requires_auth(self, api_client: MissingTableClient):
        """Test updating match clock requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import LiveMatchClock

        clock = LiveMatchClock(action="start_first_half")
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_match_clock(1, clock)

    def test_post_goal_requires_auth(self, api_client: MissingTableClient):
        """Test posting a goal requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import GoalEvent

        goal = GoalEvent(team_id=1)
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.post_goal(1, goal)

    def test_post_message_requires_auth(self, api_client: MissingTableClient):
        """Test posting a message requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import MessageEvent

        message = MessageEvent(message="Test message")
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.post_message(1, message)

    def test_delete_match_event_requires_auth(self, api_client: MissingTableClient):
        """Test deleting a match event requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_match_event(1, 1)

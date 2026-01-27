"""Contract tests for match submission and task status endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient


@pytest.mark.contract
class TestMatchSubmissionContract:
    """Test match submission endpoint contracts."""

    def test_submit_match_requires_auth(self, api_client: MissingTableClient):
        """Test submitting a match requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import MatchSubmissionData

        submission = MatchSubmissionData(
            match_date="2026-01-01",
            home_team="Team A",
            away_team="Team B",
            season="2025-26",
            home_score=1,
            away_score=0,
        )
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.submit_match_async(submission)

    def test_get_task_status_requires_auth(self, api_client: MissingTableClient):
        """Test getting task status requires authentication."""
        from api_client import APIError, AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError, APIError)):
            api_client.get_task_status("fake-task-id")

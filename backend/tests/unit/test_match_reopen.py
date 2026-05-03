"""Unit tests for match reopen flow (accidental end_match recovery)."""

from unittest.mock import MagicMock, patch

import pytest


def _make_match_dao():
    """Build a MatchDAO with mocked Supabase client."""
    from dao.match_dao import MatchDAO

    dao = object.__new__(MatchDAO)
    dao.connection_holder = MagicMock()
    dao.client = MagicMock()
    return dao


@pytest.mark.unit
class TestReopenMatchDAO:
    """Tests for MatchDAO.reopen_match()."""

    def test_returns_none_when_match_not_found(self):
        dao = _make_match_dao()

        mock_table = MagicMock()
        dao.client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.single.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=None)

        result = dao.reopen_match(999)
        assert result is None

    def test_rejects_match_not_completed(self):
        dao = _make_match_dao()

        mock_table = MagicMock()
        dao.client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.single.return_value = mock_table
        mock_table.execute.return_value = MagicMock(
            data={"match_status": "live", "match_end_time": None, "second_half_start": "2026-05-03T15:00:00Z"}
        )

        result = dao.reopen_match(123)
        assert result is None
        # No update issued — only the select call should have been made
        mock_table.update.assert_not_called()

    def test_success_clears_end_time_and_sets_status_live(self):
        dao = _make_match_dao()

        select_chain = MagicMock()
        select_chain.select.return_value = select_chain
        select_chain.eq.return_value = select_chain
        select_chain.single.return_value = select_chain
        select_chain.execute.return_value = MagicMock(
            data={
                "match_status": "completed",
                "match_end_time": "2026-05-03T16:30:00Z",
                "second_half_start": "2026-05-03T15:45:00Z",
            }
        )

        update_chain = MagicMock()
        update_chain.update.return_value = update_chain
        update_chain.eq.return_value = update_chain
        update_chain.execute.return_value = MagicMock(data=[{"id": 123}])

        # First .table() call -> select_chain (status check)
        # Second .table() call -> update_chain (write)
        dao.client.table.side_effect = [select_chain, update_chain]

        # Stub get_live_match_state to return a sentinel
        sentinel_state = {"match_id": 123, "match_status": "live", "match_end_time": None}
        with patch.object(dao, "get_live_match_state", return_value=sentinel_state) as mock_state:
            result = dao.reopen_match(123, updated_by="user-uuid-1")

        assert result is sentinel_state
        mock_state.assert_called_once_with(123)

        # Verify update payload
        update_chain.update.assert_called_once()
        update_payload = update_chain.update.call_args.args[0]
        assert update_payload["match_end_time"] is None
        assert update_payload["match_status"] == "live"
        assert update_payload["updated_by"] == "user-uuid-1"

    def test_handles_db_exception(self):
        dao = _make_match_dao()
        dao.client.table.side_effect = Exception("connection lost")

        result = dao.reopen_match(123)
        assert result is None


@pytest.mark.unit
class TestReopenMatchEndpoint:
    """Tests for POST /api/matches/{id}/live/reopen."""

    def _override_auth(self, app, *, match_management=True, can_edit=True):
        """Override FastAPI auth dependencies for endpoint tests."""
        from auth import require_match_management_permission

        user = {
            "user_id": "test-user-id",
            "id": "test-user-id",
            "username": "tester",
            "role": "admin",
        }

        if match_management:
            app.dependency_overrides[require_match_management_permission] = lambda: user

        return user

    def test_returns_404_when_match_missing(self):
        from fastapi.testclient import TestClient

        from app import app

        self._override_auth(app)

        with patch("app.match_dao") as mock_dao:
            mock_dao.get_match_by_id.return_value = None

            try:
                client = TestClient(app)
                response = client.post("/api/matches/999/live/reopen")
                assert response.status_code == 404
            finally:
                app.dependency_overrides.clear()

    def test_returns_400_when_match_not_completed(self):
        from fastapi.testclient import TestClient

        from app import app

        self._override_auth(app)

        with (
            patch("app.match_dao") as mock_dao,
            patch("app.auth_manager") as mock_auth,
        ):
            mock_dao.get_match_by_id.return_value = {
                "id": 123,
                "home_team_id": 1,
                "away_team_id": 2,
                "match_status": "live",
            }
            mock_auth.can_edit_match.return_value = True

            try:
                client = TestClient(app)
                response = client.post("/api/matches/123/live/reopen")
                assert response.status_code == 400
                assert "completed" in response.json()["detail"].lower()
            finally:
                app.dependency_overrides.clear()

    def test_returns_403_when_user_cannot_edit(self):
        from fastapi.testclient import TestClient

        from app import app

        self._override_auth(app)

        with (
            patch("app.match_dao") as mock_dao,
            patch("app.auth_manager") as mock_auth,
        ):
            mock_dao.get_match_by_id.return_value = {
                "id": 123,
                "home_team_id": 1,
                "away_team_id": 2,
                "match_status": "completed",
            }
            mock_auth.can_edit_match.return_value = False

            try:
                client = TestClient(app)
                response = client.post("/api/matches/123/live/reopen")
                assert response.status_code == 403
            finally:
                app.dependency_overrides.clear()

    def test_success_calls_dao_and_writes_audit_event(self):
        from fastapi.testclient import TestClient

        from app import app

        self._override_auth(app)

        reopened_state = {
            "match_id": 123,
            "match_status": "live",
            "match_end_time": None,
            "home_score": 2,
            "away_score": 1,
        }

        with (
            patch("app.match_dao") as mock_dao,
            patch("app.match_event_dao") as mock_event_dao,
            patch("app.auth_manager") as mock_auth,
            patch("dao.base_dao.clear_cache") as mock_clear_cache,
        ):
            mock_dao.get_match_by_id.return_value = {
                "id": 123,
                "home_team_id": 1,
                "away_team_id": 2,
                "match_status": "completed",
            }
            mock_auth.can_edit_match.return_value = True
            mock_dao.reopen_match.return_value = reopened_state

            try:
                client = TestClient(app)
                response = client.post("/api/matches/123/live/reopen")
                assert response.status_code == 200
                assert response.json() == reopened_state

                mock_dao.reopen_match.assert_called_once_with(123, updated_by="test-user-id")

                # Audit event written
                mock_event_dao.create_event.assert_called_once()
                kwargs = mock_event_dao.create_event.call_args.kwargs
                assert kwargs["match_id"] == 123
                assert kwargs["event_type"] == "status_change"
                assert kwargs["message"] == "Match reopened"
                assert kwargs["created_by"] == "test-user-id"

                # Stats cache cleared
                mock_clear_cache.assert_called_once_with("mt:dao:stats:*")
            finally:
                app.dependency_overrides.clear()

    def test_returns_500_when_dao_returns_none(self):
        from fastapi.testclient import TestClient

        from app import app

        self._override_auth(app)

        with (
            patch("app.match_dao") as mock_dao,
            patch("app.auth_manager") as mock_auth,
        ):
            mock_dao.get_match_by_id.return_value = {
                "id": 123,
                "home_team_id": 1,
                "away_team_id": 2,
                "match_status": "completed",
            }
            mock_auth.can_edit_match.return_value = True
            mock_dao.reopen_match.return_value = None

            try:
                client = TestClient(app)
                response = client.post("/api/matches/123/live/reopen")
                assert response.status_code == 500
            finally:
                app.dependency_overrides.clear()

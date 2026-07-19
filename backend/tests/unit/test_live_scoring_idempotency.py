"""Unit tests for offline-sync live scoring: idempotent replays, assists,
live substitutions, and clock/minute overrides (Android app support)."""

from unittest.mock import patch

import pytest

CLIENT_EVENT_ID = "11111111-2222-3333-4444-555555555555"

ROSTER = {
    10: {"id": 10, "team_id": 1, "jersey_number": 9, "display_name": "Scorer Nine"},
    11: {"id": 11, "team_id": 1, "jersey_number": 8, "display_name": "Assister Eight"},
    12: {"id": 12, "team_id": 1, "jersey_number": 14, "display_name": "Sub In Fourteen"},
    13: {"id": 13, "team_id": 1, "jersey_number": 6, "display_name": "Sub Out Six"},
    20: {"id": 20, "team_id": 2, "jersey_number": 7, "display_name": "Opponent Seven"},
}


def _live_match(**overrides):
    match = {
        "id": 123,
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_name": "Home FC",
        "away_team_name": "Away FC",
        "home_score": 1,
        "away_score": 0,
        "match_status": "live",
        "kickoff_time": "2026-07-19T14:00:00+00:00",
        "halftime_start": None,
        "second_half_start": None,
        "match_end_time": None,
        "half_duration": 45,
    }
    match.update(overrides)
    return match


def _override_auth(app):
    from auth import require_match_management_permission

    user = {
        "user_id": "test-user-id",
        "id": "test-user-id",
        "username": "tester",
        "role": "admin",
    }
    app.dependency_overrides[require_match_management_permission] = lambda: user
    return user


@pytest.mark.unit
class TestGoalIdempotency:
    """POST /api/matches/{id}/live/goal with client_event_id."""

    def test_replay_returns_state_without_side_effects(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao") as mock_event_dao,
            patch("app.player_stats_dao") as mock_stats_dao,
            patch("app.roster_dao") as mock_roster_dao,
            patch("app.auth_manager") as mock_auth,
            patch("app.notify_event_task"),
        ):
            mock_match_dao.get_match_by_id.return_value = _live_match()
            mock_match_dao.get_live_match_state.return_value = {"match_id": 123, "home_score": 2}
            mock_auth.can_edit_match.return_value = True
            mock_roster_dao.get_player_by_id.side_effect = lambda pid: ROSTER.get(pid)
            # Event already exists for this client_event_id -> replay
            mock_event_dao.get_event_by_client_id.return_value = {"id": 555, "event_type": "goal"}

            try:
                client = TestClient(app)
                response = client.post(
                    "/api/matches/123/live/goal",
                    json={"team_id": 1, "player_id": 10, "client_event_id": CLIENT_EVENT_ID},
                )
                assert response.status_code == 200
                mock_event_dao.create_event.assert_not_called()
                mock_match_dao.update_match_score.assert_not_called()
                mock_stats_dao.increment_goals.assert_not_called()
                mock_stats_dao.increment_assists.assert_not_called()
            finally:
                app.dependency_overrides.clear()

    def test_fresh_goal_creates_event_then_score_and_stats(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao") as mock_event_dao,
            patch("app.player_stats_dao") as mock_stats_dao,
            patch("app.roster_dao") as mock_roster_dao,
            patch("app.auth_manager") as mock_auth,
            patch("app.notify_event_task"),
        ):
            mock_match_dao.get_match_by_id.return_value = _live_match()
            mock_match_dao.update_match_score.return_value = {"match_id": 123, "home_score": 2}
            mock_auth.can_edit_match.return_value = True
            mock_roster_dao.get_player_by_id.side_effect = lambda pid: ROSTER.get(pid)
            mock_event_dao.get_event_by_client_id.return_value = None
            mock_event_dao.create_event.return_value = {"id": 556, "event_type": "goal"}

            try:
                client = TestClient(app)
                response = client.post(
                    "/api/matches/123/live/goal",
                    json={
                        "team_id": 1,
                        "player_id": 10,
                        "assist_player_id": 11,
                        "client_event_id": CLIENT_EVENT_ID,
                    },
                )
                assert response.status_code == 200

                # Event insert carries the idempotency key + assist fields
                create_kwargs = mock_event_dao.create_event.call_args.kwargs
                assert create_kwargs["client_event_id"] == CLIENT_EVENT_ID
                assert create_kwargs["assist_player_id"] == 11
                assert create_kwargs["assist_player_name"] == "Assister Eight"
                assert "(assist: Assister Eight)" in create_kwargs["message"]

                # Score incremented exactly once, stats for scorer + assister
                mock_match_dao.update_match_score.assert_called_once_with(
                    123, 2, 0, updated_by="test-user-id"
                )
                mock_stats_dao.increment_goals.assert_called_once_with(10, 123)
                mock_stats_dao.increment_assists.assert_called_once_with(11, 123)
            finally:
                app.dependency_overrides.clear()

    def test_insert_race_falls_back_to_replay(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao") as mock_event_dao,
            patch("app.player_stats_dao") as mock_stats_dao,
            patch("app.roster_dao") as mock_roster_dao,
            patch("app.auth_manager") as mock_auth,
            patch("app.notify_event_task"),
        ):
            mock_match_dao.get_match_by_id.return_value = _live_match()
            mock_match_dao.get_live_match_state.return_value = {"match_id": 123, "home_score": 2}
            mock_auth.can_edit_match.return_value = True
            mock_roster_dao.get_player_by_id.side_effect = lambda pid: ROSTER.get(pid)
            # Pre-check misses, insert fails (unique violation), re-check hits
            mock_event_dao.get_event_by_client_id.side_effect = [None, {"id": 555}]
            mock_event_dao.create_event.return_value = None

            try:
                client = TestClient(app)
                response = client.post(
                    "/api/matches/123/live/goal",
                    json={"team_id": 1, "player_id": 10, "client_event_id": CLIENT_EVENT_ID},
                )
                assert response.status_code == 200
                mock_match_dao.update_match_score.assert_not_called()
                mock_stats_dao.increment_goals.assert_not_called()
            finally:
                app.dependency_overrides.clear()

    def test_assist_cannot_be_scorer(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao"),
            patch("app.player_stats_dao"),
            patch("app.roster_dao") as mock_roster_dao,
            patch("app.auth_manager") as mock_auth,
            patch("app.notify_event_task"),
        ):
            mock_match_dao.get_match_by_id.return_value = _live_match()
            mock_auth.can_edit_match.return_value = True
            mock_roster_dao.get_player_by_id.side_effect = lambda pid: ROSTER.get(pid)

            try:
                client = TestClient(app)
                response = client.post(
                    "/api/matches/123/live/goal",
                    json={"team_id": 1, "player_id": 10, "assist_player_id": 10},
                )
                assert response.status_code == 400
                assert "scorer" in response.json()["detail"].lower()
            finally:
                app.dependency_overrides.clear()

    def test_assist_must_be_on_scoring_team(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao"),
            patch("app.player_stats_dao"),
            patch("app.roster_dao") as mock_roster_dao,
            patch("app.auth_manager") as mock_auth,
            patch("app.notify_event_task"),
        ):
            mock_match_dao.get_match_by_id.return_value = _live_match()
            mock_auth.can_edit_match.return_value = True
            mock_roster_dao.get_player_by_id.side_effect = lambda pid: ROSTER.get(pid)

            try:
                client = TestClient(app)
                response = client.post(
                    "/api/matches/123/live/goal",
                    json={"team_id": 1, "player_id": 10, "assist_player_id": 20},
                )
                assert response.status_code == 400
                assert "team" in response.json()["detail"].lower()
            finally:
                app.dependency_overrides.clear()

    def test_client_minute_override_is_stored(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao") as mock_event_dao,
            patch("app.player_stats_dao"),
            patch("app.roster_dao") as mock_roster_dao,
            patch("app.auth_manager") as mock_auth,
            patch("app.notify_event_task"),
        ):
            mock_match_dao.get_match_by_id.return_value = _live_match()
            mock_match_dao.update_match_score.return_value = {"match_id": 123}
            mock_auth.can_edit_match.return_value = True
            mock_roster_dao.get_player_by_id.side_effect = lambda pid: ROSTER.get(pid)
            mock_event_dao.get_event_by_client_id.return_value = None
            mock_event_dao.create_event.return_value = {"id": 557}

            try:
                client = TestClient(app)
                response = client.post(
                    "/api/matches/123/live/goal",
                    json={"team_id": 1, "player_id": 10, "match_minute": 33},
                )
                assert response.status_code == 200
                create_kwargs = mock_event_dao.create_event.call_args.kwargs
                assert create_kwargs["match_minute"] == 33
            finally:
                app.dependency_overrides.clear()


@pytest.mark.unit
class TestLiveSubstitution:
    """POST /api/matches/{id}/live/substitution."""

    def _post(self, client, json_body):
        return client.post("/api/matches/123/live/substitution", json=json_body)

    def test_happy_path_creates_substitution_event(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao") as mock_event_dao,
            patch("app.roster_dao") as mock_roster_dao,
            patch("app.auth_manager") as mock_auth,
        ):
            mock_match_dao.get_match_by_id.return_value = _live_match()
            mock_auth.can_edit_match.return_value = True
            mock_roster_dao.get_player_by_id.side_effect = lambda pid: ROSTER.get(pid)
            mock_event_dao.get_event_by_client_id.return_value = None
            created = {"id": 600, "event_type": "substitution"}
            mock_event_dao.create_event.return_value = created

            try:
                client = TestClient(app)
                response = self._post(
                    client,
                    {
                        "team_id": 1,
                        "player_in_id": 12,
                        "player_out_id": 13,
                        "client_event_id": CLIENT_EVENT_ID,
                    },
                )
                assert response.status_code == 200
                assert response.json()["id"] == 600

                create_kwargs = mock_event_dao.create_event.call_args.kwargs
                assert create_kwargs["event_type"] == "substitution"
                assert create_kwargs["player_id"] == 12
                assert create_kwargs["player_out_id"] == 13
                assert create_kwargs["client_event_id"] == CLIENT_EVENT_ID
                assert "Sub In Fourteen on for Sub Out Six" in create_kwargs["message"]
            finally:
                app.dependency_overrides.clear()

    def test_rejects_player_on_wrong_team(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao"),
            patch("app.roster_dao") as mock_roster_dao,
            patch("app.auth_manager") as mock_auth,
        ):
            mock_match_dao.get_match_by_id.return_value = _live_match()
            mock_auth.can_edit_match.return_value = True
            mock_roster_dao.get_player_by_id.side_effect = lambda pid: ROSTER.get(pid)

            try:
                client = TestClient(app)
                response = self._post(client, {"team_id": 1, "player_in_id": 20, "player_out_id": 13})
                assert response.status_code == 400
                assert "team" in response.json()["detail"].lower()
            finally:
                app.dependency_overrides.clear()

    def test_rejects_same_player_in_and_out(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao"),
            patch("app.roster_dao") as mock_roster_dao,
            patch("app.auth_manager") as mock_auth,
        ):
            mock_match_dao.get_match_by_id.return_value = _live_match()
            mock_auth.can_edit_match.return_value = True
            mock_roster_dao.get_player_by_id.side_effect = lambda pid: ROSTER.get(pid)

            try:
                client = TestClient(app)
                response = self._post(client, {"team_id": 1, "player_in_id": 12, "player_out_id": 12})
                assert response.status_code == 400
            finally:
                app.dependency_overrides.clear()

    def test_replay_returns_stored_event_without_insert(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao") as mock_event_dao,
            patch("app.roster_dao") as mock_roster_dao,
            patch("app.auth_manager") as mock_auth,
        ):
            mock_match_dao.get_match_by_id.return_value = _live_match()
            mock_auth.can_edit_match.return_value = True
            mock_roster_dao.get_player_by_id.side_effect = lambda pid: ROSTER.get(pid)
            stored = {"id": 600, "event_type": "substitution"}
            mock_event_dao.get_event_by_client_id.return_value = stored

            try:
                client = TestClient(app)
                response = self._post(
                    client,
                    {
                        "team_id": 1,
                        "player_in_id": 12,
                        "player_out_id": 13,
                        "client_event_id": CLIENT_EVENT_ID,
                    },
                )
                assert response.status_code == 200
                assert response.json()["id"] == 600
                mock_event_dao.create_event.assert_not_called()
            finally:
                app.dependency_overrides.clear()


@pytest.mark.unit
class TestClockIdempotency:
    """POST /api/matches/{id}/live/clock replays and occurred_at overrides."""

    def test_replayed_start_first_half_is_noop(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao") as mock_event_dao,
            patch("app.auth_manager") as mock_auth,
            patch("app.notify_event_task"),
        ):
            # kickoff_time already set -> replay must not touch the clock
            mock_match_dao.get_match_by_id.return_value = _live_match()
            mock_match_dao.get_live_match_state.return_value = {"match_id": 123, "match_status": "live"}
            mock_auth.can_edit_match.return_value = True

            try:
                client = TestClient(app)
                response = client.post(
                    "/api/matches/123/live/clock",
                    json={"action": "start_first_half", "half_duration": 40},
                )
                assert response.status_code == 200
                mock_match_dao.update_match_clock.assert_not_called()
                mock_event_dao.create_event.assert_not_called()
            finally:
                app.dependency_overrides.clear()

    def test_occurred_at_passed_to_dao(self):
        from datetime import UTC, datetime, timedelta

        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        occurred = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao"),
            patch("app.auth_manager") as mock_auth,
            patch("app.notify_event_task"),
        ):
            mock_match_dao.get_match_by_id.return_value = _live_match(kickoff_time=None, match_status="scheduled")
            mock_match_dao.update_match_clock.return_value = {"match_id": 123, "match_status": "live"}
            mock_auth.can_edit_match.return_value = True

            try:
                client = TestClient(app)
                response = client.post(
                    "/api/matches/123/live/clock",
                    json={"action": "start_first_half", "half_duration": 40, "occurred_at": occurred},
                )
                assert response.status_code == 200
                clock_kwargs = mock_match_dao.update_match_clock.call_args.kwargs
                assert clock_kwargs["occurred_at"] is not None
            finally:
                app.dependency_overrides.clear()

    def test_occurred_at_in_future_rejected(self):
        from datetime import UTC, datetime, timedelta

        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        occurred = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao"),
            patch("app.auth_manager") as mock_auth,
            patch("app.notify_event_task"),
        ):
            mock_match_dao.get_match_by_id.return_value = _live_match(kickoff_time=None, match_status="scheduled")
            mock_auth.can_edit_match.return_value = True

            try:
                client = TestClient(app)
                response = client.post(
                    "/api/matches/123/live/clock",
                    json={"action": "start_first_half", "occurred_at": occurred},
                )
                assert response.status_code == 400
                mock_match_dao.update_match_clock.assert_not_called()
            finally:
                app.dependency_overrides.clear()


@pytest.mark.unit
class TestAssistStatsOnDelete:
    """DELETE /api/matches/{id}/live/events/{event_id} adjusts assist stats."""

    def test_deleting_goal_with_assist_decrements_both(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao") as mock_event_dao,
            patch("app.player_stats_dao") as mock_stats_dao,
            patch("app.auth_manager") as mock_auth,
        ):
            mock_match_dao.get_match_by_id.return_value = _live_match(home_score=2)
            mock_auth.can_edit_match.return_value = True
            mock_event_dao.get_event_by_id.return_value = {
                "id": 556,
                "match_id": 123,
                "event_type": "goal",
                "team_id": 1,
                "player_id": 10,
                "assist_player_id": 11,
            }
            mock_event_dao.soft_delete_event.return_value = True

            try:
                client = TestClient(app)
                response = client.delete("/api/matches/123/live/events/556")
                assert response.status_code == 200
                mock_match_dao.update_match_score.assert_called_once_with(
                    123, 1, 0, updated_by="test-user-id"
                )
                mock_stats_dao.decrement_goals.assert_called_once_with(10, 123)
                mock_stats_dao.decrement_assists.assert_called_once_with(11, 123)
            finally:
                app.dependency_overrides.clear()

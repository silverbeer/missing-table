"""SB-671: starters are recorded at kickoff, not when the lineup is saved.

A lineup is a plan. Recording appearances when it was saved meant a squad's
games-played rose the moment Sunday's lineup was entered on Friday, and a lineup
entered for a match that was never played counted forever.
"""

from unittest.mock import patch

import pytest

LINEUPS = {
    "home": {"team_id": 1, "positions": [{"player_id": 10}, {"player_id": 11}]},
    "away": {"team_id": 2, "positions": [{"player_id": 20}]},
}


def _match(**overrides):
    match = {
        "id": 123,
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_name": "Home FC",
        "away_team_name": "Away FC",
        "match_status": "scheduled",
        "kickoff_time": None,
        "halftime_start": None,
        "second_half_start": None,
        "match_end_time": None,
        "half_duration": 45,
    }
    match.update(overrides)
    return match


def _override_auth(app):
    from auth import require_match_management_permission

    app.dependency_overrides[require_match_management_permission] = lambda: {
        "user_id": "test-user-id",
        "id": "test-user-id",
        "username": "tester",
        "role": "admin",
    }


def _clock(action, match=None):
    from fastapi.testclient import TestClient

    from app import app

    _override_auth(app)

    with (
        patch("app.match_dao") as mock_match_dao,
        patch("app.match_event_dao"),
        patch("app.player_stats_dao") as mock_stats_dao,
        patch("app.lineup_dao") as mock_lineup_dao,
        patch("app.auth_manager") as mock_auth,
        patch("app.notify_event_task"),
    ):
        mock_match_dao.get_match_by_id.return_value = match or _match()
        mock_match_dao.update_match_clock.return_value = {"match_id": 123}
        mock_match_dao.get_live_match_state.return_value = {"match_id": 123}
        mock_auth.can_edit_match.return_value = True
        mock_lineup_dao.get_lineups_for_match.return_value = LINEUPS

        try:
            client = TestClient(app)
            response = client.post("/api/matches/123/live/clock", json={"action": action})
        finally:
            app.dependency_overrides.clear()

    return response, mock_stats_dao


@pytest.mark.unit
class TestKickoffRecordsStarters:
    def test_kickoff_marks_both_lineups_as_started(self):
        response, mock_stats_dao = _clock("start_first_half")

        assert response.status_code == 200
        started = {c.args[0] for c in mock_stats_dao.set_started.call_args_list}
        assert started == {10, 11, 20}
        for call in mock_stats_dao.set_started.call_args_list:
            assert call.kwargs["started"] is True

    def test_other_clock_actions_record_nothing(self):
        """Only kickoff makes a starter a starter."""
        for action in ("start_halftime", "start_second_half", "end_match"):
            _, mock_stats_dao = _clock(action)
            mock_stats_dao.set_started.assert_not_called()

    def test_a_replayed_kickoff_does_not_double_write(self):
        """The idempotency guard returns before the appearance write."""
        _, mock_stats_dao = _clock(
            "start_first_half", match=_match(kickoff_time="2026-08-17T14:00:00+00:00")
        )

        mock_stats_dao.set_started.assert_not_called()

    def test_a_stats_failure_does_not_stop_the_match(self):
        """The scorer is pitch-side and cannot debug this."""
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao"),
            patch("app.player_stats_dao") as mock_stats_dao,
            patch("app.lineup_dao") as mock_lineup_dao,
            patch("app.auth_manager") as mock_auth,
            patch("app.notify_event_task"),
        ):
            mock_match_dao.get_match_by_id.return_value = _match()
            mock_match_dao.update_match_clock.return_value = {"match_id": 123}
            mock_auth.can_edit_match.return_value = True
            mock_lineup_dao.get_lineups_for_match.return_value = LINEUPS
            mock_stats_dao.set_started.side_effect = RuntimeError("db down")

            try:
                client = TestClient(app)
                response = client.post("/api/matches/123/live/clock", json={"action": "start_first_half"})
                assert response.status_code == 200
            finally:
                app.dependency_overrides.clear()

    def test_kickoff_without_a_lineup_is_fine(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao"),
            patch("app.player_stats_dao") as mock_stats_dao,
            patch("app.lineup_dao") as mock_lineup_dao,
            patch("app.auth_manager") as mock_auth,
            patch("app.notify_event_task"),
        ):
            mock_match_dao.get_match_by_id.return_value = _match()
            mock_match_dao.update_match_clock.return_value = {"match_id": 123}
            mock_auth.can_edit_match.return_value = True
            mock_lineup_dao.get_lineups_for_match.return_value = {"home": None, "away": None}

            try:
                client = TestClient(app)
                response = client.post("/api/matches/123/live/clock", json={"action": "start_first_half"})
                assert response.status_code == 200
                mock_stats_dao.set_started.assert_not_called()
            finally:
                app.dependency_overrides.clear()

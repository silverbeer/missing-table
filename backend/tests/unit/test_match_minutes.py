"""SB-1227: minutes played derived from the live-scoring timeline."""

from unittest.mock import patch

import pytest

from match_minutes import compute_minutes_played


def sub(minute, on, off, created_at=""):
    return {
        "event_type": "substitution",
        "match_minute": minute,
        "player_id": on,
        "player_out_id": off,
        "created_at": created_at,
    }


def red(minute, player):
    return {"event_type": "red_card", "match_minute": minute, "player_id": player}


@pytest.mark.unit
class TestComputeMinutesPlayed:
    def test_starters_without_subs_play_the_full_match(self):
        assert compute_minutes_played([1, 2], [], 45) == {1: 90, 2: 90}

    def test_substitution_splits_the_minutes(self):
        """Match 3888: Bobby W on for Josh S at 33', Oli J on for Sebby M at 45'."""
        minutes = compute_minutes_played([1, 2, 3], [sub(33, 10, 1), sub(45, 11, 2)], 45)
        assert minutes == {1: 33, 2: 45, 3: 90, 10: 57, 11: 45}

    def test_half_duration_sets_the_length(self):
        assert compute_minutes_played([1], [sub(20, 2, 1)], 35) == {1: 20, 2: 50}

    def test_a_player_can_go_off_and_come_back_on(self):
        minutes = compute_minutes_played([1], [sub(30, 2, 1), sub(60, 1, 2)], 45)
        assert minutes == {1: 60, 2: 30}

    def test_red_card_ends_a_players_minutes(self):
        assert compute_minutes_played([1, 2], [red(70, 1)], 45) == {1: 70, 2: 90}

    def test_sub_at_the_final_whistle_appeared_for_zero(self):
        """Appeared, so present with 0 — not absent."""
        assert compute_minutes_played([1], [sub(90, 2, 1)], 45) == {1: 90, 2: 0}

    def test_stoppage_time_is_ignored(self):
        minutes = compute_minutes_played([1], [sub(95, 2, 1)], 45)
        assert minutes == {1: 90, 2: 0}

    def test_events_are_applied_in_minute_order(self):
        events = [sub(60, 3, 2), sub(30, 2, 1)]
        assert compute_minutes_played([1], events, 45) == {1: 30, 2: 30, 3: 30}

    def test_ties_within_a_minute_keep_recorded_order(self):
        events = [sub(30, 3, 2, "2026-10-03T14:00:02"), sub(30, 2, 1, "2026-10-03T14:00:01")]
        assert compute_minutes_played([1], events, 45) == {1: 30, 2: 0, 3: 60}

    def test_events_without_a_minute_and_other_types_are_skipped(self):
        events = [
            sub(None, 2, 1),
            {"event_type": "goal", "match_minute": 10, "player_id": 1},
            {"event_type": "status_change", "match_minute": None},
        ]
        assert compute_minutes_played([1], events, 45) == {1: 90}

    def test_sub_for_a_player_not_on_the_pitch_still_brings_the_sub_on(self):
        """Unrecorded earlier sub — credit who we know came on, invent nothing."""
        assert compute_minutes_played([1], [sub(50, 3, 99)], 45) == {1: 90, 3: 40}

    def test_no_starters_and_no_subs_is_empty(self):
        """A team nobody lined up has no minutes, not zero minutes."""
        assert compute_minutes_played([], [], 45) == {}


def _override_auth(app):
    from auth import require_match_management_permission

    app.dependency_overrides[require_match_management_permission] = lambda: {
        "user_id": "u",
        "id": "u",
        "username": "tester",
        "role": "admin",
    }


LIVE_MATCH = {
    "id": 123,
    "home_team_id": 1,
    "away_team_id": 2,
    "home_team_name": "Home FC",
    "away_team_name": "Away FC",
    "match_status": "live",
    "kickoff_time": "2026-10-03T13:00:00+00:00",
    "halftime_start": "2026-10-03T13:45:00+00:00",
    "second_half_start": "2026-10-03T14:00:00+00:00",
    "match_end_time": None,
    "half_duration": 45,
}


@pytest.mark.unit
class TestFullTimeRecordsMinutes:
    def _end_match(self, match=None, stats_error=None):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)
        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao") as mock_event_dao,
            patch("app.player_stats_dao") as mock_stats_dao,
            patch("app.lineup_dao"),
            patch("app.auth_manager") as mock_auth,
            patch("app.notify_event_task"),
        ):
            mock_match_dao.get_match_by_id.return_value = match or LIVE_MATCH
            mock_match_dao.update_match_clock.return_value = {"match_id": 123}
            mock_match_dao.get_live_match_state.return_value = {"match_id": 123}
            mock_auth.can_edit_match.return_value = True
            mock_stats_dao.get_starter_ids.return_value = [1, 2]
            mock_event_dao.get_events.return_value = [sub(60, 3, 1)]
            if stats_error:
                mock_stats_dao.record_minutes.side_effect = stats_error
            try:
                response = TestClient(app).post("/api/matches/123/live/clock", json={"action": "end_match"})
            finally:
                app.dependency_overrides.clear()
        return response, mock_stats_dao

    def test_full_time_writes_derived_minutes(self):
        response, mock_stats_dao = self._end_match()
        assert response.status_code == 200
        mock_stats_dao.record_minutes.assert_called_once_with(123, {1: 60, 2: 90, 3: 30})

    def test_a_replayed_full_time_does_not_rewrite_minutes(self):
        """Minutes edited after the match must survive an offline replay."""
        _, mock_stats_dao = self._end_match(match={**LIVE_MATCH, "match_end_time": "2026-10-03T14:50:00+00:00"})
        mock_stats_dao.record_minutes.assert_not_called()

    def test_a_minutes_failure_does_not_stop_full_time(self):
        response, _ = self._end_match(stats_error=RuntimeError("db down"))
        assert response.status_code == 200


@pytest.mark.unit
class TestLiveSubstitutionMarksPlayed:
    def test_player_coming_on_is_marked_played(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)
        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao") as mock_event_dao,
            patch("app.player_stats_dao") as mock_stats_dao,
            patch("app.roster_dao") as mock_roster_dao,
            patch("app.auth_manager") as mock_auth,
        ):
            mock_match_dao.get_match_by_id.return_value = LIVE_MATCH
            mock_auth.can_edit_match.return_value = True
            mock_roster_dao.get_player_by_id.side_effect = lambda pid: {
                "id": pid,
                "team_id": 1,
                "jersey_number": pid,
                "display_name": f"P{pid}",
            }
            mock_event_dao.get_event_by_client_id.return_value = None
            mock_event_dao.create_event.return_value = {"id": 1, "event_type": "substitution"}
            try:
                response = TestClient(app).post(
                    "/api/matches/123/live/substitution",
                    json={"team_id": 1, "player_in_id": 10, "player_out_id": 11, "match_minute": 33},
                )
            finally:
                app.dependency_overrides.clear()

        assert response.status_code == 200, response.text
        mock_stats_dao.mark_played.assert_called_once_with(10, 123)

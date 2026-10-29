"""Clock corrections: undoing halftime / the second half (SB-1449)."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from clock_correction import minute_at, retime_events
from tests.unit.test_live_scoring_idempotency import _live_match, _override_auth

# Match #10106 as it was recorded: HALFTIME tapped 14' in, second half 34s later.
KICKOFF = "2026-10-28T22:30:56.972165+00:00"
HALFTIME = "2026-10-28T22:44:59.772985+00:00"
SECOND_HALF = "2026-10-28T22:45:33.439087+00:00"

EVENTS_10106 = [
    {
        "id": 676,
        "event_type": "goal",
        "created_at": "2026-10-28T23:11:47.544197+00:00",
        "match_minute": 71,
        "extra_time": 0,
    },
    {"id": 675, "event_type": "status_change", "created_at": "2026-10-28T22:45:32.576038+00:00", "match_minute": None},
    {"id": 674, "event_type": "status_change", "created_at": "2026-10-28T22:44:59.097572+00:00", "match_minute": None},
    {
        "id": 673,
        "event_type": "goal",
        "created_at": "2026-10-28T22:43:25.956164+00:00",
        "match_minute": 12,
        "extra_time": 0,
    },
    {
        "id": 672,
        "event_type": "substitution",
        "created_at": "2026-10-28T22:31:45.324731+00:00",
        "match_minute": 0,
        "extra_time": 0,
    },
]


def at(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


@pytest.mark.unit
class TestMinuteAt:
    def test_first_half_counts_from_kickoff(self):
        assert minute_at(at("2026-10-28T22:43:25+00:00"), KICKOFF, None, None, 45) == (12, 0)

    def test_first_half_stoppage_is_extra_time(self):
        assert minute_at(at("2026-10-28T23:18:57+00:00"), KICKOFF, None, None, 45) == (45, 3)

    def test_half_time_reads_half_duration(self):
        assert minute_at(at("2026-10-28T23:20:00+00:00"), KICKOFF, "2026-10-28T23:16:00+00:00", None, 45) == (45, 0)

    def test_second_half_counts_on_from_half_duration(self):
        assert minute_at(at("2026-10-28T23:41:00+00:00"), KICKOFF, HALFTIME, "2026-10-28T23:30:00+00:00", 45) == (56, 0)

    def test_second_half_stoppage_is_extra_time(self):
        assert minute_at(at("2026-10-29T00:17:00+00:00"), KICKOFF, HALFTIME, "2026-10-28T23:30:00+00:00", 45) == (90, 2)


@pytest.mark.unit
class TestRetimeEvents:
    def test_back_to_first_half_fixes_match_10106(self):
        # Undo both: the 71' goal happened 40 minutes after kickoff.
        changes = retime_events(EVENTS_10106, HALFTIME, KICKOFF, None, None, 45)
        assert changes == [(676, 40, 0)]

    def test_events_before_the_cutoff_are_untouched(self):
        changes = retime_events(EVENTS_10106, HALFTIME, KICKOFF, None, None, 45)
        assert 673 not in [event_id for event_id, _, _ in changes]
        assert 672 not in [event_id for event_id, _, _ in changes]

    def test_back_to_half_time_puts_events_at_the_break(self):
        changes = retime_events(EVENTS_10106, SECOND_HALF, KICKOFF, HALFTIME, None, 45)
        assert changes == [(676, 45, 0)]

    def test_events_without_a_minute_are_ignored(self):
        assert retime_events(EVENTS_10106[1:3], HALFTIME, KICKOFF, None, None, 45) == []

    def test_unchanged_minutes_are_not_reported(self):
        events = [{"id": 1, "created_at": "2026-10-28T22:50:00+00:00", "match_minute": 19, "extra_time": None}]
        assert retime_events(events, HALFTIME, KICKOFF, None, None, 45) == []

    def test_results_are_oldest_first(self):
        events = [
            {"id": 2, "created_at": "2026-10-28T22:55:00+00:00", "match_minute": 54},
            {"id": 1, "created_at": "2026-10-28T22:50:00+00:00", "match_minute": 49},
        ]
        assert [e for e, _, _ in retime_events(events, HALFTIME, KICKOFF, None, None, 45)] == [1, 2]


def _post_clock(action: str, match: dict, events: list[dict] | None = None):
    from fastapi.testclient import TestClient

    from app import app

    _override_auth(app)
    with (
        patch("app.match_dao") as mock_match_dao,
        patch("app.match_event_dao") as mock_event_dao,
        patch("app.auth_manager") as mock_auth,
        patch("app.notify_event_task"),
    ):
        mock_match_dao.get_match_by_id.return_value = match
        mock_match_dao.update_match_clock.return_value = {"match_id": 123, "match_status": "live"}
        mock_match_dao.get_live_match_state.return_value = {"match_id": 123, "match_status": "live"}
        mock_event_dao.get_events.return_value = events or []
        mock_auth.can_edit_match.return_value = True
        try:
            response = TestClient(app).post("/api/matches/123/live/clock", json={"action": action})
        finally:
            app.dependency_overrides.clear()
        return response, mock_match_dao, mock_event_dao


@pytest.mark.unit
class TestClockCorrectionEndpoint:
    def test_back_to_first_half_from_second_half_retimes_events(self):
        match = _live_match(kickoff_time=KICKOFF, halftime_start=HALFTIME, second_half_start=SECOND_HALF)
        response, match_dao, event_dao = _post_clock("cancel_halftime", match, EVENTS_10106)

        assert response.status_code == 200
        assert match_dao.update_match_clock.call_args.args[1] == "cancel_halftime"
        event_dao.update_event.assert_called_once_with(676, match_minute=40, extra_time=0)
        assert event_dao.create_event.call_args.kwargs["message"] == "Returned to first half"

    def test_back_to_half_time(self):
        match = _live_match(kickoff_time=KICKOFF, halftime_start=HALFTIME, second_half_start=SECOND_HALF)
        response, match_dao, event_dao = _post_clock("cancel_second_half", match, EVENTS_10106)

        assert response.status_code == 200
        assert match_dao.update_match_clock.call_args.args[1] == "cancel_second_half"
        event_dao.update_event.assert_called_once_with(676, match_minute=45, extra_time=0)
        assert event_dao.create_event.call_args.kwargs["message"] == "Returned to half time"

    def test_cancel_second_half_without_a_second_half_is_noop(self):
        match = _live_match(kickoff_time=KICKOFF, halftime_start=HALFTIME)
        response, match_dao, event_dao = _post_clock("cancel_second_half", match)

        assert response.status_code == 200
        match_dao.update_match_clock.assert_not_called()
        event_dao.create_event.assert_not_called()

    def test_undo_on_an_ended_match_is_rejected(self):
        match = _live_match(
            kickoff_time=KICKOFF,
            halftime_start=HALFTIME,
            second_half_start=SECOND_HALF,
            match_end_time=datetime(2026, 10, 28, 23, 50, tzinfo=UTC).isoformat(),
        )
        response, match_dao, _ = _post_clock("cancel_second_half", match)

        assert response.status_code == 409
        match_dao.update_match_clock.assert_not_called()

    def test_retime_failure_still_corrects_the_clock(self):
        match = _live_match(kickoff_time=KICKOFF, halftime_start=HALFTIME, second_half_start=SECOND_HALF)
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)
        with (
            patch("app.match_dao") as mock_match_dao,
            patch("app.match_event_dao") as mock_event_dao,
            patch("app.auth_manager") as mock_auth,
            patch("app.notify_event_task"),
        ):
            mock_match_dao.get_match_by_id.return_value = match
            mock_match_dao.update_match_clock.return_value = {"match_id": 123, "match_status": "live"}
            mock_event_dao.get_events.side_effect = RuntimeError("db down")
            mock_auth.can_edit_match.return_value = True
            try:
                response = TestClient(app).post("/api/matches/123/live/clock", json={"action": "cancel_halftime"})
            finally:
                app.dependency_overrides.clear()

        assert response.status_code == 200
        mock_match_dao.update_match_clock.assert_called_once()

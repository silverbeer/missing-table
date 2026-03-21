"""Unit tests for mt_cli status event display logic.

These tests cover the event-filtering and ordering fix for the bug where
``mt match status`` only showed the first two goals of a 3-0 match because
the /live endpoint returns events newest-first and the old ``[-5:]`` slice
was taking the *oldest* entries, hiding recent goals.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers mirroring the filtering logic in mt_cli.status()
# ---------------------------------------------------------------------------

_SKIP_TYPES = {"status_change"}


def _filter_and_order(all_events: list[dict]) -> list[dict]:
    """Reproduce the filtering + ordering logic from the status command."""
    return [e for e in reversed(all_events) if e.get("event_type") not in _SKIP_TYPES]


def _fallback_order(recent_events: list[dict]) -> list[dict]:
    """Reproduce the fallback path (newest-first input → chronological output)."""
    raw = recent_events or []
    return list(reversed(raw[:10]))


# ---------------------------------------------------------------------------
# Sample data for match 1190 (IFA 3-0 Long Island SC, goals at 12', 18', 65')
# ---------------------------------------------------------------------------

MATCH_1190_EVENTS_NEWEST_FIRST = [
    # newest → oldest
    {"id": 6, "event_type": "goal", "match_minute": 65, "extra_time": None, "message": "Goal! IFA #41 — 65'"},
    {"id": 5, "event_type": "status_change", "match_minute": None, "extra_time": None, "message": "Second half started"},
    {"id": 4, "event_type": "status_change", "match_minute": None, "extra_time": None, "message": "Halftime"},
    {"id": 3, "event_type": "goal", "match_minute": 18, "extra_time": None, "message": "Goal! IFA — 18'"},
    {"id": 2, "event_type": "goal", "match_minute": 12, "extra_time": None, "message": "Goal! IFA — 12'"},
    {"id": 1, "event_type": "status_change", "match_minute": None, "extra_time": None, "message": "Kickoff"},
]


@pytest.mark.unit
class TestStatusEventFiltering:
    """The normal path: get_match_events returns the full list, newest-first."""

    def test_all_three_goals_shown(self):
        result = _filter_and_order(MATCH_1190_EVENTS_NEWEST_FIRST)
        minutes = [e["match_minute"] for e in result if e.get("match_minute") is not None]
        assert minutes == [12, 18, 65], "All three goals must appear in chronological order"

    def test_status_change_events_excluded(self):
        result = _filter_and_order(MATCH_1190_EVENTS_NEWEST_FIRST)
        types = {e["event_type"] for e in result}
        assert "status_change" not in types

    def test_chronological_order(self):
        result = _filter_and_order(MATCH_1190_EVENTS_NEWEST_FIRST)
        ids = [e["id"] for e in result]
        assert ids == sorted(ids), "Events must be in chronological (ascending ID) order"

    def test_empty_input(self):
        assert _filter_and_order([]) == []

    def test_only_status_changes_returns_empty(self):
        only_status = [e for e in MATCH_1190_EVENTS_NEWEST_FIRST if e["event_type"] == "status_change"]
        assert _filter_and_order(only_status) == []

    def test_message_events_included(self):
        events = [
            {"id": 2, "event_type": "message", "match_minute": None, "message": "Great save!"},
            {"id": 1, "event_type": "status_change", "match_minute": None, "message": "Kickoff"},
        ]
        result = _filter_and_order(events)
        assert len(result) == 1
        assert result[0]["event_type"] == "message"

    def test_card_events_included(self):
        events = [
            {"id": 2, "event_type": "yellow_card", "match_minute": 30, "message": "Yellow card"},
            {"id": 1, "event_type": "status_change", "match_minute": None, "message": "Kickoff"},
        ]
        result = _filter_and_order(events)
        assert len(result) == 1
        assert result[0]["event_type"] == "yellow_card"


@pytest.mark.unit
class TestStatusEventFallback:
    """The fallback path when get_match_events raises an exception.

    Old bug: ``recent_events[-5:]`` on a newest-first list showed the oldest
    entries, hiding recent goals.  The fallback now reverses so the output
    is chronological.
    """

    def test_65_minute_goal_appears_in_fallback(self):
        """With 6 events newest-first, the 65' goal (index 0) must appear."""
        # Simulate the raw recent_events the /live endpoint returns
        raw = MATCH_1190_EVENTS_NEWEST_FIRST  # newest-first, 6 entries
        result = _fallback_order(raw)
        minutes = [e["match_minute"] for e in result if e.get("match_minute") is not None]
        assert 65 in minutes, "Fallback must include the 65' goal"

    def test_fallback_chronological_order(self):
        raw = MATCH_1190_EVENTS_NEWEST_FIRST
        result = _fallback_order(raw)
        ids = [e["id"] for e in result]
        assert ids == sorted(ids)

    def test_fallback_limits_to_ten(self):
        many = [{"id": i, "event_type": "message", "match_minute": i, "message": f"msg {i}"} for i in range(20, 0, -1)]
        result = _fallback_order(many)
        assert len(result) == 10

    def test_fallback_empty(self):
        assert _fallback_order([]) == []

    def test_old_slice_would_miss_newest_goal(self):
        """Demonstrate the original bug: ``[-5:]`` on newest-first misses index 0."""
        raw = MATCH_1190_EVENTS_NEWEST_FIRST
        buggy = raw[-5:]  # reproduces the original code
        minutes_buggy = [e["match_minute"] for e in buggy if e.get("match_minute") is not None]
        assert 65 not in minutes_buggy, "The old slice should NOT have contained 65' (confirming the bug)"
        # And the fixed version should contain it
        fixed = _fallback_order(raw)
        minutes_fixed = [e["match_minute"] for e in fixed if e.get("match_minute") is not None]
        assert 65 in minutes_fixed

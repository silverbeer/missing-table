"""Unit tests for notification formatters — pure functions, no I/O."""

from __future__ import annotations

from zoneinfo import ZoneInfo

import pytest

from notifications.formatters import (
    format_card,
    format_event,
    format_fulltime,
    format_goal,
    format_halftime,
    format_kickoff,
)

pytestmark = [pytest.mark.unit]

ET = ZoneInfo("America/New_York")

MATCH = {
    "home_team_id": 10,
    "away_team_id": 20,
    "home_team_name": "IFA",
    "away_team_name": "NEFC",
    "home_score": 2,
    "away_score": 1,
    "age_group_name": "U14",
    "division_name": "MLS Next Northeast",
    "scheduled_kickoff": "2026-04-22T19:30:00+00:00",
}


class TestFormatKickoff:
    def test_includes_matchup_emoji_and_tag(self):
        text = format_kickoff(MATCH, ET)
        assert "KICKOFF" in text
        assert "IFA vs NEFC" in text
        assert "⏱" in text
        assert "U14" in text
        assert "MLS Next Northeast" in text

    def test_renders_kickoff_time_in_club_local_time(self):
        # 19:30 UTC → 15:30 ET (standard) or 14:30 EDT. Either way, hour is 2 or 3 PM.
        text = format_kickoff(MATCH, ET)
        assert ("3:30 PM" in text) or ("2:30 PM" in text)


class TestFormatGoal:
    def test_home_goal(self):
        event = {"team_id": 10, "player_name": "Smith", "match_minute": 34, "extra_time": 0}
        text = format_goal(event, MATCH, ET)
        assert "GOAL" in text
        assert "⚽" in text
        assert "Smith" in text
        assert "IFA" in text  # scoring team in the parens
        assert "34'" in text
        # Score line present
        assert "IFA 2 - 1 NEFC" in text

    def test_away_goal_uses_away_team_name(self):
        event = {"team_id": 20, "player_name": "Jones", "match_minute": 78, "extra_time": 0}
        text = format_goal(event, MATCH, ET)
        assert "Jones" in text
        assert "NEFC" in text

    def test_extra_time_minute_format(self):
        event = {"team_id": 10, "player_name": "Kim", "match_minute": 90, "extra_time": 3}
        text = format_goal(event, MATCH, ET)
        assert "90+3'" in text

    def test_missing_minute_omits_tick(self):
        event = {"team_id": 10, "player_name": "Alvarez"}
        text = format_goal(event, MATCH, ET)
        assert "Alvarez" in text
        # No stray minute-prime character
        assert "'" not in text

    def test_unknown_team_id_falls_back(self):
        event = {"team_id": 999, "player_name": "Ghost", "match_minute": 50}
        text = format_goal(event, MATCH, ET)
        assert "Unknown" in text
        assert "Ghost" in text


class TestFormatCard:
    def test_yellow_card(self):
        event = {"card_type": "yellow_card", "team_id": 10, "player_name": "Lee", "match_minute": 45}
        text = format_card(event, MATCH, ET)
        assert "🟨" in text
        assert "Yellow card" in text
        assert "Lee" in text
        assert "IFA" in text
        assert "45'" in text

    def test_red_card(self):
        event = {"card_type": "red_card", "team_id": 20, "player_name": "Patel", "match_minute": 89}
        text = format_card(event, MATCH, ET)
        assert "🟥" in text
        assert "Red card" in text
        assert "Patel" in text
        assert "NEFC" in text


class TestFormatHalftimeAndFulltime:
    def test_halftime_shows_current_score(self):
        text = format_halftime(MATCH, ET)
        assert "HALFTIME" in text
        assert "⏸" in text
        assert "IFA 2 - 1 NEFC" in text

    def test_fulltime_shows_final_score_and_tag(self):
        text = format_fulltime(MATCH, ET)
        assert "FULL TIME" in text
        assert "🏁" in text
        assert "IFA 2 - 1 NEFC" in text
        assert "U14" in text


class TestFormatEventDispatcher:
    def test_goal_dispatches_to_format_goal(self):
        extra = {"team_id": 10, "player_name": "Smith", "match_minute": 34, "extra_time": 0}
        text = format_event("goal", MATCH, extra, ET)
        assert "GOAL" in text
        assert "Smith" in text

    @pytest.mark.parametrize("card_type", ["yellow_card", "red_card"])
    def test_card_dispatches_with_type(self, card_type):
        extra = {"team_id": 10, "player_name": "Lee", "match_minute": 45}
        text = format_event(card_type, MATCH, extra, ET)
        label = "Red card" if card_type == "red_card" else "Yellow card"
        assert label in text

    @pytest.mark.parametrize("event_type", ["kickoff", "halftime", "fulltime"])
    def test_clock_events_dispatch(self, event_type):
        text = format_event(event_type, MATCH, None, ET)
        assert text is not None
        assert "IFA" in text

    def test_unknown_event_returns_none(self):
        assert format_event("substitution", MATCH, None, ET) is None


class TestScoreEdgeCases:
    def test_zero_zero_score(self):
        match = {**MATCH, "home_score": 0, "away_score": 0}
        text = format_halftime(match, ET)
        assert "IFA 0 - 0 NEFC" in text

    def test_none_scores_render_as_zero(self):
        match = {**MATCH, "home_score": None, "away_score": None}
        text = format_halftime(match, ET)
        assert "IFA 0 - 0 NEFC" in text

"""Routing rules for scoped channels (SB-1602). Pure: no database."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from notifications.adapters.discord import DiscordAdapter
from notifications.adapters.slack import SlackAdapter
from notifications.adapters.telegram import TelegramAdapter
from notifications.audience import age_number, player_channel_problem, players_allowed_at
from notifications.channel_resolver import resolve_destinations, select_destinations

pytestmark = pytest.mark.unit


def channel(dest="d", platform="discord", audience="fans", enabled=True, event_types=None):
    return {
        "platform": platform,
        "destination": dest,
        "audience": audience,
        "enabled": enabled,
        "event_types": event_types,
    }


class TestSelectDestinations:
    def test_no_channels_is_an_empty_list(self):
        assert select_destinations([], "goal", "U15") == []

    def test_disabled_is_skipped(self):
        assert select_destinations([channel(enabled=False)], "goal", "U15") == []

    def test_null_event_types_means_every_event(self):
        assert select_destinations([channel(event_types=None)], "goal", "U15") == [("discord", "d")]

    def test_empty_event_types_means_none(self):
        assert select_destinations([channel(event_types=[])], "goal", "U15") == []

    def test_event_filter(self):
        rows = [channel(event_types=["fulltime"])]
        assert select_destinations(rows, "goal", "U15") == []
        assert select_destinations(rows, "fulltime", "U15") == [("discord", "d")]

    def test_same_destination_posts_once(self):
        assert select_destinations([channel(), channel()], "goal", "U15") == [("discord", "d")]

    def test_u13_match_never_reaches_players(self):
        assert select_destinations([channel(audience="players")], "goal", "U13") == []

    def test_u13_match_still_reaches_fans(self):
        assert select_destinations([channel(audience="fans")], "goal", "U13") == [("discord", "d")]

    def test_u14_match_reaches_players(self):
        assert select_destinations([channel(audience="players")], "goal", "U14") == [("discord", "d")]

    @pytest.mark.parametrize("name", [None, "", "tsc_ci_u18", "2012"])
    def test_unreadable_age_group_fails_closed_for_players(self, name):
        assert select_destinations([channel(audience="players")], "goal", name) == []


class TestResolveDestinations:
    MATCH = {
        "home_team_club": {"id": 1},
        "away_team_club": {"id": 2},
        "home_team_id": 10,
        "away_team_id": 20,
        "age_group_id": 3,
        "age_group_name": "U15",
    }

    def test_asks_for_both_clubs_and_both_squads(self):
        dao = Mock()
        dao.list_for_match.return_value = [channel()]
        assert resolve_destinations(self.MATCH, "goal", dao) == [("discord", "d")]
        dao.list_for_match.assert_called_once_with([1, 2], [10, 20], 3)

    def test_clubless_teams_still_resolve(self):
        dao = Mock()
        dao.list_for_match.return_value = []
        match = {**self.MATCH, "home_team_club": None, "away_team_club": None}
        assert resolve_destinations(match, "goal", dao) == []
        dao.list_for_match.assert_called_once_with([], [10, 20], 3)


class TestAudienceRules:
    @pytest.mark.parametrize(("name", "expected"), [("U14", 14), ("U19", 19), ("u14", None), (None, None)])
    def test_age_number(self, name, expected):
        assert age_number(name) == expected

    def test_players_allowed_from_u14(self):
        assert players_allowed_at("U13") is False
        assert players_allowed_at("U14") is True

    def test_telegram_is_fans_only(self):
        assert player_channel_problem(TelegramAdapter(), "U15")

    def test_discord_hosts_a_u14_squad(self):
        assert player_channel_problem(DiscordAdapter(), "U14") is None

    def test_no_player_channel_at_u13(self):
        assert player_channel_problem(DiscordAdapter(), "U13")

    def test_discord_hosts_a_club_player_channel(self):
        assert player_channel_problem(DiscordAdapter(), None) is None

    def test_slack_only_for_oldest_squads(self):
        assert player_channel_problem(SlackAdapter(), "U16")
        assert player_channel_problem(SlackAdapter(), "U17") is None

    def test_slack_cannot_host_a_club_wide_player_channel(self):
        assert player_channel_problem(SlackAdapter(), None)

    def test_unreadable_age_group_is_refused(self):
        assert player_channel_problem(DiscordAdapter(), "tsc_ci_u18")

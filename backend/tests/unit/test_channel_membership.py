"""Who may see and join a notification channel (SB-1607). Pure rules, no database."""

import pytest

from mt_tools.my_team import Squad, channel_viewer
from notifications.adapters.base import InvalidDestinationError
from notifications.membership import ChannelFacts, can_be_granted, channel_access, viewer_state
from notifications.registry import get_adapter

CLUB, OTHER_CLUB, TEAM, U15, U13 = 1, 2, 10, 15, 13


def viewer(role, club_id=CLUB, team_id=None, squads=()):
    return channel_viewer({"role": role, "club_id": club_id, "team_id": team_id}, None, list(squads))


def squad(team_id=TEAM, age_group_id=U15, club_id=CLUB, name="U15"):
    return Squad(team_id=team_id, age_group_id=age_group_id, club_id=club_id, age_group_name=name)


def team_channel(audience="fans", age_group_id=U15, name="U15", club_id=CLUB):
    return ChannelFacts("team", audience, club_id, TEAM, age_group_id, name)


def club_channel(audience="fans", club_id=CLUB):
    return ChannelFacts("club", audience, club_id)


FAN = viewer("team-fan")
PLAYER = viewer("team-player", squads=[squad()])


class TestFans:
    def test_club_fan_channel_is_joinable(self):
        assert channel_access(FAN, club_channel()) == "joinable"

    def test_squad_fan_channel_is_requested(self):
        assert channel_access(FAN, team_channel()) == "requestable"

    def test_another_clubs_channels_are_hidden(self):
        fan = viewer("club-fan", club_id=OTHER_CLUB)
        assert channel_access(fan, club_channel()) == "hidden"
        assert channel_access(fan, team_channel()) == "hidden"

    @pytest.mark.parametrize("channel", [team_channel("players"), club_channel("players")])
    def test_fans_never_see_player_channels(self, channel):
        assert channel_access(FAN, channel) == "hidden"

    def test_no_club_sees_nothing(self):
        assert channel_access(viewer("team-fan", club_id=None), club_channel()) == "hidden"

    @pytest.mark.parametrize("role", ["team-fan", "club-fan", "team_fan", "club_fan"])
    def test_both_spellings_are_fans(self, role):
        assert channel_access(viewer(role), club_channel()) == "joinable"


class TestPlayers:
    def test_own_squad_player_channel_is_joinable(self):
        assert channel_access(PLAYER, team_channel("players")) == "joinable"

    def test_club_player_channel_is_joinable(self):
        assert channel_access(PLAYER, club_channel("players")) == "joinable"

    def test_another_age_group_is_hidden(self):
        assert channel_access(PLAYER, team_channel("players", age_group_id=16, name="U16")) == "hidden"

    @pytest.mark.parametrize("channel", [team_channel(), club_channel()])
    def test_players_never_see_fan_channels(self, channel):
        assert channel_access(PLAYER, channel) == "hidden"

    def test_under_14_squad_never_joins(self):
        young = viewer("team-player", squads=[squad(age_group_id=U13, name="U13")])
        assert channel_access(young, team_channel("players", age_group_id=U13, name="U13")) == "hidden"
        assert channel_access(young, club_channel("players")) == "hidden"

    def test_unknown_age_fails_closed(self):
        assert channel_access(PLAYER, team_channel("players", name=None)) == "hidden"

    def test_former_player_is_hidden(self):
        assert channel_access(viewer("team-player"), team_channel("players")) == "hidden"

    def test_squads_are_ignored_for_non_players(self):
        fan = channel_viewer({"role": "team-fan", "club_id": CLUB}, None, [squad()])
        assert channel_access(fan, team_channel("players")) == "hidden"


class TestManagers:
    def test_team_manager_joins_own_squad_channels(self):
        manager = viewer("team-manager", team_id=TEAM)
        assert channel_access(manager, team_channel()) == "joinable"
        assert channel_access(manager, team_channel("players")) == "joinable"

    def test_team_manager_joins_club_fans_not_club_players(self):
        manager = viewer("team-manager", team_id=TEAM)
        assert channel_access(manager, club_channel()) == "joinable"
        assert channel_access(manager, club_channel("players")) == "hidden"

    def test_team_manager_club_comes_from_their_team(self):
        manager = channel_viewer({"role": "team-manager", "club_id": None, "team_id": 99}, CLUB, [])
        assert channel_access(manager, club_channel()) == "joinable"

    def test_club_manager_joins_everything_in_their_club(self):
        manager = viewer("club_manager")
        for channel in (team_channel(), team_channel("players"), club_channel(), club_channel("players")):
            assert channel_access(manager, channel) == "joinable"

    def test_club_manager_of_another_club_is_hidden(self):
        assert channel_access(viewer("club_manager", club_id=OTHER_CLUB), team_channel()) == "hidden"


def test_global_channels_are_never_listed():
    assert channel_access(viewer("admin"), ChannelFacts("global", "fans", None)) == "hidden"


def test_unknown_role_sees_nothing():
    assert channel_access(viewer("mystery"), club_channel()) == "hidden"


class TestViewerState:
    def test_hidden_has_no_state_even_with_a_grant(self):
        assert viewer_state("hidden", "active") is None

    @pytest.mark.parametrize(
        ("access", "status", "state"),
        [
            ("joinable", None, "can_join"),
            ("requestable", None, "can_request"),
            ("requestable", "requested", "requested"),
            ("requestable", "active", "member"),
            ("joinable", "revoked", "revoked"),
            ("requestable", "denied", "denied"),
        ],
    )
    def test_states(self, access, status, state):
        assert viewer_state(access, status) == state


def test_a_manager_cannot_grant_a_fan_a_player_channel():
    assert not can_be_granted(channel_access(FAN, team_channel("players")))
    assert can_be_granted(channel_access(FAN, team_channel()))


class TestInviteLinks:
    @pytest.mark.parametrize(
        ("platform", "url"),
        [
            ("discord", "https://discord.gg/abc123XY"),
            ("discord", "https://discord.com/invite/abc123XY"),
            ("telegram", "https://t.me/+AbCdEfGh1234"),
            ("telegram", "https://t.me/joinchat/AbCdEfGh1234"),
            ("slack", "https://join.slack.com/t/silverbeer/shared_invite/zt-1abc-DEF_ghi"),
        ],
    )
    def test_private_links_are_accepted(self, platform, url):
        get_adapter(platform).validate_invite_url(url)

    @pytest.mark.parametrize(
        ("platform", "url"),
        [
            ("telegram", "https://t.me/publicchannel"),
            ("discord", "http://discord.gg/abc123"),
            ("discord", "https://evil.example/discord.gg/abc"),
            ("slack", "https://hooks.slack.com/services/T0/B0/x"),
        ],
    )
    def test_public_or_foreign_links_are_rejected(self, platform, url):
        with pytest.raises(InvalidDestinationError):
            get_adapter(platform).validate_invite_url(url)

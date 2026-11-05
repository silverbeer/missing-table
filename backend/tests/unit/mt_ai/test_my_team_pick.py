"""A fan picks "my team": club + league + age group (SB-1543).

A team row is a club in one league; the picked age group makes it the squad the
fan means. `get_my_team` then answers with that one entry instead of every age
group the team plays.
"""

import pytest
from mt_ai_fakes import (
    ALIASES,
    CLUBS,
    LEAGUES,
    TEAMS,
    U15,
    U16,
    FakeClubs,
    FakeLeagues,
    FakeMatches,
    FakeSeasons,
    FakeTeams,
)

from auth import fan_age_group_for_invite
from mt_ai.tools import ToolDeps, Viewer
from mt_tools.my_team import is_valid_pick, resolve_my_team, team_pick_options

pytestmark = [pytest.mark.unit, pytest.mark.backend]

REAL = Viewer(include_test=False)
TEST = Viewer(include_test=True)


def deps() -> ToolDeps:
    return ToolDeps(
        teams=FakeTeams(TEAMS, ALIASES),
        clubs=FakeClubs(CLUBS),
        leagues=FakeLeagues(LEAGUES),
        matches=FakeMatches(),
        seasons=FakeSeasons(),
    )


def fan(**profile) -> dict:
    return {"user_id": "u-1", "role": "club-fan", **profile}


class TestResolverHonoursThePick:
    def test_no_pick_returns_every_age_group(self):
        result = resolve_my_team(deps(), fan(team_id=108), REAL)
        assert [t.age_group.id for t in result.teams] == [U15, U16]

    def test_a_pick_returns_just_that_squad(self):
        result = resolve_my_team(deps(), fan(team_id=108, assigned_age_group_id=U16), REAL)
        assert result.status == "team"
        assert [(t.team_id, t.age_group.id) for t in result.teams] == [(108, U16)]

    def test_a_pick_the_team_no_longer_plays_is_ignored_not_emptied(self):
        result = resolve_my_team(deps(), fan(team_id=108, assigned_age_group_id=999), REAL)
        assert [t.age_group.id for t in result.teams] == [U15, U16]

    def test_a_pick_keeps_both_competitions_of_that_age(self):
        # IFA U15 plays Homegrown and Flex: one squad, two registrations.
        result = resolve_my_team(deps(), fan(team_id=102, club_id=11, assigned_age_group_id=U15), REAL)
        [squad] = result.teams
        assert {r.league for r in squad.registrations} == {"Homegrown", "Flex"}


class TestPickOptions:
    def test_options_are_the_clubs_visible_teams_one_per_age_group(self):
        options = team_pick_options(deps(), fan(club_id=11), REAL)
        assert options.status == "ok" and options.club.name == "IFA"
        got = {(o.team_id, o.age_group.id) for o in options.options}
        # 105 plays only in a test league, 106 has no age groups, 109's U16 is a
        # test-league registration: none of those is a pick for a real viewer.
        assert got == {(102, U15), (109, U15), (111, U15)}

    def test_a_test_viewer_sees_test_registrations(self):
        got = {(o.team_id, o.age_group.id) for o in team_pick_options(deps(), fan(club_id=11), TEST).options}
        assert (109, U16) in got and (105, U15) in got

    def test_the_club_comes_from_the_team_when_the_profile_has_none(self):
        options = team_pick_options(deps(), fan(team_id=102), REAL)
        assert options.club.id == 11

    def test_no_club_is_nothing_to_pick(self):
        assert team_pick_options(deps(), fan(), REAL).status == "no_club"
        assert team_pick_options(deps(), fan(team_id=108), REAL).status == "no_club"  # NEFC has no club

    def test_current_pick_is_reported(self):
        options = team_pick_options(deps(), fan(club_id=11, team_id=102, assigned_age_group_id=U15), REAL)
        assert (options.current_team_id, options.current_age_group_id) == (102, U15)


class TestValidPick:
    def setup_method(self):
        self.options = team_pick_options(deps(), fan(club_id=11), REAL)

    def test_a_team_in_the_club_at_an_age_it_plays(self):
        assert is_valid_pick(self.options, 102, U15)

    def test_an_age_the_team_does_not_play(self):
        assert not is_valid_pick(self.options, 102, U16)

    def test_a_team_in_another_club(self):
        # Boston United is club 10: picking it would widen roster visibility.
        assert not is_valid_pick(self.options, 100, U15)

    def test_a_hidden_test_registration(self):
        assert not is_valid_pick(self.options, 109, U16)

    def test_nothing_is_valid_without_a_club(self):
        assert not is_valid_pick(team_pick_options(deps(), fan(), REAL), 102, U15)


class TestInviteCarriesThePick:
    def test_a_team_fan_invite_brings_its_age_group(self):
        assert fan_age_group_for_invite({"invite_type": "team_fan", "team_id": 19, "age_group_id": 3}) == 3

    @pytest.mark.parametrize("invite_type", ["club_fan", "team_manager", "team_player", "club_manager", None])
    def test_other_invites_clear_it(self, invite_type):
        assert fan_age_group_for_invite({"invite_type": invite_type, "age_group_id": 3}) is None

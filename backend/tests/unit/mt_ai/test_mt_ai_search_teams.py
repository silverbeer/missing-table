"""search_teams (SB-1142): name → team, with honest ambiguity."""

import pytest
from mt_ai_fakes import TEAMS, U15, U16, FakeLeagues, FakeTeams

from mt_ai.tools import Viewer, search_teams
from mt_ai.tools.teams import split_age_group

pytestmark = [pytest.mark.unit, pytest.mark.backend]


class TestResolved:
    def test_single_age_team_resolves_with_its_context(self, make_deps, real_viewer):
        result = search_teams(make_deps(), "IFA", real_viewer)

        assert result.status == "resolved"
        assert result.error is None
        team = result.team
        assert (team.team_id, team.name, team.club_name, team.league_name) == (102, "IFA", "IFA", "Homegrown")
        assert team.age_group.name == "U15"
        assert team.division_name == "Northeast"

    @pytest.mark.parametrize("query", ["IFA U15", "ifa u15", "IFA u-15", "  IFA   U15 "])
    def test_age_in_the_question_is_understood(self, make_deps, real_viewer, query):
        result = search_teams(make_deps(), query, real_viewer)

        assert result.status == "resolved"
        assert result.team.team_id == 102

    def test_age_picks_one_registration_of_a_multi_age_team(self, make_deps, real_viewer):
        result = search_teams(make_deps(), "NEFC", real_viewer, age_group="U16")

        assert result.status == "resolved"
        assert result.team.age_group.id == U16
        # divisions_by_age_group keys were strings (a cache hit) — still found.
        assert result.team.division_name == "Northeast"

    def test_alias_resolves_to_the_canonical_team(self, make_deps, real_viewer):
        result = search_teams(make_deps(), "Intercontinental Football Academy", real_viewer)

        assert result.status == "resolved"
        assert result.team.team_id == 102

    def test_team_without_registrations_resolves_without_an_age(self, make_deps, real_viewer):
        result = search_teams(make_deps(), "No Ages FC", real_viewer)

        assert result.status == "resolved"
        assert result.team.age_group is None


class TestAmbiguous:
    def test_multi_age_team_without_an_age_asks_which(self, make_deps, real_viewer):
        result = search_teams(make_deps(), "NEFC", real_viewer)

        assert result.status == "ambiguous"
        assert result.team is None
        assert [(c.team_id, c.age_group.id) for c in result.candidates] == [(108, U15), (108, U16)]

    def test_same_name_in_two_leagues_is_not_guessed(self, make_deps, real_viewer):
        result = search_teams(make_deps(), "Boston United U15", real_viewer)

        assert result.status == "ambiguous"
        assert {(c.team_id, c.league_name) for c in result.candidates} == {(100, "Homegrown"), (101, "Academy")}

    def test_a_near_match_is_offered_never_resolved(self, make_deps, real_viewer):
        result = search_teams(make_deps(), "Surf", real_viewer)

        assert result.status == "ambiguous"
        assert [c.team_id for c in result.candidates] == [103]

    def test_candidates_are_capped_and_say_so(self, make_deps, real_viewer):
        result = search_teams(make_deps(), "NEFC", real_viewer, limit=1)

        assert len(result.candidates) == 1
        assert result.meta.truncated is True


class TestNotFound:
    def test_team_exists_but_not_at_that_age_lists_the_ages_it_has(self, make_deps, real_viewer):
        result = search_teams(make_deps(), "IFA U19", real_viewer)

        assert result.status == "not_found"
        assert result.error is None
        assert [c.age_group.name for c in result.candidates] == ["U15"]

    def test_generic_words_alone_match_nothing(self, make_deps, real_viewer):
        result = search_teams(make_deps(), "United Soccer Club", real_viewer)

        assert result.status == "not_found"
        assert result.candidates == []

    @pytest.mark.parametrize("query", ["%", "Bos_on", "\\"])
    def test_like_wildcards_never_reach_the_database(self, make_deps, teams, real_viewer, query):
        result = search_teams(make_deps(), query, real_viewer)

        assert result.status == "not_found"
        assert teams.resolve_calls == []


class TestTestPartition:
    """Real viewers never see test content; admins and test users do."""

    def test_team_in_a_test_club_is_invisible_to_a_real_viewer(self, make_deps, real_viewer, test_viewer):
        assert search_teams(make_deps(), "TSC Test Team", real_viewer).status == "not_found"
        assert search_teams(make_deps(), "TSC Test Team", test_viewer).status == "resolved"

    def test_team_in_a_test_league_is_invisible_to_a_real_viewer(self, make_deps, real_viewer, test_viewer):
        assert search_teams(make_deps(), "Test League Team", real_viewer).status == "not_found"
        assert search_teams(make_deps(), "Test League Team", test_viewer).status == "resolved"

    def test_alias_to_a_test_team_is_reported_as_no_hit(self, make_deps, real_viewer):
        result = search_teams(make_deps(), "TSC alias", real_viewer)

        assert result.status == "not_found"
        assert result.candidates == []

    def test_registration_in_a_test_division_is_hidden(self, make_deps, real_viewer, test_viewer):
        real = search_teams(make_deps(), "Mixed Registrations", real_viewer)
        test = search_teams(make_deps(), "Mixed Registrations", test_viewer)

        assert real.status == "resolved"
        assert real.team.age_group.id == U15
        assert test.status == "ambiguous"
        assert len(test.candidates) == 2

    @pytest.mark.parametrize(
        ("user", "expected"),
        [
            (None, False),
            ({"role": "team-fan", "is_test": False}, False),
            ({"role": "team-fan", "is_test": True}, True),
            ({"role": "admin"}, True),
        ],
    )
    def test_viewer_scope_follows_the_existing_partition_rule(self, user, expected):
        assert Viewer.from_user(user).include_test is expected


class TestErrorsAreResults:
    @pytest.mark.parametrize("query", ["", "   ", "U15"])
    def test_a_name_is_required(self, make_deps, real_viewer, query):
        result = search_teams(make_deps(), query, real_viewer)

        assert result.error.kind == "invalid_args"

    def test_bad_limit_is_rejected(self, make_deps, real_viewer):
        assert search_teams(make_deps(), "IFA", real_viewer, limit=0).error.kind == "invalid_args"

    def test_empty_league_list_fails_closed(self, make_deps, real_viewer):
        """get_all_leagues swallows errors as []; without it test teams can't be hidden."""
        result = search_teams(make_deps(leagues=FakeLeagues([], fail=True)), "IFA", real_viewer)

        assert result.status == "not_found"
        assert result.error.kind == "unavailable"

    def test_a_failing_read_is_unavailable_not_not_found(self, make_deps, real_viewer):
        failing = FakeTeams([], {}, fail=True)
        result = search_teams(make_deps(team_source=failing), "IFA", real_viewer)

        assert result.error.kind == "unavailable"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Boston United U15", ("Boston United", "U15")),
        ("u09 Revolution", ("Revolution", "U9")),
        ("Boston United", ("Boston United", None)),
        ("Unity FC", ("Unity FC", None)),
    ],
)
def test_split_age_group(query, expected):
    assert split_age_group(query) == expected


def test_default_fixture_is_scraped_only():
    """Guard the fixture itself: no team in the default world carries user data."""
    user_fields = {"manager_id", "roster", "players", "player_count"}
    assert all(not (user_fields & team.keys()) for team in TEAMS)

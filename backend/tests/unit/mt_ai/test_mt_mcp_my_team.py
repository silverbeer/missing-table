"""get_my_team and the my-team resolver (SB-1317).

The default caller has no team: in prod most profiles set neither team_id nor
club_id, and that is a normal answer, never an error.
"""

import pytest
from mt_ai_fakes import (
    ALIASES,
    CLUBS,
    LEAGUES,
    REAL_HOMEGROWN,
    TEAMS,
    TEST_LEAGUE,
    U15,
    FakeClubs,
    FakeLeagues,
    FakeMatches,
    FakeSeasons,
    FakeTeams,
    reg,
    team,
)
from mt_mcp_harness import served

from mt_ai.tools import ToolDeps, Viewer
from mt_mcp.observe import TOOL_CALLS
from mt_mcp.scopes import MT_AI_CLIENT
from mt_tools.my_team import resolve_my_team

pytestmark = [pytest.mark.unit, pytest.mark.backend]

EMPTY_CLUB = {"id": 15, "name": "Empty FC", "timezone": None, "is_test": False}


def deps(
    teams: FakeTeams | None = None,
    leagues: FakeLeagues | None = None,
    matches: FakeMatches | None = None,
    seasons: FakeSeasons | None = None,
) -> ToolDeps:
    return ToolDeps(
        teams=teams or FakeTeams(TEAMS, ALIASES),
        clubs=FakeClubs([*CLUBS, EMPTY_CLUB]),
        leagues=leagues or FakeLeagues(LEAGUES),
        matches=matches or FakeMatches(),
        seasons=seasons or FakeSeasons(),
    )


def user(**membership) -> dict:
    return {"user_id": "u-1", "role": "team-fan", **membership}


REAL = Viewer(include_test=False)
TEST = Viewer(include_test=True)


class TestResolver:
    def test_no_team_set_is_a_normal_answer_and_reads_nothing(self):
        teams = FakeTeams(TEAMS, ALIASES)

        result = resolve_my_team(deps(teams), user(), REAL)

        assert result.status == "no_team"
        assert result.error is None
        assert result.teams is None
        assert teams.team_reads == 0

    def test_a_team_comes_back_once_per_age_group_with_its_club(self):
        result = resolve_my_team(deps(), user(team_id=102, club_id=11), REAL)

        assert result.status == "team"
        assert result.team_id == 102
        assert result.club.name == "IFA"
        assert [(t.team_id, t.age_group.name) for t in result.teams] == [(102, "U15")]
        assert {r.league for r in result.teams[0].registrations} == {"Homegrown", "Flex"}

    def test_a_multi_age_team_without_a_club(self):
        result = resolve_my_team(deps(), user(team_id=108), REAL)

        assert result.status == "team"
        assert result.club is None
        assert [t.age_group.name for t in result.teams] == ["U15", "U16"]

    def test_team_id_wins_over_club_id(self):
        result = resolve_my_team(deps(), user(team_id=103, club_id=11), REAL)

        assert result.status == "team"
        assert result.club.name == "LA Surf"

    def test_a_club_alone_lists_its_visible_teams(self):
        real = resolve_my_team(deps(), user(club_id=11), REAL)
        test = resolve_my_team(deps(), user(club_id=11), TEST)

        assert real.status == "club"
        assert real.team_id is None
        assert real.club.name == "IFA"
        real_ids = {t.team_id for t in real.teams}
        assert real_ids == {102, 106, 109, 111}
        # The club's test-league team exists only for test viewers.
        assert {t.team_id for t in test.teams} == real_ids | {105}

    def test_a_club_with_no_teams_is_an_empty_list_not_null(self):
        result = resolve_my_team(deps(), user(club_id=15), REAL)

        assert result.status == "club"
        assert result.teams == []

    @pytest.mark.parametrize("membership", [{"team_id": 104}, {"club_id": 13}])
    def test_test_content_does_not_reach_a_real_viewer(self, membership):
        real = resolve_my_team(deps(), user(**membership), REAL)
        test = resolve_my_team(deps(), user(**membership), TEST)

        assert real.status == "no_team"
        assert real.teams is None and real.club is None
        assert test.status in {"team", "club"}

    @pytest.mark.parametrize("membership", [{"team_id": 9999}, {"club_id": 9999}])
    def test_a_dangling_id_reads_as_no_team(self, membership):
        result = resolve_my_team(deps(), user(**membership), REAL)

        assert result.status == "no_team"
        assert result.error is None

    @pytest.mark.parametrize("team_id", [9999, 104])
    def test_a_deleted_or_hidden_team_falls_back_to_the_club(self, team_id):
        result = resolve_my_team(deps(), user(team_id=team_id, club_id=11), REAL)

        assert result.status == "club"
        assert result.team_id is None
        assert result.club.name == "IFA"

    def test_a_team_in_no_visible_competition_is_still_the_team_with_no_entries(self):
        """Every registration is test content: the team is theirs, it just plays nowhere they can see."""
        only_test = team(120, "Test Comps Only", 11, REAL_HOMEGROWN, reg(U15, "TSC Division", TEST_LEAGUE))
        teams = FakeTeams([*TEAMS, only_test], ALIASES)

        real = resolve_my_team(deps(teams), user(team_id=120), REAL)
        test = resolve_my_team(deps(teams), user(team_id=120), TEST)

        assert real.status == "team"
        assert real.team_id == 120
        assert real.teams == []
        assert [t.age_group.name for t in test.teams] == ["U15"]

    def test_a_club_team_with_no_name_does_not_break_the_club(self):
        nameless = team(121, None, 15, REAL_HOMEGROWN, reg(U15, "TSC Division", TEST_LEAGUE))
        named = team(122, "Empty FC", 15, REAL_HOMEGROWN, reg(U15, "Northeast", REAL_HOMEGROWN))
        teams = FakeTeams([*TEAMS, nameless, named], ALIASES)

        result = resolve_my_team(deps(teams), user(club_id=15), REAL)

        assert result.status == "club"
        assert [t.team_id for t in result.teams] == [122]

    @pytest.mark.parametrize(
        "broken",
        [
            {"teams": FakeTeams(TEAMS, ALIASES, fail=True)},
            {"leagues": FakeLeagues(LEAGUES, fail=True)},
        ],
    )
    def test_a_failed_read_is_unavailable_not_no_team(self, broken):
        result = resolve_my_team(deps(**broken), user(team_id=102), REAL)

        assert result.status is None
        assert result.teams is None
        assert result.error.kind == "unavailable"


# IFA (club 11) has four teams a real viewer sees: 102, 106, 109, 111. Only 102
# plays this season — the prod shape the ticket came from, at fixture scale.
ONLY_IFA_PLAYS = {102}


class TestActive:
    """Active = at least one match in the current season (SB-1322)."""

    def test_a_club_lists_only_its_active_teams_and_counts_the_rest(self):
        result = resolve_my_team(deps(matches=FakeMatches(active=ONLY_IFA_PLAYS)), user(club_id=11), REAL)

        assert result.status == "club"
        assert [t.team_id for t in result.teams] == [102]
        assert all(t.active is True for t in result.teams)
        assert result.inactive_hidden == 3
        assert result.season == "2026-2027"

    def test_include_inactive_returns_every_team_marked(self):
        result = resolve_my_team(
            deps(matches=FakeMatches(active=ONLY_IFA_PLAYS)), user(club_id=11), REAL, include_inactive=True
        )

        assert {t.team_id: t.active for t in result.teams} == {102: True, 106: False, 109: False, 111: False}
        assert result.inactive_hidden == 0

    def test_nothing_playing_yet_reads_differently_from_an_empty_club(self):
        """August, before schedules load: [] with a hidden count, not a club with no teams."""
        before_schedules = resolve_my_team(deps(matches=FakeMatches(active=set())), user(club_id=11), REAL)
        empty_club = resolve_my_team(deps(matches=FakeMatches(active=set())), user(club_id=15), REAL)

        assert before_schedules.teams == []
        assert before_schedules.inactive_hidden == 4
        assert empty_club.teams == []
        assert empty_club.inactive_hidden == 0

    def test_a_team_callers_own_inactive_team_is_still_theirs(self):
        result = resolve_my_team(deps(matches=FakeMatches(active=set())), user(team_id=102, club_id=11), REAL)

        assert result.status == "team"
        assert result.team_id == 102
        assert [t.active for t in result.teams] == [False]
        assert result.inactive_hidden == 0

    def test_activity_is_judged_on_the_current_season_and_the_viewers_partition(self):
        matches = FakeMatches()

        resolve_my_team(deps(matches=matches), user(team_id=102), REAL)
        resolve_my_team(deps(matches=matches), user(team_id=102), TEST)

        assert matches.activity_calls == [(102, 7, False), (102, 7, True)]

    @pytest.mark.parametrize("membership", [{"team_id": 102}, {"club_id": 11}])
    def test_no_current_season_is_unavailable_not_everything_inactive(self, membership):
        result = resolve_my_team(deps(seasons=FakeSeasons(None)), user(**membership), REAL)

        assert result.status is None
        assert result.teams is None
        assert result.inactive_hidden is None
        assert result.error.kind == "unavailable"

    @pytest.mark.parametrize("membership", [{"team_id": 102}, {"club_id": 11}])
    def test_a_failed_activity_read_is_unavailable_not_inactive(self, membership):
        result = resolve_my_team(deps(matches=FakeMatches(fail=True)), user(**membership), REAL)

        assert result.status is None
        assert result.teams is None
        assert result.error.kind == "unavailable"

    def test_no_team_reads_no_season_and_no_activity(self):
        matches, seasons = FakeMatches(), FakeSeasons()

        result = resolve_my_team(deps(matches=matches, seasons=seasons), user(), REAL)

        assert result.status == "no_team"
        assert result.inactive_hidden is None
        assert seasons.reads == 0
        assert matches.activity_calls == []


class TestOverMcp:
    async def test_the_caller_comes_from_the_token_not_arguments(self, make_deps):
        async with served(make_deps()) as s, s.session("fan") as session:
            tool = next(t for t in (await session.list_tools()).tools if t.name == "get_my_team")

        assert set(tool.input_schema.get("properties", {})) == {"include_inactive"}
        assert {"status", "team_id", "club", "teams", "season", "inactive_hidden", "error"} <= set(
            tool.output_schema["properties"]
        )

    async def test_no_team_is_a_result_not_an_error(self, make_deps):
        async with served(make_deps()) as s, s.session("no-team") as session:
            result = await session.call_tool("get_my_team", {})

        assert not result.is_error
        assert result.structured_content["status"] == "no_team"
        assert result.structured_content["teams"] is None

    @pytest.mark.parametrize(
        ("token", "status", "team_ids"),
        [
            ("fan", "team", [102]),
            ("player", "team", [102]),
            ("team-mgr", "team", [102]),
            ("club-mgr", "club", [102, 106, 109, 111]),
            ("club-fan", "club", [102, 106, 109, 111]),
        ],
    )
    async def test_each_role_through_mt_ai(self, make_deps, token, status, team_ids):
        async with served(make_deps()) as s, s.session(token, MT_AI_CLIENT) as session:
            result = await session.call_tool("get_my_team", {})

        data = result.structured_content
        assert data["status"] == status
        assert sorted(t["team_id"] for t in data["teams"]) == team_ids

    @pytest.mark.parametrize("token", ["fan-of-test-team", "fan-of-gone-team"])
    async def test_a_hidden_or_deleted_team_reads_as_no_team(self, make_deps, token):
        async with served(make_deps()) as s, s.session(token) as session:
            result = await session.call_tool("get_my_team", {})

        assert result.structured_content["status"] == "no_team"

    async def test_a_role_without_the_my_tier_cannot_call_it(self, make_deps):
        async with served(make_deps()) as s, s.session("legacy") as session:
            result = await session.call_tool("get_my_team", {})

        assert result.is_error and result.content[0].text == "Unknown tool: get_my_team"

    async def test_a_data_failure_is_a_typed_unavailable_result(self, make_deps):
        broken = make_deps(team_source=FakeTeams(TEAMS, ALIASES, fail=True))
        async with served(broken) as s, s.session("fan") as session:
            result = await session.call_tool("get_my_team", {})

        assert not result.is_error
        assert result.structured_content["error"]["kind"] == "unavailable"

    async def test_outcomes_are_counted(self, make_deps):
        def count(outcome: str) -> float:
            return TOOL_CALLS.labels(tool="get_my_team", client="none", role="team-fan", outcome=outcome)._value.get()

        before = {o: count(o) for o in ("team", "no_team")}
        async with served(make_deps()) as s:
            async with s.session("no-team") as session:
                await session.call_tool("get_my_team", {})
            async with s.session("fan") as session:
                await session.call_tool("get_my_team", {})

        assert count("no_team") == before["no_team"] + 1
        assert count("team") == before["team"] + 1

    @pytest.mark.parametrize(
        ("args", "team_ids", "hidden"), [({}, [102], 3), ({"include_inactive": True}, [102, 106, 109, 111], 0)]
    )
    async def test_include_inactive_is_passed_through(self, make_deps, args, team_ids, hidden):
        async with served(make_deps(matches=FakeMatches(active=ONLY_IFA_PLAYS))) as s, s.session("club-mgr") as session:
            result = await session.call_tool("get_my_team", args)

        data = result.structured_content
        assert sorted(t["team_id"] for t in data["teams"]) == team_ids
        assert data["inactive_hidden"] == hidden

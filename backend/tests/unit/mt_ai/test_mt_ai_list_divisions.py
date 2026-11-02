"""list_divisions (SB-1503): resolve a division by name, for get_standings by division.

The default world is the scraper's: teams with results and no manager. Every
division listed comes from a visible team's registration, so these tests cover
filtering, visibility, the not_found that says what does exist, and failures
that must not read as "no divisions".
"""

import pytest
from mt_ai_fake_llm import calls_tool, says, scripted
from mt_ai_fakes import (
    ALIASES,
    LEAGUES,
    NE_FLEX,
    NEW_ENGLAND,
    NORTHEAST,
    REAL_HOMEGROWN,
    SOUTHWEST,
    TEAMS,
    TSC_DIVISION,
    U14,
    U15,
    U16,
    FakeLeagues,
    FakeMatches,
    FakeTeams,
    reg,
    standings_result,
    standings_row,
    team,
)
from mt_mcp_harness import URL, served

from mt_ai.agent import McpAccess, run_turn
from mt_ai.budget import Budget
from mt_ai.tools import list_divisions
from mt_ai.tools.divisions import MAX_DIVISIONS
from mt_mcp.scopes import MT_AI_CLIENT

pytestmark = [pytest.mark.unit, pytest.mark.backend]

BOSTON, IFA = 100, 102


def ids(result) -> list[int]:
    return [d.division.id for d in result.divisions]


def ages(result, division_id: int) -> list[tuple[int, str, int]]:
    summary = next(d for d in result.divisions if d.division.id == division_id)
    return [(a.id, a.name, a.teams) for a in summary.age_groups]


class TestListing:
    def test_every_visible_division_ordered_by_league_then_name(self, make_deps, real_viewer):
        result = list_divisions(make_deps(), real_viewer)

        assert result.error is None
        assert [(d.division.league, d.division.name) for d in result.divisions] == [
            ("Academy", "New England"),
            ("Flex", "New England"),
            ("Homegrown", "Northeast"),
            ("Homegrown", "Southwest"),
        ]
        assert result.meta.truncated is False

    def test_age_groups_carry_ids_and_visible_team_counts_in_age_order(self, make_deps, real_viewer):
        """Northeast U15: Boston, IFA, NEFC, Mixed Registrations, Split Comp FC. U16: NEFC only."""
        result = list_divisions(make_deps(), real_viewer)

        assert ages(result, NORTHEAST) == [(U15, "U15", 5), (U16, "U16", 1)]
        assert ages(result, SOUTHWEST) == [(U14, "U14", 1)]

    def test_a_team_in_league_and_flex_counts_once_in_each(self, make_deps, real_viewer):
        result = list_divisions(make_deps(), real_viewer)

        assert ages(result, NE_FLEX) == [(U15, "U15", 1)]


class TestFilters:
    @pytest.mark.parametrize("age", ["U15", "u15", "U-15", " 15 "])
    def test_age_group_by_name_in_any_spelling(self, make_deps, real_viewer, age):
        result = list_divisions(make_deps(), real_viewer, age_group=age)

        assert ids(result) == [NEW_ENGLAND, NE_FLEX, NORTHEAST]
        # Only the asked-for age, so the table to pick is unambiguous.
        assert ages(result, NORTHEAST) == [(U15, "U15", 5)]

    @pytest.mark.parametrize("league", ["Homegrown", "homegrown", "  HOMEGROWN "])
    def test_league_by_name_case_insensitive(self, make_deps, real_viewer, league):
        result = list_divisions(make_deps(), real_viewer, league=league)

        assert ids(result) == [NORTHEAST, SOUTHWEST]

    def test_league_is_exact_not_a_substring(self, make_deps, real_viewer):
        result = list_divisions(make_deps(), real_viewer, league="Home")

        assert result.error.kind == "not_found"

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("Northeast", [NORTHEAST]),
            ("northEAST", [NORTHEAST]),
            ("new  england", [NEW_ENGLAND, NE_FLEX]),
            ("flex", [NE_FLEX]),
            ("north", [NORTHEAST]),
            ("Homegrown Northeast", [NORTHEAST]),
        ],
    )
    def test_query_matches_part_of_a_division_or_league_name(self, make_deps, real_viewer, query, expected):
        result = list_divisions(make_deps(), real_viewer, query=query)

        assert ids(result) == expected

    def test_filters_combine(self, make_deps, real_viewer):
        """The live question: "who's top of the U15 Northeast table?"."""
        result = list_divisions(make_deps(), real_viewer, age_group="U15", query="Northeast")

        assert ids(result) == [NORTHEAST]
        assert ages(result, NORTHEAST) == [(U15, "U15", 5)]
        assert (result.age_group, result.query, result.league) == ("U15", "Northeast", None)

    def test_league_and_query_combine(self, make_deps, real_viewer):
        result = list_divisions(make_deps(), real_viewer, league="Flex", query="New England")

        assert ids(result) == [NE_FLEX]


class TestNotFound:
    def test_lists_what_exists_at_that_age(self, make_deps, real_viewer):
        result = list_divisions(make_deps(), real_viewer, age_group="U15", query="Northest")

        assert result.error.kind == "not_found"
        assert result.divisions is None
        assert [d.division.id for d in result.alternatives] == [NEW_ENGLAND, NE_FLEX, NORTHEAST]
        assert "at U15" in result.error.message
        assert "Northeast (Homegrown) U15" in result.error.message

    def test_an_age_the_division_does_not_run_lists_the_ages_it_does(self, make_deps, real_viewer):
        result = list_divisions(make_deps(), real_viewer, age_group="U14", query="Northeast")

        assert result.error.kind == "not_found"
        assert [d.division.id for d in result.alternatives] == [NORTHEAST]
        assert [a.name for a in result.alternatives[0].age_groups] == ["U15", "U16"]

    def test_an_unknown_age_falls_back_to_every_division(self, make_deps, real_viewer):
        result = list_divisions(make_deps(), real_viewer, age_group="U9")

        assert result.error.kind == "not_found"
        assert [d.division.id for d in result.alternatives] == [NEW_ENGLAND, NE_FLEX, NORTHEAST, SOUTHWEST]


class TestVisibility:
    def test_a_test_league_division_is_hidden_from_a_real_viewer(self, make_deps, real_viewer):
        result = list_divisions(make_deps(), real_viewer, query="TSC")

        assert result.error.kind == "not_found"
        assert TSC_DIVISION not in [d.division.id for d in result.alternatives]
        assert "TSC Division" not in result.error.message

    def test_a_test_league_division_is_shown_to_a_test_viewer(self, make_deps, test_viewer):
        result = list_divisions(make_deps(), test_viewer, query="TSC")

        assert ids(result) == [TSC_DIVISION]
        assert ages(result, TSC_DIVISION) == [(U15, "U15", 1), (U16, "U16", 1)]

    def test_teams_a_real_viewer_cannot_see_are_not_counted(self, make_deps, real_viewer, test_viewer):
        test_club_team = team(120, "TSC Northeast", 13, REAL_HOMEGROWN, reg(U15, "Northeast", REAL_HOMEGROWN))
        source = FakeTeams([*TEAMS, test_club_team], ALIASES)

        real = list_divisions(make_deps(team_source=source), real_viewer, age_group="U15", query="Northeast")
        test = list_divisions(make_deps(team_source=source), test_viewer, age_group="U15", query="Northeast")

        assert ages(real, NORTHEAST) == [(U15, "U15", 5)]
        assert ages(test, NORTHEAST) == [(U15, "U15", 6)]


class TestArguments:
    @pytest.mark.parametrize("kwargs", [{"age_group": ""}, {"league": "   "}, {"query": ""}])
    def test_blank_filter_means_no_filter(self, make_deps, real_viewer, kwargs):
        assert list_divisions(make_deps(), real_viewer, **kwargs) == list_divisions(make_deps(), real_viewer)

    @pytest.mark.parametrize("kwargs", [{"query": "x" * 101}])
    def test_invalid_args(self, make_deps, real_viewer, kwargs):
        result = list_divisions(make_deps(), real_viewer, **kwargs)

        assert result.error.kind == "invalid_args"
        assert result.divisions is None


class TestFailures:
    def test_a_failed_team_read_is_unavailable_not_an_empty_list(self, make_deps, real_viewer):
        result = list_divisions(make_deps(team_source=FakeTeams([], {}, fail=True)), real_viewer)

        assert result.error.kind == "unavailable"
        assert result.divisions is None

    def test_a_failed_league_read_is_unavailable(self, make_deps, real_viewer):
        result = list_divisions(make_deps(leagues=FakeLeagues(LEAGUES, fail=True)), real_viewer)

        assert result.error.kind == "unavailable"
        assert result.divisions is None


class TestBounded:
    def test_results_are_capped_and_say_so(self, make_deps, real_viewer):
        many = [
            team(
                1000 + i,
                f"Team {i}",
                10,
                REAL_HOMEGROWN,
                {
                    "age_groups": {"id": U15, "name": "U15"},
                    "divisions": {"id": 5000 + i, "name": f"Division {i:03d}", "league_id": REAL_HOMEGROWN},
                },
            )
            for i in range(MAX_DIVISIONS + 5)
        ]

        result = list_divisions(make_deps(team_source=FakeTeams(many, {})), real_viewer)

        assert len(result.divisions) == MAX_DIVISIONS
        assert result.meta.truncated is True
        assert result.divisions[0].division.name == "Division 000"


class TestOverMcp:
    async def test_listed_for_the_read_tier_with_the_model_facing_arguments(self, make_deps):
        async with served(make_deps()) as s:
            async with s.session("legacy") as session:  # read tier and no more
                legacy = await session.list_tools()
            async with s.session("fan", MT_AI_CLIENT) as session:
                via_ai = await session.list_tools()

        tool = next(t for t in legacy.tools if t.name == "list_divisions")
        assert "list_divisions" in {t.name for t in via_ai.tools}
        assert set(tool.input_schema["properties"]) == {"age_group", "league", "query"}
        assert not tool.input_schema.get("required")
        assert {"divisions", "alternatives", "error"} <= set(tool.output_schema["properties"])

    async def test_callable_and_typed(self, make_deps):
        async with served(make_deps()) as s, s.session("fan") as session:
            result = await session.call_tool("list_divisions", {"age_group": "U15", "query": "Northeast"})

        data = result.structured_content
        assert data["error"] is None
        [northeast] = data["divisions"]
        assert northeast["division"] == {"id": NORTHEAST, "name": "Northeast", "league": "Homegrown"}
        assert northeast["age_groups"] == [{"id": U15, "name": "U15", "teams": 5}]

    async def test_the_viewer_is_the_callers_not_an_argument(self, make_deps):
        async with served(make_deps()) as s:
            async with s.session("fan") as session:
                fan = await session.call_tool("list_divisions", {"query": "TSC", "include_test": True})
            async with s.session("test-fan") as session:
                test_user = await session.call_tool("list_divisions", {"query": "TSC"})

        assert fan.structured_content["error"]["kind"] == "not_found"
        assert [d["division"]["id"] for d in test_user.structured_content["divisions"]] == [TSC_DIVISION]


class TestInApp:
    """The live question, end to end: resolve the division, then its table."""

    async def test_division_then_standings_in_process(self, make_deps, real_viewer):
        matches = FakeMatches(standings=standings_result([standings_row(IFA, "IFA", 11, 6)], fixtures=6))
        model = scripted(
            calls_tool("list_divisions", age_group="U15", query="Northeast"),
            calls_tool("get_standings", division_id=NORTHEAST, age_group_id=U15),
            says("IFA lead U15 Northeast."),
        )
        await run_turn(model, make_deps(matches), real_viewer, [], "top of U15 Northeast?", Budget(), session_id="c")

        divisions, standings = model.tool_results()[-2:]
        assert divisions["divisions"][0]["division"]["id"] == NORTHEAST
        assert standings["error"] is None
        assert matches.standings_calls[0]["division_id"] == NORTHEAST

    async def test_over_mcp_too(self, make_deps, real_viewer):
        model = scripted(calls_tool("list_divisions", query="Northeast"), says("."))
        async with served(make_deps()) as s:
            mcp = McpAccess(url=URL, bearer="fan", httpx_client_factory=s.client_factory())
            await run_turn(model, s.deps, real_viewer, [], "divisions?", Budget(), session_id="c", mcp=mcp)

        assert model.tool_results()[-1]["divisions"][0]["division"]["id"] == NORTHEAST

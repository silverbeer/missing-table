"""get_standings (SB-1496): which table, and a table that says what it is made of.

The default world is the scraper's: teams with results and no manager. The
table itself is MatchDAO.get_standings' (tested in test_qualifying_standings);
these tests cover choosing the table, visibility, and failures that must not
read as an empty table.
"""

import pytest
from mt_ai_fake_llm import calls_tool, says, scripted
from mt_ai_fakes import (
    NE_FLEX,
    NORTHEAST,
    PAST_SEASON,
    TSC_DIVISION,
    U15,
    U16,
    FakeLeagues,
    FakeMatches,
    FakeSeasons,
    standings_result,
    standings_row,
)
from mt_mcp_harness import URL, served

from mt_ai.agent import McpAccess, run_turn
from mt_ai.budget import Budget
from mt_ai.tools import get_standings
from mt_mcp.scopes import MT_AI_CLIENT

pytestmark = [pytest.mark.unit, pytest.mark.backend]

BOSTON, IFA, TSC_TEAM, NEFC, SPLIT = 100, 102, 104, 108, 111


def northeast_u15(**coverage) -> FakeMatches:
    return FakeMatches(
        standings=standings_result(
            [
                standings_row(IFA, "IFA", 11, 6, form=["W", "W"], position_change=1),
                standings_row(BOSTON, "Boston United", 10, 3),
                standings_row(NEFC, "NEFC", None, 0),
            ],
            fixtures=6,
            **coverage,
        )
    )


class TestWhichTable:
    def test_a_single_registration_is_the_table(self, make_deps, real_viewer):
        matches = northeast_u15()

        result = get_standings(make_deps(matches), real_viewer, team_id=BOSTON)

        assert result.error is None
        assert (result.age_group.name, result.division.id, result.division.name) == ("U15", NORTHEAST, "Northeast")
        assert result.division.league == "Homegrown"
        [call] = matches.standings_calls
        assert call == {
            "season_id": 7,
            "age_group_id": U15,
            "division_id": NORTHEAST,
            "match_type": "League",
            "include_test": False,
            "raise_on_error": True,
        }

    def test_league_and_flex_at_one_age_resolve_to_the_home_division(self, make_deps, real_viewer):
        """IFA U15 plays Northeast (Homegrown) and a Flex bracket: League is Northeast."""
        result = get_standings(make_deps(northeast_u15()), real_viewer, team_id=IFA)

        assert result.error is None
        assert result.division.id == NORTHEAST

    def test_qualifying_uses_the_home_division_and_passes_the_view_through(self, make_deps, real_viewer):
        matches = northeast_u15()

        result = get_standings(make_deps(matches), real_viewer, team_id=IFA, competition="Qualifying")

        assert result.error is None
        assert result.competition == "qualifying"
        assert matches.standings_calls[0]["match_type"] == "qualifying"
        assert matches.standings_calls[0]["division_id"] == NORTHEAST

    def test_flex_with_two_tables_is_ambiguous_and_lists_them(self, make_deps, real_viewer):
        matches = northeast_u15()

        result = get_standings(make_deps(matches), real_viewer, team_id=IFA, competition="Flex")

        assert result.error.kind == "ambiguous"
        assert result.rows is None
        assert [(o.age_group.id, o.division.id, o.division.league) for o in result.options] == [
            (U15, NORTHEAST, "Homegrown"),
            (U15, NE_FLEX, "Flex"),
        ]
        assert matches.standings_calls == []

    def test_an_option_picked_by_division_resolves(self, make_deps, real_viewer):
        matches = northeast_u15()

        result = get_standings(make_deps(matches), real_viewer, team_id=IFA, division_id=NE_FLEX, competition="Flex")

        assert result.error is None
        assert result.division.league == "Flex"
        assert matches.standings_calls[0]["division_id"] == NE_FLEX

    def test_a_multi_age_team_without_an_age_is_ambiguous(self, make_deps, real_viewer):
        result = get_standings(make_deps(northeast_u15()), real_viewer, team_id=NEFC)

        assert result.error.kind == "ambiguous"
        assert [o.age_group.name for o in result.options] == ["U15", "U16"]

    def test_age_group_id_narrows_it(self, make_deps, real_viewer):
        matches = northeast_u15()

        result = get_standings(make_deps(matches), real_viewer, team_id=NEFC, age_group_id=U16)

        assert result.error is None
        assert result.age_group.name == "U16"
        assert matches.standings_calls[0]["age_group_id"] == U16

    def test_an_age_the_team_does_not_play_is_not_found_with_its_tables(self, make_deps, real_viewer):
        result = get_standings(make_deps(), real_viewer, team_id=BOSTON, age_group_id=U16)

        assert result.error.kind == "not_found"
        assert [(o.age_group.name, o.division.name) for o in result.options] == [("U15", "Northeast")]

    def test_a_division_and_age_group_without_a_team(self, make_deps, real_viewer):
        matches = northeast_u15()

        result = get_standings(make_deps(matches), real_viewer, division_id=NORTHEAST, age_group_id=U15)

        assert result.error is None
        assert result.team_id is None
        assert result.division.name == "Northeast"
        assert not any(row.is_requested_team for row in result.rows)


class TestVisibility:
    def test_an_unknown_team_is_not_found(self, make_deps, real_viewer):
        result = get_standings(make_deps(), real_viewer, team_id=9999)

        assert result.error.kind == "not_found"

    def test_a_test_team_is_not_found_for_a_real_viewer(self, make_deps, real_viewer):
        result = get_standings(make_deps(), real_viewer, team_id=TSC_TEAM)

        assert result.error.kind == "not_found"
        assert "TSC" not in result.error.message

    def test_a_test_competition_is_invisible_to_a_real_viewer(self, make_deps, real_viewer, test_viewer):
        """Split Comp FC plays U15 in Northeast and in a test league's division."""
        real = get_standings(make_deps(northeast_u15()), real_viewer, team_id=SPLIT)
        test = get_standings(make_deps(northeast_u15()), test_viewer, team_id=SPLIT)

        assert real.error is None and real.division.id == NORTHEAST
        assert test.error.kind == "ambiguous"
        assert {o.division.id for o in test.options} == {NORTHEAST, TSC_DIVISION}

    def test_a_test_division_is_not_found_for_a_real_viewer(self, make_deps, real_viewer, test_viewer):
        real = get_standings(make_deps(), real_viewer, division_id=TSC_DIVISION, age_group_id=U15)
        test = get_standings(make_deps(), test_viewer, division_id=TSC_DIVISION, age_group_id=U15)

        assert real.error.kind == "not_found"
        assert test.error is None

    def test_the_viewer_decides_whether_test_matches_count(self, make_deps, test_viewer):
        matches = northeast_u15()

        get_standings(make_deps(matches), test_viewer, team_id=BOSTON)

        assert matches.standings_calls[0]["include_test"] is True


class TestArguments:
    @pytest.mark.parametrize(
        "kwargs",
        [{}, {"age_group_id": U15}, {"division_id": NORTHEAST}, {"team_id": BOSTON, "competition": "  "}],
    )
    def test_invalid_args(self, make_deps, real_viewer, kwargs):
        matches = FakeMatches()

        result = get_standings(make_deps(matches), real_viewer, **kwargs)

        assert result.error.kind == "invalid_args"
        assert result.rows is None
        assert matches.standings_calls == []


class TestSeason:
    def test_defaults_to_the_current_season(self, make_deps, real_viewer):
        result = get_standings(make_deps(northeast_u15()), real_viewer, team_id=BOSTON)

        assert (result.season.id, result.season.name) == (7, "2026-2027")

    def test_without_a_current_season_falls_back_to_the_newest_like_api_table(self, make_deps, real_viewer):
        seasons = FakeSeasons(current=None, seasons=[PAST_SEASON])

        result = get_standings(make_deps(northeast_u15(), seasons=seasons), real_viewer, team_id=BOSTON)

        assert result.season.name == "2025-2026"

    def test_a_past_season_by_id(self, make_deps, real_viewer):
        matches = northeast_u15()

        result = get_standings(make_deps(matches), real_viewer, team_id=BOSTON, season_id=PAST_SEASON["id"])

        assert result.season.name == "2025-2026"
        assert matches.standings_calls[0]["season_id"] == PAST_SEASON["id"]

    def test_an_unknown_season_is_not_found(self, make_deps, real_viewer):
        result = get_standings(make_deps(northeast_u15()), real_viewer, team_id=BOSTON, season_id=99)

        assert result.error.kind == "not_found"

    def test_no_seasons_at_all_is_unavailable_not_empty(self, make_deps, real_viewer):
        seasons = FakeSeasons(current=None, seasons=[])

        result = get_standings(make_deps(northeast_u15(), seasons=seasons), real_viewer, team_id=BOSTON)

        assert result.error.kind == "unavailable"
        assert result.rows is None


class TestTheTable:
    def test_rows_keep_table_order_and_flag_the_requested_team(self, make_deps, real_viewer):
        result = get_standings(make_deps(northeast_u15()), real_viewer, team_id=BOSTON)

        assert [(r.position, r.team.name, r.points) for r in result.rows] == [
            (1, "IFA", 6),
            (2, "Boston United", 3),
            (3, "NEFC", 0),
        ]
        assert [r.is_requested_team for r in result.rows] == [False, True, False]
        ifa = result.rows[0]
        assert (ifa.team.id, ifa.team.club_name, ifa.form, ifa.position_change) == (IFA, "IFA", ["W", "W"], 1)
        # A team with no club is absent, not an empty string.
        assert result.rows[2].team.club_name is None

    def test_coverage_ships_with_the_table(self, make_deps, real_viewer):
        result = get_standings(make_deps(northeast_u15()), real_viewer, team_id=BOSTON)

        assert result.coverage.fixtures == 6
        assert result.coverage.matches_counted == 3
        assert result.meta.coverage == "3 played of 6 scheduled"

    def test_a_combined_view_says_it_counts_outside_opponents(self, make_deps, real_viewer):
        matches = northeast_u15(
            match_type="qualifying",
            competitions=["Flex", "League"],
            counted_by_competition={"Flex": 1, "League": 2},
            matches_vs_outside_table=1,
            teams_outside_table=1,
            shootout_points=["Flex"],
        )

        result = get_standings(make_deps(matches), real_viewer, team_id=IFA, competition="qualifying")

        assert result.coverage.competitions == ["Flex", "League"]
        assert result.coverage.shootout_points == ["Flex"]
        assert result.meta.coverage == "3 played of 6 scheduled; 1 against 1 teams outside this table"

    def test_nothing_played_yet_is_an_empty_table_with_fixtures(self, make_deps, real_viewer):
        """August: the schedule is loaded, no match is played. [] plus fixtures, not an error."""
        matches = FakeMatches(standings=standings_result([], fixtures=16))

        result = get_standings(make_deps(matches), real_viewer, team_id=BOSTON)

        assert result.error is None
        assert result.rows == []
        assert (result.coverage.fixtures, result.coverage.matches_counted) == (16, 0)


class TestFailures:
    def test_a_failed_standings_read_is_unavailable_not_an_empty_table(self, make_deps, real_viewer):
        """Without raise_on_error the DAO returns an empty table on failure — the pun to avoid."""
        failing = FakeMatches(fail=True)

        result = get_standings(make_deps(failing), real_viewer, team_id=BOSTON)

        assert failing.standings_calls[0]["raise_on_error"] is True
        assert result.error.kind == "unavailable"
        assert result.rows is None
        assert result.coverage is None

    def test_a_failed_league_read_is_unavailable(self, make_deps, real_viewer):
        result = get_standings(make_deps(leagues=FakeLeagues([], fail=True)), real_viewer, team_id=BOSTON)

        assert result.error.kind == "unavailable"


class TestOverMcp:
    async def test_listed_for_the_read_tier_with_the_model_facing_arguments(self, make_deps):
        async with served(make_deps()) as s:
            async with s.session("legacy") as session:  # read tier and no more
                legacy = await session.list_tools()
            async with s.session("fan", MT_AI_CLIENT) as session:
                via_ai = await session.list_tools()

        tool = next(t for t in legacy.tools if t.name == "get_standings")
        assert "get_standings" in {t.name for t in via_ai.tools}
        assert set(tool.input_schema["properties"]) == {
            "team_id",
            "age_group_id",
            "division_id",
            "competition",
            "season_id",
        }
        assert not tool.input_schema.get("required")
        assert {"rows", "coverage", "options", "error", "season"} <= set(tool.output_schema["properties"])

    async def test_callable_and_typed(self, make_deps):
        async with served(make_deps(northeast_u15())) as s, s.session("fan") as session:
            result = await session.call_tool("get_standings", {"team_id": BOSTON})

        data = result.structured_content
        assert data["error"] is None
        assert [r["team"]["name"] for r in data["rows"]] == ["IFA", "Boston United", "NEFC"]
        assert data["coverage"]["fixtures"] == 6

    async def test_the_viewer_is_the_callers_not_an_argument(self, make_deps):
        matches = northeast_u15()
        async with served(make_deps(matches)) as s:
            async with s.session("fan") as session:
                fan = await session.call_tool("get_standings", {"team_id": SPLIT, "include_test": True})
            async with s.session("test-fan") as session:
                test_user = await session.call_tool("get_standings", {"team_id": BOSTON})

        # The fan's extra include_test is ignored: the test competition stays hidden.
        assert fan.structured_content["division"]["id"] == NORTHEAST
        assert matches.standings_calls[0]["include_test"] is False
        assert matches.standings_calls[1]["include_test"] is True
        assert test_user.structured_content["error"] is None


class TestInApp:
    """MT_MCP_ENABLED off: the same tool registered in-process."""

    async def test_my_team_standings_in_process(self, make_deps, real_viewer):
        model = scripted(
            calls_tool("search_teams", query="Boston United", age_group="U15"),
            calls_tool("get_standings", team_id=BOSTON, age_group_id=U15),
            says("Boston United are 2nd."),
        )
        await run_turn(model, make_deps(northeast_u15()), real_viewer, [], "standings?", Budget(), session_id="c")

        standings = model.tool_results()[-1]
        assert standings["error"] is None
        assert [r["is_requested_team"] for r in standings["rows"]] == [False, True, False]

    async def test_over_mcp_too(self, make_deps, real_viewer):
        model = scripted(calls_tool("get_standings", team_id=BOSTON), says("."))
        async with served(make_deps(northeast_u15())) as s:
            mcp = McpAccess(url=URL, bearer="fan", httpx_client_factory=s.client_factory())
            await run_turn(model, s.deps, real_viewer, [], "standings?", Budget(), session_id="c", mcp=mcp)

        assert model.tool_results()[-1]["division"]["id"] == NORTHEAST

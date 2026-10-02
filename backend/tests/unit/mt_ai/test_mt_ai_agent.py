"""mt_ai.agent (SB-1143): the real ADK runner and the real search_teams tool.

Only the model is scripted. Everything between it and the tool — ADK's
function declaration, dispatch, callbacks and the function_response handed
back — is the production code path.
"""

import pytest
from mt_ai_fake_llm import ModelDown, calls_tool, says, scripted
from mt_ai_fakes import FakeLeagues, FakeMatches, match_row

from mt_ai.agent import AGENT_VERSION, INSTRUCTION, AIRunError, HistoryTurn, run_turn
from mt_ai.budget import Budget

pytestmark = [pytest.mark.unit, pytest.mark.backend]


async def run(model, deps, viewer, message="Find IFA", history=(), budget=None):
    return await run_turn(model, deps, viewer, list(history), message, budget or Budget(), session_id="conv-test")


class TestToolWiring:
    async def test_both_tools_are_declared_to_the_model(self, make_deps, real_viewer):
        model = scripted(says("Hello"))
        await run(model, make_deps(), real_viewer, message="hi")

        tools = model.declared_tools()
        assert list(tools) == ["search_teams", "get_upcoming_matches"]
        assert tools["search_teams"]["required"] == ["query"]
        assert set(tools["search_teams"]["properties"]) == {"query", "age_group"}
        # The viewer and the clock are the server's, never the model's.
        assert tools["get_upcoming_matches"]["required"] == ["team_id"]
        assert set(tools["get_upcoming_matches"]["properties"]) == {"team_id", "age_group_id", "limit"}

    async def test_search_then_upcoming_matches(self, make_deps, real_viewer):
        """SB-1152: "When does IFA U15 play next?" resolves the team, then fetches its fixtures."""
        model = scripted(
            calls_tool("search_teams", query="IFA", age_group="U15"),
            calls_tool("get_upcoming_matches", team_id=102, age_group_id=15),
            says("IFA U15 plays on 1 Jan 2099."),
        )
        # Far in the future, so the real clock always sees it as upcoming.
        deps = make_deps(matches=FakeMatches([match_row(9, "2099-01-01")]))

        outcome = await run(model, deps, real_viewer, message="When does IFA U15 play next?")

        # Each request repeats the earlier results; the last request shows both.
        search, upcoming = model.tool_results()[-2:]
        assert search["team"]["team_id"] == 102
        assert upcoming["team_id"] == 102
        assert upcoming["error"] is None
        assert [m["match_date"] for m in upcoming["matches"]] == ["2099-01-01"]
        assert upcoming["today"] and upcoming["timezone"]
        assert outcome.answer == "IFA U15 plays on 1 Jan 2099."
        assert (outcome.llm_calls, outcome.tool_calls) == (3, 2)

    async def test_nothing_scheduled_reaches_the_model_as_an_empty_list(self, make_deps, real_viewer):
        """[] (checked, none) must not look like null (couldn't check)."""
        model = scripted(calls_tool("get_upcoming_matches", team_id=102), says("Nothing scheduled yet."))

        await run(model, make_deps(matches=FakeMatches([])), real_viewer)

        result = model.tool_results()[0]
        assert result["matches"] == []
        assert result["error"] is None

    async def test_upcoming_matches_cannot_reach_hidden_test_teams(self, make_deps, real_viewer):
        """The viewer is bound by the server for this tool too."""
        model = scripted(calls_tool("get_upcoming_matches", team_id=104), says("Not found."))

        await run(model, make_deps(), real_viewer)

        result = model.tool_results()[0]
        assert result["matches"] is None
        assert result["error"]["kind"] == "not_found"

    async def test_a_team_at_another_age_reaches_the_model_with_its_ages(self, make_deps, real_viewer):
        """SB-1155: "Find the IFA U19 team" → not found at U19, but IFA plays U15."""
        model = scripted(
            calls_tool("search_teams", query="IFA", age_group="U19"), says("IFA has no U19; it plays U15.")
        )

        await run(model, make_deps(), real_viewer, message="Find the IFA U19 team")

        result = model.tool_results()[0]
        assert result["status"] == "not_found"
        assert result["other_ages"] == ["U15"]

    def test_the_instruction_says_how_to_use_both_tools(self):
        assert "get_upcoming_matches" in INSTRUCTION
        assert "search_teams" in INSTRUCTION
        assert "other_ages" in INSTRUCTION
        assert AGENT_VERSION == "mt-assistant/0.2.1"

    async def test_model_calls_tool_and_typed_result_reaches_it(self, make_deps, real_viewer):
        model = scripted(calls_tool("search_teams", query="IFA"), says("IFA plays U15 in the Northeast."))

        outcome = await run(model, make_deps(), real_viewer)

        [result] = model.tool_results()
        assert result["status"] == "resolved"
        assert result["team"]["team_id"] == 102
        assert result["team"]["age_group"] == {"id": 15, "name": "U15"}
        assert outcome.status == "ok"
        assert outcome.answer == "IFA plays U15 in the Northeast."
        assert (outcome.llm_calls, outcome.tool_calls) == (2, 1)

    async def test_age_group_argument_is_passed_through(self, make_deps, real_viewer):
        model = scripted(calls_tool("search_teams", query="NEFC", age_group="U16"), says("ok"))
        await run(model, make_deps(), real_viewer)

        assert model.tool_results()[0]["team"]["age_group"]["name"] == "U16"

    async def test_ambiguity_reaches_the_model_intact(self, make_deps, real_viewer):
        model = scripted(calls_tool("search_teams", query="NEFC"), says("Which age group?"))
        await run(model, make_deps(), real_viewer)

        result = model.tool_results()[0]
        assert result["status"] == "ambiguous"
        assert len(result["candidates"]) == 2

    async def test_the_viewer_is_bound_by_the_server_not_the_model(self, make_deps, real_viewer, test_viewer):
        """The model can't widen visibility: test teams stay hidden for a real user."""
        real_model = scripted(calls_tool("search_teams", query="TSC Test Team"), says("Not found."))
        test_model = scripted(calls_tool("search_teams", query="TSC Test Team"), says("Found."))

        await run(real_model, make_deps(), real_viewer)
        await run(test_model, make_deps(), test_viewer)

        assert real_model.tool_results()[0]["status"] == "not_found"
        assert test_model.tool_results()[0]["status"] == "resolved"

    async def test_a_tool_failure_is_data_the_model_can_explain(self, make_deps, real_viewer):
        model = scripted(calls_tool("search_teams", query="IFA"), says("Team data is unavailable right now."))

        outcome = await run(model, make_deps(leagues=FakeLeagues([], fail=True)), real_viewer)

        assert model.tool_results()[0]["error"]["kind"] == "unavailable"
        assert outcome.status == "ok"


class TestBudget:
    async def test_model_call_limit_stops_the_run(self, make_deps, teams, real_viewer):
        model = scripted(calls_tool("search_teams", query="IFA"), says("never reached"))

        outcome = await run(model, make_deps(), real_viewer, budget=Budget(max_llm_calls=1))

        assert outcome.status == "budget_exhausted"
        assert outcome.exhausted == "llm_calls"
        assert outcome.answer is None
        assert len(model.requests) == 1  # the second model call never happened
        assert model.script  # its reply was never consumed

    async def test_tool_call_limit_stops_the_run_before_the_extra_tool(self, make_deps, teams, real_viewer):
        model = scripted(
            calls_tool("search_teams", query="IFA"),
            calls_tool("search_teams", query="NEFC"),
            says("never reached"),
        )

        outcome = await run(model, make_deps(), real_viewer, budget=Budget(max_llm_calls=5, max_tool_calls=1))

        assert outcome.status == "budget_exhausted"
        assert outcome.exhausted == "tool_calls"
        assert teams.team_reads == 1  # the second search never executed
        assert outcome.tool_calls == 1
        assert len(model.requests) == 2

    async def test_zero_tool_budget_means_no_tool_runs(self, make_deps, teams, real_viewer):
        model = scripted(calls_tool("search_teams", query="IFA"), says("never reached"))

        outcome = await run(model, make_deps(), real_viewer, budget=Budget(max_tool_calls=0))

        assert outcome.exhausted == "tool_calls"
        assert teams.team_reads == 0

    def test_budget_limits_must_be_sane(self):
        with pytest.raises(ValueError):
            Budget(max_llm_calls=0)


class TestHistoryAndFailures:
    async def test_previous_turns_are_shown_to_the_model(self, make_deps, real_viewer):
        model = scripted(says("It's in the Northeast division."))
        history = [HistoryTurn(user="Find IFA", assistant="IFA plays U15.")]

        await run(model, make_deps(), real_viewer, message="Which division?", history=history)

        assert model.texts_seen() == [
            ("user", "Find IFA"),
            ("model", "IFA plays U15."),
            ("user", "Which division?"),
        ]

    async def test_a_model_error_is_an_ai_run_error(self, make_deps, real_viewer):
        with pytest.raises(AIRunError, match="ModelDown"):
            await run(scripted(ModelDown("503 from provider")), make_deps(), real_viewer)

    async def test_an_empty_answer_is_an_ai_run_error(self, make_deps, real_viewer):
        model = scripted(says("   "))
        with pytest.raises(AIRunError, match="no text"):
            await run(model, make_deps(), real_viewer)
        assert len(model.requests) == 1

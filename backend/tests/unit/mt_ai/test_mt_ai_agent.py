"""mt_ai.agent (SB-1143): the real ADK runner and the real search_teams tool.

Only the model is scripted. Everything between it and the tool — ADK's
function declaration, dispatch, callbacks and the function_response handed
back — is the production code path.
"""

import pytest
from mt_ai_fake_llm import ModelDown, calls_tool, says, scripted
from mt_ai_fakes import FakeLeagues

from mt_ai.agent import AIRunError, HistoryTurn, run_turn
from mt_ai.budget import Budget

pytestmark = [pytest.mark.unit, pytest.mark.backend]


async def run(model, deps, viewer, message="Find IFA", history=(), budget=None):
    return await run_turn(model, deps, viewer, list(history), message, budget or Budget(), session_id="conv-test")


class TestToolWiring:
    async def test_search_teams_is_declared_to_the_model(self, make_deps, real_viewer):
        model = scripted(says("Hello"))
        await run(model, make_deps(), real_viewer, message="hi")

        tools = model.declared_tools()
        assert list(tools) == ["search_teams"]
        assert tools["search_teams"]["required"] == ["query"]
        assert set(tools["search_teams"]["properties"]) == {"query", "age_group"}

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

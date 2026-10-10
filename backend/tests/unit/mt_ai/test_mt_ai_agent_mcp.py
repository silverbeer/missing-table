"""MT AI's tools over mt-mcp (SB-1302, SB-1303).

The real ADK runner calls the real mt-mcp app in-process (ASGI transport): only
the model is scripted and the token check is a fake. This is the path a
production turn takes with MT_MCP_ENABLED.
"""

import pytest
from mt_ai_fake_llm import InMemoryStore, calls_tool, says, scripted
from mt_ai_fakes import FakeMatches, match_row
from mt_mcp_harness import URL, served

from mt_ai.agent import McpAccess, run_turn, unwrap_mcp_result
from mt_ai.budget import Budget
from mt_ai.service import ChatService

pytestmark = [pytest.mark.unit, pytest.mark.backend]


async def run_over_mcp(s, model, viewer, token="fan", message="Find IFA", budget=None):
    mcp = McpAccess(url=URL, bearer=token, httpx_client_factory=s.client_factory())
    return await run_turn(model, s.deps, viewer, [], message, budget or Budget(), session_id="conv-mcp", mcp=mcp)


class TestOverMcp:
    async def test_the_model_sees_the_same_tools_as_in_process(self, make_deps, real_viewer):
        model = scripted(says("Hello"))
        async with served(make_deps()) as s:
            await run_over_mcp(s, model, real_viewer, message="hi")

        tools = model.declared_tools()
        assert sorted(tools) == ["get_upcoming_matches", "search_teams"]
        assert tools["search_teams"]["required"] == ["query"]
        assert set(tools["search_teams"]["properties"]) == {"query", "age_group"}

    async def test_search_then_upcoming_both_over_mcp(self, make_deps, real_viewer):
        model = scripted(
            calls_tool("search_teams", query="IFA", age_group="U15"),
            calls_tool("get_upcoming_matches", team_id=102, age_group_id=15),
            says("IFA U15 plays on 1 Jan 2099."),
        )
        async with served(make_deps(matches=FakeMatches([match_row(9, "2099-01-01")]))) as s:
            outcome = await run_over_mcp(s, model, real_viewer, message="When does IFA U15 play next?")

        search, upcoming = model.tool_results()[-2:]
        # Unwrapped: the model sees the tool's own result, not an MCP envelope.
        for result in (search, upcoming):
            assert "structuredContent" not in result and "content" not in result
        assert search["status"] == "resolved"
        assert search["team"]["team_id"] == 102
        assert upcoming["matches"][0]["match_date"] == "2099-01-01"
        assert upcoming["today"] and upcoming["timezone"]
        assert outcome.answer == "IFA U15 plays on 1 Jan 2099."
        assert (outcome.llm_calls, outcome.tool_calls) == (3, 2)

    async def test_the_trace_records_mcp_calls_like_in_process_ones(self, make_deps, real_viewer):
        model = scripted(calls_tool("search_teams", query="IFA"), says("Found."))
        async with served(make_deps()) as s:
            outcome = await run_over_mcp(s, model, real_viewer)

        (call,) = outcome.trace
        assert call.tool_name == "search_teams"
        assert call.args == {"query": "IFA"}
        assert call.result["status"] == "resolved"
        assert call.error_kind is None
        assert call.duration_ms is not None

    async def test_the_budget_guard_counts_mcp_calls(self, make_deps, real_viewer):
        model = scripted(
            calls_tool("search_teams", query="IFA"),
            calls_tool("search_teams", query="NEFC"),
            says("unreachable"),
        )
        async with served(make_deps()) as s:
            outcome = await run_over_mcp(s, model, real_viewer, budget=Budget(max_tool_calls=1))

        assert outcome.status == "budget_exhausted"
        assert outcome.exhausted == "tool_calls"

    async def test_visibility_is_decided_by_the_token_not_the_in_process_viewer(self, make_deps, real_viewer):
        """A test user's token sees the TSC world even though this process passed a real viewer."""
        async with served(make_deps()) as s:
            as_fan = scripted(calls_tool("search_teams", query="TSC Test Team"), says("."))
            await run_over_mcp(s, as_fan, real_viewer, token="fan")
            as_test_user = scripted(calls_tool("search_teams", query="TSC Test Team"), says("."))
            await run_over_mcp(s, as_test_user, real_viewer, token="test-fan")

        assert as_fan.tool_results()[0]["status"] == "not_found"
        assert as_test_user.tool_results()[0]["status"] == "resolved"

    async def test_mt_ai_identifies_itself_as_the_mt_ai_client(self, make_deps, real_viewer):
        """The X-MT-Client header is what caps MT AI at the read tiers on the server."""
        seen: list[str | None] = []
        async with served(make_deps()) as s:
            inner = s.app

            async def spy(scope, receive, send):
                if scope["type"] == "http":
                    seen.append(dict(scope["headers"]).get(b"x-mt-client", b"").decode() or None)
                await inner(scope, receive, send)

            s.app = spy
            await run_over_mcp(s, scripted(calls_tool("search_teams", query="IFA"), says(".")), real_viewer)

        assert seen and set(seen) == {"mt-ai"}

    async def test_upcoming_over_mcp_keeps_empty_apart_from_unavailable(self, make_deps, real_viewer):
        """[] (checked, none) must still not look like null (couldn't check) after the MCP hop."""
        async with served(make_deps(matches=FakeMatches([]))) as s:
            empty = scripted(calls_tool("get_upcoming_matches", team_id=102), says("."))
            await run_over_mcp(s, empty, real_viewer)
        async with served(make_deps(matches=FakeMatches(fail=True))) as s:
            down = scripted(calls_tool("get_upcoming_matches", team_id=102), says("."))
            await run_over_mcp(s, down, real_viewer)

        assert empty.tool_results()[0]["matches"] == []
        assert empty.tool_results()[0]["error"] is None
        assert down.tool_results()[0]["matches"] is None
        assert down.tool_results()[0]["error"]["kind"] == "unavailable"

    async def test_upcoming_over_mcp_cannot_reach_hidden_test_teams(self, make_deps, real_viewer):
        async with served(make_deps()) as s:
            model = scripted(calls_tool("get_upcoming_matches", team_id=104), says("Not found."))
            await run_over_mcp(s, model, real_viewer, token="fan")

        result = model.tool_results()[0]
        assert result["matches"] is None
        assert result["error"]["kind"] == "not_found"


class TestUnwrap:
    def test_structured_content_is_the_result(self):
        wrapped = {"content": [{"type": "text", "text": "{}"}], "structuredContent": {"status": "resolved"}}

        assert unwrap_mcp_result(wrapped) == {"status": "resolved"}

    def test_a_protocol_error_becomes_a_tool_error(self):
        wrapped = {"content": [{"type": "text", "text": "Unknown tool: x"}], "isError": True}

        assert unwrap_mcp_result(wrapped) == {"error": {"kind": "unavailable", "message": "Unknown tool: x"}}

    def test_text_only_json_is_parsed(self):
        assert unwrap_mcp_result({"content": [{"type": "text", "text": '{"a": 1}'}]}) == {"a": 1}

    def test_plain_text_is_kept(self):
        assert unwrap_mcp_result({"content": [{"type": "text", "text": "hi"}]}) == {"value": "hi"}

    def test_an_in_process_result_is_left_alone(self):
        result = {"status": "resolved", "team": None}

        assert unwrap_mcp_result(result) is result


class TestServiceForwardsTheToken:
    async def _chat(self, make_deps, mcp_url, bearer):
        seen: dict = {}

        async def run(*args, **kwargs):
            seen.update(kwargs)
            from mt_ai.agent import TurnOutcome

            return TurnOutcome("ok", "answer", 1, 0)

        service = ChatService(InMemoryStore(), make_deps(), "model", run=run, mcp_url=mcp_url)
        await service.chat({"user_id": "u1", "role": "team-fan"}, "hi", None, bearer=bearer)
        return seen

    async def test_with_mt_mcp_on_the_callers_token_is_forwarded(self, make_deps):
        seen = await self._chat(make_deps, "http://127.0.0.1:8000/mcp/", "tok")

        assert seen["mcp"].bearer == "tok"
        assert seen["mcp"].url == "http://127.0.0.1:8000/mcp/"

    @pytest.mark.parametrize(("mcp_url", "bearer"), [(None, "tok"), ("http://x/mcp/", None)])
    async def test_without_both_every_tool_stays_in_process(self, make_deps, mcp_url, bearer):
        seen = await self._chat(make_deps, mcp_url, bearer)

        assert "mcp" not in seen


def test_the_google_mtls_probe_is_off_by_default():
    """Left on, ADK probes for Google credentials before each MCP session: a 3-10 s
    stall per turn off-GCP (found building SB-1302)."""
    import os

    import mt_ai.agent  # noqa: F401  (sets the default)

    assert os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] == "false"

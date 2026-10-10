"""mt-mcp over streamable HTTP (SB-1302): auth, tier gate, search_teams, observability.

The real app runs in-process (see mt_mcp_harness). The default world is the
scraper's: teams with no manager, no roster and no logged events.
"""

import pytest
from mt_ai_fakes import FakeMatches, FakeTeams, match_row
from mt_mcp_harness import MCP_HEADERS, initialize_body, served

from mt_mcp.observe import TOOL_CALLS
from mt_mcp.scopes import MT_AI_CLIENT
from mt_mcp.server import TOOL_TIERS, UNAVAILABLE

pytestmark = [pytest.mark.unit, pytest.mark.backend]

READ_TOOLS = {"search_teams", "get_upcoming_matches"}
ADMIN_TOOLS = {"list_ingest_failures", "resolve_ingest_failure"}


class TestAuthentication:
    async def test_no_token_is_401(self, make_deps):
        async with served(make_deps()) as s, s.http() as http:
            response = await http.post("/", json=initialize_body(), headers=MCP_HEADERS)

        assert response.status_code == 401

    @pytest.mark.parametrize("token", ["garbage", "service-account-jwt"])
    async def test_a_token_mt_does_not_accept_is_401(self, make_deps, token):
        async with served(make_deps()) as s, s.http({"Authorization": f"Bearer {token}"}) as http:
            response = await http.post("/", json=initialize_body(), headers=MCP_HEADERS)

        assert response.status_code == 401

    async def test_an_unknown_host_is_refused(self, make_deps):
        """DNS-rebinding protection stays on: only configured Host headers reach the server."""
        headers = {"Authorization": "Bearer fan", "Host": "evil.example"}
        async with served(make_deps()) as s, s.http(headers) as http:
            response = await http.post("/", json=initialize_body(), headers=MCP_HEADERS)

        assert response.status_code == 421

    @pytest.mark.parametrize("token", ["fan", "api"])
    async def test_a_session_or_api_account_token_connects(self, make_deps, token):
        async with served(make_deps()) as s, s.session(token) as session:
            tools = await session.list_tools()

        assert {t.name for t in tools.tools} == READ_TOOLS


class TestTierGate:
    @pytest.mark.parametrize(
        "token", ["admin", "club-mgr", "team-mgr", "player", "fan", "club-fan", "legacy", "test-fan"]
    )
    @pytest.mark.parametrize("client", [None, MT_AI_CLIENT])
    async def test_every_role_sees_the_read_tier_and_only_admins_see_admin_tools(self, make_deps, token, client):
        async with served(make_deps()) as s, s.session(token, client) as session:
            tools = await session.list_tools()

        # MT AI's client cap removes admin tools even for an admin.
        expected = READ_TOOLS | ADMIN_TOOLS if token == "admin" and client is None else READ_TOOLS
        assert {t.name for t in tools.tools} == expected

    async def test_a_tool_outside_the_callers_tiers_is_neither_listed_nor_callable(self, make_deps, monkeypatch):
        """Gate check with a tool from a tier a fan does not have; reads as an unknown tool."""
        monkeypatch.setitem(TOOL_TIERS, "search_teams", "admin")
        monkeypatch.setitem(TOOL_TIERS, "get_upcoming_matches", "admin")
        for name in ADMIN_TOOLS:
            monkeypatch.delitem(TOOL_TIERS, name)

        async with served(make_deps()) as s:
            async with s.session("fan") as session:
                listed = await session.list_tools()
                refused = await session.call_tool("search_teams", {"query": "IFA"})
                unknown = await session.call_tool("no_such_tool", {})
            async with s.session("admin") as session:
                admin_listed = await session.list_tools()
            async with s.session("admin", MT_AI_CLIENT) as session:
                via_ai = await session.list_tools()

        assert listed.tools == []
        assert refused.is_error and refused.content[0].text == "Unknown tool: search_teams"
        assert unknown.is_error and unknown.content[0].text == "Unknown tool: no_such_tool"
        assert {t.name for t in admin_listed.tools} == READ_TOOLS
        # An admin chatting through MT AI still does not get admin tools.
        assert via_ai.tools == []


class TestSearchTeams:
    async def test_the_schemas_come_from_the_pydantic_models(self, make_deps):
        async with served(make_deps()) as s, s.session("fan") as session:
            tool = next(t for t in (await session.list_tools()).tools if t.name == "search_teams")

        assert tool.input_schema["required"] == ["query"]
        assert set(tool.input_schema["properties"]) == {"query", "age_group"}
        assert set(tool.output_schema["properties"]) >= {"status", "team", "candidates", "other_ages", "error"}

    async def test_an_unclaimed_team_resolves_with_structured_content(self, make_deps):
        """The default team: scraped, no manager. A full answer anyway."""
        async with served(make_deps()) as s, s.session("fan") as session:
            result = await session.call_tool("search_teams", {"query": "IFA", "age_group": "U15"})

        assert not result.is_error
        data = result.structured_content
        assert data["status"] == "resolved"
        assert data["team"]["team_id"] == 102
        assert {r["league"] for r in data["team"]["registrations"]} == {"Homegrown", "Flex"}

    async def test_test_teams_are_invisible_to_real_users(self, make_deps):
        async with served(make_deps()) as s:
            async with s.session("fan") as session:
                fan = await session.call_tool("search_teams", {"query": "TSC Test Team"})
            async with s.session("test-fan") as session:
                test_user = await session.call_tool("search_teams", {"query": "TSC Test Team"})
            async with s.session("admin") as session:
                admin = await session.call_tool("search_teams", {"query": "TSC Test Team"})

        assert fan.structured_content["status"] == "not_found"
        assert test_user.structured_content["status"] == "resolved"
        assert admin.structured_content["status"] == "resolved"

    async def test_visibility_cannot_be_argued_for(self, make_deps):
        """The viewer is the token's, not an argument: an extra argument is ignored."""
        async with served(make_deps()) as s, s.session("fan") as session:
            result = await session.call_tool("search_teams", {"query": "TSC Test Team", "include_test": True})

        assert result.structured_content["status"] == "not_found"

    async def test_a_data_failure_is_a_typed_unavailable_result(self, make_deps, teams):
        async with served(make_deps(team_source=FakeTeams(teams.teams, teams.aliases, fail=True))) as s:
            async with s.session("fan") as session:
                result = await session.call_tool("search_teams", {"query": "IFA"})

        assert result.structured_content["error"]["kind"] == "unavailable"

    async def test_an_unexpected_crash_reaches_the_client_as_a_generic_message(self, make_deps):
        """Left alone, the SDK would send str(exc) — here, a config name — to the client."""

        def broken_deps():
            raise KeyError("SUPABASE_SERVICE_KEY")

        async with served(make_deps()) as s, s.session("fan") as session:
            s.provide = broken_deps
            result = await session.call_tool("search_teams", {"query": "IFA"})

        assert result.is_error
        assert result.content[0].text.endswith(UNAVAILABLE)
        assert "SUPABASE" not in result.content[0].text


class TestUpcomingMatches:
    async def test_schemas(self, make_deps):
        async with served(make_deps()) as s, s.session("fan") as session:
            tool = next(t for t in (await session.list_tools()).tools if t.name == "get_upcoming_matches")

        assert tool.input_schema["required"] == ["team_id"]
        assert set(tool.input_schema["properties"]) == {"team_id", "age_group_id", "limit"}
        assert {"matches", "error", "today", "timezone"} <= set(tool.output_schema["properties"])

    async def test_an_unclaimed_teams_fixtures_come_back(self, make_deps):
        async with served(make_deps(matches=FakeMatches([match_row(9, "2099-01-01")]))) as s:
            async with s.session("fan") as session:
                result = await session.call_tool("get_upcoming_matches", {"team_id": 102, "age_group_id": 15})

        data = result.structured_content
        assert data["error"] is None
        assert [m["match_date"] for m in data["matches"]] == ["2099-01-01"]

    async def test_a_test_teams_fixtures_are_visible_only_to_test_viewers(self, make_deps):
        async with served(make_deps()) as s:
            async with s.session("fan") as session:
                fan = await session.call_tool("get_upcoming_matches", {"team_id": 104})
            async with s.session("admin") as session:
                admin = await session.call_tool("get_upcoming_matches", {"team_id": 104})

        assert fan.structured_content["error"]["kind"] == "not_found"
        assert admin.structured_content["error"] is None


def _count(tool: str, client: str, role: str, outcome: str) -> float:
    return TOOL_CALLS.labels(tool=tool, client=client, role=role, outcome=outcome)._value.get()


class TestObservability:
    async def test_each_call_is_counted_with_the_tools_own_verdict(self, make_deps):
        before = {o: _count("search_teams", "mt-ai", "team-fan", o) for o in ("resolved", "not_found", "ambiguous")}

        async with served(make_deps()) as s, s.session("fan", MT_AI_CLIENT) as session:
            await session.call_tool("search_teams", {"query": "IFA"})
            await session.call_tool("search_teams", {"query": "Boston United"})
            await session.call_tool("search_teams", {"query": "Nobody FC"})

        assert _count("search_teams", "mt-ai", "team-fan", "resolved") == before["resolved"] + 1
        assert _count("search_teams", "mt-ai", "team-fan", "ambiguous") == before["ambiguous"] + 1
        assert _count("search_teams", "mt-ai", "team-fan", "not_found") == before["not_found"] + 1

    async def test_nothing_scheduled_is_counted_as_empty(self, make_deps):
        before = _count("get_upcoming_matches", "none", "team-fan", "empty")

        async with served(make_deps(matches=FakeMatches([]))) as s, s.session("fan") as session:
            await session.call_tool("get_upcoming_matches", {"team_id": 102})

        assert _count("get_upcoming_matches", "none", "team-fan", "empty") == before + 1

    async def test_refused_and_unknown_calls_are_counted_without_new_label_values(self, make_deps):
        before = _count("other", "none", "admin", "refused")

        async with served(make_deps()) as s, s.session("admin") as session:
            await session.call_tool("drop_tables", {})
            await session.call_tool("another_made_up_name", {})

        assert _count("other", "none", "admin", "refused") == before + 2

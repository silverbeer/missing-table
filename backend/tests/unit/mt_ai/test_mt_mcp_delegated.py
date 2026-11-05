"""Delegated tokens (SB-1529): sb-agents acting for a signed-in MT user, through mt-mcp.

Whatever the person's role, a delegated token reaches read/my/self tools only, with or
without a client header; the sb-agents-user client header cannot widen it either.
"""

import pytest
from mt_mcp_harness import served

from mt_mcp.scopes import DELEGATED_CAP, SB_AGENTS_CLIENT, SB_AGENTS_USER_CLIENT, allowed_tiers

pytestmark = [pytest.mark.unit, pytest.mark.backend]

READ_TOOLS = {"search_teams", "get_upcoming_matches", "get_recent_results", "get_standings", "list_divisions"}
MY_TOOLS = {"get_my_team"}


class TestAllowedTiers:
    @pytest.mark.parametrize("client", [None, SB_AGENTS_USER_CLIENT, "made-up"])
    def test_a_delegated_admin_gets_no_admin_or_writes(self, client):
        assert allowed_tiers("admin", client, delegated=True) <= DELEGATED_CAP
        assert "admin" not in allowed_tiers("admin", client, delegated=True)
        assert "team_write" not in allowed_tiers("team-manager", client, delegated=True)

    def test_a_delegated_fan_keeps_my(self):
        assert allowed_tiers("team-fan", SB_AGENTS_USER_CLIENT, delegated=True) == frozenset({"read", "my"})

    def test_the_public_sb_agents_client_still_reads_only(self):
        assert allowed_tiers("team-fan", SB_AGENTS_CLIENT, delegated=True) == frozenset({"read"})

    def test_not_delegated_is_unchanged(self):
        assert "admin" in allowed_tiers("admin", None)


class TestOverMcp:
    @pytest.mark.parametrize("client", [None, SB_AGENTS_USER_CLIENT])
    async def test_a_delegated_admin_lists_no_admin_tools(self, make_deps, client):
        async with served(make_deps()) as s, s.session("deleg-admin", client) as session:
            tools = await session.list_tools()
        assert {t.name for t in tools.tools} == READ_TOOLS | MY_TOOLS

    async def test_a_delegated_fan_can_ask_for_their_team(self, make_deps):
        async with served(make_deps()) as s, s.session("deleg-fan", SB_AGENTS_USER_CLIENT) as session:
            tools = await session.list_tools()
        assert "get_my_team" in {t.name for t in tools.tools}

    async def test_an_admin_tool_is_not_callable_with_a_delegated_token(self, make_deps):
        async with served(make_deps()) as s, s.session("deleg-admin") as session:
            result = await session.call_tool("list_ingest_failures", {})
        assert result.is_error

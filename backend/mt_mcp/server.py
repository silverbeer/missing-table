"""The mt-mcp server: tools, tier gate, HTTP app (SB-1302).

Tool logic lives in plain Python (`mt_ai.tools`) with its own tests; this module
adapts it to MCP. Every tool here:

- takes the viewer from the authenticated caller, never from its arguments;
- returns its Pydantic result model, so the SDK publishes a typed output schema
  and sends the result as structuredContent;
- runs the synchronous DAO-backed logic off the event loop;
- turns an unexpected failure into a generic message — the SDK would otherwise
  send `str(exc)` to the client.

`TierGate` filters `tools/list` and refuses `tools/call` for tools outside the
caller's tiers (role and client, see scopes.py). A refused call reads exactly like
an unknown tool, so a hidden tool's existence is not disclosed.
"""

from collections.abc import Callable, Mapping
from typing import Any

import anyio.to_thread
import structlog
from mcp.server.auth.settings import AuthSettings
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, ListToolsResult, TextContent
from starlette.applications import Starlette

from mt_ai.tools import ToolDeps, Viewer, search_teams
from mt_ai.tools.schemas import ResolveResult
from mt_mcp.auth import MTTokenVerifier, Principal, current_principal
from mt_mcp.observe import ToolCallObserver
from mt_mcp.scopes import CLIENT_HEADER, Tier, allowed_tiers

logger = structlog.get_logger()

SERVER_NAME = "mt-mcp"
SERVER_VERSION = "0.1.0"

INSTRUCTIONS = """\
MissingTable (MT) data for youth soccer: teams, matches and standings.
Resolve a team with search_teams before using its id elsewhere.
Results distinguish "not tracked" (null) from "none" ([]); never report an absent
value as zero.
"""

UNAVAILABLE = "MT could not answer that right now."

# Every tool, and the tier that may use it. A tool missing here is never listed
# and never callable.
TOOL_TIERS: dict[str, Tier] = {
    "search_teams": "read",
}

DepsProvider = Callable[[], ToolDeps]


def _caller() -> Principal:
    principal = current_principal()
    if principal is None:  # RequireAuthMiddleware makes this unreachable over HTTP
        raise ToolError("Authentication required.")
    return principal


async def _run(fn: Callable[[], Any], tool: str) -> Any:
    try:
        return await anyio.to_thread.run_sync(fn)
    except ToolError:
        raise
    except Exception:
        logger.exception("mt_mcp tool failed", tool=tool)
        raise ToolError(UNAVAILABLE) from None


def register_tools(server: MCPServer, deps: DepsProvider) -> None:
    @server.tool(name="search_teams")
    async def search_teams_tool(query: str, age_group: str | None = None) -> ResolveResult:
        """Find an MT team by name. Returns resolved, ambiguous (with candidates)
        or not_found. `age_group` is like "U15" when the user gave one."""
        viewer = Viewer.from_user(_caller().as_user())
        return await _run(lambda: search_teams(deps(), query, viewer, age_group=age_group), "search_teams")


def _client_of(ctx: ServerRequestContext[Any, Any]) -> str | None:
    request = ctx.request
    headers = getattr(request, "headers", None)
    return headers.get(CLIENT_HEADER) if headers is not None else None


class TierGate:
    """ServerMiddleware: tools/list and tools/call see only the caller's tiers."""

    def __init__(self, tool_tiers: Mapping[str, Tier]) -> None:
        self.tool_tiers = tool_tiers

    def _allowed(self, ctx: ServerRequestContext[Any, Any]) -> frozenset[Tier]:
        principal = current_principal()
        if principal is None:
            return frozenset()
        return allowed_tiers(principal.role, _client_of(ctx))

    def _visible(self, name: str, tiers: frozenset[Tier]) -> bool:
        tier = self.tool_tiers.get(name)
        return tier is not None and tier in tiers

    async def __call__(self, ctx: ServerRequestContext[Any, Any], call_next: CallNext) -> HandlerResult:
        if ctx.method == "tools/call":
            name = str((ctx.params or {}).get("name", ""))
            if not self._visible(name, self._allowed(ctx)):
                return CallToolResult(content=[TextContent(type="text", text=f"Unknown tool: {name}")], is_error=True)
            return await call_next(ctx)

        if ctx.method == "tools/list":
            result = await call_next(ctx)
            tiers = self._allowed(ctx)
            listed = result if isinstance(result, ListToolsResult) else ListToolsResult.model_validate(result)
            listed.tools = [t for t in listed.tools if self._visible(t.name, tiers)]
            return listed

        return await call_next(ctx)


def build_server(verifier: MTTokenVerifier, deps: DepsProvider, *, issuer_url: str) -> MCPServer:
    server = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions=INSTRUCTIONS,
        token_verifier=verifier,
        # Resource-server mode only: tokens come from MT's existing login, and the
        # verifier checks each token's audience itself.
        auth=AuthSettings(issuer_url=issuer_url, resource_server_url=None, validate_token_resource=False),
        # Outermost first: the observer also sees calls the gate refuses.
        middleware=[ToolCallObserver(TOOL_TIERS), TierGate(TOOL_TIERS)],
    )
    register_tools(server, deps)
    return server


def build_http_app(server: MCPServer, allowed_hosts: list[str]) -> Starlette:
    """The streamable-HTTP app, served at the root of wherever it is mounted.

    Stateless and JSON-only: each request stands alone, so any replica can
    answer and there is no session to pin. DNS-rebinding protection stays on,
    with the API's real host names allowed.
    """
    return server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            allowed_origins=[],
        ),
    )

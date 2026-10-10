"""The MT assistant: one ADK agent with two tools (SB-1143, SB-1152).

With `mcp` given (SB-1302, SB-1303), every tool comes from mt-mcp over MCP,
called with the end user's own token, so the server — not this module —
decides what the caller may see. Without it (MT_MCP_ENABLED off, the rollback
path) the same tool functions are registered in-process.

This module is the only place that knows about ADK. It takes plain inputs
(history as text, a message, a viewer, a budget) and returns a plain
`TurnOutcome`; the conversation service and the API never see ADK objects,
and the tools never see ADK or HTTP.

The ADK session is in-memory and lives for one request. It is rebuilt from
MT's own `ai_messages` rows each time, so MT owns the conversation record and
ADK's session format can change without a migration.
"""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import structlog
from google.adk.agents import LlmAgent
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.run_config import RunConfig
from google.adk.events import Event
from google.adk.models.base_llm import BaseLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from google.genai import types

from mt_ai.budget import Budget, BudgetExhaustedError, BudgetLimit, ToolCallGuard
from mt_ai.tools import ToolDeps, Viewer, get_upcoming_matches, search_teams
from mt_ai.trace import ToolCallRecord, TurnRecorder

logger = structlog.get_logger()

# ADK's MCP client tries Google mTLS before every new MCP session by probing for
# Google credentials — off-GCP, a 3-10 s wait on the metadata server — and caches
# a failure only per toolset, which here is per turn. mt-mcp is not a Google API.
# An explicit setting still wins (SB-1302).
os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")

APP_NAME = "mt_ai"
AGENT_NAME = "mt_assistant"
AGENT_VERSION = "mt-assistant/0.2.1"

INSTRUCTION = """\
You are MT, the assistant for MissingTable, a youth soccer site for players,
parents and fans. Answer questions about MT teams and their upcoming matches
using your tools.

- To find a team, use search_teams.
- To say when a team plays next, first resolve the team with search_teams, then
  call get_upcoming_matches with that team's team_id and its age_group id.
  Kickoff times are in the club's local time; dates are on or after "today" in
  the result.
- If get_upcoming_matches returns "matches": [], say nothing is scheduled yet
  as of that "today". Only say match data is unavailable when the result has
  an "error". A postponed match is still listed: say it was postponed.
- Never guess a team. If search_teams says "ambiguous", ask which one the user
  means and list the candidates (name, age group, league). If it says
  "not_found" with "other_ages", the team exists but not at that age: say so,
  and list the age groups it does play in. Otherwise say plainly that no such
  team was found.
- A team can play in several competitions at one age group (for example a
  League and Flex). Those are the "registrations" of one team: report them
  all, and never treat them as different teams.
- If a tool result has an "error", explain in one sentence that the data is
  unavailable right now. Do not invent an answer.
- Only state facts that appear in tool results. Keep answers short.
"""


@dataclass(frozen=True)
class HistoryTurn:
    user: str
    assistant: str


@dataclass(frozen=True)
class TurnOutcome:
    status: Literal["ok", "budget_exhausted"]
    answer: str | None
    llm_calls: int
    tool_calls: int
    exhausted: BudgetLimit | None = None
    # What the turn did (SB-1197): every completed tool call, and model time.
    trace: tuple[ToolCallRecord, ...] = ()
    llm_ms: int | None = None


class AIRunError(Exception):
    """The model or the agent run failed. The message is for logs, not clients.

    Carries the trace up to the failure, so a failed turn can be inspected too.
    """

    def __init__(self, message: str, trace: tuple[ToolCallRecord, ...] = (), llm_ms: int | None = None) -> None:
        super().__init__(message)
        self.trace = trace
        self.llm_ms = llm_ms


@dataclass(frozen=True)
class McpAccess:
    """How this turn reaches mt-mcp: where, and as whom.

    `bearer` is the end user's own token, forwarded unchanged; the client
    header caps the tool tiers at what MT AI may use (scopes.py), and
    `tool_filter` repeats that cap on this side.
    """

    url: str
    bearer: str
    tools: tuple[str, ...] = ("search_teams", "get_upcoming_matches")
    timeout_s: float = 10.0
    httpx_client_factory: Any = None  # tests inject an in-process transport

    def toolset(self) -> McpToolset:
        params: dict[str, Any] = {
            "url": self.url,
            "headers": {"Authorization": f"Bearer {self.bearer}", "X-MT-Client": "mt-ai"},
            "timeout": self.timeout_s,
            "sse_read_timeout": self.timeout_s,
        }
        if self.httpx_client_factory is not None:
            params["httpx_client_factory"] = self.httpx_client_factory
        return McpToolset(connection_params=StreamableHTTPConnectionParams(**params), tool_filter=list(self.tools))


def unwrap_mcp_result(tool_response: Any) -> Any:
    """An MCP tool's CallToolResult → the tool's own dict, as an in-process tool returns it.

    The model then sees one copy of the result (not a text copy plus
    structuredContent), and the trace records the same shape for both kinds of
    tool. A protocol-level error (unknown tool, refused call) becomes a tool
    error the agent's instruction already handles.
    """
    if not isinstance(tool_response, dict) or "content" not in tool_response:
        return tool_response
    structured = tool_response.get("structuredContent")
    if isinstance(structured, dict) and not tool_response.get("isError"):
        return structured
    text = "".join(c.get("text", "") for c in tool_response.get("content") or [] if isinstance(c, dict))
    if tool_response.get("isError"):
        return {"error": {"kind": "unavailable", "message": text or "Tool failed."}}
    try:
        parsed = json.loads(text)
    except ValueError:
        return {"value": text}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def model_name(model: BaseLlm | str) -> str:
    return model if isinstance(model, str) else model.model


def make_upcoming_matches_tool(deps: ToolDeps, viewer: Viewer) -> Callable[..., dict[str, Any]]:
    """Bind get_upcoming_matches like search_teams: the viewer (and so test
    visibility) and the clock are the server's; the model picks only the team."""

    def get_upcoming_matches_tool(team_id: int, age_group_id: int | None = None, limit: int = 5) -> dict[str, Any]:
        """A team's next matches, today or later in the club's time zone: scheduled,
        tbd, live or postponed. Use team_id and age_group.id from search_teams.
        "matches" is [] when nothing is scheduled and null when it could not be
        checked (see "error")."""
        return get_upcoming_matches(deps, team_id, viewer, age_group_id=age_group_id, limit=limit).model_dump(
            mode="json"
        )

    get_upcoming_matches_tool.__name__ = "get_upcoming_matches"
    return get_upcoming_matches_tool


def make_search_teams_tool(deps: ToolDeps, viewer: Viewer) -> Callable[..., dict[str, Any]]:
    """Bind the tool to this request's data sources and viewer.

    The model supplies only `query` and `age_group`; who is asking — and so
    whether test teams are visible — is fixed here and cannot be argued with.
    """

    def search_teams_tool(query: str, age_group: str | None = None) -> dict[str, Any]:
        """Find an MT team by name. Returns resolved, ambiguous (with candidates)
        or not_found. `age_group` is like "U15" when the user gave one."""
        return search_teams(deps, query, viewer, age_group=age_group).model_dump(mode="json")

    search_teams_tool.__name__ = "search_teams"
    return search_teams_tool


async def run_turn(
    model: BaseLlm | str,
    deps: ToolDeps,
    viewer: Viewer,
    history: list[HistoryTurn],
    message: str,
    budget: Budget,
    session_id: str,
    mcp: McpAccess | None = None,
) -> TurnOutcome:
    guard = ToolCallGuard(budget.max_tool_calls)
    recorder = TurnRecorder()
    llm_calls = 0

    def after_tool(tool: Any, args: dict[str, Any], tool_context: Any, tool_response: Any) -> Any:
        result = unwrap_mcp_result(tool_response)
        recorder.after_tool(tool, args, tool_context, result)
        # None keeps ADK's own response; a value replaces it.
        return None if result is tool_response else result

    toolset = mcp.toolset() if mcp else None
    tools: list[Any] = (
        [toolset] if toolset else [make_search_teams_tool(deps, viewer), make_upcoming_matches_tool(deps, viewer)]
    )

    def count_llm_call(callback_context: Any, llm_request: Any) -> None:
        nonlocal llm_calls
        llm_calls += 1

    agent = LlmAgent(
        name=AGENT_NAME,
        model=model,
        instruction=INSTRUCTION,
        tools=tools,
        # The guard runs first: a call over budget is stopped, never timed.
        before_model_callback=[count_llm_call, recorder.before_model],
        after_model_callback=recorder.after_model,
        before_tool_callback=[guard.before_tool, recorder.before_tool],
        after_tool_callback=after_tool,
    )
    sessions = InMemorySessionService()
    session = await sessions.create_session(app_name=APP_NAME, user_id="viewer", session_id=session_id)
    for turn in history:
        await sessions.append_event(session, _text_event("user", "user", turn.user))
        await sessions.append_event(session, _text_event(AGENT_NAME, "model", turn.assistant))

    runner = Runner(app_name=APP_NAME, agent=agent, session_service=sessions)
    answer_parts: list[str] = []
    try:
        async for event in runner.run_async(
            user_id="viewer",
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=message)]),
            run_config=RunConfig(max_llm_calls=budget.max_llm_calls),
        ):
            if event.is_final_response() and event.content:
                answer_parts.extend(p.text for p in event.content.parts or [] if p.text)
    except LlmCallsLimitExceededError:
        return TurnOutcome(
            "budget_exhausted", None, llm_calls, guard.calls, "llm_calls", tuple(recorder.calls), recorder.llm_ms
        )
    except BudgetExhaustedError as exc:
        return TurnOutcome(
            "budget_exhausted", None, llm_calls, guard.calls, exc.limit, tuple(recorder.calls), recorder.llm_ms
        )
    except Exception as exc:
        logger.exception("mt_ai run failed", session_id=session_id, llm_calls=llm_calls)
        raise AIRunError(type(exc).__name__, tuple(recorder.calls), recorder.llm_ms) from exc
    finally:
        if toolset is not None:
            await toolset.close()

    answer = "".join(answer_parts).strip()
    if not answer:
        raise AIRunError("model returned no text", tuple(recorder.calls), recorder.llm_ms)
    return TurnOutcome("ok", answer, llm_calls, guard.calls, trace=tuple(recorder.calls), llm_ms=recorder.llm_ms)


def _text_event(author: str, role: str, text: str) -> Event:
    return Event(
        author=author, invocation_id="history", content=types.Content(role=role, parts=[types.Part(text=text)])
    )

"""The MT assistant: one ADK agent with one tool (SB-1143).

This module is the only place that knows about ADK. It takes plain inputs
(history as text, a message, a viewer, a budget) and returns a plain
`TurnOutcome`; the conversation service and the API never see ADK objects,
and the tools never see ADK or HTTP.

The ADK session is in-memory and lives for one request. It is rebuilt from
MT's own `ai_messages` rows each time, so MT owns the conversation record and
ADK's session format can change without a migration.
"""

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
from google.genai import types

from mt_ai.budget import Budget, BudgetExhaustedError, BudgetLimit, ToolCallGuard
from mt_ai.tools import ToolDeps, Viewer, search_teams

logger = structlog.get_logger()

APP_NAME = "mt_ai"
AGENT_NAME = "mt_assistant"
AGENT_VERSION = "mt-assistant/0.1.1"

INSTRUCTION = """\
You are MT, the assistant for MissingTable, a youth soccer site for players,
parents and fans. Answer questions about MT teams using the search_teams tool.

- Never guess a team. If search_teams says "ambiguous", ask which one the user
  means and list the candidates (name, age group, league). If it says
  "not_found", say so plainly.
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


class AIRunError(Exception):
    """The model or the agent run failed. The message is for logs, not clients."""


def model_name(model: BaseLlm | str) -> str:
    return model if isinstance(model, str) else model.model


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
) -> TurnOutcome:
    guard = ToolCallGuard(budget.max_tool_calls)
    llm_calls = 0

    def count_llm_call(callback_context: Any, llm_request: Any) -> None:
        nonlocal llm_calls
        llm_calls += 1

    agent = LlmAgent(
        name=AGENT_NAME,
        model=model,
        instruction=INSTRUCTION,
        tools=[make_search_teams_tool(deps, viewer)],
        before_model_callback=count_llm_call,
        before_tool_callback=guard.before_tool,
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
        return TurnOutcome("budget_exhausted", None, llm_calls, guard.calls, exhausted="llm_calls")
    except BudgetExhaustedError as exc:
        return TurnOutcome("budget_exhausted", None, llm_calls, guard.calls, exhausted=exc.limit)
    except Exception as exc:
        logger.exception("mt_ai run failed", session_id=session_id, llm_calls=llm_calls)
        raise AIRunError(type(exc).__name__) from exc

    answer = "".join(answer_parts).strip()
    if not answer:
        raise AIRunError("model returned no text")
    return TurnOutcome("ok", answer, llm_calls, guard.calls)


def _text_event(author: str, role: str, text: str) -> Event:
    return Event(
        author=author, invocation_id="history", content=types.Content(role=role, parts=[types.Part(text=text)])
    )

"""MT AI answered by the sb-agents core instead of the in-app ADK agent (SB-1500).

`SbAgentsRunner` stands in for `mt_ai.agent.run_turn`: `ChatService` calls it
the same way and gets the same `TurnOutcome`, so MT still owns the user, the
auth and the conversation record (`ai_messages`). sb-agents keeps its own short
memory keyed by conversation_id, so no history is sent.

    POST {url}/v1/chat   Authorization: Bearer {token}
    {"conversation_id", "user_id", "text"}
    → {"text", "outcome", "escalation", "routed_to", "tables"}

Any failure to get an answer — network, non-200, a body that is not the
contract — is an `AIRunError`, so the turn is saved as ai_failed and the
client gets the usual 502.

The backend has no OpenTelemetry tracer configured, so no trace context is
propagated to sb-agents yet.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, ValidationError, model_validator

from mt_ai.agent import AIRunError, HistoryTurn, McpAccess, TurnOutcome
from mt_ai.budget import Budget
from mt_ai.tools import ToolDeps, Viewer

logger = structlog.get_logger()

# What the assistant row's `model` records for a turn sb-agents answered.
SB_AGENTS_MODEL = "sb-agents"
TIMEOUT_S = 90.0


class ChatTable(BaseModel):
    """One table sb-agents attached to an answer. An extra: the text stands alone."""

    title: str
    columns: list[str]
    rows: list[list[str]]
    notes: list[str] = []
    highlight: list[int] = []

    @model_validator(mode="after")
    def rectangular(self) -> "ChatTable":
        if not self.columns or any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("every row needs one cell per column")
        self.highlight = [i for i in self.highlight if 0 <= i < len(self.rows)]
        return self


def clean_tables(raw: Any) -> tuple[dict[str, Any], ...]:
    """The well-formed tables; a malformed one is dropped, never fails the turn."""
    if not isinstance(raw, list):
        return ()
    tables = []
    for item in raw:
        try:
            tables.append(ChatTable.model_validate(item).model_dump())
        except ValidationError:
            logger.warning("mt_ai sb-agents table dropped")
    return tuple(tables)


@dataclass(frozen=True)
class SbAgentsRunner:
    url: str
    token: str = field(repr=False)
    timeout_s: float = TIMEOUT_S
    transport: httpx.AsyncBaseTransport | None = None  # tests inject httpx.MockTransport
    # Mints the user's 5-minute delegated mt-mcp token (SB-1529); None sends no identity.
    mint: Callable[[str], str] | None = field(default=None, repr=False)

    async def __call__(
        self,
        model: Any,
        deps: ToolDeps,
        viewer: Viewer,
        history: list[HistoryTurn],
        message: str,
        budget: Budget,
        session_id: str,
        mcp: McpAccess | None = None,
        user_id: str | None = None,
    ) -> TurnOutcome:
        body = {"conversation_id": session_id, "user_id": user_id, "text": message}
        if user_id and self.mint is not None:
            body["user_token"] = self.mint(user_id)  # never logged
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, transport=self.transport) as client:
                response = await client.post(f"{self.url.rstrip('/')}/v1/chat", json=body, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("mt_ai sb-agents unreachable", session_id=session_id, error=type(exc).__name__)
            raise AIRunError(f"sb-agents unreachable: {type(exc).__name__}") from exc
        if response.status_code != 200:
            logger.warning("mt_ai sb-agents refused", session_id=session_id, status=response.status_code)
            raise AIRunError(f"sb-agents answered {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise AIRunError("sb-agents answered with a body that is not JSON") from exc
        text = data.get("text") if isinstance(data, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise AIRunError("sb-agents returned no text")

        outcome, escalation, routed_to = data.get("outcome"), data.get("escalation"), data.get("routed_to")
        return TurnOutcome(
            "ok",
            text.strip(),
            llm_calls=0,  # unknown: sb-agents does not report them
            tool_calls=0,
            outcome=outcome if isinstance(outcome, str) else None,
            escalation=escalation if isinstance(escalation, str) else None,
            routed_to=tuple(r for r in routed_to if isinstance(r, str)) if isinstance(routed_to, list) else (),
            tables=clean_tables(data.get("tables")),
        )

"""Conversation lifecycle for /api/ai/chat (SB-1143).

    request → load or create conversation → rebuild history → run one turn
            → persist the turn (always, even when it failed) → result

The service knows about conversations and outcomes, not about HTTP or ADK:
the route turns `ChatError`s into status codes, and `mt_ai.agent` hides ADK.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import structlog

from mt_ai.agent import AGENT_VERSION, AIRunError, HistoryTurn, TurnOutcome, model_name, run_turn
from mt_ai.budget import Budget
from mt_ai.tools import ToolDeps, Viewer

logger = structlog.get_logger()

BUDGET_MESSAGE = "I couldn't finish that within my limits. Try asking about one team at a time."


class ConversationStore(Protocol):
    def create_conversation(self, user_id: str, agent_version: str) -> dict: ...

    def get_conversation(self, conversation_id: str, user_id: str) -> dict | None: ...

    def list_messages(self, conversation_id: str) -> list[dict]: ...

    def add_turn(
        self, conversation_id: str, turn: int, user_row: dict[str, Any], assistant_row: dict[str, Any]
    ) -> None: ...


class ChatError(Exception):
    """An expected failure, with the status code and client-safe message to return."""

    status_code = 500
    detail = "MT AI could not answer that."

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.detail)
        if detail:
            self.detail = detail


class NotAllowedToChatError(ChatError):
    status_code = 403
    detail = "This account cannot use MT AI."


class ConversationNotFoundError(ChatError):
    status_code = 404
    detail = "Conversation not found."


class AIFailedError(ChatError):
    status_code = 502
    detail = "MT AI could not answer right now. Please try again."


class PersistenceFailedError(ChatError):
    status_code = 503
    detail = "MT AI could not save this conversation right now. Please try again."


@dataclass(frozen=True)
class ChatResult:
    conversation_id: str
    turn: int
    status: Literal["ok", "budget_exhausted"]
    answer: str | None
    message: str | None = None  # why there is no answer, when status is not ok


RunTurn = Callable[..., Awaitable[TurnOutcome]]


class ChatService:
    def __init__(
        self,
        store: ConversationStore,
        deps: ToolDeps,
        model: Any,
        budget: Budget | None = None,
        run: RunTurn = run_turn,
    ) -> None:
        self.store, self.deps, self.model = store, deps, model
        self.budget = budget or Budget()
        self.run = run

    async def chat(self, user: dict[str, Any], message: str, conversation_id: str | None) -> ChatResult:
        if not user.get("user_id"):
            # A conversation needs a user_profiles owner; a service account has none.
            raise NotAllowedToChatError()
        user_id = str(user["user_id"])
        conversation_id, history, turn = self._open(user_id, conversation_id)

        try:
            outcome = await self.run(
                self.model, self.deps, Viewer.from_user(user), history, message, self.budget, session_id=conversation_id
            )
        except AIRunError:
            try:
                self._save(conversation_id, turn, message, status="ai_failed")
            except PersistenceFailedError:
                pass  # already logged; the AI failure is what the client needs to hear
            raise AIFailedError() from None

        self._save(conversation_id, turn, message, status=outcome.status, outcome=outcome)
        if outcome.status == "budget_exhausted":
            logger.info("mt_ai budget exhausted", conversation_id=conversation_id, limit=outcome.exhausted)
            return ChatResult(conversation_id, turn, "budget_exhausted", None, BUDGET_MESSAGE)
        return ChatResult(conversation_id, turn, "ok", outcome.answer)

    def _open(self, user_id: str, conversation_id: str | None) -> tuple[str, list[HistoryTurn], int]:
        try:
            if conversation_id is None:
                created = self.store.create_conversation(user_id, AGENT_VERSION)
                return str(created["id"]), [], 1
            if self.store.get_conversation(conversation_id, user_id) is None:
                # Someone else's conversation is indistinguishable from a missing one.
                raise ConversationNotFoundError()
            rows = self.store.list_messages(conversation_id)
        except ChatError:
            raise
        except Exception:
            logger.exception("mt_ai conversation load failed", conversation_id=conversation_id)
            raise PersistenceFailedError() from None
        return conversation_id, rebuild_history(rows), max((r["turn"] for r in rows), default=0) + 1

    def _save(
        self, conversation_id: str, turn: int, message: str, status: str, outcome: TurnOutcome | None = None
    ) -> None:
        assistant = {
            "content": outcome.answer if outcome else None,
            "status": status,
            "model": model_name(self.model),
            "agent_version": AGENT_VERSION,
            "llm_calls": outcome.llm_calls if outcome else None,
            "tool_calls": outcome.tool_calls if outcome else None,
        }
        try:
            self.store.add_turn(conversation_id, turn, {"content": message}, assistant)
        except Exception:
            logger.exception("mt_ai turn save failed", conversation_id=conversation_id, turn=turn)
            raise PersistenceFailedError() from None


def rebuild_history(rows: list[dict]) -> list[HistoryTurn]:
    """Completed turns only: a turn whose answer failed is left out of what the model sees."""
    by_turn: dict[int, dict[str, dict]] = {}
    for row in rows:
        by_turn.setdefault(row["turn"], {})[row["role"]] = row
    history = []
    for turn in sorted(by_turn):
        user, assistant = by_turn[turn].get("user"), by_turn[turn].get("assistant")
        if user and assistant and assistant.get("status") == "ok" and assistant.get("content"):
            history.append(HistoryTurn(user=user["content"], assistant=assistant["content"]))
    return history

"""Conversation lifecycle for /api/ai/chat (SB-1143).

    request → load or create conversation → rebuild history → run one turn
            → persist the turn (always, even when it failed) → result

The service knows about conversations and outcomes, not about HTTP or ADK:
the route turns `ChatError`s into status codes, and `mt_ai.agent` hides ADK.

After a turn is saved, its trace (tool calls, timings) is saved best-effort
(SB-1197). `ConversationReader` serves the conversation endpoints: a user
sees their own questions and answers; an admin also sees traces, timings and
the model, which client responses otherwise never name.
"""

import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol

import structlog

from mt_ai.agent import AGENT_VERSION, AIRunError, HistoryTurn, McpAccess, TurnOutcome, model_name, run_turn
from mt_ai.budget import Budget
from mt_ai.tools import ToolDeps, Viewer
from mt_ai.trace import ToolCallRecord

logger = structlog.get_logger()

BUDGET_MESSAGE = "I couldn't finish that within my limits. Try asking about one team at a time."


class ConversationStore(Protocol):
    def create_conversation(self, user_id: str, agent_version: str) -> dict: ...

    def get_conversation(self, conversation_id: str, user_id: str) -> dict | None: ...

    def list_messages(self, conversation_id: str) -> list[dict]: ...

    def add_turn(
        self, conversation_id: str, turn: int, user_row: dict[str, Any], assistant_row: dict[str, Any]
    ) -> None: ...

    def record_trace(
        self, conversation_id: str, turn: int, timings: dict[str, int | None], calls: list[dict[str, Any]]
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


class AdminOnlyError(ChatError):
    status_code = 403
    detail = "Admin access required."


class ReadFailedError(ChatError):
    status_code = 503
    detail = "MT AI conversations are unavailable right now. Please try again."


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
        mcp_url: str | None = None,
    ) -> None:
        self.store, self.deps, self.model = store, deps, model
        self.budget = budget or Budget()
        self.run = run
        # Where mt-mcp is (SB-1302); None keeps every tool in-process.
        self.mcp_url = mcp_url

    async def chat(
        self, user: dict[str, Any], message: str, conversation_id: str | None, bearer: str | None = None
    ) -> ChatResult:
        if not user.get("user_id"):
            # A conversation needs a user_profiles owner; a service account has none.
            raise NotAllowedToChatError()
        user_id = str(user["user_id"])
        conversation_id, history, turn = self._open(user_id, conversation_id)

        # Tools reached over MCP run as the caller, with the caller's own token.
        extra: dict[str, Any] = {}
        if self.mcp_url and bearer:
            extra["mcp"] = McpAccess(url=self.mcp_url, bearer=bearer)

        started = time.monotonic()
        try:
            outcome = await self.run(
                self.model,
                self.deps,
                Viewer.from_user(user),
                history,
                message,
                self.budget,
                session_id=conversation_id,
                **extra,
            )
        except AIRunError as exc:
            try:
                self._save(conversation_id, turn, message, status="ai_failed")
                self._save_trace(conversation_id, turn, _ms_since(started), exc.trace, exc.llm_ms)
            except PersistenceFailedError:
                pass  # already logged; the AI failure is what the client needs to hear
            raise AIFailedError() from None

        self._save(conversation_id, turn, message, status=outcome.status, outcome=outcome)
        self._save_trace(conversation_id, turn, _ms_since(started), outcome.trace, outcome.llm_ms)
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

    def _save_trace(
        self,
        conversation_id: str,
        turn: int,
        duration_ms: int,
        trace: tuple[ToolCallRecord, ...],
        llm_ms: int | None,
    ) -> None:
        """Best-effort: the turn is already saved, and a trace must never fail it."""
        try:
            self.store.record_trace(
                conversation_id,
                turn,
                {"duration_ms": duration_ms, "llm_ms": llm_ms},
                [asdict(call) for call in trace],
            )
        except Exception:
            logger.warning("mt_ai trace save failed", conversation_id=conversation_id, turn=turn, exc_info=True)


def _ms_since(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


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


# --- Reading conversations (SB-1197) -------------------------------------------

MAX_PAGE = 100


class ConversationReader:
    """GET /api/ai/conversations and /api/ai/conversations/{id}.

    Ownership is enforced here, not trusted to the client: a user reads only
    their own conversations, and someone else's is a 404, like a missing one.
    Admins may read any and see the trace.
    """

    def __init__(self, store: Any) -> None:
        self.store = store

    def list_for(self, user: dict[str, Any], scope: Literal["mine", "all"], limit: int, offset: int) -> dict[str, Any]:
        admin = _is_admin(user)
        if scope == "all" and not admin:
            raise AdminOnlyError()
        owner = None if scope == "all" else _owner(user)
        try:
            rows = self.store.list_conversations(owner, limit, offset)
        except Exception:
            logger.exception("mt_ai conversation list failed")
            raise ReadFailedError() from None
        keys = ("id", "created_at", "updated_at", "agent_version", "first_question")
        if scope == "all":
            keys = (*keys, "user_id")
        return {
            "conversations": [{k: row.get(k) for k in keys} for row in rows],
            "limit": limit,
            "offset": offset,
        }

    def get_for(self, user: dict[str, Any], conversation_id: str) -> dict[str, Any]:
        admin = _is_admin(user)
        try:
            conversation = self.store.get_conversation(conversation_id, None if admin else _owner(user))
        except Exception:
            logger.exception("mt_ai conversation read failed", conversation_id=conversation_id)
            raise ReadFailedError() from None
        if conversation is None:
            raise ConversationNotFoundError()

        rows, timings_recorded = self._messages(conversation_id, admin)
        body: dict[str, Any] = {
            "id": conversation["id"],
            "created_at": conversation.get("created_at"),
            "updated_at": conversation.get("updated_at"),
            "agent_version": conversation.get("agent_version"),
            "turns": _turns(rows, admin),
        }
        if admin:
            body["user_id"] = conversation.get("user_id")
            body["timings_recorded"] = timings_recorded
            _attach_traces(body["turns"], self._tool_calls(conversation_id))
        return body

    def _messages(self, conversation_id: str, admin: bool) -> tuple[list[dict], bool]:
        """Rows, and whether SB-1197's timing columns could be read."""
        try:
            if admin:
                try:
                    return self.store.list_messages_detail(conversation_id), True
                except Exception:
                    logger.warning("mt_ai message detail unavailable", conversation_id=conversation_id, exc_info=True)
            return self.store.list_messages(conversation_id), False
        except Exception:
            logger.exception("mt_ai conversation read failed", conversation_id=conversation_id)
            raise ReadFailedError() from None

    def _tool_calls(self, conversation_id: str) -> list[dict] | None:
        """The trace rows, or None when they couldn't be read (absent, not empty)."""
        try:
            return self.store.list_tool_calls(conversation_id)
        except Exception:
            logger.warning("mt_ai tool calls unavailable", conversation_id=conversation_id, exc_info=True)
            return None


ADMIN_TURN_FIELDS = ("model", "agent_version", "llm_calls", "tool_calls", "duration_ms", "llm_ms")


def _turns(rows: list[dict], admin: bool) -> list[dict[str, Any]]:
    """One entry per turn: the question, and the answer or why there is none."""
    by_turn: dict[int, dict[str, dict]] = {}
    for row in rows:
        by_turn.setdefault(row["turn"], {})[row["role"]] = row
    turns = []
    for number in sorted(by_turn):
        user, assistant = by_turn[number].get("user") or {}, by_turn[number].get("assistant") or {}
        entry: dict[str, Any] = {
            "turn": number,
            "question": user.get("content"),
            "answer": assistant.get("content"),
            "status": assistant.get("status"),
        }
        if admin:
            entry.update({k: assistant.get(k) for k in ADMIN_TURN_FIELDS})
        turns.append(entry)
    return turns


def _attach_traces(turns: list[dict[str, Any]], calls: list[dict] | None) -> None:
    """Each turn's tool calls, in order. `trace` is None when traces couldn't be
    read, and [] when the turn called no tool (or predates SB-1197)."""
    for entry in turns:
        if calls is None:
            entry["trace"] = None
            continue
        entry["trace"] = [
            {k: c.get(k) for k in ("seq", "tool_name", "args", "result", "error_kind", "duration_ms")}
            for c in sorted(calls, key=lambda c: c.get("seq", 0))
            if c.get("turn") == entry["turn"]
        ]


def _is_admin(user: dict[str, Any]) -> bool:
    return user.get("role") == "admin"


def _owner(user: dict[str, Any]) -> str:
    if not user.get("user_id"):
        raise NotAllowedToChatError()
    return str(user["user_id"])

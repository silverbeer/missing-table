"""MT AI conversation DAO (SB-1143).

Unlike most DAOs, these methods raise on failure instead of returning a
default. A swallowed error here would look like "no conversation" or "no
history" — and the caller would silently start over, which is exactly the
absent-vs-empty confusion SB-1142 removed from the tools. The service maps
exceptions to a controlled error response.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

CONVERSATIONS = "ai_conversations"
MESSAGES = "ai_messages"
TOOL_CALLS = "ai_tool_calls"

# Every row in a bulk insert must carry every column. PostgREST inserts the
# union of the rows' keys and sends NULL — not the column DEFAULT — for a key
# a row lacks, so a user row without `status` violated NOT NULL (SB-1143,
# caught against local Supabase).
MESSAGE_COLUMNS = ("content", "status", "model", "agent_version", "llm_calls", "tool_calls")

# Read by the admin conversation view (SB-1197). duration_ms / llm_ms only
# exist once the SB-1197 migration has run; the service falls back without them.
MESSAGE_DETAIL = (
    "turn, role, content, status, model, agent_version, llm_calls, tool_calls, duration_ms, llm_ms, created_at"
)
TOOL_CALL_COLUMNS = ("turn", "seq", "tool_name", "args", "result", "error_kind", "duration_ms")


class AIConversationDAO(BaseDAO):
    """Conversations and their turns. Every read is scoped to the owner."""

    def create_conversation(self, user_id: str, agent_version: str) -> dict:
        response = (
            self.client.table(CONVERSATIONS).insert({"user_id": user_id, "agent_version": agent_version}).execute()
        )
        if not response.data:
            raise RuntimeError("ai_conversations insert returned no row")
        return response.data[0]

    def get_conversation(self, conversation_id: str, user_id: str | None) -> dict | None:
        """The conversation if it exists and belongs to this user, else None.

        `user_id=None` means any owner: for admins only, decided by the caller.
        """
        query = (
            self.client.table(CONVERSATIONS)
            .select("id, user_id, agent_version, created_at, updated_at")
            .eq("id", conversation_id)
        )
        if user_id is not None:
            query = query.eq("user_id", user_id)
        response = query.limit(1).execute()
        return response.data[0] if response.data else None

    def list_conversations(self, user_id: str | None, limit: int, offset: int) -> list[dict]:
        """Newest activity first, each with its first question. `user_id=None`: everyone's."""
        query = self.client.table(CONVERSATIONS).select("id, user_id, agent_version, created_at, updated_at")
        if user_id is not None:
            query = query.eq("user_id", user_id)
        conversations = query.order("updated_at", desc=True).range(offset, offset + limit - 1).execute().data or []
        if not conversations:
            return []
        firsts = (
            self.client.table(MESSAGES)
            .select("conversation_id, content")
            .in_("conversation_id", [c["id"] for c in conversations])
            .eq("turn", 1)
            .eq("role", "user")
            .execute()
            .data
            or []
        )
        first_by_id = {m["conversation_id"]: m["content"] for m in firsts}
        return [{**c, "first_question": first_by_id.get(c["id"])} for c in conversations]

    def list_messages_detail(self, conversation_id: str) -> list[dict]:
        """Every column the admin view shows, including SB-1197's timings."""
        response = (
            self.client.table(MESSAGES)
            .select(MESSAGE_DETAIL)
            .eq("conversation_id", conversation_id)
            .order("turn")
            .order("role", desc=True)
            .execute()
        )
        return response.data or []

    def list_tool_calls(self, conversation_id: str) -> list[dict]:
        response = (
            self.client.table(TOOL_CALLS)
            .select(", ".join(TOOL_CALL_COLUMNS))
            .eq("conversation_id", conversation_id)
            .order("turn")
            .order("seq")
            .execute()
        )
        return response.data or []

    def record_trace(
        self, conversation_id: str, turn: int, timings: dict[str, int | None], calls: list[dict[str, Any]]
    ) -> None:
        """The turn's timings on its assistant row, and its tool calls (SB-1197).

        Called after `add_turn`, best-effort: the caller logs a failure and
        moves on, so an environment without the SB-1197 migration still chats.
        """
        self.client.table(MESSAGES).update(
            {"duration_ms": timings.get("duration_ms"), "llm_ms": timings.get("llm_ms")}
        ).eq("conversation_id", conversation_id).eq("turn", turn).eq("role", "assistant").execute()
        if calls:
            rows = [
                {**{c: call.get(c) for c in TOOL_CALL_COLUMNS}, "conversation_id": conversation_id, "turn": turn}
                for call in calls
            ]
            self.client.table(TOOL_CALLS).insert(rows).execute()

    def list_messages(self, conversation_id: str) -> list[dict]:
        response = (
            self.client.table(MESSAGES)
            .select("turn, role, content, status")
            .eq("conversation_id", conversation_id)
            .order("turn")
            .order("role", desc=True)  # 'user' before 'assistant' within a turn
            .execute()
        )
        return response.data or []

    def add_turn(
        self, conversation_id: str, turn: int, user_row: dict[str, Any], assistant_row: dict[str, Any]
    ) -> None:
        """Write both halves of a turn in one request, so a turn is never half-saved."""
        user = {"status": "ok", **user_row}
        rows = [
            {**_message_row(user), "conversation_id": conversation_id, "turn": turn, "role": "user"},
            {**_message_row(assistant_row), "conversation_id": conversation_id, "turn": turn, "role": "assistant"},
        ]
        self.client.table(MESSAGES).insert(rows).execute()
        self.client.table(CONVERSATIONS).update({"updated_at": datetime.now(UTC).isoformat()}).eq(
            "id", conversation_id
        ).execute()


def _message_row(values: dict[str, Any]) -> dict[str, Any]:
    unknown = set(values) - set(MESSAGE_COLUMNS)
    if unknown:
        raise ValueError(f"unknown ai_messages columns: {sorted(unknown)}")
    return {column: values.get(column) for column in MESSAGE_COLUMNS}

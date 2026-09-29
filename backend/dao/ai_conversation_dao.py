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

# Every row in a bulk insert must carry every column. PostgREST inserts the
# union of the rows' keys and sends NULL — not the column DEFAULT — for a key
# a row lacks, so a user row without `status` violated NOT NULL (SB-1143,
# caught against local Supabase).
MESSAGE_COLUMNS = ("content", "status", "model", "agent_version", "llm_calls", "tool_calls")


class AIConversationDAO(BaseDAO):
    """Conversations and their turns. Every read is scoped to the owner."""

    def create_conversation(self, user_id: str, agent_version: str) -> dict:
        response = (
            self.client.table(CONVERSATIONS).insert({"user_id": user_id, "agent_version": agent_version}).execute()
        )
        if not response.data:
            raise RuntimeError("ai_conversations insert returned no row")
        return response.data[0]

    def get_conversation(self, conversation_id: str, user_id: str) -> dict | None:
        """The conversation if it exists and belongs to this user, else None."""
        response = (
            self.client.table(CONVERSATIONS)
            .select("id, user_id, agent_version, created_at, updated_at")
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

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

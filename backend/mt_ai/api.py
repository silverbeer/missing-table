"""MT AI's HTTP boundary: POST /api/ai/chat (SB-1143) and the conversation
reads GET /api/ai/conversations[/{id}] (SB-1197).

The route validates, authenticates and translates `ChatError`s into status
codes. Everything else is in `mt_ai.service` (conversations) and
`mt_ai.agent` (ADK).

MT AI is off unless both are set:
    MT_AI_ENABLED=true
    MT_AI_MODEL=<model id>   (Gemini ids need GOOGLE_API_KEY in the environment)
No model id is hardcoded: which model runs is configuration (mt2/ai.md).
"""

import os
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

from auth import get_ai_user
from dao.ai_conversation_dao import AIConversationDAO
from dao.match_dao import SupabaseConnection
from mt_ai.service import MAX_PAGE, ChatError, ChatService, ConversationReader
from mt_ai.tools.deps import dao_tool_deps
from mt_mcp import config as mcp_config

router = APIRouter(prefix="/api/ai", tags=["mt-ai"])

# The raw token, to forward to mt-mcp. get_ai_user has already authenticated it;
# this only reads it, so it never answers 401/403 itself.
_bearer = HTTPBearer(auto_error=False)

MAX_MESSAGE_LENGTH = 2000


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    conversation_id: uuid.UUID | None = None

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value.strip()


class ChatResponse(BaseModel):
    conversation_id: str
    turn: int
    status: Literal["ok", "budget_exhausted"]
    answer: str | None
    message: str | None = None


def configured_model() -> str | None:
    if os.getenv("MT_AI_ENABLED", "false").lower() != "true":
        return None
    return os.getenv("MT_AI_MODEL") or None


_service: ChatService | None = None


def get_chat_service() -> ChatService:
    global _service
    model = configured_model()
    if model is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MT AI is not enabled.")
    mcp_url = mcp_config.internal_url() if mcp_config.mcp_enabled() else None
    if _service is None or _service.model != model or _service.mcp_url != mcp_url:
        _service = ChatService(AIConversationDAO(SupabaseConnection()), dao_tool_deps(), model, mcp_url=mcp_url)
    return _service


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: dict[str, Any] = Depends(get_ai_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    conversation_id = str(payload.conversation_id) if payload.conversation_id else None
    try:
        # The caller's own token goes to mt-mcp, so its tools run as the caller.
        result = await service.chat(
            current_user, payload.message, conversation_id, bearer=credentials.credentials if credentials else None
        )
    except ChatError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return ChatResponse(
        conversation_id=result.conversation_id,
        turn=result.turn,
        status=result.status,
        answer=result.answer,
        message=result.message,
    )


def get_conversation_reader() -> ConversationReader:
    """Reading works whether or not MT AI is enabled: past conversations stay readable."""
    return ConversationReader(AIConversationDAO(SupabaseConnection()))


@router.get("/conversations")
def list_conversations(
    scope: Literal["mine", "all"] = "mine",
    limit: int = Query(20, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0),
    current_user: dict[str, Any] = Depends(get_ai_user),
    reader: ConversationReader = Depends(get_conversation_reader),
) -> dict[str, Any]:
    """Your conversations, newest activity first, each with its first question.
    `scope=all` (admins only) lists everyone's, with the owner's user_id."""
    try:
        return reader.list_for(current_user, scope, limit, offset)
    except ChatError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(get_ai_user),
    reader: ConversationReader = Depends(get_conversation_reader),
) -> dict[str, Any]:
    """One conversation's turns. Someone else's is a 404. Admins may read any, and
    also get each turn's model, call counts, timings and tool-call trace."""
    try:
        return reader.get_for(current_user, str(conversation_id))
    except ChatError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None

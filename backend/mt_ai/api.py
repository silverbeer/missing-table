"""MT AI's HTTP boundary: POST /api/ai/chat (SB-1143) and the conversation
reads GET /api/ai/conversations[/{id}] (SB-1197).

The route validates, authenticates and translates `ChatError`s into status
codes. Everything else is in `mt_ai.service` (conversations) and
`mt_ai.agent` (ADK).

MT AI is off unless MT_AI_ENABLED=true and the chosen backend is configured.
MT_AI_BACKEND picks who answers (SB-1500); MT owns the user, the auth and the
conversation record either way:
    in-app (default)  the ADK agent in mt_ai.agent; needs
                      MT_AI_MODEL=<model id>   (Gemini ids need GOOGLE_API_KEY;
                      ollama_chat/<model> runs a local Ollama model — mt_ai/models.py)
    sb-agents         the sb-agents core over HTTP (mt_ai.sb_agents); needs
                      MT_AI_SB_AGENTS_URL and MT_AI_SB_AGENTS_TOKEN, not MT_AI_MODEL
Rollback from sb-agents is MT_AI_BACKEND=in-app. No model id is hardcoded:
which model runs is configuration (mt2/ai.md).

GET /api/ai/status tells a logged-in client whether chat is on, and which
backend answers, so the UI can hide the entry when it is off.
"""

import hashlib
import os
import uuid
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

from auth import get_ai_user
from dao.ai_conversation_dao import AIConversationDAO
from dao.match_dao import SupabaseConnection
from mt_ai.models import ModelUnavailableError, resolve_model
from mt_ai.sb_agents import SB_AGENTS_MODEL, ChatTable, SbAgentsRunner
from mt_ai.service import MAX_PAGE, ChatError, ChatService, ConversationReader
from mt_ai.tools.deps import dao_tool_deps
from mt_mcp import config as mcp_config

logger = structlog.get_logger()

router = APIRouter(prefix="/api/ai", tags=["mt-ai"])

# The raw token, to forward to mt-mcp. get_ai_user has already authenticated it;
# this only reads it, so it never answers 401/403 itself.
_bearer = HTTPBearer(auto_error=False)

MAX_MESSAGE_LENGTH = 2000

Backend = Literal["in-app", "sb-agents"]
BACKENDS: tuple[Backend, ...] = ("in-app", "sb-agents")
REQUIRED_ENV: dict[Backend, tuple[str, ...]] = {
    "in-app": ("MT_AI_MODEL",),
    "sb-agents": ("MT_AI_SB_AGENTS_URL", "MT_AI_SB_AGENTS_TOKEN"),
}


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
    # Set only when sb-agents answered (SB-1500); in-app answers keep these defaults.
    outcome: str | None = None
    escalation: str | None = None
    routed_to: list[str] = []
    tables: list[ChatTable] = []


class AIStatusResponse(BaseModel):
    enabled: bool
    backend: Backend | None
    # Whether the web app shows its chat screen (SB-1500). Separate from `enabled`:
    # prod already answers /api/ai/chat for API clients, and the web screen is a launch
    # of its own (minors' data review first). Off unless MT_AI_WEB_CHAT=true.
    web_chat: bool = False


def web_chat_enabled() -> bool:
    return os.getenv("MT_AI_WEB_CHAT", "false").lower() == "true"


def mint_delegated_token(user_id: str) -> str:
    """The user's 5-minute mt-mcp token for one sb-agents turn (SB-1529)."""
    from app import auth_manager  # same late import as auth.get_ai_user

    return auth_manager.create_delegated_token(user_id)


def configured_backend() -> Backend | None:
    """The backend that answers chat, or None when MT AI is off or not configured.
    Logs which variable is missing — by name only, never a value."""
    if os.getenv("MT_AI_ENABLED", "false").lower() != "true":
        return None
    backend = os.getenv("MT_AI_BACKEND") or "in-app"
    if backend not in BACKENDS:
        logger.warning("mt_ai unknown backend", backend=backend)
        return None
    missing = [name for name in REQUIRED_ENV[backend] if not os.getenv(name)]
    if missing:
        logger.warning("mt_ai not configured", backend=backend, missing=missing)
        return None
    return backend


_service: ChatService | None = None
_service_key: tuple[str | None, ...] | None = None


def get_chat_service() -> ChatService:
    global _service, _service_key
    backend = configured_backend()
    if backend is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MT AI is not enabled.")
    if backend == "sb-agents":
        url, token = os.environ["MT_AI_SB_AGENTS_URL"], os.environ["MT_AI_SB_AGENTS_TOKEN"]
        # A rotated token rebuilds the service; the key holds a digest, never the token.
        key = (backend, url, hashlib.sha256(token.encode()).hexdigest())
        if _service is None or _service_key != key:
            _service = ChatService(
                AIConversationDAO(SupabaseConnection()),
                dao_tool_deps(),
                SB_AGENTS_MODEL,
                run=SbAgentsRunner(url, token, mint=mint_delegated_token),
                pass_user_id=True,
            )
            _service_key = key
        return _service
    model_id = os.environ["MT_AI_MODEL"]
    mcp_url = mcp_config.internal_url() if mcp_config.mcp_enabled() else None
    if _service is None or _service_key != (backend, model_id, mcp_url):
        try:
            model = resolve_model(model_id)
        except ModelUnavailableError:
            logger.exception("mt_ai model unavailable", model=model_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MT AI is not enabled."
            ) from None
        _service = ChatService(AIConversationDAO(SupabaseConnection()), dao_tool_deps(), model, mcp_url=mcp_url)
        _service_key = (backend, model_id, mcp_url)
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
        outcome=result.outcome,
        escalation=result.escalation,
        routed_to=list(result.routed_to),
        tables=[ChatTable(**table) for table in result.tables],
    )


@router.get("/status", response_model=AIStatusResponse)
def ai_status(current_user: dict[str, Any] = Depends(get_ai_user)) -> AIStatusResponse:
    """Whether chat is on, and who answers. Never 503: off is `enabled: false`."""
    backend = configured_backend()
    return AIStatusResponse(
        enabled=backend is not None, backend=backend, web_chat=backend is not None and web_chat_enabled()
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

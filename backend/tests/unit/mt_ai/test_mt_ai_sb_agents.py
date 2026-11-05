"""MT AI answered by sb-agents (SB-1500): the runner, the flag, the response and /status.

sb-agents itself is an httpx.MockTransport; the store is in memory.
"""

import json

import httpx
import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mt_ai_fake_llm import InMemoryStore

from auth import get_ai_user
from mt_ai import api
from mt_ai.agent import AIRunError, TurnOutcome
from mt_ai.budget import Budget
from mt_ai.sb_agents import SB_AGENTS_MODEL, SbAgentsRunner, clean_tables
from mt_ai.service import AIFailedError, ChatService
from mt_ai.tools import Viewer

pytestmark = [pytest.mark.unit, pytest.mark.backend]

USER = {"user_id": "user-1", "username": "fan", "role": "team-fan", "is_test": False}
URL = "http://sb-agents.test"
TOKEN = "sb-test-token"  # not a real credential

TABLE = {
    "title": "U15 Northeast",
    "columns": ["Team", "Pts"],
    "rows": [["IFA", "21"], ["NEFC", "18"]],
    "notes": ["7 of 9 matches played"],
    "highlight": [0],
}
ANSWER = {
    "text": "IFA lead U15 Northeast on 21 points.",
    "outcome": "answered",
    "escalation": None,
    "routed_to": ["standings"],
    "tables": [TABLE],
}


class SbAgents:
    """A fake sb-agents: records each request and answers with `reply`."""

    def __init__(self, reply=None, status=200, raw: bytes | None = None, error: Exception | None = None):
        self.reply, self.status, self.raw, self.error = reply or ANSWER, status, raw, error
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error:
            raise self.error
        if self.raw is not None:
            return httpx.Response(self.status, content=self.raw)
        return httpx.Response(self.status, json=self.reply)

    def runner(self) -> SbAgentsRunner:
        return SbAgentsRunner(URL, TOKEN, transport=httpx.MockTransport(self.handler))


async def run(runner, message="Who leads U15 Northeast?", session_id="conv-1", user_id="user-1"):
    return await runner(SB_AGENTS_MODEL, None, Viewer(), [], message, Budget(), session_id=session_id, user_id=user_id)


class TestRunner:
    async def test_the_answer_comes_back_as_a_turn_outcome(self):
        fake = SbAgents()

        outcome = await run(fake.runner())

        assert outcome.status == "ok"
        assert outcome.answer == "IFA lead U15 Northeast on 21 points."
        assert (outcome.llm_calls, outcome.tool_calls, outcome.trace) == (0, 0, ())
        assert outcome.outcome == "answered"
        assert outcome.escalation is None
        assert outcome.routed_to == ("standings",)
        assert outcome.tables == (TABLE,)

    async def test_posts_the_contract_with_the_token(self):
        fake = SbAgents()

        await run(fake.runner(), message="hi", session_id="conv-9", user_id="user-7")

        (request,) = fake.requests
        assert request.method == "POST"
        assert str(request.url) == f"{URL}/v1/chat"
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        assert json.loads(request.content) == {"conversation_id": "conv-9", "user_id": "user-7", "text": "hi"}

    def test_the_token_is_not_in_the_runner_repr(self):
        assert TOKEN not in repr(SbAgentsRunner(URL, TOKEN))

    async def test_an_escalation_is_carried(self):
        fake = SbAgents({"text": "Ask an admin.", "outcome": "escalated", "escalation": "needs a human"})

        outcome = await run(fake.runner())

        assert (outcome.outcome, outcome.escalation) == ("escalated", "needs a human")
        assert (outcome.routed_to, outcome.tables) == ((), ())

    @pytest.mark.parametrize("status", [400, 401, 500, 503])
    async def test_a_non_200_is_a_run_error(self, status):
        with pytest.raises(AIRunError):
            await run(SbAgents(status=status, reply={"detail": "no"}).runner())

    @pytest.mark.parametrize(
        "error", [httpx.ReadTimeout("slow"), httpx.ConnectError("refused"), httpx.RemoteProtocolError("eh")]
    )
    async def test_a_network_failure_is_a_run_error(self, error):
        with pytest.raises(AIRunError):
            await run(SbAgents(error=error).runner())

    @pytest.mark.parametrize("raw", [b"not json", b"[]", b'{"outcome": "answered"}', b'{"text": "  "}'])
    async def test_a_body_without_an_answer_is_a_run_error(self, raw):
        with pytest.raises(AIRunError):
            await run(SbAgents(raw=raw).runner())

    async def test_the_run_error_never_carries_the_token(self):
        with pytest.raises(AIRunError) as exc:
            await run(SbAgents(status=401).runner())

        assert TOKEN not in str(exc.value)


class TestCleanTables:
    def test_keeps_good_tables_and_drops_malformed_ones(self):
        ragged = {**TABLE, "rows": [["IFA"]]}
        no_title = {k: v for k, v in TABLE.items() if k != "title"}
        numbers = {**TABLE, "rows": [["IFA", 21]]}

        assert clean_tables([TABLE, ragged, no_title, numbers, "table", None]) == (TABLE,)

    def test_notes_and_highlight_are_optional(self):
        bare = {"title": "t", "columns": ["a"], "rows": [["1"]]}

        assert clean_tables([bare]) == ({**bare, "notes": [], "highlight": []},)

    def test_a_highlight_outside_the_rows_is_dropped(self):
        assert clean_tables([{**TABLE, "highlight": [1, 2, -1]}])[0]["highlight"] == [1]

    @pytest.mark.parametrize("raw", [None, {}, "x", 3])
    def test_anything_but_a_list_is_no_tables(self, raw):
        assert clean_tables(raw) == ()


class TestService:
    async def test_sends_the_user_and_records_the_model_as_sb_agents(self):
        store, fake = InMemoryStore(), SbAgents()
        service = ChatService(store, None, SB_AGENTS_MODEL, run=fake.runner(), pass_user_id=True)

        result = await service.chat(USER, "Who leads?", None)

        body = json.loads(fake.requests[0].content)
        assert body["user_id"] == "user-1"
        assert body["conversation_id"] == result.conversation_id
        assistant = store.list_messages(result.conversation_id)[1]
        assert (assistant["model"], assistant["status"], assistant["content"]) == (
            "sb-agents",
            "ok",
            ANSWER["text"],
        )
        assert result.outcome == "answered"
        assert result.tables == (TABLE,)

    async def test_a_failure_saves_an_ai_failed_turn(self):
        store = InMemoryStore()
        service = ChatService(store, None, SB_AGENTS_MODEL, run=SbAgents(status=500).runner(), pass_user_id=True)

        with pytest.raises(AIFailedError):
            await service.chat(USER, "Who leads?", None)

        (conversation_id,) = store.conversations
        assert store.turns(conversation_id)[1] == (1, "assistant", "ai_failed", None)
        assert store.list_messages(conversation_id)[1]["model"] == "sb-agents"


def chat_app(service: ChatService) -> TestClient:
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_ai_user] = lambda: USER
    app.dependency_overrides[api.get_chat_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


class TestChatResponse:
    def test_sb_agents_answers_carry_outcome_routing_and_tables(self):
        service = ChatService(InMemoryStore(), None, SB_AGENTS_MODEL, run=SbAgents().runner(), pass_user_id=True)

        response = chat_app(service).post("/api/ai/chat", json={"message": "Who leads U15 Northeast?"})

        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == ANSWER["text"]
        assert body["outcome"] == "answered"
        assert body["escalation"] is None
        assert body["routed_to"] == ["standings"]
        assert body["tables"] == [TABLE]

    def test_sb_agents_failure_is_the_usual_502(self):
        service = ChatService(
            InMemoryStore(), None, SB_AGENTS_MODEL, run=SbAgents(status=401).runner(), pass_user_id=True
        )

        response = chat_app(service).post("/api/ai/chat", json={"message": "hi"})

        assert response.status_code == 502
        assert response.json() == {"detail": "MT AI could not answer right now. Please try again."}

    def test_in_app_answers_keep_the_defaults(self):
        async def in_app(model, deps, viewer, history, message, budget, session_id):
            return TurnOutcome("ok", "hello", llm_calls=1, tool_calls=0)

        response = chat_app(ChatService(InMemoryStore(), None, "gemini-test", run=in_app)).post(
            "/api/ai/chat", json={"message": "hi"}
        )

        body = response.json()
        assert response.status_code == 200
        assert (body["outcome"], body["escalation"], body["routed_to"], body["tables"]) == (None, None, [], [])


AI_ENV = (
    "MT_AI_ENABLED",
    "MT_AI_BACKEND",
    "MT_AI_MODEL",
    "MT_AI_SB_AGENTS_URL",
    "MT_AI_SB_AGENTS_TOKEN",
    "MT_AI_WEB_CHAT",
)


@pytest.fixture
def env(monkeypatch):
    """Sets exactly the given MT AI variables; no real database is built."""
    monkeypatch.setattr(api, "_service", None)
    monkeypatch.setattr(api, "_service_key", None)
    monkeypatch.setattr(api, "AIConversationDAO", lambda conn: InMemoryStore())
    monkeypatch.setattr(api, "SupabaseConnection", lambda: None)
    monkeypatch.setattr(api, "dao_tool_deps", lambda: None)
    monkeypatch.setattr(api.mcp_config, "mcp_enabled", lambda: False)

    def set_env(**values):
        for key in AI_ENV:
            monkeypatch.delenv(key, raising=False)
        for key, value in values.items():
            monkeypatch.setenv(key, value)

    set_env()
    return set_env


SB_ENV = {
    "MT_AI_ENABLED": "true",
    "MT_AI_BACKEND": "sb-agents",
    "MT_AI_SB_AGENTS_URL": URL,
    "MT_AI_SB_AGENTS_TOKEN": TOKEN,
}


class TestBackendFlag:
    def test_in_app_is_the_default(self, env):
        env(MT_AI_ENABLED="true", MT_AI_MODEL="gemini-test")

        service = api.get_chat_service()

        assert service.model == "gemini-test"
        assert not isinstance(service.run, SbAgentsRunner)
        assert service.pass_user_id is False

    def test_sb_agents_needs_no_model(self, env):
        env(**SB_ENV)

        service = api.get_chat_service()

        assert isinstance(service.run, SbAgentsRunner)
        assert service.run.url == URL
        assert service.model == SB_AGENTS_MODEL
        assert service.pass_user_id is True

    def test_flipping_the_flag_takes_effect_without_a_restart(self, env):
        env(MT_AI_ENABLED="true", MT_AI_MODEL="gemini-test")
        in_app = api.get_chat_service()
        env(**SB_ENV, MT_AI_MODEL="gemini-test")
        sb = api.get_chat_service()
        env(MT_AI_ENABLED="true", MT_AI_MODEL="gemini-test", MT_AI_BACKEND="in-app")
        back = api.get_chat_service()

        assert isinstance(sb.run, SbAgentsRunner)
        assert not isinstance(in_app.run, SbAgentsRunner)
        assert not isinstance(back.run, SbAgentsRunner)

    def test_the_service_is_reused_while_config_is_unchanged(self, env):
        env(**SB_ENV)

        assert api.get_chat_service() is api.get_chat_service()

    def test_a_new_token_rebuilds_the_service_and_the_key_holds_no_token(self, env):
        env(**SB_ENV)
        first = api.get_chat_service()
        env(**{**SB_ENV, "MT_AI_SB_AGENTS_TOKEN": "rotated-token"})

        assert api.get_chat_service() is not first
        assert "rotated-token" not in repr(api._service_key)

    @pytest.mark.parametrize("missing", ["MT_AI_SB_AGENTS_URL", "MT_AI_SB_AGENTS_TOKEN"])
    def test_sb_agents_without_its_env_is_503_and_logs_the_name_only(self, env, missing):
        env(**{k: v for k, v in SB_ENV.items() if k != missing})
        client = TestClient(chat_app_without_service())

        with structlog.testing.capture_logs() as logs:
            response = client.post("/api/ai/chat", json={"message": "hi"})

        assert response.status_code == 503
        assert response.json() == {"detail": "MT AI is not enabled."}
        assert any(missing in entry.get("missing", []) for entry in logs)
        assert TOKEN not in repr(logs)

    def test_an_unknown_backend_is_503(self, env):
        env(MT_AI_ENABLED="true", MT_AI_BACKEND="cloud", MT_AI_MODEL="gemini-test")

        response = TestClient(chat_app_without_service()).post("/api/ai/chat", json={"message": "hi"})

        assert response.status_code == 503


def chat_app_without_service() -> FastAPI:
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_ai_user] = lambda: USER
    return app


class TestStatus:
    @pytest.mark.parametrize(
        ("values", "expected"),
        [
            ({}, {"enabled": False, "backend": None, "web_chat": False}),
            (
                {"MT_AI_ENABLED": "false", "MT_AI_MODEL": "gemini-test"},
                {"enabled": False, "backend": None, "web_chat": False},
            ),
            ({"MT_AI_ENABLED": "true"}, {"enabled": False, "backend": None, "web_chat": False}),
            (
                {"MT_AI_ENABLED": "true", "MT_AI_MODEL": "gemini-test"},
                {"enabled": True, "backend": "in-app", "web_chat": False},
            ),
            (SB_ENV, {"enabled": True, "backend": "sb-agents", "web_chat": False}),
            ({**SB_ENV, "MT_AI_WEB_CHAT": "true"}, {"enabled": True, "backend": "sb-agents", "web_chat": True}),
            ({"MT_AI_WEB_CHAT": "true"}, {"enabled": False, "backend": None, "web_chat": False}),
            ({**SB_ENV, "MT_AI_SB_AGENTS_TOKEN": ""}, {"enabled": False, "backend": None, "web_chat": False}),
        ],
    )
    def test_reports_whether_chat_is_on_and_who_answers(self, env, values, expected):
        env(**values)

        response = TestClient(chat_app_without_service()).get("/api/ai/status")

        assert response.status_code == 200
        assert response.json() == expected

    def test_requires_login(self):
        app = FastAPI()
        app.include_router(api.router)

        response = TestClient(app).get("/api/ai/status")

        assert response.status_code in (401, 403)

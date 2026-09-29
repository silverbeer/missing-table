"""POST /api/ai/chat (SB-1143), end to end below the network.

HTTP → auth → ChatService → real ADK runner → real search_teams over fake
DAOs → scripted model → persisted turn → JSON. Only the model and the
database are doubles.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mt_ai_fake_llm import InMemoryStore, ModelDown, calls_tool, says, scripted

from auth import get_current_user_required
from mt_ai import api
from mt_ai.budget import Budget
from mt_ai.service import ChatService

pytestmark = [pytest.mark.unit, pytest.mark.backend]

USER = {"user_id": "user-1", "username": "fan", "role": "team-fan", "is_test": False}


@pytest.fixture
def harness(make_deps):
    """An app with only the MT AI router, a logged-in user, and swappable model/store."""

    class Harness:
        store = InMemoryStore()
        model = scripted()
        budget = Budget()

        def __init__(self):
            app = FastAPI()
            app.include_router(api.router)
            app.dependency_overrides[get_current_user_required] = lambda: USER
            app.dependency_overrides[api.get_chat_service] = lambda: ChatService(
                self.store, make_deps(), self.model, budget=self.budget
            )
            self.client = TestClient(app, raise_server_exceptions=False)

        def post(self, **body):
            return self.client.post("/api/ai/chat", json=body)

    return Harness()


class TestHappyPath:
    def test_question_reaches_the_tool_and_the_answer_comes_back(self, harness):
        harness.model = scripted(calls_tool("search_teams", query="IFA", age_group="U15"), says("IFA: U15, Northeast."))

        response = harness.post(message="Find the IFA U15 team")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["answer"] == "IFA: U15, Northeast."
        assert body["turn"] == 1
        assert harness.model.tool_results()[0]["team"]["team_id"] == 102
        assert harness.store.turns(body["conversation_id"])[1] == (1, "assistant", "ok", "IFA: U15, Northeast.")

    def test_a_second_request_continues_the_conversation(self, harness):
        harness.model = scripted(
            calls_tool("search_teams", query="IFA"), says("IFA plays U15."), says("In the Northeast division.")
        )

        first = harness.post(message="Find IFA").json()
        second = harness.post(message="Which division?", conversation_id=first["conversation_id"])

        assert second.status_code == 200
        assert second.json()["conversation_id"] == first["conversation_id"]
        assert second.json()["turn"] == 2
        # The third model call saw the whole first turn as history.
        assert ("user", "Find IFA") in harness.model.texts_seen(request_index=2)
        assert ("model", "IFA plays U15.") in harness.model.texts_seen(request_index=2)

    def test_the_response_names_no_model_or_provider(self, harness):
        harness.model = scripted(says("hi"))

        body = harness.post(message="hello").json()

        assert set(body) == {"conversation_id", "turn", "status", "answer", "message"}


class TestControlledOutcomes:
    def test_budget_exhaustion_is_200_with_a_status(self, harness):
        harness.budget = Budget(max_llm_calls=1)
        harness.model = scripted(calls_tool("search_teams", query="IFA"), says("never reached"))

        response = harness.post(message="Tell me everything")

        assert response.status_code == 200
        assert response.json()["status"] == "budget_exhausted"
        assert response.json()["answer"] is None
        assert response.json()["message"]
        assert len(harness.model.requests) == 1

    def test_unknown_conversation_is_404(self, harness):
        response = harness.post(message="hi", conversation_id="00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404
        assert response.json() == {"detail": "Conversation not found."}

    def test_model_failure_is_502_without_internals(self, harness):
        harness.model = scripted(ModelDown("upstream said: secret-internal-detail"))

        response = harness.post(message="hi")

        assert response.status_code == 502
        assert "ModelDown" not in response.text
        assert "secret-internal-detail" not in response.text
        assert "Traceback" not in response.text

    def test_persistence_failure_is_503(self, harness):
        harness.store.fail_create = True

        response = harness.post(message="hi")

        assert response.status_code == 503
        assert response.json() == {"detail": "MT AI could not save this conversation right now. Please try again."}


class TestInvalidRequests:
    @pytest.mark.parametrize(
        "body",
        [
            {},
            {"message": ""},
            {"message": "   "},
            {"message": "x" * 2001},
            {"message": "hi", "conversation_id": "not-a-uuid"},
        ],
    )
    def test_is_422_and_never_reaches_the_model(self, harness, body):
        response = harness.client.post("/api/ai/chat", json=body)

        assert response.status_code == 422
        assert harness.model.requests == []


def test_requires_login():
    app = FastAPI()
    app.include_router(api.router)

    response = TestClient(app).post("/api/ai/chat", json={"message": "hi"})

    assert response.status_code in (401, 403)


@pytest.mark.parametrize(("enabled", "model"), [(None, None), ("false", "gemini-x"), ("true", None), ("true", "")])
def test_is_503_until_enabled_and_configured(monkeypatch, enabled, model):
    for key, value in (("MT_AI_ENABLED", enabled), ("MT_AI_MODEL", model)):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user_required] = lambda: USER

    response = TestClient(app).post("/api/ai/chat", json={"message": "hi"})

    assert response.status_code == 503
    assert response.json() == {"detail": "MT AI is not enabled."}

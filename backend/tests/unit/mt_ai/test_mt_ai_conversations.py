"""SB-1197: traces saved with each turn, and the conversation read endpoints.

The service and the HTTP routes, over the in-memory store. A user reads only
their own conversations; an admin reads any and also gets the trace.
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mt_ai_fake_llm import InMemoryStore

from auth import get_ai_user
from mt_ai import api
from mt_ai.agent import AIRunError, TurnOutcome
from mt_ai.service import (
    AdminOnlyError,
    AIFailedError,
    ChatService,
    ConversationNotFoundError,
    ConversationReader,
    ReadFailedError,
)
from mt_ai.trace import ToolCallRecord

pytestmark = [pytest.mark.unit, pytest.mark.backend]

FAN = {"user_id": "user-1", "role": "team-fan", "is_test": False}
OTHER = {"user_id": "user-2", "role": "team-fan", "is_test": False}
ADMIN = {"user_id": "admin-1", "role": "admin", "is_test": False}

SEARCH = ToolCallRecord(1, "search_teams", {"query": "IFA"}, {"status": "resolved"}, None, 120)
UPCOMING = ToolCallRecord(
    2, "get_upcoming_matches", {"team_id": 102}, {"matches": None, "error": {"kind": "unavailable"}}, "unavailable", 40
)


def outcome(answer="IFA plays Saturday.", trace=(SEARCH, UPCOMING)):
    return TurnOutcome("ok", answer, llm_calls=3, tool_calls=len(trace), trace=trace, llm_ms=2500)


class StubRun:
    def __init__(self, *results):
        self.results = list(results)

    async def __call__(self, model, deps, viewer, history, message, budget, session_id):
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


async def chat(store, *results, user=FAN, message="When does IFA play?", conversation_id=None):
    service = ChatService(store, deps=None, model="gemini-test", run=StubRun(*results))
    return await service.chat(user, message, conversation_id)


# --- Saving the trace --------------------------------------------------------------


class TestTraceIsSaved:
    async def test_tool_calls_and_timings_are_saved_with_the_turn(self):
        store = InMemoryStore()

        result = await chat(store, outcome())

        calls = store.list_tool_calls(result.conversation_id)
        assert [(c["turn"], c["seq"], c["tool_name"], c["error_kind"]) for c in calls] == [
            (1, 1, "search_teams", None),
            (1, 2, "get_upcoming_matches", "unavailable"),
        ]
        assert calls[0]["args"] == {"query": "IFA"}
        assert calls[1]["duration_ms"] == 40
        assistant = store.list_messages(result.conversation_id)[1]
        assert assistant["llm_ms"] == 2500
        assert assistant["duration_ms"] >= 0

    async def test_a_trace_that_cannot_be_saved_never_fails_the_turn(self):
        """E.g. the SB-1197 migration hasn't reached this environment yet."""
        store = InMemoryStore()
        store.fail_trace = True

        result = await chat(store, outcome())

        assert result.status == "ok"
        assert store.turns(result.conversation_id)[1][2:] == ("ok", "IFA plays Saturday.")
        assert store.tool_calls == []

    async def test_a_failed_turn_keeps_the_trace_up_to_the_failure(self):
        store = InMemoryStore()

        with pytest.raises(AIFailedError):
            await chat(store, AIRunError("ModelDown", trace=(SEARCH,), llm_ms=900))

        [conversation_id] = store.conversations
        assert store.turns(conversation_id)[1][2] == "ai_failed"
        assert [c["tool_name"] for c in store.list_tool_calls(conversation_id)] == ["search_teams"]

    async def test_a_turn_without_tools_records_timings_and_no_calls(self):
        store = InMemoryStore()

        result = await chat(store, outcome(answer="Hello.", trace=()))

        assert store.list_tool_calls(result.conversation_id) == []
        assert store.list_messages(result.conversation_id)[1]["llm_ms"] == 2500


# --- Reading -----------------------------------------------------------------------


async def two_conversations(store):
    first = await chat(store, outcome(), message="When does IFA play?")
    await chat(store, outcome(answer="Thanks."), message="And U16?", conversation_id=first.conversation_id)
    other = await chat(store, outcome(answer="Hi."), user=OTHER, message="Find NEFC")
    return first.conversation_id, other.conversation_id


class TestListing:
    async def test_a_user_lists_only_their_own_with_the_first_question(self):
        store = InMemoryStore()
        mine, _ = await two_conversations(store)

        body = ConversationReader(store).list_for(FAN, "mine", 20, 0)

        assert [c["id"] for c in body["conversations"]] == [mine]
        assert body["conversations"][0]["first_question"] == "When does IFA play?"
        assert "user_id" not in body["conversations"][0]
        assert (body["limit"], body["offset"]) == (20, 0)

    async def test_only_admins_list_everyones(self):
        store = InMemoryStore()
        mine, other = await two_conversations(store)

        with pytest.raises(AdminOnlyError):
            ConversationReader(store).list_for(FAN, "all", 20, 0)

        body = ConversationReader(store).list_for(ADMIN, "all", 20, 0)
        assert {c["id"] for c in body["conversations"]} == {mine, other}
        assert {c["user_id"] for c in body["conversations"]} == {"user-1", "user-2"}

    async def test_paging(self):
        store = InMemoryStore()
        await two_conversations(store)
        reader = ConversationReader(store)
        assert len(reader.list_for(ADMIN, "all", 1, 0)["conversations"]) == 1
        assert reader.list_for(ADMIN, "all", 20, 5)["conversations"] == []

    def test_a_read_failure_is_a_controlled_error(self):
        store = InMemoryStore()
        store.fail_list = True
        with pytest.raises(ReadFailedError):
            ConversationReader(store).list_for(FAN, "mine", 20, 0)


class TestReadingOne:
    async def test_a_user_gets_questions_and_answers_but_no_trace_or_model(self):
        store = InMemoryStore()
        mine, _ = await two_conversations(store)

        body = ConversationReader(store).get_for(FAN, mine)

        assert body["id"] == mine
        assert [(t["turn"], t["question"], t["answer"], t["status"]) for t in body["turns"]] == [
            (1, "When does IFA play?", "IFA plays Saturday.", "ok"),
            (2, "And U16?", "Thanks.", "ok"),
        ]
        turn = body["turns"][0]
        for hidden in ("model", "trace", "llm_ms", "duration_ms", "llm_calls"):
            assert hidden not in turn
        assert "user_id" not in body

    async def test_someone_elses_conversation_is_a_404(self):
        store = InMemoryStore()
        _, other = await two_conversations(store)

        with pytest.raises(ConversationNotFoundError):
            ConversationReader(store).get_for(FAN, other)
        with pytest.raises(ConversationNotFoundError):
            ConversationReader(store).get_for(FAN, str(uuid.uuid4()))

    async def test_an_admin_gets_any_conversation_with_its_trace(self):
        store = InMemoryStore()
        mine, _ = await two_conversations(store)

        body = ConversationReader(store).get_for(ADMIN, mine)

        assert body["user_id"] == "user-1"
        assert body["timings_recorded"] is True
        turn = body["turns"][0]
        assert (turn["model"], turn["llm_calls"], turn["tool_calls"], turn["llm_ms"]) == ("gemini-test", 3, 2, 2500)
        assert [(c["seq"], c["tool_name"], c["error_kind"]) for c in turn["trace"]] == [
            (1, "search_teams", None),
            (2, "get_upcoming_matches", "unavailable"),
        ]

    async def test_without_the_migration_an_admin_still_reads_the_turns(self):
        """Absent timing columns and trace table: shown as unknown, not as zero or empty."""
        store = InMemoryStore()
        mine, _ = await two_conversations(store)
        store.fail_detail = store.fail_tool_calls = True

        body = ConversationReader(store).get_for(ADMIN, mine)

        assert body["timings_recorded"] is False
        assert body["turns"][0]["answer"] == "IFA plays Saturday."
        assert body["turns"][0]["trace"] is None

    async def test_a_turn_without_tools_has_an_empty_trace(self):
        store = InMemoryStore()
        result = await chat(store, outcome(answer="Hello.", trace=()))

        body = ConversationReader(store).get_for(ADMIN, result.conversation_id)

        assert body["turns"][0]["trace"] == []

    async def test_a_failed_turn_shows_its_status_and_no_answer(self):
        store = InMemoryStore()
        with pytest.raises(AIFailedError):
            await chat(store, AIRunError("ModelDown"))
        [conversation_id] = store.conversations

        [turn] = ConversationReader(store).get_for(FAN, conversation_id)["turns"]

        assert (turn["question"], turn["answer"], turn["status"]) == ("When does IFA play?", None, "ai_failed")

    def test_read_failures_are_controlled_errors(self):
        store = InMemoryStore()
        store.fail_get = True
        with pytest.raises(ReadFailedError):
            ConversationReader(store).get_for(FAN, str(uuid.uuid4()))

    async def test_a_message_read_failure_is_a_controlled_error(self, monkeypatch):
        store = InMemoryStore()
        mine, _ = await two_conversations(store)

        def boom(conversation_id):
            raise RuntimeError("select failed")

        monkeypatch.setattr(store, "list_messages", boom)
        with pytest.raises(ReadFailedError):
            ConversationReader(store).get_for(FAN, mine)


# --- HTTP --------------------------------------------------------------------------


@pytest.fixture
def http():
    store = InMemoryStore()
    current = {"user": FAN}
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_ai_user] = lambda: current["user"]
    app.dependency_overrides[api.get_conversation_reader] = lambda: ConversationReader(store)
    client = TestClient(app, raise_server_exceptions=False)
    return store, current, client


class TestRoutes:
    async def test_list_and_get(self, http):
        store, current, client = http
        mine, other = await two_conversations(store)

        listed = client.get("/api/ai/conversations")
        assert listed.status_code == 200
        assert [c["id"] for c in listed.json()["conversations"]] == [mine]

        assert client.get(f"/api/ai/conversations/{mine}").status_code == 200
        assert client.get(f"/api/ai/conversations/{other}").status_code == 404

    async def test_scope_all_is_admin_only(self, http):
        store, current, client = http
        await two_conversations(store)

        assert client.get("/api/ai/conversations?scope=all").status_code == 403
        current["user"] = ADMIN
        response = client.get("/api/ai/conversations?scope=all")
        assert response.status_code == 200
        assert len(response.json()["conversations"]) == 2

    def test_bad_input_is_422(self, http):
        _, _, client = http
        assert client.get("/api/ai/conversations/not-a-uuid").status_code == 422
        assert client.get("/api/ai/conversations?limit=0").status_code == 422
        assert client.get("/api/ai/conversations?limit=101").status_code == 422
        assert client.get("/api/ai/conversations?offset=-1").status_code == 422
        assert client.get("/api/ai/conversations?scope=everyone").status_code == 422

    def test_a_store_failure_is_503(self, http):
        store, _, client = http
        store.fail_list = True
        response = client.get("/api/ai/conversations")
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"]

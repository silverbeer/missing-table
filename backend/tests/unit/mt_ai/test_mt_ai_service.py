"""mt_ai.service (SB-1143): the conversation lifecycle, with the agent stubbed."""

import pytest
from mt_ai_fake_llm import InMemoryStore

from mt_ai.agent import AGENT_VERSION, AIRunError, HistoryTurn, TurnOutcome
from mt_ai.service import (
    AIFailedError,
    ChatService,
    ConversationNotFoundError,
    NotAllowedToChatError,
    PersistenceFailedError,
    rebuild_history,
)

pytestmark = [pytest.mark.unit, pytest.mark.backend]

USER = {"user_id": "user-1", "role": "team-fan", "is_test": False}
OTHER = {"user_id": "user-2", "role": "team-fan", "is_test": False}


class StubRun:
    """Stands in for mt_ai.agent.run_turn and records what it was given."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    async def __call__(self, model, deps, viewer, history, message, budget, session_id):
        self.calls.append({"history": history, "message": message, "viewer": viewer, "session_id": session_id})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def ok(answer):
    return TurnOutcome("ok", answer, llm_calls=2, tool_calls=1)


def service(store, run):
    return ChatService(store, deps=None, model="gemini-test", run=run)


# What get_current_user returns for a service-account JWT: no user_id (SB-1145).
SERVICE_ACCOUNT = {
    "service_id": "service-match-scraper",
    "service_name": "match-scraper",
    "permissions": ["manage_matches"],
    "role": "service_account",
    "is_service_account": True,
}


async def test_a_principal_without_a_profile_is_refused_before_anything_runs():
    store, run = InMemoryStore(), StubRun()

    with pytest.raises(NotAllowedToChatError) as exc:
        await service(store, run).chat(SERVICE_ACCOUNT, "Find IFA", None)

    assert exc.value.status_code == 403
    assert run.calls == []
    assert store.conversations == {}


class TestLifecycle:
    async def test_a_first_message_creates_a_conversation(self):
        store, run = InMemoryStore(), StubRun(ok("IFA plays U15."))

        result = await service(store, run).chat(USER, "Find IFA", None)

        assert result.status == "ok"
        assert result.answer == "IFA plays U15."
        assert result.turn == 1
        assert store.conversations[result.conversation_id]["user_id"] == "user-1"
        assert store.conversations[result.conversation_id]["agent_version"] == AGENT_VERSION
        assert store.turns(result.conversation_id) == [
            (1, "user", None, "Find IFA"),
            (1, "assistant", "ok", "IFA plays U15."),
        ]

    async def test_the_assistant_row_records_model_and_work_done(self):
        store = InMemoryStore()
        result = await service(store, StubRun(ok("hi"))).chat(USER, "hello", None)

        assistant = store.list_messages(result.conversation_id)[1]
        assert (assistant["model"], assistant["llm_calls"], assistant["tool_calls"]) == ("gemini-test", 2, 1)

    async def test_a_second_message_continues_the_same_conversation(self):
        store, run = InMemoryStore(), StubRun(ok("IFA plays U15."), ok("Northeast."))
        chat = service(store, run)

        first = await chat.chat(USER, "Find IFA", None)
        second = await chat.chat(USER, "Which division?", first.conversation_id)

        assert second.conversation_id == first.conversation_id
        assert second.turn == 2
        assert run.calls[1]["history"] == [HistoryTurn("Find IFA", "IFA plays U15.")]
        assert run.calls[1]["session_id"] == first.conversation_id
        assert len(store.conversations) == 1

    async def test_the_viewer_comes_from_the_authenticated_user(self):
        run = StubRun(ok("a"), ok("b"))
        await service(InMemoryStore(), run).chat(USER, "x", None)
        await service(InMemoryStore(), run).chat({"user_id": "t", "role": "team-fan", "is_test": True}, "x", None)

        assert [c["viewer"].include_test for c in run.calls] == [False, True]


class TestConversationNotFound:
    async def test_an_unknown_id_is_not_found_and_runs_nothing(self):
        run = StubRun()
        with pytest.raises(ConversationNotFoundError):
            await service(InMemoryStore(), run).chat(USER, "hi", "00000000-0000-0000-0000-000000000000")
        assert run.calls == []

    async def test_someone_elses_conversation_is_not_found(self):
        store = InMemoryStore()
        mine = await service(store, StubRun(ok("a"))).chat(USER, "hi", None)

        with pytest.raises(ConversationNotFoundError):
            await service(store, StubRun()).chat(OTHER, "hi", mine.conversation_id)


class TestBudgetAndFailures:
    async def test_budget_exhaustion_is_a_controlled_result_and_is_recorded(self):
        store = InMemoryStore()
        run = StubRun(TurnOutcome("budget_exhausted", None, 1, 0, exhausted="llm_calls"))

        result = await service(store, run).chat(USER, "everything about every team", None)

        assert result.status == "budget_exhausted"
        assert result.answer is None
        assert result.message
        assert store.turns(result.conversation_id)[1] == (1, "assistant", "budget_exhausted", None)

    async def test_an_ai_failure_is_recorded_then_reported(self):
        store = InMemoryStore()
        chat = service(store, StubRun(AIRunError("ModelDown")))

        with pytest.raises(AIFailedError):
            await chat.chat(USER, "Find IFA", None)

        [conversation_id] = store.conversations
        assert store.turns(conversation_id) == [(1, "user", None, "Find IFA"), (1, "assistant", "ai_failed", None)]

    async def test_failed_turns_are_kept_out_of_history_but_numbering_continues(self):
        store = InMemoryStore()
        run = StubRun(ok("IFA plays U15."), AIRunError("x"), ok("Northeast."))
        chat = service(store, run)

        first = await chat.chat(USER, "Find IFA", None)
        with pytest.raises(AIFailedError):
            await chat.chat(USER, "and?", first.conversation_id)
        third = await chat.chat(USER, "Which division?", first.conversation_id)

        assert third.turn == 3
        assert run.calls[2]["history"] == [HistoryTurn("Find IFA", "IFA plays U15.")]

    async def test_ai_failure_wins_over_a_failed_save(self):
        store = InMemoryStore()
        store.fail_save = True
        with pytest.raises(AIFailedError):
            await service(store, StubRun(AIRunError("x"))).chat(USER, "hi", None)


class TestPersistenceFailures:
    async def test_cannot_create_conversation_means_no_model_call(self):
        store, run = InMemoryStore(), StubRun()
        store.fail_create = True

        with pytest.raises(PersistenceFailedError):
            await service(store, run).chat(USER, "hi", None)
        assert run.calls == []

    async def test_cannot_load_conversation_is_not_reported_as_not_found(self):
        store = InMemoryStore()
        mine = await service(store, StubRun(ok("a"))).chat(USER, "hi", None)
        store.fail_get = True

        with pytest.raises(PersistenceFailedError):
            await service(store, StubRun()).chat(USER, "again", mine.conversation_id)

    async def test_cannot_save_the_turn_is_an_error_not_a_silent_success(self):
        store = InMemoryStore()
        chat = service(store, StubRun(ok("a")))
        store.fail_save = True

        with pytest.raises(PersistenceFailedError):
            await chat.chat(USER, "hi", None)


def test_rebuild_history_pairs_turns_and_skips_unanswered_ones():
    rows = [
        {"turn": 1, "role": "user", "content": "q1"},
        {"turn": 1, "role": "assistant", "content": "a1", "status": "ok"},
        {"turn": 2, "role": "user", "content": "q2"},
        {"turn": 2, "role": "assistant", "content": None, "status": "budget_exhausted"},
        {"turn": 3, "role": "assistant", "content": "a3", "status": "ok"},  # user row missing
        {"turn": 4, "role": "user", "content": "q4"},
        {"turn": 4, "role": "assistant", "content": "a4", "status": "ok"},
    ]

    assert rebuild_history(rows) == [HistoryTurn("q1", "a1"), HistoryTurn("q4", "a4")]

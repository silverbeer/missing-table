"""AIConversationDAO (SB-1143): the query shapes PostgREST actually receives."""

from unittest.mock import MagicMock

import pytest

from dao.ai_conversation_dao import MESSAGE_COLUMNS, AIConversationDAO

pytestmark = [pytest.mark.unit, pytest.mark.backend]


@pytest.fixture
def dao():
    instance = AIConversationDAO.__new__(AIConversationDAO)  # skip the real connection
    instance.client = MagicMock()
    return instance


def inserted_rows(dao):
    return dao.client.table.return_value.insert.call_args.args[0]


def test_both_rows_of_a_turn_carry_every_column(dao):
    """A missing key is sent as NULL, not DEFAULT — so no row may omit one."""
    dao.add_turn("c-1", 3, {"content": "Find IFA"}, {"content": "IFA plays U15.", "status": "ok", "model": "m"})

    user, assistant = inserted_rows(dao)
    expected = {*MESSAGE_COLUMNS, "conversation_id", "turn", "role"}
    assert set(user) == set(assistant) == expected
    assert (user["role"], user["turn"], user["status"], user["model"]) == ("user", 3, "ok", None)
    assert (assistant["role"], assistant["status"], assistant["model"]) == ("assistant", "ok", "m")


def test_the_turn_is_one_insert(dao):
    dao.add_turn("c-1", 1, {"content": "q"}, {"content": None, "status": "ai_failed"})

    assert dao.client.table.return_value.insert.call_count == 1
    assert len(inserted_rows(dao)) == 2


def test_an_unknown_column_is_rejected_before_the_database(dao):
    with pytest.raises(ValueError, match="tokens"):
        dao.add_turn("c-1", 1, {"content": "q"}, {"content": "a", "status": "ok", "tokens": 5})
    dao.client.table.return_value.insert.assert_not_called()


def test_conversations_are_read_only_by_their_owner(dao):
    query = dao.client.table.return_value.select.return_value
    query.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

    assert dao.get_conversation("c-1", "user-2") is None
    query.eq.assert_called_once_with("id", "c-1")
    query.eq.return_value.eq.assert_called_once_with("user_id", "user-2")


def test_failures_raise_instead_of_looking_empty(dao):
    dao.client.table.return_value.select.side_effect = RuntimeError("PostgREST down")

    with pytest.raises(RuntimeError):
        dao.list_messages("c-1")


# --- SB-1197 -----------------------------------------------------------------------


def test_the_trace_updates_the_assistant_row_and_inserts_the_calls(dao):
    calls = [
        {
            "seq": 1,
            "tool_name": "search_teams",
            "args": {"query": "IFA"},
            "result": {"status": "resolved"},
            "error_kind": None,
            "duration_ms": 12,
        }
    ]

    dao.record_trace("c-1", 2, {"duration_ms": 4200, "llm_ms": 3900}, calls)

    table = dao.client.table
    assert [c.args[0] for c in table.call_args_list] == ["ai_messages", "ai_tool_calls"]
    update = table.return_value.update
    assert update.call_args.args[0] == {"duration_ms": 4200, "llm_ms": 3900}
    filters = [c.args for c in update.return_value.eq.call_args_list] + [
        c.args for c in update.return_value.eq.return_value.eq.call_args_list
    ]
    assert ("conversation_id", "c-1") in filters
    [row] = inserted_rows(dao)
    assert row["conversation_id"] == "c-1"
    assert (row["turn"], row["seq"], row["tool_name"], row["duration_ms"]) == (2, 1, "search_teams", 12)


def test_a_turn_without_tools_inserts_no_calls(dao):
    dao.record_trace("c-1", 1, {"duration_ms": 10, "llm_ms": 8}, [])
    assert [c.args[0] for c in dao.client.table.call_args_list] == ["ai_messages"]
    dao.client.table.return_value.insert.assert_not_called()


def test_an_admin_read_does_not_filter_by_owner(dao):
    select = dao.client.table.return_value.select.return_value
    select.eq.return_value.limit.return_value.execute.return_value.data = [{"id": "c-1"}]

    assert dao.get_conversation("c-1", None) == {"id": "c-1"}
    select.eq.assert_called_once_with("id", "c-1")
    select.eq.return_value.eq.assert_not_called()


def test_listing_adds_each_conversations_first_question(dao):
    conversations = [{"id": "c-2", "user_id": "u"}, {"id": "c-1", "user_id": "u"}]
    firsts = [{"conversation_id": "c-1", "content": "Find IFA"}]
    table = dao.client.table
    convo_query = table.return_value.select.return_value
    convo_query.eq.return_value.order.return_value.range.return_value.execute.return_value.data = conversations
    message_query = convo_query.in_.return_value.eq.return_value.eq.return_value
    message_query.execute.return_value.data = firsts

    rows = dao.list_conversations("u", 20, 0)

    assert rows == [
        {"id": "c-2", "user_id": "u", "first_question": None},
        {"id": "c-1", "user_id": "u", "first_question": "Find IFA"},
    ]
    convo_query.eq.return_value.order.return_value.range.assert_called_once_with(0, 19)


def test_an_empty_list_skips_the_question_lookup(dao):
    query = dao.client.table.return_value.select.return_value
    query.order.return_value.range.return_value.execute.return_value.data = []

    assert dao.list_conversations(None, 20, 0) == []
    query.in_.assert_not_called()


def test_detail_and_tool_call_reads(dao):
    select = dao.client.table.return_value.select
    chain = select.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value
    chain.data = [{"turn": 1}]

    assert dao.list_messages_detail("c-1") == [{"turn": 1}]
    assert "duration_ms" in select.call_args.args[0]
    assert dao.list_tool_calls("c-1") == [{"turn": 1}]
    assert "tool_name" in select.call_args.args[0]

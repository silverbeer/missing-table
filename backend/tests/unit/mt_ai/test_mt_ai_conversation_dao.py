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

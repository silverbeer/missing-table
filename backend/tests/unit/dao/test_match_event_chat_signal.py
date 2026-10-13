"""MatchEventDAO rings the live chat doorbell (SB-1329).

Clients can no longer read chat rows, so Realtime cannot carry them. Every
write that changes a match's chat touches live_chat_signals instead, and
clients re-read chat through the API when it changes.
"""

from unittest.mock import MagicMock

import pytest

from dao.match_event_dao import MatchEventDAO


def _dao(event_rows=None, signal_error=None):
    dao = object.__new__(MatchEventDAO)
    dao.connection_holder = MagicMock()

    events = MagicMock()
    for method in ("insert", "update", "eq"):
        getattr(events, method).return_value = events
    events.execute.return_value = MagicMock(data=event_rows)

    signals = MagicMock()
    signals.upsert.return_value = signals
    if signal_error:
        signals.execute.side_effect = signal_error

    client = MagicMock()
    client.table.side_effect = lambda name: {"match_events": events, "live_chat_signals": signals}[name]
    dao.client = client
    dao._signals = signals
    return dao


def _rung(dao):
    return [c.args[0]["match_id"] for c in dao._signals.upsert.call_args_list]


@pytest.mark.unit
class TestChatSignal:
    def test_posting_a_message_rings(self):
        dao = _dao(event_rows=[{"id": 1, "match_id": 7, "event_type": "message"}])
        dao.create_event(match_id=7, event_type="message", message="hi")
        assert _rung(dao) == [7]
        assert dao._signals.upsert.call_args.kwargs == {"on_conflict": "match_id"}

    def test_a_goal_does_not_ring(self):
        # Goals still stream over Realtime directly; ringing would only cost a re-read.
        dao = _dao(event_rows=[{"id": 2, "match_id": 7, "event_type": "goal"}])
        dao.create_event(match_id=7, event_type="goal", message="Goal!")
        assert _rung(dao) == []

    def test_deleting_a_message_rings(self):
        dao = _dao(event_rows=[{"id": 1, "match_id": 7, "event_type": "message", "is_deleted": True}])
        assert dao.soft_delete_event(1, deleted_by="admin") is True
        assert _rung(dao) == [7]

    def test_deleting_a_goal_does_not_ring(self):
        dao = _dao(event_rows=[{"id": 2, "match_id": 7, "event_type": "goal", "is_deleted": True}])
        dao.soft_delete_event(2, deleted_by="admin")
        assert _rung(dao) == []

    def test_a_failed_ring_does_not_fail_the_post(self):
        dao = _dao(
            event_rows=[{"id": 1, "match_id": 7, "event_type": "message"}],
            signal_error=RuntimeError("signals table missing"),
        )
        created = dao.create_event(match_id=7, event_type="message", message="hi")
        assert created == {"id": 1, "match_id": 7, "event_type": "message"}

    def test_a_failed_ring_does_not_fail_the_delete(self):
        dao = _dao(
            event_rows=[{"id": 1, "match_id": 7, "event_type": "message"}],
            signal_error=RuntimeError("down"),
        )
        assert dao.soft_delete_event(1, deleted_by="admin") is True

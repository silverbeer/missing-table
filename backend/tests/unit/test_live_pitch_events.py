"""Pitch events on the live match state (SB-1369).

Clients rebuild the on-pitch XI by replaying substitution and position_change
events over the starting lineup. recent_events is the last 50 events
*including chat*, so in a chatty match early subs fell out of the window and
the XI came out wrong. GET /live now also returns pitch_events: every sub and
position change for the match, oldest first, with no limit.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

USER = {"user_id": "fan-1", "id": "fan-1", "username": "fan", "role": "user"}


class _FakeQuery:
    """Minimal in-memory stand-in for the supabase query builder."""

    def __init__(self, rows: list[dict]):
        self._rows = list(rows)
        self._order: list[tuple[str, bool]] = []
        self._limit: int | None = None
        self.calls: list[str] = []

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self.calls.append(f"eq:{col}")
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def in_(self, col, vals):
        self.calls.append(f"in:{col}")
        self._rows = [r for r in self._rows if r.get(col) in vals]
        return self

    def order(self, col, desc=False):
        self._order.append((col, desc))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        rows = self._rows
        for col, desc in reversed(self._order):
            rows = sorted(rows, key=lambda r, c=col: r[c], reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        result = MagicMock()
        result.data = rows
        return result


def _dao(rows: list[dict]):
    from dao.match_event_dao import MatchEventDAO

    dao = MatchEventDAO.__new__(MatchEventDAO)
    dao.client = MagicMock()
    dao.client.table.side_effect = lambda _name: _FakeQuery(rows)
    return dao


def _ev(id_, type_, minute, *, match_id=123, deleted=False):
    return {
        "id": id_,
        "match_id": match_id,
        "event_type": type_,
        "is_deleted": deleted,
        "created_at": f"2026-10-20T10:{minute:02d}:00+00:00",
        "message": f"{type_} {id_}",
    }


@pytest.mark.unit
class TestGetPitchEvents:
    def test_only_substitutions_and_position_changes(self):
        rows = [
            _ev(1, "goal", 1),
            _ev(2, "substitution", 2),
            _ev(3, "message", 3),
            _ev(4, "position_change", 4),
            _ev(5, "card", 5),
            _ev(6, "status_change", 6),
        ]
        events = _dao(rows).get_pitch_events(123)
        assert [e["id"] for e in events] == [2, 4]

    def test_oldest_first_with_id_tiebreak(self):
        rows = [
            _ev(9, "substitution", 30),
            _ev(4, "position_change", 10),
            _ev(7, "substitution", 20),
            _ev(6, "substitution", 20),  # same created_at as 7: id breaks the tie
        ]
        events = _dao(rows).get_pitch_events(123)
        assert [e["id"] for e in events] == [4, 6, 7, 9]

    def test_deleted_and_other_matches_excluded(self):
        rows = [
            _ev(1, "substitution", 1, deleted=True),
            _ev(2, "substitution", 2, match_id=999),
            _ev(3, "position_change", 3),
        ]
        events = _dao(rows).get_pitch_events(123)
        assert [e["id"] for e in events] == [3]

    def test_chat_heavy_match_keeps_early_subs(self):
        # Two early subs, then 200 chat messages, then a late position change.
        rows = [_ev(1, "substitution", 1), _ev(2, "substitution", 2)]
        rows += [_ev(100 + i, "message", 5 + i // 60) for i in range(200)]
        rows.append(_ev(999, "position_change", 59))
        dao = _dao(rows)

        # The bug: the last-50 window is all chat.
        recent = dao.get_events(123, limit=50)
        assert not any(e["event_type"] == "substitution" for e in recent)

        events = dao.get_pitch_events(123)
        assert [e["id"] for e in events] == [1, 2, 999]

    def test_query_failure_returns_none_not_empty(self):
        from dao.match_event_dao import MatchEventDAO

        dao = MatchEventDAO.__new__(MatchEventDAO)
        dao.client = MagicMock()
        dao.client.table.side_effect = RuntimeError("db down")
        assert dao.get_pitch_events(123) is None


@pytest.fixture
def app_as_fan():
    from app import app
    from auth import get_current_user_required

    app.dependency_overrides[get_current_user_required] = lambda: USER
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
class TestLiveStateEndpoint:
    def _get(self, app, pitch_events):
        with (
            patch("app.match_dao") as match_dao,
            patch("app.match_event_dao") as event_dao,
            patch("app.moderation_dao") as mod_dao,
        ):
            match_dao.get_live_match_state.return_value = {"match_id": 123}
            mod_dao.blocked_user_ids.return_value = []
            event_dao.get_events.return_value = [_ev(50, "message", 50)]
            event_dao.get_pitch_events.return_value = pitch_events

            resp = TestClient(app).get("/api/matches/123/live")
        event_dao.get_pitch_events.assert_called_once_with(123)
        return resp

    def test_pitch_events_in_response(self, app_as_fan):
        subs = [_ev(2, "substitution", 2), _ev(4, "position_change", 4)]
        resp = self._get(app_as_fan, subs)

        assert resp.status_code == 200
        body = resp.json()
        assert [e["id"] for e in body["pitch_events"]] == [2, 4]
        assert [e["id"] for e in body["recent_events"]] == [50]

    def test_no_changes_is_an_empty_list(self, app_as_fan):
        resp = self._get(app_as_fan, [])
        assert resp.json()["pitch_events"] == []

    def test_failed_read_omits_field(self, app_as_fan):
        resp = self._get(app_as_fan, None)
        assert resp.status_code == 200
        assert "pitch_events" not in resp.json()


@pytest.mark.unit
def test_model_declares_pitch_events():
    from models.live_match import LiveMatchState

    assert LiveMatchState.model_fields["pitch_events"].default == []

"""Moderation on the live chat endpoints in app.py (SB-1309).

POST /live/message refuses filtered language, banned users and floods; the
reads hide chat from users the viewer blocked; and an author may delete
their own message without being a match manager.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

USER = {"user_id": "fan-1", "id": "fan-1", "username": "fan", "role": "user"}


def _match():
    return {"id": 123, "home_team_id": 1, "away_team_id": 2, "home_score": 0, "away_score": 0}


@pytest.fixture
def app_as_fan():
    from app import app
    from auth import get_current_user_required
    from rate_limiter import limiter

    limiter.reset()
    app.dependency_overrides[get_current_user_required] = lambda: USER
    try:
        yield app
    finally:
        app.dependency_overrides.clear()
        limiter.reset()


def _bearer(sub: str) -> dict[str, str]:
    # Signature is irrelevant: auth is overridden, and user_key reads only `sub`.
    return {"Authorization": f"Bearer {jwt.encode({'sub': sub}, 'test-secret-not-real', algorithm='HS256')}"}


@pytest.mark.unit
class TestPostMessage:
    def test_filtered_language_is_422_and_not_stored(self, app_as_fan):
        with (
            patch("app.match_dao") as match_dao,
            patch("app.match_event_dao") as event_dao,
            patch("app.moderation_dao") as mod_dao,
        ):
            match_dao.get_match_by_id.return_value = _match()
            mod_dao.is_chat_banned.return_value = False

            resp = TestClient(app_as_fan).post("/api/matches/123/live/message", json={"message": "fuck the ref"})

        assert resp.status_code == 422
        assert resp.json() == {"detail": "Message contains language that isn't allowed"}
        event_dao.create_event.assert_not_called()

    def test_banned_user_is_403(self, app_as_fan):
        with (
            patch("app.match_dao") as match_dao,
            patch("app.match_event_dao") as event_dao,
            patch("app.moderation_dao") as mod_dao,
        ):
            match_dao.get_match_by_id.return_value = _match()
            mod_dao.is_chat_banned.return_value = True

            resp = TestClient(app_as_fan).post("/api/matches/123/live/message", json={"message": "great goal"})

        assert resp.status_code == 403
        assert resp.json() == {"detail": "You can no longer post in chat"}
        mod_dao.is_chat_banned.assert_called_once_with("fan-1")
        event_dao.create_event.assert_not_called()

    def test_clean_message_from_unbanned_user_posts(self, app_as_fan):
        with (
            patch("app.match_dao") as match_dao,
            patch("app.match_event_dao") as event_dao,
            patch("app.moderation_dao") as mod_dao,
        ):
            match_dao.get_match_by_id.return_value = _match()
            mod_dao.is_chat_banned.return_value = False
            event_dao.create_event.return_value = {"id": 1, "event_type": "message"}

            resp = TestClient(app_as_fan).post("/api/matches/123/live/message", json={"message": "Scunthorpe!"})

        assert resp.status_code == 200
        event_dao.create_event.assert_called_once()

    def test_eleventh_message_in_a_minute_is_429_per_user(self, app_as_fan):
        with (
            patch("app.match_dao") as match_dao,
            patch("app.match_event_dao") as event_dao,
            patch("app.moderation_dao") as mod_dao,
        ):
            match_dao.get_match_by_id.return_value = _match()
            mod_dao.is_chat_banned.return_value = False
            event_dao.create_event.return_value = {"id": 1, "event_type": "message"}
            client = TestClient(app_as_fan)

            codes = [
                client.post(
                    "/api/matches/123/live/message", json={"message": "hi"}, headers=_bearer("fan-1")
                ).status_code
                for _ in range(11)
            ]
            # Same IP, different user: a separate bucket.
            other = client.post("/api/matches/123/live/message", json={"message": "hi"}, headers=_bearer("fan-2"))

        assert codes[:10] == [200] * 10
        assert codes[10] == 429
        assert other.status_code == 200

    def test_the_chat_route_carries_a_limit(self):
        import app as app_module

        route = next(
            r for r in app_module.app.routes if getattr(r, "path", "") == "/api/matches/{match_id}/live/message"
        )
        assert hasattr(route.endpoint, "__wrapped__")


@pytest.mark.unit
class TestReadsHideBlockedChat:
    def test_events_endpoint_passes_blocked_users(self, app_as_fan):
        with patch("app.match_event_dao") as event_dao, patch("app.moderation_dao") as mod_dao:
            mod_dao.blocked_user_ids.return_value = ["troll-1"]
            event_dao.get_events.return_value = []

            resp = TestClient(app_as_fan).get("/api/matches/123/live/events")

        assert resp.status_code == 200
        mod_dao.blocked_user_ids.assert_called_once_with("fan-1")
        assert event_dao.get_events.call_args.kwargs["exclude_messages_by"] == ["troll-1"]

    def test_live_state_passes_blocked_users(self, app_as_fan):
        with (
            patch("app.match_dao") as match_dao,
            patch("app.match_event_dao") as event_dao,
            patch("app.moderation_dao") as mod_dao,
        ):
            match_dao.get_live_match_state.return_value = {"match_id": 123}
            mod_dao.blocked_user_ids.return_value = ["troll-1"]
            event_dao.get_events.return_value = []

            resp = TestClient(app_as_fan).get("/api/matches/123/live")

        assert resp.status_code == 200
        assert event_dao.get_events.call_args.kwargs["exclude_messages_by"] == ["troll-1"]


@pytest.mark.unit
class TestGetEventsExclusion:
    def _dao(self):
        from dao.match_event_dao import MatchEventDAO

        dao = MatchEventDAO.__new__(MatchEventDAO)
        dao.client = MagicMock()
        query = dao.client.table.return_value.select.return_value.eq.return_value.eq.return_value
        query = query.order.return_value.limit.return_value
        query.execute.return_value.data = []
        query.or_.return_value.execute.return_value.data = []
        return dao, query

    def test_only_chat_messages_by_blocked_users_are_excluded(self):
        dao, query = self._dao()
        dao.get_events(123, exclude_messages_by=["a", "b"])

        # Goals, cards, subs and authorless events are kept: blocking a
        # manager must not hide the goals they record.
        query.or_.assert_called_once_with("event_type.neq.message,created_by.is.null,created_by.not.in.(a,b)")

    def test_no_blocks_no_filter(self):
        dao, query = self._dao()
        dao.get_events(123, exclude_messages_by=[])
        query.or_.assert_not_called()


@pytest.mark.unit
class TestAuthorSelfDelete:
    def _patches(self):
        return (
            patch("app.match_dao"),
            patch("app.match_event_dao"),
            patch("app.auth_manager"),
        )

    def test_author_deletes_own_message_without_manager_role(self, app_as_fan):
        p1, p2, p3 = self._patches()
        with p1 as match_dao, p2 as event_dao, p3 as auth_manager:
            match_dao.get_match_by_id.return_value = _match()
            event_dao.get_event_by_id.return_value = {
                "id": 5,
                "match_id": 123,
                "event_type": "message",
                "created_by": "fan-1",
            }
            event_dao.soft_delete_event.return_value = True

            resp = TestClient(app_as_fan).delete("/api/matches/123/live/events/5")

        assert resp.status_code == 200
        event_dao.soft_delete_event.assert_called_once_with(5, deleted_by="fan-1")
        auth_manager.can_edit_match.assert_not_called()

    def test_fan_cannot_delete_someone_elses_message(self, app_as_fan):
        p1, p2, p3 = self._patches()
        with p1 as match_dao, p2 as event_dao, p3:
            match_dao.get_match_by_id.return_value = _match()
            event_dao.get_event_by_id.return_value = {
                "id": 5,
                "match_id": 123,
                "event_type": "message",
                "created_by": "someone-else",
            }

            resp = TestClient(app_as_fan).delete("/api/matches/123/live/events/5")

        assert resp.status_code == 403
        event_dao.soft_delete_event.assert_not_called()

    def test_fan_cannot_delete_a_goal_they_recorded(self, app_as_fan):
        p1, p2, p3 = self._patches()
        with p1 as match_dao, p2 as event_dao, p3:
            match_dao.get_match_by_id.return_value = _match()
            event_dao.get_event_by_id.return_value = {
                "id": 5,
                "match_id": 123,
                "event_type": "goal",
                "created_by": "fan-1",
            }

            resp = TestClient(app_as_fan).delete("/api/matches/123/live/events/5")

        assert resp.status_code == 403
        event_dao.soft_delete_event.assert_not_called()

    def test_manager_still_deletes_any_event(self, app_as_fan):
        from auth import get_current_user_required

        manager = {"user_id": "mgr-1", "username": "mgr", "role": "team-manager"}
        app_as_fan.dependency_overrides[get_current_user_required] = lambda: manager
        p1, p2, p3 = self._patches()
        with p1 as match_dao, p2 as event_dao, p3 as auth_manager:
            match_dao.get_match_by_id.return_value = _match()
            auth_manager.can_edit_match.return_value = True
            event_dao.get_event_by_id.return_value = {
                "id": 5,
                "match_id": 123,
                "event_type": "message",
                "created_by": "fan-1",
            }
            event_dao.soft_delete_event.return_value = True

            resp = TestClient(app_as_fan).delete("/api/matches/123/live/events/5")

        assert resp.status_code == 200
        event_dao.soft_delete_event.assert_called_once_with(5, deleted_by="mgr-1")

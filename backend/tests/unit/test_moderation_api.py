"""Chat report, block and admin review endpoints (SB-1309).

The router is mounted on a bare app with auth overridden and both DAOs
mocked, so these pin the endpoint rules — status codes, idempotency, who may
act — without a database.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPORTER = {"user_id": "reporter-1", "username": "parent", "role": "user"}
ADMIN = {"user_id": "admin-1", "username": "admin", "role": "admin"}
AUTHOR_ID = "author-1"


def _chat_event(**overrides):
    event = {
        "id": 77,
        "match_id": 123,
        "event_type": "message",
        "message": "something nasty",
        "created_by": AUTHOR_ID,
        "created_by_username": "troll",
    }
    event.update(overrides)
    return event


@pytest.fixture
def harness():
    """Bare app with the moderation router; `as_user` swaps who is calling."""
    from api import moderation
    from auth import get_current_user_required

    app = FastAPI()
    app.include_router(moderation.router)
    caller = {"user": REPORTER}
    app.dependency_overrides[get_current_user_required] = lambda: caller["user"]

    mod_dao = MagicMock()
    event_dao = MagicMock()
    with (
        patch.object(moderation, "_moderation_dao", return_value=mod_dao),
        patch.object(moderation, "_event_dao", return_value=event_dao),
        patch.object(moderation, "alert_content_report") as alert,
    ):

        def as_user(user):
            caller["user"] = user

        yield TestClient(app), mod_dao, event_dao, alert, as_user


@pytest.mark.unit
class TestReport:
    URL = "/api/matches/123/live/events/77/report"

    def test_report_records_blocks_author_and_alerts(self, harness):
        client, mod_dao, event_dao, alert, _ = harness
        event_dao.get_event_by_id.return_value = _chat_event()
        mod_dao.create_report.return_value = {"id": 1}

        resp = client.post(self.URL, json={"reason": "harassment", "details": "targeting my kid"})

        assert resp.status_code == 201
        assert resp.json() == {"reported": True, "blocked_user_id": AUTHOR_ID}
        mod_dao.create_report.assert_called_once()
        assert mod_dao.create_report.call_args.kwargs["reason"] == "harassment"
        mod_dao.block_user.assert_called_once_with("reporter-1", AUTHOR_ID)
        alert.assert_called_once()

    def test_repeat_report_is_201_and_does_not_alert_again(self, harness):
        client, mod_dao, event_dao, alert, _ = harness
        event_dao.get_event_by_id.return_value = _chat_event()
        mod_dao.create_report.return_value = None  # unique (event, reporter) already present

        resp = client.post(self.URL, json={"reason": "spam"})

        assert resp.status_code == 201
        assert resp.json()["blocked_user_id"] == AUTHOR_ID
        alert.assert_not_called()

    def test_reporting_own_message_is_400(self, harness):
        client, mod_dao, event_dao, _, _ = harness
        event_dao.get_event_by_id.return_value = _chat_event(created_by="reporter-1")

        resp = client.post(self.URL, json={"reason": "spam"})

        assert resp.status_code == 400
        mod_dao.create_report.assert_not_called()

    def test_reporting_a_goal_is_400(self, harness):
        client, mod_dao, event_dao, _, _ = harness
        event_dao.get_event_by_id.return_value = _chat_event(event_type="goal")

        assert client.post(self.URL, json={"reason": "spam"}).status_code == 400
        mod_dao.create_report.assert_not_called()

    def test_unknown_event_is_404(self, harness):
        client, _, event_dao, _, _ = harness
        event_dao.get_event_by_id.return_value = None
        assert client.post(self.URL, json={"reason": "spam"}).status_code == 404

    def test_event_from_another_match_is_404(self, harness):
        client, _, event_dao, _, _ = harness
        event_dao.get_event_by_id.return_value = _chat_event(match_id=999)
        assert client.post(self.URL, json={"reason": "spam"}).status_code == 404

    def test_unknown_reason_is_422(self, harness):
        client, _, event_dao, _, _ = harness
        event_dao.get_event_by_id.return_value = _chat_event()
        assert client.post(self.URL, json={"reason": "rude"}).status_code == 422

    def test_details_over_500_chars_is_422(self, harness):
        client, _, event_dao, _, _ = harness
        event_dao.get_event_by_id.return_value = _chat_event()
        assert client.post(self.URL, json={"reason": "other", "details": "x" * 501}).status_code == 422


@pytest.mark.unit
class TestReportAlertFailure:
    def test_a_failing_alert_does_not_fail_the_report(self, monkeypatch):
        """The real alert function, with Telegram raising."""
        from api import moderation
        from auth import get_current_user_required

        monkeypatch.setenv("MT_ADMIN_TELEGRAM_CHAT_ID", "-100123")
        app = FastAPI()
        app.include_router(moderation.router)
        app.dependency_overrides[get_current_user_required] = lambda: REPORTER

        mod_dao = MagicMock()
        mod_dao.create_report.return_value = {"id": 1, "reason": "hate", "message_text": "x", "match_id": 123}
        mod_dao.count_reports_since.return_value = 1
        event_dao = MagicMock()
        event_dao.get_event_by_id.return_value = _chat_event()

        with (
            patch.object(moderation, "_moderation_dao", return_value=mod_dao),
            patch.object(moderation, "_event_dao", return_value=event_dao),
            patch("notifications.moderation_alerts.send_to", side_effect=RuntimeError("telegram down")) as send,
        ):
            resp = TestClient(app).post("/api/matches/123/live/events/77/report", json={"reason": "hate"})

        assert resp.status_code == 201
        send.assert_called_once()


@pytest.mark.unit
class TestAlert:
    def test_unconfigured_chat_sends_nothing(self, monkeypatch):
        from notifications.moderation_alerts import alert_content_report

        monkeypatch.delenv("MT_ADMIN_TELEGRAM_CHAT_ID", raising=False)
        with patch("notifications.moderation_alerts.send_to") as send:
            assert alert_content_report(MagicMock(), {"id": 1}, "parent") is False
        send.assert_not_called()

    def test_message_names_reporter_author_reason_and_match_and_truncates_text(self, monkeypatch):
        from notifications.moderation_alerts import alert_content_report

        monkeypatch.setenv("MT_ADMIN_TELEGRAM_CHAT_ID", "-100123")
        dao = MagicMock()
        dao.count_reports_since.return_value = 1
        report = {"id": 1, "reason": "hate", "reported_username": "troll", "match_id": 123, "message_text": "y" * 400}
        with patch("notifications.moderation_alerts.send_to") as send:
            assert alert_content_report(dao, report, "parent") is True

        text = send.call_args.args[2]
        assert "troll" in text and "parent" in text and "hate" in text and "123" in text
        assert "y" * 400 not in text

    def test_past_the_cap_goes_quiet(self, monkeypatch):
        from notifications.moderation_alerts import alert_content_report

        monkeypatch.setenv("MT_ADMIN_TELEGRAM_CHAT_ID", "-100123")
        monkeypatch.setenv("MT_REPORT_ALERT_MAX_PER_HOUR", "2")
        dao = MagicMock()
        with patch("notifications.moderation_alerts.send_to") as send:
            dao.count_reports_since.return_value = 3  # two earlier: exactly at cap -> summary
            assert alert_content_report(dao, {"id": 3}, "parent") is True
            assert "more than 2 reports" in send.call_args.args[2]
            send.reset_mock()
            dao.count_reports_since.return_value = 4
            assert alert_content_report(dao, {"id": 4}, "parent") is False
        send.assert_not_called()


@pytest.mark.unit
class TestBlocks:
    def test_block_is_204(self, harness):
        client, mod_dao, _, _, _ = harness
        assert client.post("/api/users/other-1/block").status_code == 204
        mod_dao.block_user.assert_called_once_with("reporter-1", "other-1")

    def test_blocking_self_is_400(self, harness):
        client, mod_dao, _, _, _ = harness
        assert client.post("/api/users/reporter-1/block").status_code == 400
        mod_dao.block_user.assert_not_called()

    def test_blocking_unknown_user_is_404(self, harness):
        from dao.moderation_dao import UnknownUserError

        client, mod_dao, _, _, _ = harness
        mod_dao.block_user.side_effect = UnknownUserError("nope")
        assert client.post("/api/users/nope/block").status_code == 404

    def test_unblock_is_204_even_when_not_blocked(self, harness):
        client, mod_dao, _, _, _ = harness
        assert client.delete("/api/users/other-1/block").status_code == 204
        mod_dao.unblock_user.assert_called_once_with("reporter-1", "other-1")

    def test_list_blocks(self, harness):
        client, mod_dao, _, _, _ = harness
        rows = [{"user_id": "other-1", "username": "troll", "created_at": "2026-10-10T12:00:00+00:00"}]
        mod_dao.list_blocks.return_value = rows

        resp = client.get("/api/users/me/blocks")

        assert resp.status_code == 200
        assert resp.json() == rows
        mod_dao.list_blocks.assert_called_once_with("reporter-1")


@pytest.mark.unit
class TestAdminReview:
    def test_non_admin_cannot_list_or_act(self, harness):
        client, mod_dao, _, _, as_user = harness
        as_user(REPORTER)
        assert client.get("/api/admin/content-reports?status=pending").status_code == 403
        assert client.patch("/api/admin/content-reports/1", json={"action": "dismiss"}).status_code == 403
        mod_dao.list_reports.assert_not_called()
        mod_dao.resolve_report.assert_not_called()

    def test_admin_lists_pending(self, harness):
        client, mod_dao, _, _, as_user = harness
        as_user(ADMIN)
        mod_dao.list_reports.return_value = [{"id": 1, "status": "pending"}]

        resp = client.get("/api/admin/content-reports?status=pending")

        assert resp.status_code == 200
        mod_dao.list_reports.assert_called_once_with("pending")

    def test_bad_status_filter_is_422(self, harness):
        client, _, _, _, as_user = harness
        as_user(ADMIN)
        assert client.get("/api/admin/content-reports?status=open").status_code == 422

    def test_dismiss_touches_nothing_but_the_report(self, harness):
        client, mod_dao, event_dao, _, as_user = harness
        as_user(ADMIN)
        mod_dao.get_report.return_value = {"id": 1, "event_id": 77, "reported_user_id": AUTHOR_ID}
        mod_dao.resolve_report.return_value = {"id": 1, "status": "dismissed"}

        resp = client.patch("/api/admin/content-reports/1", json={"action": "dismiss"})

        assert resp.status_code == 200
        event_dao.soft_delete_event.assert_not_called()
        mod_dao.ban_from_chat.assert_not_called()
        assert mod_dao.resolve_report.call_args.kwargs["status"] == "dismissed"

    def test_delete_message_soft_deletes_it(self, harness):
        client, mod_dao, event_dao, _, as_user = harness
        as_user(ADMIN)
        mod_dao.get_report.return_value = {"id": 1, "event_id": 77, "reported_user_id": AUTHOR_ID}
        mod_dao.resolve_report.return_value = {"id": 1, "status": "actioned"}

        resp = client.patch("/api/admin/content-reports/1", json={"action": "delete_message"})

        assert resp.status_code == 200
        event_dao.soft_delete_event.assert_called_once_with(77, deleted_by="admin-1")
        mod_dao.ban_from_chat.assert_not_called()
        assert mod_dao.resolve_report.call_args.kwargs["status"] == "actioned"

    def test_ban_user_deletes_message_and_bans_author(self, harness):
        client, mod_dao, event_dao, _, as_user = harness
        as_user(ADMIN)
        mod_dao.get_report.return_value = {"id": 1, "event_id": 77, "reported_user_id": AUTHOR_ID}
        mod_dao.resolve_report.return_value = {"id": 1, "status": "actioned"}

        resp = client.patch("/api/admin/content-reports/1", json={"action": "ban_user"})

        assert resp.status_code == 200
        event_dao.soft_delete_event.assert_called_once_with(77, deleted_by="admin-1")
        mod_dao.ban_from_chat.assert_called_once_with(AUTHOR_ID)

    def test_expired_message_still_resolves(self, harness):
        client, mod_dao, event_dao, _, as_user = harness
        as_user(ADMIN)
        mod_dao.get_report.return_value = {"id": 1, "event_id": None, "reported_user_id": AUTHOR_ID}
        mod_dao.resolve_report.return_value = {"id": 1, "status": "actioned"}

        assert client.patch("/api/admin/content-reports/1", json={"action": "delete_message"}).status_code == 200
        event_dao.soft_delete_event.assert_not_called()

    def test_unknown_report_is_404(self, harness):
        client, mod_dao, _, _, as_user = harness
        as_user(ADMIN)
        mod_dao.get_report.return_value = None
        assert client.patch("/api/admin/content-reports/9", json={"action": "dismiss"}).status_code == 404

    def test_unknown_action_is_422(self, harness):
        client, _, _, _, as_user = harness
        as_user(ADMIN)
        assert client.patch("/api/admin/content-reports/1", json={"action": "nuke"}).status_code == 422

"""Scraped scores send match alerts (SB-1619).

The match-scraper worker writes scores straight to the database and has no push
credentials, so it asks the API: POST /api/matches/{id}/final-score-alert.
Covers the API's rules (final_alert_blocker), the endpoint (who may call it,
once-only claim), and the worker's caller (when it asks, and that it never
raises).
"""

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from celery_tasks.final_score_alert import alert_if_new_final_score, service_token
from notifications.score_change import final_alert_blocker

TODAY = date(2026, 11, 10)


def _match(**over):
    return {"id": 7, "home_score": 2, "away_score": 1, "match_status": "completed", "match_date": "2026-11-09", **over}


@pytest.mark.unit
class TestFinalAlertBlocker:
    def test_a_recent_completed_score_may_alert(self):
        assert final_alert_blocker(_match(), TODAY) is None

    def test_today_and_the_window_edge_may_alert(self):
        assert final_alert_blocker(_match(match_date="2026-11-10"), TODAY) is None
        assert final_alert_blocker(_match(match_date="2026-11-07"), TODAY) is None

    @pytest.mark.parametrize(
        "match,reason",
        [
            (None, "not_found"),
            (_match(home_score=None), "no_score"),
            (_match(away_score=None), "no_score"),
            (_match(match_status="tbd"), "not_completed"),
            (_match(match_date="2026-11-06"), "too_old"),  # a backfill
            (_match(match_date="2025-03-01"), "too_old"),  # a season load
            (_match(match_date="2026-11-11"), "too_old"),  # future-dated
            (_match(match_date=None), "too_old"),
        ],
    )
    def test_blockers(self, match, reason):
        assert final_alert_blocker(match, TODAY) == reason

    def test_a_timestamp_date_is_read_as_its_day(self):
        assert final_alert_blocker(_match(match_date="2026-11-09T19:00:00+00:00"), TODAY) is None


# --- endpoint -------------------------------------------------------------------

SERVICE = {"role": "service_account", "service_name": "match-scraper-worker", "permissions": ["manage_matches"]}


def _post(user, match=_match(), claimed=True):
    import app as app_module
    from app import app
    from auth import get_current_user_required

    app.dependency_overrides[get_current_user_required] = lambda: user
    try:
        with (
            patch.object(app_module.match_dao, "get_match_by_id", return_value=match),
            patch("api.club_notifications.claim_once", return_value=claimed) as claim,
            patch.object(app_module, "notify_event_task") as notify,
            patch.object(app_module, "datetime") as dt,
        ):
            dt.now.return_value = datetime(2026, 11, 10, 12, tzinfo=UTC)
            response = TestClient(app).post("/api/matches/7/final-score-alert")
    finally:
        app.dependency_overrides.clear()
    return response, claim, notify


@pytest.mark.unit
class TestFinalScoreAlertEndpoint:
    def test_service_account_queues_the_fulltime_alert_keyed_by_score(self):
        response, claim, notify = _post(SERVICE)
        assert response.status_code == 200
        assert response.json() == {"match_id": 7, "queued": True, "reason": None}
        claim.assert_called_once()
        assert claim.call_args.args[0] == "alert:sent:match:7:fulltime:2-1"
        notify.assert_called_once_with("fulltime", 7, None, "match:7:fulltime:2-1")

    def test_a_repeat_call_does_not_alert_twice(self):
        response, _, notify = _post(SERVICE, claimed=False)
        assert response.json() == {"match_id": 7, "queued": False, "reason": "already_sent"}
        notify.assert_not_called()

    def test_an_old_match_is_skipped_before_claiming(self):
        response, claim, notify = _post(SERVICE, match=_match(match_date="2026-01-01"))
        assert response.json()["reason"] == "too_old"
        claim.assert_not_called()
        notify.assert_not_called()

    def test_unknown_match_is_404(self):
        response, _, notify = _post(SERVICE, match=None)
        assert response.status_code == 404
        notify.assert_not_called()

    def test_admin_may_call(self):
        assert _post({"role": "admin", "username": "tom"})[0].status_code == 200

    @pytest.mark.parametrize(
        "user",
        [
            {"role": "team-manager", "username": "m"},
            {"role": "club_manager", "username": "c"},
            {"role": "team-fan", "username": "f"},
            {"role": "service_account", "service_name": "other", "permissions": ["read"]},
        ],
    )
    def test_others_may_not(self, user):
        response, _, notify = _post(user)
        assert response.status_code == 403
        notify.assert_not_called()


# --- worker caller -----------------------------------------------------------------

BEFORE = {"id": 7, "home_score": None, "away_score": None, "match_status": "tbd"}
AFTER = {"id": 7, "home_score": 2, "away_score": 1, "match_status": "completed"}


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("MT_API_URL", "https://api.example/")
    monkeypatch.setenv("SERVICE_ACCOUNT_SECRET", "s3cret-for-tests")  # pragma: allowlist secret


@pytest.mark.unit
class TestWorkerCaller:
    def test_new_final_score_posts_with_a_service_token(self, configured):
        post = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"queued": True}))
        assert alert_if_new_final_score(BEFORE, AFTER, post=post) is True
        url = post.call_args.args[0]
        assert url == "https://api.example/api/matches/7/final-score-alert"
        token = post.call_args.kwargs["headers"]["Authorization"].removeprefix("Bearer ")
        claims = jwt.decode(token, "s3cret-for-tests", algorithms=["HS256"], audience="service-account")
        assert claims["role"] == "service_account" and claims["permissions"] == ["manage_matches"]

    def test_unchanged_score_does_not_call(self, configured):
        post = MagicMock()
        assert alert_if_new_final_score(AFTER, AFTER, post=post) is False
        post.assert_not_called()

    def test_a_new_match_with_a_score_calls(self, configured):
        post = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {}))
        assert alert_if_new_final_score(None, AFTER, post=post) is True

    def test_dormant_without_config(self, monkeypatch):
        monkeypatch.delenv("MT_API_URL", raising=False)
        post = MagicMock()
        assert alert_if_new_final_score(BEFORE, AFTER, post=post) is False
        post.assert_not_called()

    @pytest.mark.parametrize("failure", [RuntimeError("down"), None])
    def test_never_raises(self, configured, failure):
        rejected = MagicMock(return_value=MagicMock(status_code=500))
        post = MagicMock(side_effect=failure) if failure else rejected
        assert alert_if_new_final_score(BEFORE, AFTER, post=post) is True

    def test_token_is_accepted_by_the_api_verifier(self, monkeypatch):
        monkeypatch.setenv("SERVICE_ACCOUNT_SECRET", "shared")  # pragma: allowlist secret
        from auth import AuthManager

        manager = AuthManager.__new__(AuthManager)
        manager.service_account_secret = "shared"  # pragma: allowlist secret
        verified = manager.verify_service_account_token(service_token("shared"))
        assert verified["role"] == "service_account"
        assert "manage_matches" in verified["permissions"]

"""End-to-end push-delivery integration test for bracket follows.

A user follows a tournament *bracket* — the tuple (tournament_id,
tournament_group, age_group_id) — rather than a team, and gets a push at
fulltime for every match in that bracket. This proves the new fan-out branch
in dispatcher._send_push_fanout end-to-end against the real local Supabase.

Mirrors test_push_delivery_on_score.py (the team-follow version). The only
mock is the push network send (pywebpush), injected as push_send_fn.

Requires local Supabase running. Skips cleanly if it isn't reachable.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app import app, require_admin, require_match_management_permission
from dao.match_dao import SupabaseConnection
from notifications.dispatcher import Notifier, set_notifier
from notifications.web_push_sender import SendResult

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]

_TEST_PASSWORD = "test-password-123"  # pragma: allowlist secret
_BRACKET = "Bracket A"


def _admin_client():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:55321")
    if not ("127.0.0.1" in url or "localhost" in url):
        pytest.skip(f"Refusing to run destructive test against non-local Supabase: {url}")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY not set — cannot run bracket-follow integration test")
    return create_client(url, key)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


class _RecordingSender:
    """Records every push call; never hits the network. Returns 'sent'."""

    def __init__(self, result: SendResult | None = None):
        self.calls: list[tuple[dict, dict]] = []
        self._result = result or SendResult(status="sent", http_status=201)

    def __call__(self, subscription: dict, payload: dict) -> SendResult:
        self.calls.append((subscription, payload))
        return self._result


@pytest.fixture
def world():
    """Seed a tournament with a bracket match + a bracket-follower with a device.

    The follower follows the BRACKET (tournament + group + age_group), NOT the
    team — so any push proves the bracket fan-out, not team-follow.
    """
    admin = _admin_client()
    try:
        admin.table("clubs").select("id").limit(1).execute()
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("Local Supabase not reachable")

    email = f"bracket-follow-{uuid.uuid4().hex[:8]}@missingtable.local"
    created = admin.auth.admin.create_user(
        {"email": email, "password": _TEST_PASSWORD, "email_confirm": True}
    )
    user_id = created.user.id
    admin.table("user_profiles").upsert(
        {"id": user_id, "email": email, "role": "team-fan"}
    ).execute()

    def _ref(table: str) -> int:
        return admin.table(table).select("id").limit(1).execute().data[0]["id"]

    age_group_id = _ref("age_groups")
    season_id = _ref("seasons")

    home_club = admin.table("clubs").insert(
        {"name": _unique("BkHome"), "city": "Houston"}
    ).execute().data[0]
    away_club = admin.table("clubs").insert(
        {"name": _unique("BkAway"), "city": "Bergen"}
    ).execute().data[0]
    home_team = admin.table("teams").insert(
        {"name": _unique("HomeTeam"), "city": "Houston", "club_id": home_club["id"]}
    ).execute().data[0]
    away_team = admin.table("teams").insert(
        {"name": _unique("AwayTeam"), "city": "Bergen", "club_id": away_club["id"]}
    ).execute().data[0]

    tournament = admin.table("tournaments").insert(
        {
            "name": _unique("Bracket Cup"),
            "start_date": datetime.now(UTC).date().isoformat(),
            "is_active": True,
        }
    ).execute().data[0]

    # Scheduled match tagged with the bracket group + a knockout round.
    match = admin.table("matches").insert(
        {
            "home_team_id": home_team["id"],
            "away_team_id": away_team["id"],
            "age_group_id": age_group_id,
            "season_id": season_id,
            "match_type_id": 2,  # TOURNAMENT_MATCH_TYPE_ID
            "tournament_id": tournament["id"],
            "tournament_group": _BRACKET,
            "tournament_round": "semifinal",
            "match_date": datetime.now(UTC).date().isoformat(),
            "match_status": "scheduled",
        }
    ).execute().data[0]

    # The user follows the BRACKET and has one registered device.
    admin.table("user_bracket_follows").insert(
        {
            "user_id": user_id,
            "tournament_id": tournament["id"],
            "tournament_group": _BRACKET,
            "age_group_id": age_group_id,
        }
    ).execute()
    subscription = admin.table("push_subscriptions").insert(
        {
            "user_id": user_id,
            "endpoint": f"https://push.example/{uuid.uuid4().hex}",
            "p256dh_key": "p256dh-key-example",  # pragma: allowlist secret
            "auth_key": "auth-key-example",  # pragma: allowlist secret
            "device_label": "Test Phone",
        }
    ).execute().data[0]

    yield {
        "admin": admin,
        "user_id": user_id,
        "age_group_id": age_group_id,
        "home_team": home_team,
        "away_team": away_team,
        "tournament": tournament,
        "match": match,
        "subscription": subscription,
    }

    def _safe(fn):
        try:
            fn()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass

    _safe(lambda: admin.table("push_send_log").delete().eq("user_id", user_id).execute())
    _safe(lambda: admin.table("user_bracket_follows").delete().eq("user_id", user_id).execute())
    _safe(lambda: admin.table("user_notification_preferences").delete().eq("user_id", user_id).execute())
    _safe(lambda: admin.table("push_subscriptions").delete().eq("user_id", user_id).execute())
    _safe(lambda: admin.table("matches").delete().eq("id", match["id"]).execute())
    _safe(lambda: admin.table("tournaments").delete().eq("id", tournament["id"]).execute())
    _safe(lambda: admin.table("teams").delete().eq("id", home_team["id"]).execute())
    _safe(lambda: admin.table("teams").delete().eq("id", away_team["id"]).execute())
    _safe(lambda: admin.table("clubs").delete().eq("id", home_club["id"]).execute())
    _safe(lambda: admin.table("clubs").delete().eq("id", away_club["id"]).execute())
    _safe(lambda: admin.table("user_profiles").delete().eq("id", user_id).execute())
    _safe(lambda: admin.auth.admin.delete_user(user_id))


@pytest.fixture
def instrumented_notifier(monkeypatch):
    """Real-DAO Notifier with only the push network send faked. Yields
    (sender, notifier) so tests can also drive notify() directly."""
    monkeypatch.setattr("notifications.dispatcher.push_is_configured", lambda: True)
    sender = _RecordingSender()
    notifier = Notifier(connection=SupabaseConnection(), push_send_fn=sender)
    set_notifier(notifier)
    yield sender, notifier
    set_notifier(None)


@pytest.fixture(autouse=True)
def _override_admin_auth():
    fake_admin = {
        "user_id": "00000000-0000-0000-0000-0000000000ad",
        "id": "00000000-0000-0000-0000-0000000000ad",
        "email": "admin@missingtable.local",
        "username": "admin",
        "role": "admin",
    }
    app.dependency_overrides[require_admin] = lambda: fake_admin
    app.dependency_overrides[require_match_management_permission] = lambda: fake_admin
    yield
    app.dependency_overrides.clear()


def _push_log_rows(admin, match_id: int, user_id: str) -> list[dict]:
    return (
        admin.table("push_send_log")
        .select("*")
        .eq("match_id", match_id)
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )


def _score_url(world) -> str:
    return f"/api/admin/tournaments/{world['tournament']['id']}/matches/{world['match']['id']}"


class TestBracketScorePushesFollower:
    def test_fulltime_pushes_to_bracket_follower_and_logs(self, world, instrumented_notifier):
        sender, _ = instrumented_notifier
        with TestClient(app) as client:
            resp = client.put(
                _score_url(world),
                json={"home_score": 2, "away_score": 1, "match_status": "completed"},
            )
        assert resp.status_code == 200, resp.text

        assert len(sender.calls) == 1
        sub, payload = sender.calls[0]
        assert sub["endpoint"] == world["subscription"]["endpoint"]
        text = f"{payload.get('title', '')}\n{payload.get('body', '')}"
        assert "2-1" in text

        rows = _push_log_rows(world["admin"], world["match"]["id"], world["user_id"])
        assert len(rows) == 1
        assert rows[0]["event_type"] == "fulltime"
        assert rows[0]["status"] == "sent"

    def test_goal_event_does_not_push_bracket_follower(self, world, instrumented_notifier):
        """Bracket follows are fulltime-only — a goal event must stay silent
        for a user who follows the bracket but neither team."""
        sender, notifier = instrumented_notifier
        notifier.notify("goal", world["match"]["id"], {"team_id": world["home_team"]["id"]})
        assert sender.calls == []

    def test_fulltime_pref_off_suppresses_push(self, world, instrumented_notifier):
        """The shared per-user preference gate still applies: fulltime off → no push."""
        sender, _ = instrumented_notifier
        world["admin"].table("user_notification_preferences").upsert(
            {"user_id": world["user_id"], "event_type": "fulltime", "enabled": False},
            on_conflict="user_id,event_type",
        ).execute()

        with TestClient(app) as client:
            resp = client.put(
                _score_url(world),
                json={"home_score": 3, "away_score": 0, "match_status": "completed"},
            )
        assert resp.status_code == 200, resp.text
        assert sender.calls == []

    def test_following_team_and_bracket_dedupes_to_one_push(self, world, instrumented_notifier):
        """A user who follows both the home team and the bracket gets exactly
        one push per device, not two."""
        sender, _ = instrumented_notifier
        world["admin"].table("user_team_follows").insert(
            {"user_id": world["user_id"], "team_id": world["home_team"]["id"]}
        ).execute()
        try:
            with TestClient(app) as client:
                resp = client.put(
                    _score_url(world),
                    json={"home_score": 1, "away_score": 1, "match_status": "completed"},
                )
            assert resp.status_code == 200, resp.text
            assert len(sender.calls) == 1
        finally:
            world["admin"].table("user_team_follows").delete().eq(
                "user_id", world["user_id"]
            ).execute()

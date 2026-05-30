"""End-to-end push-delivery integration test for the follower-notify feature (SB-77).

This is the test that proves the "game changer": when a match score is written
via an admin/skill path, a user who follows one of the teams actually gets a
push — and the send is recorded in push_send_log.

It hits the real local Supabase for EVERYTHING in the delivery chain:
  - the real auth user + user_profiles row,
  - the real clubs, teams, tournament, match rows,
  - the real follow row + push subscription row,
  - the real fan-out query (TeamFollowDAO.list_subscriptions_for_team_ids),
  - the real preference gate (NotificationPreferencesDAO.get_preferences_batch),
  - the real push_send_log write,
  - FastAPI BackgroundTasks running the dispatcher after the response.

The ONLY thing mocked is the actual network call to the push service
(pywebpush) — injected as `push_send_fn` on the Notifier. Everything that
decides *who gets notified and whether it's logged* runs for real, which is
exactly the code that was least covered before this test (team_follow_dao at
~17%, push_send_log_dao, the dispatcher fan-out branch).

The TestClient is used as a context manager (`with TestClient(app) as client`)
so FastAPI BackgroundTasks run and complete inside the block — a bare
`TestClient(app)` lets the dispatcher run after the assertions, racing the
recorder.

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


# Throwaway password for ephemeral test auth users (deleted in teardown).
_TEST_PASSWORD = "test-password-123"  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Infrastructure helpers
# ---------------------------------------------------------------------------


def _admin_client():
    """Supabase client with the service-role key (bypasses RLS, auth.admin)."""
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
    # Hard safety rail: this test seeds + deletes rows and creates/deletes auth
    # users. It must NEVER run against a non-local Supabase. Skip unless the URL
    # is unambiguously local, regardless of how env/.mt-config resolved.
    if not ("127.0.0.1" in url or "localhost" in url):
        pytest.skip(f"Refusing to run destructive test against non-local Supabase: {url}")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY not set — cannot run push-delivery integration test")
    return create_client(url, key)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


class _RecordingSender:
    """Stand-in for web_push_sender.send_push — records every call, never hits
    the network. Returns 'sent' by default."""

    def __init__(self, result: SendResult | None = None):
        self.calls: list[tuple[dict, dict]] = []
        self._result = result or SendResult(status="sent", http_status=201)

    def __call__(self, subscription: dict, payload: dict) -> SendResult:
        self.calls.append((subscription, payload))
        return self._result


# ---------------------------------------------------------------------------
# Big seed fixture: a scored-able tournament match + a follower with a device
# ---------------------------------------------------------------------------


@pytest.fixture
def world():
    """Seed the full graph and yield handles. Tears everything down after.

    Graph:
      auth user + user_profiles (the follower)
      home_club, away_club
      home_team (in home_club), away_team (in away_club)
      tournament + one SCHEDULED tournament match home vs away (no score yet)
      follow: user follows home_team
      push subscription: user has one device
    """
    admin = _admin_client()
    try:
        admin.table("clubs").select("id").limit(1).execute()
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("Local Supabase not reachable")

    # --- auth user + profile (the follower) ---
    email = f"sb77-follow-{uuid.uuid4().hex[:8]}@missingtable.local"
    created = admin.auth.admin.create_user(
        {"email": email, "password": _TEST_PASSWORD, "email_confirm": True}
    )
    user_id = created.user.id
    # A user_profiles row is normally created by the on-auth trigger, but on
    # local it isn't reliably present by the time we insert the follow (which
    # FKs to user_profiles.id). Upsert it explicitly so the test doesn't depend
    # on trigger timing.
    admin.table("user_profiles").upsert(
        {"id": user_id, "email": email, "role": "team-fan"}
    ).execute()

    def _ref(table: str) -> int:
        return admin.table(table).select("id").limit(1).execute().data[0]["id"]

    age_group_id = _ref("age_groups")
    season_id = _ref("seasons")

    home_club = admin.table("clubs").insert(
        {"name": _unique("PushHome"), "city": "Houston"}
    ).execute().data[0]
    away_club = admin.table("clubs").insert(
        {"name": _unique("PushAway"), "city": "Bergen"}
    ).execute().data[0]

    home_team = admin.table("teams").insert(
        {"name": _unique("HomeTeam"), "city": "Houston", "club_id": home_club["id"]}
    ).execute().data[0]
    away_team = admin.table("teams").insert(
        {"name": _unique("AwayTeam"), "city": "Bergen", "club_id": away_club["id"]}
    ).execute().data[0]

    tournament = admin.table("tournaments").insert(
        {
            "name": _unique("SB77 Cup"),
            "start_date": datetime.now(UTC).date().isoformat(),
            "is_active": True,
        }
    ).execute().data[0]

    # A scheduled match with NO score yet — the state the skill loads first.
    match = admin.table("matches").insert(
        {
            "home_team_id": home_team["id"],
            "away_team_id": away_team["id"],
            "age_group_id": age_group_id,
            "season_id": season_id,
            "match_type_id": 2,  # TOURNAMENT_MATCH_TYPE_ID
            "tournament_id": tournament["id"],
            "match_date": datetime.now(UTC).date().isoformat(),
            "match_status": "scheduled",
        }
    ).execute().data[0]

    # The user follows the HOME team and has one registered device.
    admin.table("user_team_follows").insert(
        {"user_id": user_id, "team_id": home_team["id"]}
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
        "home_club": home_club,
        "away_club": away_club,
        "home_team": home_team,
        "away_team": away_team,
        "tournament": tournament,
        "match": match,
        "subscription": subscription,
    }

    # --- teardown ---
    # IMPORTANT: user_profiles has no FK to auth.users, and push_subscriptions /
    # user_team_follows reference user_profiles (not auth.users). So deleting the
    # auth user does NOT cascade to any of them. Every child must be deleted
    # explicitly by user_id, or rows leak across tests and inflate the fan-out
    # (a leaked follow+subscription makes the next test see >1 push).
    def _safe(fn):
        try:
            fn()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass

    _safe(lambda: admin.table("push_send_log").delete().eq("user_id", user_id).execute())
    _safe(lambda: admin.table("user_team_follows").delete().eq("user_id", user_id).execute())
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
    """Install a real-DAO Notifier whose only fake is the push network send.

    VAPID is force-configured so `_send_push_fanout` doesn't short-circuit.
    Returns the recorder so tests can assert what was pushed.
    """
    monkeypatch.setattr("notifications.dispatcher.push_is_configured", lambda: True)
    sender = _RecordingSender()
    notifier = Notifier(connection=SupabaseConnection(), push_send_fn=sender)
    set_notifier(notifier)
    yield sender
    set_notifier(None)


@pytest.fixture(autouse=True)
def _override_admin_auth():
    """Authenticate every request as an admin so the write endpoints accept it."""
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


# ---------------------------------------------------------------------------
# The headline path: skill scores a tournament match → follower gets a push
# ---------------------------------------------------------------------------


class TestTournamentScorePushesFollower:
    def _score_url(self, world) -> str:
        return f"/api/admin/tournaments/{world['tournament']['id']}/matches/{world['match']['id']}"

    def test_scoring_match_pushes_to_follower_and_logs(self, world, instrumented_notifier):
        with TestClient(app) as client:
            resp = client.put(
                self._score_url(world),
                json={"home_score": 0, "away_score": 1, "match_status": "completed"},
            )
        assert resp.status_code == 200, resp.text

        # The follower's one device got exactly one push.
        assert len(instrumented_notifier.calls) == 1
        sub, payload = instrumented_notifier.calls[0]
        assert sub["endpoint"] == world["subscription"]["endpoint"]
        # Payload carries the final score + both team names.
        text = f"{payload.get('title', '')}\n{payload.get('body', '')}"
        assert world["home_team"]["name"] in text
        assert world["away_team"]["name"] in text
        assert "0 - 1" in text

        # And it was logged as a fulltime send.
        rows = _push_log_rows(world["admin"], world["match"]["id"], world["user_id"])
        assert len(rows) == 1
        assert rows[0]["event_type"] == "fulltime"
        assert rows[0]["status"] == "sent"

    def test_resubmitting_same_score_does_not_re_notify(self, world, instrumented_notifier):
        """Idempotency: the skill's upsert loop re-PUTs identical scores; the
        second write must NOT produce another push or log row."""
        url = self._score_url(world)
        body = {"home_score": 2, "away_score": 2, "match_status": "completed"}

        with TestClient(app) as client:
            first = client.put(url, json=body)
        assert first.status_code == 200, first.text
        assert len(instrumented_notifier.calls) == 1

        with TestClient(app) as client:
            second = client.put(url, json=body)
        assert second.status_code == 200, second.text
        # No additional push, no additional log row.
        assert len(instrumented_notifier.calls) == 1
        rows = _push_log_rows(world["admin"], world["match"]["id"], world["user_id"])
        assert len(rows) == 1

    def test_metadata_only_update_does_not_notify(self, world, instrumented_notifier):
        """Changing round/group on an unscored match must stay silent."""
        with TestClient(app) as client:
            resp = client.put(
                self._score_url(world),
                json={"tournament_round": "final", "tournament_group": "Championship"},
            )
        assert resp.status_code == 200, resp.text
        assert instrumented_notifier.calls == []
        assert _push_log_rows(world["admin"], world["match"]["id"], world["user_id"]) == []

    def test_correcting_a_score_re_notifies(self, world, instrumented_notifier):
        """An admin fixing a wrong score is a real change → notify again."""
        url = self._score_url(world)

        with TestClient(app) as client:
            client.put(url, json={"home_score": 1, "away_score": 0, "match_status": "completed"})
        assert len(instrumented_notifier.calls) == 1

        with TestClient(app) as client:
            client.put(url, json={"home_score": 3, "away_score": 0, "match_status": "completed"})
        assert len(instrumented_notifier.calls) == 2
        rows = _push_log_rows(world["admin"], world["match"]["id"], world["user_id"])
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# The scraper path: league PATCH score → follower gets a push
# ---------------------------------------------------------------------------


class TestLeaguePatchPushesFollower:
    def test_patch_score_pushes_to_follower(self, world, instrumented_notifier):
        """match-scraper posts league results via PATCH /api/matches/{id} — the
        same follower-notify must fire there too."""
        with TestClient(app) as client:
            resp = client.patch(
                f"/api/matches/{world['match']['id']}",
                json={"home_score": 4, "away_score": 1, "match_status": "completed"},
            )
        assert resp.status_code == 200, resp.text

        assert len(instrumented_notifier.calls) == 1
        rows = _push_log_rows(world["admin"], world["match"]["id"], world["user_id"])
        assert len(rows) == 1
        assert rows[0]["event_type"] == "fulltime"


# ---------------------------------------------------------------------------
# Negative: a user following NEITHER team gets nothing
# ---------------------------------------------------------------------------


class TestNonFollowerGetsNothing:
    def test_unrelated_follower_not_notified(self, world, instrumented_notifier):
        """Seed a second user+device who follows neither team; scoring the match
        must not push to them. The original follower still does."""
        admin = world["admin"]
        other_email = f"sb77-nonfollow-{uuid.uuid4().hex[:8]}@missingtable.local"
        other = admin.auth.admin.create_user(
            {"email": other_email, "password": _TEST_PASSWORD, "email_confirm": True}
        )
        other_id = other.user.id
        admin.table("user_profiles").upsert(
            {"id": other_id, "email": other_email, "role": "team-fan"}
        ).execute()
        admin.table("push_subscriptions").insert(
            {
                "user_id": other_id,
                "endpoint": f"https://push.example/{uuid.uuid4().hex}",
                "p256dh_key": "k",  # pragma: allowlist secret
                "auth_key": "a",  # pragma: allowlist secret
            }
        ).execute()
        try:
            with TestClient(app) as client:
                resp = client.patch(
                    f"/api/matches/{world['match']['id']}",
                    json={"home_score": 1, "away_score": 1, "match_status": "completed"},
                )
            assert resp.status_code == 200, resp.text

            # Exactly one push — to the real follower, not the unrelated user.
            assert len(instrumented_notifier.calls) == 1
            pushed_endpoints = {c[0]["endpoint"] for c in instrumented_notifier.calls}
            assert world["subscription"]["endpoint"] in pushed_endpoints
            # No log row for the unrelated user.
            assert _push_log_rows(admin, world["match"]["id"], other_id) == []
        finally:
            # Explicit cleanup — no cascade from auth.users to these.
            for _table in ("push_send_log", "user_team_follows", "push_subscriptions"):
                try:
                    admin.table(_table).delete().eq("user_id", other_id).execute()
                except Exception:
                    pass
            try:
                admin.table("user_profiles").delete().eq("id", other_id).execute()
            except Exception:
                pass
            try:
                admin.auth.admin.delete_user(other_id)
            except Exception:
                pass

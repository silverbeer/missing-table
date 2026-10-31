"""FCM (native Android) delivery integration test (SB-1463).

Same approach as test_push_delivery_on_score.py: the real local Supabase for
the whole chain — the auth user + profile, clubs/teams/match, the follow row,
the fcm_devices row written through the real API endpoint, the real fan-out
query, preference gate, push_send_log write and expired-installation prune.

The ONLY thing faked is the FCM network call, injected as `fcm_send_fn` on the
Notifier. Web Push and APNs are switched off so only the FCM path runs.

Requires local Supabase running with the SB-1463 migration applied. Skips
cleanly if it isn't reachable.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dao.match_dao import SupabaseConnection
from notifications.dispatcher import Notifier
from notifications.web_push_sender import SendResult

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]


# Throwaway password for ephemeral test auth users (deleted in teardown).
_TEST_PASSWORD = "test-password-123"  # pragma: allowlist secret

# A Firebase Installation ID shape: 22 chars of base64url.
_FID_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"  # pragma: allowlist secret


def _fid() -> str:
    raw = uuid.uuid4().bytes + uuid.uuid4().bytes
    return "".join(_FID_ALPHABET[b % 64] for b in raw[:22])


def _admin_client():
    """Supabase client with the service-role key (bypasses RLS, auth.admin)."""
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:55321")
    # Hard safety rail: this test seeds + deletes rows and creates/deletes auth
    # users. It must NEVER run against a non-local Supabase.
    if not ("127.0.0.1" in url or "localhost" in url):
        pytest.skip(f"Refusing to run destructive test against non-local Supabase: {url}")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY not set — cannot run FCM delivery integration test")
    return create_client(url, key)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


class _RecordingSender:
    """Stand-in for fcm_sender.send_fcm — records every call, never hits FCM."""

    def __init__(self, result: SendResult):
        self.calls: list[tuple[dict, dict]] = []
        self.result = result

    def __call__(self, device: dict, payload: dict) -> SendResult:
        self.calls.append((device, payload))
        return self.result


@pytest.fixture
def world():
    """A follower of the home team of a completed match. Torn down after."""
    admin = _admin_client()
    try:
        admin.table("clubs").select("id").limit(1).execute()
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("Local Supabase not reachable")
    try:
        admin.table("fcm_devices").select("id").limit(1).execute()
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("fcm_devices missing — apply the SB-1463 migration to local Supabase")

    email = f"sb1463-fcm-{uuid.uuid4().hex[:8]}@missingtable.local"
    created = admin.auth.admin.create_user({"email": email, "password": _TEST_PASSWORD, "email_confirm": True})
    user_id = created.user.id
    admin.table("user_profiles").upsert({"id": user_id, "email": email, "role": "team-fan"}).execute()

    def _ref(table: str) -> int:
        return admin.table(table).select("id").limit(1).execute().data[0]["id"]

    home_club = admin.table("clubs").insert({"name": _unique("FcmHome"), "city": "Houston"}).execute().data[0]
    away_club = admin.table("clubs").insert({"name": _unique("FcmAway"), "city": "Bergen"}).execute().data[0]
    home_team = (
        admin.table("teams")
        .insert({"name": _unique("FcmHomeTeam"), "city": "Houston", "club_id": home_club["id"]})
        .execute()
        .data[0]
    )
    away_team = (
        admin.table("teams")
        .insert({"name": _unique("FcmAwayTeam"), "city": "Bergen", "club_id": away_club["id"]})
        .execute()
        .data[0]
    )
    match = (
        admin.table("matches")
        .insert(
            {
                "home_team_id": home_team["id"],
                "away_team_id": away_team["id"],
                "age_group_id": _ref("age_groups"),
                "season_id": _ref("seasons"),
                "match_type_id": _ref("match_types"),
                "match_date": datetime.now(UTC).date().isoformat(),
                "match_status": "completed",
                "home_score": 2,
                "away_score": 1,
            }
        )
        .execute()
        .data[0]
    )
    admin.table("user_team_follows").insert({"user_id": user_id, "team_id": home_team["id"]}).execute()

    yield {"admin": admin, "user_id": user_id, "match": match, "home_team": home_team}

    # No cascade from auth.users to user_profiles' children — delete explicitly.
    def _safe(fn):
        try:
            fn()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass

    _safe(lambda: admin.table("push_send_log").delete().eq("user_id", user_id).execute())
    _safe(lambda: admin.table("fcm_devices").delete().eq("user_id", user_id).execute())
    _safe(lambda: admin.table("user_team_follows").delete().eq("user_id", user_id).execute())
    _safe(lambda: admin.table("matches").delete().eq("id", match["id"]).execute())
    _safe(lambda: admin.table("teams").delete().eq("id", home_team["id"]).execute())
    _safe(lambda: admin.table("teams").delete().eq("id", away_team["id"]).execute())
    _safe(lambda: admin.table("clubs").delete().eq("id", home_club["id"]).execute())
    _safe(lambda: admin.table("clubs").delete().eq("id", away_club["id"]).execute())
    _safe(lambda: admin.table("user_profiles").delete().eq("id", user_id).execute())
    _safe(lambda: admin.auth.admin.delete_user(user_id))


@pytest.fixture
def api_as(world, monkeypatch):
    """The push router, authenticated as the world's follower, on a fresh
    real connection (the module singleton may predate env changes)."""
    from api import push
    from auth import get_current_user_required

    monkeypatch.setattr(push, "_connection", SupabaseConnection())
    app = FastAPI()
    app.include_router(push.router)
    app.dependency_overrides[get_current_user_required] = lambda: {"id": world["user_id"], "role": "team-fan"}
    return TestClient(app)


@pytest.fixture
def fcm_only(monkeypatch):
    monkeypatch.setattr("notifications.dispatcher.push_is_configured", lambda: False)
    monkeypatch.setattr("notifications.dispatcher.apns_is_configured", lambda: False)
    monkeypatch.setattr("notifications.dispatcher.fcm_is_configured", lambda: True)


def _devices(admin, user_id: str) -> list[dict]:
    return admin.table("fcm_devices").select("*").eq("user_id", user_id).execute().data or []


def _fcm_log_rows(admin, match_id: int, user_id: str) -> list[dict]:
    return (
        admin.table("push_send_log")
        .select("*")
        .eq("match_id", match_id)
        .eq("user_id", user_id)
        .eq("platform", "fcm")
        .order("id")
        .execute()
        .data
        or []
    )


class TestFcmRegisterFanOutPrune:
    def test_register_upserts_on_fid_then_fans_out_then_prunes(self, world, api_as, fcm_only):
        admin, user_id, match_id = world["admin"], world["user_id"], world["match"]["id"]
        fid = _fid()

        # --- register: second POST with the same fid updates in place --------
        first = api_as.post(
            "/api/users/me/fcm-devices",
            json={"fid": fid, "app_version": "0.2.18", "device_label": "Pixel 9"},
        )
        assert first.status_code == 201, first.text
        second = api_as.post("/api/users/me/fcm-devices", json={"fid": f" {fid} ", "app_version": "0.2.19"})
        assert second.status_code == 201, second.text
        assert second.json()["id"] == first.json()["id"]

        [row] = _devices(admin, user_id)
        assert row["fid"] == fid
        assert row["app_version"] == "0.2.19"
        assert row["device_label"] == "Pixel 9"  # omitted on re-register → kept

        # --- fan-out: the follower's installation gets the fulltime push ----
        sender = _RecordingSender(SendResult(status="sent", http_status=200))
        Notifier(connection=SupabaseConnection(), fcm_send_fn=sender).notify("fulltime", match_id)

        assert len(sender.calls) == 1
        device, payload = sender.calls[0]
        assert device["fid"] == fid
        assert payload["data"]["matchId"] == match_id
        [log] = _fcm_log_rows(admin, match_id, user_id)
        assert log["status"] == "sent"
        assert log["fcm_device_id"] == row["id"]
        assert log["subscription_id"] is None

        # --- expired: FCM says the installation is gone → row pruned --------
        sender.result = SendResult(status="expired", http_status=404, error="UNREGISTERED")
        Notifier(connection=SupabaseConnection(), fcm_send_fn=sender).notify("fulltime", match_id)

        assert len(sender.calls) == 2
        assert _devices(admin, user_id) == []
        logs = _fcm_log_rows(admin, match_id, user_id)
        assert [r["status"] for r in logs] == ["sent", "expired"]
        # ON DELETE SET NULL keeps the log rows, minus the device link.
        assert all(r["fcm_device_id"] is None for r in logs)

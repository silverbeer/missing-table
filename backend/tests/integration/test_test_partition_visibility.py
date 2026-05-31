"""Prod test-partition visibility (SB-85, Phase 1).

Verifies the is_test partition on the two public list endpoints:
  GET /api/tournaments
  GET /api/leagues

A test-flagged league / tournament must be hidden from anonymous and real
(non-test, non-admin) viewers, and visible to test users + admins.

The viewer is controlled by overriding get_current_user_optional (the same
dependency the endpoints depend on) — no real tokens needed. The DB rows are
real (seeded with is_test) so the DAO's WHERE filter is exercised for real.

Requires local Supabase. Skips cleanly if unreachable.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app import app
from auth import get_current_user_optional
from dao.base_dao import clear_cache

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]


def _admin_client():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
    if not ("127.0.0.1" in url or "localhost" in url):
        pytest.skip(f"Refusing to run destructive test against non-local Supabase: {url}")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY not set — cannot run test-partition test")
    return create_client(url, key)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def world():
    """Seed a test-flagged league + tournament and a real (control) pair."""
    admin = _admin_client()
    try:
        admin.table("leagues").select("id").limit(1).execute()
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("Local Supabase not reachable")

    test_league = admin.table("leagues").insert(
        {"name": _unique("ZZ Test League"), "is_active": True, "is_test": True}
    ).execute().data[0]
    real_league = admin.table("leagues").insert(
        {"name": _unique("ZZ Real League"), "is_active": True, "is_test": False}
    ).execute().data[0]

    today = datetime.now(UTC).date().isoformat()
    test_tourney = admin.table("tournaments").insert(
        {"name": _unique("ZZ Test Cup"), "start_date": today, "is_active": True, "is_test": True}
    ).execute().data[0]
    real_tourney = admin.table("tournaments").insert(
        {"name": _unique("ZZ Real Cup"), "start_date": today, "is_active": True, "is_test": False}
    ).execute().data[0]

    # Raw inserts above bypass the DAO's invalidates_cache, so stale cached
    # lists could hide the just-seeded rows. Bust both.
    clear_cache("mt:dao:leagues:*")
    clear_cache("mt:dao:tournaments:*")

    yield {
        "test_league": test_league,
        "real_league": real_league,
        "test_tourney": test_tourney,
        "real_tourney": real_tourney,
    }

    def _safe(fn):
        try:
            fn()
        except Exception:  # pragma: no cover
            pass

    _safe(lambda: admin.table("tournaments").delete().eq("id", test_tourney["id"]).execute())
    _safe(lambda: admin.table("tournaments").delete().eq("id", real_tourney["id"]).execute())
    _safe(lambda: admin.table("leagues").delete().eq("id", test_league["id"]).execute())
    _safe(lambda: admin.table("leagues").delete().eq("id", real_league["id"]).execute())


# Viewer fixtures injected via dependency override.
_ANON = None
_REAL_FAN = {"user_id": "real", "role": "team-fan", "is_test": False}
_TEST_USER = {"user_id": "tester", "role": "team-fan", "is_test": True}
_ADMIN = {"user_id": "admin", "role": "admin", "is_test": False}


def _as(viewer):
    """Context: run the TestClient with get_current_user_optional → viewer."""
    app.dependency_overrides[get_current_user_optional] = lambda: viewer
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _ids(rows):
    return {r["id"] for r in rows}


class TestTournamentPartition:
    def test_anonymous_and_real_users_dont_see_test_tournament(self, world):
        for viewer in (_ANON, _REAL_FAN):
            with _as(viewer) as client:
                ids = _ids(client.get("/api/tournaments").json())
            assert world["real_tourney"]["id"] in ids
            assert world["test_tourney"]["id"] not in ids, f"viewer={viewer}"

    def test_test_user_and_admin_see_test_tournament(self, world):
        for viewer in (_TEST_USER, _ADMIN):
            with _as(viewer) as client:
                ids = _ids(client.get("/api/tournaments").json())
            assert world["real_tourney"]["id"] in ids
            assert world["test_tourney"]["id"] in ids, f"viewer={viewer}"


class TestLeaguePartition:
    def test_anonymous_and_real_users_dont_see_test_league(self, world):
        for viewer in (_ANON, _REAL_FAN):
            with _as(viewer) as client:
                ids = _ids(client.get("/api/leagues").json())
            assert world["real_league"]["id"] in ids
            assert world["test_league"]["id"] not in ids, f"viewer={viewer}"

    def test_test_user_and_admin_see_test_league(self, world):
        for viewer in (_TEST_USER, _ADMIN):
            with _as(viewer) as client:
                ids = _ids(client.get("/api/leagues").json())
            assert world["real_league"]["id"] in ids
            assert world["test_league"]["id"] in ids, f"viewer={viewer}"

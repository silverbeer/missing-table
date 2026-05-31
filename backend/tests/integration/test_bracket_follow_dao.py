"""BracketFollowDAO integration tests against real local Supabase.

Covers the paths the delivery test doesn't: follow idempotency, unfollow,
and that list_subscriptions_for_bracket returns ONLY subscriptions of users
following that exact (tournament, group, age_group) tuple.

Requires local Supabase running. Skips cleanly if it isn't reachable.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest

from dao.bracket_follow_dao import BracketFollowDAO
from dao.match_dao import SupabaseConnection

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]

_TEST_PASSWORD = "test-password-123"  # pragma: allowlist secret


def _admin_client():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
    if not ("127.0.0.1" in url or "localhost" in url):
        pytest.skip(f"Refusing to run destructive test against non-local Supabase: {url}")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY not set — cannot run bracket-follow DAO test")
    return create_client(url, key)


def _mk_user(admin) -> str:
    email = f"bracket-dao-{uuid.uuid4().hex[:8]}@missingtable.local"
    created = admin.auth.admin.create_user(
        {"email": email, "password": _TEST_PASSWORD, "email_confirm": True}
    )
    uid = created.user.id
    admin.table("user_profiles").upsert(
        {"id": uid, "email": email, "role": "team-fan"}
    ).execute()
    return uid


@pytest.fixture
def ctx():
    admin = _admin_client()
    try:
        admin.table("tournaments").select("id").limit(1).execute()
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("Local Supabase not reachable")

    age_group_id = admin.table("age_groups").select("id").limit(1).execute().data[0]["id"]
    tournament = admin.table("tournaments").insert(
        {
            "name": f"BracketDAO-{uuid.uuid4().hex[:8]}",
            "start_date": datetime.now(UTC).date().isoformat(),
            "is_active": True,
        }
    ).execute().data[0]

    dao = BracketFollowDAO(SupabaseConnection())
    users: list[str] = []

    def new_user() -> str:
        uid = _mk_user(admin)
        users.append(uid)
        return uid

    yield {
        "admin": admin,
        "dao": dao,
        "tournament_id": tournament["id"],
        "age_group_id": age_group_id,
        "new_user": new_user,
    }

    def _safe(fn):
        try:
            fn()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass

    for uid in users:
        _safe(lambda u=uid: admin.table("user_bracket_follows").delete().eq("user_id", u).execute())
        _safe(lambda u=uid: admin.table("push_subscriptions").delete().eq("user_id", u).execute())
        _safe(lambda u=uid: admin.table("user_profiles").delete().eq("id", u).execute())
        _safe(lambda u=uid: admin.auth.admin.delete_user(u))
    _safe(lambda: admin.table("tournaments").delete().eq("id", tournament["id"]).execute())


def test_follow_is_idempotent(ctx):
    dao, uid = ctx["dao"], ctx["new_user"]()
    tid, ag = ctx["tournament_id"], ctx["age_group_id"]

    assert dao.follow(uid, tid, "Bracket A", ag) is True
    assert dao.follow(uid, tid, "Bracket A", ag) is True  # re-follow, no dup

    rows = (
        ctx["admin"].table("user_bracket_follows")
        .select("*").eq("user_id", uid).execute().data
    )
    assert len(rows) == 1


def test_unfollow_removes_and_is_idempotent(ctx):
    dao, uid = ctx["dao"], ctx["new_user"]()
    tid, ag = ctx["tournament_id"], ctx["age_group_id"]

    dao.follow(uid, tid, "Bracket A", ag)
    assert dao.unfollow(uid, tid, "Bracket A", ag) is True
    assert dao.unfollow(uid, tid, "Bracket A", ag) is True  # already gone

    rows = (
        ctx["admin"].table("user_bracket_follows")
        .select("*").eq("user_id", uid).execute().data
    )
    assert rows == []


def test_list_subscriptions_only_matches_exact_bracket(ctx):
    """A follower of (T, 'Bracket A', AG) is returned; a follower of a
    different group or age group is not."""
    admin, dao = ctx["admin"], ctx["dao"]
    tid, ag = ctx["tournament_id"], ctx["age_group_id"]
    other_ag = (
        admin.table("age_groups").select("id").neq("id", ag).limit(1).execute().data
    )

    follower = ctx["new_user"]()
    sub = admin.table("push_subscriptions").insert(
        {
            "user_id": follower,
            "endpoint": f"https://push.example/{uuid.uuid4().hex}",
            "p256dh_key": "k",  # pragma: allowlist secret
            "auth_key": "a",  # pragma: allowlist secret
        }
    ).execute().data[0]
    dao.follow(follower, tid, "Bracket A", ag)

    # A user following a DIFFERENT bracket group — must be excluded.
    other_group_user = ctx["new_user"]()
    admin.table("push_subscriptions").insert(
        {
            "user_id": other_group_user,
            "endpoint": f"https://push.example/{uuid.uuid4().hex}",
            "p256dh_key": "k",  # pragma: allowlist secret
            "auth_key": "a",  # pragma: allowlist secret
        }
    ).execute()
    dao.follow(other_group_user, tid, "Bracket B", ag)

    subs = dao.list_subscriptions_for_bracket(tid, "Bracket A", ag)
    endpoints = {s["endpoint"] for s in subs}
    assert sub["endpoint"] in endpoints
    assert len(subs) == 1

    # Different age group on the same group also misses (if another AG exists).
    if other_ag:
        assert dao.list_subscriptions_for_bracket(tid, "Bracket A", other_ag[0]["id"]) == []

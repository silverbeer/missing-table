"""GET /api/admin/ai/gaps (SB-1308): what MT AI could not answer.

FastAPI TestClient with `app.dependency_overrides` for the caller, and the real
local Supabase for `ai_tool_calls`. Seeded rows use a tool name unique to the
test, and every request filters on it, so rows already in the database never
leak into an assertion.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import app
from auth import get_current_user_required
from dao.ai_conversation_dao import AIConversationDAO
from dao.match_dao import SupabaseConnection

pytestmark = [pytest.mark.integration, pytest.mark.api, pytest.mark.requires_supabase]


def _fake_user(role: str) -> dict:
    return {"user_id": "u-1", "username": f"{role}_user", "role": role, "email": f"{role}@example.com"}


@contextmanager
def as_user(user: dict):
    app.dependency_overrides[get_current_user_required] = lambda: user
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user_required, None)


@pytest.fixture
def dao():
    return AIConversationDAO(SupabaseConnection())


@pytest.fixture
def tool_name():
    return f"sb1308_it_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def conversation(dao):
    profile = dao.client.table("user_profiles").select("id").limit(1).execute().data
    if not profile:
        pytest.skip("no user_profiles row to own a conversation")
    row = dao.create_conversation(profile[0]["id"], "sb-1308-test")
    yield row
    dao.client.table("ai_conversations").delete().eq("id", row["id"]).execute()


def seed(dao, conversation_id: str, tool: str, calls: list[tuple[dict, str | None, str | None, int]]):
    """calls: (args, result status, error_kind, days ago)."""
    now = datetime.now(UTC)
    rows = [
        {
            "conversation_id": conversation_id,
            "turn": 1,
            "seq": seq,
            "tool_name": tool,
            "args": args,
            "result": {"status": status} if status else {"matches": []},
            "error_kind": error_kind,
            "created_at": (now - timedelta(days=ago)).isoformat(),
        }
        for seq, (args, status, error_kind, ago) in enumerate(calls, start=1)
    ]
    dao.client.table("ai_tool_calls").insert(rows).execute()


class TestAIGaps:
    def test_nothing_unanswered_is_200_with_an_empty_list(self, tool_name):
        """The default state: no AI traffic for this tool. Never a 404."""
        with as_user(_fake_user("admin")) as c:
            r = c.get("/api/admin/ai/gaps", params={"tool": tool_name})

        assert r.status_code == 200
        body = r.json()
        assert body["gaps"] == []
        assert (body["count"], body["gap_calls"], body["total_calls"]) == (0, 0, 0)
        assert body["days"] == 30
        assert "error" not in body

    def test_groups_not_found_and_ambiguous_by_query(self, dao, conversation, tool_name):
        seed(
            dao,
            conversation["id"],
            tool_name,
            [
                ({"query": "Bayside FC", "age_group": "U14"}, "not_found", None, 2),
                ({"query": "bayside  fc"}, "not_found", None, 1),
                ({"query": "IFA"}, "ambiguous", None, 3),
                ({"query": "IFA U15"}, "resolved", None, 1),  # answered
                ({"query": "NEFC"}, "not_found", "unavailable", 1),  # outage, not a gap
                ({"query": "Old"}, "not_found", None, 45),  # outside the window
            ],
        )

        with as_user(_fake_user("admin")) as c:
            r = c.get("/api/admin/ai/gaps", params={"tool": tool_name, "days": 30})

        assert r.status_code == 200
        body = r.json()
        assert [(g["query"], g["count"], g["not_found"], g["ambiguous"]) for g in body["gaps"]] == [
            ("bayside fc", 2, 2, 0),
            ("IFA", 1, 0, 1),
        ]
        assert body["gaps"][0]["age_groups"] == ["U14"]
        assert (body["count"], body["gap_calls"], body["total_calls"]) == (2, 3, 5)

    @pytest.mark.parametrize("role", ["team-manager", "club_manager", "team-fan", "team-player", "user"])
    def test_non_admins_are_refused(self, role, tool_name):
        with as_user(_fake_user(role)) as c:
            r = c.get("/api/admin/ai/gaps", params={"tool": tool_name})
        assert r.status_code == 403

    def test_days_out_of_range_is_422(self):
        with as_user(_fake_user("admin")) as c:
            assert c.get("/api/admin/ai/gaps", params={"days": 0}).status_code == 422
            assert c.get("/api/admin/ai/gaps", params={"days": 366}).status_code == 422

"""suggest_motw_candidates over mt-mcp, and its admin API twin (SB-1551)."""

import dataclasses
import functools
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from motw_fakes import NOW, FakeMotw, deps
from mt_mcp_harness import served

import mt_mcp.server as server_module
import mt_tools.motw_candidates as candidates_module
from mt_mcp.scopes import SB_AGENTS_CLIENT

pytestmark = [pytest.mark.unit, pytest.mark.backend]

PICK = {"match": {"id": 503, "home_team_id": 5, "away_team_id": 6}, "blurb": "Picked", "reasons": None}


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    """The fake world's 'today' is Sat 2026-11-07; the tool must not read the wall clock here."""
    real = candidates_module.suggest_from_deps
    monkeypatch.setattr(server_module, "suggest_from_deps", functools.partial(real, now=NOW))
    monkeypatch.setattr(candidates_module, "suggest_from_deps", functools.partial(real, now=NOW))


def motw_deps(picks: dict | None = None):
    return dataclasses.replace(deps(), motw=FakeMotw(picks))


class TestOverMcp:
    async def test_public_agents_can_list_and_call_it(self):
        async with served(motw_deps()) as s, s.session("fan", client=SB_AGENTS_CLIENT) as session:
            names = {t.name for t in (await session.list_tools()).tools}
            result = await session.call_tool("suggest_motw_candidates", {"week": "2026-11-02"})

        assert "suggest_motw_candidates" in names
        assert not result.is_error
        data = result.structured_content
        assert data["week_start"] == "2026-11-02"
        assert data["candidates"][0]["match_id"] == 501
        assert data["coverage"]["eligible"] == 3
        assert all(f["id"].startswith("501:") for f in data["candidates"][0]["facts"])

    async def test_schema(self):
        async with served(motw_deps()) as s, s.session("fan") as session:
            tool = next(t for t in (await session.list_tools()).tools if t.name == "suggest_motw_candidates")
        assert set(tool.input_schema["properties"]) == {"week", "limit"}
        assert set(tool.output_schema["properties"]) >= {"candidates", "current_pick", "coverage", "reason", "error"}

    async def test_existing_pick_is_reported(self):
        async with served(motw_deps({"2026-11-02": PICK})) as s, s.session("fan") as session:
            data = (await session.call_tool("suggest_motw_candidates", {})).structured_content
        assert data["current_pick"]["match_id"] == 503

    async def test_empty_week_is_an_answer(self):
        async with served(motw_deps()) as s, s.session("fan") as session:
            data = (await session.call_tool("suggest_motw_candidates", {"week": "2027-01-04"})).structured_content
        assert data["candidates"] == []
        assert data["reason"]
        assert data["error"] is None

    async def test_without_a_motw_source_it_is_unavailable(self):
        async with served(deps()) as s, s.session("fan") as session:
            data = (await session.call_tool("suggest_motw_candidates", {})).structured_content
        assert data["error"]["kind"] == "unavailable"
        assert data["candidates"] is None


@pytest.fixture
def api():
    import app as app_module
    from auth import require_admin

    app_module.app.dependency_overrides[require_admin] = lambda: {"user_id": "a", "role": "admin"}
    with patch.object(app_module, "_my_team_deps", lambda: motw_deps()):
        yield TestClient(app_module.app)
    app_module.app.dependency_overrides.clear()


class TestAdminApi:
    def test_candidates(self, api):
        r = api.get("/api/admin/motw/candidates", params={"week": "2026-11-02", "limit": 2})
        assert r.status_code == 200
        body = r.json()
        assert [c["match_id"] for c in body["candidates"]][:1] == [501]
        assert len(body["candidates"]) == 2

    def test_empty_week_is_200(self, api):
        r = api.get("/api/admin/motw/candidates", params={"week": "2027-01-04"})
        assert r.status_code == 200
        assert r.json()["candidates"] == []

    def test_bad_week_is_400(self, api):
        assert api.get("/api/admin/motw/candidates", params={"week": "soon"}).status_code == 400

    def test_limit_is_bounded(self, api):
        assert api.get("/api/admin/motw/candidates", params={"limit": 50}).status_code == 422

    def test_failure_is_503_without_details(self, api):
        import app as app_module

        with patch.object(app_module, "_my_team_deps", lambda: deps(fail=True)):
            r = api.get("/api/admin/motw/candidates", params={"week": "2026-11-02"})
        assert r.status_code == 503
        assert "PostgREST" not in r.text

    def test_admin_only(self):
        import app as app_module

        r = TestClient(app_module.app).get("/api/admin/motw/candidates")
        assert r.status_code in (401, 403)

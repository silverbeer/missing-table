"""get_leaderboards over mt-mcp, and GET /api/leaderboards (SB-1781)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from leaderboards_fakes import deps, full_season
from mt_mcp_harness import served

from mt_mcp.scopes import MT_AI_CLIENT

pytestmark = [pytest.mark.unit, pytest.mark.backend]


class TestOverMcp:
    async def test_a_fan_can_list_and_call_it(self):
        async with served(deps(full_season())) as s, s.session("fan") as session:
            names = {t.name for t in (await session.list_tools()).tools}
            result = await session.call_tool("get_leaderboards", {"age_group": "U15"})

        assert "get_leaderboards" in names
        assert not result.is_error
        data = result.structured_content
        assert data["league"] == "Homegrown"
        assert data["coverage"]["teams"] == 8
        assert "not a ranking" in data["coverage"]["note"]
        pts = next(b for b in data["boards"] if b["key"] == "pts")
        assert pts["rows"][0]["team"]["id"] == 1
        assert data["unranked"] == []
        assert pts["unranked_count"] == 0
        assert "too_few_games" not in pts

    async def test_early_season_unranked_is_listed_once_and_capped(self):
        async with served(deps()) as s, s.session("fan") as session:
            data = (await session.call_tool("get_leaderboards", {"age_group": "U15", "limit": 3})).structured_content
        assert data["unranked_count"] == 8
        assert len(data["unranked"]) == 3
        assert all(b["unranked_count"] >= 0 and b["rows"] == [] for b in data["boards"])

    async def test_a_child_league_is_invalid_args(self):
        async with served(deps()) as s, s.session("fan") as session:
            data = (
                await session.call_tool("get_leaderboards", {"age_group": "U15", "league": "Flex"})
            ).structured_content
        assert data["error"]["kind"] == "invalid_args"

    async def test_mt_ai_sees_it(self):
        async with served(deps()) as s, s.session("fan", MT_AI_CLIENT) as session:
            names = {t.name for t in (await session.list_tools()).tools}
        assert "get_leaderboards" in names

    async def test_schema(self):
        async with served(deps()) as s, s.session("fan") as session:
            tool = next(t for t in (await session.list_tools()).tools if t.name == "get_leaderboards")
        assert set(tool.input_schema["properties"]) == {"age_group", "league", "season", "limit"}
        assert tool.input_schema["required"] == ["age_group"]
        assert set(tool.output_schema["properties"]) >= {
            "boards",
            "unranked",
            "unranked_count",
            "coverage",
            "reason",
            "error",
        }

    async def test_empty_age_group_is_an_answer(self):
        async with served(deps([])) as s, s.session("fan") as session:
            data = (await session.call_tool("get_leaderboards", {"age_group": "U15"})).structured_content
        assert data["error"] is None
        assert data["reason"]
        assert all(b["rows"] == [] for b in data["boards"])

    async def test_unknown_age_group_is_invalid_args(self):
        async with served(deps()) as s, s.session("fan") as session:
            data = (await session.call_tool("get_leaderboards", {"age_group": "U99"})).structured_content
        assert data["error"]["kind"] == "invalid_args"


@pytest.fixture
def api():
    import app as app_module
    from auth import get_current_user_required

    app_module.app.dependency_overrides[get_current_user_required] = lambda: {"user_id": "f", "role": "team-fan"}
    with patch.object(app_module, "_my_team_deps", lambda: deps(full_season())):
        yield TestClient(app_module.app)
    app_module.app.dependency_overrides.clear()


class TestApi:
    def test_boards(self, api):
        r = api.get("/api/leaderboards", params={"age_group": "U15", "limit": 2})
        assert r.status_code == 200
        body = r.json()
        assert body["coverage"]["teams"] == 8
        pts = next(b for b in body["boards"] if b["key"] == "pts")
        assert all(row["rank"] <= 2 for row in pts["rows"])
        assert body["unranked_count"] == 0

    def test_early_season_unranked_is_capped_at_limit(self, api):
        import app as app_module

        with patch.object(app_module, "_my_team_deps", lambda: deps()):
            body = api.get("/api/leaderboards", params={"age_group": "U15", "limit": 2}).json()
        assert body["unranked_count"] == 8
        assert len(body["unranked"]) == 2

    def test_a_child_league_is_400(self, api):
        r = api.get("/api/leaderboards", params={"age_group": "U15", "league": "Flex"})
        assert r.status_code == 400
        assert "Homegrown" in r.json()["detail"]

    def test_empty_age_group_is_200(self, api):
        import app as app_module

        with patch.object(app_module, "_my_team_deps", lambda: deps([])):
            r = api.get("/api/leaderboards", params={"age_group": "U15"})
        assert r.status_code == 200
        assert r.json()["reason"]

    def test_unknown_age_group_is_400(self, api):
        assert api.get("/api/leaderboards", params={"age_group": "U99"}).status_code == 400

    def test_age_group_is_required(self, api):
        assert api.get("/api/leaderboards").status_code == 422

    def test_limit_is_bounded(self, api):
        assert api.get("/api/leaderboards", params={"age_group": "U15", "limit": 51}).status_code == 422

    def test_failure_is_503_without_details(self, api):
        import app as app_module

        with patch.object(app_module, "_my_team_deps", lambda: deps(fail=True)):
            r = api.get("/api/leaderboards", params={"age_group": "U15"})
        assert r.status_code == 503
        assert "PostgREST" not in r.text

    def test_requires_a_logged_in_user(self):
        """Invite-only: these name teams, so no anonymous read."""
        import app as app_module

        r = TestClient(app_module.app).get("/api/leaderboards", params={"age_group": "U15"})
        assert r.status_code in (401, 403)

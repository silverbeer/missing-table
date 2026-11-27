"""get_power_rating / get_power_rating_team over mt-mcp, and GET /api/rankings (SB-1808)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from mt_mcp_harness import served
from power_rating_fakes import FakePowerRating, conference_world, deps, national_world

from mt_mcp.scopes import MT_AI_CLIENT

pytestmark = [pytest.mark.unit, pytest.mark.backend]

TOOLS = {"get_power_rating", "get_power_rating_team"}


class TestOverMcp:
    async def test_a_fan_can_list_and_call_it(self):
        async with served(deps(national_world())) as s, s.session("fan") as session:
            names = {t.name for t in (await session.list_tools()).tools}
            result = await session.call_tool("get_power_rating", {"age_group": "U15"})

        assert names >= TOOLS
        assert not result.is_error
        data = result.structured_content
        assert data["view"] == "national"
        assert data["teams"][0]["team_id"] == 1
        assert data["teams"][0]["rank_change_7d"] == 2
        assert data["coverage"]["note"].startswith("MT Power Rating from 6 Homegrown U15 teams")
        assert data["unranked"][0]["needed"] == 6

    async def test_national_asked_on_a_conference_run(self):
        async with served(deps(conference_world())) as s, s.session("fan") as session:
            data = (
                await session.call_tool("get_power_rating", {"age_group": "U15", "view": "national"})
            ).structured_content
        assert data["view"] == "conference"
        assert data["publication"]["reason"]
        assert data["tiers"] == []

    async def test_the_team_tool(self):
        async with served(deps(national_world())) as s, s.session("fan") as session:
            data = (
                await session.call_tool("get_power_rating_team", {"team_id": 1, "age_group": "U15"})
            ).structured_content
        assert data["in_run"] is True
        assert data["rating"] == 1754

    async def test_no_run_is_an_answer(self):
        async with served(deps()) as s, s.session("fan") as session:
            data = (await session.call_tool("get_power_rating", {"age_group": "U15"})).structured_content
        assert data["error"] is None
        assert data["teams"] == []
        assert data["reason"]

    async def test_unknown_age_group_is_invalid_args(self):
        async with served(deps()) as s, s.session("fan") as session:
            data = (await session.call_tool("get_power_rating", {"age_group": "U99"})).structured_content
        assert data["error"]["kind"] == "invalid_args"

    async def test_mt_ai_sees_them(self):
        async with served(deps()) as s, s.session("fan", MT_AI_CLIENT) as session:
            names = {t.name for t in (await session.list_tools()).tools}
        assert names >= TOOLS

    async def test_no_token_lists_nothing(self):
        async with served(deps()) as s, s.http() as http:
            response = await http.post("/", json={})
        assert response.status_code == 401

    async def test_schema(self):
        async with served(deps()) as s, s.session("fan") as session:
            tools = {t.name: t for t in (await session.list_tools()).tools}
        listing = tools["get_power_rating"]
        assert set(listing.input_schema["properties"]) == {"age_group", "league", "season", "view", "conference"}
        assert listing.input_schema["required"] == ["age_group"]
        assert set(listing.output_schema["properties"]) >= {
            "run",
            "publication",
            "coverage",
            "tiers",
            "teams",
            "unranked",
            "reason",
            "error",
        }
        one = tools["get_power_rating_team"]
        assert set(one.input_schema["required"]) == {"team_id", "age_group"}
        assert "game" not in (listing.description + one.description).lower()


@pytest.fixture
def api():
    import app as app_module
    from auth import get_current_user_required

    app_module.app.dependency_overrides[get_current_user_required] = lambda: {"user_id": "f", "role": "team-fan"}
    with patch.object(app_module, "_my_team_deps", lambda: deps(national_world())):
        yield TestClient(app_module.app)
    app_module.app.dependency_overrides.clear()


def _with(store):
    import app as app_module

    return patch.object(app_module, "_my_team_deps", lambda: deps(store))


class TestApi:
    def test_rankings(self, api):
        r = api.get("/api/rankings", params={"age_group": "U15"})
        assert r.status_code == 200
        body = r.json()
        assert body["view"] == "national"
        assert body["run"]["id"] == 12
        assert [t["team_id"] for t in body["teams"]] == [1, 2, 8, 5, 6]
        assert body["teams"][0]["rating"] == 1754
        assert body["coverage"]["teams_in_pool"] == 6

    def test_view_and_conference_params(self, api):
        body = api.get(
            "/api/rankings", params={"age_group": "U15", "view": "conference", "conference": "Southeast"}
        ).json()
        assert body["view"] == "conference"
        assert body["conference"] == "Southeast"
        assert {t["conference"] for t in body["teams"]} == {"Southeast"}

    def test_no_run_is_200_with_a_reason(self, api):
        with _with(FakePowerRating()):
            r = api.get("/api/rankings", params={"age_group": "U15"})
        assert r.status_code == 200
        assert r.json()["teams"] == []
        assert r.json()["reason"]

    def test_unknown_age_group_or_league_is_400(self, api):
        assert api.get("/api/rankings", params={"age_group": "U99"}).status_code == 400
        assert api.get("/api/rankings", params={"age_group": "U15", "league": "Nope"}).status_code == 400

    def test_unknown_conference_is_400(self, api):
        r = api.get("/api/rankings", params={"age_group": "U15", "conference": "Atlantis"})
        assert r.status_code == 400
        assert "Northeast" in r.json()["detail"]

    def test_an_unknown_view_is_422(self, api):
        assert api.get("/api/rankings", params={"age_group": "U15", "view": "global"}).status_code == 422

    def test_age_group_is_required(self, api):
        assert api.get("/api/rankings").status_code == 422

    def test_failure_is_503_without_details(self, api):
        with _with(FakePowerRating(fail=True)):
            r = api.get("/api/rankings", params={"age_group": "U15"})
        assert r.status_code == 503
        assert "PostgREST" not in r.text

    def test_team(self, api):
        r = api.get("/api/rankings/teams/1", params={"age_group": "U15"})
        assert r.status_code == 200
        body = r.json()
        assert body["in_run"] is True
        assert body["rank"] == 1

    def test_team_not_in_run_is_200(self, api):
        r = api.get("/api/rankings/teams/3", params={"age_group": "U15"})
        assert r.status_code == 200
        assert r.json()["in_run"] is False
        assert r.json()["reason"]

    def test_unknown_team_is_400(self, api):
        assert api.get("/api/rankings/teams/9999", params={"age_group": "U15"}).status_code == 400

    def test_team_failure_is_503(self, api):
        with _with(FakePowerRating(fail=True)):
            r = api.get("/api/rankings/teams/1", params={"age_group": "U15"})
        assert r.status_code == 503
        assert "PostgREST" not in r.text

    @pytest.mark.parametrize("path", ["/api/rankings", "/api/rankings/teams/1"])
    def test_requires_a_logged_in_user(self, path):
        """Invite-only: these name minors' teams, so no anonymous read."""
        import app as app_module

        r = TestClient(app_module.app).get(path, params={"age_group": "U15"})
        assert r.status_code in (401, 403)

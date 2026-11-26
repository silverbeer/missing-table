"""get_team_dossier over mt-mcp, and GET /api/teams/{id}/dossier (SB-1780)."""

from unittest.mock import patch

import pytest
from dossier_fakes import HG_ONLY, UNPLAYED, dossier_deps
from fastapi.testclient import TestClient
from motw_fakes import U15
from mt_mcp_harness import served

from mt_mcp.scopes import MT_AI_CLIENT, SB_AGENTS_CLIENT

pytestmark = [pytest.mark.unit, pytest.mark.backend]


class TestOverMcp:
    async def test_a_fan_can_list_and_call_it(self):
        async with served(dossier_deps()) as s, s.session("fan") as session:
            names = {t.name for t in (await session.list_tools()).tools}
            result = await session.call_tool("get_team_dossier", {"team_id": 1, "age_group_id": U15})

        assert "get_team_dossier" in names
        assert not result.is_error
        data = result.structured_content
        assert data["error"] is None
        assert [c["division"]["name"] for c in data["conferences"]] == ["Northeast", "Turnpike"]
        assert all(f["id"].startswith("t1:a15:") for f in data["facts"])

    @pytest.mark.parametrize("client", [MT_AI_CLIENT, SB_AGENTS_CLIENT])
    async def test_agents_see_it(self, client):
        async with served(dossier_deps()) as s, s.session("fan", client) as session:
            names = {t.name for t in (await session.list_tools()).tools}
        assert "get_team_dossier" in names

    async def test_schema_and_description(self):
        async with served(dossier_deps()) as s, s.session("fan") as session:
            tool = next(t for t in (await session.list_tools()).tools if t.name == "get_team_dossier")
        assert set(tool.input_schema["properties"]) == {"team_id", "age_group_id", "for_match_id"}
        assert tool.input_schema["required"] == ["team_id"]
        assert set(tool.output_schema["properties"]) >= {"conferences", "key_wins", "form", "facts", "flags", "error"}
        assert "fact id" in tool.description
        assert "another conference" in tool.description

    async def test_playing_up_from_a_match(self):
        async with served(dossier_deps()) as s, s.session("fan") as session:
            data = (await session.call_tool("get_team_dossier", {"team_id": 3, "for_match_id": 602})).structured_content
        assert data["context"]["playing_up_inferred"] is True
        assert data["age_group"]["name"] == "U15"

    async def test_no_age_and_no_match_is_invalid_args(self):
        async with served(dossier_deps()) as s, s.session("fan") as session:
            data = (await session.call_tool("get_team_dossier", {"team_id": 1})).structured_content
        assert data["error"]["kind"] == "invalid_args"


@pytest.fixture
def api():
    import app as app_module
    from auth import get_current_user_required

    app_module.app.dependency_overrides[get_current_user_required] = lambda: {"user_id": "f", "role": "team-fan"}
    with patch.object(app_module, "_my_team_deps", lambda: dossier_deps()):
        yield TestClient(app_module.app)
    app_module.app.dependency_overrides.clear()


class TestApi:
    def test_dossier(self, api):
        r = api.get(f"/api/teams/{HG_ONLY}/dossier", params={"age_group_id": U15})
        assert r.status_code == 200
        body = r.json()
        assert body["key_wins"][0]["kind"] == "pro_academy_upset"
        assert "low_sample" in body["flags"]

    def test_a_team_with_no_results_is_200_with_nulls(self, api):
        r = api.get(f"/api/teams/{UNPLAYED}/dossier", params={"age_group_id": U15})
        assert r.status_code == 200
        body = r.json()
        assert body["totals"] is None
        assert body["conferences"][0]["position"] is None
        assert body["flags"] == ["no_results"]

    def test_for_match(self, api):
        r = api.get("/api/teams/5/dossier", params={"for_match_id": 601})
        assert r.status_code == 200
        assert r.json()["context"]["playing_up"] is True

    @pytest.mark.parametrize(
        "team_id,params",
        [
            (1, {}),
            (1, {"for_match_id": 9999}),
            (9999, {"age_group_id": U15}),
            (1, {"age_group_id": 99}),
        ],
    )
    def test_bad_arguments_are_400(self, api, team_id, params):
        assert api.get(f"/api/teams/{team_id}/dossier", params=params).status_code == 400

    def test_a_failed_match_read_is_503(self, api):
        import app as app_module

        with patch.object(app_module, "_my_team_deps", lambda: dossier_deps(match_fail=True)):
            r = api.get("/api/teams/1/dossier", params={"for_match_id": 501})
        assert r.status_code == 503

    def test_failure_is_503_without_details(self, api):
        import app as app_module

        with patch.object(app_module, "_my_team_deps", lambda: dossier_deps(standings_fail=True)):
            r = api.get("/api/teams/1/dossier", params={"age_group_id": U15})
        assert r.status_code == 503
        assert "PostgREST" not in r.text

    def test_requires_a_logged_in_user(self):
        """Invite-only: a dossier names teams, so no anonymous read."""
        import app as app_module

        r = TestClient(app_module.app).get("/api/teams/1/dossier", params={"age_group_id": U15})
        assert r.status_code in (401, 403)

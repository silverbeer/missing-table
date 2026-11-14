"""Remembered filters per account (SB-1715): shape, endpoint, cache scope.

The default fixture is an account with nothing remembered — every existing
profile, and every new one until its owner touches a filter.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from filter_memory import FilterMemoryUpdate, read_filter_memory, validate_filters

USER = {"user_id": "u-1", "role": "team-fan", "username": "fan"}
SAVED_AT = 1731600000000


@pytest.mark.unit
class TestReadFilterMemory:
    @pytest.mark.parametrize("raw", [None, "", [], "{}"])
    def test_absent_is_empty_object(self, raw):
        assert read_filter_memory(raw) == {}

    def test_returns_a_copy(self):
        stored = {"table": {"saved_at": 1}}
        read_filter_memory(stored)["matches"] = {}
        assert stored == {"table": {"saved_at": 1}}


@pytest.mark.unit
class TestValidateFilters:
    def test_real_matches_filters_pass(self):
        filters = {
            "ageGroupId": 3,
            "seasonId": 3,
            "divisionIds": [1, 7, 12],
            "matchTypeId": "qualifying",
            "viewTab": "all",
            "clubId": None,
            "teamId": None,
            "savedAt": SAVED_AT,
        }
        assert validate_filters(filters) == filters

    @pytest.mark.parametrize(
        "filters",
        [
            {"nested": {"a": 1}},
            {"long": "x" * 65},
            {"list": list(range(51))},
            {"listOfObjects": [{"a": 1}]},
            {f"k{i}": i for i in range(17)},
            {"nan": float("nan")},
        ],
    )
    def test_rejects_what_is_not_a_filter(self, filters):
        with pytest.raises(ValueError):
            validate_filters(filters)


@pytest.mark.unit
class TestFilterMemoryUpdate:
    def test_patch_has_only_sent_fields(self):
        update = FilterMemoryUpdate(panel_open=False, saved_at=SAVED_AT)
        assert update.to_patch() == {"panel_open": False, "saved_at": SAVED_AT}

    def test_null_filters_is_sent_as_forget(self):
        update = FilterMemoryUpdate(filters=None, saved_at=SAVED_AT)
        assert update.to_patch() == {"filters": None, "saved_at": SAVED_AT}

    def test_saved_at_required(self):
        with pytest.raises(ValidationError):
            FilterMemoryUpdate(panel_open=True)

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError):
            FilterMemoryUpdate(saved_at=SAVED_AT, extra=1)


@pytest.mark.unit
class TestFilterMemoryEndpoint:
    def setup_method(self):
        from app import app
        from auth import get_current_user_required

        app.dependency_overrides[get_current_user_required] = lambda: USER
        self.client = TestClient(app)

    def teardown_method(self):
        from app import app

        app.dependency_overrides.clear()

    def _put(self, view, body, side_effect=None):
        import app as app_module

        with patch.object(app_module.player_dao, "set_filter_memory", side_effect=side_effect) as save:
            response = self.client.put(f"/api/auth/filter-memory/{view}", json=body)
        return response, save

    def test_saves_one_views_patch(self):
        body = {"filters": {"ageGroupId": 3}, "saved_at": SAVED_AT}
        response, save = self._put("matches", body)
        assert response.status_code == 200
        save.assert_called_once_with("u-1", "matches", body)

    def test_unknown_view_is_422(self):
        response, save = self._put("tournaments", {"saved_at": SAVED_AT})
        assert response.status_code == 422
        save.assert_not_called()

    def test_oversized_filters_are_422(self):
        response, save = self._put("table", {"filters": {"x": "y" * 500}, "saved_at": SAVED_AT})
        assert response.status_code == 422
        save.assert_not_called()

    def test_storage_failure_is_503_not_500(self):
        response, _ = self._put("table", {"panel_open": True, "saved_at": SAVED_AT}, RuntimeError("no column"))
        assert response.status_code == 503

    def test_profile_without_memory_returns_empty_object(self):
        import app as app_module

        with patch.object(
            app_module.player_dao,
            "get_user_profile_with_relationships",
            return_value={"id": "u-1", "role": "team-fan"},
        ):
            response = self.client.get("/api/auth/profile")
        assert response.status_code == 200
        assert response.json()["filter_memory"] == {}


@pytest.mark.unit
class TestSetFilterMemoryDao:
    def test_rpc_then_clears_only_this_users_profile(self):
        from dao import player_dao as module
        from dao.player_dao import PlayerDAO

        dao = PlayerDAO.__new__(PlayerDAO)
        dao.client = MagicMock()
        with patch.object(module, "clear_cache") as clear:
            dao.set_filter_memory("u-1", "table", {"panel_open": True, "saved_at": SAVED_AT})

        dao.client.rpc.assert_called_once_with(
            "set_filter_memory",
            {"p_user_id": "u-1", "p_view": "table", "p_patch": {"panel_open": True, "saved_at": SAVED_AT}},
        )
        clear.assert_called_once_with("mt:dao:players:profile:u-1")

    def test_rpc_failure_raises_and_clears_nothing(self):
        from dao import player_dao as module
        from dao.player_dao import PlayerDAO

        dao = PlayerDAO.__new__(PlayerDAO)
        dao.client = MagicMock()
        dao.client.rpc.return_value.execute.side_effect = RuntimeError("down")
        with patch.object(module, "clear_cache") as clear, pytest.raises(RuntimeError):
            dao.set_filter_memory("u-1", "table", {"saved_at": SAVED_AT})
        clear.assert_not_called()

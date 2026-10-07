"""User preferences (SB-1286): shape, merge, and the profile endpoint.

The default fixture is an account with no preferences - the state every
existing profile is in after the migration.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from user_preferences import (
    UnknownAgeGroupError,
    UserPreferences,
    merge_preferences,
    read_preferences,
)

AGE_GROUPS = [{"id": 1, "name": "U13"}, {"id": 2, "name": "U14"}, {"id": 3, "name": "U15"}]
KNOWN = [ag["id"] for ag in AGE_GROUPS]


@pytest.mark.unit
class TestReadPreferences:
    @pytest.mark.parametrize("raw", [None, "", [], "{}"])
    def test_absent_or_malformed_is_empty(self, raw):
        assert read_preferences(raw) == {}

    def test_returns_a_copy(self):
        stored = {"default_age_group_id": 2}
        read_preferences(stored)["default_age_group_id"] = 9
        assert stored == {"default_age_group_id": 2}


@pytest.mark.unit
class TestMergePreferences:
    def test_sets_on_empty(self):
        update = UserPreferences(default_age_group_id=3)
        assert merge_preferences({}, update, KNOWN) == {"default_age_group_id": 3}

    def test_null_clears(self):
        update = UserPreferences(default_age_group_id=None)
        assert merge_preferences({"default_age_group_id": 3}, update, KNOWN) == {}

    def test_unsent_keys_are_kept(self):
        stored = {"default_age_group_id": 3, "future_pref": "x"}
        assert merge_preferences(stored, UserPreferences(), KNOWN) == stored

    def test_unknown_age_group_rejected(self):
        with pytest.raises(UnknownAgeGroupError):
            merge_preferences({}, UserPreferences(default_age_group_id=99), KNOWN)

    def test_unknown_key_rejected(self):
        with pytest.raises(ValidationError):
            UserPreferences.model_validate({"default_age_group": 3})


USER = {"user_id": "u-1", "username": "tom_club", "role": "club_manager", "email": None}


@pytest.mark.unit
class TestProfileEndpoint:
    def setup_method(self):
        from app import app
        from auth import get_current_user_required

        app.dependency_overrides[get_current_user_required] = lambda: USER
        self.client = TestClient(app)

    def teardown_method(self):
        from app import app

        app.dependency_overrides.clear()

    def _put(self, body, stored=None):
        import app as app_module

        with (
            patch.object(
                app_module.player_dao,
                "get_user_profile_with_relationships",
                return_value={"id": "u-1", "preferences": stored if stored is not None else {}},
            ),
            patch.object(app_module.season_dao, "get_all_age_groups", return_value=AGE_GROUPS),
            patch.object(app_module.player_dao, "update_user_profile") as update,
        ):
            response = self.client.put("/api/auth/profile", json=body)
        return response, update

    def test_saves_default_age_group(self):
        response, update = self._put({"preferences": {"default_age_group_id": 3}})
        assert response.status_code == 200
        saved = update.call_args.args[1]
        assert saved["preferences"] == {"default_age_group_id": 3}

    def test_preferences_only_save_leaves_overlay_alone(self):
        # The model defaults overlay_style/colors; a partial save must not
        # write those defaults over the player's customisation.
        _, update = self._put({"preferences": {"default_age_group_id": 3}})
        saved = update.call_args.args[1]
        for field in ("overlay_style", "primary_color", "text_color", "accent_color"):
            assert field not in saved

    def test_null_clears_preference(self):
        _, update = self._put({"preferences": {"default_age_group_id": None}}, stored={"default_age_group_id": 3})
        assert update.call_args.args[1]["preferences"] == {}

    def test_unknown_age_group_is_400(self):
        response, update = self._put({"preferences": {"default_age_group_id": 99}})
        assert response.status_code == 400
        update.assert_not_called()

    def test_explicit_overlay_still_saved(self):
        _, update = self._put({"overlay_style": "jersey", "primary_color": "#000000"})
        saved = update.call_args.args[1]
        assert saved["overlay_style"] == "jersey"
        assert saved["primary_color"] == "#000000"
        assert "preferences" not in saved

    def test_get_profile_without_preferences_returns_empty_object(self):
        import app as app_module

        with patch.object(
            app_module.player_dao,
            "get_user_profile_with_relationships",
            return_value={"id": "u-1", "role": "club_manager"},
        ):
            response = self.client.get("/api/auth/profile")
        assert response.status_code == 200
        assert response.json()["preferences"] == {}

    def test_success_flag_returned(self):
        # authStore.updateProfile gates on `success`; without it every save
        # reported "Profile update failed" even though it had saved.
        response, _ = self._put({"preferences": {"default_age_group_id": 2}})
        assert response.json()["success"] is True

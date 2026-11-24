"""Tournament logo light/dark variants (SB-1770), without a database.

The endpoints run on the real app with the caller swapped in; the DAO and
Supabase Storage are stand-ins that record what was written where. The DAO
setter runs over a recording client so the column it touches is asserted.

A tournament with no dark logo is the normal case: `logo_dark_url` stays NULL
and the frontend falls back to `logo_url`.
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from dao.tournament_dao import TOURNAMENT_SELECT, TournamentDAO

pytestmark = pytest.mark.unit

ADMIN = {"user_id": "admin-1", "username": "admin", "role": "admin"}
MANAGER = {"user_id": "u1", "role": "team-manager"}


def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGBA", (20, 10), (0, 0, 0, 0)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def api():
    import app as app_module
    from auth import get_current_user_required

    dao = MagicMock()
    dao.set_tournament_logo.side_effect = lambda tid, url, dark=False: {
        "id": tid,
        "logo_dark_url" if dark else "logo_url": url,
    }
    bucket = MagicMock()
    bucket.get_public_url.side_effect = lambda path: f"https://cdn.test/tournament-logos/{path}"
    storage = MagicMock()
    storage.from_.return_value = bucket
    match_dao = MagicMock()
    match_dao.client.storage = storage

    caller: dict = {}
    app_module.app.dependency_overrides[get_current_user_required] = lambda: caller["user"]

    def use(user):
        caller["user"] = user
        return TestClient(app_module.app), dao, bucket

    with patch.object(app_module, "tournament_dao", dao), patch.object(app_module, "match_dao", match_dao):
        yield use
    app_module.app.dependency_overrides.clear()


def _upload(client, query=""):
    return client.post(
        f"/api/admin/tournaments/7/logo{query}",
        files={"file": ("logo.png", _png(), "image/png")},
    )


def _uploaded_paths(bucket) -> list[str]:
    return [c.args[0] for c in bucket.upload.call_args_list]


class TestUpload:
    def test_default_upload_is_the_light_logo(self, api):
        client, dao, bucket = api(ADMIN)
        res = _upload(client)
        assert res.status_code == 200
        assert res.json()["logo_url"] == "https://cdn.test/tournament-logos/7.png"
        dao.set_tournament_logo.assert_called_once_with(7, "https://cdn.test/tournament-logos/7.png", dark=False)
        assert _uploaded_paths(bucket) == ["7.png", "7_sm.png", "7_md.png"]

    def test_dark_upload_writes_its_own_file_and_column(self, api):
        client, dao, bucket = api(ADMIN)
        res = _upload(client, "?variant=dark")
        assert res.status_code == 200
        assert res.json()["logo_dark_url"] == "https://cdn.test/tournament-logos/7-dark.png"
        dao.set_tournament_logo.assert_called_once_with(7, "https://cdn.test/tournament-logos/7-dark.png", dark=True)
        # Never overwrites the light logo's files.
        assert _uploaded_paths(bucket) == ["7-dark.png", "7-dark_sm.png", "7-dark_md.png"]

    def test_unknown_variant_is_rejected(self, api):
        client, dao, _ = api(ADMIN)
        assert _upload(client, "?variant=sepia").status_code == 422
        dao.set_tournament_logo.assert_not_called()

    def test_non_admin_cannot_upload(self, api):
        client, dao, _ = api(MANAGER)
        assert _upload(client, "?variant=dark").status_code == 403
        dao.set_tournament_logo.assert_not_called()


class TestRemove:
    def test_remove_dark_clears_only_the_dark_column(self, api):
        client, dao, _ = api(ADMIN)
        res = client.delete("/api/admin/tournaments/7/logo?variant=dark")
        assert res.status_code == 200
        dao.set_tournament_logo.assert_called_once_with(7, None, dark=True)

    def test_remove_defaults_to_light(self, api):
        client, dao, _ = api(ADMIN)
        assert client.delete("/api/admin/tournaments/7/logo").status_code == 200
        dao.set_tournament_logo.assert_called_once_with(7, None, dark=False)

    def test_missing_tournament_is_404(self, api):
        client, dao, _ = api(ADMIN)
        dao.set_tournament_logo.side_effect = None
        dao.set_tournament_logo.return_value = None
        assert client.delete("/api/admin/tournaments/999/logo?variant=dark").status_code == 404

    def test_non_admin_cannot_remove(self, api):
        client, dao, _ = api(MANAGER)
        assert client.delete("/api/admin/tournaments/7/logo?variant=dark").status_code == 403
        dao.set_tournament_logo.assert_not_called()


class TestDao:
    def _dao(self):
        client = MagicMock()
        dao = TournamentDAO.__new__(TournamentDAO)
        dao.client = client
        dao.get_tournament_by_id = MagicMock(return_value={"id": 7})
        return dao, client

    @pytest.mark.parametrize(("dark", "column"), [(False, "logo_url"), (True, "logo_dark_url")])
    def test_setter_writes_one_column(self, dark, column):
        dao, client = self._dao()
        TournamentDAO.set_tournament_logo.__wrapped__(dao, 7, "https://x/y.png", dark=dark)
        client.table.return_value.update.assert_called_once_with({column: "https://x/y.png"})

    def test_setter_can_clear(self):
        dao, client = self._dao()
        TournamentDAO.set_tournament_logo.__wrapped__(dao, 7, None, dark=True)
        client.table.return_value.update.assert_called_once_with({"logo_dark_url": None})

    def test_every_tournament_read_returns_the_dark_column(self):
        assert "logo_dark_url" in TOURNAMENT_SELECT

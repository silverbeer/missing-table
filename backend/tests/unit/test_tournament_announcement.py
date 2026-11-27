"""Tournament announcement (SB-1797).

One optional line an admin sets on a tournament ("Every MLS NEXT Fest match
scored live"). NULL means none. On update None already means "leave
unchanged", so a blank string is how an admin clears it.

The endpoint tests use the real app with auth overridden and tournament_dao
mocked; the DAO tests capture what would be written to the database.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.unit, pytest.mark.backend]

ADMIN = {"user_id": "admin-1", "username": "admin", "role": "admin"}
CREATE = {"name": "MLS NEXT Fest", "season_id": 184, "start_date": "2026-12-04"}
LINE = "Every MLS NEXT Fest match scored live"


@pytest.fixture
def client():
    import app as app_module
    from auth import require_admin

    dao = MagicMock()
    dao.create_tournament.return_value = {"id": 7}
    dao.update_tournament.return_value = {"id": 7}
    app_module.app.dependency_overrides[require_admin] = lambda: ADMIN
    with patch.object(app_module, "tournament_dao", dao):
        yield TestClient(app_module.app), dao
    app_module.app.dependency_overrides.clear()


class TestEndpoints:
    def test_create_passes_the_announcement_through(self, client):
        http, dao = client
        r = http.post("/api/admin/tournaments", json={**CREATE, "announcement": LINE})
        assert r.status_code == 201
        assert dao.create_tournament.call_args.kwargs["announcement"] == LINE

    def test_create_without_an_announcement_passes_none(self, client):
        http, dao = client
        http.post("/api/admin/tournaments", json=CREATE)
        assert dao.create_tournament.call_args.kwargs["announcement"] is None

    def test_update_passes_the_announcement_through(self, client):
        http, dao = client
        r = http.put("/api/admin/tournaments/7", json={"announcement": LINE})
        assert r.status_code == 200
        assert dao.update_tournament.call_args.kwargs["announcement"] == LINE

    def test_update_without_the_field_leaves_it_unchanged(self, client):
        http, dao = client
        http.put("/api/admin/tournaments/7", json={"name": "Renamed"})
        assert dao.update_tournament.call_args.kwargs["announcement"] is None

    def test_update_passes_an_empty_string_so_the_dao_can_clear_it(self, client):
        http, dao = client
        r = http.put("/api/admin/tournaments/7", json={"announcement": ""})
        assert r.status_code == 200
        assert dao.update_tournament.call_args.kwargs["announcement"] == ""

    def test_160_characters_is_accepted(self, client):
        http, _ = client
        assert http.post("/api/admin/tournaments", json={**CREATE, "announcement": "x" * 160}).status_code == 201

    def test_create_over_160_characters_is_422(self, client):
        http, dao = client
        r = http.post("/api/admin/tournaments", json={**CREATE, "announcement": "x" * 161})
        assert r.status_code == 422
        dao.create_tournament.assert_not_called()

    def test_update_over_160_characters_is_422(self, client):
        http, dao = client
        r = http.put("/api/admin/tournaments/7", json={"announcement": "x" * 161})
        assert r.status_code == 422
        dao.update_tournament.assert_not_called()


@pytest.fixture
def dao():
    from dao.tournament_dao import TournamentDAO

    d = TournamentDAO.__new__(TournamentDAO)
    d.connection_holder = MagicMock()
    d.client = MagicMock()
    d.get_tournament_by_id = MagicMock(return_value={"id": 7})
    return d


def _captured_insert(dao):
    table = dao.client.table.return_value
    table.insert.return_value.execute.return_value.data = [{"id": 7}]
    dao._attach_age_groups = MagicMock(side_effect=lambda rows: rows)
    return table


class TestDaoWrites:
    def test_create_writes_the_stripped_announcement(self, dao):
        table = _captured_insert(dao)
        dao.create_tournament(**CREATE, announcement=f"  {LINE}  ")
        assert table.insert.call_args.args[0]["announcement"] == LINE

    @pytest.mark.parametrize("blank", [None, "", "   "])
    def test_create_with_a_blank_announcement_writes_none(self, dao, blank):
        table = _captured_insert(dao)
        dao.create_tournament(**CREATE, announcement=blank)
        assert "announcement" not in table.insert.call_args.args[0]

    def test_update_writes_the_stripped_announcement(self, dao):
        table = dao.client.table.return_value
        dao.update_tournament(7, announcement=f" {LINE} ")
        assert table.update.call_args.args[0] == {"announcement": LINE}

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_update_with_a_blank_string_clears_to_null(self, dao, blank):
        table = dao.client.table.return_value
        dao.update_tournament(7, announcement=blank)
        assert table.update.call_args.args[0] == {"announcement": None}

    def test_update_with_none_leaves_it_unchanged(self, dao):
        table = dao.client.table.return_value
        dao.update_tournament(7, name="Renamed")
        assert table.update.call_args.args[0] == {"name": "Renamed"}

    def test_every_tournament_read_selects_the_announcement(self):
        from dao.tournament_dao import TOURNAMENT_SELECT

        assert "announcement" in [c.strip() for c in TOURNAMENT_SELECT.split(",")]

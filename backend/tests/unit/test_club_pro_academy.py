"""The Pro Academy flag reaches the database (SB-842).

The Admin UI has had this checkbox on the create and edit forms since before
the field existed anywhere behind it. The value was posted and silently
dropped by Pydantic, so ticking the box, saving and reloading showed it
unticked. The column existed and two clubs had it set — out of band, because
no code path wrote it.
"""

from unittest.mock import MagicMock

import pytest

from models.clubs import Club


@pytest.mark.unit
class TestClubModel:
    def test_the_api_model_accepts_the_flag(self):
        assert Club(name="Toronto FC", city="Toronto, ON", pro_academy=True).pro_academy is True

    def test_it_defaults_to_false(self):
        # Most clubs are not pro academies, and every existing caller omits it.
        assert Club(name="Bayside FC", city="East Providence, RI").pro_academy is False

    def test_it_is_a_bool_not_an_optional(self):
        # PUT /api/clubs/{id} is a replace. None would read as "leave alone" in
        # the DAO while the UI meant "unticked", so the model refuses None.
        with pytest.raises(ValueError):
            Club(name="X", city="Y", pro_academy=None)


def _dao(returned=None):
    from dao.club_dao import ClubDAO

    dao = object.__new__(ClubDAO)
    dao.connection_holder = MagicMock()
    client = MagicMock()
    table = MagicMock()
    for m in ("insert", "update", "eq", "select", "limit"):
        getattr(table, m).return_value = table
    table.execute.return_value = MagicMock(data=[returned or {"id": 1, "name": "Toronto FC"}])
    client.table.return_value = table
    dao.client = client
    dao._table = table
    return dao


@pytest.mark.unit
class TestClubDAO:
    def test_create_writes_the_flag_when_true(self):
        dao = _dao()
        dao.create_club(name="Toronto FC", city="Toronto, ON", pro_academy=True)
        assert dao._table.insert.call_args.args[0]["pro_academy"] is True

    def test_create_writes_the_flag_when_false(self):
        # Written unconditionally, unlike the optional strings: False is a real
        # answer, not an absent one. Omitting it would leave the column at its
        # database default and make the API's answer depend on the schema.
        dao = _dao()
        dao.create_club(name="Bayside FC", city="East Providence, RI")
        assert dao._table.insert.call_args.args[0]["pro_academy"] is False

    def test_update_sets_the_flag(self):
        dao = _dao()
        dao.update_club(club_id=1, pro_academy=True)
        assert dao._table.update.call_args.args[0] == {"pro_academy": True}

    def test_update_can_clear_the_flag(self):
        dao = _dao()
        dao.update_club(club_id=1, pro_academy=False)
        assert dao._table.update.call_args.args[0] == {"pro_academy": False}

    def test_an_update_that_does_not_mention_it_leaves_it_alone(self):
        # None means "not being changed" at the DAO layer. The API model's
        # non-optional bool is what stops the UI from accidentally relying on
        # that; a direct DAO caller renaming a club must not un-flag it.
        dao = _dao()
        dao.update_club(club_id=1, name="Renamed")
        assert "pro_academy" not in dao._table.update.call_args.args[0]

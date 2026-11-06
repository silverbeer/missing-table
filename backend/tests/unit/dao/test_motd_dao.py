"""MotdDAO and check_pick — Tournament Match of the Day (SB-1559).

One pick per (tournament, day). The rules worth pinning are which match may
be a day's pick, and the ways a stored pick can fail to be showable.
"""

from unittest.mock import MagicMock

import pytest

from dao.motd_dao import MotdDAO, MotdPickError, check_pick

FEST = 12

MATCH = {
    "id": 501,
    "match_date": "2026-12-04",
    "tournament_id": FEST,
    "tournament_name": "MLS NEXT Fest 2026",
    "home_team_name": "IFA",
    "away_team_name": "Cedar Stars Bergen",
}

ROW = {
    "id": 1,
    "tournament_id": FEST,
    "match_date": "2026-12-04",
    "match_id": 501,
    "blurb": "Northeast leaders meet in the desert.",
    "reasons": [{"text": "Both unbeaten in league play", "kind": "form"}],
    "selected_by": "admin-uuid",
    "created_at": "2026-12-04T13:00:00Z",
    "updated_at": "2026-12-04T13:00:00Z",
}


def _dao(table_data=None, table_error=None, match=MATCH):
    dao = object.__new__(MotdDAO)
    dao.connection_holder = MagicMock()

    table = MagicMock()
    for method in ("select", "eq", "limit", "order", "upsert", "delete"):
        getattr(table, method).return_value = table
    table.execute.return_value = MagicMock(data=table_data)
    if table_error:
        table.execute.side_effect = table_error

    dao.client = MagicMock()
    dao.client.table.return_value = table
    dao._table = table

    match_dao = MagicMock()
    match_dao.get_match_by_id.return_value = match
    dao._match_dao = match_dao
    return dao


@pytest.mark.unit
class TestCheckPick:
    def test_a_match_in_the_tournament_is_picked_for_its_own_day(self):
        assert check_pick(MATCH, FEST) == "2026-12-04"

    def test_a_match_from_another_tournament_is_rejected(self):
        with pytest.raises(MotdPickError, match="not in tournament 99"):
            check_pick(MATCH, 99)

    def test_a_league_match_with_no_tournament_is_rejected(self):
        with pytest.raises(MotdPickError):
            check_pick({**MATCH, "tournament_id": None}, FEST)

    def test_the_day_guard_catches_a_match_from_a_different_day(self):
        # Picking for Dec 5 and passing Dec 4's match is the mistake this exists for.
        with pytest.raises(MotdPickError, match="on 2026-12-04, not 2026-12-05"):
            check_pick(MATCH, FEST, "2026-12-05")

    def test_the_day_guard_accepts_a_timestamp(self):
        assert check_pick({**MATCH, "match_date": "2026-12-04T19:30:00Z"}, FEST, "2026-12-04") == "2026-12-04"

    def test_a_match_without_a_date_is_rejected(self):
        with pytest.raises(MotdPickError, match="no date"):
            check_pick({**MATCH, "match_date": None}, FEST)


@pytest.mark.unit
class TestGetForDay:
    def test_returns_the_pick_with_its_match_and_reasons(self):
        result = _dao(table_data=[ROW]).get_for_day(FEST, "2026-12-04")
        assert result["match"]["id"] == 501
        assert result["reasons"] == ROW["reasons"]
        assert result["blurb"] == ROW["blurb"]

    def test_no_pick_is_none_not_an_error(self):
        assert _dao(table_data=[]).get_for_day(FEST, "2026-12-04") is None

    def test_reasons_never_provided_stay_null_not_empty(self):
        # null (never written) and [] (written, empty) are different states.
        result = _dao(table_data=[{**ROW, "reasons": None}]).get_for_day(FEST, "2026-12-04")
        assert result["reasons"] is None

    def test_a_pick_whose_match_is_hidden_reads_as_no_pick(self):
        # A test match picked by an admin, read by a visitor.
        assert _dao(table_data=[ROW], match=None).get_for_day(FEST, "2026-12-04") is None

    def test_a_database_error_reads_as_no_pick(self):
        assert _dao(table_error=RuntimeError("down")).get_for_day(FEST, "2026-12-04") is None

    def test_visitors_do_not_see_test_matches(self):
        dao = _dao(table_data=[ROW])
        dao.get_for_day(FEST, "2026-12-04")
        dao._match_dao.get_match_by_id.assert_called_with(501, include_test=False)


@pytest.mark.unit
class TestListForTournament:
    def test_lists_picks_oldest_day_first(self):
        dao = _dao(table_data=[ROW, {**ROW, "id": 2, "match_date": "2026-12-05"}])
        picks = dao.list_for_tournament(FEST)
        assert [p["match_date"] for p in picks] == ["2026-12-04", "2026-12-05"]
        dao._table.order.assert_called_with("match_date")

    def test_hidden_matches_are_dropped_from_the_list(self):
        assert _dao(table_data=[ROW], match=None).list_for_tournament(FEST) == []

    def test_a_database_error_is_an_empty_list(self):
        assert _dao(table_error=RuntimeError("down")).list_for_tournament(FEST) == []


@pytest.mark.unit
class TestSetForMatch:
    def test_upserts_on_tournament_and_the_matchs_own_day(self):
        dao = _dao(table_data=[ROW])
        result = dao.set_for_match(FEST, 501, blurb="x", reasons=[{"text": "y", "kind": None}], selected_by="admin")
        payload = dao._table.upsert.call_args.args[0]
        assert payload["match_date"] == "2026-12-04"
        assert payload["tournament_id"] == FEST
        assert payload["reasons"] == [{"text": "y", "kind": None}]
        assert dao._table.upsert.call_args.kwargs["on_conflict"] == "tournament_id,match_date"
        assert result["match"]["id"] == 501

    def test_an_unknown_match_is_none(self):
        assert _dao(match=None).set_for_match(FEST, 999) is None

    def test_a_match_from_another_tournament_raises_before_writing(self):
        dao = _dao()
        with pytest.raises(MotdPickError):
            dao.set_for_match(99, 501)
        dao._table.upsert.assert_not_called()

    def test_picking_reads_the_match_including_test_fixtures(self):
        dao = _dao(table_data=[ROW])
        dao.set_for_match(FEST, 501)
        dao._match_dao.get_match_by_id.assert_any_call(501, include_test=True)


@pytest.mark.unit
class TestClearDay:
    def test_true_when_a_row_went_away(self):
        assert _dao(table_data=[ROW]).clear_day(FEST, "2026-12-04") is True

    def test_false_when_nothing_was_picked(self):
        assert _dao(table_data=[]).clear_day(FEST, "2026-12-04") is False

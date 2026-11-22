"""MotdDAO and check_pick — Tournament Match of the Day (SB-1559, SB-1750).

One pick per (tournament, day, age group). The rules worth pinning are which
match may be a slot's pick, that one age group's pick never stands in for
another's, and the ways a stored pick can fail to be showable.
"""

from unittest.mock import MagicMock

import pytest

from dao.motd_dao import MotdDAO, MotdPickError, MotdWriteError, check_pick

FEST = 12
U15 = 3
U16 = 4

MATCH = {
    "id": 501,
    "match_date": "2026-12-04",
    "tournament_id": FEST,
    "age_group_id": U15,
    "age_group_name": "U15",
    "tournament_name": "MLS NEXT Fest 2026",
    "home_team_name": "IFA",
    "away_team_name": "Cedar Stars Bergen",
}

ROW = {
    "id": 1,
    "tournament_id": FEST,
    "match_date": "2026-12-04",
    "age_group_id": U15,
    "match_id": 501,
    "blurb": "Northeast leaders meet in the desert.",
    "reasons": [{"text": "Both unbeaten in league play", "kind": "form"}],
    "selected_by": "admin-uuid",
    "created_at": "2026-12-04T13:00:00Z",
    "updated_at": "2026-12-04T13:00:00Z",
}

U16_MATCH = {**MATCH, "id": 502, "age_group_id": U16, "age_group_name": "U16"}
U16_ROW = {**ROW, "id": 2, "age_group_id": U16, "match_id": 502}
MATCHES = {501: MATCH, 502: U16_MATCH}


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


def _two_ages(rows):
    """A day at a multi-age tournament: each row hydrates with its own match."""
    dao = _dao(table_data=rows)
    dao._match_dao.get_match_by_id.side_effect = lambda match_id, include_test=False: MATCHES[match_id]
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

    def test_a_match_without_an_age_group_is_rejected(self):
        # Production allows NULL matches.age_group_id; the slot key does not.
        with pytest.raises(MotdPickError, match="Match 501 has no age group"):
            check_pick({**MATCH, "age_group_id": None}, FEST)

    def test_a_match_without_an_age_group_is_rejected_whatever_slot_was_asked_for(self):
        with pytest.raises(MotdPickError, match="has no age group"):
            check_pick({**MATCH, "age_group_id": None}, FEST, age_group_id=U16)

    def test_the_age_guard_accepts_the_matchs_own_age_group(self):
        assert check_pick(MATCH, FEST, age_group_id=U15) == "2026-12-04"

    def test_the_age_guard_catches_a_match_from_another_age_group(self):
        # Picking the U16 slot and passing a U15 match.
        with pytest.raises(MotdPickError, match=f"in age group {U15}, not {U16}"):
            check_pick(MATCH, FEST, age_group_id=U16)


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

    def test_the_pick_carries_its_age_group(self):
        result = _dao(table_data=[ROW]).get_for_day(FEST, "2026-12-04")
        assert result["age_group_id"] == U15
        assert result["age_group"] == "U15"

    def test_each_age_group_gets_its_own_pick_on_the_same_day(self):
        dao = _two_ages([U16_ROW, ROW])
        assert dao.get_for_day(FEST, "2026-12-04", age_group_id=U15)["match"]["id"] == 501
        assert dao.get_for_day(FEST, "2026-12-04", age_group_id=U16)["match"]["id"] == 502

    def test_an_age_group_with_no_pick_is_none_not_another_ages_pick(self):
        # U15 has a pick that day; U16 must not borrow it.
        assert _dao(table_data=[ROW]).get_for_day(FEST, "2026-12-04", age_group_id=U16) is None

    def test_without_an_age_group_the_days_first_pick_by_age_is_returned(self):
        # What a single-age tournament, and a caller from before SB-1750, gets.
        assert _two_ages([U16_ROW, ROW]).get_for_day(FEST, "2026-12-04")["age_group_id"] == U15

    def test_a_legacy_row_without_an_age_group_takes_its_matchs(self):
        # Before the SB-1750 migration the column does not exist.
        legacy = {k: v for k, v in ROW.items() if k != "age_group_id"}
        dao = _dao(table_data=[legacy])
        assert dao.get_for_day(FEST, "2026-12-04")["age_group_id"] == U15
        assert dao.get_for_day(FEST, "2026-12-04", age_group_id=U15)["match"]["id"] == 501
        assert dao.get_for_day(FEST, "2026-12-04", age_group_id=U16) is None

    def test_reads_never_name_the_age_group_column(self):
        # So the public banner survives the gap before the migration runs.
        dao = _dao(table_data=[ROW])
        dao.get_for_day(FEST, "2026-12-04", age_group_id=U15)
        assert all(call.args[0] != "age_group_id" for call in dao._table.eq.call_args_list)
        dao._table.order.assert_not_called()


@pytest.mark.unit
class TestListForDay:
    def test_two_age_groups_on_one_day_are_two_picks_in_age_order(self):
        picks = _two_ages([U16_ROW, ROW]).list_for_day(FEST, "2026-12-04")
        assert [p["age_group_id"] for p in picks] == [U15, U16]
        assert [p["match"]["id"] for p in picks] == [501, 502]

    def test_an_unpicked_day_is_an_empty_list(self):
        assert _dao(table_data=[]).list_for_day(FEST, "2026-12-04") == []

    def test_a_database_error_is_an_empty_list(self):
        assert _dao(table_error=RuntimeError("down")).list_for_day(FEST, "2026-12-04") == []


@pytest.mark.unit
class TestListForTournament:
    def test_lists_picks_oldest_day_first(self):
        dao = _dao(table_data=[ROW, {**ROW, "id": 2, "match_date": "2026-12-05"}])
        picks = dao.list_for_tournament(FEST)
        assert [p["match_date"] for p in picks] == ["2026-12-04", "2026-12-05"]
        dao._table.order.assert_called_with("match_date")

    def test_two_age_groups_on_the_same_day_list_as_two_picks(self):
        picks = _two_ages([U16_ROW, ROW]).list_for_tournament(FEST)
        assert [(p["match_date"], p["age_group_id"]) for p in picks] == [("2026-12-04", U15), ("2026-12-04", U16)]

    def test_hidden_matches_are_dropped_from_the_list(self):
        assert _dao(table_data=[ROW], match=None).list_for_tournament(FEST) == []

    def test_a_database_error_is_an_empty_list(self):
        assert _dao(table_error=RuntimeError("down")).list_for_tournament(FEST) == []


@pytest.mark.unit
class TestSetForMatch:
    def test_upserts_on_tournament_the_matchs_own_day_and_its_age_group(self):
        dao = _dao(table_data=[ROW])
        result = dao.set_for_match(FEST, 501, blurb="x", reasons=[{"text": "y", "kind": None}], selected_by="admin")
        payload = dao._table.upsert.call_args.args[0]
        assert payload["match_date"] == "2026-12-04"
        assert payload["tournament_id"] == FEST
        assert payload["reasons"] == [{"text": "y", "kind": None}]
        assert payload["age_group_id"] == U15
        assert dao._table.upsert.call_args.kwargs["on_conflict"] == "tournament_id,match_date,age_group_id"
        assert result["match"]["id"] == 501

    def test_the_age_group_comes_from_the_match_when_none_is_passed(self):
        dao = _two_ages([U16_ROW])
        result = dao.set_for_match(FEST, 502)
        assert dao._table.upsert.call_args.args[0]["age_group_id"] == U16
        assert result["age_group_id"] == U16

    def test_a_mismatched_age_group_raises_before_writing(self):
        dao = _dao()
        with pytest.raises(MotdPickError, match="age group"):
            dao.set_for_match(FEST, 501, age_group_id=U16)
        dao._table.upsert.assert_not_called()

    def test_a_match_without_an_age_group_raises_before_writing(self):
        dao = _dao(match={**MATCH, "age_group_id": None})
        with pytest.raises(MotdPickError, match="no age group"):
            dao.set_for_match(FEST, 501)
        dao._table.upsert.assert_not_called()

    def test_a_failed_write_raises_instead_of_looking_like_an_unknown_match(self):
        # None means "no such match" (404); a write the database refused is not that.
        dao = _dao(table_error=RuntimeError('column "age_group_id" does not exist'))
        with pytest.raises(MotdWriteError) as raised:
            dao.set_for_match(FEST, 501)
        assert "age_group_id" not in str(raised.value)

    def test_a_pick_that_cannot_be_read_back_raises(self):
        with pytest.raises(MotdWriteError):
            _dao(table_data=[]).set_for_match(FEST, 501)

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
    def test_counts_the_rows_that_went_away(self):
        assert _dao(table_data=[ROW]).clear_day(FEST, "2026-12-04") == 1

    def test_zero_when_nothing_was_picked(self):
        assert _dao(table_data=[]).clear_day(FEST, "2026-12-04") == 0

    def test_without_an_age_group_every_pick_that_day_goes(self):
        dao = _dao(table_data=[ROW, U16_ROW])
        assert dao.clear_day(FEST, "2026-12-04") == 2
        assert [call.args for call in dao._table.eq.call_args_list] == [
            ("tournament_id", FEST),
            ("match_date", "2026-12-04"),
        ]

    def test_with_an_age_group_only_that_slot_goes(self):
        dao = _dao(table_data=[U16_ROW])
        assert dao.clear_day(FEST, "2026-12-04", age_group_id=U16) == 1
        dao._table.eq.assert_any_call("age_group_id", U16)

    def test_a_failed_delete_raises_instead_of_looking_like_nothing_was_picked(self):
        # 0 means "none was there"; a delete the database refused left the pick in place.
        dao = _dao(table_error=RuntimeError('column "age_group_id" does not exist'))
        with pytest.raises(MotdWriteError) as raised:
            dao.clear_day(FEST, "2026-12-04", age_group_id=U16)
        assert "age_group_id" not in str(raised.value)

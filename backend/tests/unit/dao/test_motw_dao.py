"""MotwDAO (SB-1010).

The Match of the Week is singular by construction: one row per week_start.
The interesting behaviour here is all about which week a pick lands in, and
about the two ways a pick can exist in the table but not be showable.
"""

from unittest.mock import MagicMock

import pytest

from dao.motw_dao import MotwDAO, week_start_for

MATCH = {
    "id": 77,
    "match_date": "2026-09-05",
    "home_team_name": "NEFC",
    "away_team_name": "IFA",
    "match_status": "scheduled",
}

ROW = {
    "id": 1,
    "match_id": 77,
    "week_start": "2026-08-31",
    "blurb": "Two unbeaten records.",
    "selected_by": "admin-uuid",
    "created_at": "2026-09-01T10:00:00Z",
    "updated_at": "2026-09-01T10:00:00Z",
}


def _dao(table_data=None, table_error=None, match=MATCH):
    dao = object.__new__(MotwDAO)
    dao.connection_holder = MagicMock()

    table = MagicMock()
    for method in ("select", "eq", "in_", "limit", "upsert", "delete"):
        getattr(table, method).return_value = table
    table.execute.return_value = MagicMock(data=table_data)
    if table_error:
        table.execute.side_effect = table_error

    client = MagicMock()
    client.table.return_value = table
    dao.client = client
    dao._table = table

    match_dao = MagicMock()
    match_dao.get_match_by_id.return_value = match
    dao._match_dao = match_dao
    return dao


@pytest.mark.unit
class TestWeekStartFor:
    def test_snaps_a_midweek_date_back_to_monday(self):
        # Saturday 2026-09-05 belongs to the week beginning Monday 2026-08-31.
        assert week_start_for("2026-09-05") == "2026-08-31"

    def test_a_monday_is_its_own_week_start(self):
        assert week_start_for("2026-08-31") == "2026-08-31"

    def test_sunday_belongs_to_the_week_that_started_six_days_earlier(self):
        # The off-by-one that would put Sunday's fixture in next week's slot,
        # silently overwriting a pick made for the week ahead.
        assert week_start_for("2026-09-06") == "2026-08-31"

    def test_accepts_a_timestamp_and_reads_only_the_date(self):
        assert week_start_for("2026-09-05T14:30:00Z") == "2026-08-31"


@pytest.mark.unit
class TestGetForWeek:
    def test_returns_the_pick_with_its_match(self):
        dao = _dao(table_data=[ROW])
        result = dao.get_for_week("2026-08-31")

        assert result["week_start"] == "2026-08-31"
        assert result["blurb"] == "Two unbeaten records."
        assert result["match"]["home_team_name"] == "NEFC"

    def test_no_pick_is_none_not_an_error(self):
        # Most weeks start unpicked. That is the ordinary state, and every
        # caller has to render it anyway.
        assert _dao(table_data=[]).get_for_week("2026-08-31") is None

    def test_hides_a_pick_whose_match_the_viewer_cannot_see(self):
        # A pick made on a test match by an admin must not render as a hero
        # with an empty middle for a visitor.
        dao = _dao(table_data=[ROW], match=None)
        assert dao.get_for_week("2026-08-31") is None

    def test_a_read_failure_degrades_to_no_pick(self):
        dao = _dao(table_error=RuntimeError("connection reset"))
        assert dao.get_for_week("2026-08-31") is None


@pytest.mark.unit
class TestSetForMatch:
    def test_files_the_pick_under_the_match_s_own_week(self):
        # Not under "this week" — picking next week's fixture in advance must
        # fill next week's slot, not overwrite the current one.
        dao = _dao(table_data=[ROW])
        dao.set_for_match(77, blurb="Two unbeaten records.", selected_by="admin-uuid")

        payload = dao._table.upsert.call_args.args[0]
        assert payload["week_start"] == "2026-08-31"
        assert payload["match_id"] == 77
        assert dao._table.upsert.call_args.kwargs["on_conflict"] == "week_start"

    def test_records_who_picked_it(self):
        dao = _dao(table_data=[ROW])
        dao.set_for_match(77, selected_by="admin-uuid")

        assert dao._table.upsert.call_args.args[0]["selected_by"] == "admin-uuid"

    def test_unknown_match_is_none_so_the_api_can_404(self):
        # Distinct from an unpicked week: a bad match id really is a bad
        # request.
        dao = _dao(table_data=[], match=None)
        assert dao.set_for_match(999) is None

    def test_sees_test_matches_so_an_admin_can_feature_one(self):
        dao = _dao(table_data=[ROW])
        dao.set_for_match(77)

        assert dao._match_dao.get_match_by_id.call_args.kwargs["include_test"] is True


@pytest.mark.unit
class TestClearWeek:
    def test_true_when_a_row_went_away(self):
        assert _dao(table_data=[ROW]).clear_week("2026-08-31") is True

    def test_false_when_the_week_was_already_empty(self):
        assert _dao(table_data=[]).clear_week("2026-08-31") is False


@pytest.mark.unit
class TestWeekStartsWithPicks:
    def test_maps_match_ids_to_their_week(self):
        dao = _dao(table_data=[{"match_id": 77, "week_start": "2026-08-31"}])
        assert dao.week_starts_with_picks([77, 78]) == {77: "2026-08-31"}

    def test_empty_input_never_reaches_the_database(self):
        # `in_()` with an empty list is an easy way to ask for everything.
        dao = _dao(table_data=[])
        assert dao.week_starts_with_picks([]) == {}
        dao.client.table.assert_not_called()

"""CoverageDAO (SB-1021).

This DAO exists because absence produces no row to count. Every other view of
competitions in the product is built from fixtures that arrived, so a
conference that sent nothing is invisible to all of them — which is how six of
eight Homegrown League conferences went a season without anyone noticing.

So the cases that matter here are the ones about nothing: a conference expected
and empty, a league nobody wrote expectations for, and a read that fails.
"""

from unittest.mock import MagicMock

import pytest

from dao.coverage_dao import COVERED, EMPTY, UNDECLARED, UNEXPECTED, CoverageDAO


def _row(**overrides):
    row = {
        "league_name": "Homegrown",
        "division_id": 1,
        "division_name": "Northeast",
        "age_group_id": 3,
        "age_group_name": "U15",
        "is_expected": True,
        "fixtures": 190,
        "played": 12,
        "last_fixture": "2026-09-05",
        "teams_registered": 24,
    }
    row.update(overrides)
    return row


def _dao(rpc_data=None, rpc_error=None):
    dao = object.__new__(CoverageDAO)
    dao.connection_holder = MagicMock()

    rpc = MagicMock()
    rpc.execute.return_value = MagicMock(data=rpc_data)
    if rpc_error:
        rpc.execute.side_effect = rpc_error

    client = MagicMock()
    client.rpc.return_value = rpc
    dao.client = client
    dao._rpc = rpc
    return dao


@pytest.mark.unit
class TestStatus:
    def test_expected_with_fixtures_is_covered(self):
        dao = _dao(rpc_data=[_row(fixtures=190)])
        assert dao.report(184)["rows"][0]["status"] == COVERED

    def test_expected_with_nothing_is_empty(self):
        # The whole reason this DAO exists: Frontier runs U13-U19 and sent
        # zero fixtures, and no other query in the product can say so.
        dao = _dao(rpc_data=[_row(division_name="Frontier", fixtures=0)])
        assert dao.report(184)["rows"][0]["status"] == EMPTY

    def test_fixtures_outside_a_declared_leagues_expectations_are_unexpected(self):
        # The other direction — a feed quietly changing shape. Only meaningful
        # in a league that HAS expectations, so this row needs a declared
        # sibling to be judged against.
        dao = _dao(
            rpc_data=[
                _row(fixtures=190),
                _row(division_name="Somewhere New", is_expected=False, fixtures=14),
            ]
        )
        assert dao.report(184)["rows"][1]["status"] == UNEXPECTED

    def test_fixtures_in_a_league_with_no_expectations_are_undeclared_not_unexpected(
        self,
    ):
        # MT holds 49 real Academy fixtures and no statement of what the
        # Academy Division runs. Calling those "unexpected" would raise an
        # alarm about correct data.
        dao = _dao(
            rpc_data=[
                _row(league_name="Academy", division_name="New England",
                     is_expected=False, fixtures=49)
            ]
        )
        report = dao.report(184)

        assert report["rows"][0]["status"] == UNDECLARED
        assert report["summary"]["unexpected"] == 0
        assert report["summary"]["undeclared"] == 1

    def test_a_missing_fixture_count_is_treated_as_none(self):
        dao = _dao(rpc_data=[_row(fixtures=None)])
        assert dao.report(184)["rows"][0]["status"] == EMPTY


@pytest.mark.unit
class TestSummary:
    def test_counts_each_outcome(self):
        dao = _dao(
            rpc_data=[
                _row(fixtures=190),
                _row(division_name="Frontier", fixtures=0),
                _row(division_name="Mid-America", fixtures=0),
                _row(is_expected=False, fixtures=3),
            ]
        )
        summary = dao.report(184)["summary"]

        assert summary == {
            "expected": 3,
            "covered": 1,
            "empty": 2,
            "unexpected": 1,
            "undeclared": 0,
        }

    def test_the_denominator_ships_with_every_summary(self):
        # A coverage figure without its denominator is the aggregate CLAUDE.md
        # rule 3 forbids.
        dao = _dao(rpc_data=[_row(fixtures=0), _row(fixtures=5)])
        assert dao.report(184)["summary"]["expected"] == 2

    def test_empty_count_is_the_number_worth_alerting_on(self):
        dao = _dao(rpc_data=[_row(fixtures=0), _row(fixtures=0), _row(fixtures=5)])
        assert dao.empty_count(184) == 2


@pytest.mark.unit
class TestPerLeague:
    def test_splits_totals_by_league(self):
        dao = _dao(
            rpc_data=[
                _row(league_name="Homegrown", fixtures=190),
                _row(league_name="Homegrown", division_name="Frontier", fixtures=0),
                _row(league_name="Flex", division_name="Turnpike", fixtures=45),
            ]
        )
        leagues = {lg["league"]: lg for lg in dao.report(184)["leagues"]}

        assert leagues["Homegrown"]["covered"] == 1
        assert leagues["Homegrown"]["empty"] == 1
        assert leagues["Flex"]["covered"] == 1
        assert leagues["Flex"]["empty"] == 0

    def test_counts_distinct_conferences_not_rows(self):
        dao = _dao(
            rpc_data=[
                _row(division_name="Northeast", age_group_name="U15"),
                _row(division_name="Northeast", age_group_name="U16"),
                _row(division_name="Florida", age_group_name="U15"),
            ]
        )
        leagues = {lg["league"]: lg for lg in dao.report(184)["leagues"]}

        assert leagues["Homegrown"]["divisions"] == 2

    def test_a_division_covered_at_some_ages_and_empty_at_others_counts_both(self):
        # Homegrown Florida: fixtures at U13/U14, nothing at U15-U19. Counting
        # by division would call it covered and hide four missing brackets,
        # which is why the unit is (division, age group).
        dao = _dao(
            rpc_data=[
                _row(division_name="Florida", age_group_name="U13", fixtures=71),
                _row(division_name="Florida", age_group_name="U14", fixtures=71),
                _row(division_name="Florida", age_group_name="U15", fixtures=0),
                _row(division_name="Florida", age_group_name="U16", fixtures=0),
            ]
        )
        summary = dao.report(184)["summary"]

        assert summary["covered"] == 2
        assert summary["empty"] == 2

    def test_a_league_with_no_expectations_says_so(self):
        # The Academy Division runs its own MLS NEXT Cup with separate U15-U19
        # finals. MT holds one conference of it. Reporting that as covered
        # because nothing contradicts it would be a lie by omission.
        dao = _dao(
            rpc_data=[
                _row(league_name="Homegrown", fixtures=190),
                _row(
                    league_name="Academy",
                    division_name="New England",
                    is_expected=False,
                    fixtures=49,
                ),
            ]
        )
        leagues = {lg["league"]: lg for lg in dao.report(184)["leagues"]}

        assert leagues["Academy"]["declared"] is False
        assert leagues["Homegrown"]["declared"] is True


@pytest.mark.unit
class TestDegradation:
    def test_a_read_failure_returns_an_empty_report_rather_than_raising(self):
        # This backs an admin screen. A diagnostic that takes down the page it
        # reports on is worse than no diagnostic.
        dao = _dao(rpc_error=RuntimeError("connection reset"))
        report = dao.report(184)

        assert report["rows"] == []
        assert report["available"] is False
        assert report["summary"]["empty"] == 0

    def test_a_season_with_no_expectations_reports_nothing_not_everything_missing(self):
        # An unseeded season must not read as "the whole league is missing".
        dao = _dao(rpc_data=[])
        report = dao.report(184)

        assert report["available"] is True
        assert report["summary"] == {
            "expected": 0,
            "covered": 0,
            "empty": 0,
            "unexpected": 0,
            "undeclared": 0,
        }

    def test_passes_the_season_through_to_the_function(self):
        dao = _dao(rpc_data=[])
        dao.report(184)

        assert dao.client.rpc.call_args.args[1] == {"p_season_id": 184}

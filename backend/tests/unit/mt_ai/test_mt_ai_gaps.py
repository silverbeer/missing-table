"""SB-1308: what MT AI could not answer — grouping ai_tool_calls rows.

Pure logic over plain dicts shaped like AIConversationDAO.gap_tool_calls returns
them; no database.
"""

from datetime import UTC, datetime

import pytest

from mt_tools.ai_gaps import MAX_DAYS, MAX_ROWS, call_outcome, group_gaps, list_ai_gaps, query_of

pytestmark = [pytest.mark.unit, pytest.mark.backend]

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def call(query, status="not_found", *, tool="search_teams", age_group=None, error_kind=None, at="2026-10-09T10:00"):
    args = {"query": query} if isinstance(query, str) else dict(query)
    if age_group:
        args["age_group"] = age_group
    return {"tool_name": tool, "args": args, "status": status, "error_kind": error_kind, "created_at": at}


class FakeSource:
    def __init__(self, rows=(), total=None, fail=False):
        self.rows = list(rows)
        self.total = len(self.rows) if total is None else total
        self.fail = fail
        self.seen: list[tuple] = []

    def gap_tool_calls(self, since, outcomes, tool=None, max_rows=MAX_ROWS):
        self.seen.append((since, outcomes, tool, max_rows))
        if self.fail:
            raise RuntimeError('relation "ai_tool_calls" does not exist')
        return [r for r in self.rows if tool is None or r["tool_name"] == tool][:max_rows]

    def count_tool_calls(self, since, tool=None):
        return self.total


class TestOutcome:
    def test_the_tools_status_is_the_outcome(self):
        assert call_outcome(call("IFA", "ambiguous")) == "ambiguous"

    def test_an_error_kind_wins_over_the_status(self):
        """search_teams reports an outage as status not_found + error unavailable: not a gap."""
        assert call_outcome(call("IFA", "not_found", error_kind="unavailable")) == "unavailable"

    def test_status_is_read_from_a_full_result_too(self):
        row = {"tool_name": "search_teams", "args": {}, "result": {"status": "not_found"}, "error_kind": None}
        assert call_outcome(row) == "not_found"

    def test_a_list_tool_without_a_status_has_none(self):
        assert call_outcome(call({"team_id": 1}, None, tool="get_upcoming_matches")) is None


class TestQuery:
    def test_query_argument_with_whitespace_collapsed(self):
        assert query_of({"query": "  IFA   U15 ", "age_group": "U15"}) == "IFA U15"

    def test_tools_without_a_query_show_their_arguments(self):
        assert query_of({"team_id": 9999, "limit": 5}) == "limit=5, team_id=9999"

    def test_missing_args_are_an_empty_query(self):
        assert query_of(None) == ""


class TestGrouping:
    def test_nothing_unanswered_is_an_empty_list(self):
        assert group_gaps([]) == []

    def test_answered_calls_and_outages_are_not_gaps(self):
        rows = [
            call("IFA", "resolved"),
            call("NEFC", "not_found", error_kind="unavailable"),
            call({"team_id": 1}, None, tool="get_upcoming_matches"),
        ]
        assert group_gaps(rows) == []

    def test_same_query_in_different_case_and_spacing_is_one_gap(self):
        rows = [
            call("Bayside  FC", at="2026-10-01T09:00"),
            call("bayside fc", "ambiguous", age_group="U14", at="2026-10-08T09:00"),
            call("BAYSIDE FC", age_group="U15", at="2026-10-03T09:00"),
        ]
        [gap] = group_gaps(rows)
        assert (gap.tool, gap.count, gap.not_found, gap.ambiguous) == ("search_teams", 3, 2, 1)
        assert gap.query == "bayside fc"  # the latest spelling
        assert gap.first_seen.startswith("2026-10-01")
        assert gap.last_seen.startswith("2026-10-08")
        assert gap.age_groups == ["U14", "U15"]

    def test_same_query_on_different_tools_are_separate_gaps(self):
        rows = [call("Rovers"), call("Rovers", tool="search_players")]
        assert sorted(g.tool for g in group_gaps(rows)) == ["search_players", "search_teams"]

    def test_error_kind_not_found_counts_for_tools_without_a_status(self):
        rows = [call({"team_id": 9999}, None, tool="get_upcoming_matches", error_kind="not_found")]
        [gap] = group_gaps(rows)
        assert (gap.tool, gap.query, gap.not_found) == ("get_upcoming_matches", "team_id=9999", 1)

    def test_most_asked_first_then_most_recent(self):
        rows = [
            call("Old", at="2026-10-01T09:00"),
            call("New", at="2026-10-09T09:00"),
            call("Often", at="2026-10-02T09:00"),
            call("Often", at="2026-10-03T09:00"),
        ]
        assert [g.query for g in group_gaps(rows)] == ["Often", "New", "Old"]

    def test_no_age_group_given_is_an_empty_list_not_a_guess(self):
        [gap] = group_gaps([call("IFA")])
        assert gap.age_groups == []


class TestReport:
    def test_empty_window_is_an_empty_list_with_its_denominator(self):
        result = list_ai_gaps(FakeSource(total=42), days=30, now=NOW)

        assert result.gaps == []
        assert (result.count, result.gap_calls, result.total_calls) == (0, 0, 42)
        assert result.error is None

    def test_report_counts_and_window(self):
        source = FakeSource([call("Bayside"), call("Bayside"), call("IFA", "ambiguous")], total=40)

        result = list_ai_gaps(source, days=7, now=NOW)

        assert (result.count, result.gap_calls, result.total_calls) == (2, 3, 40)
        assert result.since == "2026-10-03T12:00:00+00:00"
        since, outcomes, tool, _ = source.seen[0]
        assert (since, outcomes, tool) == (result.since, ("not_found", "ambiguous"), None)

    def test_one_tool_only(self):
        source = FakeSource(
            [call("Bayside"), call({"team_id": 1}, None, tool="get_upcoming_matches", error_kind="not_found")]
        )
        result = list_ai_gaps(source, tool="get_upcoming_matches", now=NOW)
        assert [g.tool for g in result.gaps] == ["get_upcoming_matches"]
        assert result.tool == "get_upcoming_matches"

    def test_days_are_clamped(self):
        assert list_ai_gaps(FakeSource(), days=0, now=NOW).days == 1
        assert list_ai_gaps(FakeSource(), days=10_000, now=NOW).days == MAX_DAYS

    def test_a_failed_read_is_an_error_not_an_empty_report(self):
        result = list_ai_gaps(FakeSource(fail=True), now=NOW)

        assert result.gaps is None
        assert result.error is not None and result.error.kind == "unavailable"

    def test_hitting_the_row_cap_says_so(self):
        source = FakeSource([call("X")] * MAX_ROWS)
        assert list_ai_gaps(source, now=NOW).truncated is True
        assert list_ai_gaps(FakeSource([call("X")]), now=NOW).truncated is False

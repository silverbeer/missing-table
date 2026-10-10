"""Admin ingest-failure tools (SB-1304): the logic, and the same tools over mt-mcp."""

from datetime import UTC, datetime

import pytest
from mt_mcp_harness import FakeIngest, failure_row, served

from mt_mcp.observe import TOOL_CALLS
from mt_mcp.scopes import MT_AI_CLIENT
from mt_tools.ingest import list_ingest_failures, resolve_ingest_failure

pytestmark = [pytest.mark.unit, pytest.mark.backend]

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)


def ingest() -> FakeIngest:
    return FakeIngest(
        [
            failure_row(1, "Boston Utd", "2026-10-09T00:00:00+00:00", match_count=5),
            failure_row(2, "IFA Academy", "2026-09-01T00:00:00+00:00"),  # unseen > 7 days
            failure_row(3, "Old Name FC", "2026-10-08T00:00:00+00:00", resolved_at="2026-10-08T01:00:00+00:00"),
        ]
    )


class TestListLogic:
    def test_open_rows_newest_first_with_totals_and_stale_hint(self):
        result = list_ingest_failures(ingest(), now=NOW)

        assert [f.raw_name for f in result.failures] == ["Boston Utd", "IFA Academy"]
        assert (result.count, result.matches_dropped, result.stale_count) == (2, 8, 1)
        assert [f.stale for f in result.failures] == [False, True]
        assert result.error is None

    def test_nothing_open_is_an_empty_list_not_an_error(self):
        result = list_ingest_failures(FakeIngest([]), now=NOW)

        assert result.failures == []
        assert result.error is None

    def test_a_failed_read_is_null_with_an_error_not_an_empty_list(self):
        source = ingest()
        source.fail = True

        result = list_ingest_failures(source, now=NOW)

        assert result.failures is None
        assert result.error.kind == "unavailable"

    @pytest.mark.parametrize(("asked", "used"), [(0, 1), (10_000, 200), (25, 25)])
    def test_limit_is_clamped(self, asked, used):
        seen = {}

        class Spy(FakeIngest):
            def open_failures(self, since=None, limit=200):
                seen["limit"] = limit
                return []

        list_ingest_failures(Spy(), limit=asked, now=NOW)

        assert seen["limit"] == used


class TestResolveLogic:
    def test_dry_run_is_the_default_and_writes_nothing(self):
        source = ingest()

        result = resolve_ingest_failure(source, 1, "u-admin", note="fixed at the sender", now=NOW)

        assert result.status == "would_resolve"
        assert result.dry_run is True
        assert result.failure.raw_name == "Boston Utd"
        assert source.resolve_calls == []

    def test_a_real_close_records_who_and_why(self):
        source = ingest()

        result = resolve_ingest_failure(source, 1, "u-admin", note="fixed at the sender", dry_run=False, now=NOW)

        assert result.status == "resolved"
        assert source.resolve_calls == [(1, "u-admin", "fixed at the sender")]
        assert result.failure.resolution_note == "fixed at the sender"

    def test_closing_twice_is_idempotent(self):
        """ADK's MCP client retries a failed call once; a retry must not re-stamp the row."""
        source = ingest()
        resolve_ingest_failure(source, 1, "u-admin", dry_run=False, now=NOW)

        again = resolve_ingest_failure(source, 1, "someone-else", dry_run=False, now=NOW)

        assert again.status == "already_resolved"
        assert len(source.resolve_calls) == 1

    def test_unknown_id(self):
        assert resolve_ingest_failure(ingest(), 99, "u-admin", dry_run=False).status == "not_found"

    def test_a_failed_read_is_unavailable_and_writes_nothing(self):
        source = ingest()
        source.fail = True

        result = resolve_ingest_failure(source, 1, "u-admin", dry_run=False)

        assert result.status is None
        assert result.error.kind == "unavailable"
        assert source.resolve_calls == []


class TestOverMcp:
    async def test_an_admin_lists_and_resolves(self, make_deps):
        source = ingest()
        async with served(make_deps(), source) as s, s.session("admin") as session:
            listed = await session.call_tool("list_ingest_failures", {})
            preview = await session.call_tool("resolve_ingest_failure", {"failure_id": 1})
            closed = await session.call_tool(
                "resolve_ingest_failure", {"failure_id": 1, "note": "fixed at the sender", "dry_run": False}
            )

        assert [f["raw_name"] for f in listed.structured_content["failures"]] == ["Boston Utd", "IFA Academy"]
        assert preview.structured_content["status"] == "would_resolve"
        assert closed.structured_content["status"] == "resolved"
        # Provenance: the closer is the token's user, never an argument.
        assert source.resolve_calls == [(1, "u-admin", "fixed at the sender")]

    @pytest.mark.parametrize(("token", "client"), [("team-mgr", None), ("fan", None), ("admin", MT_AI_CLIENT)])
    async def test_nobody_else_can_call_them(self, make_deps, token, client):
        source = ingest()
        async with served(make_deps(), source) as s, s.session(token, client) as session:
            listed = await session.call_tool("list_ingest_failures", {})
            closed = await session.call_tool("resolve_ingest_failure", {"failure_id": 1, "dry_run": False})

        assert listed.is_error and listed.content[0].text == "Unknown tool: list_ingest_failures"
        assert closed.is_error
        assert source.resolve_calls == []

    async def test_a_note_over_500_characters_is_rejected(self, make_deps):
        source = ingest()
        async with served(make_deps(), source) as s, s.session("admin") as session:
            result = await session.call_tool(
                "resolve_ingest_failure", {"failure_id": 1, "note": "x" * 501, "dry_run": False}
            )

        assert result.is_error
        assert source.resolve_calls == []

    async def test_outcomes_are_counted(self, make_deps):
        def count(outcome: str) -> float:
            return TOOL_CALLS.labels(
                tool="resolve_ingest_failure", client="none", role="admin", outcome=outcome
            )._value.get()

        before = count("would_resolve")
        async with served(make_deps(), ingest()) as s, s.session("admin") as session:
            await session.call_tool("resolve_ingest_failure", {"failure_id": 1})

        assert count("would_resolve") == before + 1

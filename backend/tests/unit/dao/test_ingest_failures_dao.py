"""IngestFailuresDAO (SB-829).

This DAO runs on the failure path of a task that is already failing. Its one
non-negotiable property is that it cannot make things worse: a diagnostic that
raises turns "one unresolved name" into "one unresolved name plus a confusing
second exception", and the real cause gets harder to find, not easier.
"""

from unittest.mock import MagicMock

import pytest

from dao.ingest_failures_dao import DEFAULT_SOURCE, IngestFailuresDAO

ROW = {"id": 3, "match_count": 1, "should_alert": True}


def _dao(rpc_data=None, rpc_error=None, table_data=None, table_error=None, count=None):
    dao = object.__new__(IngestFailuresDAO)
    dao.connection_holder = MagicMock()
    client = MagicMock()

    rpc = MagicMock()
    rpc.execute.return_value = MagicMock(data=rpc_data)
    if rpc_error:
        rpc.execute.side_effect = rpc_error
    client.rpc.return_value = rpc

    table = MagicMock()
    for method in ("select", "update", "in_", "gte", "is_", "order", "limit"):
        getattr(table, method).return_value = table
    table.execute.return_value = MagicMock(data=table_data, count=count)
    if table_error:
        table.execute.side_effect = table_error
    client.table.return_value = table

    dao.client = client
    dao._rpc, dao._table = rpc, table
    return dao


@pytest.mark.unit
class TestRecord:
    def test_returns_the_row_and_defaults_the_source(self):
        dao = _dao(rpc_data=[ROW])
        assert dao.record("team", "Brand New FC") == ROW
        assert dao.client.rpc.call_args.args[1]["p_source"] == DEFAULT_SOURCE

    def test_passes_league_and_sample_through(self):
        dao = _dao(rpc_data=[ROW])
        dao.record("team", "Brand New FC", league="Flex", source="kitman", sample="A vs B")
        params = dao.client.rpc.call_args.args[1]
        assert params["p_league"] == "Flex"
        assert params["p_sample"] == "A vs B"
        assert params["p_source"] == "kitman"

    def test_an_empty_result_is_none_not_an_index_error(self):
        dao = _dao(rpc_data=[])
        assert dao.record("team", "Brand New FC") is None

    def test_a_database_error_returns_none_rather_than_raising(self):
        # None means "not recorded", and the caller declines to alert on it —
        # alerting on a failure we did not persist would re-alert on the next
        # match, and the next.
        dao = _dao(rpc_error=RuntimeError("relation does not exist"))
        assert dao.record("team", "Brand New FC") is None


@pytest.mark.unit
class TestResolve:
    def test_returns_the_number_of_rows_closed(self):
        dao = _dao(rpc_data=2)
        assert dao.resolve("team", "Brand New FC") == 2

    def test_a_database_error_is_zero_rather_than_raising(self):
        # This runs on the SUCCESS path. It must never turn a good match into
        # a failed task.
        dao = _dao(rpc_error=RuntimeError("db down"))
        assert dao.resolve("team", "Brand New FC") == 0


@pytest.mark.unit
class TestReadsAndMarks:
    def test_open_failures_filters_to_unresolved(self):
        dao = _dao(table_data=[{"id": 1}])
        assert dao.open_failures() == [{"id": 1}]
        dao._table.is_.assert_called_once_with("resolved_at", "null")

    def test_open_failures_applies_the_since_window(self):
        dao = _dao(table_data=[])
        dao.open_failures(since="2026-09-05T00:00:00Z")
        dao._table.gte.assert_called_once_with("last_seen", "2026-09-05T00:00:00Z")

    def test_mark_notified_with_no_ids_touches_nothing(self):
        dao = _dao()
        dao.mark_notified([])
        dao.client.table.assert_not_called()

    def test_notified_since_returns_the_count(self):
        dao = _dao(table_data=[], count=4)
        assert dao.notified_since("2026-09-05T00:00:00Z") == 4

    @pytest.mark.parametrize(
        "call",
        [
            lambda d: d.open_failures(),
            lambda d: d.notified_since("2026-09-05T00:00:00Z"),
            lambda d: d.mark_notified([1, 2]),
        ],
    )
    def test_read_and_write_errors_are_swallowed(self, call):
        dao = _dao(table_error=RuntimeError("db down"))
        call(dao)  # must not raise

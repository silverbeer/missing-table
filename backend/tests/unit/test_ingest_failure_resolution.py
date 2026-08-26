"""Closing an ingest failure that was fixed at the sender (SB-845).

`resolve_ingest_failures` closes a row when the same raw_name later resolves —
add an alias mid-load and the alert clears itself. That is the case it was
designed for, and it is only half of them.

When the fix is to stop *sending* the bad name rather than to teach MT about
it, that string is never submitted again. Nothing triggers the resolve, so the
row stays open forever: reported on every subsequent scraper run as a problem
that no longer exists, and counted in `matches_dropped`. A permanent false
positive in an alerting surface is how people learn to ignore that surface.

Two halves here. A person can close a row, and the decision is recorded rather
than the row deleted — the table's value is the history of which names were
wrong and when. And the API flags rows nobody has seen lately, so a report can
de-emphasise without deciding: absent is not the same as fixed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from dao.ingest_failures_dao import IngestFailuresDAO

OPEN_ROW = {
    "id": 1,
    "kind": "team",
    "raw_name": "IFA HG",
    "league": "Homegrown",
    "match_count": 1,
    "resolved_at": None,
}


def _dao(select_data=None, update_data=None, error=None):
    dao = object.__new__(IngestFailuresDAO)
    dao.connection_holder = MagicMock()
    client = MagicMock()

    select_chain = MagicMock()
    select_chain.eq.return_value = select_chain
    select_chain.execute.return_value = MagicMock(data=select_data)

    update_chain = MagicMock()
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = MagicMock(data=update_data)

    table = MagicMock()
    table.select.return_value = select_chain
    table.update.return_value = update_chain
    if error:
        select_chain.execute.side_effect = error
    client.table.return_value = table

    dao.client = client
    dao._table = table
    dao._update = update_chain
    return dao


@pytest.mark.unit
class TestResolveById:
    def test_it_closes_an_open_row(self):
        resolved = {**OPEN_ROW, "resolved_at": "2026-08-26T22:00:00Z"}
        dao = _dao(select_data=[OPEN_ROW], update_data=[resolved])

        assert dao.resolve_by_id(1)["resolved_at"] is not None

    def test_it_records_who_and_why(self):
        dao = _dao(select_data=[OPEN_ROW], update_data=[OPEN_ROW])
        dao.resolve_by_id(1, resolved_by="user-uuid", note="Fixed at the sender")

        payload = dao._table.update.call_args.args[0]
        assert payload["resolved_by"] == "user-uuid"
        assert payload["resolution_note"] == "Fixed at the sender"

    def test_it_stamps_rather_than_deletes(self):
        """The row is the record of which names were wrong and when."""
        dao = _dao(select_data=[OPEN_ROW], update_data=[OPEN_ROW])
        dao.resolve_by_id(1)

        dao._table.delete.assert_not_called()
        assert "resolved_at" in dao._table.update.call_args.args[0]

    def test_an_unknown_id_is_none_not_a_silent_success(self):
        dao = _dao(select_data=[])
        assert dao.resolve_by_id(999) is None

    def test_an_already_resolved_row_keeps_its_first_decision(self):
        already = {**OPEN_ROW, "resolved_at": "2026-08-20T00:00:00Z", "resolution_note": "alias added"}
        dao = _dao(select_data=[already])

        assert dao.resolve_by_id(1) == already
        dao._table.update.assert_not_called()

    def test_a_database_error_is_none_rather_than_an_exception(self):
        # This DAO sits on the failure path of something already failing.
        dao = _dao(error=RuntimeError("boom"))
        assert dao.resolve_by_id(1) is None


@pytest.mark.unit
class TestStaleness:
    """`stale` is a hint for de-emphasising, never a decision to close.

    A name fixed at the sender and a name that simply was not scraped this week
    look identical from here. Auto-closing the second would lose a real
    problem, which is why only a person may resolve.
    """

    @staticmethod
    def _flag(last_seen, days=7):
        from app import _last_seen_before

        cutoff = datetime.now(UTC) - timedelta(days=days)
        return _last_seen_before(last_seen, cutoff)

    def test_a_row_seen_today_is_fresh(self):
        assert self._flag(datetime.now(UTC).isoformat()) is False

    def test_a_row_unseen_for_a_month_is_stale(self):
        old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        assert self._flag(old) is True

    def test_the_boundary_belongs_to_fresh(self):
        edge = (datetime.now(UTC) - timedelta(days=6, hours=23)).isoformat()
        assert self._flag(edge) is False

    def test_a_zulu_timestamp_is_understood(self):
        old = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert self._flag(old) is True

    def test_a_naive_timestamp_is_read_as_utc(self):
        old = (datetime.now(UTC) - timedelta(days=30)).replace(tzinfo=None).isoformat()
        assert self._flag(old) is True

    def test_an_unparseable_timestamp_reads_as_fresh(self):
        # Erring towards "still a problem" — a row wrongly hidden is worse than
        # a row wrongly shown.
        assert self._flag("not a date") is False

    def test_a_missing_timestamp_reads_as_fresh(self):
        assert self._flag(None) is False


@pytest.mark.unit
class TestStaleWindowConfig:
    def test_it_defaults_to_a_week(self, monkeypatch):
        from app import DEFAULT_INGEST_FAILURE_STALE_AFTER_DAYS, ingest_failure_stale_after_days

        monkeypatch.delenv("MT_INGEST_STALE_AFTER_DAYS", raising=False)
        assert ingest_failure_stale_after_days() == DEFAULT_INGEST_FAILURE_STALE_AFTER_DAYS

    def test_it_is_configurable(self, monkeypatch):
        from app import ingest_failure_stale_after_days

        monkeypatch.setenv("MT_INGEST_STALE_AFTER_DAYS", "30")
        assert ingest_failure_stale_after_days() == 30

    def test_nonsense_falls_back_rather_than_crashing_the_endpoint(self, monkeypatch):
        from app import DEFAULT_INGEST_FAILURE_STALE_AFTER_DAYS, ingest_failure_stale_after_days

        monkeypatch.setenv("MT_INGEST_STALE_AFTER_DAYS", "soon")
        assert ingest_failure_stale_after_days() == DEFAULT_INGEST_FAILURE_STALE_AFTER_DAYS

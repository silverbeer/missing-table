"""Unit tests for TournamentDAO._attach_match_counts (SB-1752).

The count used to be the length of one ``.in_("tournament_id", ids)`` select,
which PostgREST caps at 1,000 rows, so a big tournament under-reported. It is
now one exact-count HEAD query per tournament; the number comes from the
response's ``count``, never from the rows.

The default fixture is a tournament with scraped matches and no user data.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.backend]


class _Query:
    """Records the filter chain for one tournament's count query."""

    def __init__(self, result):
        self.select_args = None
        self.select_kwargs = None
        self.filters = []
        self._result = result

    def select(self, *args, **kwargs):
        self.select_args, self.select_kwargs = args, kwargs
        return self

    def eq(self, col, val):
        self.filters.append((col, val))
        return self

    def execute(self):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _response(count, data=None):
    r = MagicMock()
    r.count = count
    r.data = data if data is not None else []
    return r


@pytest.fixture
def dao():
    from dao.tournament_dao import TournamentDAO

    d = TournamentDAO.__new__(TournamentDAO)
    d.connection_holder = MagicMock()
    d.client = MagicMock()
    return d


def _wire(dao, results_by_tid):
    """Make client.table() hand back one recorded query per tournament, in call order."""
    queries = [_Query(r) for r in results_by_tid]
    dao.client.table.side_effect = queries
    return queries


class TestAttachMatchCounts:
    def test_empty_list_makes_no_query(self, dao):
        assert dao._attach_match_counts([]) == []
        dao.client.table.assert_not_called()

    def test_count_comes_from_exact_count_not_row_length(self, dao):
        # A HEAD request returns no rows; even if rows came back, the count wins.
        queries = _wire(dao, [_response(1437, data=[{"id": 1}] * 3)])

        out = dao._attach_match_counts([{"id": 7}])

        assert out[0]["match_count"] == 1437
        assert queries[0].select_kwargs == {"count": "exact", "head": True}

    def test_counts_above_the_postgrest_row_cap(self, dao):
        _wire(dao, [_response(25000)])
        assert dao._attach_match_counts([{"id": 7}])[0]["match_count"] == 25000

    def test_one_query_per_tournament_scoped_by_tournament_id(self, dao):
        queries = _wire(dao, [_response(5), _response(9)])

        out = dao._attach_match_counts([{"id": 7}, {"id": 8}])

        assert [t["match_count"] for t in out] == [5, 9]
        assert ("tournament_id", 7) in queries[0].filters
        assert ("tournament_id", 8) in queries[1].filters

    def test_tournament_with_no_matches_is_zero_not_none(self, dao):
        # The scraper/user created a tournament with nothing in it yet: 200 with 0.
        _wire(dao, [_response(0)])
        assert dao._attach_match_counts([{"id": 7}])[0]["match_count"] == 0

    def test_missing_count_attribute_is_zero(self, dao):
        _wire(dao, [_response(None)])
        assert dao._attach_match_counts([{"id": 7}])[0]["match_count"] == 0

    def test_test_partition_filter_applied_by_default(self, dao):
        queries = _wire(dao, [_response(3)])
        dao._attach_match_counts([{"id": 7}])
        assert ("is_test", False) in queries[0].filters

    def test_include_test_drops_the_filter(self, dao):
        queries = _wire(dao, [_response(3)])
        dao._attach_match_counts([{"id": 7}], include_test=True)
        assert all(col != "is_test" for col, _ in queries[0].filters)

    def test_reads_the_matches_read_relation(self, dao):
        from dao.base_dao import MATCHES_READ_RELATION

        _wire(dao, [_response(1)])
        dao._attach_match_counts([{"id": 7}])
        dao.client.table.assert_called_once_with(MATCHES_READ_RELATION)

    def test_one_failed_count_does_not_zero_the_others(self, dao):
        _wire(dao, [_response(11), RuntimeError("boom"), _response(22)])

        out = dao._attach_match_counts([{"id": 1}, {"id": 2}, {"id": 3}])

        assert [t["match_count"] for t in out] == [11, 0, 22]

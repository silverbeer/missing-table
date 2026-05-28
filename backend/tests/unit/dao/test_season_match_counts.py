"""Unit tests for SeasonDAO.get_match_counts_by_season (SB-61).

Uses a mocked Supabase client. The DAO's value is the data-shape parsing of
PostgREST's embedded-count response + the N+1 fallback when the embedded
path fails.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dao.season_dao import SeasonDAO

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]


def _make_dao() -> tuple[SeasonDAO, MagicMock]:
    """Build a SeasonDAO whose `client.table(...)` is a chainable mock."""
    client_mock = MagicMock()
    connection_holder = MagicMock()
    connection_holder.get_client.return_value = client_mock

    dao = SeasonDAO.__new__(SeasonDAO)
    dao.connection_holder = connection_holder
    dao.client = client_mock
    return dao, client_mock


class TestEmbeddedCountPath:
    def test_parses_postgrest_embedded_count_into_flat_rows(self):
        dao, client = _make_dao()
        client.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[
                {"id": 1, "matches": [{"count": 1437}]},
                {"id": 2, "matches": [{"count": 980}]},
                {"id": 3, "matches": [{"count": 0}]},
            ]
        )

        counts = dao.get_match_counts_by_season()

        assert counts == [
            {"season_id": 1, "match_count": 1437},
            {"season_id": 2, "match_count": 980},
            {"season_id": 3, "match_count": 0},
        ]
        client.table.assert_called_with("seasons")

    def test_treats_missing_matches_array_as_zero(self):
        dao, client = _make_dao()
        client.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[
                {"id": 1, "matches": []},
                {"id": 2},  # field omitted entirely
                {"id": 3, "matches": [{}]},  # count missing on the inner dict
            ]
        )

        counts = dao.get_match_counts_by_season()

        assert counts == [
            {"season_id": 1, "match_count": 0},
            {"season_id": 2, "match_count": 0},
            {"season_id": 3, "match_count": 0},
        ]

    def test_empty_response_returns_empty_list(self):
        dao, client = _make_dao()
        client.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[]
        )

        assert dao.get_match_counts_by_season() == []


class TestFallbackPath:
    def test_falls_back_to_per_season_count_when_embedded_fails(self):
        dao, client = _make_dao()

        # First call: seasons.select("id, matches(count)").execute() raises.
        # Second call: seasons.select("id").execute() returns the season list.
        # Third+: matches.select("id", count="exact")... returns per-season counts.
        seasons_select = MagicMock()
        seasons_select.execute.side_effect = [
            RuntimeError("embedded count not supported"),  # primary path fails
            MagicMock(data=[{"id": 1}, {"id": 2}]),  # fallback fetches seasons
        ]

        per_season_calls = []

        def matches_table_side_effect(name):
            if name == "seasons":
                client.table.side_effect = None  # only first call uses this side_effect
                return MagicMock(select=MagicMock(return_value=seasons_select))
            if name == "matches":
                m = MagicMock()
                # .select("id", count="exact").eq("season_id", N).limit(0).execute()
                eq_chain = MagicMock()
                count_result = MagicMock()
                count_result.count = 100 + len(per_season_calls)
                per_season_calls.append(count_result.count)
                eq_chain.limit.return_value.execute.return_value = count_result
                m.select.return_value.eq.return_value = eq_chain
                return m
            return MagicMock()

        # First call to client.table is for the embedded path.
        primary_select = MagicMock()
        primary_select.execute.side_effect = RuntimeError("embedded count not supported")
        client.table.return_value.select.return_value = primary_select

        # Reset table side effects for the fallback so each table() call returns the right mock.
        seasons_after_fallback = MagicMock()
        seasons_after_fallback.select.return_value.execute.return_value = MagicMock(
            data=[{"id": 1}, {"id": 2}]
        )

        matches_mock_1 = MagicMock()
        c1 = MagicMock()
        c1.count = 1437
        matches_mock_1.select.return_value.eq.return_value.limit.return_value.execute.return_value = c1

        matches_mock_2 = MagicMock()
        c2 = MagicMock()
        c2.count = 980
        matches_mock_2.select.return_value.eq.return_value.limit.return_value.execute.return_value = c2

        # client.table call sequence:
        # 1. table("seasons") for the embedded path (raises on execute)
        # 2. table("seasons") for the fallback list
        # 3. table("matches") for season 1's count
        # 4. table("matches") for season 2's count
        first_seasons = MagicMock()
        first_seasons.select.return_value.execute.side_effect = RuntimeError("nope")

        client.table.side_effect = [
            first_seasons,
            seasons_after_fallback,
            matches_mock_1,
            matches_mock_2,
        ]

        counts = dao.get_match_counts_by_season()

        assert counts == [
            {"season_id": 1, "match_count": 1437},
            {"season_id": 2, "match_count": 980},
        ]

    def test_returns_empty_list_if_both_paths_fail(self):
        dao, client = _make_dao()
        # Embedded path raises; fallback seasons select also raises.
        first_seasons = MagicMock()
        first_seasons.select.return_value.execute.side_effect = RuntimeError("a")
        fallback_seasons = MagicMock()
        fallback_seasons.select.return_value.execute.side_effect = RuntimeError("b")
        client.table.side_effect = [first_seasons, fallback_seasons]

        assert dao.get_match_counts_by_season() == []

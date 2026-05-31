"""Regression tests for SB-72: match writes must bust the tournament cache.

The bracket view reads `GET /api/tournaments/{id}` → `get_tournament_by_id`,
cached under `mt:dao:tournaments:by_id:{id}`. Several match-write methods
(`create_match`, `add_match`, `add_match_with_external_id`,
`update_match_external_id`) previously invalidated only `mt:dao:matches:*`, so
creating/relinking a tournament match left the bracket cache stale until a
`redis-cli FLUSHDB`. These assert each now also clears the tournaments pattern.

The `@invalidates_cache` decorator calls `clear_cache(pattern)` per pattern
after the method returns, so patching `clear_cache` lets us assert invalidation
with a mocked Supabase client (no DB, no Redis).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dao.match_dao import TOURNAMENTS_CACHE_PATTERN, MatchDAO

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]


def _make_dao() -> MatchDAO:
    """MatchDAO with a chainable mock client whose writes return a row."""
    client = MagicMock()
    holder = MagicMock()
    holder.get_client.return_value = client
    dao = MatchDAO.__new__(MatchDAO)
    dao.connection_holder = holder
    dao.client = client
    # Any insert/update .execute() returns a single fake row so the methods
    # take their success path.
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": 1}]
    )
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": 1}]
    )
    return dao


class TestTournamentCacheInvalidation:
    def test_create_match_busts_tournament_cache(self):
        dao = _make_dao()
        with patch("dao.base_dao.clear_cache") as clear_cache:
            dao.create_match(
                home_team_id=1, away_team_id=2, match_date="2026-05-30", season_id=3
            )
        clear_cache.assert_any_call(TOURNAMENTS_CACHE_PATTERN)

    def test_add_match_busts_tournament_cache(self):
        dao = _make_dao()
        with patch("dao.base_dao.clear_cache") as clear_cache:
            dao.add_match(
                home_team_id=1,
                away_team_id=2,
                match_date="2026-05-30",
                home_score=0,
                away_score=0,
                season_id=3,
                age_group_id=2,
                match_type_id=2,
            )
        clear_cache.assert_any_call(TOURNAMENTS_CACHE_PATTERN)

    def test_update_match_external_id_busts_tournament_cache(self):
        dao = _make_dao()
        with patch("dao.base_dao.clear_cache") as clear_cache:
            dao.update_match_external_id(1, "ext-123")
        clear_cache.assert_any_call(TOURNAMENTS_CACHE_PATTERN)

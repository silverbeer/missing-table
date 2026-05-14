"""
Unit tests for Redis caching of QoP rankings endpoints (SB-12).

Covers:
- GET /api/qop-rankings cache hit → DAO not invoked
- GET cache miss with data → DAO invoked, cache_set called with correct key + TTL
- GET cache miss with no data (has_data=False) → cache_set NOT called
- GET with explicit snapshot_id → cache key includes snapshot_id
- POST /api/qop-rankings status=inserted → clear_cache called
- POST status=unchanged → clear_cache NOT called
- Admin DELETE /api/admin/cache/{cache_type} accepts "qop"
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.unit
class TestGetQoPRankingsCache:
    """Cache wiring on GET /api/qop-rankings."""

    def test_cache_hit_returns_cached_without_dao_call(self):
        cached_payload = {"has_data": True, "week_of": "2026-04-18", "rankings": []}
        with patch("dao.base_dao.cache_get", return_value=cached_payload) as mock_get, \
             patch("dao.base_dao.cache_set") as mock_set, \
             patch("dao.qop_rankings_dao.QoPRankingsDAO.get_with_delta") as mock_dao:
            from app import get_qop_rankings

            result = _run(get_qop_rankings(division_id=10, age_group_id=20, snapshot_id=None))

            assert result is cached_payload
            mock_get.assert_called_once_with("mt:dao:qop:10:20")
            mock_dao.assert_not_called()
            mock_set.assert_not_called()

    def test_cache_miss_calls_dao_and_caches_result(self):
        dao_result = {"has_data": True, "week_of": "2026-04-18", "rankings": [{"rank": 1}]}
        with patch("dao.base_dao.cache_get", return_value=None), \
             patch("dao.base_dao.cache_set") as mock_set, \
             patch("dao.qop_rankings_dao.QoPRankingsDAO.get_with_delta", return_value=dao_result) as mock_dao:
            from app import get_qop_rankings

            result = _run(get_qop_rankings(division_id=10, age_group_id=20, snapshot_id=None))

            assert result == dao_result
            mock_dao.assert_called_once()
            mock_set.assert_called_once_with("mt:dao:qop:10:20", dao_result, ttl=3600)

    def test_cache_miss_with_no_data_does_not_cache(self):
        dao_result = {"has_data": False, "week_of": None, "rankings": []}
        with patch("dao.base_dao.cache_get", return_value=None), \
             patch("dao.base_dao.cache_set") as mock_set, \
             patch("dao.qop_rankings_dao.QoPRankingsDAO.get_with_delta", return_value=dao_result):
            from app import get_qop_rankings

            result = _run(get_qop_rankings(division_id=10, age_group_id=20, snapshot_id=None))

            assert result == dao_result
            mock_set.assert_not_called()

    def test_explicit_snapshot_id_in_cache_key(self):
        cached_payload = {"has_data": True, "rankings": []}
        with patch("dao.base_dao.cache_get", return_value=cached_payload) as mock_get, \
             patch("dao.qop_rankings_dao.QoPRankingsDAO.get_with_delta"):
            from app import get_qop_rankings

            _run(get_qop_rankings(division_id=10, age_group_id=20, snapshot_id=42))

            mock_get.assert_called_once_with("mt:dao:qop:10:20:42")


@pytest.mark.unit
class TestIngestQoPRankingsInvalidation:
    """Cache invalidation on POST /api/qop-rankings."""

    @staticmethod
    def _payload():
        return MagicMock(
            model_dump=MagicMock(
                return_value={
                    "detected_at": "2026-04-18",
                    "division": "Northeast",
                    "age_group": "U14",
                    "rankings": [],
                }
            )
        )

    def test_inserted_triggers_cache_clear(self):
        with patch("dao.base_dao.clear_cache") as mock_clear, \
             patch(
                 "dao.qop_rankings_dao.QoPRankingsDAO.record_snapshot",
                 return_value={"status": "inserted", "snapshot_id": 99, "rankings_count": 5},
             ):
            from app import ingest_qop_rankings

            _run(ingest_qop_rankings(self._payload(), current_user={"username": "admin"}))

            mock_clear.assert_called_once_with("mt:dao:qop:*")

    def test_unchanged_skips_cache_clear(self):
        with patch("dao.base_dao.clear_cache") as mock_clear, \
             patch(
                 "dao.qop_rankings_dao.QoPRankingsDAO.record_snapshot",
                 return_value={"status": "unchanged", "snapshot_id": 99, "rankings_count": 0},
             ):
            from app import ingest_qop_rankings

            _run(ingest_qop_rankings(self._payload(), current_user={"username": "admin"}))

            mock_clear.assert_not_called()


@pytest.mark.unit
class TestAdminCacheTypeQoP:
    """qop is accepted as a cache type to clear via the admin endpoint."""

    def test_qop_is_valid_cache_type(self):
        with patch("dao.base_dao.clear_cache", return_value=3) as mock_clear:
            from app import clear_cache_by_type

            result = _run(
                clear_cache_by_type(cache_type="qop", current_user={"username": "admin"})
            )

            mock_clear.assert_called_once_with("mt:dao:qop:*")
            assert result["deleted"] == 3
            assert "qop" in result["message"]

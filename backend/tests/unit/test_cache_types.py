"""SB-1278: every cache namespace the code writes can be cleared on its own.

GET /api/admin/cache groups keys by the first segment after `mt:dao:`, and
DELETE /api/admin/cache/{type} only clears names in CACHE_TYPES. The old
hand-kept list had drifted: most groups the admin view showed could only be
cleared by clearing everything, and "rosters" never matched the DAO's
"roster" keys. These tests derive the namespaces from the source so the list
cannot drift again.
"""

import asyncio
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from dao.base_dao import CACHE_TYPE_ALIASES, CACHE_TYPES

BACKEND = Path(__file__).resolve().parents[2]

# @dao_cache("teams:all") — the decorator prepends mt:dao: itself.
DAO_CACHE = re.compile(r'@dao_cache\(\s*f?"([a-z_]+):')
# Literal keys and invalidation patterns: "mt:dao:roster:*", f"mt:dao:qop:{...}".
LITERAL_KEY = re.compile(r'"mt:dao:([a-z_]+):')


def _written_namespaces() -> set[str]:
    found = set()
    for path in BACKEND.rglob("*.py"):
        rel = path.relative_to(BACKEND).parts
        if rel[0] in {".venv", "tests"}:
            continue
        source = path.read_text()
        found.update(DAO_CACHE.findall(source))
        found.update(LITERAL_KEY.findall(source))
    return found


def _clear(cache_type):
    from app import clear_cache_by_type

    return asyncio.run(clear_cache_by_type(cache_type=cache_type, current_user={"username": "admin"}))


@pytest.mark.unit
class TestCacheTypesMatchTheSource:
    def test_scan_finds_the_namespaces(self):
        """Guard the guard: a broken regex would make the next test pass vacuously."""
        assert {"teams", "roster", "qop", "stats"} <= _written_namespaces()

    def test_every_written_namespace_is_clearable(self):
        missing = _written_namespaces() - CACHE_TYPES
        assert not missing, f"cache namespaces written but not in CACHE_TYPES: {sorted(missing)}"

    def test_no_listed_namespace_is_dead(self):
        dead = CACHE_TYPES - _written_namespaces()
        assert not dead, f"CACHE_TYPES lists namespaces nothing writes: {sorted(dead)}"

    def test_aliases_point_into_real_namespaces(self):
        for alias, prefix in CACHE_TYPE_ALIASES.items():
            assert alias not in CACHE_TYPES
            assert prefix.split(":")[0] in CACHE_TYPES


@pytest.mark.unit
class TestClearCacheByType:
    @pytest.mark.parametrize("cache_type", sorted(CACHE_TYPES))
    def test_each_type_clears_its_own_namespace(self, cache_type):
        with patch("dao.base_dao.clear_cache", return_value=2) as mock_clear:
            result = _clear(cache_type)

        mock_clear.assert_called_once_with(f"mt:dao:{cache_type}:*")
        assert result["deleted"] == 2

    def test_rosters_clears_the_roster_keys(self):
        with patch("dao.base_dao.clear_cache", return_value=1) as mock_clear:
            _clear("rosters")

        mock_clear.assert_called_once_with("mt:dao:roster:*")

    def test_standings_clears_the_standings_keys_under_matches(self):
        with patch("dao.base_dao.clear_cache", return_value=1) as mock_clear:
            _clear("standings")

        mock_clear.assert_called_once_with("mt:dao:matches:standings:*")

    @pytest.mark.parametrize("cache_type", ["*", "teams:*", "nope", "matches:standings"])
    def test_unknown_type_is_rejected_before_touching_redis(self, cache_type):
        with patch("dao.base_dao.clear_cache") as mock_clear, pytest.raises(HTTPException) as exc:
            _clear(cache_type)

        assert exc.value.status_code == 400
        mock_clear.assert_not_called()

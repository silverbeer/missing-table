"""An in-memory stand-in for the sync Redis client the DAO cache uses.

Covers exactly what ``dao.base_dao`` calls — ``setex``, ``get``, ``scan``,
``delete``, ``ping`` — with a clock the test moves by hand, so a TTL can be
crossed without sleeping. Patch it in where ``dao.base_dao`` gets its client:

    with patch("dao.base_dao.get_redis_client", return_value=FakeRedis()):
        ...

Patching the lookup, not the environment, is what keeps a test off a real
Redis even when the developer's shell has ``CACHE_ENABLED=true``.
"""

from __future__ import annotations

from fnmatch import fnmatchcase


class FakeRedis:
    """Keys with expiry, and a clock that only moves when told to."""

    def __init__(self):
        self.now = 0.0
        self._store: dict[str, tuple[str, float]] = {}
        # Every (key, ttl) written, in order — for asserting on the TTL used.
        self.writes: list[tuple[str, int]] = []

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def _live(self, key: str) -> bool:
        entry = self._store.get(key)
        if entry is None:
            return False
        # Redis expires a key once its TTL has fully elapsed.
        if self.now >= entry[1]:
            del self._store[key]
            return False
        return True

    def ping(self) -> bool:
        return True

    def setex(self, key: str, ttl: int, value: str) -> bool:
        self._store[key] = (value, self.now + ttl)
        self.writes.append((key, ttl))
        return True

    def get(self, key: str) -> str | None:
        return self._store[key][0] if self._live(key) else None

    def keys(self) -> list[str]:
        return [key for key in list(self._store) if self._live(key)]

    def scan(self, cursor: int = 0, match: str | None = None, count: int | None = None):
        found = [key for key in self.keys() if match is None or fnmatchcase(key, match)]
        return 0, found

    def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if self._live(key):
                del self._store[key]
                deleted += 1
        return deleted

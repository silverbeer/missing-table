"""Scraped tournament scores reach the page without a cache clear (SB-1756).

The ingest worker cannot clear the API's cache: it runs without CACHE_ENABLED
or REDIS_URL, in a different cluster from the API's Redis, so
``@invalidates_cache`` does nothing there. The score-bearing tournament reads
are bounded by a 60-second TTL instead.

Two things are pinned here:

- the TTL each read is stored with — and that ``tournaments:age_groups``, which
  does not depend on matches, keeps the 24-hour default;
- the behaviour: a cached read still shows the old score inside the TTL (so
  the cache in the test is real) and the new one after it, with nothing
  cleared in between.

Reads pass every argument in the cache key, as the API does: ``@dao_cache``
skips caching when a keyed argument is left to its default.

No database and no Redis: an in-memory Supabase stand-in holds the rows, and
``FakeRedis`` is patched in where ``dao.base_dao`` gets its client, so a
developer's ``CACHE_ENABLED=true`` cannot send this at a real one.

The default fixture is scraped matches with no user data: a match without a
score is ``None``, not 0.
"""

from __future__ import annotations

import copy
from unittest.mock import MagicMock, patch

import pytest

from dao.match_dao import MatchDAO
from dao.tournament_dao import TOURNAMENT_PAGE_CACHE_TTL, TOURNAMENT_SCORE_CACHE_TTL, TournamentDAO
from tests.utils.fake_redis import FakeRedis

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]

DEFAULT_TTL = 86400
TOURNAMENT_ID = 6
SEASON_ID = 3


class _Query:
    """One PostgREST chain over the in-memory rows — only what these reads use."""

    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filters: list = []
        self._update: dict | None = None
        self._count = False
        self._head = False
        self._single = False

    def select(self, *_columns, count=None, head=False):
        self._count, self._head = count == "exact", head
        return self

    def update(self, values: dict):
        self._update = values
        return self

    def eq(self, column, value):
        self._filters.append(lambda row: row.get(column) == value)
        return self

    def in_(self, column, values):
        self._filters.append(lambda row: row.get(column) in values)
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, _n):
        return self

    def single(self):
        self._single = True
        return self

    def execute(self):
        matched = [row for row in self._rows if all(f(row) for f in self._filters)]
        if self._update is not None:
            for row in matched:
                row.update(self._update)
        response = MagicMock()
        response.count = len(matched) if self._count else None
        # Copies, as from the wire: the DAO reshapes what it is handed.
        data = [] if self._head else copy.deepcopy(matched)
        response.data = (data[0] if data else None) if self._single else data
        return response


class _Supabase:
    """Tables as lists of dicts. ``matches_with_test`` is a view of ``matches``."""

    def __init__(self):
        self.tables: dict[str, list[dict]] = {
            "tournaments": [
                {
                    "id": TOURNAMENT_ID,
                    "name": "Fest",
                    "season_id": SEASON_ID,
                    "start_date": "2026-12-02",
                    "end_date": None,
                    "location": None,
                    "description": None,
                    "is_active": True,
                    "is_test": False,
                    "logo_url": None,
                }
            ],
            "tournament_age_groups": [{"tournament_id": TOURNAMENT_ID, "age_group": {"id": 5, "name": "U13"}}],
            "matches": [_scraped_match(1)],
        }

    def table(self, name: str) -> _Query:
        return _Query(self.tables["matches" if name == "matches_with_test" else name])


def _scraped_match(match_id: int) -> dict:
    """A scraped fixture before kickoff: no score, no user data."""
    return {
        "id": match_id,
        "tournament_id": TOURNAMENT_ID,
        "is_test": False,
        "match_date": "2026-12-04",
        "match_status": "scheduled",
        "home_score": None,
        "away_score": None,
        "home_team": {"id": 1, "name": "Home", "club": None},
        "away_team": {"id": 2, "name": "Away", "club": None},
    }


def _dao(cls, supabase: _Supabase):
    dao = cls.__new__(cls)
    dao.connection_holder = MagicMock()
    dao.client = supabase
    return dao


@pytest.fixture
def supabase():
    return _Supabase()


@pytest.fixture
def tournaments(supabase):
    return _dao(TournamentDAO, supabase)


class TestScoreBearingReadsUseTheShortTtl:
    """What each read is stored with."""

    @pytest.fixture
    def stored(self):
        with patch("dao.base_dao.cache_get", return_value=None), patch("dao.base_dao.cache_set") as put:
            yield put

    def test_the_ttl_is_sixty_seconds_and_the_pages_share_it(self):
        assert TOURNAMENT_SCORE_CACHE_TTL == 60
        assert TOURNAMENT_PAGE_CACHE_TTL == TOURNAMENT_SCORE_CACHE_TTL

    def test_the_active_list_is_stored_for_sixty_seconds(self, tournaments, stored):
        result = tournaments.get_active_tournaments(include_test=False, season_id=SEASON_ID)

        stored.assert_called_once_with(f"mt:dao:tournaments:active:False:{SEASON_ID}", result, 60)

    def test_the_admin_list_is_stored_for_sixty_seconds(self, tournaments, stored):
        result = tournaments.get_all_tournaments()

        stored.assert_called_once_with("mt:dao:tournaments:all", result, 60)

    def test_the_detail_is_stored_for_sixty_seconds(self, tournaments, stored):
        result = tournaments.get_tournament_by_id(TOURNAMENT_ID, include_test=False)

        stored.assert_called_once_with(f"mt:dao:tournaments:by_id:{TOURNAMENT_ID}:testFalse", result, 60)

    def test_age_groups_keep_the_default_they_do_not_depend_on_matches(self, tournaments, stored):
        result = tournaments.get_tournament_age_groups(TOURNAMENT_ID)

        stored.assert_called_once_with(f"mt:dao:tournaments:age_groups:{TOURNAMENT_ID}", result, DEFAULT_TTL)


class TestACachedReadChangesAfterAnIngestWrite:
    """The acceptance proof: old inside the TTL, new after it, nothing cleared."""

    @pytest.fixture
    def redis(self):
        # Replaces the lookup itself, so no real client is ever built —
        # whatever CACHE_ENABLED and REDIS_URL say in this shell.
        fake = FakeRedis()
        with patch("dao.base_dao.get_redis_client", return_value=fake):
            yield fake

    @staticmethod
    def _worker_writes_score(supabase):
        """The ingest worker's write: the real DAO method, with no cache to clear."""
        with patch("dao.base_dao.get_redis_client", return_value=None):
            written = _dao(MatchDAO, supabase).update_ingested_tournament_match(
                1, {"home_score": 2, "away_score": 1, "match_status": "completed"}
            )
        assert written

    @staticmethod
    def _score(tournament: dict) -> tuple:
        match = tournament["matches"][0]
        return match["home_score"], match["away_score"]

    def test_a_score_the_worker_files_shows_once_the_ttl_has_passed(self, tournaments, supabase, redis):
        before = tournaments.get_tournament_by_id(TOURNAMENT_ID, include_test=False)
        assert self._score(before) == (None, None)  # unplayed is absent, not 0-0

        self._worker_writes_score(supabase)
        assert redis.keys() == [f"mt:dao:tournaments:by_id:{TOURNAMENT_ID}:testFalse"]  # the write cleared nothing

        redis.advance(TOURNAMENT_SCORE_CACHE_TTL - 1)
        assert self._score(tournaments.get_tournament_by_id(TOURNAMENT_ID, include_test=False)) == (None, None)

        redis.advance(1)
        after = tournaments.get_tournament_by_id(TOURNAMENT_ID, include_test=False)
        assert self._score(after) == (2, 1)
        assert after["matches"][0]["match_status"] == "completed"

    def test_a_match_the_worker_creates_is_counted_once_the_ttl_has_passed(self, tournaments, supabase, redis):
        def count():
            return tournaments.get_active_tournaments(include_test=False, season_id=SEASON_ID)[0]["match_count"]

        assert count() == 1

        # A row created behind the cache, which is all a worker insert is to
        # the API: nothing cleared.
        supabase.tables["matches"].append(_scraped_match(2))

        redis.advance(TOURNAMENT_SCORE_CACHE_TTL - 1)
        assert count() == 1

        redis.advance(1)
        assert count() == 2

    def test_the_admin_list_count_catches_up_too(self, tournaments, supabase, redis):
        assert tournaments.get_all_tournaments()[0]["match_count"] == 1

        supabase.tables["matches"].append(_scraped_match(2))

        redis.advance(TOURNAMENT_SCORE_CACHE_TTL - 1)
        assert tournaments.get_all_tournaments()[0]["match_count"] == 1

        redis.advance(1)
        assert tournaments.get_all_tournaments()[0]["match_count"] == 2

    def test_a_writer_that_shares_the_cache_still_clears_it_at_once(self, tournaments, supabase, redis):
        # The API's own writes: same method, cache reachable, no wait.
        tournaments.get_tournament_by_id(TOURNAMENT_ID, include_test=False)

        _dao(MatchDAO, supabase).update_ingested_tournament_match(1, {"home_score": 2, "away_score": 1})

        assert self._score(tournaments.get_tournament_by_id(TOURNAMENT_ID, include_test=False)) == (2, 1)

    def test_every_tournament_read_was_stored_with_the_short_ttl(self, tournaments, redis):
        tournaments.get_tournament_by_id(TOURNAMENT_ID, include_test=False)
        tournaments.get_active_tournaments(include_test=False, season_id=SEASON_ID)
        tournaments.get_all_tournaments()

        assert [ttl for _, ttl in redis.writes] == [60, 60, 60]

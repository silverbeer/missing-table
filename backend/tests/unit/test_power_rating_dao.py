"""MT Power Rating storage (SB-1807): the gatherer, the fingerprint, the rows, the writes.

The gatherer and row builders are pure and tested on plain dicts. `write_run`
runs against a small in-memory stand-in for the Supabase client, so "deltas for
the latest run only" is checked on what is left in the tables.

The default fixture is the common case: scraped results and nothing else.
"""

from datetime import UTC, date, datetime
from itertools import count

import pytest

from dao.power_rating_dao import (
    NO_SCORE,
    OTHER_AGE_GROUP,
    Gathered,
    PowerRatingDAO,
    delta_rows,
    fingerprint,
    matches_excluded,
    rating_rows,
    run_row,
    to_rated_matches,
)
from mt_tools.power_rating import PARAMS_VERSION, MasseyResult, RatedMatch, massey, rate

pytestmark = [pytest.mark.unit, pytest.mark.backend]

U17 = 5
U19 = 7
HOMEGROWN = 1
FLEX = 290
NORTHEAST = 11
SOUTHEAST = 12


def row(mid, home, away, hs=1, as_=0, *, kind="League", league=HOMEGROWN, division="Northeast", **kw) -> dict:
    """A played match in get_season_results' flat shape, at U17."""
    division_id = {"Northeast": NORTHEAST, "Southeast": SOUTHEAST}.get(division, 300)
    return {
        "id": mid,
        "match_date": f"2026-09-{mid % 28 + 1:02d}",
        "scheduled_kickoff": None,
        "home_team_id": home,
        "away_team_id": away,
        "home_score": hs,
        "away_score": as_,
        "home_penalty_score": None,
        "away_penalty_score": None,
        "age_group_id": U17,
        "home_age_group_id": None,
        "away_age_group_id": None,
        "match_type_name": kind,
        "league_id": league,
        "division_id": division_id,
        "division_name": division,
        "match_status": "completed",
        **kw,
    }


def tournament(mid, home, away, hs=1, as_=0, **kw) -> dict:
    return {
        **row(mid, home, away, hs, as_, kind="Tournament", league=None, division=None),
        "division_id": None,
        "tournament_id": 6,
        **kw,
    }


def by_id(gathered: Gathered) -> dict[int, RatedMatch]:
    return {m.match_id: m for m in gathered.matches}


# --- the gatherer --------------------------------------------------------------------


class TestGatherer:
    def test_league_match_carries_its_conference_and_is_not_neutral(self):
        m = by_id(to_rated_matches([row(1, 10, 20)], U17, HOMEGROWN))[1]
        assert (m.competition, m.conference, m.neutral, m.forfeit) == ("league", "Northeast", False, False)
        assert m.home_in_pool and m.away_in_pool
        assert m.match_date == date(2026, 9, 2)

    def test_flex_is_included_with_no_conference(self):
        rows = [row(1, 10, 20), row(2, 30, 40, division="Southeast"), row(3, 10, 30, kind="Flex", league=FLEX)]
        m = by_id(to_rated_matches(rows, U17, HOMEGROWN))[3]
        assert (m.competition, m.conference, m.neutral) == ("flex", None, False)
        assert m.home_in_pool and m.away_in_pool

    def test_tournament_is_neutral(self):
        rows = [row(1, 10, 20), tournament(2, 10, 20)]
        m = by_id(to_rated_matches(rows, U17, HOMEGROWN))[2]
        assert (m.competition, m.neutral, m.conference) == ("tournament", True, None)
        assert m.is_neutral

    def test_a_match_read_by_both_reads_is_taken_once_as_a_tournament_match(self):
        rows = [row(1, 10, 20), row(2, 10, 20), tournament(2, 10, 20)]
        gathered = to_rated_matches(rows, U17, HOMEGROWN)
        assert [m.match_id for m in gathered.matches] == [1, 2]
        assert by_id(gathered)[2].competition == "tournament"

    def test_forfeit_is_passed_flagged_so_the_engine_counts_it(self):
        rows = [row(1, 10, 20), row(2, 10, 20, hs=None, as_=None, match_status="forfeit")]
        gathered = to_rated_matches(rows, U17, HOMEGROWN)
        assert by_id(gathered)[2].forfeit
        assert rate(gathered.matches).matches_excluded["forfeit"] == 1

    def test_a_flex_only_academy_side_is_out_of_pool(self):
        # 99 plays Flex but has no Homegrown conference at U17.
        rows = [row(1, 10, 20), row(2, 10, 99, kind="Flex", league=FLEX)]
        m = by_id(to_rated_matches(rows, U17, HOMEGROWN))[2]
        assert m.home_in_pool and not m.away_in_pool
        assert rate(to_rated_matches(rows, U17, HOMEGROWN).matches).matches_excluded["out_of_pool_opponent"] == 1

    def test_a_scheduled_league_fixture_puts_a_team_in_pool_and_is_not_rated(self):
        # Early season: 30 has not played a League match yet, but has a conference.
        rows = [
            row(1, 10, 20),
            row(2, 30, 40, hs=None, as_=None, match_status="scheduled"),
            row(3, 10, 30, kind="Flex", league=FLEX),
        ]
        gathered = to_rated_matches(rows, U17, HOMEGROWN)
        assert [m.match_id for m in gathered.matches] == [1, 3]
        assert by_id(gathered)[3].away_in_pool
        assert gathered.no_score == 0  # a scheduled match is not a missing score

    def test_a_tournament_guest_is_out_of_pool(self):
        rows = [row(1, 10, 20), tournament(2, 10, 500)]
        assert not by_id(to_rated_matches(rows, U17, HOMEGROWN))[2].away_in_pool

    def test_a_league_match_in_another_league_gives_no_pool_membership(self):
        rows = [row(1, 10, 20), row(2, 30, 40, league=2, division="Academy NE")]
        gathered = to_rated_matches(rows, U17, HOMEGROWN)
        m = by_id(gathered)[2]
        assert not (m.home_in_pool or m.away_in_pool)
        assert m.conference is None

    def test_a_play_up_is_excluded_and_counted(self):
        # 10 fielded its U17 side against 20's U19 side: not a U17 match.
        rows = [row(1, 10, 20), row(2, 10, 20, away_age_group_id=U19)]
        gathered = to_rated_matches(rows, U17, HOMEGROWN)
        assert [m.match_id for m in gathered.matches] == [1]
        assert gathered.other_age_group == 1

    def test_a_side_playing_up_into_this_age_group_is_excluded_too(self):
        rows = [row(1, 10, 20), row(2, 10, 20, age_group_id=U19, home_age_group_id=U17)]
        gathered = to_rated_matches(rows, U17, HOMEGROWN)
        assert gathered.other_age_group == 1
        assert 2 not in by_id(gathered)

    def test_completed_without_a_score_is_counted_not_rated(self):
        gathered = to_rated_matches([row(1, 10, 20), row(2, 10, 20, hs=None, as_=None)], U17, HOMEGROWN)
        assert gathered.no_score == 1
        assert 2 not in by_id(gathered)

    def test_penalties_are_carried_and_kickoff_parsed_in_utc(self):
        r = row(1, 10, 20, 2, 2, home_penalty_score=4, away_penalty_score=3)
        r["scheduled_kickoff"] = "2026-09-02T14:30:00-04:00"
        m = by_id(to_rated_matches([r], U17, HOMEGROWN))[1]
        assert (m.home_penalty_score, m.away_penalty_score) == (4, 3)
        assert m.kickoff_time.isoformat() == "18:30:00"

    def test_conference_ids_map_division_names(self):
        rows = [row(1, 10, 20), row(2, 30, 40, division="Southeast")]
        assert to_rated_matches(rows, U17, HOMEGROWN).conference_ids == {"Northeast": NORTHEAST, "Southeast": SOUTHEAST}

    def test_other_match_types_are_ignored(self):
        assert to_rated_matches([row(1, 10, 20, kind="Friendly")], U17, HOMEGROWN).matches == ()

    def test_no_rows_is_an_empty_input(self):
        assert to_rated_matches([], U17, HOMEGROWN) == Gathered(())


# --- the fingerprint -----------------------------------------------------------------


class TestFingerprint:
    ROWS = [row(1, 10, 20), row(2, 20, 30, 2, 2), tournament(3, 10, 30)]

    def test_stable_whatever_the_read_order(self):
        a = fingerprint(to_rated_matches(self.ROWS, U17, HOMEGROWN))
        b = fingerprint(to_rated_matches(list(reversed(self.ROWS)), U17, HOMEGROWN))
        assert a == b
        assert len(a) == 64

    def test_a_score_correction_changes_it(self):
        corrected = [row(1, 10, 20, 2, 0), *self.ROWS[1:]]
        assert fingerprint(to_rated_matches(self.ROWS, U17, HOMEGROWN)) != fingerprint(
            to_rated_matches(corrected, U17, HOMEGROWN)
        )

    def test_a_status_change_to_forfeit_changes_it(self):
        forfeited = [row(1, 10, 20, match_status="forfeit"), *self.ROWS[1:]]
        assert fingerprint(to_rated_matches(self.ROWS, U17, HOMEGROWN)) != fingerprint(
            to_rated_matches(forfeited, U17, HOMEGROWN)
        )

    def test_the_params_version_is_part_of_it(self):
        gathered = to_rated_matches(self.ROWS, U17, HOMEGROWN)
        assert fingerprint(gathered) == fingerprint(gathered, PARAMS_VERSION)
        assert fingerprint(gathered) != fingerprint(gathered, "elo-v2")


# --- engine output -> rows -----------------------------------------------------------


def league_season(conference: str, teams: list[int], start_id: int) -> list[RatedMatch]:
    """A double round robin: every team plays every other twice, 2(n-1) matches each."""
    ids = count(start_id)
    out = []
    for i, home in enumerate(teams):
        for away in teams[i + 1 :]:
            for h, a in ((home, away), (away, home)):
                mid = next(ids)
                out.append(
                    RatedMatch(
                        mid, date(2026, 9, 1 + mid % 28), h, a, (h * 7 + a) % 4, (a * 3 + h) % 3, conference=conference
                    )
                )
    return out


class TestRatingRows:
    def test_conference_only_age_group_has_conference_ranks_and_no_national_rank(self):
        # Two conferences that never meet: two islands, no national list.
        matches = league_season("Northeast", [1, 2, 3, 4], 1) + league_season("Southeast", [5, 6, 7, 8], 100)
        result = rate(matches)
        assert not result.publication.national
        rows = {r["team_id"]: r for r in rating_rows(result, None, {"Northeast": NORTHEAST, "Southeast": SOUTHEAST})}
        assert all(r["rank"] is None for r in rows.values())
        for conference, ids, division_id in (
            ("Northeast", [1, 2, 3, 4], NORTHEAST),
            ("Southeast", [5, 6, 7, 8], SOUTHEAST),
        ):
            ordered = sorted(ids, key=lambda t: -rows[t]["rating"])
            assert [rows[t]["conference_rank"] for t in ordered] == [1, 2, 3, 4], conference
            assert {rows[t]["conference_division_id"] for t in ids} == {division_id}

    def test_national_age_group_ranks_the_main_island_by_rating(self):
        matches = league_season("Northeast", [1, 2, 3, 4], 1) + league_season("Southeast", [5, 6, 7, 8], 100)
        # Enough cross-conference matches to pass the publication rule.
        bridges = [
            RatedMatch(500 + i, date(2026, 10, 1 + i), h, a, 1, 0, competition="flex")
            for i, (h, a) in enumerate([(1, 5), (2, 6), (3, 7), (4, 8), (5, 2), (6, 1)])
        ]
        result = rate(matches + bridges)
        assert result.publication.national
        rows = rating_rows(result, massey(matches + bridges), {})
        ranked = [r for r in rows if r["rank"] is not None]
        assert [r["rank"] for r in ranked] == list(range(1, 9))
        assert [r["rating"] for r in ranked] == sorted((r["rating"] for r in ranked), reverse=True)
        assert sorted(r["massey_rank"] for r in rows) == list(range(1, 9))

    def test_unranked_team_carries_no_rank_of_any_kind_and_no_zero(self):
        matches = [
            *league_season("Northeast", [1, 2, 3, 4], 1),
            RatedMatch(900, date(2026, 11, 1), 1, 9, 2, 0, conference="Northeast"),
        ]
        result = rate(matches)
        audit = MasseyResult(ratings={t.team_id: float(-t.team_id) for t in result.teams}, home_advantage=0.0)
        newcomer = next(r for r in rating_rows(result, audit, {"Northeast": NORTHEAST}) if r["team_id"] == 9)
        assert newcomer["mp"] == 1
        assert (newcomer["rank"], newcomer["conference_rank"], newcomer["massey_rank"]) == (None, None, None)
        assert "provisional" not in newcomer["badges"]

    def test_badges_from_the_engine_flags(self):
        # 6 matches each: ranked, still provisional (< 8), no cross-conference matches.
        result = rate(league_season("Northeast", [1, 2, 3, 4], 1))
        r = rating_rows(result, None, {})[0]
        assert r["badges"] == ["provisional", "low_cross_conference"]
        assert r["conference_division_id"] is None  # name not in the map: stored as null

    def test_deltas_two_per_rated_match(self):
        result = rate(league_season("Northeast", [1, 2, 3], 1))
        rows = delta_rows(result)
        assert len(rows) == 2 * result.matches_counted
        assert set(rows[0]) == {
            "match_id", "team_id", "opponent_id", "rating_before", "opponent_before",
            "expected", "result", "k", "margin_mult", "delta",
        }  # fmt: skip

    def test_run_row_states_every_exclusion_and_the_last_rated_day(self):
        gathered = to_rated_matches(
            [row(1, 10, 20), row(5, 10, 20, match_status="forfeit"), row(2, 10, 20, away_age_group_id=U19)],
            U17,
            HOMEGROWN,
        )
        result = rate(gathered.matches)
        run = run_row(
            season_id=184, age_group_id=U17, league_id=HOMEGROWN, result=result, gathered=gathered,
            input_fingerprint="f", computed_at=datetime(2026, 11, 28, 10, tzinfo=UTC),
        )  # fmt: skip
        assert run["matches_counted"] == 1
        assert run["matches_excluded"] == {"forfeit": 1, "out_of_pool_opponent": 0, OTHER_AGE_GROUP: 1, NO_SCORE: 0}
        assert run["through_date"] == "2026-09-02"  # the forfeit on 09-06 was not rated
        assert run["params_version"] == PARAMS_VERSION
        assert run["params"]["k"] == 30.0
        assert run["national"] is False and run["publication_reason"]

    def test_nothing_rated_has_no_through_date(self):
        gathered = Gathered(())
        result = rate(())
        run = run_row(
            season_id=184, age_group_id=U17, league_id=HOMEGROWN, result=result, gathered=gathered,
            input_fingerprint="f", computed_at=datetime(2026, 11, 28, tzinfo=UTC),
        )  # fmt: skip
        assert run["through_date"] is None
        assert matches_excluded(result, gathered) == {
            "forfeit": 0, "out_of_pool_opponent": 0, OTHER_AGE_GROUP: 0, NO_SCORE: 0,
        }  # fmt: skip


# --- writes, against an in-memory client ---------------------------------------------


class _Query:
    def __init__(self, db: "FakeClient", table: str):
        self.db, self.table, self.op, self.payload, self.filters = db, table, "select", None, []

    def select(self, *_):
        return self

    def insert(self, rows):
        self.op, self.payload = "insert", rows if isinstance(rows, list) else [rows]
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, col, value):
        self.filters.append(lambda r: r.get(col) == value)
        return self

    def neq(self, col, value):
        self.filters.append(lambda r: r.get(col) != value)
        return self

    def in_(self, col, values):
        self.filters.append(lambda r: r.get(col) in set(values))
        return self

    def lte(self, col, value):
        self.filters.append(lambda r: r.get(col) <= value)
        return self

    def order(self, col, desc=False):
        self.sort = (col, desc)
        return self

    def limit(self, n):
        self.n = n
        return self

    def range(self, start, end):
        self.window = (start, end + 1)
        return self

    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        if self.table in self.db.fail_on and self.op == "insert":
            raise RuntimeError("boom")
        if self.op == "insert":
            out = []
            for r in self.payload:
                stored = {"id": next(self.db.ids), **r}
                rows.append(stored)
                out.append(stored)
            return type("R", (), {"data": out})
        matched = [r for r in rows if all(f(r) for f in self.filters)]
        if self.op == "delete":
            gone = {id(r) for r in matched}
            self.db.tables[self.table] = [r for r in rows if id(r) not in gone]
            if self.table == "power_rating_runs":  # ON DELETE CASCADE
                ids = {r["id"] for r in matched}
                for child in ("power_ratings", "power_rating_match_deltas"):
                    self.db.tables[child] = [r for r in self.db.tables.get(child, []) if r["run_id"] not in ids]
            return type("R", (), {"data": matched})
        if hasattr(self, "sort"):
            col, desc = self.sort
            matched = sorted(matched, key=lambda r: (r.get(col), r["id"]), reverse=desc)
        if hasattr(self, "window"):
            matched = matched[self.window[0] : self.window[1]]
        return type("R", (), {"data": matched[: getattr(self, "n", None)]})


class FakeClient:
    def __init__(self, fail_on=()):
        self.tables: dict[str, list[dict]] = {}
        self.ids = count(1)
        self.fail_on = set(fail_on)

    def table(self, name):
        return _Query(self, name)


def make_dao(client) -> PowerRatingDAO:
    dao = PowerRatingDAO.__new__(PowerRatingDAO)
    dao.client = client
    dao.connection_holder = None
    dao._match_dao = None
    return dao


def scope_run(day: int, fp: str = "f") -> dict:
    return {
        "season_id": 184, "age_group_id": U17, "league_id": HOMEGROWN,
        "computed_at": f"2026-11-{day:02d}T10:00:00+00:00", "input_fingerprint": fp,
    }  # fmt: skip


class TestWriteRun:
    def test_writes_run_ratings_and_deltas_with_the_run_id(self):
        db = FakeClient()
        dao = make_dao(db)
        run_id = dao.write_run(scope_run(20), [{"team_id": 1}, {"team_id": 2}], [{"match_id": 7, "team_id": 1}])
        assert [r["run_id"] for r in db.tables["power_ratings"]] == [run_id, run_id]
        assert [r["run_id"] for r in db.tables["power_rating_match_deltas"]] == [run_id]

    def test_only_the_latest_run_keeps_deltas(self):
        db = FakeClient()
        dao = make_dao(db)
        first = dao.write_run(scope_run(20), [{"team_id": 1}], [{"match_id": 7, "team_id": 1}])
        second = dao.write_run(scope_run(21), [{"team_id": 1}], [{"match_id": 7, "team_id": 1}])
        assert {r["run_id"] for r in db.tables["power_rating_match_deltas"]} == {second}
        # The older run and its ratings stay: they are the published record.
        assert {r["id"] for r in db.tables["power_rating_runs"]} == {first, second}
        assert {r["run_id"] for r in db.tables["power_ratings"]} == {first, second}

    def test_another_age_groups_deltas_are_untouched(self):
        db = FakeClient()
        dao = make_dao(db)
        u19 = dao.write_run({**scope_run(20), "age_group_id": U19}, [], [{"match_id": 8, "team_id": 3}])
        u17 = dao.write_run(scope_run(21), [], [{"match_id": 7, "team_id": 1}])
        assert {r["run_id"] for r in db.tables["power_rating_match_deltas"]} == {u19, u17}

    def test_a_failed_write_leaves_no_half_run(self):
        db = FakeClient(fail_on={"power_rating_match_deltas"})
        dao = make_dao(db)
        with pytest.raises(RuntimeError):
            dao.write_run(scope_run(20), [{"team_id": 1}], [{"match_id": 7, "team_id": 1}])
        assert db.tables["power_rating_runs"] == []
        assert db.tables["power_ratings"] == []

    def test_latest_run_and_run_as_of(self):
        db = FakeClient()
        dao = make_dao(db)
        assert dao.latest_run(184, U17, HOMEGROWN) is None
        a = dao.write_run(scope_run(14, "a"), [], [])
        b = dao.write_run(scope_run(21, "b"), [], [])
        assert dao.latest_run(184, U17, HOMEGROWN)["input_fingerprint"] == "b"
        assert dao.latest_run_id(184, U17, HOMEGROWN) == b
        week_ago = datetime(2026, 11, 14, 12, tzinfo=UTC)
        assert dao.run_as_of(184, U17, HOMEGROWN, week_ago)["id"] == a
        assert dao.run_as_of(184, U17, HOMEGROWN, datetime(2026, 11, 1, tzinfo=UTC)) is None


class TestRunPayload:
    """SB-1808: a run as served, cached by run id; a half-written run is never cached."""

    def _cache(self, monkeypatch):
        store: dict[str, object] = {}
        monkeypatch.setattr("dao.power_rating_dao.cache_get", store.get)
        monkeypatch.setattr("dao.power_rating_dao.cache_set", lambda key, value, ttl: store.__setitem__(key, value))
        return store

    def test_run_ratings_and_conference_names(self, monkeypatch):
        cache = self._cache(monkeypatch)
        db = FakeClient()
        db.tables["divisions"] = [{"id": NORTHEAST, "name": "Northeast"}]
        dao = make_dao(db)
        run_id = dao.write_run(
            {**scope_run(20), "matches_counted": 1},
            [{"team_id": 1, "rating": 1510.0, "conference_division_id": NORTHEAST}, {"team_id": 2, "rating": 1490.0}],
            [],
        )
        payload = dao.run_payload(run_id)
        assert payload["run"]["id"] == run_id
        assert [r["team_id"] for r in payload["ratings"]] == [1, 2]
        assert payload["conferences"] == {str(NORTHEAST): "Northeast"}
        assert cache == {f"mt:dao:power_rating:run:{run_id}": payload}

    def test_a_cached_payload_is_served_without_a_read(self, monkeypatch):
        cache = self._cache(monkeypatch)
        cache["mt:dao:power_rating:run:5"] = {"run": {"id": 5}, "ratings": [], "conferences": {}}
        dao = make_dao(FakeClient())
        assert dao.run_payload(5)["run"] == {"id": 5}

    def test_a_run_caught_before_its_ratings_is_not_cached(self, monkeypatch):
        cache = self._cache(monkeypatch)
        db = FakeClient()
        db.tables["power_rating_runs"] = [{**scope_run(20), "id": 9, "matches_counted": 12}]
        dao = make_dao(db)
        assert dao.run_payload(9)["ratings"] == []
        assert cache == {}

    def test_an_empty_run_is_cached(self, monkeypatch):
        cache = self._cache(monkeypatch)
        db = FakeClient()
        dao = make_dao(db)
        run_id = dao.write_run({**scope_run(20), "matches_counted": 0}, [], [])
        assert dao.run_payload(run_id)["ratings"] == []
        assert list(cache) == [f"mt:dao:power_rating:run:{run_id}"]

    def test_no_such_run(self, monkeypatch):
        self._cache(monkeypatch)
        assert make_dao(FakeClient()).run_payload(404) is None

    def test_team_reads(self):
        db = FakeClient()
        dao = make_dao(db)
        a = dao.write_run(scope_run(13), [{"team_id": 1, "rating": 1500.0}], [])
        b = dao.write_run(
            scope_run(20),
            [{"team_id": 1, "rating": 1520.0}, {"team_id": 2, "rating": 1480.0}],
            [{"match_id": 7, "team_id": 1, "delta": 20.0}, {"match_id": 7, "team_id": 2, "delta": -20.0}],
        )
        assert [r["id"] for r in dao.runs(184, U17, HOMEGROWN)] == [a, b]
        assert {r["run_id"] for r in dao.team_ratings(1, [a, b])} == {a, b}
        assert dao.team_ratings(1, []) == []
        assert [d["delta"] for d in dao.team_deltas(b, 1)] == [20.0]
        db.tables["matches_with_test"] = [{"id": 7, "home_score": 1}, {"id": 8, "home_score": 0}]
        assert dao.matches_by_ids([7, 7]) == [{"id": 7, "home_score": 1}]
        assert dao.matches_by_ids([]) == []

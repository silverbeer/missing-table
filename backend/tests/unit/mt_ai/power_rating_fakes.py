"""Stored Power Rating runs for the read tests (SB-1808).

Built on the leaderboards' league world (`leaderboards_fakes`): teams 1-4
Northeast, 5-6 Southeast, 7 Flex only, 8 a pro academy, 9 a test team. The
default store has no run at all: before launch, that is every age group.
"""

from dataclasses import replace

from leaderboards_fakes import HG, NORTHEAST, SOUTHEAST, U15
from leaderboards_fakes import deps as league_deps

SEASON = 7  # leaderboards_fakes.CURRENT
CONFERENCES = {str(NORTHEAST): "Northeast", str(SOUTHEAST): "Southeast"}


def run(run_id: int, day: str, *, national: bool = False, reason: str | None = None, **extra) -> dict:
    """A power_rating_runs row as `run_payload` serves it, U15 Homegrown."""
    return {
        "id": run_id,
        "season_id": SEASON,
        "age_group_id": U15,
        "league_id": HG,
        "computed_at": f"{day}T10:00:00+00:00",
        "through_date": day,
        "params_version": "elo-v1",
        "matches_counted": 40,
        "matches_excluded": {"forfeit": 0, "out_of_pool_opponent": 2, "other_age_group": 0, "no_score": 0},
        "national": national,
        "publication_reason": None if national else (reason or "The largest connected group holds 60% of ranked teams; a national list needs 90%."),
        **extra,
    }  # fmt: skip


def rating(team_id: int, value: float, mp: int = 8, *, conf: int | None = NORTHEAST, **extra) -> dict:
    """A power_ratings row. Ranks default to none: pass rank / conference_rank."""
    return {
        "team_id": team_id,
        "rating": value,
        "rank": None,
        "island": 1,
        "conference_division_id": conf,
        "conference_rank": None,
        "mp": mp,
        "w": mp // 2,
        "d": 1 if mp else 0,
        "l": mp - mp // 2 - (1 if mp else 0),
        "xconf_mp": 1,
        "sos": 1500.0,
        "tier": None,
        "badges": ["low_cross_conference"],
        **extra,
    }


def delta(match_id: int, team_id: int, opponent_id: int, value: float, result: float, expected: float = 0.5) -> dict:
    return {
        "match_id": match_id,
        "team_id": team_id,
        "opponent_id": opponent_id,
        "rating_before": 1500.0,
        "opponent_before": 1500.0,
        "expected": expected,
        "result": result,
        "k": 30.0,
        "margin_mult": 1.0,
        "delta": value,
    }


def score(match_id: int, day: str, home: int, away: int, hs: int, as_: int, hp=None, ap=None) -> dict:
    return {
        "id": match_id,
        "match_date": day,
        "home_team_id": home,
        "away_team_id": away,
        "home_score": hs,
        "away_score": as_,
        "home_penalty_score": hp,
        "away_penalty_score": ap,
    }


class FakePowerRating:
    """Stands in for PowerRatingDAO's serving reads; one scope (U15 Homegrown, season 7)."""

    def __init__(self, runs=(), ratings=None, deltas=None, matches=(), *, fail: bool = False):
        self.run_rows = list(runs)
        self.ratings = ratings or {}
        self.deltas = deltas or {}
        self.matches = {m["id"]: m for m in matches}
        self.fail = fail
        self.payload_reads: list[int] = []

    def _check(self):
        if self.fail:
            raise RuntimeError("PostgREST down at db.internal:5432")

    def _scope(self, season_id, age_group_id, league_id):
        return sorted(
            (
                r
                for r in self.run_rows
                if (r["season_id"], r["age_group_id"], r["league_id"]) == (season_id, age_group_id, league_id)
            ),
            key=lambda r: (r["computed_at"], r["id"]),
        )

    def latest_run(self, season_id, age_group_id, league_id):
        self._check()
        rows = self._scope(season_id, age_group_id, league_id)
        return dict(rows[-1]) if rows else None

    def run_as_of(self, season_id, age_group_id, league_id, at):
        self._check()
        rows = [r for r in self._scope(season_id, age_group_id, league_id) if r["computed_at"] <= at.isoformat()]
        return dict(rows[-1]) if rows else None

    def run_payload(self, run_id):
        self._check()
        self.payload_reads.append(run_id)
        found = next((r for r in self.run_rows if r["id"] == run_id), None)
        if found is None:
            return None
        return {
            "run": dict(found),
            "ratings": [dict(r) for r in self.ratings.get(run_id, [])],
            "conferences": CONFERENCES,
        }

    def runs(self, season_id, age_group_id, league_id):
        self._check()
        return [
            {"id": r["id"], "computed_at": r["computed_at"], "through_date": r["through_date"]}
            for r in self._scope(season_id, age_group_id, league_id)
        ]

    def team_ratings(self, team_id, run_ids):
        self._check()
        ids = set(run_ids)
        return [
            {"run_id": rid, **{k: r[k] for k in ("rating", "rank", "conference_rank", "mp")}}
            for rid, rows in self.ratings.items()
            if rid in ids
            for r in rows
            if r["team_id"] == team_id
        ]

    def team_deltas(self, run_id, team_id):
        self._check()
        return [dict(d) for d in self.deltas.get(run_id, []) if d["team_id"] == team_id]

    def matches_by_ids(self, match_ids):
        self._check()
        return [dict(self.matches[i]) for i in set(match_ids) if i in self.matches]


def deps(store: FakePowerRating | None = None, **kwargs):
    return replace(league_deps(**kwargs), power_rating=store if store is not None else FakePowerRating())


# --- worlds --------------------------------------------------------------------


def national_world() -> FakePowerRating:
    """A national run on Nov 27 and the one users saw a week earlier (Nov 20), plus one on Nov 25.

    Team 6 is ranked but outside the main island; team 7 has 4 matches; team 9
    is a test team, never shown.
    """
    latest = [
        rating(1, 1754.4, 12, rank=1, conference_rank=1, tier="elite"),
        rating(2, 1650.6, 11, rank=2, conference_rank=2, tier="contender", badges=["provisional"]),
        rating(8, 1540.0, 10, conf=SOUTHEAST, rank=3, conference_rank=1, tier="above_average"),
        rating(5, 1420.0, 9, conf=SOUTHEAST, rank=4, conference_rank=2),
        rating(6, 1480.0, 7, conf=SOUTHEAST, island=2),
        rating(7, 1500.0, 4, conf=None, badges=["low_cross_conference"]),
        rating(9, 1600.0, 9, rank=5, conference_rank=3),
    ]
    week_ago = [
        rating(1, 1742.0, 10, rank=3, conference_rank=1),
        rating(2, 1660.0, 9, rank=1, conference_rank=2),
        rating(8, 1530.0, 8, conf=SOUTHEAST, rank=2, conference_rank=1),
    ]
    two_days_ago = [rating(1, 1700.0, 11, rank=9, conference_rank=1)]
    return FakePowerRating(
        runs=[run(10, "2026-11-20", national=True), run(11, "2026-11-25", national=True), run(12, "2026-11-27", national=True)],
        ratings={10: week_ago, 11: two_days_ago, 12: latest},
    )  # fmt: skip


def conference_world() -> FakePowerRating:
    """One run, not national: conference lists only, no run a week earlier."""
    ratings = [
        rating(1, 1600.0, 8, conference_rank=1),
        rating(3, 1550.0, 8, conference_rank=2),
        rating(5, 1700.0, 8, conf=SOUTHEAST, conference_rank=1),
        rating(4, 1450.0, 3),
    ]
    return FakePowerRating(runs=[run(20, "2026-11-27")], ratings={20: ratings})

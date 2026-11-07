"""Match of the Week candidate scoring (SB-1550).

The world here is MT's default: scraped fixtures and results, no rosters, no
logged goals. Nothing in a candidate may depend on user data.
"""

from datetime import UTC, date, datetime

import pytest

from mt_ai.tools import ToolDeps
from mt_tools.motw_candidates import (
    FEATURED_PENALTY,
    POOL,
    Pool,
    TeamStanding,
    _percentiles,
    form_score,
    score_fixture,
    stakes_score,
    standings_from_rows,
    streak_text,
    suggest_motw_candidates,
    team_strengths,
    week_bounds,
)

pytestmark = pytest.mark.unit

HG, FLEX = 1, 2
U15, U16 = 15, 16
NORTHEAST, PPP, EMPIRE, NEW_ENGLAND, TURNPIKE = 201, 202, 203, 204, 205
DIVS = {
    NORTHEAST: ("Northeast", HG),
    PPP: ("Northeast (Pro Player Pathway)", HG),
    EMPIRE: ("Empire", FLEX),
    NEW_ENGLAND: ("New England", FLEX),
    TURNPIKE: ("Turnpike", FLEX),
}
LEAGUES = [
    {"id": HG, "name": "Homegrown", "is_test": False},
    {"id": FLEX, "name": "Flex", "is_test": False, "parent_league_id": HG},
]
CLUBS = [{"id": i, "name": f"Club {i}", "timezone": "America/New_York", "is_test": False} for i in range(1, 9)]

# "Today" is Saturday 2026-11-07 in New York; the week is Nov 2-8.
NOW = datetime(2026, 11, 7, 14, 0, tzinfo=UTC)
TODAY = date(2026, 11, 7)


def reg(age: int, division_id: int) -> dict:
    name, league_id = DIVS[division_id]
    return {
        "age_groups": {"id": age, "name": f"U{age}"},
        "divisions": {"id": division_id, "name": name, "league_id": league_id},
    }


def team(team_id: int, *mappings: dict) -> dict:
    return {
        "id": team_id,
        "name": f"Team {team_id}",
        "club_id": team_id,
        "league_id": HG,
        "team_mappings": list(mappings),
    }


# Six U15 teams: Northeast (League) plus Turnpike (Flex). Team 1 also plays U16.
TEAMS = [
    team(1, reg(U15, NORTHEAST), reg(U15, TURNPIKE), reg(U16, NORTHEAST)),
    team(2, reg(U15, NORTHEAST), reg(U15, TURNPIKE), reg(U16, NORTHEAST)),
    team(3, reg(U15, NORTHEAST), reg(U15, TURNPIKE)),
    team(4, reg(U15, NORTHEAST), reg(U15, TURNPIKE)),
    team(5, reg(U15, NORTHEAST), reg(U15, EMPIRE)),
    team(6, reg(U15, NORTHEAST), reg(U15, NEW_ENGLAND)),
    team(7, reg(U16, PPP)),
    team(8, reg(U16, PPP)),
]

_ids = iter(range(1000, 9999))


def match(home, away, day, division, *, age=U15, hs=None, as_=None, status=None, mtype=None, mid=None):
    name, league_id = DIVS[division]
    return {
        "id": mid or next(_ids),
        "match_date": day,
        "scheduled_kickoff": None,
        "home_team_id": home,
        "away_team_id": away,
        "home_team_name": f"Team {home}",
        "away_team_name": f"Team {away}",
        "home_score": hs,
        "away_score": as_,
        "match_status": status or ("completed" if hs is not None else "scheduled"),
        "match_type_name": mtype or ("Flex" if league_id == FLEX else "League"),
        "division_id": division,
        "age_group_id": age,
        "age_group_name": f"U{age}",
        "league_name": "Flex" if league_id == FLEX else "Homegrown",
    }


def played(home, away, day, division, hs, as_, **kw):
    return match(home, away, day, division, hs=hs, as_=as_, **kw)


def default_matches() -> list[dict]:
    return [
        # Turnpike U15 (Flex): 1 and 2 unbeaten at the top, 3 mid, 4 bottom.
        played(1, 3, "2026-10-03", TURNPIKE, 2, 0),
        played(2, 4, "2026-10-03", TURNPIKE, 3, 1),
        played(1, 4, "2026-10-17", TURNPIKE, 4, 0),
        played(2, 3, "2026-10-17", TURNPIKE, 1, 1),
        played(3, 4, "2026-10-24", TURNPIKE, 2, 1),
        played(1, 2, "2026-10-10", TURNPIKE, 1, 1),
        match(1, 2, "2026-11-08", TURNPIKE, mid=501),  # the top-of-table rematch
        match(3, 4, "2026-11-08", TURNPIKE, mid=502),
        # Northeast U15 (League)
        played(1, 5, "2026-09-12", NORTHEAST, 3, 0),
        played(2, 6, "2026-09-12", NORTHEAST, 0, 1),
        played(5, 6, "2026-09-19", NORTHEAST, 2, 2),
        played(1, 6, "2026-09-26", NORTHEAST, 1, 0),
        played(2, 5, "2026-09-26", NORTHEAST, 2, 1),
        played(3, 5, "2026-10-31", NORTHEAST, 0, 2),
        match(5, 6, "2026-11-08", NORTHEAST, mid=503),
        match(3, 4, "2026-11-05", NORTHEAST, mid=504),  # in the week, already past
        match(1, 6, "2026-11-07", NORTHEAST, status="cancelled", mid=505),
        match(2, 3, "2026-11-21", NORTHEAST, mid=506),  # a later week
        # U16: team 1 loses everything there. Its U15 form must not see this.
        played(1, 2, "2026-10-01", NORTHEAST, 0, 5, age=U16),
        played(2, 1, "2026-10-08", NORTHEAST, 4, 0, age=U16),
        played(1, 2, "2026-10-15", NORTHEAST, 0, 3, age=U16),
        # PPP U16: two teams, nothing played
        match(7, 8, "2026-11-08", PPP, age=U16, mid=507),
    ]


def standings(matches: list[dict], shootout: bool = False) -> list[dict]:
    rows: dict[int, dict] = {}
    for m in matches:
        if m["match_status"] != "completed":
            continue
        for tid, gf, ga in (
            (m["home_team_id"], m["home_score"], m["away_score"]),
            (m["away_team_id"], m["away_score"], m["home_score"]),
        ):
            r = rows.setdefault(
                tid,
                {
                    "team_id": tid,
                    "team": f"Team {tid}",
                    "played": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "points": 0,
                },
            )
            r["played"] += 1
            r["goals_for"] += gf
            r["goals_against"] += ga
            if gf > ga:
                r["wins"] += 1
                r["points"] += 3
            elif gf == ga:
                r["draws"] += 1
                r["points"] += 1
            else:
                r["losses"] += 1
    return sorted(rows.values(), key=lambda r: (-r["points"], -(r["goals_for"] - r["goals_against"]), r["team_id"]))


class FakeMatches:
    def __init__(self, matches: list[dict], fail: bool = False) -> None:
        self.matches, self.fail = matches, fail
        self.standings_calls: list[tuple] = []

    def get_all_matches(
        self, season_id=None, age_group_id=None, division_id=None, include_test=False, raise_on_error=False, **_
    ):
        if self.fail:
            raise RuntimeError("PostgREST down")
        return [
            dict(m)
            for m in self.matches
            if (division_id is None or m["division_id"] == division_id)
            and (age_group_id is None or m["age_group_id"] == age_group_id)
        ]

    def get_standings(
        self,
        season_id=None,
        age_group_id=None,
        division_id=None,
        match_type="League",
        include_test=False,
        raise_on_error=False,
    ):
        self.standings_calls.append((division_id, age_group_id, match_type))
        ms = [
            m
            for m in self.matches
            if m["division_id"] == division_id
            and m["age_group_id"] == age_group_id
            and m["match_type_name"] == match_type
        ]
        return {"standings": standings(ms), "coverage": {}}

    def team_has_matches_in_season(self, *a, **k):
        return True


class FakeTeams:
    def get_all_teams(self):
        return [dict(t) for t in TEAMS]

    def resolve_team_by_name(self, name, league_id=None):
        return None


class FakeClubs:
    def get_all_clubs(self, include_team_counts=True):
        return CLUBS


class FakeLeagues:
    def get_all_leagues(self, include_test=False):
        return LEAGUES


class FakeSeasons:
    def get_current_season(self):
        return {"id": 7, "name": "2026-2027"}

    def get_all_seasons(self):
        return [self.get_current_season()]


def deps(matches=None, fail=False) -> ToolDeps:
    return ToolDeps(
        teams=FakeTeams(),
        clubs=FakeClubs(),
        leagues=FakeLeagues(),
        matches=FakeMatches(default_matches() if matches is None else matches, fail=fail),
        seasons=FakeSeasons(),
    )


def no_picks(_week: str):
    return None


def run(week=None, picks=no_picks, **kw):
    return suggest_motw_candidates(kw.pop("d", None) or deps(), week, picks=picks, now=NOW, **kw)


def by_id(result):
    return {c.match_id: c for c in result.candidates}


# --- pure functions -------------------------------------------------------------


class TestPure:
    def test_percentiles_share_ties(self):
        assert _percentiles({1: 3.0, 2: 1.0, 3: 1.0}) == {1: 1.0, 2: 0.25, 3: 0.25}
        assert _percentiles({1: 2.0}) == {1: 0.5}

    def test_cross_age_normalization(self):
        """Two tables with the same order but different scales give the same strengths."""
        u15 = standings_from_rows(
            [
                {"team_id": 1, "played": 4, "points": 12, "goals_for": 12, "goals_against": 1},
                {"team_id": 2, "played": 4, "points": 6, "goals_for": 5, "goals_against": 5},
                {"team_id": 3, "played": 4, "points": 0, "goals_for": 0, "goals_against": 11},
            ]
        )
        u19 = standings_from_rows(
            [
                {"team_id": 1, "played": 4, "points": 8, "goals_for": 5, "goals_against": 2},
                {"team_id": 2, "played": 4, "points": 5, "goals_for": 4, "goals_against": 4},
                {"team_id": 3, "played": 4, "points": 3, "goals_for": 2, "goals_against": 5},
            ]
        )
        assert team_strengths(u15) == team_strengths(u19)

    def test_low_sample_is_damped_and_flagged(self):
        table = standings_from_rows(
            [
                {"team_id": 1, "played": 1, "points": 3, "goals_for": 3, "goals_against": 0},
                {"team_id": 2, "played": 5, "points": 0, "goals_for": 0, "goals_against": 9},
            ]
        )
        strengths = team_strengths(table)
        assert strengths[1] == (pytest.approx(0.5 + 0.5 / 3), True)
        assert strengths[2] == (0.0, False)

    def test_team_without_games_is_neutral_not_zero(self):
        table = {9: TeamStanding(9, 1, 0, 0, 0, 0, 0, 0, 0)}
        assert team_strengths(table)[9] == (0.5, True)

    def test_form_score_weights_newest_most(self):
        assert form_score(["W", "L"]) == pytest.approx(5 / 9)
        assert form_score(["L", "W"]) == pytest.approx(4 / 9)
        assert form_score([]) is None
        assert form_score(["W"] * 8) == 1.0

    def test_stakes(self):
        a = TeamStanding(1, 1, 3, 7, 2, 1, 0, 0, 0)
        b = TeamStanding(2, 2, 3, 5, 1, 2, 0, 0, 0)
        c = TeamStanding(3, 6, 3, 1, 0, 1, 2, 0, 0)
        table = {1: a, 2: b, 3: c}
        assert stakes_score(a, b, 6, [1], table) == (1.0, ["adjacent", "qualifying_line", "top_of_table"])
        assert stakes_score(a, c, 6, [], table) == (0.0, [])
        assert stakes_score(None, b, 6, [1], table) == (0.0, [])

    def test_featured_penalty(self):
        plain = score_fixture(0.8, 0.8, 1.0, 1.0, 1.0, featured=False)
        featured = score_fixture(0.8, 0.8, 1.0, 1.0, 1.0, featured=True)
        assert featured.total == pytest.approx(plain.total * FEATURED_PENALTY, abs=1e-4)

    def test_missing_form_is_neutral(self):
        assert score_fixture(0.5, 0.5, 0.0, None, None, featured=False).form == 0.5

    @pytest.mark.parametrize(
        ("results", "text"),
        [
            (["W", "W", "W"], "won all 3"),
            (["W", "W", "W", "L"], "won 3 League/Flex games in a row"),
            (["D", "W", "D", "L"], "unbeaten in 3"),
            (["L", "L", "L", "W"], "lost 3 in a row"),
            (["W", "L", "W"], None),
        ],
    )
    def test_streaks(self, results, text):
        out = streak_text("Team", results)
        assert (out is None) if text is None else (text in out)

    def test_week_bounds(self):
        assert week_bounds(None, TODAY) == (date(2026, 11, 2), date(2026, 11, 8))
        assert week_bounds("2026-11-14", TODAY) == (date(2026, 11, 9), date(2026, 11, 15))


# --- the tool --------------------------------------------------------------------


class TestSuggest:
    def test_ranks_the_top_of_table_clash_first(self):
        result = run()
        assert result.error is None
        assert result.week_start == date(2026, 11, 2)
        assert result.candidates[0].match_id == 501

    def test_only_eligible_fixtures(self):
        ids = set(by_id(run()))
        assert 504 not in ids  # in the week but before today
        assert 505 not in ids  # cancelled
        assert 506 not in ids  # another week
        assert {501, 502, 503, 507} <= ids

    def test_coverage_states_the_denominator(self):
        cov = run().coverage
        assert cov.divisions == 5
        assert cov.fixtures_in_week == 6  # 501-505 and 507
        assert cov.eligible == 4
        assert cov.rules_season == "2026-27"

    def test_flex_fixture_carries_flex_rules(self):
        top = by_id(run())[501]
        assert "qualifying_line" in top.flags
        rules = {r.id: r.confirmed for r in top.rules}
        assert rules == {"hg-flex-conference-bye-race": True, "hg-flex-conference-winner-berth": False}
        inferred = next(f for f in top.facts if f.rule_id == "hg-flex-conference-winner-berth")
        assert inferred.confirmed is False and inferred.text.startswith("Unconfirmed: ")

    def test_league_fixture_has_no_qualifying_line(self):
        """No source ties a Northeast league finish to a Cup place."""
        ne = by_id(run())[503]
        assert "qualifying_line" not in ne.flags
        assert [r.id for r in ne.rules] == ["hg-league-play"]

    def test_fact_ids_are_unique_and_scoped_to_the_match(self):
        for c in run().candidates:
            ids = [f.id for f in c.facts]
            assert len(ids) == len(set(ids))
            assert all(i.startswith(f"{c.match_id}:") for i in ids)

    def test_facts_from_scraped_data_only(self):
        top = by_id(run())[501]
        ids = {f.id.split(":", 1)[1] for f in top.facts}
        assert {"pos:home", "pos:away", "gap", "h2h", "rate:home", "rate:away"} <= ids
        assert not any("goal" in f.text.lower() and "scorer" in f.text.lower() for f in top.facts)

    def test_history_is_scoped_to_the_age_group(self):
        """Team 1 lost all its U16 games; its U15 form is all wins and a draw."""
        home = by_id(run())[501].home
        assert home.id == 1
        assert home.form > 0.7
        streaks = [f.text for f in by_id(run())[501].facts if f.id.endswith("streak:home")]
        assert streaks and "unbeaten" in streaks[0]

    def test_teams_with_no_games_are_low_sample_not_zero(self):
        ppp = by_id(run())[507]
        assert "low_sample" in ppp.flags
        assert ppp.home.position is None and ppp.home.points is None
        assert ppp.home.strength == 0.5 and ppp.home.form is None
        assert not [f for f in ppp.facts if f.kind == "standings"]

    def test_empty_week(self):
        result = run("2026-12-21")
        assert result.error is None
        assert result.candidates == []
        assert "No pool fixtures" in result.reason
        assert result.coverage.fixtures_in_week == 0

    def test_week_with_nothing_left_to_play(self):
        result = run("2026-10-31")
        assert result.candidates == []
        assert "still to be played" in result.reason

    def test_already_picked_week_still_lists_candidates(self):
        def picks(week):
            if week == "2026-11-02":
                return {"match": {"id": 503, "home_team_id": 5, "away_team_id": 6}, "blurb": "b", "reasons": []}
            return None

        result = run(picks=picks)
        assert result.current_pick.match_id == 503
        assert result.current_pick.has_reasons is False
        assert result.candidates

    def test_recently_featured_teams_are_penalised(self):
        def picks(week):
            if week == "2026-10-26":
                return {"match": {"id": 1, "home_team_id": 1, "away_team_id": 9}}
            return None

        plain = by_id(run())[501]
        result = by_id(run(picks=picks))[501]
        assert "recently_featured" in result.flags
        assert result.score.penalty == FEATURED_PENALTY
        assert result.score.total < plain.score.total

    def test_limit(self):
        assert len(run(limit=2).candidates) == 2
        assert run(limit=0).error.kind == "invalid_args"

    def test_bad_week(self):
        assert run("next tuesday").error.kind == "invalid_args"

    def test_unknown_pool_division_fails_loudly(self):
        pool = Pool(
            age_groups=POOL.age_groups,
            match_types=POOL.match_types,
            conferences=(*POOL.conferences, ("Flex", "Atlantis")),
        )
        result = run(pool=pool)
        assert result.error.kind == "unavailable"
        assert "Flex / Atlantis" in result.error.message
        assert result.candidates is None

    def test_failed_read_is_unavailable_not_empty(self):
        result = run(d=deps(fail=True))
        assert result.error.kind == "unavailable"
        assert result.candidates is None

    def test_test_content_is_never_requested(self):
        d = deps()
        calls = []
        original = d.matches.get_all_matches

        def spy(**kw):
            calls.append(kw["include_test"])
            return original(**kw)

        d.matches.get_all_matches = spy
        run(d=d)
        assert calls and not any(calls)

"""A small league world for the leaderboards tests (SB-1781).

MT's default data: scraped results, no rosters, no logged goals. Two Homegrown
conferences that never meet, a Flex bracket, a pro academy, a test club.
"""

from mt_ai.tools import ToolDeps

HG, FLEX, ACADEMY, TEST_LEAGUE = 1, 2, 3, 9
U13, U15, U16 = 13, 15, 16
NORTHEAST, SOUTHEAST, TURNPIKE, ACAD_DIV = 201, 202, 203, 204
DIVS = {
    NORTHEAST: ("Northeast", HG),
    SOUTHEAST: ("Southeast", HG),
    TURNPIKE: ("Turnpike", FLEX),
    ACAD_DIV: ("New England", ACADEMY),
}
LEAGUE_TYPE, FLEX_TYPE = 11, 15  # match_types ids; not MT's seed ids, so nothing hardcodes them
LEAGUES = [
    {"id": HG, "name": "Homegrown", "is_test": False, "match_type_id": LEAGUE_TYPE},
    {"id": FLEX, "name": "Flex", "is_test": False, "parent_league_id": HG, "match_type_id": FLEX_TYPE},
    {"id": ACADEMY, "name": "Academy", "is_test": False, "match_type_id": LEAGUE_TYPE},
    {"id": TEST_LEAGUE, "name": "TSC League", "is_test": True},
]
PRO_CLUB, TEST_CLUB = 50, 99
CLUBS = [
    *({"id": i, "name": f"Club {i}", "is_test": False, "pro_academy": False} for i in range(1, 20)),
    {"id": PRO_CLUB, "name": "Pro Academy FC", "is_test": False, "pro_academy": True},
    {"id": TEST_CLUB, "name": "TSC Club", "is_test": True, "pro_academy": False},
]


def reg(age: int, division_id: int) -> dict:
    name, league_id = DIVS[division_id]
    return {
        "age_groups": {"id": age, "name": f"U{age}"},
        "divisions": {"id": division_id, "name": name, "league_id": league_id},
    }


def team(team_id: int, *mappings: dict, club_id: int | None = None) -> dict:
    return {
        "id": team_id,
        "name": f"Team {team_id}",
        "club_id": club_id if club_id is not None else team_id,
        "league_id": HG,
        "team_mappings": list(mappings),
    }


# 1-4 Northeast, 5-6 Southeast, 7 Flex only (no Homegrown conference), 8 a pro
# academy, 9 a test team. 10 is registered at U13 only.
TEAMS = [
    *(team(i, reg(U15, NORTHEAST), reg(U15, TURNPIKE)) for i in (1, 2, 3, 4)),
    team(5, reg(U15, SOUTHEAST)),
    team(6, reg(U15, SOUTHEAST)),
    team(7, reg(U15, TURNPIKE)),
    team(8, reg(U15, TURNPIKE), club_id=PRO_CLUB),
    team(9, reg(U15, NORTHEAST), club_id=TEST_CLUB),
    team(10, reg(U13, NORTHEAST)),
]

_ids = iter(range(1000, 99999))


def result(home, away, hs, as_, division=NORTHEAST, *, age=U15, status="completed", mtype=None, **extra) -> dict:
    """A get_season_results row, in get_all_matches' flat shape."""
    name, league_id = DIVS[division]
    row = {
        "id": next(_ids),
        "match_date": "2026-10-01",
        "home_team_id": home,
        "away_team_id": away,
        "home_team_name": f"Team {home}",
        "away_team_name": f"Team {away}",
        "home_score": hs,
        "away_score": as_,
        "home_penalty_score": None,
        "away_penalty_score": None,
        "age_group_id": age,
        "age_group_name": f"U{age}",
        "home_age_group_id": None,
        "away_age_group_id": None,
        "match_type_name": mtype or ("Flex" if league_id == FLEX else "League"),
        "division_id": division,
        "division_name": name,
        "league_id": league_id,
        "league_name": {HG: "Homegrown", FLEX: "Flex", ACADEMY: "Academy"}[league_id],
        "match_status": status,
    }
    row.update(extra)
    return row


def default_results() -> list[dict]:
    return [
        # Northeast: 1 beats everyone, 2 and 3 draw.
        result(1, 2, 2, 0),
        result(1, 3, 3, 1),
        result(2, 3, 1, 1),
        result(4, 1, 0, 1),
        # Southeast, never against Northeast.
        result(5, 6, 4, 0, SOUTHEAST),
        # Flex: 7 has no Homegrown conference; 8 is a pro academy.
        result(1, 7, 1, 1, TURNPIKE),
        result(8, 2, 0, 2, TURNPIKE),
        result(7, 8, 3, 0, TURNPIKE),
    ]


class FakeMatches:
    def __init__(self, rows: list[dict] | None = None, fail: bool = False) -> None:
        self.rows = default_results() if rows is None else rows
        self.fail = fail
        self.calls: list[dict] = []

    def get_season_results(self, season_id, age_group_id, league_ids, match_type_ids, statuses=(), include_test=False):
        self.calls.append(
            {
                "season_id": season_id,
                "age_group_id": age_group_id,
                "league_ids": list(league_ids),
                "match_type_ids": tuple(match_type_ids),
                "statuses": tuple(statuses),
                "include_test": include_test,
            }
        )
        if self.fail:
            raise RuntimeError("PostgREST down at db.internal:5432")
        ages = ("age_group_id", "home_age_group_id", "away_age_group_id")
        return [
            dict(r)
            for r in self.rows
            if age_group_id in (r.get(k) for k in ages)
            and r["league_id"] in league_ids
            and r["match_status"] in statuses
        ]

    def get_all_matches(self, *a, **k):
        raise AssertionError("leaderboards read with get_season_results: get_all_matches does not page")

    def team_has_matches_in_season(self, *a, **k):
        return True

    def get_standings(self, *a, **k):
        raise AssertionError("not used")

    def get_match_by_id(self, *a, **k):
        raise AssertionError("not used")


class FakeTeams:
    def get_all_teams(self):
        return [dict(t) for t in TEAMS]

    def resolve_team_by_name(self, name, league_id=None):
        return None


class FakeClubs:
    def get_all_clubs(self, include_team_counts=True):
        return [dict(c) for c in CLUBS]


class FakeLeagues:
    def __init__(self, fail: bool = False, leagues: list[dict] | None = None) -> None:
        self.fail, self.leagues = fail, LEAGUES if leagues is None else leagues

    def get_all_leagues(self, include_test=False):
        return [] if self.fail else [dict(lg) for lg in self.leagues]


FUTURE = {"id": 8, "name": "2027-2028", "start_date": "2027-08-01", "end_date": "2028-06-30"}
CURRENT = {"id": 7, "name": "2026-2027", "start_date": "2026-08-01", "end_date": "2027-06-30"}
PAST = {"id": 6, "name": "2025-2026", "start_date": "2025-09-01", "end_date": "2026-06-30"}


class FakeSeasons:
    """Like SeasonDAO: newest first; get_current_season None on a failed read."""

    def __init__(self, current: dict | None = CURRENT, seasons: list[dict] | None = None) -> None:
        self.current = current
        self.seasons = [CURRENT, PAST] if seasons is None else seasons

    def get_current_season(self):
        return dict(self.current) if self.current else None

    def get_all_seasons(self):
        return [dict(s) for s in self.seasons]


def deps(
    rows: list[dict] | None = None,
    *,
    fail: bool = False,
    leagues_fail: bool = False,
    leagues: list[dict] | None = None,
    seasons: FakeSeasons | None = None,
) -> ToolDeps:
    return ToolDeps(
        teams=FakeTeams(),
        clubs=FakeClubs(),
        leagues=FakeLeagues(fail=leagues_fail, leagues=leagues),
        matches=FakeMatches(rows, fail=fail),
        seasons=seasons or FakeSeasons(),
    )


def full_season() -> list[dict]:
    """default_results six times over: every team reaches MIN_GP and is ranked."""
    return [row for _ in range(6) for row in default_results()]

"""A small MOTW pool world for the Match of the Week tests (SB-1550, SB-1551).

MT's default data: scraped fixtures and results, no rosters, no logged goals.
"""

from datetime import UTC, date, datetime

from mt_ai.tools import ToolDeps

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


class FakeMotw:
    """Stands in for MotwDAO.list_for_week: {week_start: pick or [picks]}."""

    def __init__(self, picks: dict[str, dict | list[dict]] | None = None) -> None:
        self.picks = picks or {}

    def list_for_week(self, week_start: str, *, include_test: bool = False) -> list[dict]:
        got = self.picks.get(week_start)
        return got if isinstance(got, list) else ([got] if got else [])

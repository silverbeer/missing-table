"""Fake DAOs and a small MT world for the MT AI tool tests (SB-1142).

The default world follows MT's data reality (root CLAUDE.md): every team here
exists because the scraper made it. None has a manager, a roster or logged
events, and the tools must give full answers anyway.
"""

import copy
from typing import Any

REAL_HOMEGROWN, REAL_ACADEMY, REAL_FLEX, TEST_LEAGUE = 1, 2, 3, 9
U14, U15, U16 = 14, 15, 16

LEAGUE_NAMES = {REAL_HOMEGROWN: "Homegrown", REAL_ACADEMY: "Academy", REAL_FLEX: "Flex", TEST_LEAGUE: "TSC Test League"}


def reg(age: int, division: str | None, league_id: int) -> dict:
    """One team_mappings row, in the shape TeamDAO.get_all_teams returns it."""
    divisions = None
    if division:
        name = LEAGUE_NAMES[league_id]
        divisions = {
            "name": division,
            "league_id": league_id,
            "league_name": name,
            "leagues": {"id": league_id, "name": name, "sport_type": "soccer"},
        }
    return {"age_groups": {"id": age, "name": f"U{age}"}, "divisions": divisions}


def team(team_id: int, name: str, club_id: int | None, league_id: int, *mappings: dict) -> dict:
    return {
        "id": team_id,
        "name": name,
        "club_id": club_id,
        "league_id": league_id,
        "team_mappings": list(mappings),
        # get_all_teams also derives these; the tools must not rely on them (SB-1146).
        "age_groups": [m["age_groups"] for m in mappings],
    }


LEAGUES = [
    {"id": REAL_HOMEGROWN, "name": "Homegrown", "is_test": False},
    {"id": REAL_ACADEMY, "name": "Academy", "is_test": False},
    {"id": REAL_FLEX, "name": "Flex", "is_test": False},
    {"id": TEST_LEAGUE, "name": "TSC Test League", "is_test": True},
]

CLUBS = [
    {"id": 10, "name": "Boston United", "timezone": "America/New_York", "is_test": False},
    {"id": 11, "name": "IFA", "timezone": "America/New_York", "is_test": False},
    {"id": 12, "name": "LA Surf", "timezone": "America/Los_Angeles", "is_test": False},
    {"id": 13, "name": "TSC Club", "timezone": None, "is_test": True},
    {"id": 14, "name": "Nowhere FC", "timezone": "Not/AZone", "is_test": False},
]

TEAMS = [
    # Same name in two leagues — a real, legitimate ambiguity.
    team(100, "Boston United", 10, REAL_HOMEGROWN, reg(U15, "Northeast", REAL_HOMEGROWN)),
    team(101, "Boston United", 10, REAL_ACADEMY, reg(U15, "New England", REAL_ACADEMY)),
    # One team, two competitions at U15 — as IFA is in prod. Not ambiguous (SB-1146).
    team(102, "IFA", 11, REAL_HOMEGROWN, reg(U15, "Northeast", REAL_HOMEGROWN), reg(U15, "New England", REAL_FLEX)),
    team(103, "LA Surf", 12, REAL_HOMEGROWN, reg(U14, "Southwest", REAL_HOMEGROWN)),
    team(104, "TSC Test Team", 13, REAL_HOMEGROWN, reg(U15, None, REAL_HOMEGROWN)),
    team(105, "Test League Team", 11, TEST_LEAGUE, reg(U15, None, TEST_LEAGUE)),
    team(106, "No Ages FC", 11, REAL_HOMEGROWN),
    # Multi-age team.
    team(
        108, "NEFC", None, REAL_HOMEGROWN, reg(U16, "Northeast", REAL_HOMEGROWN), reg(U15, "Northeast", REAL_HOMEGROWN)
    ),
    # Real team with one registration in a test league's division.
    team(
        109,
        "Mixed Registrations",
        11,
        REAL_HOMEGROWN,
        reg(U15, "Northeast", REAL_HOMEGROWN),
        reg(U16, "TSC Division", TEST_LEAGUE),
    ),
    # Same age in a real and a test competition: only the real one is visible to real viewers.
    team(
        111,
        "Split Comp FC",
        11,
        REAL_HOMEGROWN,
        reg(U15, "Northeast", REAL_HOMEGROWN),
        reg(U15, "TSC Division", TEST_LEAGUE),
    ),
    team(110, "Nowhere FC", 14, REAL_HOMEGROWN, reg(U15, None, REAL_HOMEGROWN)),
]

ALIASES = {"intercontinental football academy": 102, "tsc alias": 104}


class FakeTeams:
    def __init__(self, teams: list[dict], aliases: dict[str, int], fail: bool = False) -> None:
        self.teams, self.aliases, self.fail = teams, aliases, fail
        self.resolve_calls: list[str] = []
        self.team_reads = 0  # one per search_teams call: counts tool executions

    def get_all_teams(self) -> list[dict]:
        self.team_reads += 1
        if self.fail:
            raise RuntimeError("PostgREST down")
        return copy.deepcopy(self.teams)

    def resolve_team_by_name(self, name: str, league_id: int | None = None) -> dict | None:
        self.resolve_calls.append(name)
        wanted = name.casefold()
        for team in self.teams:
            if team["name"].casefold() == wanted:
                return {"id": team["id"], "name": team["name"]}
        team_id = self.aliases.get(wanted)
        if team_id is None:
            return None
        team = next(t for t in self.teams if t["id"] == team_id)
        return {"id": team["id"], "name": team["name"]}


class FakeClubs:
    def __init__(self, clubs: list[dict]) -> None:
        self.clubs = clubs

    def get_all_clubs(self, include_team_counts: bool = True) -> list[dict]:
        return copy.deepcopy(self.clubs)


class FakeLeagues:
    """Like LeagueDAO: failures come back as [], not as an exception."""

    def __init__(self, leagues: list[dict], fail: bool = False) -> None:
        self.leagues, self.fail = leagues, fail

    def get_all_leagues(self, include_test: bool = False) -> list[dict]:
        if self.fail:
            return []
        return [lg for lg in copy.deepcopy(self.leagues) if include_test or not lg["is_test"]]


class FakeMatches:
    """Like MatchDAO.get_all_matches, including its swallow-errors default."""

    def __init__(self, rows: list[dict] | None = None, fail: bool = False) -> None:
        self.rows, self.fail = rows or [], fail
        self.calls: list[dict[str, Any]] = []

    def get_all_matches(
        self,
        season_id: int | None = None,
        age_group_id: int | None = None,
        division_id: int | None = None,
        team_id: int | None = None,
        match_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_test: bool = False,
        *,
        raise_on_error: bool = False,
    ) -> list[dict]:
        self.calls.append(
            {
                "team_id": team_id,
                "age_group_id": age_group_id,
                "start_date": start_date,
                "raise_on_error": raise_on_error,
            }
        )
        if self.fail:
            if raise_on_error:
                raise RuntimeError("PostgREST down")
            return []
        out = []
        for row in copy.deepcopy(self.rows):
            if team_id and team_id not in (row.get("home_team_id"), row.get("away_team_id")):
                continue
            if age_group_id and row.get("age_group_id") != age_group_id:
                continue
            if start_date and str(row.get("match_date", "")) < start_date:
                continue
            if row.pop("is_test", False) and not include_test:
                continue
            out.append(row)
        return out


def match_row(match_id: int, match_date: str, **overrides: Any) -> dict:
    """A get_all_matches row: IFA (102) at home to Boston United (100), scraped."""
    row = {
        "id": match_id,
        "match_date": match_date,
        "scheduled_kickoff": None,
        "home_team_id": 102,
        "away_team_id": 100,
        "home_team_name": "IFA",
        "away_team_name": "Boston United",
        "home_team_club": {"id": 11, "name": "IFA", "logo_url": None},
        "away_team_club": {"id": 10, "name": "Boston United", "logo_url": None},
        "age_group_id": U15,
        "age_group_name": "U15",
        "division_name": "Northeast",
        "match_type_name": "League",
        "league_name": "Homegrown",
        "match_status": "scheduled",
        "source": "match-scraper",
        "updated_at": "2026-09-20T12:00:00+00:00",
        "home_score": None,
        "away_score": None,
    }
    row.update(overrides)
    return row

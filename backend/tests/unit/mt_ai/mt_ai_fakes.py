"""Fake DAOs and a small MT world for the MT AI tool tests (SB-1142).

The default world follows MT's data reality (root CLAUDE.md): every team here
exists because the scraper made it. None has a manager, a roster or logged
events, and the tools must give full answers anyway.
"""

import copy
from typing import Any

REAL_HOMEGROWN, REAL_ACADEMY, TEST_LEAGUE = 1, 2, 9
U14, U15, U16 = 14, 15, 16


def _ages(*ids: int) -> list[dict]:
    return [{"id": i, "name": f"U{i}"} for i in ids]


LEAGUES = [
    {"id": REAL_HOMEGROWN, "name": "Homegrown", "is_test": False},
    {"id": REAL_ACADEMY, "name": "Academy", "is_test": False},
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
    {
        "id": 100,
        "name": "Boston United",
        "club_id": 10,
        "league_id": REAL_HOMEGROWN,
        "age_groups": _ages(U15),
        "divisions_by_age_group": {U15: {"name": "Northeast", "league_id": REAL_HOMEGROWN}},
    },
    {
        "id": 101,
        "name": "Boston United",
        "club_id": 10,
        "league_id": REAL_ACADEMY,
        "age_groups": _ages(U15),
        "divisions_by_age_group": {U15: {"name": "New England", "league_id": REAL_ACADEMY}},
    },
    {
        "id": 102,
        "name": "IFA",
        "club_id": 11,
        "league_id": REAL_HOMEGROWN,
        "age_groups": _ages(U15),
        "divisions_by_age_group": {U15: {"name": "Northeast", "league_id": REAL_HOMEGROWN}},
    },
    {
        "id": 103,
        "name": "LA Surf",
        "club_id": 12,
        "league_id": REAL_HOMEGROWN,
        "age_groups": _ages(U14),
        "divisions_by_age_group": {U14: {"name": "Southwest", "league_id": REAL_HOMEGROWN}},
    },
    {
        "id": 104,
        "name": "TSC Test Team",
        "club_id": 13,
        "league_id": REAL_HOMEGROWN,
        "age_groups": _ages(U15),
        "divisions_by_age_group": {},
    },
    {
        "id": 105,
        "name": "Test League Team",
        "club_id": 11,
        "league_id": TEST_LEAGUE,
        "age_groups": _ages(U15),
        "divisions_by_age_group": {},
    },
    {"id": 106, "name": "No Ages FC", "club_id": 11, "league_id": REAL_HOMEGROWN},
    # Multi-age team. Keys are strings: this is what a Redis cache hit returns.
    {
        "id": 108,
        "name": "NEFC",
        "club_id": None,
        "league_id": REAL_HOMEGROWN,
        "age_groups": _ages(U15, U16),
        "divisions_by_age_group": {
            str(U15): {"name": "Northeast", "league_id": REAL_HOMEGROWN},
            str(U16): {"name": "Northeast", "league_id": REAL_HOMEGROWN},
        },
    },
    # Real team with one registration in a test league's division.
    {
        "id": 109,
        "name": "Mixed Registrations",
        "club_id": 11,
        "league_id": REAL_HOMEGROWN,
        "age_groups": _ages(U15, U16),
        "divisions_by_age_group": {
            U15: {"name": "Northeast", "league_id": REAL_HOMEGROWN},
            U16: {"name": "TSC Division", "league_id": TEST_LEAGUE},
        },
    },
    {
        "id": 110,
        "name": "Nowhere FC",
        "club_id": 14,
        "league_id": REAL_HOMEGROWN,
        "age_groups": _ages(U15),
        "divisions_by_age_group": {},
    },
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

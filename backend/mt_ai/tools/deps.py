"""What the MT AI tools need from the data layer, and nothing more.

The tools depend on these Protocols rather than on the DAO classes, so tests
pass small hand-written fakes and the real DAOs satisfy them unchanged.
"""

from dataclasses import dataclass
from typing import Protocol


class TeamSource(Protocol):
    def get_all_teams(self) -> list[dict]: ...

    def resolve_team_by_name(self, name: str, league_id: int | None = None) -> dict | None: ...


class ClubSource(Protocol):
    def get_all_clubs(self, include_team_counts: bool = True) -> list[dict]: ...


class LeagueSource(Protocol):
    def get_all_leagues(self, include_test: bool = False) -> list[dict]: ...


class MatchSource(Protocol):
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
    ) -> list[dict]: ...

    def team_has_matches_in_season(self, team_id: int, season_id: int, include_test: bool = False) -> bool: ...

    def get_standings(
        self,
        season_id: int | None = None,
        age_group_id: int | None = None,
        division_id: int | None = None,
        match_type: str = "League",
        include_test: bool = False,
        *,
        raise_on_error: bool = False,
    ) -> dict: ...


class LiveMatchSource(Protocol):
    def get_live_match_state(self, match_id: int, include_test: bool = False) -> dict | None: ...


class MatchEventSource(Protocol):
    def get_key_events(self, match_id: int) -> list[dict] | None: ...


class RosterSource(Protocol):
    def get_player_by_id(self, player_id: int) -> dict | None: ...


class SeasonSource(Protocol):
    def get_current_season(self) -> dict | None: ...

    def get_all_seasons(self) -> list[dict]: ...


@dataclass(frozen=True)
class ToolDeps:
    teams: TeamSource
    clubs: ClubSource
    leagues: LeagueSource
    matches: MatchSource
    seasons: SeasonSource
    # get_live_match only (SB-1584). Optional so callers that never ask about a live
    # match don't need them; the tool reports "unavailable" without them.
    live: LiveMatchSource | None = None
    events: MatchEventSource | None = None
    roster: RosterSource | None = None


def dao_tool_deps() -> ToolDeps:
    """The production data sources: one shared Supabase connection, real DAOs."""
    # Imported here: the DAOs pull in Supabase and Redis, which the tool tests never need.
    from dao.club_dao import ClubDAO
    from dao.league_dao import LeagueDAO
    from dao.match_dao import MatchDAO, SupabaseConnection
    from dao.match_event_dao import MatchEventDAO
    from dao.roster_dao import RosterDAO
    from dao.season_dao import SeasonDAO
    from dao.team_dao import TeamDAO

    conn = SupabaseConnection()
    matches = MatchDAO(conn)
    return ToolDeps(
        teams=TeamDAO(conn),
        clubs=ClubDAO(conn),
        leagues=LeagueDAO(conn),
        matches=matches,
        seasons=SeasonDAO(conn),
        live=matches,
        events=MatchEventDAO(conn),
        roster=RosterDAO(conn),
    )

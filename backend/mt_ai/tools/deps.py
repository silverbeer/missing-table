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


@dataclass(frozen=True)
class ToolDeps:
    teams: TeamSource
    clubs: ClubSource
    leagues: LeagueSource
    matches: MatchSource

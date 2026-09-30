"""The set of teams a viewer may see, built from cached reads.

A team is test content (SB-85/SB-591) when its club or its own league is
flagged `is_test`; an age-group registration is test content when its
division's league is. Real viewers never see either — a tool that leaked a
test team would put CI's fake fixtures into a parent's answer.

Everything here comes from `@dao_cache`d DAO reads, so building the index costs
Redis lookups, not queries, on a warm cache.
"""

from dataclasses import dataclass, field
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.schemas import AgeGroupRef, Registration, TeamCandidate, Viewer

DEFAULT_TIMEZONE = "America/New_York"  # matches notifications/channel_resolver.py


class DataUnavailableError(Exception):
    """A read the tool depends on failed or returned something impossible."""


@dataclass(frozen=True)
class TeamIndex:
    teams: dict[int, dict] = field(default_factory=dict)  # visible teams only
    clubs: dict[int, dict] = field(default_factory=dict)
    leagues: dict[int, dict] = field(default_factory=dict)
    test_league_ids: frozenset[int] = frozenset()
    include_test: bool = False

    def club_name(self, team: dict) -> str | None:
        club = self.clubs.get(team.get("club_id") or 0)
        return club.get("name") if club else None

    def league_name(self, team: dict) -> str | None:
        league = self.leagues.get(team.get("league_id") or 0)
        return league.get("name") if league else team.get("league_name")

    def timezone(self, team: dict) -> ZoneInfo:
        club = self.clubs.get(team.get("club_id") or 0)
        name = (club or {}).get("timezone") or DEFAULT_TIMEZONE
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            return ZoneInfo(DEFAULT_TIMEZONE)

    def candidates(self, team: dict, age_group_name: str | None = None) -> list[TeamCandidate]:
        """One candidate per age group the team plays in (optionally just one age).

        Built from the raw `team_mappings` rows, one per (age group, division).
        A team in two competitions at one age — League and Flex — is one
        candidate with two registrations. `divisions_by_age_group`, a dict keyed
        by age group, keeps only one division per age, which made such a team
        look like two identical teams (SB-1146).

        A team with no visible registrations yields a single age-less
        candidate, unless a specific age was asked for — then it yields none.
        """
        by_age: dict[int, tuple[AgeGroupRef, list[Registration]]] = {}
        for mapping in team.get("team_mappings") or []:
            age = mapping.get("age_groups")
            if not age:
                continue
            if age_group_name and str(age.get("name", "")).casefold() != age_group_name.casefold():
                continue
            division = mapping.get("divisions") or {}
            if not self.include_test and division.get("league_id") in self.test_league_ids:
                continue
            ref, registrations = by_age.setdefault(age["id"], (AgeGroupRef(id=age["id"], name=age["name"]), []))
            if division:
                registration = Registration(league=_league_of(division), division=division.get("name"))
                if registration not in registrations:
                    registrations.append(registration)

        out = [self._candidate(team, ref, regs) for ref, regs in sorted(by_age.values(), key=_age_order)]
        if not out and not age_group_name and not team.get("team_mappings"):
            out.append(self._candidate(team, None, []))
        return out

    def _candidate(self, team: dict, age: AgeGroupRef | None, registrations: list[Registration]) -> TeamCandidate:
        return TeamCandidate(
            team_id=team["id"],
            name=team["name"],
            club_name=self.club_name(team),
            league_name=self.league_name(team),
            age_group=age,
            registrations=sorted(registrations, key=lambda r: (r.league or "", r.division or "")),
        )


def _league_of(division: dict) -> str | None:
    leagues = division.get("leagues")
    return (leagues or {}).get("name") or division.get("league_name")


def _age_order(item: tuple[AgeGroupRef, list[Registration]]) -> tuple[int, str]:
    """U9 before U13 before U19: numeric where the name has a number."""
    name = item[0].name
    digits = "".join(ch for ch in name if ch.isdigit())
    return (int(digits) if digits else 999, name)


def load_team_index(deps: ToolDeps, viewer: Viewer) -> TeamIndex:
    leagues = deps.leagues.get_all_leagues(include_test=True)
    if not leagues:
        # get_all_leagues swallows errors and returns []. MT always has leagues,
        # so empty means the read failed — and without it test teams can't be
        # told apart. Fail closed rather than risk showing them.
        raise DataUnavailableError("league list unavailable")
    clubs = deps.clubs.get_all_clubs(include_team_counts=False)

    test_league_ids = frozenset(lg["id"] for lg in leagues if lg.get("is_test"))
    test_club_ids = frozenset(c["id"] for c in clubs if c.get("is_test"))

    teams: dict[int, dict] = {}
    for team in deps.teams.get_all_teams():
        is_test = team.get("club_id") in test_club_ids or team.get("league_id") in test_league_ids
        if is_test and not viewer.include_test:
            continue
        teams[team["id"]] = team

    return TeamIndex(
        teams=teams,
        clubs={c["id"]: c for c in clubs},
        leagues={lg["id"]: lg for lg in leagues},
        test_league_ids=test_league_ids,
        include_test=viewer.include_test,
    )

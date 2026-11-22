"""Planning the teams and aliases a tournament needs before it is ingested (SB-1763).

Tournament ingest never creates a team: a name it cannot place becomes an
`ingest_failures` row (SB-1748). For an event the size of MLS NEXT Fest that
is hundreds of names, most of them a club's Academy side that MT only holds as
its Homegrown team. This module turns the list of names a tournament uses into
a report and a list of proposed actions for a person to review. Nothing here
is applied by planning, and nothing is applied until a reviewer marks it
`approved`.

Pure: no database, no DAO imports. Each name's verdict comes from the
resolver ingest itself uses (`TeamDAO.resolve_tournament_team`) and is handed
in, so "resolved" in a plan means what ingest will do. What is decided here is
only what to *propose* for a name that failed — and never from a near match:
similar names are shown to the reviewer, not acted on.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from dao.team_sides import (
    AMBIGUOUS,
    MISSING,
    RESOLVED,
    WRONG_SIDE,
    league_named,
    team_sides,
    top_level_league,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

# The message's age group is not one MT has: ingest drops the match before it
# looks at either team.
UNKNOWN_AGE_GROUP = "unknown_age_group"

ALIAS = "alias"
CREATE_TEAM = "create_team"
ACTION_TYPES = (ALIAS, CREATE_TEAM)

# A freshly generated plan holds only the first two. `approved` is written by
# the reviewer, by hand, and is the only status that is ever applied.
PROPOSED = "proposed"
NEEDS_REVIEW = "needs_review"
APPROVED = "approved"

NO_HINT = "no hint"

# A club's Academy-side team is stored as "<Club> Academy" ("IFA Academy",
# "FC Greater Boston Bolts Academy"). There is no such convention for a
# Homegrown-side team, so a name proposed for one is always for review.
CONVENTION_SIDE = "Academy"

_PLACEHOLDERS = frozenset({"tbd", "tba", "bye"})
# The select teams of a "Best Of" fixture: "East AD One", "West HD Two".
_SELECT_TEAM = re.compile(r"^(east|west|north|south|central) (ad|hd) \w+$")


class PlanInputError(ValueError):
    """The teams or brackets input is not in a shape this can read."""


def normalise(name: str | None) -> str:
    """A name with its whitespace collapsed, as the resolver reads it."""
    return " ".join((name or "").split())


def name_key(name: str | None) -> str:
    """What two spellings of one name share: no case, no extra whitespace."""
    return normalise(name).casefold()


def is_placeholder(name: str | None) -> bool:
    """Whether a name stands for a team not yet known, or for no club at all.

    `TBD` in a bracket slot, and the select sides of a showcase game. Neither
    is a team MT should hold, so neither gets an action.
    """
    key = name_key(name)
    return key in _PLACEHOLDERS or bool(_SELECT_TEAM.match(key))


@dataclass(frozen=True)
class Entry:
    """One name a tournament uses, at one age group, on one side."""

    name: str
    age_group: str
    league: str | None = None

    @property
    def key(self) -> tuple[str, str, str]:
        return (name_key(self.name), name_key(self.age_group), name_key(self.league))

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "age_group": self.age_group, "league": self.league}


@dataclass(frozen=True)
class Verdict:
    """What the resolver said about one entry.

    `candidate_ids` is the teams the resolver found for the name before the
    side guard — the team that owns the name on the other side, when the
    status is WRONG_SIDE.
    """

    status: str
    team_id: int | None = None
    reason: str | None = None
    candidate_ids: tuple[int, ...] = ()


@dataclass
class World:
    """What MT holds, as plain rows.

    `teams` rows carry `id`, `name`, `club_id`, `league_id` and `mappings`, a
    list of `(age_group_id, league_id)` — the league being the mapped
    division's. `leagues` maps id → a row with `name` and `parent_league_id`,
    `divisions` rows carry `id`, `name`, `league_id`, `clubs` maps id → name
    and `age_groups` maps id → name.
    """

    teams: list[dict] = field(default_factory=list)
    clubs: dict[int, str] = field(default_factory=dict)
    leagues: dict[int, dict] = field(default_factory=dict)
    divisions: list[dict] = field(default_factory=list)
    age_groups: dict[int, str] = field(default_factory=dict)

    def age_group_id(self, name: str | None) -> int | None:
        wanted = name_key(name)
        if not wanted:
            return None
        for age_group_id, age_name in self.age_groups.items():
            if name_key(age_name) == wanted:
                return age_group_id
        return None


# --- Reading the inputs -----------------------------------------------------


def _text(item: Mapping, key: str) -> str | None:
    value = item.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise PlanInputError(f"'{key}' must be text, not {type(value).__name__}")
    return normalise(value) or None


def parse_teams_input(items: Any) -> tuple[list[Entry], list[dict]]:
    """Read the `--teams` input into distinct entries and the matches it carries.

    A list whose items are either:

    - a scraper message, as `match-scraper-agent scrape-event --json` prints
      them: `home_team`, `away_team`, `age_group`, and optionally `league`
      and `competition`. Any other field is ignored.
    - a hand-made `{"name", "age_group", "league"}`, `league` optional.

    The two may be mixed. Entries are distinct by name, age group and league,
    compared without case or extra whitespace; the first spelling is kept.
    Returns `(entries, matches)`, `matches` being one
    `{"home": Entry, "away": Entry, "competition"}` per message.
    """
    if not isinstance(items, list):
        raise PlanInputError("the teams input must be a JSON list")

    entries: dict[tuple[str, str, str], Entry] = {}
    matches: list[dict] = []

    def keep(name: str | None, age_group: str | None, league: str | None, where: str) -> Entry:
        if not name:
            raise PlanInputError(f"{where}: a team name is missing")
        if not age_group:
            raise PlanInputError(f"{where}: 'age_group' is missing")
        entry = Entry(name, age_group, league)
        return entries.setdefault(entry.key, entry)

    for index, item in enumerate(items):
        where = f"teams[{index}]"
        if not isinstance(item, dict):
            raise PlanInputError(f"{where}: expected an object")
        try:
            age_group, league = _text(item, "age_group"), _text(item, "league")
            if "home_team" in item or "away_team" in item:
                home = keep(_text(item, "home_team"), age_group, league, where)
                away = keep(_text(item, "away_team"), age_group, league, where)
                matches.append({"home": home, "away": away, "competition": _text(item, "competition")})
            elif "name" in item:
                keep(_text(item, "name"), age_group, league, where)
            else:
                raise PlanInputError(f"{where}: expected 'home_team' and 'away_team', or 'name'")
        except PlanInputError as exc:
            if str(exc).startswith(where):
                raise
            raise PlanInputError(f"{where}: {exc}") from exc

    return list(entries.values()), matches


def parse_brackets_input(items: Any) -> list[dict]:
    """Read the `--brackets` input: which conference each team plays in.

    A list of `{"league", "conference", "age_group", "teams": [names]}` — one
    per league standings bracket. Only the shape is checked here; whether MT
    has the league and conference is decided against the database, and one it
    does not have is reported, never created.
    """
    if items is None:
        return []
    if not isinstance(items, list):
        raise PlanInputError("the brackets input must be a JSON list")

    brackets = []
    for index, item in enumerate(items):
        where = f"brackets[{index}]"
        if not isinstance(item, dict):
            raise PlanInputError(f"{where}: expected an object")
        try:
            row = {key: _text(item, key) for key in ("league", "conference", "age_group")}
        except PlanInputError as exc:
            raise PlanInputError(f"{where}: {exc}") from exc
        for key, value in row.items():
            if not value:
                raise PlanInputError(f"{where}: '{key}' is missing")
        teams = item.get("teams")
        if not isinstance(teams, list) or not all(isinstance(name, str) for name in teams):
            raise PlanInputError(f"{where}: 'teams' must be a list of names")
        row["teams"] = [normalise(name) for name in teams if normalise(name)]
        brackets.append(row)
    return brackets


# --- Planning ---------------------------------------------------------------


@dataclass
class _Group:
    """The failing entries that one action would fix: one name on one side."""

    name: str
    league_id: int | None
    league: str | None
    side: str | None
    entries: list[Entry] = field(default_factory=list)


class _Planner:
    def __init__(
        self,
        entries: list[Entry],
        verdicts: Mapping[tuple[str, str, str], Verdict],
        world: World,
        brackets: list[dict],
        near_matches: Callable[[str], list[dict]] | None,
    ):
        self.entries = entries
        self.verdicts = verdicts
        self.world = world
        self.near_matches = near_matches
        self.teams_by_id = {team["id"]: team for team in world.teams}
        self.teams_by_name: dict[str, list[dict]] = {}
        for team in world.teams:
            self.teams_by_name.setdefault(name_key(team.get("name")), []).append(team)
        self.clubs_by_name = {name_key(name): club_id for club_id, name in world.clubs.items()}
        self.actions: list[dict] = []
        # entry key → "alias_fixable" | "needs_create" | "unknown", for the report.
        self.outcome: dict[tuple[str, str, str], str] = {}
        self.unknown: list[dict] = []
        self.unknown_conferences: list[dict] = []
        self.conferences = self._index_brackets(brackets)

    # -- brackets --

    def _index_brackets(self, brackets: list[dict]) -> dict[tuple[str, str, str], list[dict]]:
        """(side, age group, name) → the conferences that name plays in there."""
        index: dict[tuple[str, str, str], list[dict]] = {}
        reported: set[tuple[str, str, str]] = set()

        def report(row: dict, reason: str) -> None:
            key = (name_key(row["league"]), name_key(row["conference"]), reason)
            if key not in reported:
                reported.add(key)
                self.unknown_conferences.append(
                    {"league": row["league"], "conference": row["conference"], "reason": reason}
                )

        for row in brackets:
            league_id = league_named(row["league"], self.world.leagues)
            if league_id is None:
                report(row, "MT has no league by that name")
                continue
            division = next(
                (
                    d
                    for d in self.world.divisions
                    if d.get("league_id") == league_id and name_key(d.get("name")) == name_key(row["conference"])
                ),
                None,
            )
            if division is None:
                report(row, "MT has no conference by that name in that league")
                continue
            if self.world.age_group_id(row["age_group"]) is None:
                report(row, f"MT has no age group '{row['age_group']}'")
                continue
            side = top_level_league(league_id, self.world.leagues)
            placement = {"league": self.world.leagues[league_id]["name"], "conference": division["name"]}
            for name in row["teams"]:
                found = index.setdefault((name_key(side), name_key(row["age_group"]), name_key(name)), [])
                if placement not in found:
                    found.append(placement)
        return index

    def _placements(self, group: _Group) -> list[dict]:
        placements = []
        for age_group in _age_groups(group.entries):
            for found in self.conferences.get((name_key(group.side), name_key(age_group), name_key(group.name)), []):
                placements.append({"age_group": age_group, **found})
        return placements

    # -- sides --

    def _sides(self, team: dict, age_group_ids: Iterable[int | None]) -> frozenset[str]:
        """Every side a team answers to at any of these age groups."""
        sides: set[str] = set()
        for age_group_id in age_group_ids:
            sides |= team_sides(team.get("mappings") or [], team.get("league_id"), age_group_id, self.world.leagues)
        return frozenset(sides)

    def _registered_on(self, team: dict, side: str) -> list[str]:
        """The age groups a team is registered at on this side, by name."""
        ages = {
            self.world.age_groups.get(age_group_id)
            for age_group_id, league_id in team.get("mappings") or []
            if name_key(top_level_league(league_id, self.world.leagues)) == name_key(side)
        }
        return sorted(age for age in ages if age)

    def _candidate(self, team: dict, side: str | None) -> dict:
        row = {"team_id": team["id"], "team_name": team.get("name")}
        if side:
            row["registered_age_groups"] = self._registered_on(team, side)
        return row

    # -- the plan --

    def run(self) -> None:
        groups: dict[tuple[str, int | None], _Group] = {}
        unhinted: dict[str, list[Entry]] = {}
        for entry in self.entries:
            verdict = self.verdicts[entry.key]
            if verdict.status not in (WRONG_SIDE, MISSING):
                continue
            if is_placeholder(entry.name):
                self._unknown(entry, "placeholder name, not a team")
                continue
            if not entry.league:
                unhinted.setdefault(name_key(entry.name), []).append(entry)
                continue
            league_id = league_named(entry.league, self.world.leagues)
            group = groups.setdefault(
                (name_key(entry.name), league_id),
                _Group(
                    name=entry.name,
                    league_id=league_id,
                    league=self.world.leagues[league_id]["name"],
                    side=top_level_league(league_id, self.world.leagues),
                ),
            )
            group.entries.append(entry)

        for group in groups.values():
            self._plan_group(group)
        for key, entries in unhinted.items():
            self._plan_unhinted(key, entries)
        for number, action in enumerate(self.actions, start=1):
            action["id"] = f"a{number:03d}"
        self._flag_clashes()

    def _flag_clashes(self) -> None:
        """Two actions that would make the same team, or the same club.

        The first keeps its status; each later one is for review, naming the
        action it clashes with. Applied as they stand, the second would be
        refused or would quietly share the first one's row.
        """
        for key, what in (("team_name", "team"), ("new_club_name", "club")):
            first: dict[str, str] = {}
            for action in self.actions:
                if action["type"] != CREATE_TEAM or not action.get(key):
                    continue
                earlier = first.setdefault(name_key(action[key]), action["id"])
                if earlier == action["id"]:
                    continue
                concern = f"action {earlier} proposes the same new {what}, '{normalise(action[key])}'"
                if action["status"] == PROPOSED:
                    action["status"] = NEEDS_REVIEW
                    action["reason"] = f"{action['reason']} Needs review: {concern}."
                else:
                    action["reason"] = f"{action['reason'].rstrip('.')}; {concern}."

    def _unknown(self, entry: Entry, reason: str) -> None:
        self.outcome[entry.key] = "unknown"
        self.unknown.append({**entry.as_dict(), "reason": reason})

    def _plan_group(self, group: _Group) -> None:
        age_group_ids = [self.world.age_group_id(entry.age_group) for entry in group.entries]
        candidate_ids = sorted(
            {team_id for entry in group.entries for team_id in self.verdicts[entry.key].candidate_ids}
        )
        owners = [self.teams_by_id[team_id] for team_id in candidate_ids if team_id in self.teams_by_id]

        if not owners:
            self._create_unknown(group)
            return

        if not any(self._sides(team, age_group_ids) for team in owners):
            ids = ", ".join(str(team["id"]) for team in owners)
            for entry in group.entries:
                self._unknown(
                    entry,
                    f"team {ids} has this name but no league or division registration: "
                    "register it rather than create another",
                )
            return

        club_ids = sorted({team["club_id"] for team in owners if team.get("club_id") is not None})
        owner_ids = {team["id"] for team in owners}
        siblings = [
            team
            for team in self.world.teams
            if team.get("club_id") in club_ids
            and team["id"] not in owner_ids
            and name_key(group.side) in {name_key(side) for side in self._sides(team, age_group_ids)}
        ]
        if siblings:
            self._alias(group, owners, siblings, age_group_ids)
        else:
            self._create_side_team(group, owners, club_ids)

    def _redirects(self, group: _Group, team_id: int | None) -> str | None:
        """Why a league-scoped alias for this name would change a name that works.

        The alias is rule 1 of the resolver at every age group, so it also
        moves any age group where the same name already resolves on this side.
        """
        moved = []
        for entry in self.entries:
            if name_key(entry.name) != name_key(group.name) or not entry.league:
                continue
            if league_named(entry.league, self.world.leagues) != group.league_id:
                continue
            verdict = self.verdicts[entry.key]
            if verdict.status == RESOLVED and verdict.team_id != team_id:
                moved.append(f"{entry.age_group} (team {verdict.team_id})")
        if not moved:
            return None
        return f"the name already resolves on this side at {', '.join(sorted(moved))}, and an alias would move it"

    def _base(self, kind: str, group: _Group) -> dict:
        return {
            "id": "",
            "type": kind,
            "status": PROPOSED,
            "reason": "",
            "external_name": normalise(group.name),
            "league": group.league,
        }

    def _finish(self, action: dict, group: _Group, outcome: str, concerns: list[str]) -> None:
        if concerns:
            action["status"] = NEEDS_REVIEW
            action["reason"] = f"{action['reason']} Needs review: {'; '.join(concerns)}."
        action["fixes"] = [{**entry.as_dict(), "status": self.verdicts[entry.key].status} for entry in group.entries]
        for entry in group.entries:
            self.outcome[entry.key] = outcome
        self.actions.append(action)

    def _alias(self, group: _Group, owners: list[dict], siblings: list[dict], age_group_ids: list) -> None:
        action = self._base(ALIAS, group)
        owner = owners[0]
        club = self.world.clubs.get(owner.get("club_id"), f"club {owner.get('club_id')}")
        concerns = []
        if len(siblings) == 1:
            target = siblings[0]
            action["team_id"] = target["id"]
            action["team_name"] = target.get("name")
            action["reason"] = (
                f"'{group.name}' is team {owner['id']} on the other side; {club} has one {group.side} "
                f"team, '{target.get('name')}' ({target['id']})."
            )
            if {name_key(side) for side in self._sides(target, age_group_ids)} != {name_key(group.side)}:
                concerns.append(f"team {target['id']} is registered on more than the {group.side} side")
            redirect = self._redirects(group, target["id"])
        else:
            action["team_id"] = None
            action["team_name"] = None
            action["reason"] = (
                f"'{group.name}' is team {owner['id']} on the other side; {club} has {len(siblings)} "
                f"{group.side} teams."
            )
            concerns.append("pick one of the candidates and set team_id and team_name")
            redirect = self._redirects(group, None)
        if redirect:
            concerns.append(redirect)
        action["candidates"] = [self._candidate(team, group.side) for team in sorted(siblings, key=lambda t: t["id"])]
        self._finish(action, group, "alias_fixable", concerns)

    def _team_name_concerns(self, team_name: str) -> list[str]:
        taken = self.teams_by_name.get(name_key(team_name)) or []
        if not taken:
            return []
        ids = ", ".join(str(team["id"]) for team in taken)
        return [f"the name '{team_name}' is already taken by team {ids}"]

    def _create_base(self, group: _Group) -> tuple[dict, list[str]]:
        """A create action, in the side's own league.

        `teams.league_id` is the side, never a child league: a hint of Flex
        makes a Homegrown team, and that is said.
        """
        action = self._base(CREATE_TEAM, group)
        action["league"] = group.side
        concerns = []
        if name_key(group.league) != name_key(group.side):
            concerns.append(f"the feed says {group.league}; the team and its alias are made in {group.side}")
        return action, concerns

    def _create_side_team(self, group: _Group, owners: list[dict], club_ids: list[int]) -> None:
        action, concerns = self._create_base(group)
        owner = owners[0]
        if len(club_ids) == 1:
            club_name = self.world.clubs.get(club_ids[0]) or normalise(group.name)
            action.update(club_id=club_ids[0], club_name=club_name, new_club_name=None)
            action["reason"] = (
                f"'{group.name}' is team {owner['id']} on the other side; {club_name} has no {group.side} team."
            )
        else:
            club_name = normalise(group.name)
            action.update(club_id=None, club_name=None, new_club_name=club_name)
            action["reason"] = f"'{group.name}' is team {owner['id']} on the other side."
            if club_ids:
                ids = ", ".join(map(str, club_ids))
                concerns.append(f"teams with this name belong to clubs {ids}: set club_id and club_name")
            else:
                concerns.append(f"team {owner['id']} has no club: set club_id and club_name, or accept a new club")

        action["team_name"] = f"{club_name} {group.side}"
        if name_key(group.side) != name_key(CONVENTION_SIDE):
            concerns.append(f"there is no naming convention for a {group.side}-side team")
        if name_key(club_name).endswith(name_key(group.side)):
            concerns.append(f"the club's name already ends in '{group.side}'")
        concerns += self._team_name_concerns(action["team_name"])
        redirect = self._redirects(group, None)
        if redirect:
            concerns.append(redirect)
        self._place(action, group)
        self._finish(action, group, "needs_create", concerns)

    def _create_unknown(self, group: _Group) -> None:
        """A name MT has no team for. A new club and team, always for review."""
        action, concerns = self._create_base(group)
        name = normalise(group.name)
        club_id = self.clubs_by_name.get(name_key(name))
        concerns.append("MT has no team by this name: check the near matches before creating one")
        if club_id is not None:
            action.update(club_id=club_id, club_name=self.world.clubs[club_id], new_club_name=None)
            action["reason"] = f"MT has no team named '{name}'; the club exists ({club_id}) with no such team."
        else:
            action.update(club_id=None, club_name=None, new_club_name=name)
            action["reason"] = f"MT has no team or club named '{name}'."
        if group.league is None:
            concerns.append("the feed names no side: the team gets no league unless one is set")
        action["team_name"] = name
        concerns += self._team_name_concerns(name)
        self._place(action, group)
        action["near_matches"] = list(self.near_matches(name)) if self.near_matches else []
        self._finish(action, group, "needs_create", concerns)

    def _place(self, action: dict, group: _Group) -> None:
        action["age_groups"] = _age_groups(group.entries)
        action["placements"] = self._placements(group) if group.side else []

    def _plan_unhinted(self, key: str, entries: list[Entry]) -> None:
        """Names sent with no side that MT has no team for.

        With no hint a single team by the name is the answer, so a team
        created for the same name on one side fixes these too. Two would make
        it ambiguous, and that is said rather than planned.
        """
        creating = [
            action for action in self.actions if action["type"] == CREATE_TEAM and name_key(action["team_name"]) == key
        ]
        if len(creating) == 1:
            action = creating[0]
            action["fixes"] += [{**entry.as_dict(), "status": self.verdicts[entry.key].status} for entry in entries]
            for entry in entries:
                self.outcome[entry.key] = "needs_create"
            return
        if creating:
            for entry in entries:
                self._unknown(entry, "sent with no side, and the plan creates a team by this name on each side")
            return
        group = _Group(name=entries[0].name, league_id=None, league=None, side=None, entries=list(entries))
        self._create_unknown(group)


def _age_groups(entries: Iterable[Entry]) -> list[str]:
    seen: dict[str, str] = {}
    for entry in entries:
        seen.setdefault(name_key(entry.age_group), entry.age_group)
    return sorted(seen.values())


def side_label(league: str | None) -> str:
    """The report's row for an entry: its league as sent, or "no hint"."""
    return normalise(league) or NO_HINT


def build_plan(
    entries: list[Entry],
    matches: list[dict],
    verdicts: Mapping[tuple[str, str, str], Verdict],
    world: World,
    brackets: list[dict] | None = None,
    near_matches: Callable[[str], list[dict]] | None = None,
) -> dict:
    """The report and the proposed actions for a tournament's team names.

    `verdicts` maps each entry's `key` to what the resolver said about it.
    `near_matches` is asked for teams with a similar name, only for a name MT
    has no team for; what it returns is shown to the reviewer and never acted
    on. Returns `{"report", "actions"}`, both plain JSON-ready data.
    """
    planner = _Planner(entries, verdicts, world, brackets or [], near_matches)
    planner.run()

    sides: dict[str, dict] = {}
    ambiguous = []
    for entry in entries:
        verdict = verdicts[entry.key]
        side = sides.setdefault(
            side_label(entry.league),
            {
                "entries": 0,
                "resolved": 0,
                "ambiguous": 0,
                "missing": {"total": 0, "alias_fixable": 0, "needs_create": 0, "unknown": 0},
                "unknown_league": 0,
                "unknown_age_group": 0,
                "resolver": {"wrong_side": 0, "missing": 0},
            },
        )
        side["entries"] += 1
        if verdict.status in (WRONG_SIDE, MISSING):
            side["resolver"][verdict.status] += 1
            side["missing"]["total"] += 1
            side["missing"][planner.outcome[entry.key]] += 1
        else:
            side[verdict.status] += 1
        if verdict.status == AMBIGUOUS:
            ambiguous.append({**entry.as_dict(), "reason": verdict.reason})

    fixed = {
        (name_key(fix["name"]), name_key(fix["age_group"]), name_key(fix["league"]))
        for action in planner.actions
        for fix in action["fixes"]
    }

    def lands(entry: Entry, after: bool) -> bool:
        return verdicts[entry.key].status == RESOLVED or (after and entry.key in fixed)

    match_report = None
    if matches:
        match_report = {
            "total": len(matches),
            "would_land": sum(lands(m["home"], False) and lands(m["away"], False) for m in matches),
            "would_land_after_plan": sum(lands(m["home"], True) and lands(m["away"], True) for m in matches),
        }

    placed: dict[tuple[str, str], dict] = {}
    unplaced = 0
    for action in planner.actions:
        if action["type"] != CREATE_TEAM:
            continue
        if not action["placements"]:
            unplaced += 1
        for league, conference in {(p["league"], p["conference"]) for p in action["placements"]}:
            row = placed.setdefault(
                (league, conference), {"league": league, "conference": conference, "teams": 0, "registrations": 0}
            )
            row["teams"] += 1
            row["registrations"] += sum(
                1 for p in action["placements"] if (p["league"], p["conference"]) == (league, conference)
            )

    counts: dict[str, dict[str, int]] = {kind: {PROPOSED: 0, NEEDS_REVIEW: 0} for kind in ACTION_TYPES}
    for action in planner.actions:
        counts[action["type"]][action["status"]] += 1

    report = {
        "entries": len(entries),
        "sides": sides,
        "matches": match_report,
        "conferences": {
            "placed": sorted(placed.values(), key=lambda row: (row["league"], row["conference"])),
            "unplaced": unplaced,
            "unknown": planner.unknown_conferences,
        },
        "ambiguous": ambiguous,
        "unknown": planner.unknown,
        "actions": counts,
    }
    return {"report": report, "actions": planner.actions}


def plan_id_for(actions: list[dict], generated_at: str) -> str:
    """A name for a plan: when it was made, and a digest of what it proposes."""
    digest = hashlib.sha256(json.dumps(actions, sort_keys=True).encode()).hexdigest()[:8]
    stamp = re.sub(r"[^0-9T]", "", generated_at.split(".")[0].split("+")[0])
    return f"plan-{stamp}-{digest}"


# --- Reading a reviewed plan back -------------------------------------------


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(normalise(value))


def action_error(action: Any) -> str | None:
    """Why an action from a plan file cannot be read, or None if it can.

    A plan file is edited by hand between planning and applying, so every
    field is checked rather than trusted.
    """
    if not isinstance(action, dict):
        return "not an object"
    kind = action.get("type")
    if kind not in ACTION_TYPES:
        return f"unknown action type '{kind}'"
    if not _is_text(action.get("external_name")):
        return "external_name is missing"
    league = action.get("league")
    if league is not None and not _is_text(league):
        return "league must be a league name or null"
    fixes = action.get("fixes", [])
    if not isinstance(fixes, list) or not all(
        isinstance(fix, dict) and _is_text(fix.get("name")) and _is_text(fix.get("age_group")) for fix in fixes
    ):
        return "fixes must be a list of {name, age_group, league, status}"
    if any(name_key(fix["name"]) != name_key(action["external_name"]) for fix in fixes):
        return "every entry in fixes must be for external_name"

    if kind == ALIAS:
        if league is None:
            return "an alias needs a league"
        team_id = action.get("team_id")
        if not isinstance(team_id, int) or isinstance(team_id, bool):
            return "team_id is not set"
        if not _is_text(action.get("team_name")):
            return "team_name is not set: it must name the team team_id refers to"
        return None

    if not _is_text(action.get("team_name")):
        return "team_name is missing"
    club_id, new_club_name = action.get("club_id"), action.get("new_club_name")
    if club_id is not None and (not isinstance(club_id, int) or isinstance(club_id, bool)):
        return "club_id must be a club id or null"
    if club_id is None and not _is_text(new_club_name):
        return "one of club_id and new_club_name must be set"
    if club_id is not None and new_club_name:
        return "club_id and new_club_name are both set: keep one"
    if club_id is not None and not _is_text(action.get("club_name")):
        return "club_name is not set: it must name the club club_id refers to"
    placements = action.get("placements", [])
    if not isinstance(placements, list) or not all(
        isinstance(p, dict) and all(_is_text(p.get(key)) for key in ("age_group", "league", "conference"))
        for p in placements
    ):
        return "placements must be a list of {age_group, league, conference}"
    return None


def is_approved(action: Any) -> bool:
    """Whether a reviewer approved this action. Nothing else is ever applied."""
    return isinstance(action, dict) and action.get("status") == APPROVED


def applicable(actions: Iterable[Any]) -> list[dict]:
    """The actions of a plan that may be applied: the approved ones."""
    return [action for action in actions if is_approved(action)]


def read_plan(plan: Any) -> dict:
    """A plan file's content, checked for the two things apply needs.

    Raises PlanInputError for something that is not a plan at all. An action
    that is individually unreadable is left in: apply refuses it by itself,
    with the reason, rather than the whole file.
    """
    if not isinstance(plan, dict):
        raise PlanInputError("a plan must be a JSON object")
    if not _is_text(plan.get("plan_id")):
        raise PlanInputError("the plan has no plan_id")
    if not isinstance(plan.get("actions"), list):
        raise PlanInputError("the plan has no actions list")
    return plan

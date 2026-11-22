"""Which side of the youth pyramid a team is on (SB-1748).

MLS NEXT Fest puts the Homegrown Division and the Academy Division in one
event, and many clubs field a team on each side under the same name. A
tournament message says which side it means (`league`: "Homegrown" or
"Academy"); this module decides whether a team found by name is on that side.

Pure: no database, no DAO imports. The DAO fetches rows and hands them here,
so every rule below is tested without one.

`teams.league_id` alone cannot be the test — Homegrown clubs carry Flex there
and MLS academies carry NULL — so a team's side is read from where it is
registered to play (`team_mappings`), with `teams.league_id` only as a
fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

RESOLVED = "resolved"
AMBIGUOUS = "ambiguous"
WRONG_SIDE = "wrong_side"
MISSING = "missing"
# The message's league is not one MT has: nothing about the team was looked up.
UNKNOWN_LEAGUE = "unknown_league"


@dataclass(frozen=True)
class Candidate:
    """A team a name could refer to, with the sides it plays on.

    `sides_at_age` is the part of `sides` read from its registrations at the
    message's age group itself; empty when `sides` is the every-age fallback.
    """

    team_id: int
    sides: frozenset[str]
    sides_at_age: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Resolution:
    """What a name resolved to. `team_id` is set only when status is RESOLVED.

    `reason` is for the ingest failure row an admin reads, never for a client.
    """

    status: str
    team_id: int | None = None
    reason: str | None = None


def top_level_league(league_id: int | None, leagues: Mapping[int, Mapping]) -> str | None:
    """The name of the league at the top of `league_id`'s parent chain.

    A child league is folded into its parent (Flex → Homegrown). `leagues`
    maps id → a row with `name` and `parent_league_id`. None for no league or
    one the map does not have.
    """
    seen: set[int] = set()
    current = league_id
    while current is not None and current in leagues and current not in seen:
        seen.add(current)
        parent = leagues[current].get("parent_league_id")
        if parent is None or parent not in leagues:
            return leagues[current].get("name")
        current = parent
    # A parent chain that loops has no top; name where the walk stopped.
    return leagues[current].get("name") if current in leagues else None


def league_named(hint: str | None, leagues: Mapping[int, Mapping]) -> int | None:
    """The id of the league a message's `league` names, or None if MT has none.

    Compared whole, without case or padding. Never a pattern and never a
    nearest match: "HD" is not Homegrown.
    """
    wanted = (hint or "").strip().casefold()
    if not wanted:
        return None
    for league_id, row in leagues.items():
        if (row.get("name") or "").strip().casefold() == wanted:
            return league_id
    return None


def _fold(league_ids: Iterable[int | None], leagues: Mapping[int, Mapping]) -> frozenset[str]:
    names = (top_level_league(league_id, leagues) for league_id in league_ids)
    return frozenset(name for name in names if name)


def sides_at_age(
    mappings: Iterable[tuple[int | None, int | None]],
    age_group_id: int | None,
    leagues: Mapping[int, Mapping],
) -> frozenset[str]:
    """The top-level leagues of a team's divisions at one age group.

    Empty when it has no registration there, or the age group is unknown.
    """
    if age_group_id is None:
        return frozenset()
    return _fold((league for age, league in mappings if league is not None and age == age_group_id), leagues)


def team_sides(
    mappings: Iterable[tuple[int | None, int | None]],
    team_league_id: int | None,
    age_group_id: int | None,
    leagues: Mapping[int, Mapping],
) -> frozenset[str]:
    """The top-level leagues a team plays in at an age group.

    `mappings` is the team's registrations as `(age_group_id, league_id)`,
    the league being that of the mapped division.

    At `age_group_id`, the answer is the leagues of its divisions at that age.
    A team with none there falls back to its registrations at every age plus
    `teams.league_id`. Empty when nothing says which side it is on.
    """
    rows = [(age, league) for age, league in mappings if league is not None]
    at_age = sides_at_age(rows, age_group_id, leagues)
    if at_age:
        return at_age
    return _fold([*(league for _, league in rows), team_league_id], leagues)


def classify(candidates: Iterable[Candidate], hint: str | None) -> Resolution:
    """Pick the candidate on the hinted side, or say why none can be picked.

    With a hint, only candidates whose sides include it count: one is the
    answer, several are ambiguous, none means the name exists only on the
    other side. With no hint there is nothing to tell candidates apart, so one
    candidate is the answer and several are ambiguous. Never a guess.

    A candidate registered on the hinted side *and* another at the message's
    age group does not count as on that side: the registrations cannot say
    which of the two it is, and taking it is how an Academy fixture lands on a
    Homegrown team. A candidate cleanly on the hinted side beats it; with
    none, the name is ambiguous and the reason names the team.
    """
    unique: dict[int, Candidate] = {}
    for candidate in candidates:
        unique.setdefault(candidate.team_id, candidate)
    found = list(unique.values())
    if not found:
        return Resolution(MISSING)

    wanted = (hint or "").strip()
    if not wanted:
        if len(found) == 1:
            return Resolution(RESOLVED, team_id=found[0].team_id)
        return Resolution(AMBIGUOUS, reason=_ambiguous(found))

    def includes(sides: frozenset[str]) -> bool:
        return wanted.casefold() in {side.casefold() for side in sides}

    on_side = [c for c in found if includes(c.sides)]
    both = [c for c in on_side if includes(c.sides_at_age) and len(c.sides_at_age) > 1]
    clean = [c for c in on_side if c not in both]
    if len(clean) == 1:
        return Resolution(RESOLVED, team_id=clean[0].team_id)
    if clean:
        return Resolution(AMBIGUOUS, reason=_ambiguous(clean))
    if both:
        return Resolution(AMBIGUOUS, reason=_on_both_sides(both))

    elsewhere = sorted({side for c in found for side in c.sides})
    if not elsewhere:
        return Resolution(WRONG_SIDE, reason="wrong side: team has no league or division registration")
    return Resolution(WRONG_SIDE, reason=f"wrong side: exists as {', '.join(elsewhere)}")


def _ambiguous(candidates: Iterable[Candidate]) -> str:
    ids = ", ".join(str(team_id) for team_id in sorted(c.team_id for c in candidates))
    return f"ambiguous: team ids {ids}"


def _on_both_sides(candidates: Iterable[Candidate]) -> str:
    parts = []
    for candidate in sorted(candidates, key=lambda c: c.team_id):
        *rest, last = sorted(candidate.sides_at_age)
        sides = f"{', '.join(rest)} and {last}"
        parts.append(f"team {candidate.team_id} is registered as both {sides} at this age group")
    return f"ambiguous: {'; '.join(parts)}"

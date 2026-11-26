"""Matchup: both teams of one match, each inside its own tables (SB-1782).

Fest matches pair teams from different conferences, so a match preview's common
opponents and head-to-head are mostly empty. The matchup puts the two team
dossiers side by side for a Scouting tab, and never compares across them: each
side is described in its own conference tables (`team_dossier`), and its badges
come from the cross-conference stat boards (`leaderboards`), which are stat
boards, not rankings.

Two layers, so the rules are testable without a database:

- **Gathering** (`get_matchup`) reads the match, one dossier per side, the stat
  boards and the two teams' previous meetings through `ToolDeps`.
- **Rules** (`stakes_for`, `shares_conference`, `badges_from`, `meetings_from`)
  are pure functions over plain values.

## Sides

Each side is `get_team_dossier(..., for_match_id=match_id)`, so it carries its
season age and whether it is playing up. One side's dossier error is that
side's `dossier.error`: it never fails the call or blanks the other side.

## Badges

Per side, the boards of each top-level league the team is registered in at its
**season age** (a Flex conference counts as its parent, Homegrown), read once
per (league, age) for the call; test leagues are skipped. A badge is a board
where the team ranks in the top `BADGE_RANK` and in the top third of the board's
`ranked_count` (teams with `MIN_GP` games), so never "8th of 8"; a 0 on a count
board (points, goals, unbeaten, pro wins) is no badge. At most `MAX_BADGES` per
team, best rank first, then board order. Badges are null when the boards could
not be read, [] when the team is on none (or its league has no boards).

## Conference and stakes

`shares_conference` is whether the dossiers share a table (a division id); null
when either dossier failed. `scouting_relevant`: a tournament match, or two teams
known not to share a conference. `stakes` is null outside a tournament, "group"
in a group stage, "none" for a showcase, consolation, third-place or placement
final, and "elimination" for every other knockout round.

## Previous meetings

Played matches between the two teams at the match's age group, every season,
newest first; the score is this match's home team first. Null when the read
failed.

Badge fact ids are `t<team>:a<age>:board:<league_id>:<key>`, with the season age.
"""

from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Literal

import structlog
from pydantic import BaseModel

from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.schemas import AgeGroupRef, ToolError, Viewer
from mt_ai.tools.visibility import DataUnavailableError, TeamIndex, load_team_index
from mt_tools.leaderboards import NOT_A_RANKING, Board, LeaderboardsResult, get_leaderboards
from mt_tools.motw_candidates import PLAYED_STATUSES
from mt_tools.team_dossier import TeamDossierResult, get_team_dossier, visible_mappings

logger = structlog.get_logger()

BADGE_RANK = 10
MAX_BADGES = 3
# Boards where 0 is nothing to show: "1st with 0 wins over pro academies" is no badge.
# (Fewest goals against is not here: 0 is the best there.)
ZERO_IS_NOTHING = frozenset({"pts", "ppg", "gf", "gf_pg", "unbeaten", "pro_wins"})
UNAVAILABLE = "The matchup is unavailable right now."

Stakes = Literal["none", "group", "elimination"]

NO_STAKES_ROUNDS = frozenset({"showcase", "consolation", "placement_final", "third_place"})
GROUP_ROUNDS = frozenset({"group_stage"})
ELIMINATION_ROUNDS = frozenset(
    {
        "round_of_32",
        "round_of_16",
        "quarterfinal",
        "semifinal",
        "final",
        "wildcard",
        "silver_semifinal",
        "bronze_semifinal",
        "silver_final",
        "bronze_final",
    }
)


# --- result models -----------------------------------------------------------


class MatchupTournament(BaseModel):
    id: int
    name: str | None = None


class MatchupMatch(BaseModel):
    id: int
    date: date
    age_group: AgeGroupRef  # the bracket: a side playing up is younger
    tournament: MatchupTournament | None = None
    tournament_round: str | None = None
    stakes: Stakes | None = None  # null: not a tournament match, or an unknown round


class Badge(BaseModel):
    """A stat board the team is near the top of. A stat board, not a ranking."""

    board: str  # the board key, e.g. "gf_pg"
    title: str
    league_id: int
    league: str
    age_group: str  # the team's season age, not the bracket
    rank: int
    of: int  # teams the board ranks (MIN_GP games)
    value: int | float | None = None
    fact_id: str
    text: str


class MatchupSide(BaseModel):
    dossier: TeamDossierResult
    # Null: the boards could not be read. []: on no board's top BADGE_RANK.
    badges: list[Badge] | None = None
    badges_note: str | None = None  # the boards' coverage note, verbatim


class Meeting(BaseModel):
    match_id: int
    date: date
    season: str | None = None
    score: str  # this match's home team first
    competition: str | None = None


class MatchupResult(BaseModel):
    """Both sides of one match, each in its own tables.

    `home` and `away` are null only with `error`, when the match itself could not
    be read; a side whose dossier failed carries its own `dossier.error`.
    """

    match: MatchupMatch | None = None
    shares_conference: bool | None = None
    scouting_relevant: bool = False
    home: MatchupSide | None = None
    away: MatchupSide | None = None
    previous_meetings: list[Meeting] | None = None
    error: ToolError | None = None


# --- pure rules ----------------------------------------------------------------


def stakes_for(tournament_id: int | None, round_name: str | None) -> Stakes | None:
    if tournament_id is None or not round_name:
        return None
    if round_name in GROUP_ROUNDS:
        return "group"
    if round_name in NO_STAKES_ROUNDS:
        return "none"
    if round_name in ELIMINATION_ROUNDS:
        return "elimination"
    return None


def shares_conference(home: TeamDossierResult, away: TeamDossierResult) -> bool | None:
    """Whether the two teams share a table; null when either dossier could not be built."""
    if home.error or away.error or home.conferences is None or away.conferences is None:
        return None
    return bool({c.division.id for c in home.conferences} & {c.division.id for c in away.conferences})


def _ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _value_text(board: Board, value) -> str:
    if value is None:
        return ""
    if board.variant == "per_game":
        return f" ({value:.2f})"
    return f" ({value})"


def badge_cutoff(ranked_count: int) -> int:
    """The worst rank that is a badge: the top BADGE_RANK, and never below the top third."""
    return min(BADGE_RANK, ranked_count // 3)


def badge_label(rank: int, age_name: str, league: str, title: str, of: int) -> str:
    """'2nd in U15 Homegrown goals for per game, of 134 teams': the title's case, but its first letter."""
    teams = "team" if of == 1 else "teams"
    return f"{_ordinal(rank)} in {age_name} {league} {title[:1].lower()}{title[1:]}, of {of} {teams}"


def badges_from(
    team_id: int, team_name: str, age: AgeGroupRef, league_id: int, league: str, boards: Iterable[Board]
) -> list[Badge]:
    """Every board of one league where the team is in the top third and the top BADGE_RANK, in board order."""
    out: list[Badge] = []
    for board in boards:
        row = next((r for r in board.rows if r.team.id == team_id and r.rank is not None), None)
        if row is None or row.rank > badge_cutoff(board.ranked_count):
            continue
        if board.key in ZERO_IS_NOTHING and not row.value:
            continue
        label = badge_label(row.rank, age.name, league, board.title, board.ranked_count)
        out.append(
            Badge(
                board=board.key,
                title=board.title,
                league_id=league_id,
                league=league,
                age_group=age.name,
                rank=row.rank,
                of=board.ranked_count,
                value=row.value,
                fact_id=f"t{team_id}:a{age.id}:board:{league_id}:{board.key}",
                text=f"{team_name}: {label}{_value_text(board, row.value)}. {NOT_A_RANKING}",
            )
        )
    return out


def best_badges(badges: list[Badge]) -> list[Badge]:
    """At most MAX_BADGES, best rank first; `badges` arrive in board order, which breaks ties."""
    return sorted(badges, key=lambda b: b.rank)[:MAX_BADGES]


def meetings_from(rows: Iterable[dict], match: dict) -> list[Meeting]:
    """The two teams' played meetings at the match's age group, newest first, this match excluded."""
    home, away = match["home_team_id"], match["away_team_id"]
    out: list[Meeting] = []
    for m in rows:
        if m.get("id") == match["id"] or {m.get("home_team_id"), m.get("away_team_id")} != {home, away}:
            continue
        if m.get("age_group_id") != match.get("age_group_id") or m.get("match_status") not in PLAYED_STATUSES:
            continue
        hs, as_ = m.get("home_score"), m.get("away_score")
        if hs is None or as_ is None:
            continue
        ours, theirs = (hs, as_) if m["home_team_id"] == home else (as_, hs)
        out.append(
            Meeting(
                match_id=m["id"],
                date=_date(m["match_date"]),
                season=m.get("season_name"),
                score=f"{ours}-{theirs}",
                competition=m.get("match_type_name"),
            )
        )
    return sorted(out, key=lambda x: (x.date, x.match_id), reverse=True)


# --- gathering -----------------------------------------------------------------


class _InvalidArgsError(Exception):
    pass


def _date(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _is_test(index: TeamIndex, league: dict) -> bool:
    return bool(league.get("is_test")) or league.get("id") in index.test_league_ids


def top_leagues(index: TeamIndex, team_id: int, dossier: TeamDossierResult) -> list[tuple[int, str]]:
    """(id, name) of the top-level leagues of the team's tables (Flex counts as Homegrown).

    Test leagues are skipped for every viewer: the stat boards never count them.
    """
    team = index.teams.get(team_id)
    if team is None or not dossier.conferences or dossier.age_group is None:
        return []
    divisions = {c.division.id for c in dossier.conferences}
    out: list[tuple[int, str]] = []
    for m in visible_mappings(team, index):
        division = m.get("divisions") or {}
        if m["age_groups"]["id"] != dossier.age_group.id or division.get("id") not in divisions:
            continue
        league = index.leagues.get(division.get("league_id") or 0)
        if league and not _is_test(index, league) and league.get("parent_league_id") is not None:
            league = index.leagues.get(league["parent_league_id"])
        if not league or _is_test(index, league) or not league.get("name"):
            continue
        entry = (league["id"], str(league["name"]))
        if entry not in out:
            out.append(entry)
    return out


def _side(
    deps: ToolDeps,
    team_id: int,
    dossier: TeamDossierResult,
    index: TeamIndex | None,
    boards: dict[tuple[str, str], LeaderboardsResult],
) -> MatchupSide:
    if dossier.error or dossier.team is None or dossier.age_group is None or index is None:
        return MatchupSide(dossier=dossier)
    age = dossier.age_group  # the season age: the dossier's, never the bracket
    found: list[Badge] = []
    notes: list[str] = []
    for league_id, league in top_leagues(index, team_id, dossier):
        key = (league, age.name)
        if key not in boards:
            boards[key] = get_leaderboards(
                deps, league, age.name, dossier.season.name if dossier.season else None, limit=BADGE_RANK
            )
        result = boards[key]
        if result.error and result.error.kind == "invalid_args":
            # No boards for this league or age (not a top-level league, an age it
            # has no registrations at): nothing to rank in, not a failed read.
            continue
        if result.error or result.boards is None:
            logger.warning("matchup_badges_unavailable", team_id=team_id, league=league, age_group=age.name)
            return MatchupSide(dossier=dossier)
        found.extend(badges_from(team_id, dossier.team.name, age, league_id, league, result.boards))
        if result.coverage and result.coverage.note not in notes:
            notes.append(result.coverage.note)
    return MatchupSide(dossier=dossier, badges=best_badges(found), badges_note=" ".join(notes) or None)


def get_matchup(deps: ToolDeps, match_id: int, *, viewer: Viewer, now: datetime | None = None) -> MatchupResult:
    """Both teams of `match_id` (this season) in their own tables, with badges and past meetings."""

    def fail(kind: Literal["unavailable", "invalid_args"], message: str) -> MatchupResult:
        return MatchupResult(error=ToolError(kind=kind, message=message))

    current = now or datetime.now(UTC)
    try:
        season = deps.seasons.get_current_season()
        if not season:
            raise DataUnavailableError("no current season")
        match = deps.matches.get_match_by_id(match_id, include_test=viewer.include_test, raise_on_error=True)
        if not match:
            raise _InvalidArgsError(f"No match with id {match_id}.")
        if match.get("season_id") != season["id"]:
            raise _InvalidArgsError(f"Match {match_id} is not in the current season.")
        header = MatchupMatch(
            id=match["id"],
            date=_date(match["match_date"]),
            age_group=AgeGroupRef(id=match["age_group_id"], name=str(match.get("age_group_name") or "")),
            tournament=MatchupTournament(id=match["tournament_id"], name=match.get("tournament_name"))
            if match.get("tournament_id") is not None
            else None,
            tournament_round=match.get("tournament_round"),
            stakes=stakes_for(match.get("tournament_id"), match.get("tournament_round")),
        )
    except _InvalidArgsError as exc:
        return fail("invalid_args", str(exc))
    except DataUnavailableError as exc:
        logger.warning("matchup_unavailable", error=str(exc))
        return fail("unavailable", UNAVAILABLE)
    except Exception:
        logger.exception("get_matchup failed", match_id=match_id)
        return fail("unavailable", UNAVAILABLE)

    home_id, away_id = match["home_team_id"], match["away_team_id"]
    home_dossier, away_dossier = (
        get_team_dossier(deps, team_id, None, for_match_id=match_id, viewer=viewer, now=current)
        for team_id in (home_id, away_id)
    )

    # Badges and meetings degrade on their own: neither blanks the dossiers.
    index: TeamIndex | None = None
    try:
        index = load_team_index(deps, viewer)
    except Exception:
        logger.warning("matchup_index_unavailable", match_id=match_id, exc_info=True)
    boards: dict[tuple[str, str], LeaderboardsResult] = {}
    home = _side(deps, home_id, home_dossier, index, boards)
    away = _side(deps, away_id, away_dossier, index, boards)

    meetings: list[Meeting] | None
    try:
        rows = deps.matches.get_all_matches(team_id=home_id, include_test=viewer.include_test, raise_on_error=True)
        meetings = meetings_from(rows, match)
    except Exception:
        logger.warning("matchup_meetings_unavailable", match_id=match_id, exc_info=True)
        meetings = None

    shared = shares_conference(home_dossier, away_dossier)
    logger.info(
        "matchup_built",
        match_id=match_id,
        shares_conference=shared,
        tournament=header.tournament is not None,
        home_error=bool(home_dossier.error),
        away_error=bool(away_dossier.error),
        boards_read=len(boards),
        meetings=None if meetings is None else len(meetings),
    )
    return MatchupResult(
        match=header,
        shares_conference=shared,
        scouting_relevant=header.tournament is not None or shared is False,
        home=home,
        away=away,
        previous_meetings=meetings,
    )

"""Cross-conference leaderboards: one league and age group, the whole season (SB-1781).

A stat board, not a strength ranking. Homegrown conferences only meet at
tournaments, so a team's points or goals are earned against its own conference
(and its Flex bracket): the boards compare numbers, they do not say who is better.
Every response carries that sentence and its denominator.

Two layers, so the counting is testable without a database:

- **Gathering** (`get_leaderboards`) resolves the league, age group and season and
  reads the results through the DAO protocols MT AI uses (`ToolDeps`).
- **Counting and ranking** (`tally`, `conference_of`, `rank_rows`, `split_min_gp`,
  `build_boards`) are pure functions over plain dicts.

## Counted

Status completed or forfeit; divisions of a top-level league and its child
leagues (Homegrown + Flex); the competitions those leagues hold
(`leagues.match_type_id`: League, Flex); the season; the age group. A side counts
only if it fielded that age group (`effective_side_age_groups`), so a side that
played up into another age group's match counts at its own age. A match with no
score is skipped and counted in coverage. Points are W=3, D=1, and a level score
is a draw (D) even when a Flex shootout decided it: Flex standings award
shootout points, these boards do not, and the board title and note say so.

## Boards

Total and per game, top `limit` (ties share a rank, 1, 1, 3): points, goals for,
goals against (fewest first), goal difference; unbeaten (no loss, by games
played); wins over pro academies. **Every board ranks only teams with `MIN_GP`
games**, so a team with one game and none conceded can never top fewest goals
against. Teams under it are listed once, in the result's `unranked` (top `limit`
by games played, with `unranked_count`); each board carries only its own
`unranked_count`, and `ranked_count`, the teams it ranks (the "of N"). Wins over
pro academies lists only teams that played one: a team that never met a pro
academy is absent from that board, not 0.

Every row carries games played, the team's club id and logo (null when absent),
and the team's Homegrown conference: the conference it played most League games
in. A team with only Flex games has none; it is shown with `no_conference`,
never dropped.
"""

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from fractions import Fraction
from typing import Literal, NamedTuple

import structlog
from pydantic import BaseModel

from dao.side_age_groups import effective_side_age_groups
from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.schemas import AgeGroupRef, SeasonRef, TeamRef, ToolError, Viewer
from mt_ai.tools.visibility import DataUnavailableError, TeamIndex, load_team_index

logger = structlog.get_logger()

MIN_GP = 6
DEFAULT_LIMIT = 20
MAX_LIMIT = 50

COMPETITIONS = ("League", "Flex")
COUNTED_STATUSES = frozenset({"completed", "forfeit"})

UNAVAILABLE = "Leaderboards are unavailable right now."
NOT_A_RANKING = (
    "Conferences only meet at tournaments, so this compares stats across conferences: a stat board, not a ranking."
)
SHOOTOUTS = "Level scores count as draws; Flex shootout points are not counted."

Variant = Literal["total", "per_game"]
Better = Literal["higher", "lower"]


# --- result models -----------------------------------------------------------


class LeaderRow(BaseModel):
    rank: int | None  # null: in `unranked`, under MIN_GP games
    team: TeamRef
    # The team's club, so a client can show its logo and filter by it without
    # loading every team and club. Null when the team has no club or no logo.
    club_id: int | None = None
    club_logo_url: str | None = None
    conference: str | None = None
    no_conference: bool = False
    gp: int
    w: int
    d: int
    l: int
    # Per-game boards: rounded to 2 places, ranked exactly. Null on `unranked` rows.
    value: int | float | None = None
    # Wins over pro academies only: games played against one.
    pro_games: int | None = None


class Board(BaseModel):
    key: str
    title: str
    variant: Variant
    better: Better
    rows: list[LeaderRow]
    # Teams this board would hold but for MIN_GP; listed once, in the result's `unranked`.
    unranked_count: int = 0
    # Teams the board ranks (MIN_GP games, and on the board at all): the "of N" for a rank.
    ranked_count: int = 0


class LeaderboardsCoverage(BaseModel):
    teams: int
    matches: int
    conferences: int
    min_gp: int = MIN_GP
    competitions_present: list[str]
    competitions_absent: list[str]
    teams_without_conference: int
    matches_without_score: int = 0
    sides_other_age_group: int = 0
    note: str


class LeaderboardsResult(BaseModel):
    """Boards for one league and age group in one season.

    `boards` holds every board, each with `rows` [] when nothing was played (with
    `reason`); null with `error` when MT could not check.
    """

    league: str
    age_group: AgeGroupRef | None = None
    season: SeasonRef | None = None
    boards: list[Board] | None = None
    # Teams under MIN_GP games, most games first, at most `limit` of `unranked_count`.
    unranked: list[LeaderRow] | None = None
    unranked_count: int = 0
    coverage: LeaderboardsCoverage | None = None
    reason: str | None = None
    error: ToolError | None = None


# --- pure counting -------------------------------------------------------------


@dataclass
class TeamTally:
    team_id: int
    name: str
    gp: int = 0
    w: int = 0
    d: int = 0
    l: int = 0
    gf: int = 0
    ga: int = 0
    pro_gp: int = 0
    pro_w: int = 0
    # The team is itself a pro academy: off the "wins over pro academies" board (SB-1819).
    is_pro: bool = False
    # Homegrown division name → League games played in it.
    divisions: Counter = field(default_factory=Counter)

    @property
    def points(self) -> int:
        return 3 * self.w + self.d

    @property
    def gd(self) -> int:
        return self.gf - self.ga


@dataclass
class Tally:
    teams: dict[int, TeamTally] = field(default_factory=dict)
    matches: int = 0
    by_competition: Counter = field(default_factory=Counter)
    without_score: int = 0
    sides_other_age_group: int = 0


def tally(
    matches: Iterable[dict],
    age_group_id: int,
    *,
    home_league_id: int | None = None,
    pro_team_ids: frozenset[int] | set[int] = frozenset(),
    visible: Callable[[int], bool] | None = None,
) -> Tally:
    """Each team's season record at `age_group_id` from played League/Flex matches.

    `home_league_id` is the league whose League divisions are conferences.
    `visible` hides a team's own line (test content); its opponent still counts the game.
    """
    out = Tally()
    for m in matches:
        if m.get("match_status") not in COUNTED_STATUSES or m.get("match_type_name") not in COMPETITIONS:
            continue
        hs, as_ = m.get("home_score"), m.get("away_score")
        if hs is None or as_ is None:
            out.without_score += 1
            continue
        out.matches += 1
        out.by_competition[m["match_type_name"]] += 1
        home_age, away_age = effective_side_age_groups(m)
        sides = (
            (m.get("home_team_id"), m.get("home_team_name"), home_age, hs, as_, m.get("away_team_id")),
            (m.get("away_team_id"), m.get("away_team_name"), away_age, as_, hs, m.get("home_team_id")),
        )
        for team_id, name, side_age, gf, ga, opponent in sides:
            if team_id is None or (visible is not None and not visible(team_id)):
                continue
            if side_age != age_group_id:
                out.sides_other_age_group += 1
                continue
            t = out.teams.setdefault(
                team_id, TeamTally(team_id=team_id, name=name or str(team_id), is_pro=team_id in pro_team_ids)
            )
            t.gp += 1
            t.gf += gf
            t.ga += ga
            # A level score is a draw, whoever won the shootout.
            if gf > ga:
                t.w += 1
            elif gf == ga:
                t.d += 1
            else:
                t.l += 1
            if opponent in pro_team_ids:
                t.pro_gp += 1
                t.pro_w += int(gf > ga)
            if m["match_type_name"] == "League" and home_league_id is not None and m.get("league_id") == home_league_id:
                division = m.get("division_name")
                if division:
                    t.divisions[division] += 1
    return out


def conference_of(team: TeamTally) -> str | None:
    """The Homegrown division the team played most League games in; ties alphabetical."""
    if not team.divisions:
        return None
    return sorted(team.divisions.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


Value = int | Fraction


def rank_rows[T](items: Iterable[T], value: Callable[[T], Value], *, higher: bool = True) -> list[tuple[int, T]]:
    """Competition ranking (1, 1, 3): equal values share a rank, the next skips.

    Values compare exactly, so per-game values are Fractions: 2/3 and 4/6 tie.
    Order within a tie is the input order.
    """
    ordered = sorted(items, key=lambda i: -value(i) if higher else value(i))
    out: list[tuple[int, T]] = []
    previous: Value | None = None
    rank = 0
    for position, item in enumerate(ordered, start=1):
        v = value(item)
        if previous is None or v != previous:
            rank, previous = position, v
        out.append((rank, item))
    return out


def split_min_gp(teams: Iterable[TeamTally], min_gp: int = MIN_GP) -> tuple[list[TeamTally], list[TeamTally]]:
    """(ranked, too few games): every board ranks only teams with `min_gp` games."""
    teams = list(teams)
    return [t for t in teams if t.gp >= min_gp], [t for t in teams if t.gp < min_gp]


@dataclass(frozen=True)
class BoardSpec:
    key: str
    title: str
    variant: Variant
    better: Better
    value: Callable[[TeamTally], Value]


BOARDS: tuple[BoardSpec, ...] = (
    BoardSpec("pts", "Points (W=3, D=1; shootouts count as draws)", "total", "higher", lambda t: t.points),
    BoardSpec("ppg", "Points per match", "per_game", "higher", lambda t: Fraction(t.points, t.gp)),
    BoardSpec("gf", "Goals for", "total", "higher", lambda t: t.gf),
    BoardSpec("gf_pg", "Goals for per match", "per_game", "higher", lambda t: Fraction(t.gf, t.gp)),
    BoardSpec("ga", "Goals against (fewest)", "total", "lower", lambda t: t.ga),
    BoardSpec("ga_pg", "Goals against per match (fewest)", "per_game", "lower", lambda t: Fraction(t.ga, t.gp)),
    BoardSpec("gd", "Goal difference", "total", "higher", lambda t: t.gd),
    BoardSpec("gd_pg", "Goal difference per match", "per_game", "higher", lambda t: Fraction(t.gd, t.gp)),
)
BOARD_KEYS = (*(b.key for b in BOARDS), "unbeaten", "pro_wins")


class TeamClub(NamedTuple):
    club_id: int | None
    logo_url: str | None


def _row(
    team: TeamTally,
    rank: int | None,
    value: Value | None,
    refs: dict[int, TeamRef],
    clubs: dict[int, TeamClub],
    **extra,
) -> LeaderRow:
    conference = conference_of(team)
    club = clubs.get(team.team_id)
    return LeaderRow(
        rank=rank,
        team=refs.get(team.team_id) or TeamRef(id=team.team_id, name=team.name),
        club_id=club.club_id if club else None,
        club_logo_url=club.logo_url if club else None,
        conference=conference,
        no_conference=conference is None,
        gp=team.gp,
        w=team.w,
        d=team.d,
        l=team.l,
        value=round(float(value), 2) if isinstance(value, Fraction) else value,
        **extra,
    )


def _by_name(teams: Iterable[TeamTally]) -> list[TeamTally]:
    return sorted(teams, key=lambda t: (t.name.casefold(), t.team_id))


def _ranked(teams: list[TeamTally], spec_value, higher: bool, limit: int, refs, clubs) -> list[LeaderRow]:
    return [
        _row(t, rank, spec_value(t), refs, clubs)
        for rank, t in rank_rows(_by_name(teams), spec_value, higher=higher)
        if rank <= limit
    ]


def build_boards(
    teams: Iterable[TeamTally],
    *,
    limit: int = DEFAULT_LIMIT,
    min_gp: int = MIN_GP,
    refs: dict[int, TeamRef] | None = None,
    clubs: dict[int, TeamClub] | None = None,
) -> list[Board]:
    """Every board from the teams' tallies. Top `limit` by rank, so a tie at the cut stays."""
    refs = refs or {}
    clubs = clubs or {}
    played = [t for t in teams if t.gp > 0]
    ranked, too_few = split_min_gp(played, min_gp)
    enough = {t.team_id for t in ranked}
    boards: list[Board] = []
    for spec in BOARDS:
        boards.append(
            Board(
                key=spec.key,
                title=spec.title,
                variant=spec.variant,
                better=spec.better,
                rows=_ranked(ranked, spec.value, spec.better == "higher", limit, refs, clubs),
                unranked_count=len(too_few),
                ranked_count=len(ranked),
            )
        )

    unbeaten = [t for t in played if t.l == 0]
    boards.append(
        Board(
            key="unbeaten",
            title=f"Unbeaten (no losses, {min_gp}+ matches; by matches played)",
            variant="total",
            better="higher",
            rows=_ranked([t for t in unbeaten if t.team_id in enough], lambda t: t.gp, True, limit, refs, clubs),
            unranked_count=sum(1 for t in unbeaten if t.team_id not in enough),
            ranked_count=sum(1 for t in unbeaten if t.team_id in enough),
        )
    )

    # Non-pro teams that met a pro academy. A pro academy beating another pro
    # academy is not the upset this board exists to show (SB-1819).
    vs_pro = [t for t in played if t.pro_gp > 0 and not t.is_pro]
    boards.append(
        Board(
            key="pro_wins",
            title="Wins over pro academies",
            variant="total",
            better="higher",
            rows=[
                _row(t, rank, t.pro_w, refs, clubs, pro_games=t.pro_gp)
                for rank, t in rank_rows(_by_name(t for t in vs_pro if t.team_id in enough), lambda t: t.pro_w)
                if rank <= limit
            ],
            unranked_count=sum(1 for t in vs_pro if t.team_id not in enough),
            ranked_count=sum(1 for t in vs_pro if t.team_id in enough),
        )
    )
    return boards


def unranked_rows(
    teams: Iterable[TeamTally],
    *,
    limit: int = DEFAULT_LIMIT,
    min_gp: int = MIN_GP,
    refs: dict[int, TeamRef] | None = None,
    clubs: dict[int, TeamClub] | None = None,
) -> tuple[list[LeaderRow], int]:
    """(the first `limit` teams under `min_gp`, most games first; how many there are).

    Listed once for every board rather than per board: early in a season that is
    most teams, ten times over.
    """
    refs = refs or {}
    clubs = clubs or {}
    _, too_few = split_min_gp((t for t in teams if t.gp > 0), min_gp)
    ordered = sorted(too_few, key=lambda t: (-t.gp, t.name.casefold(), t.team_id))
    return [_row(t, None, None, refs, clubs) for t in ordered[:limit]], len(too_few)


def coverage_note(
    teams: int, conferences: int, without_conference: int, absent: list[str], age_group: str, min_gp: int = MIN_GP
) -> str:
    """The denominator and the caveat, in words (root CLAUDE.md: aggregates state it)."""
    text = f"{teams} {'team' if teams == 1 else 'teams'} from {conferences} conference{'' if conferences == 1 else 's'}"
    if without_conference:
        text += f", plus {without_conference} with no Homegrown conference"
    text += f". {NOT_A_RANKING} Teams with fewer than {min_gp} matches are listed, not ranked. {SHOOTOUTS}"
    for competition in absent:
        text += f" No {competition} results at {age_group}."
    return text


# --- gathering -----------------------------------------------------------------


class _InvalidArgsError(Exception):
    pass


def _day(value) -> date | None:
    try:
        return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _season(deps: ToolDeps, season: str | None, today: date) -> SeasonRef:
    if season is None:
        current = deps.seasons.get_current_season()
        if current:
            return SeasonRef(id=current["id"], name=current["name"])
    # get_all_seasons swallows errors and returns []. MT always has seasons, so
    # empty means the read failed.
    seasons = deps.seasons.get_all_seasons()
    if not seasons:
        raise DataUnavailableError("season list unavailable")
    if season is None:
        # get_current_season also swallows errors, so None may be a failed read.
        # The newest row can be a season that has not started: only the season
        # whose dates contain today stands in for the current one.
        spanning = next(
            (
                s
                for s in seasons
                if (start := _day(s.get("start_date"))) and (end := _day(s.get("end_date"))) and start <= today <= end
            ),
            None,
        )
        if spanning is None:
            raise DataUnavailableError("no current season")
        return SeasonRef(id=spanning["id"], name=spanning["name"])
    found = next((s for s in seasons if str(s.get("name")) == season.strip()), None)
    if found is None:
        raise _InvalidArgsError(f"No season named {season!r}. Seasons look like {seasons[0]['name']}.")
    return SeasonRef(id=found["id"], name=found["name"])


def _leagues(index: TeamIndex, name: str) -> tuple[dict, list[int], list[int]]:
    """(the named league, the league ids it covers, the match type ids they hold).

    Only a top-level league: a child (Flex) has no conferences of its own, so its
    boards would flag every team as having none. The league ids are the league
    and its children; the match types are what those leagues declare
    (`leagues.match_type_id`: League for Homegrown, Flex for Flex).
    """
    visible = [lg for lg in index.leagues.values() if index.include_test or not lg.get("is_test")]
    top = [lg for lg in visible if lg.get("parent_league_id") is None]
    league = next((lg for lg in top if str(lg.get("name", "")).casefold() == name.strip().casefold()), None)
    if league is None:
        raise _InvalidArgsError(f"league must be one of {', '.join(sorted(str(lg.get('name')) for lg in top))}.")
    covered = [league, *(lg for lg in visible if lg.get("parent_league_id") == league["id"])]
    match_type_ids = sorted({lg["match_type_id"] for lg in covered if lg.get("match_type_id") is not None})
    if not match_type_ids:
        raise DataUnavailableError(f"league {league.get('name')!r} declares no match type")
    return league, [lg["id"] for lg in covered], match_type_ids


def _age_group(index: TeamIndex, name: str) -> AgeGroupRef:
    """An age group MT has a visible registration at, by name."""
    ages: dict[str, AgeGroupRef] = {}
    for team in index.teams.values():
        for mapping in team.get("team_mappings") or []:
            age = mapping.get("age_groups") or {}
            division = mapping.get("divisions") or {}
            if not age.get("name") or (not index.include_test and division.get("league_id") in index.test_league_ids):
                continue
            ages.setdefault(str(age["name"]).casefold(), AgeGroupRef(id=age["id"], name=age["name"]))
    found = ages.get(name.strip().casefold())
    if found is None:
        raise _InvalidArgsError(f"age_group must be one of {', '.join(sorted(a.name for a in ages.values()))}.")
    return found


def _pro_team_ids(index: TeamIndex) -> frozenset[int]:
    return frozenset(
        team_id
        for team_id, team in index.teams.items()
        if (index.clubs.get(team.get("club_id") or 0) or {}).get("pro_academy")
    )


def _team_club(index: TeamIndex, team_id: int) -> TeamClub:
    club_id = index.teams[team_id].get("club_id")
    club = index.clubs.get(club_id) if club_id is not None else None
    return TeamClub(club_id, (club or {}).get("logo_url") or None)


def get_leaderboards(
    deps: ToolDeps,
    league: str = "Homegrown",
    age_group: str = "U15",
    season: str | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
    today: date | None = None,
) -> LeaderboardsResult:
    """Cross-conference boards for `league` (with its Flex) at `age_group`, public data only.

    `season` is a season name ("2026-2027"); default the current season.
    """

    def fail(kind: Literal["unavailable", "invalid_args"], message: str) -> LeaderboardsResult:
        return LeaderboardsResult(league=league, error=ToolError(kind=kind, message=message))

    if not 1 <= limit <= MAX_LIMIT:
        return fail("invalid_args", f"limit must be between 1 and {MAX_LIMIT}.")

    viewer = Viewer(include_test=False)
    try:
        season_ref = _season(deps, season, today or date.today())
        index = load_team_index(deps, viewer)
        league_row, league_ids, match_type_ids = _leagues(index, league)
        age = _age_group(index, age_group)
        matches = deps.matches.get_season_results(
            season_id=season_ref.id,
            age_group_id=age.id,
            league_ids=league_ids,
            match_type_ids=match_type_ids,
            statuses=tuple(sorted(COUNTED_STATUSES)),
            include_test=False,
        )
    except _InvalidArgsError as exc:
        return fail("invalid_args", str(exc))
    except DataUnavailableError as exc:
        logger.warning("leaderboards_unavailable", error=str(exc))
        return fail("unavailable", UNAVAILABLE)
    except Exception:
        logger.exception("get_leaderboards failed")
        return fail("unavailable", UNAVAILABLE)

    counted = tally(
        matches,
        age.id,
        home_league_id=league_row["id"],
        pro_team_ids=_pro_team_ids(index),
        visible=lambda team_id: team_id in index.teams,
    )
    refs = {
        team_id: TeamRef(id=team_id, name=t.name, club_name=index.club_name(index.teams[team_id]))
        for team_id, t in counted.teams.items()
    }
    clubs = {team_id: _team_club(index, team_id) for team_id in counted.teams}
    teams = [t for t in counted.teams.values() if t.gp > 0]
    conferences = {conference_of(t) for t in teams} - {None}
    without = sum(1 for t in teams if conference_of(t) is None)
    present = [c for c in COMPETITIONS if counted.by_competition[c]]
    absent = [c for c in COMPETITIONS if not counted.by_competition[c]]
    coverage = LeaderboardsCoverage(
        teams=len(teams),
        matches=counted.matches,
        conferences=len(conferences),
        competitions_present=present,
        competitions_absent=absent,
        teams_without_conference=without,
        matches_without_score=counted.without_score,
        sides_other_age_group=counted.sides_other_age_group,
        note=coverage_note(len(teams), len(conferences), without, absent, age.name),
    )
    logger.info(
        "leaderboards_built",
        league=league_row.get("name"),
        age_group=age.name,
        season=season_ref.name,
        teams=coverage.teams,
        matches=coverage.matches,
        teams_without_conference=without,
        competitions_absent=absent,
    )
    unranked, unranked_count = unranked_rows(teams, limit=limit, refs=refs, clubs=clubs)
    return LeaderboardsResult(
        league=str(league_row.get("name")),
        age_group=age,
        season=season_ref,
        boards=build_boards(teams, limit=limit, refs=refs, clubs=clubs),
        unranked=unranked,
        unranked_count=unranked_count,
        coverage=coverage,
        reason=None
        if teams
        else f"No League or Flex results at {age.name} {league_row.get('name')} in {season_ref.name} yet.",
    )

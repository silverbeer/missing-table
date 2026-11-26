"""Team dossier: where one team stands in its own conferences, at one age group (SB-1780).

A scouting summary for the Match of the Day agent and a Fest match preview. Two
teams from different conferences have never played a common table, so the
dossier describes each team *inside its own tables* and never compares across
them: every position, percentile and "top third" is measured in one conference,
and every fact names only that conference.

Two layers, so the facts are testable without a database:

- **Gathering** (`get_team_dossier`) resolves the season, the team and its age
  group (from a match when `for_match_id` is given), and reads the team's tables
  and matches through the DAO protocols MT AI uses (`ToolDeps`).
- **Facts** (`detect_playing_up`, `conference_line`, `key_wins`, `form_lines`,
  `dossier_facts`) are pure functions over plain dicts.

## Conferences

One line per `team_mappings` row at the age group: a Homegrown conference, a Flex
conference and a Pro Player Pathway division stay separate. Position, record and
goals come from `MatchDAO.get_standings` (the table /api/table shows), never a
re-tally. Strength percentile is `team_strengths` (points and goal difference per
game, damped under 3 games). A registered team with no counted results keeps its
line with null position and stats and `no_results`: absent is never 0.

## Key wins

Played wins (any competition at the age) over:

- a team in the top third of its *own* table (position <= ceil(N/3), N >= 3).
  The opponent's table is, in order: the division the match counted in, if the
  opponent is registered there; else its registration in the match's competition
  (League or Flex); else its first registration, League before Pro Player
  Pathway before Flex. Opponent tables are loaded lazily, and at most
  `MAX_OPPONENT_TABLES` distinct ones beyond the team's own;
- a pro academy (`clubs.pro_academy`): `pro_academy_upset` when the winner is not
  one, `pro_academy` when it is.

Forfeits are never key wins. Strongest opponent first (its strength in its own
table), then newest. Registrations outside Homegrown, Academy and Flex are no table.

## Playing up

Given a match, the bracket age is the match's. A recorded side age
(`home_age_group_id` / `away_age_group_id`) is the team's age; younger than the
bracket is playing up, older is `playing_down` (no playing-up claim). Scraped
tournament matches never record side ages, so a team with no registration at the
bracket age and exactly one at a lower age is inferred to be playing up from it
(`playing_up_inferred`). An `age_group_id` given with the match only picks the
tables: it must agree with a recorded side age (else invalid_args), and playing
up derived from it is inferred. The match must be in the current season. The
dossier describes the team at its season age: that is where its tables are.

Fact ids are `t<team>:a<age>:<kind>:<division_id>:<slug>`, `t<team>:a<age>:win:<match_id>`
and `t<team>:a<age>:form:<slug>`: the same whether or not a match was given.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from math import ceil
from typing import Literal

import structlog
from pydantic import BaseModel

from dao.side_age_groups import effective_side_age_groups
from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.matches import SCRAPER_SOURCE
from mt_ai.tools.schemas import AgeGroupRef, DivisionRef, Provenance, SeasonRef, TeamRef, ToolError, Viewer
from mt_ai.tools.visibility import DataUnavailableError, TeamIndex, load_team_index
from mt_tools.motw_candidates import (
    FORM_GAMES,
    LOW_SAMPLE_GAMES,
    PLAYED_STATUSES,
    POOL_TIMEZONE,
    MotwFact,
    TeamStanding,
    result_for,
    standings_from_rows,
    streak_text,
    team_results,
    team_strengths,
)
from mt_tools.qualification_rules import conference_kind

logger = structlog.get_logger()

MAX_OPPONENT_TABLES = 10
UNAVAILABLE = "The team dossier is unavailable right now."
NOT_COMPARED = (
    "Positions, percentiles and key wins are measured inside each team's own conference table. "
    "Conferences only meet at tournaments, so they are never compared."
)

Kind = Literal["league", "flex", "pathway"]
KeyWinKind = Literal["top_third", "pro_academy", "pro_academy_upset"]


# --- result models -----------------------------------------------------------


class DossierTeam(TeamRef):
    club_id: int | None = None
    logo_url: str | None = None
    pro_academy: bool = False


class DossierContext(BaseModel):
    """The match the dossier was asked for, and the age the team plays it at."""

    match_id: int
    bracket_age_group: AgeGroupRef
    season_age_group: AgeGroupRef
    playing_up: bool = False  # the side is younger than the bracket
    playing_up_inferred: bool = False  # ...and the match did not record its age
    playing_down: bool = False  # the side is older: no playing-up claim


class ConferenceLine(BaseModel):
    """The team in one of its tables. Null stats: no counted result there yet."""

    kind: Kind
    competition: str  # League or Flex: the table's match type
    division: DivisionRef
    league: str | None = None
    position: int | None = None
    table_size: int | None = None
    played: int = 0
    wins: int | None = None
    draws: int | None = None
    losses: int | None = None
    gf: int | None = None
    ga: int | None = None
    gd: int | None = None
    ppg: float | None = None
    gf_per_game: float | None = None
    ga_per_game: float | None = None
    clean_sheets: int | None = None
    strength_percentile: int | None = None  # 0-100, inside this table only
    low_sample: bool = False
    no_results: bool = False
    fact_ids: list[str] = []


class DossierTotals(BaseModel):
    """Counts over the team's played League/Flex matches at the age. Counts only:
    a rate across two conferences would compare them."""

    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    clean_sheets: int


class KeyWin(BaseModel):
    match_id: int
    date: date
    competition: str | None = None
    opponent: TeamRef
    opponent_conference: str | None = None  # the table the opponent's position is in
    opponent_position: int | None = None
    opponent_table_size: int | None = None
    opponent_pro_academy: bool = False
    top_third: bool = False
    score: str  # the team's goals first
    kind: KeyWinKind
    fact_id: str


class FormEntry(BaseModel):
    match_id: int
    date: date
    opponent: TeamRef
    score: str  # the team's goals first
    result: Literal["W", "D", "L"]
    competition: str | None = None
    forfeit: bool = False


class DossierCoverage(BaseModel):
    results_counted: int  # played League/Flex matches of the team at the age
    tables_loaded: int
    opponent_tables_skipped: int = 0  # distinct tables over MAX_OPPONENT_TABLES: wins there not judged on table
    source: Provenance | None = None
    note: str = NOT_COMPARED


class TeamDossierResult(BaseModel):
    """One team at one age group this season.

    `conferences` [] means no registration at the age (flag `no_conference`);
    `totals` null means no counted League/Flex result (flag `no_results`). Lists
    are null only with `error`, when MT could not check.
    """

    team: DossierTeam | None = None
    age_group: AgeGroupRef | None = None
    season: SeasonRef | None = None
    context: DossierContext | None = None
    conferences: list[ConferenceLine] | None = None
    totals: DossierTotals | None = None
    key_wins: list[KeyWin] | None = None
    form: list[FormEntry] | None = None
    streak_fact_id: str | None = None
    flags: list[str] = []
    facts: list[MotwFact] = []
    coverage: DossierCoverage | None = None
    error: ToolError | None = None


# --- pure facts ----------------------------------------------------------------


@dataclass(frozen=True)
class Conference:
    """One team_mappings row at an age group: a table the team plays in."""

    kind: Kind
    competition: str
    division_id: int
    division: str
    league: str | None

    def label(self, age_name: str) -> str:
        return " ".join(p for p in (age_name, self.league, self.division) if p)


def conference_of(division: dict, index: TeamIndex) -> Conference | None:
    if division.get("id") is None:
        return None
    league = (index.leagues.get(division.get("league_id") or 0) or division.get("leagues") or {}).get("name")
    rules_kind = conference_kind(league, division.get("name"))
    if rules_kind is None:
        # Not a Homegrown, Academy or Flex table: nothing the dossier can place a team in.
        return None
    kind: Kind = "flex" if rules_kind == "flex" else "pathway" if rules_kind == "ppp" else "league"
    return Conference(
        kind=kind,
        competition="Flex" if kind == "flex" else "League",
        division_id=division["id"],
        division=str(division.get("name") or ""),
        league=league,
    )


def visible_mappings(team: dict, index: TeamIndex) -> list[dict]:
    """The team's registrations this viewer may see (test leagues hidden)."""
    return [
        m
        for m in team.get("team_mappings") or []
        if (m.get("age_groups") or {}).get("id") is not None
        and (index.include_test or (m.get("divisions") or {}).get("league_id") not in index.test_league_ids)
    ]


def conferences_at(team: dict, age_group_id: int, index: TeamIndex) -> list[Conference]:
    out: list[Conference] = []
    for m in visible_mappings(team, index):
        if m["age_groups"]["id"] != age_group_id:
            continue
        conf = conference_of(m.get("divisions") or {}, index)
        if conf and all(c.division_id != conf.division_id for c in out):
            out.append(conf)
    kinds = {"league": 0, "pathway": 1, "flex": 2}
    return sorted(out, key=lambda c: (kinds[c.kind], c.division))


def age_number(name: str | None) -> int | None:
    digits = "".join(ch for ch in str(name or "") if ch.isdigit())
    return int(digits) if digits else None


def detect_playing_up(match: dict, team_id: int, mappings: Iterable[dict]) -> tuple[int, int, bool]:
    """(the team's season age, the match's bracket age, whether the match recorded the side's age).

    `mappings` are the team's visible registrations. A recorded side age is
    returned as is, younger or older: `age_direction` says which. Unrecorded, the
    season age is inferred: no registration at the bracket and exactly one below.
    """
    bracket = match["age_group_id"]
    home_age, away_age = effective_side_age_groups(match)
    side = home_age if match.get("home_team_id") == team_id else away_age
    if side is not None and side != bracket:
        return side, bracket, True
    ages = {(m.get("age_groups") or {}).get("id"): (m.get("age_groups") or {}).get("name") for m in mappings}
    if bracket in ages:
        return bracket, bracket, False
    bracket_n = age_number(match.get("age_group_name"))
    lower = {a for a, name in ages.items() if a is not None and bracket_n and (n := age_number(name)) and n < bracket_n}
    if len(lower) == 1:
        return lower.pop(), bracket, False
    return bracket, bracket, False


def age_direction(season_name: str | None, bracket_name: str | None) -> Literal["up", "down", "same"]:
    """Whether a side at `season_name` plays up (younger than the bracket) or down."""
    season_n, bracket_n = age_number(season_name), age_number(bracket_name)
    if season_n is None or bracket_n is None or season_n == bracket_n:
        return "same"
    return "up" if season_n < bracket_n else "down"


def _score(match: dict, team_id: int) -> str:
    hs, as_ = match.get("home_score"), match.get("away_score")
    return f"{hs}-{as_}" if match.get("home_team_id") == team_id else f"{as_}-{hs}"


def _scored(match: dict, team_id: int) -> int:
    return match["home_score"] if match.get("home_team_id") == team_id else match["away_score"]


def _conceded(match: dict, team_id: int) -> int:
    return match["away_score"] if match.get("home_team_id") == team_id else match["home_score"]


def _opponent(match: dict, team_id: int) -> tuple[int, str]:
    if match.get("home_team_id") == team_id:
        return match["away_team_id"], match.get("away_team_name") or str(match["away_team_id"])
    return match["home_team_id"], match.get("home_team_name") or str(match["home_team_id"])


def conference_line(
    team_id: int, conf: Conference, table: dict[int, TeamStanding], league_results: list[dict]
) -> ConferenceLine:
    """The team's line in one table. `league_results` are its played League/Flex matches."""
    base = {
        "kind": conf.kind,
        "competition": conf.competition,
        "division": DivisionRef(id=conf.division_id, name=conf.division, league=conf.league),
        "league": conf.league,
        "table_size": len(table) or None,
    }
    s = table.get(team_id)
    if s is None or s.played == 0:
        return ConferenceLine(**base, low_sample=True, no_results=True)
    strength, low = team_strengths(table)[team_id]
    here = [
        m
        for m in league_results
        if m.get("division_id") == conf.division_id and m.get("match_type_name") == conf.competition
    ]
    return ConferenceLine(
        **base,
        position=s.position,
        played=s.played,
        wins=s.wins,
        draws=s.draws,
        losses=s.losses,
        gf=s.goals_for,
        ga=s.goals_against,
        gd=s.goals_for - s.goals_against,
        ppg=round(s.points / s.played, 2),
        gf_per_game=round(s.goals_for / s.played, 2),
        ga_per_game=round(s.goals_against / s.played, 2),
        clean_sheets=sum(1 for m in here if _conceded(m, team_id) == 0),
        strength_percentile=round(strength * 100),
        low_sample=low,
    )


@dataclass(frozen=True)
class OpponentTable:
    conference: str  # its label, e.g. "U15 Flex Turnpike"
    standing: TeamStanding | None
    size: int
    strength: float | None


def is_top_third(t: OpponentTable | None) -> bool:
    if t is None or t.standing is None or t.standing.played == 0 or t.size < 3:
        return False
    return t.standing.position <= ceil(t.size / 3)


def key_wins(
    team_id: int,
    prefix: str,
    played: Iterable[dict],
    *,
    team_is_pro: bool,
    is_pro: Callable[[int], bool],
    opponent_table: Callable[[dict, int], OpponentTable | None],
    refs: Callable[[int, str], TeamRef],
) -> list[KeyWin]:
    """Wins over a top-third team (in its own table) or a pro academy, strongest first."""
    out: list[tuple[float, KeyWin]] = []
    for m in played:
        # A forfeit is a result, not a win anyone earned on the pitch.
        if m.get("match_status") == "forfeit" or result_for(m, team_id) != "W":
            continue
        opp_id, opp_name = _opponent(m, team_id)
        pro = is_pro(opp_id)
        table = opponent_table(m, opp_id)
        top = is_top_third(table)
        if not (top or pro):
            continue
        kind: KeyWinKind = ("pro_academy" if team_is_pro else "pro_academy_upset") if pro else "top_third"
        win = KeyWin(
            match_id=m["id"],
            date=_date(m["match_date"]),
            competition=m.get("match_type_name"),
            opponent=refs(opp_id, opp_name),
            opponent_conference=table.conference if table and table.standing else None,
            opponent_position=table.standing.position if table and table.standing else None,
            opponent_table_size=table.size if table and table.standing else None,
            opponent_pro_academy=pro,
            top_third=top,
            score=_score(m, team_id),
            kind=kind,
            fact_id=f"{prefix}:win:{m['id']}",
        )
        strength = table.strength if table and table.strength is not None else -1.0
        out.append((strength, win))
    out.sort(key=lambda sw: (-sw[0], -sw[1].date.toordinal(), sw[1].match_id))
    return [w for _, w in out]


def form_lines(results: list[tuple[dict, str]], team_id: int, refs: Callable[[int, str], TeamRef]) -> list[FormEntry]:
    """The last FORM_GAMES results, newest first (`results` as team_results returns them)."""
    out = []
    for m, r in results[:FORM_GAMES]:
        opp_id, opp_name = _opponent(m, team_id)
        out.append(
            FormEntry(
                match_id=m["id"],
                date=_date(m["match_date"]),
                opponent=refs(opp_id, opp_name),
                score=_score(m, team_id),
                result=r,
                competition=m.get("match_type_name"),
                forfeit=m.get("match_status") == "forfeit",
            )
        )
    return out


def _ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def dossier_facts(
    team_id: int,
    prefix: str,
    name: str,
    age_name: str,
    lines: list[tuple[Conference, ConferenceLine]],
    wins: list[KeyWin],
    form: list[FormEntry],
    results: list[str],
    context: DossierContext | None,
) -> tuple[list[MotwFact], str | None]:
    """Every fact the dossier supports, and the streak fact's id. Sets each line's fact_ids.

    Each fact names at most one conference: its own.
    """
    facts: list[MotwFact] = []
    for conf, line in lines:
        label = conf.label(age_name)
        cid = f"{prefix}:{conf.kind}:{conf.division_id}"
        own: list[MotwFact] = []
        if line.no_results:
            own.append(
                MotwFact(
                    team_id=team_id,
                    id=f"{cid}:no_results",
                    kind="standings",
                    text=f"{name} are registered in {label} but have no counted results there yet.",
                )
            )
        else:
            small = " (fewer than 3 games: a small sample)" if line.low_sample else ""
            own.append(
                MotwFact(
                    team_id=team_id,
                    id=f"{cid}:pos",
                    kind="standings",
                    text=(
                        f"{name} are {_ordinal(line.position)} of {line.table_size} in {label} with "
                        f"{line.ppg:.2f} points per game from {_plural(line.played, 'game')} "
                        f"({line.wins}-{line.draws}-{line.losses}){small}."
                    ),
                )
            )
            own.append(
                MotwFact(
                    team_id=team_id,
                    id=f"{cid}:rate",
                    kind="form",
                    text=(
                        f"{name} score {line.gf_per_game:.1f} and concede {line.ga_per_game:.1f} goals per game "
                        f"in {label} (goal difference {line.gd:+d})."
                    ),
                )
            )
            own.append(
                MotwFact(
                    team_id=team_id,
                    id=f"{cid}:strength",
                    kind="standings",
                    text=(
                        f"{name} are in the {_ordinal(line.strength_percentile)} percentile within {label} "
                        f"on points and goal difference per game{small}."
                    ),
                )
            )
            own.append(
                MotwFact(
                    team_id=team_id,
                    id=f"{cid}:clean_sheets",
                    kind="form",
                    text=f"{name} kept {_plural(line.clean_sheets, 'clean sheet')} in {label}.",
                )
            )
        line.fact_ids = [f.id for f in own]
        facts.extend(own)

    for w in wins:
        when = f"{w.date:%b %-d}" + (f" ({w.competition})" if w.competition else "")
        if w.kind == "pro_academy_upset":
            text = f"{name}, not a pro academy, beat pro academy {w.opponent.name} {w.score} on {when}."
        elif w.kind == "pro_academy":
            text = f"{name} beat fellow pro academy {w.opponent.name} {w.score} on {when}."
        else:
            text = f"{name} beat {w.opponent.name} {w.score} on {when}."
        if w.opponent_position is not None:
            standing = f"{_ordinal(w.opponent_position)} of {w.opponent_table_size}"
            text += f" {w.opponent.name} are {standing} in {w.opponent_conference}."
        facts.append(MotwFact(team_id=team_id, id=w.fact_id, kind="storyline", text=text))

    if form:
        recent = ", ".join(
            f"{f.result} {f.score} v {f.opponent.name}" + (" (forfeit)" if f.forfeit else "") for f in form
        )
        facts.append(
            MotwFact(
                team_id=team_id,
                id=f"{prefix}:form:last{len(form)}",
                kind="form",
                text=f"{name}'s last {_plural(len(form), 'League/Flex result')}, newest first: {recent}.",
            )
        )
    streak_id = None
    streak = streak_text(name, results)
    if streak:
        streak_id = f"{prefix}:form:streak"
        facts.append(MotwFact(team_id=team_id, id=streak_id, kind="form", text=streak))

    if context and context.playing_up:
        how = (
            f"{name} are taken to be their {context.season_age_group.name} side in this "
            f"{context.bracket_age_group.name} match, so playing up (inferred: the match does not record it)."
            if context.playing_up_inferred
            else f"{name} fielded their {context.season_age_group.name} side in this "
            f"{context.bracket_age_group.name} match: playing up."
        )
        facts.append(
            MotwFact(team_id=team_id, id=f"{prefix}:context:m{context.match_id}:playing_up", kind="storyline", text=how)
        )
    return facts, streak_id


def totals_of(results: list[tuple[dict, str]], team_id: int) -> DossierTotals | None:
    if not results:
        return None
    rs = [r for _, r in results]
    return DossierTotals(
        played=len(rs),
        wins=rs.count("W"),
        draws=rs.count("D"),
        losses=rs.count("L"),
        goals_for=sum(_scored(m, team_id) for m, _ in results),
        goals_against=sum(_conceded(m, team_id) for m, _ in results),
        clean_sheets=sum(1 for m, _ in results if _conceded(m, team_id) == 0),
    )


def provenance(rows: list[dict]) -> Provenance | None:
    scraped = {(r.get("source") or "") == SCRAPER_SOURCE for r in rows}
    if not scraped:
        return None
    if len(scraped) > 1:
        return "mixed"
    return "scraper" if scraped.pop() else "user"


# --- gathering -----------------------------------------------------------------


class _InvalidArgsError(Exception):
    pass


def _date(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _ages(index: TeamIndex) -> dict[int, AgeGroupRef]:
    """Every age group MT has a visible registration at."""
    out: dict[int, AgeGroupRef] = {}
    for team in index.teams.values():
        for m in visible_mappings(team, index):
            age = m["age_groups"]
            out.setdefault(age["id"], AgeGroupRef(id=age["id"], name=str(age.get("name") or age["id"])))
    return out


@dataclass
class _Tables:
    """Standings tables read so far, by (age, division, competition)."""

    deps: ToolDeps
    season_id: int
    include_test: bool
    loaded: dict[tuple[int, int, str], dict[int, TeamStanding]] = field(default_factory=dict)
    extra: int = 0
    skipped: set[tuple[int, int, str]] = field(default_factory=set)

    def get(self, age_id: int, conf: Conference, *, opponent: bool = False) -> dict[int, TeamStanding] | None:
        key = (age_id, conf.division_id, conf.competition)
        if key not in self.loaded:
            if opponent:
                if self.extra >= MAX_OPPONENT_TABLES:
                    self.skipped.add(key)
                    return None
                self.extra += 1
            data = self.deps.matches.get_standings(
                season_id=self.season_id,
                age_group_id=age_id,
                division_id=conf.division_id,
                match_type=conf.competition,
                include_test=self.include_test,
                raise_on_error=True,
            )
            self.loaded[key] = standings_from_rows((data or {}).get("standings") or [])
        return self.loaded[key]


def get_team_dossier(
    deps: ToolDeps,
    team_id: int,
    age_group_id: int | None = None,
    *,
    for_match_id: int | None = None,
    viewer: Viewer,
    now: datetime | None = None,
) -> TeamDossierResult:
    """The dossier for `team_id` at `age_group_id` (or at its age in `for_match_id`), this season."""

    def fail(kind: Literal["unavailable", "invalid_args"], message: str) -> TeamDossierResult:
        return TeamDossierResult(error=ToolError(kind=kind, message=message))

    if age_group_id is None and for_match_id is None:
        return fail("invalid_args", "Give age_group_id, or for_match_id to use the team's age in that match.")
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    today = current.astimezone(POOL_TIMEZONE).date()

    try:
        season_row = deps.seasons.get_current_season()
        if not season_row:
            raise DataUnavailableError("no current season")
        season = SeasonRef(id=season_row["id"], name=season_row["name"])
        index = load_team_index(deps, viewer)
        team = index.teams.get(team_id)
        if team is None:
            raise _InvalidArgsError(f"No team with id {team_id}.")
        mappings = visible_mappings(team, index)
        ages = _ages(index)
        if age_group_id is not None and age_group_id not in ages:
            raise _InvalidArgsError(f"No age group with id {age_group_id}.")

        context: DossierContext | None = None
        if for_match_id is not None:
            match = deps.matches.get_match_by_id(for_match_id, include_test=viewer.include_test, raise_on_error=True)
            if not match:
                raise _InvalidArgsError(f"No match with id {for_match_id}.")
            if match.get("season_id") != season.id:
                raise _InvalidArgsError(f"Match {for_match_id} is not in the current season.")
            if team_id not in (match.get("home_team_id"), match.get("away_team_id")):
                raise _InvalidArgsError(f"Team {team_id} does not play in match {for_match_id}.")
            season_age, bracket, recorded = detect_playing_up(match, team_id, mappings)
            if age_group_id is not None:
                # The given age only picks the tables; it may not contradict the match.
                if recorded and age_group_id != season_age:
                    raise _InvalidArgsError(
                        f"Match {for_match_id} records team {team_id} at another age group than {age_group_id}."
                    )
                season_age = age_group_id
            bracket_ref = ages.get(bracket) or AgeGroupRef(id=bracket, name=str(match.get("age_group_name") or bracket))
            season_ref = ages.get(season_age) or AgeGroupRef(id=season_age, name=str(season_age))
            direction = age_direction(season_ref.name, bracket_ref.name)
            context = DossierContext(
                match_id=for_match_id,
                bracket_age_group=bracket_ref,
                season_age_group=season_ref,
                playing_up=direction == "up",
                # Inferred whenever the match did not record the side's age.
                playing_up_inferred=direction == "up" and not recorded,
                playing_down=direction == "down",
            )
            age = season_ref
        else:
            age = ages[age_group_id]

        own = deps.matches.get_all_matches(
            season_id=season.id,
            age_group_id=age.id,
            team_id=team_id,
            include_test=viewer.include_test,
            raise_on_error=True,
        )
        tables = _Tables(deps, season.id, viewer.include_test)
        confs = conferences_at(team, age.id, index)
        own_tables = [(c, tables.get(age.id, c)) for c in confs]

        def opponent_table(m: dict, opp_id: int) -> OpponentTable | None:
            opp = index.teams.get(opp_id)
            if opp is None:
                return None
            home_age, away_age = effective_side_age_groups(m)
            opp_age = home_age if m.get("home_team_id") == opp_id else away_age
            options = conferences_at(opp, opp_age, index)
            if not options:
                return None
            conf = (
                next((c for c in options if c.division_id == m.get("division_id")), None)
                or next((c for c in options if c.competition == m.get("match_type_name")), None)
                or options[0]
            )
            table = tables.get(opp_age, conf, opponent=True)
            if table is None:
                return None
            standing = table.get(opp_id)
            strength = team_strengths(table).get(opp_id, (None, True))[0] if standing else None
            label = conf.label((ages.get(opp_age) or AgeGroupRef(id=opp_age, name="")).name)
            return OpponentTable(conference=label, standing=standing, size=len(table), strength=strength)

        def is_pro(tid: int) -> bool:
            t = index.teams.get(tid) or {}
            return bool((index.clubs.get(t.get("club_id") or 0) or {}).get("pro_academy"))

        def refs(tid: int, name: str) -> TeamRef:
            t = index.teams.get(tid)
            return TeamRef(id=tid, name=name, club_name=index.club_name(t) if t else None)

        results = team_results(own, team_id, today + timedelta(days=1))
        league_results = [m for m, _ in results]
        played = sorted(
            (m for m in own if m.get("match_status") in PLAYED_STATUSES and result_for(m, team_id)),
            key=lambda m: (_date(m["match_date"]), m["id"]),
            reverse=True,
        )
        prefix = f"t{team_id}:a{age.id}"
        wins = key_wins(
            team_id,
            prefix,
            played,
            team_is_pro=is_pro(team_id),
            is_pro=is_pro,
            opponent_table=opponent_table,
            refs=refs,
        )
    except _InvalidArgsError as exc:
        return fail("invalid_args", str(exc))
    except DataUnavailableError as exc:
        logger.warning("team_dossier_unavailable", error=str(exc))
        return fail("unavailable", UNAVAILABLE)
    except Exception:
        logger.exception("get_team_dossier failed", team_id=team_id)
        return fail("unavailable", UNAVAILABLE)

    lines = [(c, conference_line(team_id, c, table, league_results)) for c, table in own_tables]
    form = form_lines(results, team_id, refs)
    facts, streak_id = dossier_facts(
        team_id, prefix, team["name"], age.name, lines, wins, form, [r for _, r in results], context
    )
    totals = totals_of(results, team_id)

    flags: list[str] = []
    if totals is None:
        flags.append("no_results")
    elif totals.played < LOW_SAMPLE_GAMES:
        flags.append("low_sample")
    if not confs:
        flags.append("no_conference")
    if context and context.playing_up:
        flags.append("playing_up")
        if context.playing_up_inferred:
            flags.append("playing_up_inferred")
    if context and context.playing_down:
        flags.append("playing_down")

    club = index.clubs.get(team.get("club_id") or 0) or {}
    logger.info(
        "team_dossier_built",
        team_id=team_id,
        age_group=age.name,
        for_match_id=for_match_id,
        conferences=len(lines),
        results=len(results),
        key_wins=len(wins),
        tables_loaded=len(tables.loaded),
        opponent_tables_skipped=len(tables.skipped),
        flags=flags,
    )
    return TeamDossierResult(
        team=DossierTeam(
            id=team_id,
            name=team["name"],
            club_name=club.get("name"),
            club_id=team.get("club_id"),
            logo_url=club.get("logo_url"),
            pro_academy=bool(club.get("pro_academy")),
        ),
        age_group=age,
        season=season,
        context=context,
        conferences=[line for _, line in lines],
        totals=totals,
        key_wins=wins,
        form=form,
        streak_fact_id=streak_id,
        flags=flags,
        facts=facts,
        coverage=DossierCoverage(
            results_counted=len(results),
            tables_loaded=len(tables.loaded),
            opponent_tables_skipped=len(tables.skipped),
            source=provenance(league_results),
        ),
    )

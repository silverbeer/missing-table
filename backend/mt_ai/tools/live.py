"""get_live_match — one match's live state: score, clock, goals and cards (SB-1584).

What the live-match view shows, read-only: the score (and a shootout), which half
it is and the current minute, and every goal and card with its minute and team.
Chat is never read: it is user content, and `match_events.message` is free text
that can hold anyone's name.

Players are minors. Whatever the roster holds, a player leaves this tool as at
most "#7 Tom D." (jersey number, first name, last initial) and "#7" when there
is no first name (SB-1583). The rule is enforced here, not trusted to the data.
"""

from datetime import UTC, datetime
from typing import Any

import structlog

from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.schemas import (
    ErrorKind,
    LiveEvent,
    LiveMatchResult,
    LivePeriod,
    TeamRef,
    ToolError,
    ToolMeta,
    Viewer,
)

logger = structlog.get_logger()

NOT_TRACKED = (
    "Goals and cards are recorded live in the MT app by a team manager; this match "
    "was not tracked live, so only its score is known."
)


def get_live_match(
    deps: ToolDeps,
    match_id: int,
    viewer: Viewer,
    now: datetime | None = None,
) -> LiveMatchResult:
    def fail(kind: ErrorKind, message: str) -> LiveMatchResult:
        return LiveMatchResult(match_id=match_id, error=ToolError(kind=kind, message=message))

    if deps.live is None or deps.events is None or deps.roster is None:
        return fail("unavailable", "Live match data is not available here.")

    try:
        state = deps.live.get_live_match_state(match_id, include_test=viewer.include_test)
    except Exception:
        logger.exception("get_live_match failed", match_id=match_id)
        return fail("unavailable", "Live match data is unavailable right now.")
    if not state:
        # The DAO reports a read failure as None too, so this may also be an outage.
        return fail("not_found", f"No match with id {match_id}.")

    home_id, away_id = state.get("home_team_id"), state.get("away_team_id")
    teams = {home_id: state.get("home_team_name"), away_id: state.get("away_team_name")}
    period = _period(state)
    minute, extra = _clock(state, period, now or datetime.now(UTC))

    # Absent is not zero: a match nobody has kicked off has no score yet, not 0-0.
    scored = period != "not_started"

    rows = deps.events.get_key_events(match_id)
    events = None if rows is None else _events(rows, teams, deps)
    tracked = bool(state.get("kickoff_time"))

    return LiveMatchResult(
        match_id=match_id,
        status=state.get("match_status"),
        period=period,
        minute=minute,
        extra_time=extra,
        home_team=TeamRef(id=home_id, name=teams[home_id] or "") if home_id else None,
        away_team=TeamRef(id=away_id, name=teams[away_id] or "") if away_id else None,
        home_score=state.get("home_score") if scored else None,
        away_score=state.get("away_score") if scored else None,
        home_penalty_score=state.get("home_penalty_score"),
        away_penalty_score=state.get("away_penalty_score"),
        age_group=state.get("age_group_name"),
        competition=state.get("match_type_name"),
        events=events,
        error=(
            ToolError(kind="unavailable", message="Goals and cards are unavailable right now.")
            if rows is None
            else None
        ),
        meta=ToolMeta(coverage=None if tracked or events else NOT_TRACKED),
    )


def _period(state: dict) -> LivePeriod:
    if state.get("match_end_time") or state.get("match_status") in ("completed", "forfeit"):
        return "full_time"
    if state.get("second_half_start"):
        return "second_half"
    if state.get("halftime_start"):
        return "halftime"
    if state.get("kickoff_time"):
        return "first_half"
    return "not_started"


def _clock(state: dict, period: LivePeriod, now: datetime) -> tuple[int | None, int | None]:
    """The running minute, as the live view counts it; None unless the clock runs."""
    half = state.get("half_duration") or 45
    if period == "halftime":
        return half, None
    if period == "first_half":
        start, base, end = _when(state.get("kickoff_time")), 0, half
    elif period == "second_half":
        start, base, end = _when(state.get("second_half_start")), half, half * 2
    else:
        return None, None
    if start is None:
        return None, None
    total = base + int((now - start).total_seconds() // 60) + 1
    return (end, total - end) if total > end else (max(total, base + 1), None)


def _when(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _events(rows: list[dict], teams: dict, deps: ToolDeps) -> list[LiveEvent]:
    players: dict[int, dict | None] = {}

    def lookup(player_id: Any) -> dict | None:
        if not isinstance(player_id, int):
            return None
        if player_id not in players:
            try:
                players[player_id] = deps.roster.get_player_by_id(player_id)  # type: ignore[union-attr]
            except Exception:
                logger.warning("roster lookup failed", player_id=player_id)
                players[player_id] = None
        return players[player_id]

    out = []
    for row in rows:
        kind = row.get("event_type")
        if kind not in ("goal", "yellow_card", "red_card"):
            continue
        team_id = row.get("team_id")
        out.append(
            LiveEvent(
                type=kind,
                minute=row.get("match_minute"),
                extra_time=row.get("extra_time"),
                team_id=team_id,
                team=teams.get(team_id),
                player=player_label(lookup(row.get("player_id")), row.get("player_name")),
                assist=player_label(lookup(row.get("assist_player_id")), row.get("assist_player_name")),
            )
        )
    return out


def player_label(player: dict | None, recorded_name: str | None = None) -> str | None:
    """'#7 Tom D.': jersey number, first name, last initial — never more (SB-1583).

    From the roster entry when there is one (its own names, else the linked
    account's); otherwise parsed from the name recorded on the event, whose
    first word is taken as the first name and last word as the surname.
    """
    number: Any = None
    first = last = None
    if player:
        number = player.get("jersey_number")
        profile = player.get("user_profile") or {}
        first = player.get("first_name") or profile.get("first_name")
        last = player.get("last_name") or profile.get("last_name")
    elif recorded_name:
        words = recorded_name.split()
        if words and words[0].startswith("#"):
            number, words = words[0][1:], words[1:]
        if words:
            first, last = words[0], (words[-1] if len(words) > 1 else None)

    parts = []
    if number not in (None, ""):
        parts.append(f"#{number}")
    if first and first.strip():
        parts.append(first.strip())
        if last and last.strip():
            parts.append(f"{last.strip()[0].upper()}.")
    return " ".join(parts) or None

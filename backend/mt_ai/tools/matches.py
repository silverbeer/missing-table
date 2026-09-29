"""get_upcoming_matches — a team's next fixtures, from the club's point of view.

"Today" is the club's calendar day (clubs.timezone), worked out here and not
by the model: at 9pm in Boston it is already tomorrow in UTC, and "who do we
play next?" must not skip tonight's game or include last night's.

Upcoming means dated today or later and not finished: scheduled, tbd, live or
postponed. Postponed fixtures are included and labelled, because "our game
Saturday was postponed" is part of the answer. Cancelled, completed and
forfeit matches are not upcoming.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import structlog

from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.schemas import (
    ErrorKind,
    Provenance,
    TeamRef,
    ToolError,
    ToolMeta,
    UpcomingMatch,
    UpcomingMatchesResult,
    Viewer,
)
from mt_ai.tools.visibility import DataUnavailableError, load_team_index

logger = structlog.get_logger()

UPCOMING_STATUSES = frozenset({"scheduled", "tbd", "live", "postponed"})
MAX_LIMIT = 20
SCRAPER_SOURCE = "match-scraper"


def get_upcoming_matches(
    deps: ToolDeps,
    team_id: int,
    viewer: Viewer,
    age_group_id: int | None = None,
    limit: int = 5,
    now: datetime | None = None,
) -> UpcomingMatchesResult:
    def fail(kind: ErrorKind, message: str) -> UpcomingMatchesResult:
        return UpcomingMatchesResult(
            team_id=team_id, age_group_id=age_group_id, error=ToolError(kind=kind, message=message)
        )

    if not 1 <= limit <= MAX_LIMIT:
        return fail("invalid_args", f"limit must be between 1 and {MAX_LIMIT}.")

    try:
        index = load_team_index(deps, viewer)
        team = index.teams.get(team_id)
        if team is None:
            return fail("not_found", f"No team with id {team_id}.")

        tz = index.timezone(team)
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        today = current.astimezone(tz).date()

        rows = deps.matches.get_all_matches(
            team_id=team_id,
            age_group_id=age_group_id,
            start_date=today.isoformat(),
            include_test=viewer.include_test,
            raise_on_error=True,
        )
    except DataUnavailableError as exc:
        return fail("unavailable", f"Match data is unavailable right now ({exc}).")
    except Exception:
        logger.exception("get_upcoming_matches failed", team_id=team_id)
        return fail("unavailable", "Match data is unavailable right now.")

    upcoming = []
    for row in rows:
        match = _to_match(row, team_id, tz)
        if match and match.status in UPCOMING_STATUSES and match.match_date >= today:
            upcoming.append((match, row))
    upcoming.sort(key=lambda m: (m[0].match_date, m[0].kickoff or datetime.max.replace(tzinfo=UTC)))

    kept = upcoming[:limit]
    return UpcomingMatchesResult(
        team_id=team_id,
        age_group_id=age_group_id,
        today=today,
        timezone=tz.key,
        matches=[m for m, _ in kept],
        meta=ToolMeta(
            source=_provenance([r for _, r in kept]),
            as_of=_newest([r for _, r in kept]),
            truncated=len(upcoming) > limit,
        ),
    )


def _to_match(row: dict, team_id: int, tz: ZoneInfo) -> UpcomingMatch | None:
    """Shape one DAO row, or None (logged) if it is too malformed to use."""
    try:
        home_id, away_id = row["home_team_id"], row["away_team_id"]
        return UpcomingMatch(
            match_id=row["id"],
            match_date=date.fromisoformat(str(row["match_date"])[:10]),
            kickoff=_kickoff(row.get("scheduled_kickoff"), tz),
            status=row.get("match_status") or "scheduled",
            home_team=TeamRef(
                id=home_id, name=row.get("home_team_name") or "", club_name=_club(row.get("home_team_club"))
            ),
            away_team=TeamRef(
                id=away_id, name=row.get("away_team_name") or "", club_name=_club(row.get("away_team_club"))
            ),
            is_home=home_id == team_id,
            age_group=row.get("age_group_name"),
            division=row.get("division_name"),
            competition=row.get("match_type_name"),
            league=row.get("league_name"),
        )
    except (KeyError, TypeError, ValueError):
        logger.warning("Skipping malformed match row", match_id=row.get("id"))
        return None


def _kickoff(value: str | None, tz: ZoneInfo) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)  # the column is timestamptz; naive means UTC
    return parsed.astimezone(tz)


def _club(club: dict | None) -> str | None:
    return club.get("name") if isinstance(club, dict) else None


def _provenance(rows: list[dict]) -> Provenance | None:
    scraped = {(r.get("source") or "") == SCRAPER_SOURCE for r in rows}
    if not scraped:
        return None
    if len(scraped) > 1:
        return "mixed"
    return "scraper" if scraped.pop() else "user"


def _newest(rows: list[dict]) -> datetime | None:
    stamps = []
    for row in rows:
        try:
            stamp = datetime.fromisoformat(row["updated_at"])
        except (KeyError, TypeError, ValueError):
            continue
        stamps.append(stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC))
    return max(stamps, default=None)

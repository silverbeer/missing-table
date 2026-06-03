#!/usr/bin/env python3
"""CLI helpers for the load-tournament-matches skill.

Thin typer wrapper around MissingTableClient. Every subcommand prints JSON
to stdout so the calling skill (Claude) can parse the result.

Run from the repo root:

    cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py <subcommand> ...

Auth: reads MT_ADMIN_TOKEN from the environment. MT_API_BASE_URL is optional
(default http://localhost:8000).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Skill lives at .claude/skills/load-tournament-matches/scripts/mt.py
# api_client lives at backend/api_client/ — add backend/ to sys.path.
_REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO_ROOT / "backend"))

import typer

from api_client import APIError, MissingTableClient
from api_client.models import (
    Team,
    TournamentCreate,
    TournamentMatchCreate,
    TournamentMatchUpdate,
)

app = typer.Typer(no_args_is_help=True, add_completion=False)
auth_app = typer.Typer(no_args_is_help=True, add_completion=False)
club_app = typer.Typer(no_args_is_help=True, add_completion=False)
team_app = typer.Typer(no_args_is_help=True, add_completion=False)
tournament_app = typer.Typer(no_args_is_help=True, add_completion=False)
match_app = typer.Typer(no_args_is_help=True, add_completion=False)
logo_app = typer.Typer(no_args_is_help=True, add_completion=False)
refdata_app = typer.Typer(no_args_is_help=True, add_completion=False)
clubmap_app = typer.Typer(no_args_is_help=True, add_completion=False)

app.add_typer(auth_app, name="auth")
app.add_typer(club_app, name="club")
app.add_typer(team_app, name="team")
app.add_typer(tournament_app, name="tournament")
app.add_typer(match_app, name="match")
app.add_typer(logo_app, name="logo")
app.add_typer(refdata_app, name="refdata")
app.add_typer(clubmap_app, name="clubmap")


# Shared with backend/mt_cli.py — both tools read/write the same login state.
_MT_CLI_STATE_FILE = _REPO_ROOT / "backend" / ".mt-cli-state.json"


def _load_cached_token() -> tuple[str | None, str | None]:
    """Return (access_token, username) from the shared mt_cli state file."""
    if not _MT_CLI_STATE_FILE.exists():
        return None, None
    try:
        data = json.loads(_MT_CLI_STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None, None
    return data.get("access_token"), data.get("username")


def _client() -> MissingTableClient:
    base_url = os.environ.get("MT_API_BASE_URL", "http://localhost:8000")
    token = os.environ.get("MT_ADMIN_TOKEN")
    if not token:
        token, _username = _load_cached_token()
    if not token:
        typer.echo(
            json.dumps(
                {
                    "error": "not_authenticated",
                    "detail": (
                        "No token found. Either export MT_ADMIN_TOKEN, or run "
                        "the mt_cli login (in your terminal, not via Claude): "
                        "cd backend && uv run python mt_cli.py login <username>"
                    ),
                }
            ),
            err=True,
        )
        raise typer.Exit(code=2)
    return MissingTableClient(base_url=base_url, access_token=token)


def _out(obj: object) -> None:
    typer.echo(json.dumps(obj, indent=2, default=str))


def _err_exit(msg: str, exc: Exception | None = None) -> None:
    payload: dict[str, object] = {"error": msg}
    if isinstance(exc, APIError):
        payload["status_code"] = exc.status_code
        payload["response"] = exc.response_data
    elif exc is not None:
        payload["detail"] = str(exc)
    typer.echo(json.dumps(payload, default=str), err=True)
    raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@auth_app.command("status")
def auth_status() -> None:
    """Report whether a token is available and (when possible) the user's role.

    Resolution order: MT_ADMIN_TOKEN env var → backend/.mt-cli-state.json.
    """
    env_token = os.environ.get("MT_ADMIN_TOKEN")
    cached_token, cached_username = _load_cached_token()
    source = None
    username = None
    if env_token:
        source = "env"
    elif cached_token:
        source = "mt_cli_state"
        username = cached_username
    base_url = os.environ.get("MT_API_BASE_URL", "http://localhost:8000")

    if source is None:
        _out(
            {
                "authenticated": False,
                "source": None,
                "username": None,
                "base_url": base_url,
                "hint": (
                    "Ask the user to run `! cd backend && uv run python mt_cli.py login <username>` "
                    "in their terminal (the `!` prefix runs interactively so getpass can prompt for "
                    "the password). Pick an admin user — admin endpoints reject non-admin tokens."
                ),
            }
        )
        return

    # Probe role by hitting an admin-only endpoint that returns the cheapest payload.
    role: str | None = None
    role_check: str
    try:
        with _client() as c:
            c.lookup_team(name="__role_probe__")
        role = "admin"
        role_check = "ok"
    except APIError as exc:
        if exc.status_code in (401, 403):
            role = "not_admin"
            role_check = f"{exc.status_code}"
        else:
            role_check = f"error:{exc.status_code}"
    _out(
        {
            "authenticated": True,
            "source": source,
            "username": username,
            "base_url": base_url,
            "role": role,
            "role_check": role_check,
        }
    )


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------


@refdata_app.command("show")
def refdata_show() -> None:
    """Print age groups, divisions, seasons, and active tournaments in one shot."""
    with _client() as c:
        try:
            _out(
                {
                    "age_groups": c.get_age_groups(),
                    "divisions": c.get_divisions(),
                    "seasons": c.get_seasons(),
                    "tournaments": c.get_active_tournaments(),
                }
            )
        except APIError as exc:
            _err_exit("failed to load reference data", exc)


# ---------------------------------------------------------------------------
# Local club mapping (MLS NEXT)
# ---------------------------------------------------------------------------

_CLUBMAP_PATH = _REPO_ROOT / "backend" / "data" / "mls-next-clubs.json"


@clubmap_app.command("lookup")
def clubmap_lookup(
    team: str = typer.Option(..., "--team"),
    age_group: str = typer.Option(..., "--age-group", help="e.g. U13, U14, U15, U16, U17, U19"),
) -> None:
    """Look up an MLS NEXT club in backend/data/mls-next-clubs.json.

    Match is case-insensitive on team name. Returns:
      {
        "match": {age_group, division, team, is_pro_academy} | null,
        "all_age_groups_for_team": [...rows for that team across all age groups...]
      }

    Use this when the API team_lookup returns no exact match — it gives the
    correct (division, is_pro_academy) defaults for team creation without
    having to ask the user to guess.
    """
    try:
        data = json.loads(_CLUBMAP_PATH.read_text())
    except FileNotFoundError:
        _err_exit(f"clubmap file not found at {_CLUBMAP_PATH}")
    except json.JSONDecodeError as exc:
        _err_exit("clubmap file is not valid JSON", exc)

    team_lower = team.lower()
    same_team = [r for r in data.get("teams", []) if r["team"].lower() == team_lower]
    match = next((r for r in same_team if r["age_group"] == age_group), None)
    _out({"match": match, "all_age_groups_for_team": same_team})


# ---------------------------------------------------------------------------
# Clubs
# ---------------------------------------------------------------------------


@club_app.command("list")
def club_list(include_teams: bool = typer.Option(False, "--include-teams")) -> None:
    """List all clubs."""
    with _client() as c:
        _out(c.get_clubs(include_teams=include_teams))


@club_app.command("find")
def club_find(name: str = typer.Argument(...)) -> None:
    """Case-insensitive substring search across club names. Local filter (no name-search endpoint exists)."""
    with _client() as c:
        clubs = c.get_clubs()
    needle = name.casefold()
    exact = [club for club in clubs if club.get("name", "").casefold() == needle]
    similar = [club for club in clubs if club not in exact and needle in club.get("name", "").casefold()]
    _out({"exact": exact[0] if exact else None, "similar": similar})


@club_app.command("create")
def club_create(
    name: str = typer.Option(..., "--name"),
    city: str = typer.Option(..., "--city"),
    description: str | None = typer.Option(None, "--description"),
) -> None:
    """Create a new club. Admin only. 409 if name already exists."""
    with _client() as c:
        try:
            _out(c.create_club(name=name, city=city, description=description))
        except APIError as exc:
            _err_exit("failed to create club", exc)


@club_app.command("teams")
def club_teams(club_id: int = typer.Argument(...)) -> None:
    """List a club's existing teams with league, division, and age-group coverage.

    Run this BEFORE creating a team. MT teams are multi-age: one team per
    (club, league) carries mappings for several age groups. Reuse the club's
    existing team in the target league and add an age-group mapping (see
    `team add-age-group`) instead of creating a per-age duplicate.
    """
    with _client() as c:
        teams = c.get_teams()
    out = []
    for t in teams:
        if t.get("club_id") != club_id:
            continue
        ages = sorted(
            {
                (m.get("age_groups") or {}).get("name")
                for m in (t.get("team_mappings") or [])
                if (m.get("age_groups") or {}).get("name")
            }
        )
        out.append(
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "league": (t.get("leagues") or {}).get("name"),
                "division_id": t.get("division_id"),
                "age_groups": ages,
            }
        )
    _out({"club_id": club_id, "teams": out})


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


@team_app.command("lookup")
def team_lookup(name: str = typer.Argument(...)) -> None:
    """Admin team lookup: returns {exact, similar} without creating anything."""
    with _client() as c:
        try:
            _out(c.lookup_team(name=name))
        except APIError as exc:
            _err_exit("failed to lookup team", exc)


@team_app.command("create")
def team_create(
    name: str = typer.Option(..., "--name"),
    city: str = typer.Option(..., "--city"),
    age_group_id: int = typer.Option(..., "--age-group-id"),
    division_id: int = typer.Option(..., "--division-id"),
    club_id: int | None = typer.Option(None, "--club-id"),
    academy_team: bool = typer.Option(False, "--academy-team"),
) -> None:
    """Create a team tied to one age group + division.

    Only create a team when the club has NO team in the target league yet
    (check with `club teams <club_id>` first). To add another age group to an
    EXISTING team, use `team add-age-group` — do not create a per-age duplicate.
    """
    payload = Team(
        name=name,
        city=city,
        age_group_ids=[age_group_id],
        division_id=division_id,
        club_id=club_id,
        academy_team=academy_team,
    )
    with _client() as c:
        try:
            _out(c.create_team(payload))
        except APIError as exc:
            _err_exit("failed to create team", exc)


@team_app.command("add-age-group")
def team_add_age_group(
    team_id: int = typer.Option(..., "--team-id"),
    age_group_id: int = typer.Option(..., "--age-group-id"),
    division_id: int = typer.Option(..., "--division-id"),
) -> None:
    """Add an (age_group, division) mapping to an EXISTING team.

    MT teams are multi-age: this is how a team gains another age group. Use it
    to reuse a club's canonical team across age groups instead of creating a
    per-age duplicate. division_id must be the team's existing division.
    """
    with _client() as c:
        try:
            _out(c.create_team_mapping(team_id, age_group_id, division_id))
        except APIError as exc:
            _err_exit("failed to add team age-group mapping", exc)


# ---------------------------------------------------------------------------
# Tournaments
# ---------------------------------------------------------------------------


@tournament_app.command("list")
def tournament_list() -> None:
    """List active tournaments (public endpoint)."""
    with _client() as c:
        _out(c.get_active_tournaments())


@tournament_app.command("find")
def tournament_find(name: str = typer.Argument(...)) -> None:
    """Case-insensitive substring search across active tournaments."""
    with _client() as c:
        tournaments = c.get_active_tournaments()
    needle = name.casefold()
    exact = [t for t in tournaments if t.get("name", "").casefold() == needle]
    similar = [t for t in tournaments if t not in exact and needle in t.get("name", "").casefold()]
    _out({"exact": exact[0] if exact else None, "similar": similar})


@tournament_app.command("matches")
def tournament_matches(tournament_id: int = typer.Argument(...)) -> None:
    """List a tournament's existing matches so screenshot rows can be mapped to match IDs.

    Prints a compact row per match: id, date, kickoff, status, round, both team
    names/ids, and current scores (incl. penalties). Use this before updating to
    decide create-vs-update and to find the match_id to PUT against.
    """
    with _client() as c:
        try:
            tournament = c.get_tournament(tournament_id)
        except APIError as exc:
            _err_exit("failed to fetch tournament", exc)

    def _team(side: object) -> dict | None:
        if isinstance(side, dict):
            return {"id": side.get("id"), "name": side.get("name")}
        return None

    def _age_group(ag: object) -> dict | None:
        if isinstance(ag, dict):
            return {"id": ag.get("id"), "name": ag.get("name")}
        return None

    matches = [
        {
            "id": m.get("id"),
            "match_date": m.get("match_date"),
            "scheduled_kickoff": m.get("scheduled_kickoff"),
            "match_status": m.get("match_status"),
            "tournament_round": m.get("tournament_round"),
            # Bracket-position fields — required for Step 5 reconcile + the
            # mandatory bracket sanity checks. Omitting these caused the
            # 2026-05-28 MLS NEXT Cup U15 SF incident: existing matches
            # reported group=None/order=None, so the next match was loaded
            # the same way and silently dropped out of the bracket view
            # (frontend filter is `tournament_group === selected`).
            "tournament_group": m.get("tournament_group"),
            "tournament_round_order": m.get("tournament_round_order"),
            "age_group": _age_group(m.get("age_group")),
            "home_team": _team(m.get("home_team")),
            "away_team": _team(m.get("away_team")),
            "home_score": m.get("home_score"),
            "away_score": m.get("away_score"),
            "home_penalty_score": m.get("home_penalty_score"),
            "away_penalty_score": m.get("away_penalty_score"),
        }
        for m in (tournament.get("matches") or [])
    ]
    _out(
        {
            "tournament_id": tournament.get("id"),
            "name": tournament.get("name"),
            "match_count": len(matches),
            "matches": matches,
        }
    )


@tournament_app.command("create")
def tournament_create(
    name: str = typer.Option(..., "--name"),
    start_date: str = typer.Option(..., "--start-date"),
    end_date: str | None = typer.Option(None, "--end-date"),
    location: str | None = typer.Option(None, "--location"),
    description: str | None = typer.Option(None, "--description"),
    age_group_ids: str | None = typer.Option(
        None,
        "--age-group-ids",
        help="Comma-separated age group IDs (e.g. '1,2,3').",
    ),
    is_active: bool = typer.Option(True, "--active/--inactive"),
) -> None:
    """Create a tournament."""
    ag_ids = [int(x.strip()) for x in age_group_ids.split(",") if x.strip()] if age_group_ids else []
    payload = TournamentCreate(
        name=name,
        start_date=start_date,
        end_date=end_date,
        location=location,
        description=description,
        age_group_ids=ag_ids,
        is_active=is_active,
    )
    with _client() as c:
        try:
            _out(c.create_tournament(payload))
        except APIError as exc:
            _err_exit("failed to create tournament", exc)


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------


VALID_ROUNDS = {
    "group_stage",
    "round_of_32",
    "round_of_16",
    "quarterfinal",
    "semifinal",
    "final",
    "third_place",
    "wildcard",
    "silver_semifinal",
    "bronze_semifinal",
    "silver_final",
    "bronze_final",
}


@match_app.command("create")
def match_create(
    tournament_id: int = typer.Option(..., "--tournament-id"),
    our_team_id: int = typer.Option(..., "--our-team-id"),
    opponent_name: str = typer.Option(..., "--opponent-name"),
    match_date: str = typer.Option(..., "--match-date"),
    age_group_id: int = typer.Option(..., "--age-group-id"),
    season_id: int = typer.Option(..., "--season-id"),
    is_home: bool = typer.Option(True, "--home/--away"),
    home_score: int | None = typer.Option(None, "--home-score"),
    away_score: int | None = typer.Option(None, "--away-score"),
    home_penalty_score: int | None = typer.Option(None, "--home-penalty-score"),
    away_penalty_score: int | None = typer.Option(None, "--away-penalty-score"),
    match_status: str = typer.Option("scheduled", "--match-status"),
    tournament_group: str | None = typer.Option(None, "--tournament-group"),
    tournament_round: str | None = typer.Option(None, "--tournament-round"),
    tournament_round_order: int | None = typer.Option(
        None,
        "--tournament-round-order",
        help="Bracket position within the round (0-based, top of bracket = 0). Required for bracket-round matches if you want the bracket UI to render in the canonical order.",
    ),
    scheduled_kickoff: str | None = typer.Option(None, "--scheduled-kickoff"),
) -> None:
    """Add a match to a tournament. our_team_id is one of our tracked teams; opponent_name is the visitor."""
    if tournament_round is not None and tournament_round not in VALID_ROUNDS:
        _err_exit(f"invalid --tournament-round '{tournament_round}'; must be one of: {sorted(VALID_ROUNDS)}")
    payload = TournamentMatchCreate(
        our_team_id=our_team_id,
        opponent_name=opponent_name,
        match_date=match_date,
        age_group_id=age_group_id,
        season_id=season_id,
        is_home=is_home,
        home_score=home_score,
        away_score=away_score,
        home_penalty_score=home_penalty_score,
        away_penalty_score=away_penalty_score,
        match_status=match_status,
        tournament_group=tournament_group,
        tournament_round=tournament_round,
        tournament_round_order=tournament_round_order,
        scheduled_kickoff=scheduled_kickoff,
    )
    with _client() as c:
        try:
            _out(c.create_tournament_match(tournament_id=tournament_id, match=payload))
        except APIError as exc:
            _err_exit("failed to create tournament match", exc)


@match_app.command("update")
def match_update(
    tournament_id: int = typer.Option(..., "--tournament-id"),
    match_id: int = typer.Option(..., "--match-id", help="The MT match id (from `tournament matches`)."),
    home_score: int | None = typer.Option(None, "--home-score"),
    away_score: int | None = typer.Option(None, "--away-score"),
    home_penalty_score: int | None = typer.Option(None, "--home-penalty-score"),
    away_penalty_score: int | None = typer.Option(None, "--away-penalty-score"),
    match_status: str | None = typer.Option(None, "--match-status"),
    tournament_group: str | None = typer.Option(None, "--tournament-group"),
    tournament_round: str | None = typer.Option(None, "--tournament-round"),
    tournament_round_order: int | None = typer.Option(
        None,
        "--tournament-round-order",
        help="Bracket position within the round (0-based, top of bracket = 0).",
    ),
    scheduled_kickoff: str | None = typer.Option(None, "--scheduled-kickoff"),
    match_date: str | None = typer.Option(None, "--match-date"),
    swap_home_away: bool = typer.Option(False, "--swap-home-away", help="Swap which team is home/away."),
    home_team_id: int | None = typer.Option(
        None,
        "--home-team-id",
        help="Replace the home team. Use to resolve a TBD placeholder when the real team is announced.",
    ),
    away_team_id: int | None = typer.Option(
        None,
        "--away-team-id",
        help="Replace the away team. Use to resolve a TBD placeholder when the real team is announced.",
    ),
) -> None:
    """Partially update an existing tournament match (fill in scores/status as results come in).

    Only the options you pass are changed; everything else is left untouched. Use
    `tournament matches <id>` to find the --match-id. Penalty scores are only valid
    when regulation ends in a draw; pass both or neither.
    """
    if tournament_round is not None and tournament_round not in VALID_ROUNDS:
        _err_exit(f"invalid --tournament-round '{tournament_round}'; must be one of: {sorted(VALID_ROUNDS)}")
    payload = TournamentMatchUpdate(
        home_score=home_score,
        away_score=away_score,
        home_penalty_score=home_penalty_score,
        away_penalty_score=away_penalty_score,
        match_status=match_status,
        tournament_group=tournament_group,
        tournament_round=tournament_round,
        tournament_round_order=tournament_round_order,
        scheduled_kickoff=scheduled_kickoff,
        match_date=match_date,
        swap_home_away=swap_home_away,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
    )
    with _client() as c:
        try:
            _out(c.update_tournament_match(tournament_id=tournament_id, match_id=match_id, match=payload))
        except APIError as exc:
            _err_exit("failed to update tournament match", exc)


# ---------------------------------------------------------------------------
# Logos
# ---------------------------------------------------------------------------


@logo_app.command("crop")
def logo_crop(
    image: str = typer.Option(..., "--image", help="Path to the source screenshot."),
    bbox: str = typer.Option(..., "--bbox", help="x,y,w,h in pixels (top-left origin)."),
    output: str = typer.Option(..., "--output", help="Destination PNG path."),
    max_size: int = typer.Option(512, "--max-size", help="Max width/height after thumbnailing."),
) -> None:
    """Crop a logo region from a screenshot and write a square-friendly PNG (≤2MB)."""
    from PIL import Image  # local import: keeps startup fast for non-logo paths

    try:
        x_s, y_s, w_s, h_s = bbox.split(",")
        x, y, w, h = int(x_s), int(y_s), int(w_s), int(h_s)
    except ValueError as exc:
        _err_exit(f"invalid --bbox '{bbox}'; expected 'x,y,w,h'", exc)

    img = Image.open(image).convert("RGBA")
    crop = img.crop((x, y, x + w, y + h))
    crop.thumbnail((max_size, max_size))
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(out_path, "PNG", optimize=True)
    size = out_path.stat().st_size
    if size > 2 * 1024 * 1024:
        _err_exit(
            f"cropped logo is {size} bytes (>2MB limit); try a smaller --max-size",
        )
    _out(
        {
            "output": str(out_path),
            "size_bytes": size,
            "width": crop.width,
            "height": crop.height,
        }
    )


@logo_app.command("upload")
def logo_upload(
    club_id: int = typer.Option(..., "--club-id"),
    path: str = typer.Option(..., "--path"),
) -> None:
    """Upload a PNG/JPG (≤2MB) as a club's logo. Admin only."""
    with _client() as c:
        try:
            _out(c.upload_club_logo(club_id=club_id, file_path=path))
        except APIError as exc:
            _err_exit("failed to upload club logo", exc)


@tournament_app.command("logo-upload")
def tournament_logo_upload(
    tournament_id: int = typer.Option(..., "--tournament-id"),
    path: str = typer.Option(..., "--path"),
) -> None:
    """Upload a PNG/JPG (≤2MB) as a tournament's logo. Admin only.

    Shown on the public tournament page header and on IG share cards for
    matches in this tournament. Mirrors the club logo upload flow — the
    backend generates `_sm` (64px) and `_md` (128px) variants for PNGs
    automatically.
    """
    with _client() as c:
        try:
            _out(c.upload_tournament_logo(tournament_id=tournament_id, file_path=path))
        except APIError as exc:
            _err_exit("failed to upload tournament logo", exc)


if __name__ == "__main__":
    app()

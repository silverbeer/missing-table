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
)

app = typer.Typer(no_args_is_help=True, add_completion=False)
auth_app = typer.Typer(no_args_is_help=True, add_completion=False)
club_app = typer.Typer(no_args_is_help=True, add_completion=False)
team_app = typer.Typer(no_args_is_help=True, add_completion=False)
tournament_app = typer.Typer(no_args_is_help=True, add_completion=False)
match_app = typer.Typer(no_args_is_help=True, add_completion=False)
logo_app = typer.Typer(no_args_is_help=True, add_completion=False)
refdata_app = typer.Typer(no_args_is_help=True, add_completion=False)

app.add_typer(auth_app, name="auth")
app.add_typer(club_app, name="club")
app.add_typer(team_app, name="team")
app.add_typer(tournament_app, name="tournament")
app.add_typer(match_app, name="match")
app.add_typer(logo_app, name="logo")
app.add_typer(refdata_app, name="refdata")


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
    """Create a team tied to one age group + division."""
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
        scheduled_kickoff=scheduled_kickoff,
    )
    with _client() as c:
        try:
            _out(c.create_tournament_match(tournament_id=tournament_id, match=payload))
        except APIError as exc:
            _err_exit("failed to create tournament match", exc)


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


if __name__ == "__main__":
    app()

#!/usr/bin/env python3
"""
Match Tracking CLI for MissingTable

Chat with Claw during matches to post live events.

Usage:
    mt login tom
    mt search --age U14 --days 30
    mt match start 1053
    mt match goal --team home --player "Matt"
    mt match message "Great pass by Carter"
    mt match status
    mt match halftime
    mt match secondhalf
    mt match end
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from getpass import getpass
from pathlib import Path

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from api_client import APIError, AuthenticationError, MissingTableClient
from api_client.models import (
    GoalEvent,
    LiveMatchClock,
    MessageEvent,
    Team,
    TournamentCreate,
    TournamentMatchCreate,
    TournamentMatchUpdate,
)

app = typer.Typer(help="MT Match Tracking CLI")
match_app = typer.Typer(help="Live match tracking commands")
tournament_app = typer.Typer(help="Tournament + bracket seeding commands (admin)")
team_app = typer.Typer(help="Team stats, matches, and admin edits")
player_app = typer.Typer(help="Player stats (read-only)")
club_app = typer.Typer(help="Club admin: create and rename")
alias_app = typer.Typer(help="Team name aliases (admin)")
app.add_typer(match_app, name="match")
app.add_typer(tournament_app, name="tournament")
app.add_typer(team_app, name="team")
app.add_typer(player_app, name="player")
app.add_typer(club_app, name="club")
team_app.add_typer(alias_app, name="alias")
console = Console()

# Valid tournament_round values accepted by the backend (mirrors
# tournament_dao.VALID_ROUNDS). group_stage is the default for bracket pools.
# What -c/--competition accepts beyond a competition name. 'all' is no filter;
# 'qualifying' is the union of the types flagged counts_for_qualification.
QUALIFYING = "qualifying"

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

# Paths
REPO_ROOT = Path(__file__).parent.parent
BACKEND_DIR = Path(__file__).parent
MT_CONFIG_FILE = REPO_ROOT / ".mt-config"
STATE_FILE = BACKEND_DIR / ".mt-cli-state.json"


# --- Models ---


class CLIState(BaseModel):
    """Persistent state for CLI (login session + active match)."""

    access_token: str | None = None
    refresh_token: str | None = None
    username: str | None = None
    match_id: int | None = None
    home_team_name: str | None = None
    away_team_name: str | None = None


# --- Config Helpers ---


def mt_config_get(key: str, default: str = "") -> str:
    """Read a key from .mt-config."""
    if MT_CONFIG_FILE.exists():
        with open(MT_CONFIG_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1]
    return default


def get_current_env() -> str:
    """Get current environment (local or prod)."""
    config_val = mt_config_get("supabase_env")
    if config_val:
        return config_val
    return os.getenv("APP_ENV", "local")


def get_base_url() -> str:
    """Get API base URL for current environment."""
    env = get_current_env()
    env_file = BACKEND_DIR / f".env.{env}"
    if not env_file.exists():
        console.print(f"[red]Environment file not found: {env_file}[/red]")
        raise typer.Exit(1)

    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key] = value

    if env == "local":
        return env_vars.get("BACKEND_URL", "http://localhost:8000")

    base_url = env_vars.get("BACKEND_URL")
    if not base_url:
        console.print(
            "[red]BACKEND_URL not set in .env.prod[/red]\n"
            "[yellow]Add this line to backend/.env.prod:[/yellow]\n"
            "BACKEND_URL=https://your-prod-api.com"
        )
        raise typer.Exit(1)
    return base_url


# --- State Management ---


def load_state() -> CLIState:
    """Load CLI state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            data = json.load(f)
            return CLIState(**data)
    return CLIState()


def save_state(state: CLIState) -> None:
    """Save CLI state to file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state.model_dump(), f, indent=2)


def get_client() -> tuple[MissingTableClient, CLIState]:
    """Get an authenticated MissingTableClient and current state."""
    state = load_state()
    if not state.access_token:
        console.print("[red]Not logged in[/red]\n[yellow]Login first:[/yellow] mt login <username>")
        raise typer.Exit(1)

    client = MissingTableClient(
        base_url=get_base_url(),
        access_token=state.access_token,
    )
    return client, state


def require_active_match(state: CLIState) -> int:
    """Return the active match_id from state, or exit with an error."""
    if not state.match_id:
        console.print("[red]No active match[/red]\n[yellow]Start a match first:[/yellow] mt match start <match_id>")
        raise typer.Exit(1)
    return state.match_id


# --- Helpers ---


def op_reference(username: str) -> str:
    """Where mt looks in 1Password for this environment's login.

    Overridable with MT_OP_ITEM or an `op_item` line in .mt-config, so a second
    account or vault does not need a code change. Defaults to the mt-<env> item
    the account already uses for infrastructure secrets.
    """
    explicit = os.environ.get("MT_OP_ITEM") or mt_config_get("op_item")
    if explicit:
        return explicit.replace("{env}", get_current_env()).replace("{user}", username)
    return f"op://Personal/mt-{get_current_env()}/credential"


def password_from_op(username: str) -> str | None:
    """Read the login password from 1Password, or None if unavailable.

    Never raises: 1Password not installed, locked, or the field missing are all
    ordinary situations that should fall through to the next source rather than
    stop the command. Output is deliberately not logged — a password in a
    terminal transcript is permanent.
    """
    reference = op_reference(username)
    try:
        result = subprocess.run(  # noqa: S603
            ["op", "read", reference],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _load_env_vars() -> dict[str, str]:
    """Load env vars for the current environment."""
    env = get_current_env()
    env_file = BACKEND_DIR / f".env.{env}"
    if not env_file.exists():
        return {}
    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key] = value
    return env_vars


def _resolve_team(live: dict, team_arg: str) -> tuple[int, str]:
    """Resolve a team argument to (team_id, team_name).

    Accepts "home", "away", or a case-insensitive substring of a team name.
    """
    home_id = live["home_team_id"]
    away_id = live["away_team_id"]
    home_name = live.get("home_team_name", "Home")
    away_name = live.get("away_team_name", "Away")

    lower = team_arg.lower()

    if lower == "home":
        return home_id, home_name
    if lower == "away":
        return away_id, away_name

    # Try case-insensitive substring match against team names
    home_match = lower in home_name.lower()
    away_match = lower in away_name.lower()

    if home_match and away_match:
        console.print(
            f"[red]'{team_arg}' matches both teams:[/red] {home_name} and {away_name}\n"
            "[yellow]Use 'home' or 'away' to disambiguate[/yellow]"
        )
        raise typer.Exit(1)

    if home_match:
        return home_id, home_name
    if away_match:
        return away_id, away_name

    console.print(
        f"[red]'{team_arg}' doesn't match either team[/red]\n"
        f"  Home: {home_name}\n"
        f"  Away: {away_name}\n"
        "[yellow]Use 'home', 'away', or part of a team name[/yellow]"
    )
    raise typer.Exit(1)


def _resolve_player(
    client: MissingTableClient, team_id: int, season_id: int | None, player_arg: str
) -> tuple[int | None, str | None]:
    """Resolve a player argument to (player_id, display_name).

    Accepts a jersey number or a player name (case-insensitive substring).
    Returns (None, None) if roster lookup fails gracefully.
    """
    # Try as jersey number first
    try:
        jersey = int(player_arg)
    except ValueError:
        jersey = None

    # Fetch roster
    roster = []
    if season_id:
        try:
            result = client.get_team_roster(team_id, season_id=season_id)
            roster = result.get("roster", [])
        except Exception as e:
            console.print(f"[yellow]Could not fetch roster: {e}[/yellow]")

    if jersey is not None:
        # Look up by jersey number
        player = next((p for p in roster if p.get("jersey_number") == jersey), None)
        if not player:
            if roster:
                console.print(f"[yellow]No player #{jersey} on roster — recording goal without player[/yellow]")
            return None, f"#{jersey}"

        display = player.get("display_name") or player.get("first_name") or f"#{jersey}"
        return player.get("id"), display

    # Look up by name (case-insensitive substring)
    if roster:
        matches = []
        for p in roster:
            name = p.get("display_name") or p.get("first_name") or ""
            if player_arg.lower() in name.lower():
                matches.append(p)

        if len(matches) == 1:
            p = matches[0]
            display = p.get("display_name") or p.get("first_name") or f"#{p.get('jersey_number')}"
            return p.get("id"), display

        if len(matches) > 1:
            console.print(f"[yellow]'{player_arg}' matches multiple players:[/yellow]")
            for p in matches:
                name = p.get("display_name") or p.get("first_name") or "?"
                console.print(f"  #{p.get('jersey_number')} {name}")
            console.print("[yellow]Use the jersey number instead[/yellow]")
            raise typer.Exit(1)

    # No roster match — use as free-text name
    return None, player_arg


def _parse_ts(value: str | None) -> datetime | None:
    """Parse an ISO timestamp string to datetime."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _match_clock(live: dict) -> tuple[str, str]:
    """Calculate current period and match minute from live state.

    Returns (period, minute_display) e.g. ("1st Half", "23'") or ("Halftime", "40'").
    """
    kickoff_time = _parse_ts(live.get("kickoff_time"))
    halftime_start = _parse_ts(live.get("halftime_start"))
    second_half_start = _parse_ts(live.get("second_half_start"))
    match_end_time = _parse_ts(live.get("match_end_time"))
    half_duration = live.get("half_duration") or 45

    if not kickoff_time:
        return "Pre-match", "-"

    if match_end_time:
        return "Full time", f"{half_duration * 2}'"

    now = datetime.now(UTC)

    if second_half_start:
        elapsed = int((now - second_half_start).total_seconds() / 60) + 1
        minute = half_duration + elapsed
        full_time = half_duration * 2
        if minute > full_time:
            return "2nd Half", f"{full_time}+{minute - full_time}'"
        return "2nd Half", f"{minute}'"

    if halftime_start:
        return "Halftime", f"{half_duration}'"

    elapsed = int((now - kickoff_time).total_seconds() / 60) + 1
    if elapsed > half_duration:
        return "1st Half", f"{half_duration}+{elapsed - half_duration}'"
    return "1st Half", f"{elapsed}'"


# --- Top-level Commands ---


@app.command()
def login(username: str = typer.Argument("tom", help="Username to login with (default: tom)")):
    """Login to the MT API."""
    # Try to find password from env file: TEST_USER_PASSWORD_<USERNAME>
    env_vars = _load_env_vars()
    env_key = f"TEST_USER_PASSWORD_{username.upper().replace('-', '_')}"
    password = env_vars.get(env_key)

    if password:
        console.print(f"[dim]Using password from {env_key}[/dim]")
    elif os.environ.get("MT_PASSWORD"):
        password = os.environ["MT_PASSWORD"]
        console.print("[dim]Using password from MT_PASSWORD[/dim]")
    elif (from_op := password_from_op(username)) is not None:
        password = from_op
        console.print(f"[dim]Using password from {op_reference(username)}[/dim]")
    elif not sys.stdin.isatty():
        # getpass cannot turn off echo without a terminal, so it warns, echoes
        # the password and aborts. Refuse up front instead: an agent shell or a
        # piped session should be told what to do, not shown a typed password.
        console.print("[red]No terminal available for a password prompt.[/red]")
        console.print(
            f"Set [cyan]MT_PASSWORD[/cyan] or [cyan]{env_key}[/cyan], or run [cyan]mt login[/cyan] in a terminal."
        )
        raise typer.Exit(1)
    else:
        password = getpass(f"Password for {username}: ")

    base_url = get_base_url()
    client = MissingTableClient(base_url=base_url)

    try:
        result = client.login(username, password)
    except AuthenticationError as e:
        console.print(f"[red]Login failed: {e}[/red]")
        raise typer.Exit(1) from None
    finally:
        client.close()

    # Preserve any existing match state
    state = load_state()
    state.access_token = result.get("access_token")
    state.refresh_token = result.get("refresh_token")
    state.username = username
    save_state(state)

    user = result.get("user", {})
    role = user.get("role", "unknown")
    console.print(f"[green]Logged in as {username} ({role})[/green]")
    console.print(f"[dim]Environment: {get_current_env()}[/dim]")


@app.command()
def logout():
    """Logout and clear stored credentials."""
    state = load_state()
    state.access_token = None
    state.refresh_token = None
    state.username = None
    save_state(state)
    console.print("[green]Logged out[/green]")


@app.command()
def config():
    """Show current configuration."""
    env = get_current_env()
    base_url = get_base_url()
    state = load_state()

    table = Table(title="MT CLI Configuration", show_header=False)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Environment", env)
    table.add_row("API URL", base_url)
    table.add_row("Logged in as", state.username or "Not logged in")
    if state.match_id:
        match_label = f"#{state.match_id}"
        if state.home_team_name and state.away_team_name:
            match_label += f" ({state.home_team_name} vs {state.away_team_name})"
        table.add_row("Active match", match_label)

    console.print(table)
    console.print(f"\n[dim]Config file: {MT_CONFIG_FILE}[/dim]")
    console.print(f"[dim]State file: {STATE_FILE}[/dim]")


@app.command()
def search(
    age_group: str = typer.Option(None, "--age", "-a", help="Filter by age group (e.g., 'U13', 'U14')"),
    team: str = typer.Option(None, "--team", "-t", help="Filter by team name (substring match)"),
    days: int = typer.Option(7, "--days", "-d", help="Number of days to search (default: 7)"),
):
    """Search for upcoming matches by age group, team, and date range."""
    client, _ = get_client()

    now = datetime.now(UTC)
    start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    end = datetime.fromtimestamp(start.timestamp() + (days * 86400), tz=UTC)

    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    matches = client.get_games(start_date=start_str, end_date=end_str)

    # Filter by age group and team if provided
    filtered = []
    for match in matches:
        home_name = match.get("home_team_name", "Unknown")
        away_name = match.get("away_team_name", "Unknown")
        age_name = match.get("age_group_name", "Unknown")

        if age_group:
            if age_group.lower() not in age_name.lower():
                continue

        if team:
            if team.lower() not in home_name.lower() and team.lower() not in away_name.lower():
                continue

        filtered.append(match)

    if not filtered:
        console.print("[yellow]No matches found matching your criteria.[/yellow]")
        return

    table = Table(title=f"Upcoming Matches (Next {days} days)")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Date", style="magenta")
    table.add_column("Home", style="white")
    table.add_column("Away", style="white")
    table.add_column("Age", style="yellow")

    for m in filtered:
        match_id = str(m.get("id", "?"))
        date_str = m.get("match_date", "?")
        home = m.get("home_team_name", "Unknown")
        away = m.get("away_team_name", "Unknown")
        age = m.get("age_group_name", "?")

        table.add_row(match_id, date_str, home, away, age)

    console.print(table)
    console.print(f"\n[dim]Found {len(filtered)} match(es)[/dim]")
    console.print("[green]Use 'mt match start <match_id>' to start tracking[/green]")


# --- Match Subcommands ---


@match_app.command()
def start(
    match_id: int = typer.Argument(..., help="Match ID to track"),
    half: int = typer.Option(40, "--half", help="Half duration in minutes (default: 40)"),
):
    """Start tracking a match and kick off the first half."""
    client, state = get_client()

    console.print(f"[dim]Fetching match {match_id}...[/dim]")
    try:
        match = client.get_game(match_id)
    except AuthenticationError:
        console.print("[red]Session expired[/red]\n[yellow]Login again:[/yellow] mt login <username>")
        raise typer.Exit(1) from None
    except APIError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    # Start the match clock (sets status to live, records kickoff time)
    clock = LiveMatchClock(action="start_first_half", half_duration=half)
    client.update_match_clock(match_id, clock)

    # Save match_id and team names to state
    home_name = match.get("home_team_name") or "Unknown"
    away_name = match.get("away_team_name") or "Unknown"
    state.match_id = match_id
    state.home_team_name = home_name
    state.away_team_name = away_name
    save_state(state)

    table = Table(title=f"Match #{match_id}", show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Home", home_name)
    table.add_row("Away", away_name)
    table.add_row("Date", match.get("match_date", "Unknown"))
    table.add_row("Half Duration", f"{half} min/half = {half * 2} min total")
    table.add_row("Status", "live")

    console.print(table)
    console.print(f"[green]Match {match_id} kicked off![/green]")
    console.print(f"[dim]Environment: {get_current_env()}[/dim]")


@match_app.command()
def goal(
    team: str = typer.Option(..., "--team", "-t", help="Team: 'home', 'away', or team name"),
    player: str = typer.Option(None, "--player", "-p", help="Player: jersey number or name (optional)"),
):
    """Record a goal."""
    client, state = get_client()
    match_id = require_active_match(state)

    live = client.get_live_match_state(match_id)
    team_id, team_name = _resolve_team(live, team)

    # Resolve player if provided
    player_id = None
    player_display = None
    if player:
        player_id, player_display = _resolve_player(client, team_id, live.get("season_id"), player)

    # Build and post goal event
    goal_event = GoalEvent(
        team_id=team_id,
        player_id=player_id,
        player_name=player_display,
    )
    client.post_goal(match_id, goal_event)

    # Calculate current minute for display
    _, minute = _match_clock(live)

    scorer = f" - {player_display}" if player_display else ""
    console.print(
        Panel(
            f"[bold]{team_name}[/bold]{scorer} ({minute})",
            title="Goal!",
            border_style="green",
        )
    )


@match_app.command()
def message(
    text: str = typer.Argument(..., help="Message text"),
):
    """Post a chat message to the match."""
    client, state = get_client()
    match_id = require_active_match(state)

    msg = MessageEvent(message=text)
    client.post_message(match_id, msg)

    console.print(f"[dim]{text}[/dim]")


@match_app.command()
def status(
    match_id_arg: int = typer.Argument(None, metavar="MATCH_ID", help="Match ID (uses active match if omitted)"),
):
    """Show live match status."""
    client, state = get_client()
    match_id = match_id_arg if match_id_arg is not None else require_active_match(state)

    live = client.get_live_match_state(match_id)

    home_name = live.get("home_team_name", "Home")
    away_name = live.get("away_team_name", "Away")
    period, minute = _match_clock(live)

    home_score = live.get("home_score", 0)
    away_score = live.get("away_score", 0)

    table = Table(title=f"Match #{match_id}", show_header=False)
    table.add_column("Field", style="cyan", width=15)
    table.add_column("Value", style="white")

    table.add_row("Home", f"{home_name} — {home_score}")
    table.add_row("Away", f"{away_name} — {away_score}")
    table.add_row("Status", live.get("match_status", "Unknown"))
    table.add_row("Period", period)
    table.add_row("Minute", minute)
    table.add_row("Half Duration", f"{live.get('half_duration', '-')} min")

    console.print(table)

    # Fetch full event list and filter out status-change noise so every goal is shown.
    # The /live endpoint returns events newest-first; using [-N:] on that list would
    # show only the oldest entries, hiding recent goals (the original bug).
    events_to_show: list[dict] = []
    try:
        all_events = client.get_match_events(match_id)
        # all_events is newest-first; reverse to chronological order.
        # Exclude status_change events (kickoff, halftime, etc.) from the CLI display —
        # those are already surfaced via the Period/Status rows above.
        _SKIP_TYPES = {"status_change"}
        events_to_show = [e for e in reversed(all_events) if e.get("event_type") not in _SKIP_TYPES]
    except Exception:
        # Graceful fallback: use whatever recent_events the /live response included,
        # but fix the ordering bug by taking the first (newest) entries, not the last.
        raw = live.get("recent_events") or []
        events_to_show = list(reversed(raw[:10]))

    if events_to_show:
        console.print("\n[bold]Match Events:[/bold]")
        for event in events_to_show:
            event_type = event.get("event_type", "")
            msg = event.get("message", "")
            minute = event.get("match_minute")
            extra = event.get("extra_time")
            if minute is not None:
                minute_str = f"{minute}+{extra}'" if extra else f"{minute}'"
                console.print(f"  [dim]{minute_str}[/dim] {msg}")
            else:
                console.print(f"  [dim]{event_type}:[/dim] {msg}")


@match_app.command()
def halftime():
    """End the first half (start halftime)."""
    client, state = get_client()
    match_id = require_active_match(state)

    clock = LiveMatchClock(action="start_halftime")
    client.update_match_clock(match_id, clock)
    console.print(f"[green]Match {match_id} — Halftime[/green]")


@match_app.command()
def secondhalf():
    """Start the second half."""
    client, state = get_client()
    match_id = require_active_match(state)

    clock = LiveMatchClock(action="start_second_half")
    client.update_match_clock(match_id, clock)
    console.print(f"[green]Match {match_id} — Second half kicked off[/green]")


@match_app.command()
def end():
    """End the match (full time) and clear active match."""
    client, state = get_client()
    match_id = require_active_match(state)

    clock = LiveMatchClock(action="end_match")
    client.update_match_clock(match_id, clock)

    console.print(f"[green]Match {match_id} — Full time[/green]")

    # Clear match state
    state.match_id = None
    state.home_team_name = None
    state.away_team_name = None
    save_state(state)


# --- Tournament helpers ---


def _resolve_age_group_id(client: MissingTableClient, name: str) -> int:
    """Resolve an age-group name (e.g. 'U14') to its id. Exits on no match."""
    groups = client.get_age_groups()
    lower = name.lower()
    # Exact (case-insensitive) first, then substring.
    for g in groups:
        if g.get("name", "").lower() == lower:
            return g["id"]
    for g in groups:
        if lower in g.get("name", "").lower():
            return g["id"]
    available = ", ".join(sorted(g.get("name", "?") for g in groups))
    console.print(f"[red]Age group '{name}' not found[/red]\n[yellow]Available:[/yellow] {available}")
    raise typer.Exit(1)


def _resolve_season_id(client: MissingTableClient, season: str | None) -> int:
    """Resolve a season name to its id, or use the current season when omitted."""
    if season:
        lower = season.lower()
        for s in client.get_seasons():
            if lower in s.get("name", "").lower():
                return s["id"]
        console.print(f"[red]Season '{season}' not found[/red]")
        raise typer.Exit(1)
    current = client.get_current_season()
    if not current or "id" not in current:
        console.print(
            "[red]No current season set[/red]\n[yellow]Pass --season explicitly (e.g. --season 2025-2026)[/yellow]"
        )
        raise typer.Exit(1)
    return current["id"]


def _resolve_team_id(client: MissingTableClient, name: str) -> tuple[int, str]:
    """Resolve a team name to (id, name) via the admin lookup endpoint.

    Requires an exact match — seeding should never silently pick the wrong team.
    """
    result = client.lookup_team(name)
    exact = result.get("exact")
    if exact:
        return exact["id"], exact["name"]
    similar = result.get("similar") or []
    hint = ""
    if similar:
        hint = "\n[yellow]Did you mean:[/yellow] " + ", ".join(t.get("name", "?") for t in similar[:5])
    console.print(f"[red]No exact team match for '{name}'[/red]{hint}")
    raise typer.Exit(1)


# --- Tournament Subcommands ---


@tournament_app.command("create")
def tournament_create(
    name: str = typer.Option(..., "--name", "-n", help="Tournament name"),
    start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(None, "--end", "-e", help="End date (YYYY-MM-DD)"),
    age: list[str] = typer.Option(None, "--age", "-a", help="Age group(s), e.g. -a U14 (repeatable)"),
    location: str = typer.Option(None, "--location", help="Location"),
    description: str = typer.Option(None, "--description", help="Description"),
    inactive: bool = typer.Option(False, "--inactive", help="Create as inactive"),
):
    """Create a new tournament (admin). Prints the new tournament id."""
    client, _ = get_client()
    age_group_ids = [_resolve_age_group_id(client, a) for a in (age or [])]
    payload = TournamentCreate(
        name=name,
        start_date=start,
        end_date=end,
        location=location,
        description=description,
        age_group_ids=age_group_ids,
        is_active=not inactive,
    )
    try:
        created = client.create_tournament(payload)
    except APIError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    tid = created.get("id")
    console.print(f"[green]Created tournament #{tid}:[/green] {name}")
    console.print(f"[dim]Environment: {get_current_env()}[/dim]")
    console.print(
        f"[dim]Add matches:[/dim] mt tournament add-match --tournament {tid} "
        '--home "Team A" --away "Team B" --age U14 --bracket "Bracket A" --date '
        f"{start}"
    )


@tournament_app.command("list")
def tournament_list():
    """List active tournaments."""
    client, _ = get_client()
    tournaments = client.get_active_tournaments()
    if not tournaments:
        console.print("[yellow]No active tournaments.[/yellow]")
        return
    table = Table(title="Active Tournaments")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Start", style="magenta")
    table.add_column("End", style="magenta")
    for t in tournaments:
        table.add_row(
            str(t.get("id", "?")),
            t.get("name", "?"),
            str(t.get("start_date", "")),
            str(t.get("end_date", "") or ""),
        )
    console.print(table)


@tournament_app.command("show")
def tournament_show(
    tournament_id: int = typer.Argument(..., help="Tournament ID"),
):
    """Show a tournament's matches grouped by bracket + round."""
    client, _ = get_client()
    try:
        t = client.get_tournament(tournament_id)
    except APIError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    console.print(f"[bold]{t.get('name', '?')}[/bold] (#{tournament_id})")
    matches = t.get("matches", []) or []
    if not matches:
        console.print("[yellow]No matches yet.[/yellow]")
        return
    table = Table(title=f"{len(matches)} matches")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Bracket", style="yellow")
    table.add_column("Age", style="yellow")
    table.add_column("Round", style="blue")
    table.add_column("Home", style="white")
    table.add_column("Away", style="white")
    table.add_column("Score", style="green")
    table.add_column("Status", style="magenta")
    for m in matches:
        score = ""
        if m.get("home_score") is not None and m.get("away_score") is not None:
            score = f"{m['home_score']}-{m['away_score']}"
        table.add_row(
            str(m.get("id", "?")),
            str(m.get("tournament_group") or ""),
            str((m.get("age_group") or {}).get("name") or m.get("age_group_name") or ""),
            str(m.get("tournament_round") or ""),
            str(m.get("home_team_name") or (m.get("home_team") or {}).get("name") or "?"),
            str(m.get("away_team_name") or (m.get("away_team") or {}).get("name") or "?"),
            score,
            str(m.get("match_status") or ""),
        )
    console.print(table)


@tournament_app.command("add-match")
def tournament_add_match(
    tournament: int = typer.Option(..., "--tournament", "-T", help="Tournament ID"),
    home: str = typer.Option(..., "--home", help="Home team name (must exist exactly)"),
    away: str = typer.Option(..., "--away", help="Away team name (created if new)"),
    age: str = typer.Option(..., "--age", "-a", help="Age group, e.g. U14"),
    date: str = typer.Option(..., "--date", "-d", help="Match date (YYYY-MM-DD)"),
    bracket: str = typer.Option(None, "--bracket", "-b", help="Bracket / tournament_group, e.g. 'Bracket A'"),
    round_: str = typer.Option("group_stage", "--round", "-r", help=f"Round ({', '.join(sorted(VALID_ROUNDS))})"),
    order: int = typer.Option(None, "--order", help="tournament_round_order (bracket position)"),
    kickoff: str = typer.Option(None, "--kickoff", "-k", help="Scheduled kickoff ISO ts, e.g. 2026-06-07T14:00:00Z"),
    home_score: int = typer.Option(None, "--home-score", help="Home score"),
    away_score: int = typer.Option(None, "--away-score", help="Away score"),
    status: str = typer.Option("scheduled", "--status", help="Match status"),
    season: str = typer.Option(None, "--season", help="Season name (default: current)"),
):
    """Add a match to a tournament bracket (admin).

    The home team must already exist; the away team is created on the fly if
    its name doesn't match an existing team (backend get_or_create).
    """
    if round_ not in VALID_ROUNDS:
        console.print(f"[red]Invalid round '{round_}'[/red]\n[yellow]Valid:[/yellow] {', '.join(sorted(VALID_ROUNDS))}")
        raise typer.Exit(1)

    client, _ = get_client()
    age_group_id = _resolve_age_group_id(client, age)
    season_id = _resolve_season_id(client, season)
    home_id, home_name = _resolve_team_id(client, home)

    payload = TournamentMatchCreate(
        home_team_id=home_id,
        away_team_name=away,
        match_date=date,
        age_group_id=age_group_id,
        season_id=season_id,
        home_score=home_score,
        away_score=away_score,
        match_status=status,
        tournament_group=bracket,
        tournament_round=round_,
        tournament_round_order=order,
        scheduled_kickoff=kickoff,
    )
    try:
        created = client.create_tournament_match(tournament, payload)
    except APIError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    mid = created.get("id", "?")
    bracket_label = f" [{bracket}]" if bracket else ""
    console.print(f"[green]Added match #{mid}[/green]{bracket_label} {home_name} vs {away} ({age}, {round_})")


@tournament_app.command("remove-match")
def tournament_remove_match(
    tournament: int = typer.Option(..., "--tournament", "-T", help="Tournament ID"),
    match: int = typer.Option(..., "--match", "-m", help="Match ID to delete"),
):
    """Delete a match from a tournament (admin)."""
    client, _ = get_client()
    try:
        client.delete_tournament_match(tournament, match)
    except APIError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None
    console.print(f"[green]Removed match #{match} from tournament #{tournament}[/green]")


@tournament_app.command("score")
def tournament_score(
    tournament: int = typer.Option(..., "--tournament", "-T", help="Tournament ID"),
    match: int = typer.Option(..., "--match", "-m", help="Match ID"),
    home_score: int = typer.Option(..., "--home", help="Home score"),
    away_score: int = typer.Option(..., "--away", help="Away score"),
    status: str = typer.Option("completed", "--status", help="Match status"),
):
    """Set a tournament match's final score (admin).

    Goes through the admin match-write path, which fires the 'fulltime'
    follower notification — this is what bracket followers receive.
    """
    client, _ = get_client()
    payload = TournamentMatchUpdate(home_score=home_score, away_score=away_score, match_status=status)
    try:
        client.update_tournament_match(tournament, match, payload)
    except APIError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None
    console.print(
        f"[green]Match #{match} → {home_score}-{away_score} ({status})[/green]  "
        "[dim]fulltime notification fired to bracket + team followers[/dim]"
    )


# --- Read commands (SB-672) -------------------------------------------------
#
# `mt` could drive a match but not ask about one, so a data question ("why does
# this squad show 3 games played after 2 friendlies?") meant reading source and
# running SQL by hand. These go over HTTP with the existing `mt login` session —
# no database credentials anywhere.


class ResolutionError(Exception):
    """A name did not resolve to exactly one thing."""


# Mirrors GoldenBoot.vue, in the same order. A stat that disagrees between the
# CLI and the web board is worse than one missing from either.
STAT_FIELDS = [
    ("GP", "games_played"),
    ("GS", "games_started"),
    ("G", "total_goals"),
    ("A", "total_assists"),
    ("YC", "total_yellow_cards"),
    ("RC", "total_red_cards"),
]

SORT_FIELDS = {key.lower(): field for key, field in STAT_FIELDS}


def resolve_team(client, term: str) -> dict:
    """One team, by id or by name.

    Team names carry no age group — the squad shown as "IFA U15 HG" on the team
    page is the team named "IFA" — so a plausible-looking query matches nothing.
    A bare "no team" is a dead end, so near-misses are offered instead.
    """
    teams = client.get_teams() or []

    # By id, from the list rather than GET /api/teams/{id} — that route does not
    # exist. /api/teams/{team_id} serves only PUT and DELETE, so the by-id
    # lookup returned 405 for every numeric argument (SB-824). The list is
    # already fetched for name resolution, so this costs nothing extra.
    if str(term).isdigit():
        target = int(term)
        for t in teams:
            if t.get("id") == target:
                return t
        raise ResolutionError(f"No team with id {target}")

    needle = term.lower().strip()

    # An exact name wins outright: "IFA" should resolve, even though a dozen
    # other teams have it as a prefix.
    exact = [t for t in teams if (t.get("name") or "").lower().strip() == needle]
    if len(exact) == 1:
        return exact[0]

    matches = [t for t in teams if needle in (t.get("name") or "").lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(t.get("name", "?") for t in matches[:6])
        more = "" if len(matches) <= 6 else f" (+{len(matches) - 6} more)"
        raise ResolutionError(f"{len(matches)} teams match {term!r}: {names}{more}")

    # Nothing contains the whole string. Fall back to word-by-word so a query
    # that mixes a club with an age group still points somewhere useful.
    tokens = [w for w in needle.split() if w]
    near = [t for t in teams if any(w in (t.get("name") or "").lower() for w in tokens)]
    if near:
        names = ", ".join(t.get("name", "?") for t in near[:8])
        more = "" if len(near) <= 8 else f" (+{len(near) - 8} more)"
        raise ResolutionError(f"No team named {term!r}. Did you mean: {names}{more}")
    raise ResolutionError(f"No team matching {term!r}")


def resolve_season(client, name: str | None = None) -> dict | None:
    """The named season, or the current one."""
    seasons = client.get_seasons() or []
    if name:
        needle = name.lower()
        matches = [s for s in seasons if needle in (s.get("name") or "").lower()]
        if not matches:
            raise ResolutionError(f"No season matching {name!r}")
        return matches[0]
    return next((s for s in seasons if s.get("is_current")), seasons[0] if seasons else None)


def resolve_match_type(client, name: str | None = None) -> dict | None:
    """The named competition, or League by default. None means every competition.

    Defaulting to League matches the web board: a squad total that silently
    folds friendlies in is not comparable with the league table beside it.

    One competition only. `qualifying` spans several, so it belongs to
    resolve_match_types and to the commands that can filter a list client-side
    — /api/team-stats takes a single match_type_id and cannot union.
    """
    if name and name.lower() == "all":
        return None
    if name and name.lower() == QUALIFYING:
        raise ResolutionError(
            f"{QUALIFYING!r} spans several competitions and is not available here — "
            "name one, or use 'all'. `mt team matches -c qualifying` does support it."
        )

    types = client.get_match_types() or []
    needle = (name or "league").lower()
    matches = [t for t in types if needle in (t.get("name") or "").lower()]
    if matches:
        return matches[0]
    if name:
        raise ResolutionError(f"No competition matching {name!r}")
    # No League configured is not an error — show everything rather than nothing.
    return None


def resolve_match_types(client, name: str | None = None) -> list[dict] | None:
    """Every competition a selection covers, or None for all of them.

    Unlike resolve_match_type this defaults to *all*. A schedule should open
    showing the schedule: hiding four fixtures because they are friendlies is
    the surprise, not the service. Stats default to League for the opposite
    reason — see resolve_match_type.

    `qualifying` is the union of the types flagged counts_for_qualification,
    read from the API rather than listed here, so the next qualifying
    competition is one flag in one row and not an edit in the CLI, the Matches
    filter and the standings separately (SB-849).
    """
    if name is None or name.lower() == "all":
        return None

    types = client.get_match_types() or []
    needle = name.lower()

    if needle == QUALIFYING:
        flagged = [t for t in types if t.get("counts_for_qualification")]
        if not flagged:
            raise ResolutionError(
                "No competition is flagged as counting for qualification, "
                "so there is nothing to combine under 'qualifying'."
            )
        return flagged

    matches = [t for t in types if needle in (t.get("name") or "").lower()]
    if not matches:
        known = ", ".join(t.get("name") or "?" for t in types) or "none configured"
        raise ResolutionError(f"No competition matching {name!r}. Known: {known}")
    return [matches[0]]


def match_type_id_of(match: dict) -> int | None:
    """The match's competition id, from either shape the API returns."""
    return match.get("match_type_id") or (match.get("match_type") or {}).get("id")


def took_part(player: dict) -> bool:
    """Did this player do anything recordable? Mirrors the web board (SB-670)."""
    return any((player.get(field) or 0) > 0 for _, field in STAT_FIELDS)


def _player_label(p: dict) -> str:
    name = f"{p.get('first_name') or ''} {p.get('last_name') or ''}".strip()
    jersey = p.get("jersey_number")
    if name and jersey:
        return f"#{jersey} {name}"
    return name or (f"#{jersey}" if jersey else "?")


def sort_stats(players: list[dict], sort_key: str = "g") -> list[dict]:
    """Sort as the web board does: chosen column, then goals, then assists, then name."""
    primary = SORT_FIELDS.get(sort_key.lower(), "total_goals")

    def key(p: dict):
        return (
            -(p.get(primary) or 0),
            -(p.get("total_goals") or 0),
            -(p.get("total_assists") or 0),
            _player_label(p),
        )

    return sorted(players, key=key)


def _fail(message: str) -> None:
    console.print(f"[red]{message}[/red]")
    raise typer.Exit(1)


def _api(fn, *args, **kwargs):
    """Call the API, turning a dead session into advice rather than a traceback.

    The write commands already catch this; the read commands did not, so an
    expired token dumped a full rich traceback at someone who only asked for a
    table (SB-672).
    """
    try:
        return fn(*args, **kwargs)
    except AuthenticationError:
        console.print("[red]Session expired.[/red] Run [cyan]mt login[/cyan] and try again.")
        raise typer.Exit(1) from None
    except ResolutionError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from None
    except APIError as exc:
        console.print(f"[red]API error: {exc}[/red]")
        raise typer.Exit(1) from None


@team_app.command("stats")
def team_stats(
    team: str = typer.Argument(..., help="Team name or id"),
    season: str = typer.Option(None, "--season", "-s", help="Season name (default: current)"),
    competition: str = typer.Option(
        None, "--competition", "-c", help="League (default), Friendly, Tournament, or 'all'"
    ),
    sort: str = typer.Option("g", "--sort", help="Column to sort by: gp, gs, g, a, yc, rc"),
    everyone: bool = typer.Option(False, "--everyone", help="Include players who have not played"),
):
    """The Golden Boot board for a team."""
    client, _ = get_client()

    team_row = _api(resolve_team, client, team)
    season_row = _api(resolve_season, client, season)
    match_type = _api(resolve_match_type, client, competition)

    if not season_row:
        _fail("No season configured")

    payload = _api(
        client.get_team_stats,
        team_row["id"],
        season_id=season_row["id"],
        match_type_id=(match_type or {}).get("id"),
    )
    players = payload.get("players") if isinstance(payload, dict) else payload
    players = players or []
    if not everyone:
        players = [p for p in players if took_part(p)]

    scope = (match_type or {}).get("name", "All competitions")
    title = f"Golden Boot — {team_row.get('name', team)} · {season_row.get('name', '?')} · {scope}"

    if not players:
        console.print(f"[yellow]Nothing recorded for {team_row.get('name', team)} in {scope}.[/yellow]")
        console.print("[dim]Appearances and goals appear once matches are scored in the app.[/dim]")
        return

    table = Table(title=title)
    table.add_column("#", style="dim", no_wrap=True)
    table.add_column("Player", style="white")
    for label, _field in STAT_FIELDS:
        table.add_column(label, justify="right", style="cyan")

    for rank, p in enumerate(sort_stats(players, sort), start=1):
        table.add_row(str(rank), _player_label(p), *[str(p.get(f) or 0) for _, f in STAT_FIELDS])

    console.print(table)
    console.print(f"[dim]{len(players)} player(s) · sorted by {sort.upper()}[/dim]")


@team_app.command("matches")
def team_matches(
    team: str = typer.Argument(..., help="Team name or id"),
    season: str = typer.Option(None, "--season", "-s", help="Season name (default: current)"),
    competition: str = typer.Option(
        None,
        "--competition",
        "-c",
        help="Competition name, 'qualifying', or 'all' (default). See: mt competitions",
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="How many to show"),
):
    """Matches for a team, with the status that decides whether they count."""
    client, _ = get_client()

    team_row = _api(resolve_team, client, team)
    season_row = _api(resolve_season, client, season)
    wanted = _api(resolve_match_types, client, competition)

    matches = _api(client.get_games_by_team, team_row["id"], season_id=(season_row or {}).get("id")) or []
    if not matches:
        console.print(f"[yellow]No matches for {team_row.get('name', team)}.[/yellow]")
        return

    scope = "All competitions"
    if wanted is not None:
        names = [t.get("name") or "?" for t in wanted]
        scope = "Qualifying (" + " + ".join(names) + ")" if len(names) > 1 else names[0]
        keep = {t.get("id") for t in wanted}
        matches = [m for m in matches if match_type_id_of(m) in keep]

    if not matches:
        console.print(f"[yellow]No {scope} matches for {team_row.get('name', team)}.[/yellow]")
        console.print("[dim]Other competitions may have matches — drop -c to see the whole schedule.[/dim]")
        return

    # The scope is in the title on purpose: a filtered list of 6 must not read
    # as a 6-match season.
    table = Table(title=f"Matches — {team_row.get('name', team)} · {scope}")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Date", style="magenta")
    table.add_column("Status", style="yellow")
    table.add_column("Competition", style="dim")
    table.add_column("Home", style="white")
    table.add_column("Away", style="white")
    table.add_column("Score", justify="right")

    for m in matches[:limit]:
        home_score, away_score = m.get("home_score"), m.get("away_score")
        score = f"{home_score}-{away_score}" if home_score is not None and away_score is not None else "-"
        table.add_row(
            str(m.get("id", "?")),
            str(m.get("match_date", "?")),
            str(m.get("match_status", "?")),
            str(m.get("match_type_name") or (m.get("match_type") or {}).get("name") or "?"),
            str(m.get("home_team_name", "?")),
            str(m.get("away_team_name", "?")),
            score,
        )

    console.print(table)
    shown = min(len(matches), limit)
    console.print(f"[dim]{shown} of {len(matches)} {scope} match(es).[/dim]")
    console.print("[dim]Only live, completed and forfeit matches count towards season stats (SB-671).[/dim]")


@app.command("competitions")
def competitions():
    """The competitions the API knows, and which of them qualify for the cup.

    `-c` on team stats and team matches accepts any of these, but nothing else
    told you what they were — which is how six Flex fixtures stayed invisible
    for a day.
    """
    client, _ = get_client()
    types = _api(client.get_match_types) or []

    if not types:
        console.print("[yellow]No competitions configured.[/yellow]")
        return

    table = Table(title="Competitions")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Qualifies", justify="center", style="green")

    for t in types:
        table.add_row(
            str(t.get("id", "?")),
            str(t.get("name", "?")),
            "yes" if t.get("counts_for_qualification") else "",
        )

    console.print(table)
    console.print(f"[dim]Also accepted by -c: '{QUALIFYING}' (every qualifying competition) and 'all'.[/dim]")


@match_app.command("show")
def match_show(match_id: int = typer.Argument(..., help="Match ID")):
    """One match: status, lineups and events."""
    client, _ = get_client()

    match = _api(client.get_game, match_id)

    status = match.get("match_status", "?")
    counts = status in ("live", "completed", "forfeit")
    console.print(
        Panel(
            f"[bold]{match.get('home_team_name', '?')}[/bold] vs [bold]{match.get('away_team_name', '?')}[/bold]\n"
            f"{match.get('match_date', '?')} · status [yellow]{status}[/yellow]\n"
            f"Counts towards season stats: {'[green]yes[/green]' if counts else '[red]no[/red]'}",
            title=f"Match {match_id}",
        )
    )

    for side in ("home", "away"):
        team_id = match.get(f"{side}_team_id")
        if not team_id:
            continue
        try:
            lineup = client.get_lineup(match_id, team_id)
        except APIError:
            lineup = None
        positions = (lineup or {}).get("positions") or []
        label = match.get(f"{side}_team_name", side)
        if not positions:
            console.print(f"[dim]{label}: no lineup saved[/dim]")
            continue
        table = Table(title=f"{label} lineup ({len(positions)})")
        table.add_column("Position", style="dim")
        table.add_column("Player", style="white")
        for pos in positions:
            table.add_row(str(pos.get("position", "?")), _player_label(pos))
        console.print(table)

    try:
        events = client.get_match_events(match_id) or []
    except APIError:
        events = []
    if events:
        table = Table(title="Events")
        table.add_column("Min", justify="right", style="dim")
        table.add_column("Type", style="yellow")
        table.add_column("Message", style="white")
        for e in reversed(events):
            table.add_row(str(e.get("match_minute") or "-"), str(e.get("event_type", "?")), str(e.get("message", "")))
        console.print(table)

    # Appearance rows are not exposed by the API, so this shows who was listed,
    # not who is counted. Saying so beats implying completeness.
    console.print("[dim]Per-player appearance records are not exposed by the API; lineup shown instead.[/dim]")


@player_app.command("stats")
def player_stats(
    player_id: int = typer.Argument(..., help="Roster player id"),
    season: str = typer.Option(None, "--season", "-s", help="Season name (default: current)"),
):
    """A player's season line."""
    client, _ = get_client()

    season_row = _api(resolve_season, client, season)

    stats = _api(client.get_roster_player_stats, player_id, season_id=(season_row or {}).get("id"))
    if not stats:
        console.print("[yellow]No stats for that player.[/yellow]")
        return

    table = Table(title=f"Player {player_id} · {(season_row or {}).get('name', '?')}")
    for label, _f in STAT_FIELDS:
        table.add_column(label, justify="right", style="cyan")
    table.add_row(*[str(stats.get(f) or 0) for _, f in STAT_FIELDS])
    console.print(table)


# ---------------------------------------------------------------------------
# Team and club admin writes (SB-824)
#
# `team` was read-only, so a season's identity changes — renames, new clubs —
# had to be clicked through Admin forms. Rollover is a scripted, repeatable,
# reviewable operation, and it happens against a deadline.
# ---------------------------------------------------------------------------


# U19 is id 7; there is no id 6. Resolved by name so nobody has to know that.
def _resolve_division_id(client, term: str) -> int:
    """Resolve a division name (e.g. 'Northeast') to its id."""
    if str(term).isdigit():
        return int(term)
    divisions = _api(client.get_divisions) or []
    needle = str(term).lower().strip()
    for d in divisions:
        if (d.get("name") or "").lower().strip() == needle:
            return d["id"]
    matches = [d for d in divisions if needle in (d.get("name") or "").lower()]
    if len(matches) == 1:
        return matches[0]["id"]
    available = ", ".join(sorted({d.get("name", "?") for d in divisions}))
    raise ResolutionError(f"Division {term!r} not found. Available: {available}")


def _resolve_club(client, term: str) -> dict:
    """One club, by id or name."""
    if str(term).isdigit():
        target = int(term)
        for c in _api(client.get_clubs) or []:
            if c.get("id") == target:
                return c
        raise ResolutionError(f"No club with id {target}")

    clubs = _api(client.get_clubs) or []
    needle = term.lower().strip()
    exact = [c for c in clubs if (c.get("name") or "").lower().strip() == needle]
    if len(exact) == 1:
        return exact[0]
    matches = [c for c in clubs if needle in (c.get("name") or "").lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(c.get("name", "?") for c in matches[:6])
        raise ResolutionError(f"{len(matches)} clubs match {term!r}: {names}")
    raise ResolutionError(f"No club matches {term!r}")


@team_app.command("rename")
def team_rename(
    team: str = typer.Argument(..., help="Team name or id"),
    name: str = typer.Option(..., "--name", "-n", help="New team name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Rename a team, preserving its club, city and academy flag.

    Renaming is safe for history: matches reference teams by id, not by name,
    so every past fixture follows the team.
    """
    client, _ = get_client()
    current = _api(resolve_team, client, team)
    old_name = current.get("name")

    if old_name == name:
        console.print(f"[yellow]{old_name!r} already has that name.[/yellow]")
        return

    console.print(f"[bold]{old_name}[/bold] -> [bold]{name}[/bold]  (team #{current['id']})")
    console.print(f"[dim]club_id {current.get('club_id')} and city {current.get('city')!r} preserved[/dim]")
    if not yes and not typer.confirm("Apply?"):
        raise typer.Exit(1)

    updated = _api(
        client.update_team_profile,
        current["id"],
        name=name,
        city=current.get("city") or "",
        academy_team=bool(current.get("academy_team")),
        club_id=current.get("club_id"),
    )
    console.print(f"[green]Renamed team #{current['id']}[/green] -> {updated.get('name', name)}")
    console.print(
        f"[dim]Record the old name so a stale feed cannot re-split it:[/dim] "
        f'mt team alias add {current["id"]} --alias "{old_name}" --kind former_name'
    )


@team_app.command("set-club")
def team_set_club(
    team: str = typer.Argument(..., help="Team name or id"),
    club: str = typer.Option(..., "--club", "-c", help="Club name or id"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Point a team at a different club. Crest and colours come from the club."""
    client, _ = get_client()
    current = _api(resolve_team, client, team)
    target = _api(_resolve_club, client, club)

    console.print(
        f"[bold]{current.get('name')}[/bold] club {current.get('club_id')} -> "
        f"{target['id']} ([bold]{target.get('name')}[/bold])"
    )
    if not yes and not typer.confirm("Apply?"):
        raise typer.Exit(1)

    _api(
        client.update_team_profile,
        current["id"],
        name=current.get("name"),
        city=current.get("city") or "",
        academy_team=bool(current.get("academy_team")),
        club_id=target["id"],
    )
    console.print(f"[green]{current.get('name')} now belongs to {target.get('name')}[/green]")


@team_app.command("create")
def team_create(
    name: str = typer.Option(..., "--name", "-n", help="Team name (globally unique)"),
    city: str = typer.Option("", "--city", help="City"),
    division: str = typer.Option(..., "--division", "-d", help="Division name or id"),
    age: list[str] = typer.Option(..., "--age", "-a", help="Age group, repeatable (e.g. -a U13 -a U14)"),
    club: str = typer.Option(None, "--club", "-c", help="Club name or id"),
    academy: bool = typer.Option(False, "--academy", help="Mark as an academy team"),
):
    """Create a team.

    One team row covers every age group it plays — teams.name is globally
    unique, so a row per age group is impossible. The age groups given here
    become team_mappings rows, and league_id is derived from the division.
    """
    client, _ = get_client()
    age_group_ids = [_resolve_age_group_id(client, a) for a in age]
    division_id = _api(_resolve_division_id, client, division)
    club_row = _api(_resolve_club, client, club) if club else None

    payload = Team(
        name=name,
        city=city,
        age_group_ids=age_group_ids,
        division_id=division_id,
        club_id=(club_row or {}).get("id"),
        academy_team=academy,
    )
    created = _api(client.create_team, payload)
    team_row = created.get("team", created)
    console.print(f"[green]Created team #{team_row.get('id')}:[/green] {name}")
    console.print(f"[dim]division {division_id}, age groups {age_group_ids}, club {(club_row or {}).get('id')}[/dim]")


@club_app.command("list")
def club_list(
    search: str = typer.Argument(None, help="Filter by name substring"),
):
    """List clubs."""
    client, _ = get_client()
    clubs = _api(client.get_clubs) or []
    if search:
        needle = search.lower()
        clubs = [c for c in clubs if needle in (c.get("name") or "").lower()]
    if not clubs:
        console.print("[yellow]No clubs.[/yellow]")
        return
    table = Table(title=f"Clubs ({len(clubs)})")
    table.add_column("id", justify="right")
    table.add_column("name")
    table.add_column("city")
    for c in sorted(clubs, key=lambda x: (x.get("name") or "").lower()):
        table.add_row(str(c.get("id")), c.get("name") or "", c.get("city") or "")
    console.print(table)


@club_app.command("create")
def club_create(
    name: str = typer.Option(..., "--name", "-n", help="Club name (unique)"),
    city: str = typer.Option(None, "--city", help="City"),
    pro_academy: bool = typer.Option(False, "--pro-academy", help="Mark as a professional club academy (MLS academy)"),
):
    """Create a club. Crest and colours are set afterwards in the Admin UI."""
    client, _ = get_client()
    created = _api(client.create_club, name=name, city=city, pro_academy=pro_academy)
    club_row = created.get("club", created)
    console.print(f"[green]Created club #{club_row.get('id')}:[/green] {name}")
    console.print(f'[dim]Attach a team:[/dim] mt team create --name "..." --club {club_row.get("id")}')


@club_app.command("rename")
def club_rename(
    club: str = typer.Argument(..., help="Club name or id"),
    name: str = typer.Option(..., "--name", "-n", help="New club name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Rename a club.

    Teams keep pointing at it by id, so their crest and colours are unaffected.
    """
    client, _ = get_client()
    current = _api(_resolve_club, client, club)
    if current.get("name") == name:
        console.print(f"[yellow]{name!r} already has that name.[/yellow]")
        return

    console.print(f"[bold]{current.get('name')}[/bold] -> [bold]{name}[/bold]  (club #{current['id']})")
    if not yes and not typer.confirm("Apply?"):
        raise typer.Exit(1)

    # Read-then-resend: PUT /api/clubs/{id} replaces the whole record, so
    # anything omitted is blanked — including logo_url and the brand colours
    # the IG cards read.
    full = _api(client.get_club, current["id"]) or current
    _api(
        client.update_club_profile,
        current["id"],
        name=name,
        city=full.get("city") or "",
        website=full.get("website"),
        description=full.get("description"),
        logo_url=full.get("logo_url"),
        primary_color=full.get("primary_color"),
        secondary_color=full.get("secondary_color"),
        pro_academy=bool(full.get("pro_academy")),
    )
    console.print(f"[green]Renamed club #{current['id']}[/green] -> {name}")
    console.print("[dim]crest, colours and pro-academy flag preserved[/dim]")


@alias_app.command("add")
def team_alias_add(
    team: str = typer.Argument(..., help="Team name or id"),
    alias: str = typer.Option(..., "--alias", "-a", help="String that should resolve to this team"),
    kind: str = typer.Option("feed_variant", "--kind", "-k", help="feed_variant | former_name"),
    source: str = typer.Option("mlssoccer.com", "--source", "-s", help="Which feed uses this spelling"),
):
    """Record a string that should resolve to this team.

    Makes a rename durable: once the old name is recorded, a stale feed
    carrying it resolves to the renamed team instead of creating a second one.
    """
    client, _ = get_client()
    if kind not in ("feed_variant", "former_name"):
        console.print("[red]--kind must be feed_variant or former_name[/red]")
        raise typer.Exit(1)

    current = _api(resolve_team, client, team)
    _api(client.add_team_alias, current["id"], external_name=alias, source=source, kind=kind)
    console.print(f"[green]{alias!r} now resolves to[/green] {current.get('name')} (#{current['id']})")


@alias_app.command("list")
def team_alias_list(team: str = typer.Argument(..., help="Team name or id")):
    """Every alternate string that resolves to a team."""
    client, _ = get_client()
    current = _api(resolve_team, client, team)
    aliases = (_api(client.get_team_aliases, current["id"]) or {}).get("aliases", [])
    if not aliases:
        console.print(f"[yellow]No aliases for {current.get('name')}.[/yellow]")
        return
    table = Table(title=f"Aliases for {current.get('name')}")
    table.add_column("alias")
    table.add_column("kind")
    table.add_column("source")
    for a in aliases:
        table.add_row(a.get("external_name") or "", a.get("kind") or "", a.get("source") or "")
    console.print(table)


if __name__ == "__main__":
    app()

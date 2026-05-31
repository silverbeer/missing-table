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
    TournamentCreate,
    TournamentMatchCreate,
    TournamentMatchUpdate,
)

app = typer.Typer(help="MT Match Tracking CLI")
match_app = typer.Typer(help="Live match tracking commands")
tournament_app = typer.Typer(help="Tournament + bracket seeding commands (admin)")
app.add_typer(match_app, name="match")
app.add_typer(tournament_app, name="tournament")
console = Console()

# Valid tournament_round values accepted by the backend (mirrors
# tournament_dao.VALID_ROUNDS). group_stage is the default for bracket pools.
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
        console.print(
            "[red]Not logged in[/red]\n"
            "[yellow]Login first:[/yellow] mt login <username>"
        )
        raise typer.Exit(1)

    client = MissingTableClient(
        base_url=get_base_url(),
        access_token=state.access_token,
    )
    return client, state


def require_active_match(state: CLIState) -> int:
    """Return the active match_id from state, or exit with an error."""
    if not state.match_id:
        console.print(
            "[red]No active match[/red]\n"
            "[yellow]Start a match first:[/yellow] mt match start <match_id>"
        )
        raise typer.Exit(1)
    return state.match_id


# --- Helpers ---


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
        console.print(
            "[red]Session expired[/red]\n"
            "[yellow]Login again:[/yellow] mt login <username>"
        )
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
        player_id, player_display = _resolve_player(
            client, team_id, live.get("season_id"), player
        )

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
    console.print(
        f"[red]Age group '{name}' not found[/red]\n[yellow]Available:[/yellow] {available}"
    )
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
            "[red]No current season set[/red]\n"
            "[yellow]Pass --season explicitly (e.g. --season 2025-2026)[/yellow]"
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
        hint = "\n[yellow]Did you mean:[/yellow] " + ", ".join(
            t.get("name", "?") for t in similar[:5]
        )
    console.print(f"[red]No exact team match for '{name}'[/red]{hint}")
    raise typer.Exit(1)


# --- Tournament Subcommands ---


@tournament_app.command("create")
def tournament_create(
    name: str = typer.Option(..., "--name", "-n", help="Tournament name"),
    start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(None, "--end", "-e", help="End date (YYYY-MM-DD)"),
    age: list[str] = typer.Option(
        None, "--age", "-a", help="Age group(s), e.g. -a U14 (repeatable)"
    ),
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
    bracket: str = typer.Option(
        None, "--bracket", "-b", help="Bracket / tournament_group, e.g. 'Bracket A'"
    ),
    round_: str = typer.Option(
        "group_stage", "--round", "-r", help=f"Round ({', '.join(sorted(VALID_ROUNDS))})"
    ),
    order: int = typer.Option(None, "--order", help="tournament_round_order (bracket position)"),
    kickoff: str = typer.Option(
        None, "--kickoff", "-k", help="Scheduled kickoff ISO ts, e.g. 2026-06-07T14:00:00Z"
    ),
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
        console.print(
            f"[red]Invalid round '{round_}'[/red]\n"
            f"[yellow]Valid:[/yellow] {', '.join(sorted(VALID_ROUNDS))}"
        )
        raise typer.Exit(1)

    client, _ = get_client()
    age_group_id = _resolve_age_group_id(client, age)
    season_id = _resolve_season_id(client, season)
    home_id, home_name = _resolve_team_id(client, home)

    payload = TournamentMatchCreate(
        our_team_id=home_id,
        opponent_name=away,
        match_date=date,
        age_group_id=age_group_id,
        season_id=season_id,
        is_home=True,
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
    console.print(
        f"[green]Added match #{mid}[/green]{bracket_label} {home_name} vs {away} "
        f"({age}, {round_})"
    )


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
    payload = TournamentMatchUpdate(
        home_score=home_score, away_score=away_score, match_status=status
    )
    try:
        client.update_tournament_match(tournament, match, payload)
    except APIError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None
    console.print(
        f"[green]Match #{match} → {home_score}-{away_score} ({status})[/green]  "
        "[dim]fulltime notification fired to bracket + team followers[/dim]"
    )


if __name__ == "__main__":
    app()

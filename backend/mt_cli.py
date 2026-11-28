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
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from getpass import getpass
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

import httpx
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

if TYPE_CHECKING:
    from collections.abc import Callable

app = typer.Typer(help="MT Match Tracking CLI")
match_app = typer.Typer(help="Live match tracking commands")
tournament_app = typer.Typer(help="Tournament + bracket seeding commands (admin)")
team_app = typer.Typer(help="Team stats, matches, and admin edits")
player_app = typer.Typer(help="Player stats (read-only)")
club_app = typer.Typer(help="Club admin: create, rename, crest and colours")
alias_app = typer.Typer(help="Team name aliases (admin)")
mapping_app = typer.Typer(help="Team age-group / division registrations (admin)")
ingest_app = typer.Typer(help="Ingest: unresolved names, and planned fixes for a tournament's teams (admin)")
app.add_typer(match_app, name="match")
app.add_typer(tournament_app, name="tournament")
app.add_typer(team_app, name="team")
app.add_typer(player_app, name="player")
app.add_typer(club_app, name="club")
team_app.add_typer(alias_app, name="alias")
team_app.add_typer(mapping_app, name="mapping")
guest_app = typer.Typer(help="Teams with no row in a table they play fixtures in (admin)")
team_app.add_typer(guest_app, name="guest")
app.add_typer(ingest_app, name="ingest")
ai_app = typer.Typer(help="MT AI: what it could not answer (admin)")
app.add_typer(ai_app, name="ai")
mcp_app = typer.Typer(help="mt-mcp: credentials for MCP clients such as Claude Code (SB-1304)")
app.add_typer(mcp_app, name="mcp")
motw_app = typer.Typer(help="Match of the Week: candidates and the current pick (admin)")
app.add_typer(motw_app, name="motw")
console = Console()


@app.callback()
def main(
    env: str = typer.Option(
        None,
        "--env",
        metavar="local|prod",
        help="Target this environment for one command. Does not change .mt-config.",
    ),
) -> None:
    """MT Match Tracking CLI."""
    global _ENV_OVERRIDE
    if env is None:
        return
    if env not in KNOWN_ENVS:
        console.print(f"[red]Unknown environment {env!r}[/red]  Known: {', '.join(KNOWN_ENVS)}")
        raise typer.Exit(1)
    _ENV_OVERRIDE = env


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
    "showcase",
    "consolation",
    "placement_final",
}

# Paths
REPO_ROOT = Path(__file__).parent.parent
BACKEND_DIR = Path(__file__).parent
MT_CONFIG_FILE = REPO_ROOT / ".mt-config"
STATE_FILE = BACKEND_DIR / ".mt-cli-state.json"

# Environments `mt` knows how to target. Each needs a backend/.env.<name>.
KNOWN_ENVS = ("local", "prod")

# Set by the --env option for the lifetime of one invocation. Nothing is
# written to disk: targeting prod is an act, not a mode you can forget you are
# in (SB-841).
_ENV_OVERRIDE: str | None = None


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


def resolve_env() -> tuple[str, str]:
    """The environment this invocation targets, and where that came from.

    Precedence: --env, then APP_ENV, then .mt-config, then local.

    APP_ENV used to lose to .mt-config, which is the surprising half:
    `APP_ENV=prod mt ...` looks like it should work and silently did nothing.
    A value someone typed for this command beats a mode left on disk.
    """
    if _ENV_OVERRIDE is not None:
        return _ENV_OVERRIDE, "--env"
    from_environ = os.getenv("APP_ENV")
    if from_environ:
        return from_environ, "APP_ENV"
    config_val = mt_config_get("supabase_env")
    if config_val:
        return config_val, MT_CONFIG_FILE.name
    return "local", "default"


def get_current_env() -> str:
    """Get current environment (local or prod)."""
    return resolve_env()[0]


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


def _read_raw_state() -> dict:
    """The state file as stored, or {} when there is none."""
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE) as f:
        return json.load(f) or {}


def _write_raw_state(environments: dict, users: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump({"environments": environments, "users": users}, f, indent=2)


def _read_state_file() -> dict:
    """The whole state file, as {env: session}.

    Sessions are per environment. They were not, and with --env making the
    target easy to change that would be actively dangerous: a token minted
    against prod would be sent to localhost, and an active prod match id would
    be the id of some unrelated local fixture.

    A pre-SB-841 file is a bare session at the top level. It is migrated under
    whichever environment is current when it is first read — the only
    information available about where that token came from.
    """
    data = _read_raw_state()
    if isinstance(data, dict) and "environments" in data:
        return data["environments"] or {}
    if data:
        return {get_current_env(): data}
    return {}


def load_state() -> CLIState:
    """The session for the environment this command targets."""
    return CLIState(**_read_state_file().get(get_current_env(), {}))


def save_state(state: CLIState) -> None:
    """Write the session back, leaving other environments' sessions alone."""
    environments = _read_state_file()
    environments[get_current_env()] = state.model_dump()
    _write_raw_state(environments, _read_users())


def _read_users() -> dict:
    """Every stored login, as {env: {username: session}} (SB-1331)."""
    data = _read_raw_state()
    users = data.get("users") if isinstance(data, dict) else None
    return users or {}


def load_user_state(username: str) -> CLIState:
    """The session `mt login <username>` left for the targeted environment.

    The environment's current session, rather than per-user storage, is what
    every other command uses. A login made before per-user storage existed is
    only there, so it still counts when it belongs to this user.
    """
    env = get_current_env()
    stored = _read_users().get(env, {}).get(username)
    if stored:
        return CLIState(**stored)
    current = load_state()
    if current.username == username and current.access_token:
        return CLIState(access_token=current.access_token, refresh_token=current.refresh_token, username=username)
    return CLIState(username=username)


def save_user_state(state: CLIState) -> None:
    """Keep this user's tokens for the targeted environment, beside everyone else's.

    Only the tokens: an active match belongs to the environment's session.
    """
    if not state.username:
        return
    users = _read_users()
    users.setdefault(get_current_env(), {})[state.username] = {
        "access_token": state.access_token,
        "refresh_token": state.refresh_token,
        "username": state.username,
    }
    _write_raw_state(_read_state_file(), users)


def announce_target() -> None:
    """Say so, out loud, whenever a command is aimed somewhere other than local.

    The ticket asked for this on writes. Every command gets it instead: a read
    that quietly answers about production is its own kind of wrong, and one
    rule cannot be applied to the wrong half of the command list.
    """
    env, source = resolve_env()
    if env != "local":
        console.print(f"[yellow]→ {env}[/yellow] [dim](from {source})[/dim]")


def get_client() -> tuple[MissingTableClient, CLIState]:
    """Get an authenticated MissingTableClient and current state."""
    announce_target()
    state = load_state()
    if not state.access_token:
        console.print(
            f"[red]Not logged in to {get_current_env()}[/red]\n[yellow]Login first:[/yellow] mt login <username>"
        )
        raise typer.Exit(1)

    if state.refresh_token and _near_expiry(state.access_token):
        try:
            fresh_access_token(state, get_base_url(), persist=_persist_session)
        except (AuthenticationError, APIError):
            _session_expired()

    client = MissingTableClient(
        base_url=get_base_url(),
        access_token=state.access_token,
    )
    # A token revoked or expired early still gets one refresh-and-retry (SB-1410).
    client._refresh_token = state.refresh_token
    client.on_token_refresh = lambda tokens: _persist_session(_with_tokens(state, tokens))
    return client, state


def _near_expiry(access_token: str) -> bool:
    """A readable token within the refresh margin of expiry. An unreadable one
    goes to the server as-is: a 401 there still triggers the refresh."""
    import time

    expires = token_expires_at(access_token)
    return expires is not None and expires - time.time() <= MCP_REFRESH_MARGIN_S


def _with_tokens(state: CLIState, tokens: dict) -> CLIState:
    state.access_token = tokens["access_token"]
    state.refresh_token = tokens.get("refresh_token") or state.refresh_token
    return state


def _persist_session(state: CLIState) -> None:
    """Save refreshed tokens to the environment's session and the user's copy.

    Refresh tokens rotate, so a copy left holding the old one could never
    refresh again.
    """
    save_state(state)
    save_user_state(state)


def _session_expired() -> NoReturn:
    env = get_current_env()
    console.print(f"[red]Session expired for {env}[/red]\n[yellow]Log in again:[/yellow] mt --env {env} login")
    raise typer.Exit(1)


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
    return f"op://agents/mt-{get_current_env()}/credential"


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
    # Before a password is read, not after: which environment is about to be
    # handed a credential is the thing worth knowing early.
    announce_target()

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
    save_user_state(state)

    user = result.get("user", {})
    role = user.get("role", "unknown")
    console.print(f"[green]Logged in as {username} ({role})[/green]")
    console.print(f"[dim]Environment: {get_current_env()}[/dim]")


# --- mt-mcp (SB-1304) ---

# Refresh a session token this close to expiry, so a long Claude Code session
# never hands mt-mcp - or any mt command (SB-1410) - a token that dies mid-call.
MCP_REFRESH_MARGIN_S = 300
MCP_CLIENT = "claude-code"


def token_expires_at(token: str) -> int | None:
    """The `exp` claim of a JWT, read without verifying it — the server verifies."""
    import jwt

    try:
        exp = jwt.decode(token, options={"verify_signature": False}).get("exp")
    except jwt.PyJWTError:
        return None
    return int(exp) if exp is not None else None


def fresh_access_token(
    state: CLIState,
    base_url: str,
    now: float | None = None,
    persist: Callable[[CLIState], None] | None = None,
) -> str:
    """The stored session token, refreshed first if it is near expiry or unreadable.

    A refreshed token is written back with `persist` (default: the environment's session).
    """
    import time

    if not state.access_token:
        raise AuthenticationError(f"Not logged in to {get_current_env()}")
    expires = token_expires_at(state.access_token)
    if expires is not None and expires - (now or time.time()) > MCP_REFRESH_MARGIN_S:
        return state.access_token

    client = MissingTableClient(base_url=base_url, access_token=state.access_token)
    client._refresh_token = state.refresh_token
    try:
        refreshed = client.refresh_access_token()
    finally:
        client.close()
    state.access_token = refreshed["access_token"]
    state.refresh_token = refreshed.get("refresh_token") or state.refresh_token
    (persist or save_state)(state)
    return state.access_token


@mcp_app.command("headers")
def mcp_headers(
    user: str | None = typer.Option(
        None,
        "--user",
        "-u",
        help="Speak as this user's `mt login` session instead of the environment's current one (SB-1331).",
    ),
):
    """Print mt-mcp auth headers as JSON, for Claude Code's headersHelper.

    Stdout is the JSON object and nothing else; every message goes to stderr.
    Uses the `mt login` session for the targeted environment — or, with --user,
    that user's — refreshing it when it is within five minutes of expiry.
    """
    err = Console(stderr=True)
    if user:
        state, persist = load_user_state(user), save_user_state
    else:
        state, persist = load_state(), save_state
    try:
        token = fresh_access_token(state, get_base_url(), persist=persist)
    except (AuthenticationError, APIError) as e:
        who = f"mt login {user}" if user else "mt login"
        err.print(f"[red]mt-mcp: {e}[/red] — run [cyan]{who}[/cyan] for {get_current_env()}")
        raise typer.Exit(1) from None
    sys.stdout.write(json.dumps({"Authorization": f"Bearer {token}", "X-MT-Client": MCP_CLIENT}))


@app.command()
def logout():
    """Logout and clear stored credentials for the targeted environment."""
    env = get_current_env()
    state = load_state()
    state.access_token = None
    state.refresh_token = None
    state.username = None
    save_state(state)
    console.print(f"[green]Logged out of {env}[/green]")


@app.command()
def config():
    """Show current configuration, including where the environment came from."""
    env, source = resolve_env()
    base_url = get_base_url()
    state = load_state()

    table = Table(title="MT CLI Configuration", show_header=False)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Environment", f"{env}  [dim](from {source})[/dim]")
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


def _resolve_age_group(client: MissingTableClient, name: str) -> dict:
    """Resolve an age-group name (e.g. 'U14') to its row ({id, name}). Exits on no match."""
    groups = client.get_age_groups()
    lower = name.lower()
    # Exact (case-insensitive) first, then substring.
    for g in groups:
        if g.get("name", "").lower() == lower:
            return g
    for g in groups:
        if lower in g.get("name", "").lower():
            return g
    available = ", ".join(sorted(g.get("name", "?") for g in groups))
    console.print(f"[red]Age group '{name}' not found[/red]\n[yellow]Available:[/yellow] {available}")
    raise typer.Exit(1)


def _resolve_age_group_id(client: MissingTableClient, name: str) -> int:
    """Resolve an age-group name (e.g. 'U14') to its id. Exits on no match."""
    return _resolve_age_group(client, name)["id"]


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


motd_app = typer.Typer(help="Tournament Match of the Day: one featured match per tournament, day and age group (admin)")
tournament_app.add_typer(motd_app, name="motd")


def _motd_teams(match: dict[str, Any]) -> str:
    home = match.get("home_team_name") or (match.get("home_team") or {}).get("name") or "?"
    away = match.get("away_team_name") or (match.get("away_team") or {}).get("name") or "?"
    return f"{home} vs {away}"


def _print_motd(pick: dict[str, Any]) -> None:
    match = pick.get("match") or {}
    age = pick.get("age_group") or match.get("age_group_name")
    age_label = f"{age}  " if age else ""
    console.print(f"[bold]{pick.get('match_date')}[/bold]  {age_label}#{match.get('id', '?')}  {_motd_teams(match)}")
    if pick.get("blurb"):
        console.print(f"  {pick['blurb']}")
    reasons = pick.get("reasons")
    if reasons:
        for r in reasons:
            console.print(f"  • {r.get('text')}")
    elif reasons == []:
        console.print("  [dim](reasons left empty)[/dim]")


@motd_app.command("show")
def tournament_motd_show(
    tournament: int = typer.Option(..., "--tournament", "-T", help="Tournament ID"),
    date: str = typer.Option(None, "--date", "-d", help="Day (YYYY-MM-DD); omit to list every pick"),
    age: str = typer.Option(None, "--age", "-a", help="Age group (e.g. U15); omit for every age group"),
):
    """Show a day's Match of the Day picks, or every pick in the tournament."""
    client, _ = get_client()
    try:
        age_group_id = _resolve_age_group_id(client, age) if age else None
        result = client.get_tournament_motd(tournament, date, age_group_id)
    except APIError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None
    slot = f" ({age})" if age else ""
    if date:
        # With an age group the answer is that slot's pick; without, every age group's.
        one = [result["motd"]] if result.get("motd") else []
        picks = one if age else result.get("picks") or one
        if not picks:
            console.print(f"[yellow]No Match of the Day picked for {result.get('match_date')}{slot}.[/yellow]")
        for pick in picks:
            _print_motd(pick)
        return
    picks = result.get("picks") or []
    if not picks:
        console.print(f"[yellow]No Match of the Day picked yet for tournament #{tournament}{slot}.[/yellow]")
    for pick in picks:
        _print_motd(pick)


@motd_app.command("set")
def tournament_motd_set(
    tournament: int = typer.Option(..., "--tournament", "-T", help="Tournament ID"),
    match: int = typer.Option(..., "--match", "-m", help="Match ID to feature (must be in the tournament)"),
    date: str = typer.Option(None, "--date", "-d", help="Guard: refuse unless the match is on this day"),
    age: str = typer.Option(None, "--age", "-a", help="Guard: refuse unless the match is in this age group"),
    blurb: str = typer.Option(None, "--blurb", "-b", help="One-line headline"),
    reason: list[str] = typer.Option(None, "--reason", "-r", help="'Why this match' line; repeat for more (max 6)"),
):
    """Feature a match as its day's Match of the Day for its age group, replacing that slot's pick."""
    client, _ = get_client()
    reasons = [{"text": r} for r in reason] if reason else None
    try:
        age_group_id = _resolve_age_group_id(client, age) if age else None
        pick = client.set_tournament_motd(
            tournament, match, match_date=date, age_group_id=age_group_id, blurb=blurb, reasons=reasons
        )
    except APIError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None
    console.print("[green]Match of the Day set[/green]")
    _print_motd(pick)


@motd_app.command("clear")
def tournament_motd_clear(
    tournament: int = typer.Option(..., "--tournament", "-T", help="Tournament ID"),
    date: str = typer.Option(..., "--date", "-d", help="Day to unpick (YYYY-MM-DD)"),
    age: str = typer.Option(None, "--age", "-a", help="Age group to unpick (e.g. U15); omit to unpick every one"),
):
    """Unpick a tournament day: one age group's pick, or every pick that day."""
    client, _ = get_client()
    try:
        age_group_id = _resolve_age_group_id(client, age) if age else None
        result = client.clear_tournament_motd(tournament, date, age_group_id)
    except APIError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None
    slot = f" ({age})" if age else ""
    cleared = int(result.get("cleared") or 0)
    if cleared:
        noun = "pick" if cleared == 1 else "picks"
        console.print(f"[green]Cleared {cleared} Match of the Day {noun} for {result.get('match_date')}{slot}[/green]")
    else:
        console.print(f"[yellow]Nothing was picked for {result.get('match_date')}{slot}.[/yellow]")


def _motw_team(team: dict[str, Any]) -> str:
    pos = team.get("position")
    where = f"{pos}/{team.get('table_size')}" if pos else "no games"
    return f"{team.get('name')} ({where})"


@motw_app.command("suggest")
def motw_suggest(
    week: str = typer.Option(None, "--week", "-w", help="Any date (YYYY-MM-DD) in the week; default this week"),
    limit: int = typer.Option(5, "--limit", "-n", min=1, max=10, help="How many candidates"),
    facts: bool = typer.Option(False, "--facts", "-f", help="Show every fact id and text"),
    as_json: bool = typer.Option(False, "--json", help="Print the raw result"),
):
    """Rank this week's Match of the Week candidates (SB-1551)."""
    client, _ = get_client()
    try:
        result = client.get_motw_candidates(week, limit=limit)
    except APIError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None
    if as_json:
        console.print_json(data=result)
        return
    console.print(f"[bold]Week {result['week_start']} - {result['week_end']}[/bold]")
    pick = result.get("current_pick")
    if pick:
        console.print(f"[yellow]Already picked: match #{pick['match_id']}. Candidates are for reference.[/yellow]")
    cov = result.get("coverage") or {}
    console.print(
        f"[dim]{cov.get('eligible', 0)} eligible of {cov.get('fixtures_in_week', 0)} pool fixtures; "
        f"{cov.get('teams_low_sample', 0)} teams with under 3 games; rules {cov.get('rules_season') or 'none'}[/dim]"
    )
    candidates = result.get("candidates") or []
    if not candidates:
        console.print(f"[yellow]{result.get('reason') or 'No candidates.'}[/yellow]")
        return
    for rank, c in enumerate(candidates, start=1):
        s = c["score"]
        console.print(
            f"\n[bold]#{rank}[/bold] {s['total']:.3f}  match #{c['match_id']}  {c['match_date']}  "
            f"{c['age_group']['name']} {c['division']['name']} ({c['competition']})"
        )
        console.print(f"   {_motw_team(c['home'])} vs {_motw_team(c['away'])}")
        console.print(
            f"   [dim]quality {s['quality']}  closeness {s['closeness']}  stakes {s['stakes']}  "
            f"form {s['form']}  x{s['penalty']}  {' '.join(c.get('flags') or [])}[/dim]"
        )
        if facts:
            for fact in c.get("facts") or []:
                console.print(f"   [cyan]{fact['id']}[/cyan] {fact['text']}")


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
    — this returns one type; /api/teams/{id}/stats can total several (SB-1599).
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
    age_group: str = typer.Option(
        None,
        "--age-group",
        "-a",
        help="Age group, e.g. U14 — a team name is not unique to one (e.g. IFA plays U14 and U15)",
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="How many to show"),
):
    """Matches for a team, with the status that decides whether they count."""
    client, _ = get_client()

    team_row = _api(resolve_team, client, team)
    season_row = _api(resolve_season, client, season)
    wanted = _api(resolve_match_types, client, competition)
    age_group_row = _api(_resolve_age_group, client, age_group) if age_group else None

    matches = (
        _api(
            client.get_games_by_team,
            team_row["id"],
            season_id=(season_row or {}).get("id"),
            age_group_id=(age_group_row or {}).get("id"),
        )
        or []
    )
    if not matches:
        console.print(f"[yellow]No matches for {team_row.get('name', team)}.[/yellow]")
        return

    scope = "All competitions"
    if wanted is not None:
        names = [t.get("name") or "?" for t in wanted]
        scope = "Qualifying (" + " + ".join(names) + ")" if len(names) > 1 else names[0]
        keep = {t.get("id") for t in wanted}
        matches = [m for m in matches if match_type_id_of(m) in keep]

    # Named ahead of the competition so a same-day pair across two age groups
    # (a team row spans every age group it plays) reads as what it is, not as
    # a double-ingest — e.g. "26 of 26 U14 League match(es)".
    if age_group_row:
        scope = f"{age_group_row.get('name', age_group)} {scope}"

    if not matches:
        console.print(f"[yellow]No {scope} matches for {team_row.get('name', team)}.[/yellow]")
        console.print("[dim]Other competitions may have matches — drop -c to see the whole schedule.[/dim]")
        return

    # The scope is in the title on purpose: a filtered list of 6 must not read
    # as a 6-match season.
    table = Table(title=f"Matches — {team_row.get('name', team)} · {scope}")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Date", style="magenta", no_wrap=True, min_width=10)
    table.add_column("Status", style="yellow")
    # Always shown, even unfiltered: a team row covers every age group it
    # plays, so a same-day pair across two of them looks like a duplicate
    # without this column (SB-866).
    table.add_column("Age", style="dim", no_wrap=True)
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
            str(m.get("age_group_name") or (m.get("age_group") or {}).get("name") or "?"),
            str(m.get("match_type_name") or (m.get("match_type") or {}).get("name") or "?"),
            str(m.get("home_team_name", "?")),
            str(m.get("away_team_name", "?")),
            score,
        )

    console.print(table)
    shown = min(len(matches), limit)
    console.print(f"[dim]{shown} of {len(matches)} {scope} match(es).[/dim]")
    console.print("[dim]Only live, completed and forfeit matches count towards season stats (SB-671).[/dim]")


def _dash(value, fmt: str = "{}") -> str:
    """An absent value renders as absent, never as 0 (CLAUDE.md rule 2)."""
    return "—" if value is None else fmt.format(value)


@team_app.command("dossier")
def team_dossier(
    team: str = typer.Argument(..., help="Team name or id"),
    age: str = typer.Option(None, "--age", "-a", help="Age group, e.g. U15 (or give --match)"),
    match_id: int = typer.Option(None, "--match", "-m", help="Use the team's age in this match; shows playing up"),
    as_json: bool = typer.Option(False, "--json", help="Print the raw result"),
):
    """A team inside its own conference tables, at one age group (SB-1780).

    Positions and percentiles are within each table: conferences are never compared.
    """
    if age is None and match_id is None:
        _fail("Give --age (e.g. U15) or --match")
    client, _ = get_client()
    team_row = _api(resolve_team, client, team)
    age_row = _resolve_age_group(client, age) if age else None
    result = _api(
        client.get_team_dossier,
        team_row["id"],
        age_group_id=(age_row or {}).get("id"),
        for_match_id=match_id,
    )
    if as_json:
        console.print_json(data=result)
        return

    t = result.get("team") or {}
    age_name = (result.get("age_group") or {}).get("name", "?")
    season_name = (result.get("season") or {}).get("name", "?")
    console.print(f"[bold]{t.get('name', team)} · {age_name} · {season_name}[/bold]")
    ctx = result.get("context")
    if ctx and ctx.get("playing_up"):
        how = "inferred from registrations" if ctx.get("playing_up_inferred") else "recorded on the match"
        console.print(
            f"[yellow]Playing up in match {ctx['match_id']}: {ctx['season_age_group']['name']} side in a "
            f"{ctx['bracket_age_group']['name']} match ({how}).[/yellow]"
        )
    console.print(f"[dim]{(result.get('coverage') or {}).get('note', '')}[/dim]")
    if result.get("flags"):
        console.print(f"[yellow]Flags: {', '.join(result['flags'])}[/yellow]")

    confs = result.get("conferences") or []
    if not confs:
        console.print(f"[yellow]No {age_name} registration: no conference table to place the team in.[/yellow]")
    else:
        table = Table(title="Conferences (each its own table)")
        table.add_column("Kind", style="dim")
        table.add_column("Conference", style="cyan")
        table.add_column("Pos", justify="right")
        table.add_column("GP", justify="right")
        table.add_column("W-D-L", justify="right")
        table.add_column("GF-GA", justify="right")
        table.add_column("PPG", justify="right")
        table.add_column("CS", justify="right")
        table.add_column("Pctl", justify="right")
        for c in confs:
            division = c.get("division") or {}
            pos = "—" if c.get("position") is None else f"{c['position']}/{c.get('table_size')}"
            record = "—" if c.get("wins") is None else f"{c['wins']}-{c['draws']}-{c['losses']}"
            goals = "—" if c.get("gf") is None else f"{c['gf']}-{c['ga']}"
            label = f"{c.get('league') or ''} {division.get('name', '?')}".strip()
            if c.get("low_sample") and not c.get("no_results"):
                label += " (small sample)"
            table.add_row(
                c.get("kind", "?"),
                label,
                pos,
                str(c.get("played", 0)),
                record,
                goals,
                _dash(c.get("ppg"), "{:.2f}"),
                _dash(c.get("clean_sheets")),
                _dash(c.get("strength_percentile")),
            )
        console.print(table)

    wins = result.get("key_wins") or []
    if wins:
        table = Table(title="Key wins (strongest opponent first)")
        table.add_column("Date", style="magenta", no_wrap=True)
        table.add_column("Opponent", style="white")
        table.add_column("Score", justify="right")
        table.add_column("Why", style="cyan")
        table.add_column("Opponent's table", style="dim")
        for w in wins:
            where = (
                "—"
                if w.get("opponent_position") is None
                else f"{w['opponent_position']}/{w.get('opponent_table_size')} {w.get('opponent_conference')}"
            )
            table.add_row(
                str(w.get("date", "?")), w["opponent"]["name"], w.get("score", "?"), w.get("kind", "?"), where
            )
        console.print(table)

    form = result.get("form") or []
    if form:
        recent = ", ".join(f"{f['result']} {f['score']} v {f['opponent']['name']}" for f in form)
        console.print(f"Form (newest first): {recent}")
    streak_id = result.get("streak_fact_id")
    streak = next((f for f in result.get("facts") or [] if f.get("id") == streak_id), None)
    if streak:
        console.print(f"[dim]{streak['text']}[/dim]")


@app.command("coverage")
def coverage(
    season_id: int = typer.Option(None, "--season", help="Season id (default: current)"),
    all_rows: bool = typer.Option(False, "--all", help="Every row, not just the gaps"),
):
    """Are we tracking everything? Expected conferences vs fixtures that arrived.

    Every other view of competitions is built from fixtures that showed up, so
    none of them can report a conference that sent nothing. This one can.
    """
    client, _ = get_client()
    payload = _api(client.get_competition_coverage, season_id=season_id)

    if not payload.get("available", True):
        console.print("[red]Coverage could not be read.[/red]")
        raise typer.Exit(1)

    summary = payload.get("summary") or {}
    rows = payload.get("rows") or []

    table = Table(title="Competition coverage")
    table.add_column("League", style="cyan")
    table.add_column("Conference", style="white")
    table.add_column("Age", style="dim", no_wrap=True)
    table.add_column("Fixtures", justify="right")
    table.add_column("Teams", justify="right", style="dim")
    table.add_column("Status")

    # Undeclared rows are real fixtures in a league nobody wrote expectations
    # for. They are context, not a finding, so they stay out of the default
    # view — the gaps are what this command is for.
    interesting = {"empty", "unexpected"}
    shown = rows if all_rows else [r for r in rows if r.get("status") in interesting]
    for row in shown:
        status = row.get("status")
        colour = {
            "empty": "red",
            "unexpected": "yellow",
            "undeclared": "dim",
        }.get(status, "green")
        table.add_row(
            str(row.get("league_name") or "?"),
            str(row.get("division_name") or "?"),
            str(row.get("age_group_name") or "?"),
            str(row.get("fixtures", 0)),
            str(row.get("teams_registered", 0)),
            f"[{colour}]{status}[/{colour}]",
        )

    if shown:
        console.print(table)
    else:
        console.print("[green]Every expected conference has fixtures.[/green]")

    # The denominator ships with the figure — a coverage percentage without
    # one is the aggregate CLAUDE.md rule 3 forbids.
    console.print(
        f"[dim]{summary.get('covered', 0)} of {summary.get('expected', 0)} expected "
        f"brackets covered · {summary.get('empty', 0)} empty · "
        f"{summary.get('unexpected', 0)} unexpected[/dim]"
    )

    # A league nobody wrote expectations for is not the same as a league with
    # full coverage, and the report must not let the two look alike.
    undeclared = [lg for lg in (payload.get("leagues") or []) if not lg.get("declared")]
    for lg in undeclared:
        console.print(
            f"[yellow]{lg['league']}[/yellow][dim]: no expected coverage on file — "
            f"{lg.get('divisions', 0)} division(s) present, so this report cannot say "
            "whether anything is missing.[/dim]"
        )


LEADER_BOARDS = ("pts", "ppg", "gf", "gf_pg", "ga", "ga_pg", "gd", "gd_pg", "unbeaten", "pro_wins")


def _leader_cells(row: dict[str, Any]) -> list[str]:
    team = row.get("team") or {}
    conference = row.get("conference") or "[yellow]no conference[/yellow]"
    value = "" if row.get("value") is None else str(row["value"])
    if row.get("pro_games") is not None:
        value += f" of {row['pro_games']}"
    return [
        "" if row.get("rank") is None else str(row["rank"]),
        str(team.get("name") or "?"),
        conference,
        str(row.get("gp", 0)),
        f"{row.get('w', 0)}-{row.get('d', 0)}-{row.get('l', 0)}",
        value,
    ]


@app.command("leaders")
def leaders(
    age_group: str = typer.Argument(..., help="Age group, e.g. U15"),
    league: str = typer.Option("Homegrown", "--league", "-l", help="League (its Flex is included)"),
    season: str = typer.Option(None, "--season", "-s", help="Season name (default: current)"),
    limit: int = typer.Option(20, "--limit", "-n", min=1, max=50, help="Top N per board"),
    board: str = typer.Option(None, "--board", "-b", help=f"One board: {', '.join(LEADER_BOARDS)}"),
    as_json: bool = typer.Option(False, "--json", help="Print the raw result"),
):
    """Cross-conference stat boards for a league and age group (SB-1781).

    A stat board, not a ranking: conferences only meet at tournaments.
    """
    if board is not None and board not in LEADER_BOARDS:
        _fail(f"--board must be one of {', '.join(LEADER_BOARDS)}")
    client, _ = get_client()
    result = _api(client.get_leaderboards, age_group, league=league, season=season, limit=limit)
    if as_json:
        console.print_json(data=result)
        return

    # The denominator and the caveat come first (CLAUDE.md rule 3).
    cov = result.get("coverage") or {}
    season_name = (result.get("season") or {}).get("name", "?")
    console.print(f"[bold]{result.get('league')} {age_group.upper()} · {season_name}[/bold]")
    console.print(f"[dim]{cov.get('matches', 0)} matches · {cov.get('note', '')}[/dim]")
    if result.get("reason"):
        console.print(f"[yellow]{result['reason']}[/yellow]")
        return

    for b in result.get("boards") or []:
        if board is not None and b.get("key") != board:
            continue
        table = Table(title=f"{b.get('title')} · {b.get('key')}")
        table.add_column("#", style="dim", no_wrap=True)
        table.add_column("Team", style="white")
        table.add_column("Conference", style="cyan")
        table.add_column("MP", justify="right")
        table.add_column("W-D-L", justify="right", style="dim")
        table.add_column("Value", justify="right", style="bold")
        for row in b.get("rows") or []:
            table.add_row(*_leader_cells(row))
        unranked = f" · {b['unranked_count']} unranked" if b.get("unranked_count") else ""
        if not b.get("rows"):
            console.print(f"[dim]{b.get('title')}: nobody ranked yet{unranked}.[/dim]")
            continue
        table.caption = unranked.lstrip(" ·") or None
        console.print(table)

    # Listed once, not per board: early in a season that is most teams.
    unranked_rows = result.get("unranked") or []
    if unranked_rows:
        console.print(
            f"\n[dim]Unranked: under {cov.get('min_gp', '?')} matches "
            f"({len(unranked_rows)} of {result.get('unranked_count', len(unranked_rows))}, most matches first)[/dim]"
        )
        table = Table(style="dim")
        table.add_column("Team")
        table.add_column("Conference")
        table.add_column("MP", justify="right")
        table.add_column("W-D-L", justify="right")
        for row in unranked_rows:
            _, name, conference, gp, record, _ = _leader_cells(row)
            table.add_row(name, conference, gp, record, style="dim")
        console.print(table)


RANKING_VIEWS = ("national", "conference")


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _movement(row: dict[str, Any]) -> str:
    """Places and points since the run a week earlier. Absent is "—", never "0" (CLAUDE.md rule 2)."""
    places, points = row.get("rank_change_7d"), row.get("rating_change_7d")
    if places is None and points is None:
        return "—"
    moved = "—" if places is None else f"▲{places}" if places > 0 else f"▼{-places}" if places < 0 else "="
    return f"{moved} · {_dash(points, '{:+d}')}"


def _ranking_cells(row: dict[str, Any]) -> list[str]:
    conference = row.get("conference") or "[yellow]no conference[/yellow]"
    if row.get("conference") and row.get("conference_rank"):
        conference += f" · {_ordinal(row['conference_rank'])}"
    badges = [b.replace("_", " ") for b in row.get("badges") or []]
    if row.get("pro_academy"):
        badges.append("pro academy")
    return [
        "" if row.get("rank") is None else str(row["rank"]),
        str(row.get("team") or "?"),
        conference,
        f"{row.get('rating', 0):,}",
        _movement(row),
        f"{row.get('w', 0)}-{row.get('d', 0)}-{row.get('l', 0)}",
        str(row.get("mp", 0)),
        ", ".join(badges),
    ]


def _ranking_table(title: str, rows: list[dict[str, Any]]) -> Table:
    table = Table(title=title)
    table.add_column("#", style="dim", no_wrap=True)
    table.add_column("Team", style="white")
    table.add_column("Conference", style="cyan")
    table.add_column("Rating", justify="right", style="bold")
    table.add_column("Move", justify="right")
    table.add_column("W-D-L", justify="right", style="dim")
    table.add_column("MP", justify="right")
    table.add_column("Badges", style="dim")
    for row in rows:
        table.add_row(*_ranking_cells(row))
    return table


def _print_rankings(result: dict[str, Any], age_group: str) -> None:
    run = result.get("run") or {}
    console.print(
        f"[bold]MT Power Rating · {result.get('league')} {result.get('age_group') or age_group.upper()} · "
        f"{result.get('season') or '?'}[/bold]"
    )
    # The denominator comes first (CLAUDE.md rule 3).
    cov = result.get("coverage") or {}
    if cov.get("note"):
        console.print(f"[dim]{cov['note']}[/dim]")
    if run:
        since = result.get("movement_since")
        moved = f" · movement since run {since['run_id']}" if since else " · no run a week earlier: no movement"
        console.print(
            f"[dim]Run {run.get('id')} · computed {str(run.get('computed_at', '?'))[:10]} · "
            f"through {run.get('through_date') or '—'}{moved}[/dim]"
        )
    publication = result.get("publication") or {}
    if result.get("reason"):
        console.print(f"[yellow]{result['reason']}[/yellow]")
        return
    if not publication.get("national"):
        console.print(f"[yellow]No national list: {publication.get('reason') or 'not yet comparable'}[/yellow]")

    teams = result.get("teams") or []
    if result.get("view") == "national":
        tiers = result.get("tiers") or []
        for tier in tiers:
            rows = [t for t in teams if t.get("rank") is not None and t.get("tier") == tier["key"]]
            if rows:
                console.print(_ranking_table(f"{tier['label']} · {tier['min']:,}+", rows))
        lowest = min((t["min"] for t in tiers), default=None)
        rest = [t for t in teams if t.get("rank") is not None and t.get("tier") is None]
        if rest:
            console.print(_ranking_table(f"Below {lowest:,}" if lowest is not None else "Ranked", rest))
        apart = [t for t in teams if t.get("rank") is None]
        if apart:
            console.print(_ranking_table("Not yet comparable nationally", apart))
    else:
        groups: dict[str | None, list[dict[str, Any]]] = {}
        for t in teams:
            groups.setdefault(t.get("conference"), []).append(t)
        for name, rows in groups.items():
            console.print(_ranking_table(name or "No conference", rows))

    unranked = result.get("unranked") or []
    if unranked:
        console.print(f"\n[dim]Unranked: fewer than {cov.get('min_matches', '?')} matches ({len(unranked)})[/dim]")
        table = Table(style="dim")
        table.add_column("Team")
        table.add_column("Conference")
        table.add_column("Matches", justify="right")
        for row in unranked:
            table.add_row(
                str(row.get("team") or "?"),
                row.get("conference") or "no conference",
                f"{row.get('mp', 0)} of {row.get('needed', '?')}",
                style="dim",
            )
        console.print(table)


def _move_score(move: dict[str, Any]) -> str:
    if move.get("goals_for") is None or move.get("goals_against") is None:
        return "—"
    score = f"{move['goals_for']}-{move['goals_against']}"
    if move.get("penalties_for") is not None and move.get("penalties_against") is not None:
        score += f" ({move['penalties_for']}-{move['penalties_against']} pens)"
    return score


def _print_ranking_team(result: dict[str, Any]) -> None:
    console.print(
        f"[bold]{result.get('team') or result.get('team_id')} · MT Power Rating · {result.get('league')} "
        f"{result.get('age_group') or '?'} · {result.get('season') or '?'}[/bold]"
    )
    if not result.get("in_run"):
        console.print(f"[yellow]{result.get('reason') or 'Not in the latest run.'}[/yellow]")
        return
    where = []
    if result.get("rank") is not None:
        where.append(f"national rank {result['rank']}")
    if result.get("conference"):
        place = f" · {_ordinal(result['conference_rank'])}" if result.get("conference_rank") else ""
        where.append(f"{result['conference']}{place}")
    if result.get("tier"):
        where.append(str(result["tier"]).replace("_", " "))
    console.print(f"Rating [bold]{result.get('rating', 0):,}[/bold]" + "".join(f" · {w}" for w in where))
    console.print(
        f"[dim]{result.get('mp', 0)} matches · {result.get('w', 0)}-{result.get('d', 0)}-{result.get('l', 0)} · "
        f"{result.get('xconf_mp', 0)} against other conferences[/dim]"
    )
    if not result.get("ranked"):
        mp = result.get("mp", 0)
        console.print(f"[yellow]Unranked: {mp} of {mp + (result.get('needed') or 0)} matches[/yellow]")
    if result.get("badges"):
        console.print(f"[dim]Badges: {', '.join(b.replace('_', ' ') for b in result['badges'])}[/dim]")
    sos = result.get("sos")
    if sos:
        ranked = f" — {_ordinal(sos['rank'])} toughest of {sos['of']} ({sos['scope']})" if sos.get("rank") else ""
        console.print(f"Strength of schedule {sos['rating']:,}{ranked}")

    movers = result.get("biggest_movers") or []
    if movers:
        table = Table(title="Biggest movers")
        table.add_column("Date", style="magenta", no_wrap=True)
        table.add_column("Opponent", style="white")
        table.add_column("Result", justify="center")
        table.add_column("Score", justify="right")
        table.add_column("Expected", justify="right", style="dim")
        table.add_column("Change", justify="right", style="bold")
        for m in movers:
            table.add_row(
                str(m.get("match_date") or "—"),
                str(m.get("opponent") or "?"),
                str(m.get("result") or "?"),
                _move_score(m),
                f"{m.get('expected', 0):.0%}",
                f"{m.get('delta', 0):+.1f}",
            )
        console.print(table)

    history = result.get("history") or []
    if history:
        table = Table(title="Weekly history", style="dim")
        table.add_column("Run", style="dim")
        table.add_column("Computed", no_wrap=True)
        table.add_column("Rating", justify="right")
        table.add_column("Rank", justify="right")
        table.add_column("Conf. rank", justify="right")
        for h in history:
            table.add_row(
                str(h.get("run_id")),
                str(h.get("computed_at", "?"))[:10],
                f"{h.get('rating', 0):,}",
                _dash(h.get("rank")),
                _dash(h.get("conference_rank")),
            )
        console.print(table)


@app.command("rankings")
def rankings(
    target: str = typer.Argument(..., help='Age group, e.g. U17; or "team" followed by a team'),
    team: str = typer.Argument(None, help='After "team": team name or id'),
    age: str = typer.Option(None, "--age", "-a", help='With "team": the age group, e.g. U15'),
    league: str = typer.Option("Homegrown", "--league", "-l", help="Top-level league"),
    season: str = typer.Option(None, "--season", "-s", help="Season name (default: current)"),
    view: str = typer.Option(None, "--view", help="national or conference (national only when published)"),
    conference: str = typer.Option(None, "--conference", "-c", help="One conference, e.g. Northeast"),
    as_json: bool = typer.Option(False, "--json", help="Print the raw result"),
):
    """The MT Power Rating (SB-1808): `mt rankings U17`, or `mt rankings team "IFA" --age U15`.

    National lists only once the conferences are connected by matches; until
    then each conference is ranked on its own.
    """
    if target.casefold() == "team":
        if not team or not age:
            _fail('Usage: mt rankings team "<team>" --age U15')
        client, _ = get_client()
        team_row = _api(resolve_team, client, team)
        result = _api(client.get_power_rating_team, team_row["id"], age, league=league, season=season)
        if as_json:
            console.print_json(data=result)
            return
        _print_ranking_team(result)
        return

    if team is not None:
        _fail(f'Unexpected argument {team!r}. For one team: mt rankings team "<team>" --age U15')
    if view is not None and view not in RANKING_VIEWS:
        _fail(f"--view must be one of {', '.join(RANKING_VIEWS)}")
    client, _ = get_client()
    result = _api(client.get_power_rating, target, league=league, season=season, view=view, conference=conference)
    if as_json:
        console.print_json(data=result)
        return
    _print_rankings(result, target)


# The ingest_failures kinds that are feed-vs-person conflicts rather than
# names (SB-1787). Mirrors CONFLICT_KINDS in dao/ingest_failures_dao.py: the
# CLI is an HTTP client and does not import the DAO layer.
_CONFLICT_KINDS = "score_locked,scraped_overrode_manual"


@ingest_app.command("failures")
def ingest_failures(
    since: str = typer.Option(None, "--since", help="ISO timestamp; only names seen since then"),
    limit: int = typer.Option(50, "--limit", "-l", help="How many to show"),
    conflicts: bool = typer.Option(
        False, "--conflicts", help="Matches where the feed disagreed with a person's result, instead"
    ),
):
    """Names the ingest could not resolve, and what each one cost.

    --conflicts lists the feed-vs-person disagreements instead (SB-1787): a
    locked result the feed tried to change, or a person's score the feed
    replaced. One row per match; the sample says what differed.
    """
    client, _ = get_client()
    kind = _CONFLICT_KINDS if conflicts else None
    payload = _api(client.get_ingest_failures, since=since, limit=limit, kind=kind)
    rows = payload.get("failures") or []

    if not rows:
        console.print("[green]No open conflicts.[/green]" if conflicts else "[green]Nothing unresolved.[/green]")
        return

    if conflicts:
        table = Table(title="Feed conflicts")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Kind", style="dim")
        table.add_column("Match", style="white")
        table.add_column("What differed", style="white")
        table.add_column("Times", justify="right", style="yellow")
        table.add_column("Last seen", style="magenta")
        for row in rows:
            table.add_row(
                str(row.get("id", "?")),
                str(row.get("kind", "?")),
                str(row.get("raw_name", "?")),
                str(row.get("sample") or "—"),
                str(row.get("match_count", 0)),
                str(row.get("last_seen", "?"))[:10],
            )
        console.print(table)
        console.print("[dim]Close one with [/dim][cyan]mt ingest resolve <id>[/cyan]")
        return

    table = Table(title="Ingest failures")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Kind", style="dim")
    table.add_column("Name", style="white")
    table.add_column("League", style="dim")
    table.add_column("Matches", justify="right", style="yellow")
    table.add_column("Last seen", style="magenta")
    table.add_column("", style="dim")

    for row in rows:
        table.add_row(
            str(row.get("id", "?")),
            str(row.get("kind", "?")),
            str(row.get("raw_name", "?")),
            str(row.get("league") or "—"),
            str(row.get("match_count", 0)),
            str(row.get("last_seen", "?"))[:10],
            "stale" if row.get("stale") else "",
        )

    console.print(table)
    console.print(
        f"[dim]{payload.get('count', len(rows))} open · {payload.get('matches_dropped', 0)} matches dropped[/dim]"
    )

    stale_count = payload.get("stale_count") or 0
    if stale_count:
        # Stale means unseen, not fixed. Saying which is the point.
        days = payload.get("stale_after_days")
        console.print(
            f"[dim]{stale_count} not seen in {days} days. That is not the same as fixed — "
            "close one with [/dim][cyan]mt ingest resolve <id>[/cyan]"
        )


@ingest_app.command("resolve")
def ingest_resolve(
    failure_id: int = typer.Argument(..., help="Ingest failure id (from mt ingest failures)"),
    note: str = typer.Option(None, "--note", "-n", help="Why it is no longer a problem"),
):
    """Close an ingest failure that was fixed at the sender.

    The automatic resolve only fires when the same name resolves later. A name
    that will never be submitted again cannot trigger it, so the row would be
    reported forever as a problem that no longer exists (SB-845).
    """
    client, _ = get_client()
    row = _api(client.resolve_ingest_failure, failure_id, note)

    console.print(f"[green]Resolved #{row.get('id')}[/green] {row.get('raw_name')}")
    if row.get("resolution_note"):
        console.print(f"[dim]{row['resolution_note']}[/dim]")
    console.print("[dim]The row is kept — it is the record of which names were wrong and when.[/dim]")


# What `mt ingest plan` sends of each item in the --teams file. A scraper
# message carries a dozen more fields; the plan reads none of them.
_PLAN_MATCH_FIELDS = ("home_team", "away_team", "age_group", "league", "competition")
_PLAN_ENTRY_FIELDS = ("name", "age_group", "league")

# Actions sent per request by `mt ingest apply`. Each approved action costs
# the server several database round trips; a whole plan in one request can
# outlast the HTTP timeout, and a small batch bounds what an interrupted one
# leaves in doubt.
_APPLY_BATCH = 10


def _read_json_file(path: Path, what: str) -> Any:
    try:
        return json.loads(path.read_text())
    except OSError as exc:
        console.print(f"[red]Cannot read {what} {path}: {exc.strerror}[/red]")
        raise typer.Exit(1) from None
    except json.JSONDecodeError as exc:
        console.print(f"[red]{what} {path} is not JSON: {exc}[/red]")
        raise typer.Exit(1) from None


def _plan_teams_payload(items: Any, path: Path) -> list[dict]:
    """The --teams file cut down to the fields a plan reads."""
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        console.print(f"[red]{path} must be a JSON list of objects[/red]")
        raise typer.Exit(1)
    payload = []
    for item in items:
        fields = _PLAN_MATCH_FIELDS if "home_team" in item or "away_team" in item else _PLAN_ENTRY_FIELDS
        payload.append({key: item[key] for key in fields if item.get(key) is not None})
    return payload


def _print_plan_report(report: dict) -> None:
    table = Table(title="Team names by side")
    for column, style in (("Side", "white"), ("Entries", "dim"), ("Resolved", "green"), ("Ambiguous", "yellow")):
        table.add_column(column, style=style, justify="left" if column == "Side" else "right")
    for column in ("Missing", "alias-fixable", "needs-create", "unknown"):
        table.add_column(column, justify="right", style="red" if column == "Missing" else "dim")
    for name, side in (report.get("sides") or {}).items():
        missing = side.get("missing") or {}
        table.add_row(
            name,
            str(side.get("entries", 0)),
            str(side.get("resolved", 0)),
            str(side.get("ambiguous", 0)),
            str(missing.get("total", 0)),
            str(missing.get("alias_fixable", 0)),
            str(missing.get("needs_create", 0)),
            str(missing.get("unknown", 0)),
        )
    console.print(table)

    for name, side in (report.get("sides") or {}).items():
        dropped = ("unknown_league", "unknown_age_group")
        other = [f"{side[key]} {key.replace('_', ' ')}" for key in dropped if side.get(key)]
        if other:
            console.print(f"[yellow]{name}[/yellow][dim]: {', '.join(other)} — ingest drops these matches[/dim]")

    matches = report.get("matches")
    if matches:
        console.print(
            f"Matches that would land: [green]{matches['would_land']}[/green] of {matches['total']} now, "
            f"[cyan]{matches['would_land_after_plan']}[/cyan] if every action were applied"
        )
    else:
        console.print("[dim]The input carries no matches, so there is no count of matches that would land.[/dim]")

    conferences = report.get("conferences") or {}
    for row in conferences.get("placed") or []:
        console.print(
            f"[dim]Conference[/dim] {row['league']} / {row['conference']}: "
            f"{row['teams']} team(s), {row['registrations']} age group registration(s)"
        )
    if conferences.get("unplaced"):
        console.print(
            f"[yellow]{conferences['unplaced']} team(s) to create have no conference[/yellow] "
            "[dim]— they get a league and no registration, so they appear in no picker[/dim]"
        )
    for row in conferences.get("unknown") or []:
        console.print(f"[yellow]Bracket not used:[/yellow] {row['league']} / {row['conference']} — {row['reason']}")

    for row in report.get("ambiguous") or []:
        console.print(
            f"[yellow]Ambiguous:[/yellow] {row['name']} ({row['age_group']}, {row.get('league') or 'no hint'}) "
            f"[dim]{row.get('reason') or ''}[/dim]"
        )


@ingest_app.command("plan")
def ingest_plan(
    teams: Path = typer.Option(..., "--teams", help="JSON: scraper dry-run messages, or {name, age_group, league}"),
    brackets: Path = typer.Option(None, "--brackets", help="JSON: [{league, conference, age_group, teams}]"),
    output: Path = typer.Option(..., "--output", "-o", help="Where to write the plan file"),
):
    """Report what a tournament's team names resolve to, and propose fixes. Read-only.

    Writes the proposed aliases and teams to a plan file. Nothing in it is
    applied until someone edits an action's status to "approved" and runs
    `mt ingest apply` (SB-1763).
    """
    payload = _plan_teams_payload(_read_json_file(teams, "teams file"), teams)
    bracket_rows = _read_json_file(brackets, "brackets file") if brackets else None

    client, state = get_client()
    result = _api(client.plan_ingest, payload, bracket_rows)

    plan = {
        "plan_id": result["plan_id"],
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "generated_by": getattr(state, "username", None),
        "environment": get_current_env(),
        "database": result.get("database"),
        "inputs": {"teams": teams.name, "brackets": brackets.name if brackets else None},
        "review": (
            'Nothing here is applied as generated. Set "status" to "approved" on each action to apply, '
            'and fill in whatever a "needs_review" action asks for first.'
        ),
        "report": result["report"],
        "actions": result["actions"],
    }
    output.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")

    _print_plan_report(result["report"])
    counts = result["report"].get("actions") or {}
    for kind, by_status in counts.items():
        console.print(
            f"{kind}: [green]{by_status.get('proposed', 0)} proposed[/green], "
            f"[yellow]{by_status.get('needs_review', 0)} needs review[/yellow]"
        )
    console.print(f"[green]Plan {plan['plan_id']} written to {output}[/green] — {len(plan['actions'])} action(s)")
    console.print(
        '[dim]Nothing has been changed. Review the file, set "status": "approved" on the actions to apply, '
        "then:[/dim] [cyan]mt ingest apply " + str(output) + " --dry-run[/cyan]"
    )


_APPLY_STYLES = {
    "applied": "green",
    "would_apply": "cyan",
    "already_applied": "dim",
    "refused": "red",
    "failed": "red",
}


def _print_apply_rows(rows: list[dict]) -> None:
    for row in rows:
        outcome = row.get("outcome")
        if outcome == "skipped":
            continue
        style = _APPLY_STYLES.get(outcome, "white")
        detail = row.get("detail") or "; ".join(row.get("steps") or [])
        console.print(
            f"[{style}]{str(outcome).replace('_', ' ')}[/{style}] "
            f"{row.get('id') or '?'} {row.get('type') or '?'} {row.get('external_name') or ''}"
            + (f" [dim]— {detail}[/dim]" if detail else "")
        )


def _applied_log_path(plan_file: Path) -> Path:
    """`plan.json` → `plan.applied.json`, beside it."""
    return plan_file.with_name(f"{plan_file.stem}.applied.json")


def _read_applied_log(path: Path, plan: dict, env: str) -> dict:
    """The applied log for this plan: what is there, or a new one.

    Stops if the file belongs to another plan — appending to it would mix two
    plans' ids in the one record there is of what each created.
    """
    if not path.exists():
        return {"plan_id": plan["plan_id"], "environment": env, "database": plan["database"], "batches": []}
    log = _read_json_file(path, "applied log")
    if not isinstance(log, dict) or log.get("plan_id") != plan["plan_id"] or not isinstance(log.get("batches"), list):
        console.print(
            f"[red]{path} is not the applied log of plan {plan['plan_id']}.[/red] "
            "[yellow]Move it aside and run again.[/yellow]"
        )
        raise typer.Exit(1)
    return log


def _record_applied(path: Path, log: dict, batch: int, response: dict) -> None:
    """Append what one batch wrote to the applied log, and save it at once.

    `teams` and `team_mappings` carry no creator column, so this file — the
    ids each action created or touched — is the record an undo works from.
    """
    wrote = [
        {key: row.get(key) for key in ("id", "type", "external_name", "outcome", "ids", "steps")}
        for row in response.get("results") or []
        if row.get("ids")
    ]
    closed = response.get("failures_closed") or []
    if not wrote and not closed:
        return
    log["batches"].append(
        {
            "batch": batch,
            "applied_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "actions": wrote,
            "failures_closed": closed,
        }
    )
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n")


@ingest_app.command("apply")
def ingest_apply(
    plan_file: Path = typer.Argument(..., help="A reviewed plan file from mt ingest plan"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Check everything on the server; write nothing"),
):
    """Apply the approved actions of a reviewed plan. Idempotent (admin).

    Only actions whose status is "approved" are applied; the server re-checks
    each one and refuses any whose precondition no longer holds or that would
    duplicate a team name. What each action created is appended to
    <plan>.applied.json beside the plan file (SB-1763).
    """
    plan = _read_json_file(plan_file, "plan file")
    if not isinstance(plan, dict) or not plan.get("plan_id") or not isinstance(plan.get("actions"), list):
        console.print(f"[red]{plan_file} is not a plan file: it needs a plan_id and an actions list[/red]")
        raise typer.Exit(1)

    # Team and club ids are per database: an id from one names a different row
    # in another. The server checks the fingerprint; this is the readable half,
    # and a plan that does not say where it was made is not taken on trust.
    env = get_current_env()
    if not plan.get("environment") or not plan.get("database"):
        missing = "environment" if not plan.get("environment") else "database"
        console.print(
            f'[red]{plan_file} has no "{missing}" in its header, so there is no telling which database '
            "it was made against.[/red]\n[yellow]Plan again:[/yellow] mt ingest plan --teams … -o …"
        )
        raise typer.Exit(1)
    if plan["environment"] != env:
        console.print(
            f"[red]This plan was generated against {plan['environment']}, and this command targets {env}.[/red]\n"
            f"[yellow]Plan again against {env}, or run:[/yellow] "
            f"mt --env {plan['environment']} ingest apply {plan_file}"
        )
        raise typer.Exit(1)

    actions = plan["actions"]
    log_path = _applied_log_path(plan_file)
    log = None if dry_run else _read_applied_log(log_path, plan, env)
    client, _ = get_client()

    # A dry run goes as one request: the server then judges two actions that
    # share a new club or team as the real run would. A real run goes in
    # batches, each reported as it returns.
    size = max(len(actions), 1) if dry_run else _APPLY_BATCH
    batches = [actions[start : start + size] for start in range(0, len(actions), size)]
    counts: Counter = Counter()
    closed = 0
    for number, batch in enumerate(batches, start=1):
        first = (number - 1) * size + 1
        label = f"Batch {number} of {len(batches)} (actions {first}-{first + len(batch) - 1})"
        try:
            response = client.apply_ingest_plan(plan["plan_id"], batch, plan["database"], dry_run)
        except (httpx.TransportError, APIError) as exc:
            reason = str(exc) or type(exc).__name__
            console.print(f"[red]{label} did not complete: {reason}[/red]")
            console.print(
                f"{number - 1} of {len(batches)} batch(es) completed before it."
                + ("" if dry_run else f" What they wrote is in {log_path}.")
            )
            if not dry_run:
                console.print(
                    "[yellow]This batch may have been partly applied[/yellow] — the server carries on after the "
                    "client stops waiting. Run the same command again: apply is idempotent, so what is already "
                    "there is reported as already applied and the rest is finished."
                )
            raise typer.Exit(1) from None

        rows = response.get("results") or []
        if len(batches) > 1:
            console.print(f"[dim]{label}[/dim]")
        _print_apply_rows(rows)
        counts.update(row.get("outcome") for row in rows)
        closed += len(response.get("failures_closed") or [])
        if log is not None:
            _record_applied(log_path, log, number, response)

    done = "would apply" if dry_run else "applied"
    console.print(
        f"{counts.get('would_apply' if dry_run else 'applied', 0)} {done} · "
        f"{counts.get('already_applied', 0)} already applied · "
        f"{counts.get('refused', 0)} refused · {counts.get('failed', 0)} failed"
    )
    skipped = counts.get("skipped", 0)
    if skipped:
        console.print(
            f"[yellow]{skipped} of {len(actions)} action(s) skipped: not approved.[/yellow] "
            '[dim]Set "status": "approved" in the plan file to apply one.[/dim]'
        )
    if dry_run:
        console.print("[dim]Dry run: nothing was written.[/dim]")
    else:
        if closed:
            console.print(f"[green]{closed} ingest failure(s) closed[/green] [dim](note: plan {plan['plan_id']})[/dim]")
        if log and log["batches"]:
            console.print(f"[dim]What was written is recorded in {log_path} — commit it with the plan.[/dim]")
    if counts.get("refused") or counts.get("failed"):
        raise typer.Exit(1)


@ai_app.command("gaps")
def ai_gaps(
    days: int = typer.Option(30, "--days", "-d", help="How far back to look"),
    tool: str = typer.Option(None, "--tool", "-t", help="One tool only, e.g. search_teams"),
    limit: int = typer.Option(50, "--limit", "-l", help="How many to show"),
):
    """What MT AI could not answer: not_found and ambiguous tool calls, most asked first.

    A not_found name that is a real team wants an alias; a recurring one is an
    eval case; a recurring question no tool answers is the next tool (SB-1308).
    """
    client, _ = get_client()
    payload = _api(client.get_ai_gaps, days=days, tool=tool)
    rows = payload.get("gaps") or []
    total = payload.get("total_calls")

    if not rows:
        console.print(f"[green]Nothing unanswered in the last {payload.get('days', days)} days.[/green]")
        if total is not None:
            console.print(f"[dim]{total} tool call(s) in that window.[/dim]")
        return

    table = Table(title=f"MT AI gaps — last {payload.get('days', days)} days")
    table.add_column("Tool", style="dim")
    table.add_column("Query", style="white")
    table.add_column("Age", style="dim")
    table.add_column("Asked", justify="right", style="yellow")
    table.add_column("Not found", justify="right")
    table.add_column("Ambiguous", justify="right")
    table.add_column("Last seen", style="magenta")

    for row in rows[:limit]:
        table.add_row(
            str(row.get("tool", "?")),
            str(row.get("query") or "—"),
            ", ".join(row.get("age_groups") or []) or "—",
            str(row.get("count", 0)),
            str(row.get("not_found", 0)),
            str(row.get("ambiguous", 0)),
            str(row.get("last_seen") or "?")[:10],
        )

    console.print(table)
    # The denominator ships with the figure (CLAUDE.md rule 3).
    of_total = f" of {total} tool calls" if total is not None else ""
    console.print(
        f"[dim]{payload.get('gap_calls', 0)} unanswered{of_total} · {payload.get('count', len(rows))} distinct"
        + (f" · showing {limit}" if len(rows) > limit else "")
        + "[/dim]"
    )
    if payload.get("truncated"):
        console.print("[yellow]Hit the row cap — narrow with --days or --tool.[/yellow]")


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
    table.add_column("Shootout pts", justify="center", style="magenta")
    table.add_column("Table", justify="center", style="blue")

    for t in types:
        table.add_row(
            str(t.get("id", "?")),
            str(t.get("name", "?")),
            "yes" if t.get("counts_for_qualification") else "",
            "2 / 1" if t.get("shootout_points") else "",
            "yes" if t.get("has_standings") else "",
        )

    console.print(table)
    if any(t.get("shootout_points") for t in types):
        console.print("[dim]Shootout pts: a match level after regulation goes to penalties; winner 2, loser 1.[/dim]")
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


def _print_merge(result: dict, title: str) -> list[dict]:
    """The per-table counts of a merge, then its blockers. Returns the blockers."""
    tables = result.get("tables") or {}
    # A blocked dry run can stop before counting anything; an empty table
    # would read as "nothing references this".
    if tables:
        table = Table(title=title)
        table.add_column("Table", style="cyan")
        table.add_column("Moved", justify="right")
        table.add_column("Dropped", justify="right")
        for name, counts in sorted(tables.items()):
            moved, dropped = counts.get("moved", 0), counts.get("dropped", 0)
            style = None if moved or dropped else "dim"
            table.add_row(name, str(moved), str(dropped), style=style)
        console.print(table)
        console.print("[dim]dropped = the target already had that row, or it is derived and gets recomputed[/dim]")

    blockers = result.get("blockers") or []
    for b in blockers:
        ref = ", ".join(f"{k} {v}" for k, v in b.items() if k not in ("kind", "detail"))
        console.print(f"[red]blocked[/red] {b.get('kind')}: {b.get('detail')} ({ref})")
    return blockers


def _resolve_exact(items: list[dict], term: str, kind: str) -> dict:
    """One row by id or by its exact full name (case-insensitive).

    Merges delete a row, so the near-miss matching every other command offers
    is refused here: "City SC" must not quietly become "City SC San Diego".
    """
    if str(term).isdigit():
        target = int(term)
        for item in items:
            if item.get("id") == target:
                return item
        raise ResolutionError(f"No {kind} with id {target}")
    needle = term.lower().strip()
    exact = [i for i in items if (i.get("name") or "").lower().strip() == needle]
    if len(exact) == 1:
        return exact[0]
    if exact:
        ids = ", ".join(f"#{i['id']}" for i in exact)
        raise ResolutionError(f"{len(exact)} {kind}s are named {term!r} ({ids}); use the id")
    raise ResolutionError(f"No {kind} named exactly {term!r}; merges need the exact name or the id")


def _run_merge(kind: str, source: dict, target: dict, merge_fn, yes: bool) -> dict:
    """Dry run, show it, confirm, then merge for real. Shared by team and club."""
    if source["id"] == target["id"]:
        _fail(f"Both arguments are {kind} #{source['id']}")

    console.print(
        f"[bold]{source.get('name')}[/bold] ({kind} #{source['id']}) -> "
        f"[bold]{target.get('name')}[/bold] ({kind} #{target['id']})"
    )
    preview = _api(merge_fn, source["id"], target["id"], dry_run=True)
    blockers = _print_merge(preview, f"Dry run: merge {kind} #{source['id']} into #{target['id']}")
    # A dry run stops early at the first constraint it trips (often the one a
    # blocker names); the payload says which, as a SQLSTATE and table.
    error = preview.get("error") or {}
    if error:
        where = ", ".join(f"{k} {v}" for k, v in error.items())
        console.print(f"[yellow]dry run stopped early: {where}[/yellow]")
    if blockers:
        _fail(f"{len(blockers)} blocker(s); nothing was changed. Resolve them and run again.")
    if not preview.get("complete", True):
        _fail("The dry run did not complete; nothing was changed.")

    if not yes and not typer.confirm(f"Merge and delete {kind} #{source['id']}?"):
        raise typer.Exit(1)
    result = _api(merge_fn, source["id"], target["id"], dry_run=False)
    console.print(f"[green]Merged {kind} #{source['id']} into #{target['id']} ({target.get('name')})[/green]")
    return result


@team_app.command("merge")
def team_merge(
    source: str = typer.Argument(..., help="Duplicate team (id or exact name) — deleted after the merge"),
    target: str = typer.Argument(..., help="Team to keep (id or exact name)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation after the dry run"),
):
    """Fold a duplicate team into the one to keep (SB-1822).

    Matches, mappings, aliases, rosters, managers and follows move to the
    target; rows the target already has are dropped, and power ratings are
    dropped for the next run to recompute. The duplicate's name is kept as a
    former_name alias, so the feed resolves either spelling. Always shows a
    dry run first.
    """
    client, _ = get_client()
    teams = _api(client.get_teams) or []
    src = _api(_resolve_exact, teams, source, "team")
    dst = _api(_resolve_exact, teams, target, "team")
    result = _run_merge("team", src, dst, client.merge_team, yes)
    alias = result.get("alias")
    if alias == "added":
        console.print(f"[dim]{src.get('name')!r} kept as a former_name alias of #{dst['id']}[/dim]")
    elif alias == "exists":
        console.print(f"[dim]{src.get('name')!r} was already an alias of #{dst['id']}; left as it was[/dim]")
    copied = result.get("copied") or []
    if copied:
        console.print(f"[dim]copied from #{src['id']} because #{dst['id']} had none: {', '.join(copied)}[/dim]")


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


def _mapping_rows(team: dict) -> list[dict]:
    """The team's registrations, flattened for display."""
    rows = []
    for mapping in team.get("team_mappings") or []:
        age_group = mapping.get("age_groups") or {}
        division = mapping.get("divisions") or {}
        rows.append(
            {
                "age_group": age_group.get("name") or "?",
                "age_group_id": age_group.get("id"),
                "division": division.get("name") or "?",
                "division_id": division.get("id"),
                "league": (division.get("leagues") or {}).get("name") or "?",
            }
        )
    return sorted(rows, key=lambda r: (r["age_group"], r["league"], r["division"]))


def _print_mappings(team: dict) -> None:
    rows = _mapping_rows(team)
    if not rows:
        console.print(f"[yellow]{team.get('name')} is registered in no age group.[/yellow]")
        console.print("[dim]It will not appear in any age-group team picker until it is.[/dim]")
        return

    table = Table(title=f"Registrations — {team.get('name')}")
    table.add_column("Age Group", style="cyan", no_wrap=True)
    table.add_column("League", style="white")
    table.add_column("Division", style="white")
    for row in rows:
        table.add_row(row["age_group"], row["league"], row["division"])
    console.print(table)


@mapping_app.command("list")
def team_mapping_list(team: str = typer.Argument(..., help="Team name or id")):
    """Which age groups and divisions a team is registered in.

    This is what /api/teams turns into a team's age_groups, and what every
    age-group team picker filters on. A team with matches at an age group it is
    not registered in is invisible there (SB-852).
    """
    client, _ = get_client()
    _print_mappings(_api(resolve_team, client, team))


@mapping_app.command("add")
def team_mapping_add(
    team: str = typer.Argument(..., help="Team name or id"),
    age: str = typer.Option(..., "--age", "-a", help="Age group, e.g. U15"),
    division: str = typer.Option(..., "--division", "-d", help="Division name or id"),
):
    """Register a team in an age group and division."""
    client, _ = get_client()

    team_row = _api(resolve_team, client, team)
    age_group_id = _resolve_age_group_id(client, age)
    division_id = _api(_resolve_division_id, client, division)

    _api(client.create_team_mapping, team_row["id"], age_group_id, division_id)
    console.print(f"[green]Registered {team_row.get('name')}[/green] · {age} · division {division_id}")

    # Re-read and print rather than claim success and stop. The Admin UI's
    # equivalent shows a stale list after writing, which reads as a failed save
    # and invites a duplicate attempt — worth not repeating here.
    _print_mappings(_api(resolve_team, client, team_row["id"]))


@mapping_app.command("remove")
def team_mapping_remove(
    team: str = typer.Argument(..., help="Team name or id"),
    age: str = typer.Option(..., "--age", "-a", help="Age group, e.g. U15"),
    division: str = typer.Option(..., "--division", "-d", help="Division name or id"),
):
    """Remove a team's registration in an age group and division.

    The matches stay. This only says the team no longer plays there, which is
    what the age-group pickers read.
    """
    client, _ = get_client()

    team_row = _api(resolve_team, client, team)
    age_group_id = _resolve_age_group_id(client, age)
    division_id = _api(_resolve_division_id, client, division)

    _api(client.delete_team_mapping, team_row["id"], age_group_id, division_id)
    console.print(f"[green]Removed registration[/green] {team_row.get('name')} · {age} · division {division_id}")
    _print_mappings(_api(resolve_team, client, team_row["id"]))


def _resolve_division_in_league(client, name: str, league: str) -> int:
    """A division by name within one league.

    Names repeat across leagues: "New England" is both an Academy conference and
    a Flex conference, so a name alone could hide a team from the wrong table.
    """
    needle = name.lower().strip()
    found = [
        d
        for d in _api(client.get_divisions) or []
        if (d.get("name") or "").lower().strip() == needle
        and ((d.get("leagues") or {}).get("name") or "").lower() == league.lower().strip()
    ]
    if len(found) != 1:
        raise ResolutionError(f"Expected one {league} division named {name!r}, found {len(found)}")
    return found[0]["id"]


def _print_guests(client, season_id: int, age_group_id: int | None = None) -> None:
    guests = _api(client.list_division_guests, season_id, age_group_id) or []
    if not guests:
        console.print("[dim]No guests: every team that plays in a table has a row.[/dim]")
        return
    table = Table(title="Division guests — no table row, results still count for opponents")
    for column in ("ID", "Team", "Age", "League", "Division", "Reason"):
        table.add_column(column)
    for guest in guests:
        division = guest.get("division") or {}
        table.add_row(
            str(guest["id"]),
            (guest.get("team") or {}).get("name") or "?",
            (guest.get("age_group") or {}).get("name") or "?",
            (division.get("leagues") or {}).get("name") or "?",
            division.get("name") or "?",
            guest.get("reason") or "",
        )
    console.print(table)


def _guest_target(client, team: str, age: str, division: str, league: str, season: str | None):
    team_row = _api(resolve_team, client, team)
    age_group_id = _resolve_age_group_id(client, age)
    try:
        division_id = _resolve_division_in_league(client, division, league)
    except ResolutionError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    season_id = _resolve_season_id(client, season)
    return team_row, division_id, age_group_id, season_id


@guest_app.command("list")
def team_guest_list(
    age: str = typer.Option(None, "--age", "-a", help="Age group, e.g. U15"),
    season: str = typer.Option(None, "--season", "-s", help="Season name (default: current)"),
):
    """Which teams have no row in a table they play fixtures in."""
    client, _ = get_client()
    _print_guests(client, _resolve_season_id(client, season), _resolve_age_group_id(client, age) if age else None)


@guest_app.command("add")
def team_guest_add(
    team: str = typer.Argument(..., help="Team name or id"),
    age: str = typer.Option(..., "--age", "-a", help="Age group, e.g. U15"),
    division: str = typer.Option(..., "--division", "-d", help="Division name"),
    reason: str = typer.Option(..., "--reason", "-r", help="Why this team is not in the table"),
    league: str = typer.Option("Flex", "--league", "-l", help="League the division belongs to"),
    season: str = typer.Option(None, "--season", "-s", help="Season name (default: current)"),
):
    """Hide a team from one table. Its matches still count for its opponents."""
    client, _ = get_client()
    team_row, division_id, age_group_id, season_id = _guest_target(client, team, age, division, league, season)
    _api(client.add_division_guest, team_row["id"], division_id, age_group_id, season_id, reason)
    console.print(f"[green]{team_row.get('name')} has no row[/green] in {age} {league} {division}")
    _print_guests(client, season_id, age_group_id)


@guest_app.command("remove")
def team_guest_remove(
    team: str = typer.Argument(..., help="Team name or id"),
    age: str = typer.Option(..., "--age", "-a", help="Age group, e.g. U15"),
    division: str = typer.Option(..., "--division", "-d", help="Division name"),
    league: str = typer.Option("Flex", "--league", "-l", help="League the division belongs to"),
    season: str = typer.Option(None, "--season", "-s", help="Season name (default: current)"),
):
    """Give a team its row in a table back."""
    client, _ = get_client()
    team_row, division_id, age_group_id, season_id = _guest_target(client, team, age, division, league, season)
    guests = _api(client.list_division_guests, season_id, age_group_id) or []
    guest = next((g for g in guests if g["team_id"] == team_row["id"] and g["division_id"] == division_id), None)
    if guest is None:
        console.print(f"[yellow]{team_row.get('name')} is not a guest in {age} {league} {division}.[/yellow]")
        raise typer.Exit(1)
    _api(client.remove_division_guest, guest["id"])
    console.print(f"[green]{team_row.get('name')} has its row back[/green] in {age} {league} {division}")
    _print_guests(client, season_id, age_group_id)


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


def _print_club(club: dict) -> None:
    """A club's fields, including the ones a careless write would blank."""
    table = Table(title=f"Club #{club.get('id')} — {club.get('name')}", show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    for label, key in (
        ("City", "city"),
        ("Website", "website"),
        ("Description", "description"),
        ("Crest", "logo_url"),
        ("Primary", "primary_color"),
        ("Secondary", "secondary_color"),
    ):
        table.add_row(label, str(club.get(key) or "—"))
    table.add_row("Pro academy", "yes" if club.get("pro_academy") else "no")
    console.print(table)


@club_app.command("show")
def club_show(club: str = typer.Argument(..., help="Club name or id")):
    """One club, with every field a write has to preserve.

    There was no way to read a club from the CLI, which is why correcting one
    meant querying the database first (SB-872).
    """
    client, _ = get_client()
    _print_club(_api(_resolve_club, client, club))


@club_app.command("set-pro-academy")
def club_set_pro_academy(
    club: str = typer.Argument(..., help="Club name or id"),
    on: bool = typer.Option(True, "--on/--off", help="Flag or unflag the club"),
):
    """Mark a club as an MLS pro academy, or unmark it.

    `mt club create` takes --pro-academy; nothing could set it afterwards, so a
    club that already existed had to be corrected by hand through
    update_club_profile (SB-872).

    PUT /api/clubs/{id} is a **replace, not a patch**: every field it is not
    given is blanked. So this reads the club first and resends all of it,
    changing only the flag. Omitting logo_url and the brand colours is how a
    crest gets destroyed — SB-824 and SB-842 are both that bug.
    """
    client, _ = get_client()
    current = _api(_resolve_club, client, club)

    if bool(current.get("pro_academy")) == on:
        console.print(f"[yellow]{current.get('name')} is already {'flagged' if on else 'unflagged'}.[/yellow]")
        return

    updated = _api(
        client.update_club_profile,
        current["id"],
        current.get("name"),
        current.get("city") or "",
        current.get("website"),
        current.get("description"),
        current.get("logo_url"),
        current.get("primary_color"),
        current.get("secondary_color"),
        on,
    )

    was = "yes" if current.get("pro_academy") else "no"
    now = "yes" if updated.get("pro_academy") else "no"
    console.print(f"[green]{current.get('name')}[/green] pro academy: {was} → {now}")
    console.print("[dim]Every other field was read and resent unchanged.[/dim]")
    _print_club(updated)


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


# The server's own limits for POST /api/clubs/{id}/logo, checked here so a bad
# file fails before it is sent rather than as a 400 after.
LOGO_SUFFIXES = {".png", ".jpg", ".jpeg"}
LOGO_MAX_BYTES = 2 * 1024 * 1024

_HEX_COLOUR = re.compile(r"^#[0-9A-Fa-f]{6}$")


@club_app.command("set-logo")
def club_set_logo(
    club: str = typer.Argument(..., help="Club name or id"),
    file: Path = typer.Argument(..., help="PNG or JPG crest, 2MB at most"),
    if_missing: bool = typer.Option(False, "--if-missing", help="Do nothing if the club already has a crest"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Replace an existing crest without asking"),
):
    """Upload a club's crest.

    The server stores it, writes the 64px and 128px variants the app and IG
    cards use, and sets logo_url itself — so unlike set-colors this is not a
    read-modify-write, and nothing else on the club changes (SB-1777).
    """
    if not file.is_file():
        _fail(f"No such file: {file}")
    if file.suffix.lower() not in LOGO_SUFFIXES:
        _fail(f"Crest must be PNG or JPG, got {file.suffix or 'no extension'}")
    size = file.stat().st_size
    if size > LOGO_MAX_BYTES:
        _fail(f"Crest is {size / 1024 / 1024:.2f}MB; the server takes 2MB at most")

    client, _ = get_client()
    current = _api(_resolve_club, client, club)
    name = current.get("name")

    if current.get("logo_url"):
        if if_missing:
            console.print(f"[yellow]{name} already has a crest; left alone (--if-missing).[/yellow]")
            return
        console.print(f"{name} already has a crest: {current['logo_url']}")
        if not yes and not typer.confirm("Replace it?"):
            raise typer.Exit(1)

    result = _api(client.upload_club_logo, current["id"], str(file))
    console.print(f"[green]{name}[/green] (club #{current['id']}) crest set: {result.get('logo_url')}")


@club_app.command("set-colors")
def club_set_colors(
    club: str = typer.Argument(..., help="Club name or id"),
    primary: str | None = typer.Option(None, "--primary", "-p", help="Primary colour, #RRGGBB"),
    secondary: str | None = typer.Option(None, "--secondary", "-s", help="Secondary colour, #RRGGBB"),
):
    """Set a club's brand colours, which the IG cards and team headers use.

    PUT /api/clubs/{id} is a replace, not a patch, so this reads the club and
    resends every field, changing only the colours given. Sending a subset is
    how a crest gets blanked (SB-824, SB-842).
    """
    if primary is None and secondary is None:
        _fail("Give --primary, --secondary or both")
    for label, value in (("primary", primary), ("secondary", secondary)):
        if value is not None and not _HEX_COLOUR.match(value):
            _fail(f"{label} colour must look like #1E3A8A, got {value!r}")

    client, _ = get_client()
    current = _api(_resolve_club, client, club)
    full = _api(client.get_club, current["id"]) or current

    new_primary = primary.upper() if primary else full.get("primary_color")
    new_secondary = secondary.upper() if secondary else full.get("secondary_color")

    updated = _api(
        client.update_club_profile,
        current["id"],
        name=full.get("name"),
        city=full.get("city") or "",
        website=full.get("website"),
        description=full.get("description"),
        logo_url=full.get("logo_url"),
        primary_color=new_primary,
        secondary_color=new_secondary,
        pro_academy=bool(full.get("pro_academy")),
    )
    console.print(
        f"[green]{full.get('name')}[/green] colours: "
        f"{full.get('primary_color')} / {full.get('secondary_color')} → {new_primary} / {new_secondary}"
    )
    console.print("[dim]crest, website, description and pro-academy flag preserved[/dim]")
    _print_club(updated or full)


@club_app.command("merge")
def club_merge(
    source: str = typer.Argument(..., help="Duplicate club (id or exact name) — deleted after the merge"),
    target: str = typer.Argument(..., help="Club to keep (id or exact name)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation after the dry run"),
):
    """Fold a duplicate club into the one to keep (SB-1822).

    Teams, members, invitations and channels move to the target. The target
    keeps its own crest and colours; the duplicate's only fill ones it lacks.
    Merge duplicate teams first (mt team merge) — a team of the same name in
    both clubs blocks this. Always shows a dry run first.
    """
    client, _ = get_client()
    clubs = _api(client.get_clubs) or []
    src = _api(_resolve_exact, clubs, source, "club")
    dst = _api(_resolve_exact, clubs, target, "club")
    result = _run_merge("club", src, dst, client.merge_club, yes)
    copied = result.get("copied") or []
    if copied:
        console.print(f"[dim]copied from #{src['id']} because #{dst['id']} had none: {', '.join(copied)}[/dim]")


@club_app.command("logo-gaps")
def club_logo_gaps(
    season_id: int = typer.Option(None, "--season", help="Season id (default: current)"),
    include_all: bool = typer.Option(False, "--all", help="Every team and club, not only those with matches"),
):
    """Where crests are missing: teams with no club, clubs with no logo, hot-linked logos (SB-1815).

    Scoped to teams with a match in the season and their clubs, so the list
    is what visitors actually see. A hot-linked logo is one not stored in our
    club-logos bucket — it breaks whenever the other site changes.
    """
    client, _ = get_client()
    payload = _api(client.get_club_logo_gaps, season_id=season_id, include_all=include_all)
    scope = "every team and club" if include_all else f"teams with matches in season {payload.get('season_id')}"
    console.print(f"[dim]Scope: {scope}[/dim]")

    teams = payload.get("teams_without_club") or []
    console.print(f"\n[bold]Teams with no club[/bold] ({len(teams)})")
    for t in teams:
        console.print(f"  #{t['id']:<5} {t.get('name')}  [dim]{t.get('match_count', 0)} matches[/dim]")
    if not teams:
        console.print("  none")

    missing = payload.get("clubs_without_logo") or []
    console.print(f"\n[bold]Clubs with no logo[/bold] ({len(missing)})")
    for c in missing:
        console.print(f"  #{c['id']:<5} {c.get('name')}")
    if not missing:
        console.print("  none")

    external = payload.get("clubs_external_logo") or []
    console.print(f"\n[bold]Clubs with a hot-linked logo[/bold] ({len(external)})")
    for c in external:
        console.print(f"  #{c['id']:<5} {c.get('name')}  [dim]{c.get('host') or c.get('logo_url')}[/dim]")
    if not external:
        console.print("  none")
    if external:
        console.print("\n[dim]Fix one with: mt club set-logo <club> <file>[/dim]")


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

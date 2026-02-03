#!/usr/bin/env python3
"""
Sync authentication users from cloud Supabase (prod) to local Supabase.
Assigns known passwords based on user roles for local development testing.

Usage:
    cd backend && uv run python scripts/sync_users_to_local.py --from prod
    cd backend && uv run python scripts/sync_users_to_local.py --from prod --users tom
    cd backend && uv run python scripts/sync_users_to_local.py --from prod --filter "tom%"
    cd backend && uv run python scripts/sync_users_to_local.py --from prod --role admin
    cd backend && uv run python scripts/sync_users_to_local.py --from prod --include-all
    cd backend && uv run python scripts/sync_users_to_local.py --from prod --dry-run
    cd backend && uv run python scripts/sync_users_to_local.py --from prod --force
"""

import contextlib
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from supabase import Client, create_client

app = typer.Typer()
console = Console()

# Role-based password mapping
ROLE_PASSWORDS = {
    "admin": "admin123",
    "team-manager": "team123",
    "team_manager": "team123",
    "club_manager": "club123",
    "club-manager": "club123",
    "team-fan": "fan123",
    "team_fan": "fan123",
    "club-fan": "fan123",
    "club_fan": "fan123",
    "team-player": "play123",
    "team_player": "play123",
    "user": "fan123",
}

# Default username patterns to exclude (test users)
DEFAULT_EXCLUSIONS = [
    "contract_test_%",
    "test_login_%",
    "duplicate_%",
]


def get_password_for_role(role: str) -> str:
    """Get the password for a given role, defaulting to fan123."""
    return ROLE_PASSWORDS.get(role, "fan123")


def load_env_file(env_name: str) -> dict:
    """Load environment variables from a specific .env file."""
    env_file = Path(__file__).parent.parent / f".env.{env_name}"

    if not env_file.exists():
        console.print(f"[red]Environment file not found: {env_file}[/red]")
        raise typer.Exit(1)

    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env_vars[key.strip()] = value.strip()

    return env_vars


def _get_users_list(response) -> list:
    """Extract users list from Supabase auth response."""
    if isinstance(response, list):
        return response
    return getattr(response, "data", {}).get("users", [])


def _match_like_pattern(value: str, pattern: str) -> bool:
    """Match a value against a SQL LIKE pattern."""
    value_lower = value.lower()
    pattern_lower = pattern.lower()

    if pattern_lower.endswith("%") and not pattern_lower.startswith("%"):
        return value_lower.startswith(pattern_lower[:-1])
    elif pattern_lower.startswith("%") and not pattern_lower.endswith("%"):
        return value_lower.endswith(pattern_lower[1:])
    elif "%" in pattern_lower:
        parts = pattern_lower.split("%")
        if len(parts) == 2:
            return parts[0] in value_lower and parts[1] in value_lower
    return value_lower == pattern_lower


def _is_excluded(username: str, include_all: bool) -> bool:
    """Check if a username should be excluded based on default patterns."""
    if include_all:
        return False
    return any(_match_like_pattern(username, pattern) for pattern in DEFAULT_EXCLUSIONS)


def _apply_filters(
    username: str,
    role: str,
    usernames: list[str] | None,
    filter_pattern: str | None,
    roles: list[str] | None,
) -> bool:
    """Apply user filters, return True if user should be included."""
    if usernames and username not in usernames:
        return False

    if filter_pattern and not _match_like_pattern(username, filter_pattern):
        return False

    if roles:
        normalized_roles = [r.replace("-", "_") for r in roles]
        user_role_normalized = role.replace("-", "_")
        if user_role_normalized not in normalized_roles:
            return False

    return True


def _fetch_user_profile(supabase: Client, user_id: str) -> dict | None:
    """Fetch a user profile from Supabase."""
    try:
        result = supabase.table("user_profiles").select("*").eq("id", user_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        console.print(f"[dim]Could not fetch profile for {user_id}: {e}[/dim]")
        return None


def fetch_users_from_cloud(
    supabase: Client,
    usernames: list[str] | None = None,
    filter_pattern: str | None = None,
    roles: list[str] | None = None,
    include_all: bool = False,
) -> list[dict]:
    """Fetch users from cloud Supabase with optional filtering."""
    console.print("[cyan]Fetching users from cloud...[/cyan]")

    # Paginate through all auth users (default limit is 50)
    users_list = []
    page = 1
    per_page = 100
    while True:
        response = supabase.auth.admin.list_users(page=page, per_page=per_page)
        page_users = _get_users_list(response)
        if not page_users:
            break
        users_list.extend(page_users)
        console.print(f"[dim]  Fetched page {page}: {len(page_users)} users[/dim]")
        if len(page_users) < per_page:
            break
        page += 1

    if not users_list:
        console.print("[yellow]No users found in cloud[/yellow]")
        return []

    console.print(f"[dim]Found {len(users_list)} total auth users[/dim]")

    # Build user data with profiles
    users_data = []
    for user in users_list:
        user_id = user.id if hasattr(user, "id") else user.get("id")
        auth_email = user.email if hasattr(user, "email") else user.get("email")
        meta = user.user_metadata if hasattr(user, "user_metadata") else None
        user_metadata = meta or user.get("user_metadata", {}) or {}

        profile = _fetch_user_profile(supabase, user_id)

        users_data.append(
            {
                "id": user_id,
                "auth_email": auth_email,
                "user_metadata": user_metadata,
                "profile": profile,
            }
        )

    # Apply filters
    filtered_users = []
    for user in users_data:
        profile = user.get("profile") or {}
        username = profile.get("username", "")
        role = profile.get("role", "user")

        if not username:
            continue

        if _is_excluded(username, include_all):
            continue

        if not _apply_filters(username, role, usernames, filter_pattern, roles):
            continue

        filtered_users.append(user)

    console.print(f"[green]Filtered to {len(filtered_users)} users[/green]")
    return filtered_users


def fetch_team_manager_assignments(
    supabase: Client,
    user_ids: list[str],
) -> dict[str, list[int]]:
    """Fetch team_manager_assignments for the given user IDs."""
    if not user_ids:
        return {}

    console.print("[cyan]Fetching team manager assignments...[/cyan]")

    assignments = {}
    for user_id in user_ids:
        try:
            result = supabase.table("team_manager_assignments").select("team_id").eq("user_id", user_id).execute()
            if result.data:
                assignments[user_id] = [row["team_id"] for row in result.data]
        except Exception as e:
            console.print(f"[dim]Could not fetch assignments for {user_id}: {e}[/dim]")

    total_assignments = sum(len(teams) for teams in assignments.values())
    console.print(f"[dim]Found {total_assignments} team manager assignments[/dim]")
    return assignments


def fetch_player_team_history(
    supabase: Client,
    user_ids: list[str],
) -> dict[str, list[dict]]:
    """Fetch player_team_history records for the given user IDs (player_ids)."""
    if not user_ids:
        return {}

    console.print("[cyan]Fetching player team history...[/cyan]")

    history = {}
    for user_id in user_ids:
        try:
            result = supabase.table("player_team_history").select("*").eq("player_id", user_id).execute()
            if result.data:
                history[user_id] = result.data
        except Exception as e:
            console.print(f"[dim]Could not fetch player history for {user_id}: {e}[/dim]")

    total_entries = sum(len(entries) for entries in history.values())
    console.print(f"[dim]Found {total_entries} player team history entries[/dim]")
    return history


def display_users_preview(
    users: list[dict],
    assignments: dict[str, list[int]],
    player_history: dict[str, list[dict]] | None = None,
) -> None:
    """Display a preview table of users to sync."""
    player_history = player_history or {}

    table = Table(
        title="Users to Sync",
        show_header=True,
        header_style="bold magenta",
        show_lines=True,
        box=box.ROUNDED,
    )
    table.add_column("Username", style="green", max_width=20)
    table.add_column("Role", style="yellow", max_width=15)
    table.add_column("Password", style="cyan", max_width=10)
    table.add_column("Email", style="dim", max_width=30)
    table.add_column("Team ID", style="blue", max_width=10)
    table.add_column("Club ID", style="blue", max_width=10)
    table.add_column("TM Assigns", style="magenta", max_width=12)
    table.add_column("Player Hist", style="cyan", max_width=12)

    for user in users:
        profile = user.get("profile") or {}
        username = profile.get("username", "N/A")
        role = profile.get("role", "user")
        password = get_password_for_role(role)
        email = profile.get("email") or user.get("auth_email", "N/A")
        team_id = str(profile.get("team_id", "-"))
        club_id = str(profile.get("club_id", "-"))

        user_assignments = assignments.get(user["id"], [])
        tm_display = ", ".join(str(t) for t in user_assignments) if user_assignments else "-"

        user_history = player_history.get(user["id"], [])
        history_display = str(len(user_history)) if user_history else "-"

        table.add_row(username, role, password, email, team_id, club_id, tm_display, history_display)

    console.print(table)


def _create_auth_user(
    supabase: Client,
    user_id: str,
    email: str,
    password: str,
    user_metadata: dict,
) -> bool:
    """Create an auth user in Supabase."""
    try:
        response = supabase.auth.admin.create_user(
            {
                "id": user_id,
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": user_metadata,
            }
        )
        return response.user is not None
    except Exception as e:
        console.print(f"[red]Error creating auth user: {e}[/red]")
        return False


def _create_user_profile(supabase: Client, profile_data: dict) -> bool:
    """Create a user profile in Supabase."""
    try:
        # Remove None values
        clean_data = {k: v for k, v in profile_data.items() if v is not None}
        supabase.table("user_profiles").insert(clean_data).execute()
        return True
    except Exception as e:
        console.print(f"[red]Error creating profile: {e}[/red]")
        return False


def _create_player_team_history(supabase: Client, player_history: list[dict]) -> int:
    """Create player team history entries. Returns count of successful inserts."""
    success_count = 0
    for entry in player_history:
        try:
            entry_data = {
                "player_id": entry["player_id"],
                "team_id": entry["team_id"],
                "season_id": entry.get("season_id"),
                "age_group_id": entry.get("age_group_id"),
                "league_id": entry.get("league_id"),
                "division_id": entry.get("division_id"),
                "jersey_number": entry.get("jersey_number"),
                "positions": entry.get("positions"),
                "is_current": entry.get("is_current", False),
                "notes": entry.get("notes"),
            }
            # Remove None values
            entry_data = {k: v for k, v in entry_data.items() if v is not None}
            supabase.table("player_team_history").insert(entry_data).execute()
            success_count += 1
        except Exception as e:
            team_id = entry.get("team_id")
            console.print(f"[dim]Player history failed (team {team_id}): {e}[/dim]")
    return success_count


def _delete_existing_user(supabase: Client, user_id: str, username: str) -> None:
    """Delete an existing user from local Supabase."""
    console.print(f"[yellow]Deleting existing user: {username}...[/yellow]")
    try:
        # Delete player team history first (FK constraint)
        supabase.table("player_team_history").delete().eq("player_id", user_id).execute()
        # Delete team manager assignments
        supabase.table("team_manager_assignments").delete().eq("user_id", user_id).execute()
        # Delete user profile
        supabase.table("user_profiles").delete().eq("id", user_id).execute()
        # Delete auth user
        supabase.auth.admin.delete_user(user_id)
    except Exception as e:
        console.print(f"[dim]Delete cleanup: {e}[/dim]")


def sync_user_to_local(
    local_supabase: Client,
    user: dict,
    team_assignments: list[int],
    player_history: list[dict] | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> bool:
    """Sync a single user to local Supabase. Returns True if successful."""
    player_history = player_history or []
    profile = user.get("profile") or {}
    user_id = user["id"]
    username = profile.get("username", "")
    role = profile.get("role", "user")
    password = get_password_for_role(role)
    internal_email = f"{username}@missingtable.local"

    if dry_run:
        console.print(f"[dim]Would sync: {username} ({role}) -> {password}[/dim]")
        return True

    # Check if user already exists
    try:
        existing = local_supabase.table("user_profiles").select("id").eq("id", user_id).execute()
        user_exists = bool(existing.data)
    except Exception:
        user_exists = False

    if user_exists:
        if force:
            _delete_existing_user(local_supabase, user_id, username)
        else:
            msg = f"[yellow]Skipping existing: {username} (use --force)[/yellow]"
            console.print(msg)
            return False

    # Create auth user
    if not _create_auth_user(
        local_supabase,
        user_id,
        internal_email,
        password,
        user.get("user_metadata", {}),
    ):
        console.print(f"[red]Failed to create auth user: {username}[/red]")
        return False

    # Create user profile
    profile_data = {
        "id": user_id,
        "username": username,
        "role": role,
        "display_name": profile.get("display_name"),
        "email": profile.get("email"),
        "phone_number": profile.get("phone_number"),
        "team_id": profile.get("team_id"),
        "club_id": profile.get("club_id"),
        "player_number": profile.get("player_number"),
        "positions": profile.get("positions"),
        "assigned_age_group_id": profile.get("assigned_age_group_id"),
        "invited_via_code": profile.get("invited_via_code"),
    }

    if not _create_user_profile(local_supabase, profile_data):
        console.print(f"[red]Error creating profile for {username}[/red]")
        # Cleanup: try to delete the auth user we just created
        with contextlib.suppress(Exception):
            local_supabase.auth.admin.delete_user(user_id)
        return False

    # Create team manager assignments
    for team_id in team_assignments:
        try:
            local_supabase.table("team_manager_assignments").insert(
                {
                    "user_id": user_id,
                    "team_id": team_id,
                }
            ).execute()
        except Exception as e:
            console.print(f"[dim]Team assignment failed ({team_id}): {e}[/dim]")

    # Create player team history entries
    history_count = _create_player_team_history(local_supabase, player_history)
    history_msg = f", {history_count} history" if history_count else ""
    console.print(f"[green]Synced: {username} ({role}) -> {password}{history_msg}[/green]")
    return True


def _validate_env(from_env: str) -> None:
    """Validate source environment."""
    if from_env not in ("prod",):
        console.print(f"[red]Invalid source environment: {from_env}[/red]")
        console.print("[yellow]Valid source environments: prod[/yellow]")
        raise typer.Exit(1)


def _validate_env_vars(env_name: str, env_vars: dict) -> None:
    """Validate environment has required variables."""
    required = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")
    if not all(k in env_vars for k in required):
        console.print(f"[red]Missing credentials in {env_name} environment[/red]")
        raise typer.Exit(1)


@app.command()
def sync(
    from_env: str = typer.Option(..., "--from", "-f", help="Source environment (prod)"),
    users: str | None = typer.Option(None, "--users", "-u", help="Comma-separated usernames"),
    filter_pattern: str | None = typer.Option(None, "--filter", help="SQL LIKE pattern (e.g., 'tom%')"),
    role: str | None = typer.Option(None, "--role", "-r", help="Comma-separated roles"),
    include_all: bool = typer.Option(False, "--include-all", help="Include test users"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview only"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing users"),
):
    """
    Sync users from cloud Supabase to local.

    By default, excludes test users (contract_test_%, test_login_%, duplicate_%).
    Use --include-all to override.
    """
    console.print("[bold cyan]User Sync Tool: Cloud -> Local[/bold cyan]")
    console.print(f"[dim]Source: {from_env} -> Target: local[/dim]\n")

    _validate_env(from_env)

    # Load environment configurations
    cloud_env = load_env_file(from_env)
    local_env = load_env_file("local")

    _validate_env_vars("cloud", cloud_env)
    _validate_env_vars("local", local_env)

    console.print(f"[dim]Cloud URL: {cloud_env['SUPABASE_URL']}[/dim]")
    console.print(f"[dim]Local URL: {local_env['SUPABASE_URL']}[/dim]\n")

    cloud_supabase = create_client(
        cloud_env["SUPABASE_URL"],
        cloud_env["SUPABASE_SERVICE_KEY"],
    )
    local_supabase = create_client(
        local_env["SUPABASE_URL"],
        local_env["SUPABASE_SERVICE_KEY"],
    )

    usernames_list = users.split(",") if users else None
    roles_list = role.split(",") if role else None

    cloud_users = fetch_users_from_cloud(
        cloud_supabase,
        usernames=usernames_list,
        filter_pattern=filter_pattern,
        roles=roles_list,
        include_all=include_all,
    )

    if not cloud_users:
        console.print("[yellow]No users to sync[/yellow]")
        raise typer.Exit(0)

    user_ids = [u["id"] for u in cloud_users]
    assignments = fetch_team_manager_assignments(cloud_supabase, user_ids)
    player_history = fetch_player_team_history(cloud_supabase, user_ids)

    console.print()
    display_users_preview(cloud_users, assignments, player_history)
    console.print()

    if dry_run:
        console.print("[yellow]DRY RUN - No changes made[/yellow]")
        raise typer.Exit(0)

    console.print("[bold]Syncing users to local...[/bold]\n")

    success_count = 0
    skip_count = 0

    for user in cloud_users:
        user_assignments = assignments.get(user["id"], [])
        user_history = player_history.get(user["id"], [])
        result = sync_user_to_local(
            local_supabase,
            user,
            user_assignments,
            player_history=user_history,
            force=force,
            dry_run=dry_run,
        )
        if result:
            success_count += 1
        else:
            skip_count += 1

    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  [green]Synced: {success_count}[/green]")
    console.print(f"  [yellow]Skipped: {skip_count}[/yellow]")
    console.print("\n[bold green]Done![/bold green]")


@app.command("list-cloud")
def list_cloud(
    from_env: str = typer.Option("prod", "--from", "-f", help="Source environment (prod)"),
    include_all: bool = typer.Option(False, "--include-all", help="Include test users"),
):
    """List users in cloud environment (for preview)."""
    console.print(f"[bold cyan]Cloud Users ({from_env})[/bold cyan]\n")

    _validate_env(from_env)

    cloud_env = load_env_file(from_env)
    cloud_supabase = create_client(
        cloud_env["SUPABASE_URL"],
        cloud_env["SUPABASE_SERVICE_KEY"],
    )

    cloud_users = fetch_users_from_cloud(cloud_supabase, include_all=include_all)
    user_ids = [u["id"] for u in cloud_users]
    assignments = fetch_team_manager_assignments(cloud_supabase, user_ids)
    player_history = fetch_player_team_history(cloud_supabase, user_ids)

    display_users_preview(cloud_users, assignments, player_history)


@app.command("passwords")
def show_passwords():
    """Display the role-to-password mapping."""
    console.print("[bold cyan]Role-Based Password Mapping[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
    table.add_column("Role", style="yellow")
    table.add_column("Password", style="cyan")

    # Deduplicate and sort
    seen = {}
    for role, password in sorted(ROLE_PASSWORDS.items()):
        normalized = role.replace("-", "_")
        if normalized not in seen:
            seen[normalized] = (role, password)

    for role, password in sorted(seen.values(), key=lambda x: x[1]):
        table.add_row(role, password)

    console.print(table)
    console.print("\n[dim]Default password for unknown roles: fan123[/dim]")


if __name__ == "__main__":
    app()

#!/usr/bin/env python3
"""
TSC Test Data Cleanup Tool.

Intelligently finds and removes test entities by prefix (tsc_a_ or tsc_b_).
Uses rich for beautiful output and typer for CLI interface.

Usage:
    # Scan for entities (no deletion)
    cd backend && uv run python -m tests.tsc.utils.cleanup scan --prefix tsc_b_

    # Preview what would be deleted (dry run - default)
    cd backend && uv run python -m tests.tsc.utils.cleanup clean --prefix tsc_b_

    # Actually delete test data
    cd backend && uv run python -m tests.tsc.utils.cleanup clean --prefix tsc_b_ --no-dry-run

    # Clean up both prefixes
    cd backend && uv run python -m tests.tsc.utils.cleanup clean --prefix tsc_a_ --no-dry-run
    cd backend && uv run python -m tests.tsc.utils.cleanup clean --prefix tsc_b_ --no-dry-run
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Add backend to path for imports
backend_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_path))

from api_client import MissingTableClient  # noqa: E402

# Load environment from .env.tsc if it exists
env_file = Path(__file__).parent.parent / ".env.tsc"
if env_file.exists():
    load_dotenv(env_file)

app = typer.Typer(
    name="tsc-cleanup",
    help="Clean up TSC test data by prefix (tsc_a_ or tsc_b_)",
    add_completion=False,
)
console = Console()


@dataclass
class EntityInventory:
    """Tracks entities found for cleanup."""

    seasons: list[dict] = field(default_factory=list)
    age_groups: list[dict] = field(default_factory=list)
    leagues: list[dict] = field(default_factory=list)
    divisions: list[dict] = field(default_factory=list)
    clubs: list[dict] = field(default_factory=list)
    teams: list[dict] = field(default_factory=list)
    matches: list[dict] = field(default_factory=list)
    invitations: list[dict] = field(default_factory=list)
    users: list[dict] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return (
            len(self.seasons)
            + len(self.age_groups)
            + len(self.leagues)
            + len(self.divisions)
            + len(self.clubs)
            + len(self.teams)
            + len(self.matches)
            + len(self.invitations)
            + len(self.users)
        )

    def is_empty(self) -> bool:
        return self.total_count == 0


def find_entities(client: MissingTableClient, prefix: str, verbose: bool = False) -> EntityInventory:
    """Find all entities matching the prefix by querying the API."""
    inventory = EntityInventory()

    if verbose:
        console.print("  [dim]Scanning seasons...[/dim]")
    try:
        seasons = client.get_seasons()
        inventory.seasons = [s for s in seasons if s.get("name", "").startswith(prefix)]
    except Exception as e:
        if verbose:
            console.print(f"  [yellow]Warning: Could not fetch seasons: {e}[/yellow]")

    if verbose:
        console.print("  [dim]Scanning age groups...[/dim]")
    try:
        age_groups = client.get_age_groups()
        inventory.age_groups = [
            ag for ag in age_groups if ag.get("name", "").startswith(prefix)
        ]
    except Exception as e:
        if verbose:
            console.print(f"  [yellow]Warning: Could not fetch age groups: {e}[/yellow]")

    if verbose:
        console.print("  [dim]Scanning leagues...[/dim]")
    try:
        leagues = client.get_leagues()
        inventory.leagues = [lg for lg in leagues if lg.get("name", "").startswith(prefix)]
    except Exception as e:
        if verbose:
            console.print(f"  [yellow]Warning: Could not fetch leagues: {e}[/yellow]")

    if verbose:
        console.print("  [dim]Scanning divisions...[/dim]")
    try:
        divisions = client.get_divisions()
        inventory.divisions = [
            d for d in divisions if d.get("name", "").startswith(prefix)
        ]
    except Exception as e:
        if verbose:
            console.print(f"  [yellow]Warning: Could not fetch divisions: {e}[/yellow]")

    if verbose:
        console.print("  [dim]Scanning clubs...[/dim]")
    try:
        clubs = client.get_clubs()
        inventory.clubs = [c for c in clubs if c.get("name", "").startswith(prefix)]
    except Exception as e:
        if verbose:
            console.print(f"  [yellow]Warning: Could not fetch clubs: {e}[/yellow]")

    if verbose:
        console.print("  [dim]Scanning teams...[/dim]")
    try:
        teams = client.get_teams()
        inventory.teams = [t for t in teams if t.get("name", "").startswith(prefix)]
    except Exception as e:
        if verbose:
            console.print(f"  [yellow]Warning: Could not fetch teams: {e}[/yellow]")

    # Find matches belonging to test teams
    if inventory.teams:
        team_ids = {t["id"] for t in inventory.teams}
        if verbose:
            console.print(f"  [dim]Scanning matches for {len(team_ids)} test teams...[/dim]")
        try:
            matches = client.get_games()
            inventory.matches = [
                m
                for m in matches
                if m.get("home_team_id") in team_ids or m.get("away_team_id") in team_ids
            ]
        except Exception as e:
            if verbose:
                console.print(f"  [yellow]Warning: Could not fetch matches: {e}[/yellow]")

    # Find invitations belonging to test clubs or teams
    if inventory.clubs or inventory.teams:
        club_ids = {c["id"] for c in inventory.clubs}
        team_ids = {t["id"] for t in inventory.teams}
        if verbose:
            console.print("  [dim]Scanning invitations...[/dim]")
        try:
            invites = client.get_my_invites()  # Get all invites created by admin
            inventory.invitations = [
                inv for inv in invites
                if inv.get("club_id") in club_ids or inv.get("team_id") in team_ids
            ]
        except Exception as e:
            if verbose:
                console.print(f"  [yellow]Warning: Could not fetch invitations: {e}[/yellow]")

    # Try to find users by username prefix (requires admin access)
    if verbose:
        console.print("  [dim]Scanning users...[/dim]")
    try:
        users = client.get_users()
        inventory.users = [
            u for u in users if u.get("username", "").startswith(prefix)
        ]
    except Exception:
        # User listing may not be available or user doesn't have permission
        pass

    return inventory


def display_inventory(inventory: EntityInventory, prefix: str) -> None:
    """Display found entities in a nice table."""
    table = Table(title=f"Entities Found with Prefix '[cyan]{prefix}[/cyan]'")
    table.add_column("Entity Type", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Names/IDs", style="dim", max_width=60)

    def format_items(items: list[dict], name_key: str = "name") -> str:
        if not items:
            return "-"
        names = [str(item.get(name_key, item.get("id", "?"))) for item in items[:5]]
        if len(items) > 5:
            names.append(f"... +{len(items) - 5} more")
        return ", ".join(names)

    # Display in deletion order (shows what will be deleted first)
    table.add_row("Matches", str(len(inventory.matches)), format_items(inventory.matches, "id"))
    table.add_row("Invitations", str(len(inventory.invitations)), format_items(inventory.invitations, "id"))
    table.add_row("Teams", str(len(inventory.teams)), format_items(inventory.teams))
    table.add_row("Clubs", str(len(inventory.clubs)), format_items(inventory.clubs))
    table.add_row("Divisions", str(len(inventory.divisions)), format_items(inventory.divisions))
    table.add_row("Leagues", str(len(inventory.leagues)), format_items(inventory.leagues))
    table.add_row("Age Groups", str(len(inventory.age_groups)), format_items(inventory.age_groups))
    table.add_row("Seasons", str(len(inventory.seasons)), format_items(inventory.seasons))
    table.add_row("Users", str(len(inventory.users)), format_items(inventory.users, "username"))

    console.print(table)
    console.print(f"\n[bold]Total entities: {inventory.total_count}[/bold]")


def delete_entities(
    client: MissingTableClient,
    inventory: EntityInventory,
    dry_run: bool = True,
    verbose: bool = False,
) -> dict[str, int]:
    """Delete entities in FK-safe order."""
    results = {
        "matches": 0,
        "invitations": 0,
        "teams": 0,
        "clubs": 0,
        "divisions": 0,
        "leagues": 0,
        "age_groups": 0,
        "seasons": 0,
        "users": 0,
        "errors": 0,
    }

    # Map entity types to their delete methods
    delete_methods = {
        "matches": client.delete_game,
        "invitations": client.cancel_invite,
        "teams": client.delete_team,
        "clubs": client.delete_club,
        "divisions": client.delete_division,
        "leagues": client.delete_league,
        "age_groups": client.delete_age_group,
        "seasons": client.delete_season,
    }

    # FK-safe deletion order (most dependent first)
    # Invitations must be deleted before clubs/teams due to FK constraints
    deletion_order = [
        ("matches", inventory.matches),
        ("invitations", inventory.invitations),
        ("teams", inventory.teams),
        ("clubs", inventory.clubs),
        ("divisions", inventory.divisions),
        ("leagues", inventory.leagues),
        ("age_groups", inventory.age_groups),
        ("seasons", inventory.seasons),
        # Users are typically not auto-deleted for safety
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for entity_type, items in deletion_order:
            if not items:
                continue

            task = progress.add_task(
                f"{'[DRY RUN] ' if dry_run else ''}Deleting {entity_type}...",
                total=len(items),
            )

            delete_fn = delete_methods.get(entity_type)

            for item in items:
                item_id = item.get("id")
                item_name = item.get("name", item.get("username", str(item_id)))

                if dry_run:
                    if verbose:
                        console.print(f"  [dim]Would delete {entity_type[:-1]}: {item_name} (ID: {item_id})[/dim]")
                    results[entity_type] += 1
                else:
                    try:
                        if delete_fn:
                            delete_fn(item_id)
                            results[entity_type] += 1
                            if verbose:
                                console.print(f"  [green]✓[/green] Deleted {entity_type[:-1]}: {item_name}")
                        else:
                            results["errors"] += 1
                            if verbose:
                                console.print(f"  [red]✗[/red] No delete method for {entity_type}")
                    except Exception as e:
                        # Check if it's a "not found" error (already deleted)
                        error_str = str(e).lower()
                        if "not found" in error_str or "404" in error_str:
                            results[entity_type] += 1
                            if verbose:
                                console.print(f"  [dim]Already deleted: {item_name}[/dim]")
                        else:
                            results["errors"] += 1
                            if verbose:
                                console.print(f"  [red]✗[/red] Error deleting {entity_type[:-1]}: {item_name} - {e}")

                progress.advance(task)

    return results


def get_client_config(
    base_url: str | None,
    username: str | None,
    password: str | None,
) -> tuple[str, str, str]:
    """Get client configuration from args or environment."""
    url = base_url or os.getenv("BASE_URL", "http://localhost:8000")
    user = username or os.getenv("TSC_EXISTING_ADMIN_USERNAME", "tom")
    pwd = password or os.getenv("TSC_EXISTING_ADMIN_PASSWORD", "tom123!")
    return url, user, pwd


@app.command()
def clean(
    prefix: str = typer.Option(
        "tsc_b_",
        "--prefix",
        "-p",
        help="Entity name prefix to match (tsc_a_ or tsc_b_)",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        "-d/-D",
        help="Preview without deleting (default: dry run)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output for each entity",
    ),
    base_url: str = typer.Option(
        None,
        "--url",
        "-u",
        help="API base URL (default: from env or http://localhost:8000)",
    ),
    username: str = typer.Option(
        None,
        "--username",
        help="Admin username (default: from TSC_EXISTING_ADMIN_USERNAME env)",
    ),
    password: str = typer.Option(
        None,
        "--password",
        help="Admin password (default: from TSC_EXISTING_ADMIN_PASSWORD env)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Clean up TSC test entities by prefix.

    Finds all entities (seasons, age groups, teams, matches, etc.) that start
    with the given prefix and deletes them in FK-safe order.

    Examples:

        # Preview what tsc_b_ entities would be deleted
        uv run python -m tests.tsc.utils.cleanup clean -p tsc_b_

        # Actually delete tsc_b_ entities
        uv run python -m tests.tsc.utils.cleanup clean -p tsc_b_ --no-dry-run

        # Delete tsc_a_ entities with verbose output
        uv run python -m tests.tsc.utils.cleanup clean -p tsc_a_ -v --no-dry-run
    """
    url, user, pwd = get_client_config(base_url, username, password)

    # Validate prefix
    if not prefix.startswith("tsc_"):
        console.print("[red]Error:[/red] Prefix must start with 'tsc_' (e.g., tsc_a_ or tsc_b_)")
        raise typer.Exit(1)

    # Header
    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[red]LIVE DELETE[/red]"
    console.print(
        Panel(
            f"[bold]TSC Cleanup Tool[/bold]\n"
            f"Mode: {mode}\n"
            f"Prefix: [cyan]{prefix}[/cyan]\n"
            f"URL: [dim]{url}[/dim]",
            title="🧹 TSC Cleanup",
        )
    )

    # Login
    console.print("\n[bold]Step 1:[/bold] Authenticating...")
    client = MissingTableClient(base_url=url)
    try:
        client.login(user, pwd)
        console.print(f"  [green]✓[/green] Logged in as [cyan]{user}[/cyan]")
    except Exception as e:
        console.print(f"  [red]✗[/red] Login failed: {e}")
        raise typer.Exit(1)

    # Find entities
    console.print("\n[bold]Step 2:[/bold] Scanning for entities...")
    inventory = find_entities(client, prefix, verbose=verbose)

    if inventory.is_empty():
        console.print(f"\n[green]✓[/green] No entities found with prefix '{prefix}'. Nothing to clean up!")
        raise typer.Exit(0)

    # Display what was found
    console.print()
    display_inventory(inventory, prefix)

    # Confirm if not dry run and not forced
    if not dry_run and not force:
        console.print()
        confirm = typer.confirm(
            f"Are you sure you want to delete {inventory.total_count} entities?",
            default=False,
        )
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    # Delete
    console.print(f"\n[bold]Step 3:[/bold] {'Previewing' if dry_run else 'Deleting'} entities...")
    results = delete_entities(client, inventory, dry_run=dry_run, verbose=verbose)

    # Summary
    console.print("\n[bold]Summary:[/bold]")
    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("Entity", style="cyan")
    summary_table.add_column("Count", justify="right")

    total_deleted = 0
    for entity_type, count in results.items():
        if entity_type != "errors" and count > 0:
            summary_table.add_row(entity_type.replace("_", " ").title(), str(count))
            total_deleted += count

    if results["errors"] > 0:
        summary_table.add_row("[red]Errors[/red]", f"[red]{results['errors']}[/red]")

    console.print(summary_table)

    if dry_run:
        console.print(
            f"\n[yellow]Dry run complete.[/yellow] Would delete {total_deleted} entities."
        )
        console.print("Run with [bold]--no-dry-run[/bold] to actually delete.")
    else:
        console.print(f"\n[green]✓[/green] Cleanup complete. Deleted {total_deleted} entities.")

    if inventory.users:
        console.print(
            f"\n[yellow]Note:[/yellow] Found {len(inventory.users)} test users. "
            "Users are NOT automatically deleted for safety."
        )


@app.command()
def scan(
    prefix: str = typer.Option(
        "tsc_b_",
        "--prefix",
        "-p",
        help="Entity name prefix to match (tsc_a_ or tsc_b_)",
    ),
    base_url: str = typer.Option(
        None,
        "--url",
        "-u",
        help="API base URL",
    ),
    username: str = typer.Option(
        None,
        "--username",
        help="Admin username",
    ),
    password: str = typer.Option(
        None,
        "--password",
        help="Admin password",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed scan progress",
    ),
) -> None:
    """
    Scan for TSC test entities without deleting.

    Just shows what entities exist with the given prefix.

    Examples:

        # Scan for tsc_b_ entities
        uv run python -m tests.tsc.utils.cleanup scan -p tsc_b_

        # Scan for tsc_a_ entities with verbose output
        uv run python -m tests.tsc.utils.cleanup scan -p tsc_a_ -v
    """
    url, user, pwd = get_client_config(base_url, username, password)

    console.print(
        Panel(
            f"[bold]TSC Entity Scanner[/bold]\n"
            f"Prefix: [cyan]{prefix}[/cyan]\n"
            f"URL: [dim]{url}[/dim]",
            title="🔍 Scan",
        )
    )

    console.print("\nAuthenticating...")
    client = MissingTableClient(base_url=url)
    try:
        client.login(user, pwd)
        console.print(f"[green]✓[/green] Logged in as [cyan]{user}[/cyan]")
    except Exception as e:
        console.print(f"[red]Login failed:[/red] {e}")
        raise typer.Exit(1)

    console.print("\nScanning for entities...")
    inventory = find_entities(client, prefix, verbose=verbose)

    console.print()
    if inventory.is_empty():
        console.print(f"[green]✓[/green] No entities found with prefix '[cyan]{prefix}[/cyan]'")
    else:
        display_inventory(inventory, prefix)


@app.command()
def both(
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        "-d/-D",
        help="Preview without deleting (default: dry run)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
    base_url: str = typer.Option(
        None,
        "--url",
        "-u",
        help="API base URL",
    ),
    username: str = typer.Option(
        None,
        "--username",
        help="Admin username",
    ),
    password: str = typer.Option(
        None,
        "--password",
        help="Admin password",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Clean up BOTH tsc_a_ and tsc_b_ test entities.

    Convenience command to clean up all TSC test data in one go.

    Examples:

        # Preview what would be deleted
        uv run python -m tests.tsc.utils.cleanup both

        # Actually delete both prefixes
        uv run python -m tests.tsc.utils.cleanup both --no-dry-run
    """
    url, user, pwd = get_client_config(base_url, username, password)

    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[red]LIVE DELETE[/red]"
    console.print(
        Panel(
            f"[bold]TSC Cleanup - All Prefixes[/bold]\n"
            f"Mode: {mode}\n"
            f"Prefixes: [cyan]tsc_a_[/cyan] and [cyan]tsc_b_[/cyan]\n"
            f"URL: [dim]{url}[/dim]",
            title="🧹 TSC Full Cleanup",
        )
    )

    # Login once
    console.print("\nAuthenticating...")
    client = MissingTableClient(base_url=url)
    try:
        client.login(user, pwd)
        console.print(f"[green]✓[/green] Logged in as [cyan]{user}[/cyan]")
    except Exception as e:
        console.print(f"[red]Login failed:[/red] {e}")
        raise typer.Exit(1)

    total_entities = 0
    all_results: dict[str, int] = {}

    for prefix in ["tsc_a_", "tsc_b_"]:
        console.print(f"\n[bold]{'='*50}[/bold]")
        console.print(f"[bold]Scanning prefix: [cyan]{prefix}[/cyan][/bold]")
        console.print(f"[bold]{'='*50}[/bold]")

        inventory = find_entities(client, prefix, verbose=verbose)

        if inventory.is_empty():
            console.print(f"[green]✓[/green] No entities found with prefix '{prefix}'")
            continue

        display_inventory(inventory, prefix)
        total_entities += inventory.total_count

        if not dry_run:
            console.print(f"\nDeleting {prefix} entities...")
            results = delete_entities(client, inventory, dry_run=False, verbose=verbose)
            for key, value in results.items():
                all_results[key] = all_results.get(key, 0) + value
        else:
            console.print(f"\n[dim]Would delete {inventory.total_count} entities[/dim]")

    # Final summary
    console.print(f"\n[bold]{'='*50}[/bold]")
    console.print("[bold]Overall Summary[/bold]")
    console.print(f"[bold]{'='*50}[/bold]")

    if dry_run:
        console.print(f"[yellow]Dry run complete.[/yellow] Would delete {total_entities} total entities.")
        console.print("Run with [bold]--no-dry-run[/bold] to actually delete.")
    else:
        total_deleted = sum(v for k, v in all_results.items() if k != "errors")
        console.print(f"[green]✓[/green] Deleted {total_deleted} total entities.")
        if all_results.get("errors", 0) > 0:
            console.print(f"[red]Errors: {all_results['errors']}[/red]")


if __name__ == "__main__":
    app()

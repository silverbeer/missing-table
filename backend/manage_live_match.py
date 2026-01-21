#!/usr/bin/env python3
"""
Live Match Management CLI Tool

This tool helps manage live matches during development and testing.
Works directly with the database via DAOs.

Usage:
    python manage_live_match.py status <match_id>     # Show live match status
    python manage_live_match.py list                  # List all live matches
    python manage_live_match.py clear-events <id>    # Delete all events for a match
    python manage_live_match.py reset <match_id>      # Reset match to pre-live state
"""

import os
import sys
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dao.match_dao import MatchDAO, SupabaseConnection
from dao.match_event_dao import MatchEventDAO

# Initialize Typer app and Rich console
app = typer.Typer(help="Live Match Management CLI Tool")
console = Console()

# Shared connection holder (initialized lazily)
_connection: SupabaseConnection | None = None


def get_connection() -> SupabaseConnection:
    """Get or create shared Supabase connection."""
    global _connection
    if _connection is None:
        _connection = SupabaseConnection()
    return _connection


def load_env():
    """Load environment variables from .env file."""
    env = os.getenv("APP_ENV", "local")
    backend_dir = Path(__file__).parent
    env_file = backend_dir / f".env.{env}"

    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, value = line.strip().split("=", 1)
                    os.environ.setdefault(key, value)


# Load environment on module import
load_env()


@app.command()
def status(match_id: int = typer.Argument(..., help="Match ID to check")):
    """Show the current status of a live match."""
    conn = get_connection()
    match_dao = MatchDAO(conn)
    event_dao = MatchEventDAO(conn)

    # Get match details
    match = match_dao.get_match_by_id(match_id)
    if not match:
        console.print(f"[red]❌ Match {match_id} not found[/red]")
        raise typer.Exit(code=1)

    # Get event count
    event_count = event_dao.get_events_count(match_id)

    # Create status table
    table = Table(title=f"Live Match #{match_id}", box=box.ROUNDED)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    # Match info
    table.add_row("Status", match.get("match_status", "N/A"))
    table.add_row("Home Team", f"{match.get('home_team_name', 'N/A')} (ID: {match.get('home_team_id')})")
    table.add_row("Away Team", f"{match.get('away_team_name', 'N/A')} (ID: {match.get('away_team_id')})")
    table.add_row("Score", f"{match.get('home_score', 0)} - {match.get('away_score', 0)}")
    table.add_row("Half Duration", f"{match.get('half_duration', 45)} minutes")
    table.add_row("Match Date", str(match.get("match_date", "N/A")))

    # Clock timestamps
    table.add_row("", "")  # Spacer
    table.add_row("[bold]Clock Timestamps[/bold]", "")
    table.add_row("Kickoff Time", str(match.get("kickoff_time") or "Not started"))
    table.add_row("Halftime Start", str(match.get("halftime_start") or "-"))
    table.add_row("Second Half Start", str(match.get("second_half_start") or "-"))
    table.add_row("Match End Time", str(match.get("match_end_time") or "-"))

    # Events
    table.add_row("", "")  # Spacer
    table.add_row("[bold]Events[/bold]", "")
    table.add_row("Total Events", str(event_count))

    console.print(table)


@app.command("list")
def list_live(
    all_: bool = typer.Option(False, "--all", "-a", help="Show matches with live data OR completed status"),
    status: str = typer.Option(None, "--status", "-s", help="Filter by status (live, completed, scheduled)"),
):
    """List matches by status. Default shows only live matches."""
    conn = get_connection()
    match_dao = MatchDAO(conn)

    if all_ or status:
        # Build query for matches
        query = conn.client.table("matches").select("""
                id,
                match_status,
                match_date,
                home_score,
                away_score,
                kickoff_time,
                home_team:teams!matches_home_team_id_fkey(id, name),
                away_team:teams!matches_away_team_id_fkey(id, name)
            """)

        if status:
            # Filter by specific status
            query = query.eq("match_status", status)
            title = f"Matches with status '{status}'"
        else:
            # Show live or completed or those with kickoff_time
            query = query.or_("match_status.eq.live,match_status.eq.completed,kickoff_time.not.is.null")
            title = "Live & Completed Matches (recent 20)"

        response = query.order("id", desc=True).limit(20).execute()

        # Flatten the response
        matches = []
        for match in response.data or []:
            matches.append(
                {
                    "match_id": match["id"],
                    "match_status": match["match_status"],
                    "match_date": match["match_date"],
                    "home_score": match["home_score"],
                    "away_score": match["away_score"],
                    "kickoff_time": match["kickoff_time"],
                    "home_team_name": match["home_team"]["name"] if match.get("home_team") else "N/A",
                    "away_team_name": match["away_team"]["name"] if match.get("away_team") else "N/A",
                }
            )
    else:
        # Get only currently live matches
        matches = match_dao.get_live_matches()
        title = "Live Matches"

    if not matches:
        console.print("[yellow]No matches found[/yellow]")
        return

    table = Table(title=title, box=box.ROUNDED)
    table.add_column("ID", style="cyan")
    table.add_column("Home", style="white")
    table.add_column("Away", style="white")
    table.add_column("Score", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Kickoff", style="white")

    for match in matches:
        score = f"{match.get('home_score', 0)} - {match.get('away_score', 0)}"
        kickoff = match.get("kickoff_time") or "Not started"
        if kickoff and kickoff != "Not started":
            # Format timestamp for display
            kickoff = str(kickoff)[:19]  # Truncate to seconds

        # get_live_matches returns match_id instead of id
        match_id = match.get("match_id") or match.get("id")
        table.add_row(
            str(match_id),
            match.get("home_team_name", "N/A"),
            match.get("away_team_name", "N/A"),
            score,
            match.get("match_status", "N/A"),
            str(kickoff),
        )

    console.print(table)


@app.command("clear-events")
def clear_events(
    match_id: int = typer.Argument(..., help="Match ID to clear events for"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete all events for a match (goals, messages, status changes)."""
    conn = get_connection()
    match_dao = MatchDAO(conn)
    event_dao = MatchEventDAO(conn)

    # Verify match exists
    match = match_dao.get_match_by_id(match_id)
    if not match:
        console.print(f"[red]❌ Match {match_id} not found[/red]")
        raise typer.Exit(code=1)

    # Get event count
    event_count = event_dao.get_events_count(match_id)

    if event_count == 0:
        console.print(f"[yellow]No events found for match {match_id}[/yellow]")
        return

    console.print(f"[cyan]Match:[/cyan] {match.get('home_team_name')} vs {match.get('away_team_name')}")
    console.print(f"[cyan]Events to delete:[/cyan] {event_count}")

    if not force and not Confirm.ask("Are you sure you want to delete all events?"):
        console.print("[yellow]Cancelled[/yellow]")
        return

    # Delete all events for this match (hard delete for testing)
    try:
        response = event_dao.client.table("match_events").delete().eq("match_id", match_id).execute()
        deleted = len(response.data) if response.data else 0
        console.print(f"[green]✓ Deleted {deleted} events[/green]")
    except Exception as e:
        console.print(f"[red]❌ Error deleting events: {e}[/red]")
        raise typer.Exit(code=1) from e


@app.command()
def reset(
    match_id: int = typer.Argument(..., help="Match ID to reset"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Reset a match to pre-live state (clears events and resets clock/score)."""
    conn = get_connection()
    match_dao = MatchDAO(conn)
    event_dao = MatchEventDAO(conn)

    # Verify match exists
    match = match_dao.get_match_by_id(match_id)
    if not match:
        console.print(f"[red]❌ Match {match_id} not found[/red]")
        raise typer.Exit(code=1)

    event_count = event_dao.get_events_count(match_id)

    console.print(f"[cyan]Match:[/cyan] {match.get('home_team_name')} vs {match.get('away_team_name')}")
    console.print(f"[cyan]Current status:[/cyan] {match.get('match_status')}")
    console.print(f"[cyan]Current score:[/cyan] {match.get('home_score', 0)} - {match.get('away_score', 0)}")
    console.print(f"[cyan]Events to delete:[/cyan] {event_count}")
    console.print()
    console.print("[yellow]This will:[/yellow]")
    console.print("  - Delete all match events (goals, messages)")
    console.print("  - Reset score to 0-0")
    console.print("  - Clear all clock timestamps")
    console.print("  - Set match status to 'scheduled'")

    if not force and not Confirm.ask("Are you sure you want to reset this match?"):
        console.print("[yellow]Cancelled[/yellow]")
        return

    # Delete all events
    try:
        if event_count > 0:
            response = event_dao.client.table("match_events").delete().eq("match_id", match_id).execute()
            deleted = len(response.data) if response.data else 0
            console.print(f"[green]✓ Deleted {deleted} events[/green]")
    except Exception as e:
        console.print(f"[red]❌ Error deleting events: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Reset match fields
    try:
        response = (
            match_dao.client.table("matches")
            .update(
                {
                    "match_status": "scheduled",
                    "home_score": None,
                    "away_score": None,
                    "kickoff_time": None,
                    "halftime_start": None,
                    "second_half_start": None,
                    "match_end_time": None,
                    "half_duration": 45,  # Reset to default
                }
            )
            .eq("id", match_id)
            .execute()
        )

        if response.data:
            console.print("[green]✓ Reset match clock and score[/green]")
            console.print(f"[green]✓ Match {match_id} fully reset[/green]")
        else:
            console.print("[red]❌ Failed to update match[/red]")
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[red]❌ Error resetting match: {e}[/red]")
        raise typer.Exit(code=1) from e


@app.command("set-live")
def set_live(
    match_id: int = typer.Argument(..., help="Match ID to set as live"),
):
    """Set a match status to 'live' without starting the clock."""
    conn = get_connection()
    match_dao = MatchDAO(conn)

    # Verify match exists
    match = match_dao.get_match_by_id(match_id)
    if not match:
        console.print(f"[red]❌ Match {match_id} not found[/red]")
        raise typer.Exit(code=1)

    if match.get("match_status") == "live":
        console.print(f"[yellow]Match {match_id} is already live[/yellow]")
        return

    try:
        response = match_dao.client.table("matches").update({"match_status": "live"}).eq("id", match_id).execute()

        if response.data:
            console.print(f"[green]✓ Match {match_id} set to live[/green]")
        else:
            console.print("[red]❌ Failed to update match[/red]")
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(code=1) from e


@app.command("find-with-events")
def find_with_events():
    """Find all matches that have events (for cleanup)."""
    conn = get_connection()

    # Direct query to find matches with events
    try:
        # Get distinct match_ids from match_events
        events_response = conn.client.table("match_events").select("match_id").execute()

        if not events_response.data:
            console.print("[yellow]No matches with events found[/yellow]")
            return

        # Get unique match IDs and count events
        from collections import Counter

        match_counts = Counter(e["match_id"] for e in events_response.data)

        if not match_counts:
            console.print("[yellow]No matches with events found[/yellow]")
            return

        # Get match details for these IDs
        match_ids = list(match_counts.keys())
        matches_response = (
            conn.client.table("matches")
            .select("""
                id,
                match_status,
                match_date,
                home_team:teams!matches_home_team_id_fkey(name),
                away_team:teams!matches_away_team_id_fkey(name)
            """)
            .in_("id", match_ids)
            .execute()
        )

        table = Table(title="Matches With Events", box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("Home", style="white")
        table.add_column("Away", style="white")
        table.add_column("Status", style="yellow")
        table.add_column("Events", style="green")

        for match in matches_response.data or []:
            match_id = match["id"]
            table.add_row(
                str(match_id),
                match["home_team"]["name"] if match.get("home_team") else "N/A",
                match["away_team"]["name"] if match.get("away_team") else "N/A",
                match.get("match_status", "N/A"),
                str(match_counts.get(match_id, 0)),
            )

        console.print(table)
        console.print()
        console.print("[dim]To clear events: manage_live_match.py clear-events <ID>[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(code=1) from e


if __name__ == "__main__":
    app()

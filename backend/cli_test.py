#!/usr/bin/env python3
"""
CLI testing tool for Missing Table backend API.

A beautiful, type-safe CLI for ad-hoc testing of the backend API using Typer and Rich.

Examples:
    # Health check
    uv run python cli_test.py health

    # List matches with filters
    uv run python cli_test.py matches list --search "IFA" --limit 10
    uv run python cli_test.py matches list --season-id 1 --age-group-id 3
    uv run python cli_test.py matches get 123

    # List teams
    uv run python cli_test.py teams list --search "Academy"
    uv run python cli_test.py teams get 42

    # Reference data
    uv run python cli_test.py ref seasons
    uv run python cli_test.py ref age-groups
    uv run python cli_test.py ref divisions

    # Login and test authenticated endpoints
    uv run python cli_test.py auth login -u tom -p admin123
    uv run python cli_test.py auth profile

    # Use different environments
    uv run python cli_test.py -b https://dev.missingtable.com matches list
"""

from datetime import datetime
from typing import Optional
import json
import sys
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.json import JSON
from rich import print as rprint

from api_client.client import MissingTableClient
from api_client.exceptions import APIError

# Initialize
app = typer.Typer(
    name="cli-test",
    help="🧪 CLI testing tool for Missing Table backend API",
    add_completion=False,
)
console = Console()

# Global state for authenticated client and configuration
_client: Optional[MissingTableClient] = None
_base_url: str = "http://localhost:8000"

# Token storage path
TOKEN_FILE = Path.home() / ".missing-table" / "cli-token.json"


def save_token(access_token: str, refresh_token: str, base_url: str):
    """Save authentication token to file."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    token_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "base_url": base_url
    }
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    TOKEN_FILE.chmod(0o600)  # Secure the file


def load_token(base_url: str) -> Optional[tuple[str, str]]:
    """Load authentication token from file if it matches the base_url."""
    if not TOKEN_FILE.exists():
        return None

    try:
        token_data = json.loads(TOKEN_FILE.read_text())
        # Only use token if it's for the same base_url
        if token_data.get("base_url") == base_url:
            return (token_data.get("access_token"), token_data.get("refresh_token"))
    except Exception:
        pass

    return None


def clear_token():
    """Clear saved authentication token."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()


@app.callback()
def main_callback(
    base_url: str = typer.Option(
        "http://localhost:8000",
        "--base-url",
        "-b",
        help="API base URL",
        envvar="BACKEND_URL",
    ),
):
    """🧪 CLI testing tool for Missing Table backend API"""
    global _base_url
    _base_url = base_url


def get_client(base_url: Optional[str] = None) -> MissingTableClient:
    """Get or create API client with saved token if available."""
    global _client, _base_url
    url = base_url or _base_url

    if _client is None or _client.base_url != url:
        # Try to load saved token
        token_info = load_token(url)
        if token_info:
            access_token, refresh_token = token_info
            _client = MissingTableClient(base_url=url, access_token=access_token)
            _client._refresh_token = refresh_token
        else:
            _client = MissingTableClient(base_url=url)

    return _client


def format_date(date_str: str) -> str:
    """Format date string for display."""
    if not date_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except:
        return date_str


def get_season_id_by_name(client: MissingTableClient, name: str) -> Optional[int]:
    """Get season ID by name."""
    seasons = client.get_seasons()
    for season in seasons:
        if season.get('name', '').lower() == name.lower():
            return season.get('id')
    return None


def get_age_group_id_by_name(client: MissingTableClient, name: str) -> Optional[int]:
    """Get age group ID by name."""
    age_groups = client.get_age_groups()
    for ag in age_groups:
        if ag.get('name', '').lower() == name.lower():
            return ag.get('id')
    return None


def get_team_id_by_name(client: MissingTableClient, name: str) -> Optional[int]:
    """Get team ID by name (supports partial matching)."""
    teams = client.get_teams()
    name_lower = name.lower()

    # First try exact match
    for team in teams:
        if team.get('name', '').lower() == name_lower:
            return team.get('id')

    # Then try partial match (case-insensitive)
    matches = []
    for team in teams:
        if name_lower in team.get('name', '').lower():
            matches.append(team)

    if len(matches) == 1:
        return matches[0].get('id')
    elif len(matches) > 1:
        console.print(f"[yellow]Multiple teams found matching '{name}':[/yellow]")
        for team in matches[:5]:  # Show first 5 matches
            console.print(f"  - {team.get('name')}")
        console.print(f"[yellow]Please be more specific.[/yellow]")
        return None

    return None


def get_game_type_id_by_name(client: MissingTableClient, name: str) -> Optional[int]:
    """Get game type ID by name."""
    game_types = client.get_game_types()
    for gt in game_types:
        if gt.get('name', '').lower() == name.lower():
            return gt.get('id')
    return None


def handle_error(e: Exception, verbose: bool = False):
    """Handle and display errors nicely."""
    if isinstance(e, APIError):
        console.print(f"[bold red]API Error ({e.status_code}): {e.message}[/bold red]")

        # Special handling for authentication errors
        if e.status_code == 403 and "not authenticated" in e.message.lower():
            console.print("\n[yellow]🔐 You need to login first![/yellow]")
            console.print("[dim]Run:[/dim] [cyan]uv run python cli_test.py auth login -u <username> -p <password>[/cyan]")
        elif e.status_code == 401:
            console.print("\n[yellow]⏰ Your session has expired or token is invalid![/yellow]")
            console.print("[dim]Please login again:[/dim] [cyan]uv run python cli_test.py auth login -u <username> -p <password>[/cyan]")

        if verbose and e.details:
            console.print("\n[dim]Error details:[/dim]")
            console.print(JSON(json.dumps(e.details)))
    else:
        console.print(f"[bold red]Error: {e}[/bold red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())


# ============================================================================
# Health Commands
# ============================================================================

@app.command()
def health(
    full: bool = typer.Option(False, "--full", "-f", help="Run full health check"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """🏥 Check API health status."""
    try:
        client = get_client()

        if full:
            console.print("[cyan]Running full health check...[/cyan]\n")
            result = client.full_health_check()
        else:
            console.print("[cyan]Running basic health check...[/cyan]\n")
            result = client.health_check()

        # Display results
        status = result.get('status', 'unknown')
        status_color = "green" if status == "healthy" else "red"

        console.print(Panel(
            f"[{status_color}]Status: {status.upper()}[/{status_color}]",
            title="Health Check Results",
            border_style=status_color,
        ))

        if verbose or full:
            console.print("\n[bold]Full Response:[/bold]")
            console.print(JSON(json.dumps(result, indent=2)))

    except Exception as e:
        handle_error(e, verbose)
        raise typer.Exit(1)


# ============================================================================
# Matches Commands
# ============================================================================

matches_app = typer.Typer(help="🎮 Manage and query matches")
app.add_typer(matches_app, name="matches")


@matches_app.command("list")
def list_matches(
    season: Optional[str] = typer.Option(None, "--season", "-s", help="Season name or ID"),
    age_group: Optional[str] = typer.Option(None, "--age-group", "-a", help="Age group name or ID"),
    game_type: Optional[str] = typer.Option(None, "--game-type", "-g", help="Game type name or ID"),
    team: Optional[str] = typer.Option(None, "--team", "-t", help="Team name or ID"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l"),
    upcoming: bool = typer.Option(False, "--upcoming", help="Show only upcoming matches"),
    search: Optional[str] = typer.Option(None, "--search", help="Search team names"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """📋 List matches with optional filters.

    You can filter by name or ID for season, age group, game type, and team.
    Examples:
        --season "2025-2026" or --season 1
        --age-group U14 or --age-group 3
        --team IFA or --team 42
    """
    try:
        client = get_client()

        # Resolve names to IDs
        season_id = None
        age_group_id = None
        game_type_id = None
        team_id = None

        if season:
            # Try to parse as int, otherwise lookup by name
            try:
                season_id = int(season)
            except ValueError:
                season_id = get_season_id_by_name(client, season)
                if season_id is None:
                    console.print(f"[red]Season '{season}' not found[/red]")
                    raise typer.Exit(1)

        if age_group:
            try:
                age_group_id = int(age_group)
            except ValueError:
                age_group_id = get_age_group_id_by_name(client, age_group)
                if age_group_id is None:
                    console.print(f"[red]Age group '{age_group}' not found[/red]")
                    raise typer.Exit(1)

        # Note: Backend expects match_type as name, not ID
        match_type_name = None
        if game_type:
            # Validate that the game type exists
            try:
                # If it's an integer, look up the name
                game_type_id = int(game_type)
                game_types = client.get_game_types()
                for gt in game_types:
                    if gt.get('id') == game_type_id:
                        match_type_name = gt.get('name')
                        break
                if match_type_name is None:
                    console.print(f"[red]Game type ID '{game_type}' not found[/red]")
                    raise typer.Exit(1)
            except ValueError:
                # It's a name, validate it exists
                game_type_id = get_game_type_id_by_name(client, game_type)
                if game_type_id is None:
                    console.print(f"[red]Game type '{game_type}' not found[/red]")
                    raise typer.Exit(1)
                match_type_name = game_type

        if team:
            try:
                team_id = int(team)
            except ValueError:
                team_id = get_team_id_by_name(client, team)
                if team_id is None:
                    console.print(f"[red]Team '{team}' not found or ambiguous[/red]")
                    raise typer.Exit(1)

        # Show filters being applied
        if verbose:
            filters = []
            if season_id: filters.append(f"season_id={season_id}")
            if age_group_id: filters.append(f"age_group_id={age_group_id}")
            if match_type_name: filters.append(f"match_type={match_type_name}")
            if team_id: filters.append(f"team_id={team_id}")
            if limit: filters.append(f"limit={limit}")
            if upcoming: filters.append("upcoming=true")
            if search: filters.append(f"search={search}")

            if filters:
                console.print(f"[dim]Applying filters: {', '.join(filters)}[/dim]\n")

        # Fetch matches - use direct HTTP request since client method might not match API
        params = {}
        if season_id is not None:
            params["season_id"] = season_id
        if age_group_id is not None:
            params["age_group_id"] = age_group_id
        if match_type_name is not None:
            params["match_type"] = match_type_name
        if team_id is not None:
            params["team_id"] = team_id
        if limit is not None:
            params["limit"] = limit
        if upcoming:
            params["upcoming"] = upcoming

        response = client._request("GET", "/api/matches", params=params)
        matches = response.json()

        # Filter by search term if provided
        if search:
            search_lower = search.lower()
            matches = [
                m for m in matches
                if search_lower in str(m.get('home_team_name', '')).lower()
                or search_lower in str(m.get('away_team_name', '')).lower()
            ]

        # Sort by match_date ascending (oldest first, most recent last)
        matches = sorted(matches, key=lambda m: m.get('match_date', ''))

        # Output
        if json_output:
            console.print(JSON(json.dumps(matches, indent=2)))
            return

        if not matches:
            console.print("[yellow]No matches found[/yellow]")
            return

        # Display matches in table
        table = Table(title=f"Matches ({len(matches)} found)", show_header=True, show_lines=False)
        table.add_column("MT ID", style="cyan", no_wrap=True)
        table.add_column("MLS ID", style="dim cyan", no_wrap=True)
        table.add_column("Date", style="magenta", no_wrap=True)
        table.add_column("Home Team", style="green")
        table.add_column("Away Team", style="blue")
        table.add_column("Score", justify="center", no_wrap=True)
        table.add_column("Result", justify="center", no_wrap=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("Season", no_wrap=True)
        table.add_column("Age", no_wrap=True)

        for match in matches:
            match_id = str(match.get('id', ''))
            external_match_id = match.get('match_id') or match.get('external_match_id') or '-'
            external_match_id_str = str(external_match_id) if external_match_id != '-' else '[dim]-[/dim]'
            date = format_date(match.get('match_date'))  # Fixed: was 'game_date', should be 'match_date'
            home_team = match.get('home_team_name', 'Unknown')
            away_team = match.get('away_team_name', 'Unknown')
            home_team_id = match.get('home_team_id')
            away_team_id = match.get('away_team_id')
            home_score = match.get('home_score')
            away_score = match.get('away_score')

            # Format score
            score_home = home_score if home_score is not None else '-'
            score_away = away_score if away_score is not None else '-'
            score = f"{score_home} - {score_away}"

            status = match.get('match_status', 'N/A')  # Get status early for result calculation

            # Calculate result (only for completed matches)
            result = "-"
            if status == 'completed' and home_score is not None and away_score is not None:
                # Determine which team's perspective to show
                if team_id is not None:
                    # Show result from filtered team's perspective
                    if home_team_id == team_id:
                        # Filtered team is home
                        if home_score > away_score:
                            result = "[bold green]W[/bold green]"
                        elif home_score < away_score:
                            result = "[bold red]L[/bold red]"
                        else:
                            result = "[yellow]D[/yellow]"
                    elif away_team_id == team_id:
                        # Filtered team is away
                        if away_score > home_score:
                            result = "[bold green]W[/bold green]"
                        elif away_score < home_score:
                            result = "[bold red]L[/bold red]"
                        else:
                            result = "[yellow]D[/yellow]"
                else:
                    # No team filter, show from home team's perspective
                    if home_score > away_score:
                        result = "[bold green]W[/bold green]"
                    elif home_score < away_score:
                        result = "[bold red]L[/bold red]"
                    else:
                        result = "[yellow]D[/yellow]"

            season_name = match.get('season_name', 'N/A')
            age_group = match.get('age_group_name', 'N/A')

            # Color status
            if status == 'completed':
                status_display = f"[green]{status}[/green]"
            elif status == 'scheduled':
                status_display = f"[yellow]{status}[/yellow]"
            elif status == 'live':
                status_display = f"[bold cyan]{status}[/bold cyan]"
            elif status == 'tbd':
                status_display = f"[dim yellow]{status}[/dim yellow]"
            else:
                status_display = status

            table.add_row(match_id, external_match_id_str, date, home_team, away_team, score, result, status_display, season_name, age_group)

        console.print(table)

        # Summary stats
        if verbose:
            teams = set()
            for m in matches:
                teams.add(m.get('home_team_name'))
                teams.add(m.get('away_team_name'))
            console.print(f"\n[dim]Total: {len(matches)} matches, {len(teams)} unique teams[/dim]")

    except Exception as e:
        handle_error(e, verbose)
        raise typer.Exit(1)


@matches_app.command("get")
def get_match(
    match_id: int = typer.Argument(..., help="Match ID"),
    json_output: bool = typer.Option(False, "--json"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """🔍 Get specific match by ID."""
    try:
        client = get_client()
        console.print(f"[cyan]Fetching match {match_id}...[/cyan]\n")

        response = client._request("GET", f"/api/matches/{match_id}")
        match = response.json()

        if json_output:
            console.print(JSON(json.dumps(match, indent=2)))
            return

        # Display match details
        panel_content = f"""
[bold]Match ID:[/bold] {match.get('id')}
[bold]Date:[/bold] {format_date(match.get('match_date'))}
[bold]Status:[/bold] {match.get('match_status', 'N/A')}

[bold cyan]Home Team:[/bold cyan] {match.get('home_team_name', 'Unknown')}
[bold blue]Away Team:[/bold blue] {match.get('away_team_name', 'Unknown')}
[bold]Score:[/bold] {match.get('home_score', '-')} - {match.get('away_score', '-')}

[bold]Season:[/bold] {match.get('season_name', 'N/A')}
[bold]Age Group:[/bold] {match.get('age_group_name', 'N/A')}
[bold]Division:[/bold] {match.get('division_name', 'N/A')}
[bold]Match Type:[/bold] {match.get('match_type_name', 'N/A')}
"""

        console.print(Panel(panel_content.strip(), title="Match Details", border_style="green"))

        if verbose:
            console.print("\n[bold]Full Data:[/bold]")
            console.print(JSON(json.dumps(match, indent=2)))

    except Exception as e:
        handle_error(e, verbose)
        raise typer.Exit(1)


@matches_app.command("edit")
def edit_match(
    match_id: int = typer.Argument(..., help="Match ID to edit"),
    home_score: Optional[int] = typer.Option(None, "--home-score", help="Update home team score"),
    away_score: Optional[int] = typer.Option(None, "--away-score", help="Update away team score"),
    status: Optional[str] = typer.Option(None, "--status", help="Update match status (scheduled, live, completed, postponed, cancelled)"),
    match_date: Optional[str] = typer.Option(None, "--date", help="Update match date (YYYY-MM-DD)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """✏️  Edit/update a match by ID.

    Examples:
        # Update scores
        cli_test.py matches edit 123 --home-score 2 --away-score 1

        # Update status
        cli_test.py matches edit 123 --status completed

        # Update scores and status together
        cli_test.py matches edit 123 --home-score 3 --away-score 2 --status completed

        # Update match date
        cli_test.py matches edit 123 --date 2025-11-15
    """
    try:
        client = get_client()

        # Check if any updates were provided
        if not any([home_score is not None, away_score is not None, status, match_date]):
            console.print("[red]❌ Error: No updates specified. Use --home-score, --away-score, --status, or --date[/red]")
            raise typer.Exit(1)

        # First, get the match details to show what's being updated
        console.print(f"[cyan]Fetching match {match_id}...[/cyan]\n")
        response = client._request("GET", f"/api/matches/{match_id}")
        match = response.json()

        # Display current match info
        console.print(Panel(
            f"[bold]Current Match:[/bold]\n"
            f"ID: {match.get('id')}\n"
            f"Date: {format_date(match.get('match_date'))}\n"
            f"Teams: {match.get('home_team_name')} vs {match.get('away_team_name')}\n"
            f"Score: {match.get('home_score', '-')} - {match.get('away_score', '-')}\n"
            f"Status: {match.get('match_status')}\n"
            f"Age Group: {match.get('age_group_name')}",
            title="Match Details",
            border_style="blue"
        ))

        # Build update payload
        update_data = {}

        if home_score is not None:
            update_data["home_score"] = home_score
        if away_score is not None:
            update_data["away_score"] = away_score
        if status:
            # Validate status
            valid_statuses = ["scheduled", "live", "completed", "postponed", "cancelled", "tbd"]
            if status not in valid_statuses:
                console.print(f"[red]❌ Invalid status '{status}'. Valid options: {', '.join(valid_statuses)}[/red]")
                raise typer.Exit(1)
            update_data["match_status"] = status
        if match_date:
            # Basic date format validation
            try:
                from datetime import datetime
                datetime.strptime(match_date, '%Y-%m-%d')
                update_data["match_date"] = match_date
            except ValueError:
                console.print("[red]❌ Invalid date format. Use YYYY-MM-DD (e.g., 2025-11-15)[/red]")
                raise typer.Exit(1)

        # Show what will be updated
        console.print("\n[bold yellow]Updates to apply:[/bold yellow]")
        for key, value in update_data.items():
            console.print(f"  • {key}: [cyan]{value}[/cyan]")

        # Confirm update
        confirm = typer.confirm("\nProceed with update?")
        if not confirm:
            console.print("[yellow]Update cancelled.[/yellow]")
            return

        # Update the match
        console.print(f"\n[cyan]Updating match {match_id}...[/cyan]")
        update_response = client._request("PATCH", f"/api/matches/{match_id}", json_data=update_data)
        updated_match = update_response.json()

        console.print("[bold green]✓ Match updated successfully![/bold green]\n")

        # Display updated match
        console.print(Panel(
            f"[bold]Updated Match:[/bold]\n"
            f"ID: {updated_match.get('id')}\n"
            f"Date: {format_date(updated_match.get('match_date'))}\n"
            f"Teams: {updated_match.get('home_team_name')} vs {updated_match.get('away_team_name')}\n"
            f"Score: {updated_match.get('home_score', '-')} - {updated_match.get('away_score', '-')}\n"
            f"Status: {updated_match.get('match_status')}\n"
            f"Age Group: {updated_match.get('age_group_name')}",
            title="✓ Updated Match Details",
            border_style="green"
        ))

        if verbose:
            console.print("\n[bold]Full Updated Data:[/bold]")
            console.print(JSON(json.dumps(updated_match, indent=2)))

    except Exception as e:
        handle_error(e, verbose)
        raise typer.Exit(1)


@matches_app.command("delete")
def delete_match(
    match_id: int = typer.Argument(..., help="Match ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """🗑️  Delete a match by ID."""
    try:
        client = get_client()

        # First, get the match details
        console.print(f"[cyan]Fetching match {match_id}...[/cyan]\n")
        response = client._request("GET", f"/api/matches/{match_id}")
        match = response.json()

        # Display what will be deleted
        console.print(Panel(
            f"[bold red]Match to DELETE:[/bold red]\n"
            f"ID: {match.get('id')}\n"
            f"Date: {format_date(match.get('match_date'))}\n"
            f"Teams: {match.get('home_team_name')} vs {match.get('away_team_name')}\n"
            f"Age Group: {match.get('age_group_name')}\n"
            f"Status: {match.get('match_status')}\n"
            f"Source: {match.get('source', 'unknown')}\n"
            f"External ID: {match.get('match_id', 'N/A')}",
            title="⚠️  Confirm Deletion",
            border_style="red"
        ))

        # Confirm deletion
        if not force:
            confirm = typer.confirm("\nAre you sure you want to delete this match?")
            if not confirm:
                console.print("[yellow]Deletion cancelled.[/yellow]")
                return

        # Delete the match
        console.print(f"\n[red]Deleting match {match_id}...[/red]")
        delete_response = client._request("DELETE", f"/api/matches/{match_id}")

        if delete_response.status_code == 204 or delete_response.status_code == 200:
            console.print(f"[bold green]✓ Match {match_id} deleted successfully![/bold green]")
        else:
            console.print(f"[bold red]✗ Failed to delete match. Status: {delete_response.status_code}[/bold red]")
            if verbose:
                console.print(delete_response.text)

    except Exception as e:
        handle_error(e, verbose)
        raise typer.Exit(1)


# ============================================================================
# Teams Commands
# ============================================================================

teams_app = typer.Typer(help="👥 Manage and query teams")
app.add_typer(teams_app, name="teams")


@teams_app.command("list")
def list_teams(
    game_type_id: Optional[int] = typer.Option(None, "--game-type-id", "-g"),
    age_group_id: Optional[int] = typer.Option(None, "--age-group-id", "-a"),
    search: Optional[str] = typer.Option(None, "--search", help="Search team names"),
    json_output: bool = typer.Option(False, "--json"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """📋 List all teams."""
    try:
        client = get_client()

        teams = client.get_teams(game_type_id=game_type_id, age_group_id=age_group_id)

        # Filter by search
        if search:
            search_lower = search.lower()
            teams = [t for t in teams if search_lower in str(t.get('name', '')).lower()]

        if json_output:
            console.print(JSON(json.dumps(teams, indent=2)))
            return

        if not teams:
            console.print("[yellow]No teams found[/yellow]")
            return

        # Display teams
        table = Table(title=f"Teams ({len(teams)} found)")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Name", style="green", width=40)
        table.add_column("City", style="blue", width=20)
        table.add_column("Age Groups", width=20)

        for team in teams:
            team_id = str(team.get('id', ''))
            name = team.get('name', 'Unknown')
            city = team.get('city', 'N/A')
            age_groups = ', '.join(str(ag) for ag in team.get('age_group_ids', []))

            table.add_row(team_id, name, city, age_groups)

        console.print(table)

    except Exception as e:
        handle_error(e, verbose)
        raise typer.Exit(1)


@teams_app.command("get")
def get_team(
    team_id: int = typer.Argument(..., help="Team ID"),
    json_output: bool = typer.Option(False, "--json"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """🔍 Get specific team by ID."""
    try:
        client = get_client()
        team = client.get_team(team_id)

        if json_output:
            console.print(JSON(json.dumps(team, indent=2)))
            return

        panel_content = f"""
[bold]Team ID:[/bold] {team.get('id')}
[bold]Name:[/bold] {team.get('name', 'Unknown')}
[bold]City:[/bold] {team.get('city', 'N/A')}
[bold]Age Groups:[/bold] {', '.join(str(ag) for ag in team.get('age_group_ids', []))}
"""

        console.print(Panel(panel_content.strip(), title="Team Details", border_style="green"))

        if verbose:
            console.print("\n[bold]Full Data:[/bold]")
            console.print(JSON(json.dumps(team, indent=2)))

    except Exception as e:
        handle_error(e, verbose)
        raise typer.Exit(1)


# ============================================================================
# Reference Data Commands
# ============================================================================

ref_app = typer.Typer(help="📚 Query reference data")
app.add_typer(ref_app, name="ref")


@ref_app.command("seasons")
def list_seasons(
    current: bool = typer.Option(False, "--current", help="Show only current season"),
    active: bool = typer.Option(False, "--active", help="Show only active seasons"),
    json_output: bool = typer.Option(False, "--json"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """📅 List seasons."""
    try:
        client = get_client()

        if current:
            seasons = [client.get_current_season()]
        elif active:
            seasons = client.get_active_seasons()
        else:
            seasons = client.get_seasons()

        if json_output:
            console.print(JSON(json.dumps(seasons, indent=2)))
            return

        table = Table(title="Seasons")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Name", style="green", width=30)
        table.add_column("Start Date", width=15)
        table.add_column("End Date", width=15)
        table.add_column("Current", justify="center", width=10)

        for season in seasons:
            season_id = str(season.get('id', ''))
            name = season.get('name', 'Unknown')
            start = format_date(season.get('start_date'))
            end = format_date(season.get('end_date'))
            is_current = "✓" if season.get('is_current') else ""

            table.add_row(season_id, name, start, end, is_current)

        console.print(table)

    except Exception as e:
        handle_error(e, verbose)
        raise typer.Exit(1)


@ref_app.command("age-groups")
def list_age_groups(
    json_output: bool = typer.Option(False, "--json"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """👶 List age groups."""
    try:
        client = get_client()
        age_groups = client.get_age_groups()

        if json_output:
            console.print(JSON(json.dumps(age_groups, indent=2)))
            return

        table = Table(title="Age Groups")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Name", style="green", width=20)

        for ag in age_groups:
            table.add_row(str(ag.get('id', '')), ag.get('name', 'Unknown'))

        console.print(table)

    except Exception as e:
        handle_error(e, verbose)
        raise typer.Exit(1)


@ref_app.command("divisions")
def list_divisions(
    json_output: bool = typer.Option(False, "--json"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """🏆 List divisions."""
    try:
        client = get_client()
        divisions = client.get_divisions()

        if json_output:
            console.print(JSON(json.dumps(divisions, indent=2)))
            return

        table = Table(title="Divisions")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Name", style="green", width=30)
        table.add_column("Level", justify="center", width=10)

        for div in divisions:
            div_id = str(div.get('id', ''))
            name = div.get('name', 'Unknown')
            level = str(div.get('level', 'N/A'))

            table.add_row(div_id, name, level)

        console.print(table)

    except Exception as e:
        handle_error(e, verbose)
        raise typer.Exit(1)


@ref_app.command("game-types")
def list_game_types(
    json_output: bool = typer.Option(False, "--json"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """🎮 List game types."""
    try:
        client = get_client()
        game_types = client.get_game_types()

        if json_output:
            console.print(JSON(json.dumps(game_types, indent=2)))
            return

        table = Table(title="Game Types")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Name", style="green", width=30)

        for gt in game_types:
            table.add_row(str(gt.get('id', '')), gt.get('name', 'Unknown'))

        console.print(table)

    except Exception as e:
        handle_error(e, verbose)
        raise typer.Exit(1)


# ============================================================================
# Auth Commands
# ============================================================================

auth_app = typer.Typer(help="🔐 Authentication")
app.add_typer(auth_app, name="auth")


@auth_app.command("login")
def login(
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """🔑 Login and store credentials."""
    try:
        client = get_client()
        console.print("[cyan]Logging in...[/cyan]")

        result = client.login(username, password)

        # Save token for future commands
        access_token = result.get('access_token')
        refresh_token = result.get('refresh_token')
        if access_token and refresh_token:
            save_token(access_token, refresh_token, client.base_url)
            console.print("[dim]✓ Token saved for future commands[/dim]")

        console.print("[bold green]✓ Login successful![/bold green]\n")

        user = result.get('user', {})
        console.print(Panel(
            f"[bold]Username:[/bold] {user.get('username', 'N/A')}\n"
            f"[bold]Role:[/bold] {user.get('role', 'N/A')}\n"
            f"[bold]Display Name:[/bold] {user.get('display_name', 'N/A')}\n"
            f"[bold]Email:[/bold] {user.get('email', 'N/A')}",
            title="User Info",
            border_style="green",
        ))

        if verbose:
            console.print("\n[bold]Full Response:[/bold]")
            # Don't show tokens in verbose output for security
            safe_result = {k: v for k, v in result.items() if 'token' not in k.lower()}
            console.print(JSON(json.dumps(safe_result, indent=2)))

    except Exception as e:
        handle_error(e, verbose)
        raise typer.Exit(1)


@auth_app.command("profile")
def get_profile(
    json_output: bool = typer.Option(False, "--json"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """👤 Get current user profile (requires login)."""
    try:
        client = get_client()
        profile = client.get_profile()

        if json_output:
            console.print(JSON(json.dumps(profile, indent=2)))
            return

        console.print(Panel(
            f"[bold]Username:[/bold] {profile.get('username', 'N/A')}\n"
            f"[bold]Role:[/bold] {profile.get('role', 'N/A')}\n"
            f"[bold]Display Name:[/bold] {profile.get('display_name', 'N/A')}\n"
            f"[bold]Team ID:[/bold] {profile.get('team_id', 'N/A')}\n"
            f"[bold]Email:[/bold] {profile.get('email', 'N/A')}",
            title="Profile",
            border_style="blue",
        ))

    except Exception as e:
        handle_error(e, verbose)
        raise typer.Exit(1)


@auth_app.command("logout")
def logout():
    """🚪 Logout and clear stored credentials."""
    try:
        if TOKEN_FILE.exists():
            clear_token()
            console.print("[bold green]✓ Logged out successfully![/bold green]")
            console.print("[dim]Token cleared from storage[/dim]")
        else:
            console.print("[yellow]No active session found[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Error during logout: {e}[/red]")
        raise typer.Exit(1)


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    try:
        app()
    finally:
        if _client:
            _client.close()

#!/usr/bin/env python3
"""
Match Search Tool

A focused CLI tool for searching matches with comprehensive filters.

Features:
- Filter by Match Type (default: League)
- Filter by League
- Filter by Division/Conference
- Filter by Age Group
- Filter by Team (home or away)
- Filter by Season (default: 2025-2026)
- Beautiful rich table output
- Environment-aware (local/dev/prod)

Usage:
    # Search with defaults (League matches, 2025-2026 season)
    python search_matches.py

    # Search by team
    python search_matches.py --team IFA

    # Search by MLS ID (external match identifier)
    python search_matches.py --mls-id 100502

    # Search by age group and division
    python search_matches.py --age-group U14 --division "Elite Division"

    # Search by league
    python search_matches.py --league Academy

    # Search specific match type
    python search_matches.py --match-type Friendly

    # Search different season
    python search_matches.py --season 2024-2025

    # Combine filters
    python search_matches.py --team IFA --age-group U14 --season 2025-2026
"""

import os
import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import DAO layer
from dao.enhanced_data_access_fixed import SupabaseConnection, EnhancedSportsDAO

app = typer.Typer(help="Match Search Tool - Search matches with comprehensive filters")
console = Console()

# Defaults
DEFAULT_MATCH_TYPE = "League"
DEFAULT_SEASON = "2025-2026"


def load_environment():
    """Load environment variables from .env file based on APP_ENV"""
    app_env = os.getenv("APP_ENV", "local")
    console.print(f"[green]✓[/green] Environment: [cyan]{app_env}[/cyan]")
    return app_env


def get_dao() -> EnhancedSportsDAO:
    """Get DAO instance using proper data access layer"""
    try:
        connection = SupabaseConnection()
        dao = EnhancedSportsDAO(connection)
        return dao
    except Exception as e:
        console.print(f"[red]Error connecting to database: {e}[/red]")
        raise typer.Exit(1)


def get_reference_data(dao: EnhancedSportsDAO):
    """Get reference data for validation and filtering using DAO"""
    try:
        match_types = {mt["name"]: mt["id"] for mt in dao.get_all_match_types()}
        seasons = {s["name"]: s["id"] for s in dao.get_all_seasons()}
        age_groups = {ag["name"]: ag["id"] for ag in dao.get_all_age_groups()}
        divisions = {d["name"]: d["id"] for d in dao.get_all_divisions()}
        leagues = {l["name"]: l["id"] for l in dao.get_all_leagues()}
        teams = {t["name"]: t["id"] for t in dao.get_all_teams()}

        return {
            "match_types": match_types,
            "seasons": seasons,
            "age_groups": age_groups,
            "divisions": divisions,
            "leagues": leagues,
            "teams": teams
        }
    except Exception as e:
        console.print(f"[red]Error loading reference data: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def search(
    match_type: Optional[str] = typer.Option(
        DEFAULT_MATCH_TYPE,
        "--match-type", "-m",
        help=f"Match type (default: {DEFAULT_MATCH_TYPE})"
    ),
    season: Optional[str] = typer.Option(
        DEFAULT_SEASON,
        "--season", "-s",
        help=f"Season (default: {DEFAULT_SEASON})"
    ),
    league: Optional[str] = typer.Option(None, "--league", "-l", help="Filter by league"),
    division: Optional[str] = typer.Option(None, "--division", "-d", help="Filter by division/conference"),
    age_group: Optional[str] = typer.Option(None, "--age-group", "-a", help="Filter by age group (e.g., U14, U15)"),
    team: Optional[str] = typer.Option(None, "--team", "-t", help="Filter by team name (searches both home and away)"),
    mls_id: Optional[str] = typer.Option(None, "--mls-id", help="Filter by MLS match ID (external identifier from mlssoccer.com)"),
    limit: int = typer.Option(100, "--limit", help="Maximum number of matches to show"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    show_filters: bool = typer.Option(True, "--show-filters/--no-filters", help="Show applied filters"),
):
    """
    Search for matches with comprehensive filters.

    Defaults:
    - Match Type: League
    - Season: 2025-2026

    Examples:
        # Default search (League matches, 2025-2026)
        python search_matches.py

        # Search by team
        python search_matches.py --team IFA

        # Search by MLS ID (external match identifier)
        python search_matches.py --mls-id 100502

        # Search by age group and division
        python search_matches.py --age-group U14 --division "Elite Division"

        # Search different season
        python search_matches.py --season 2024-2025 --match-type Tournament
    """
    env = load_environment()
    dao = get_dao()

    # Load reference data
    ref_data = get_reference_data(dao)

    # Validate filters
    if match_type and match_type not in ref_data["match_types"]:
        console.print(f"[red]Error: Match type '{match_type}' not found.[/red]")
        console.print(f"[yellow]Available match types: {', '.join(ref_data['match_types'].keys())}[/yellow]")
        raise typer.Exit(1)

    if season and season not in ref_data["seasons"]:
        console.print(f"[red]Error: Season '{season}' not found.[/red]")
        console.print(f"[yellow]Available seasons: {', '.join(ref_data['seasons'].keys())}[/yellow]")
        raise typer.Exit(1)

    if age_group and age_group not in ref_data["age_groups"]:
        console.print(f"[red]Error: Age group '{age_group}' not found.[/red]")
        console.print(f"[yellow]Available age groups: {', '.join(ref_data['age_groups'].keys())}[/yellow]")
        raise typer.Exit(1)

    if division and division not in ref_data["divisions"]:
        console.print(f"[red]Error: Division '{division}' not found.[/red]")
        console.print(f"[yellow]Available divisions: {', '.join(ref_data['divisions'].keys())}[/yellow]")
        raise typer.Exit(1)

    # Look up team ID if team name is provided (exact match)
    team_id = None
    if team:
        team_obj = dao.get_team_by_name(team)
        if not team_obj:
            console.print(f"[red]Error: Team '{team}' not found.[/red]")
            console.print(f"[yellow]Tip: Use 'list-teams' command to see available teams[/yellow]")
            raise typer.Exit(1)
        team_id = team_obj["id"]

    # Get matches using DAO layer - all filtering done in database
    matches_data = dao.get_all_matches(
        season_id=ref_data["seasons"].get(season) if season else None,
        age_group_id=ref_data["age_groups"].get(age_group) if age_group else None,
        division_id=ref_data["divisions"].get(division) if division else None,
        team_id=team_id,  # Exact team ID lookup
        match_type=match_type  # DAO handles match_type by name
    )

    # Apply client-side filters (league and mls_id not in DAO)
    original_count = len(matches_data)

    # Filter by MLS ID if provided
    if mls_id:
        matches_data = [
            m for m in matches_data
            if m.get("match_id") == mls_id
        ]

    if league:
        if league not in ref_data["leagues"]:
            console.print(f"[red]Error: League '{league}' not found.[/red]")
            console.print(f"[yellow]Available leagues: {', '.join(ref_data['leagues'].keys())}[/yellow]")
            raise typer.Exit(1)

        def get_match_league(match):
            """Extract the league name from the division"""
            division = match.get("division")
            if division and isinstance(division, dict):
                leagues_data = division.get("leagues!divisions_league_id_fkey") or division.get("leagues")
                if isinstance(leagues_data, dict):
                    return leagues_data.get("name")
            return None

        matches_data = [
            m for m in matches_data
            if get_match_league(m) == league
        ]

    # Apply limit AFTER filtering
    matches_data = matches_data[:limit]

    # Display results
    if show_filters:
        filters_applied = []
        if match_type:
            filters_applied.append(f"Match Type: [cyan]{match_type}[/cyan]")
        if season:
            filters_applied.append(f"Season: [cyan]{season}[/cyan]")
        if league:
            filters_applied.append(f"League: [cyan]{league}[/cyan]")
        if division:
            filters_applied.append(f"Division: [cyan]{division}[/cyan]")
        if age_group:
            filters_applied.append(f"Age Group: [cyan]{age_group}[/cyan]")
        if team:
            filters_applied.append(f"Team: [cyan]{team}[/cyan]")
        if mls_id:
            filters_applied.append(f"MLS ID: [cyan]{mls_id}[/cyan]")

        if filters_applied:
            console.print(Panel(
                "\n".join(filters_applied),
                title="[bold]Applied Filters[/bold]",
                border_style="blue"
            ))
            console.print()

    # Create results table
    table = Table(
        title=f"Matches ({len(matches_data)} found)",
        show_header=True,
        header_style="bold magenta"
    )

    table.add_column("ID", style="cyan", width=5)
    table.add_column("MLS ID", style="dim", width=12)
    table.add_column("Date", style="yellow", width=10)
    table.add_column("Home Team", style="green", width=20)
    table.add_column("H.ID", style="dim", width=5)
    table.add_column("Score", style="white", width=7, justify="center")
    table.add_column("Away Team", style="blue", width=20)
    table.add_column("A.ID", style="dim", width=5)
    table.add_column("League", style="magenta", width=10)
    if verbose:
        table.add_column("Age Group", style="dim", width=8)
        table.add_column("Division", style="dim", width=15)
        table.add_column("Status", style="dim", width=10)

    for match in matches_data:
        # DAO returns flattened structure
        home_team = match.get("home_team_name", "Unknown")
        away_team = match.get("away_team_name", "Unknown")
        home_team_id = match.get("home_team_id", "-")
        away_team_id = match.get("away_team_id", "-")
        home_score = match.get("home_score")
        away_score = match.get("away_score")
        mls_match_id = match.get("match_id", "-") or "-"  # External match ID from MLSNext

        # Extract league name from division
        league_name = "-"
        division = match.get("division")
        if division and isinstance(division, dict):
            leagues_data = division.get("leagues!divisions_league_id_fkey") or division.get("leagues")
            if isinstance(leagues_data, dict):
                league_name = leagues_data.get("name", "-")

        # Format score
        if home_score is not None and away_score is not None:
            score = f"{home_score}-{away_score}"
        else:
            score = "TBD"

        row = [
            str(match["id"]),  # Primary key
            mls_match_id,      # External match ID from MLSNext website
            match["match_date"],
            home_team,
            str(home_team_id),
            score,
            away_team,
            str(away_team_id),
            league_name
        ]

        if verbose:
            row.append(match.get("age_group_name", "-"))
            row.append(match.get("division_name", "-") or "-")
            row.append(match.get("match_status", "-"))

        table.add_row(*row)

    console.print(table)

    # Summary
    if original_count != len(matches_data):
        console.print(f"\n[dim]Filtered from {original_count} to {len(matches_data)} matches[/dim]")

    console.print(f"\n[green]Environment:[/green] {env}")


@app.command()
def list_options():
    """List all available filter options (match types, seasons, leagues, etc.)"""
    load_environment()
    dao = get_dao()
    ref_data = get_reference_data(dao)

    console.print(Panel("[bold]Available Filter Options[/bold]", border_style="green"))
    console.print()

    # Match Types
    console.print("[bold cyan]Match Types:[/bold cyan]")
    for name in sorted(ref_data["match_types"].keys()):
        default = " [yellow](default)[/yellow]" if name == DEFAULT_MATCH_TYPE else ""
        console.print(f"  • {name}{default}")
    console.print()

    # Seasons
    console.print("[bold cyan]Seasons:[/bold cyan]")
    for name in sorted(ref_data["seasons"].keys(), reverse=True):
        default = " [yellow](default)[/yellow]" if name == DEFAULT_SEASON else ""
        console.print(f"  • {name}{default}")
    console.print()

    # Leagues
    console.print("[bold cyan]Leagues:[/bold cyan]")
    for name in sorted(ref_data["leagues"].keys()):
        console.print(f"  • {name}")
    console.print()

    # Age Groups
    console.print("[bold cyan]Age Groups:[/bold cyan]")
    for name in sorted(ref_data["age_groups"].keys()):
        console.print(f"  • {name}")
    console.print()

    # Divisions
    console.print("[bold cyan]Divisions:[/bold cyan]")
    for name in sorted(ref_data["divisions"].keys()):
        console.print(f"  • {name}")


@app.command()
def list_teams(
    league: Optional[str] = typer.Option(None, "--league", "-l", help="Filter teams by league"),
    age_group: Optional[str] = typer.Option(None, "--age-group", "-a", help="Filter teams by age group"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search teams by name (partial match)"),
):
    """List all teams with optional filtering"""
    load_environment()
    dao = get_dao()
    ref_data = get_reference_data(dao)

    # Validate filters
    if league and league not in ref_data["leagues"]:
        console.print(f"[red]Error: League '{league}' not found.[/red]")
        console.print(f"[yellow]Available leagues: {', '.join(ref_data['leagues'].keys())}[/yellow]")
        raise typer.Exit(1)

    if age_group and age_group not in ref_data["age_groups"]:
        console.print(f"[red]Error: Age group '{age_group}' not found.[/red]")
        console.print(f"[yellow]Available age groups: {', '.join(ref_data['age_groups'].keys())}[/yellow]")
        raise typer.Exit(1)

    # Get all teams
    all_teams = dao.get_all_teams()

    # Apply filters
    teams = all_teams

    # Filter by search term (partial match)
    if search:
        teams = [t for t in teams if search.lower() in t["name"].lower()]

    # Filter by league (check team's league_id)
    if league:
        league_id = ref_data["leagues"][league]
        teams = [t for t in teams if t.get("league_id") == league_id]

    # Note: Can't easily filter by age_group since teams can play in multiple age groups via team_mappings
    # For now, skip age_group filtering

    # Display results
    table = Table(
        title=f"Teams ({len(teams)} found)",
        show_header=True,
        header_style="bold magenta"
    )

    table.add_column("Name", style="green", width=40)
    table.add_column("City", style="yellow", width=20)
    table.add_column("League", style="cyan", width=15)

    for team in sorted(teams, key=lambda t: t["name"]):
        league_name = "-"
        if team.get("league_id"):
            # Find league name from ref_data
            for l_name, l_id in ref_data["leagues"].items():
                if l_id == team["league_id"]:
                    league_name = l_name
                    break

        table.add_row(
            team["name"],
            team.get("city", "-") or "-",
            league_name
        )

    console.print(table)

    if search or league:
        console.print(f"\n[dim]Showing {len(teams)} of {len(all_teams)} total teams[/dim]")


if __name__ == "__main__":
    app()

#!/usr/bin/env python3
"""
Match League Validation Tool

Validates that matches are assigned to the correct league based on team memberships.

A match's league should match at least one of the participating teams' leagues.
If neither the home nor away team belongs to the match's league, it's a data integrity issue.

Usage:
    # Check all matches for league mismatches
    python validate_match_leagues.py check

    # Check specific league
    python validate_match_leagues.py check --league Academy

    # Check specific season
    python validate_match_leagues.py check --season 2025-2026

    # Export results to JSON
    python validate_match_leagues.py check --export mismatches.json
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional
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

app = typer.Typer(help="Match League Validation Tool - Find league assignment errors")
console = Console()


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


def get_match_league_name(match: dict) -> str:
    """Extract league name from match's division"""
    division = match.get("division")
    if division and isinstance(division, dict):
        leagues_data = division.get("leagues!divisions_league_id_fkey") or division.get("leagues")
        if isinstance(leagues_data, dict):
            return leagues_data.get("name", "Unknown")
    return "Unknown"


@app.command()
def check(
    league: Optional[str] = typer.Option(None, "--league", "-l", help="Filter by specific league"),
    season: Optional[str] = typer.Option(None, "--season", "-s", help="Filter by season"),
    match_type: Optional[str] = typer.Option(None, "--match-type", "-m", help="Filter by match type"),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Export results to JSON file"),
    show_valid: bool = typer.Option(False, "--show-valid", help="Also show valid matches"),
):
    """
    Check matches for league assignment errors.

    A match is invalid if neither the home nor away team belongs to the match's league.
    """
    env = load_environment()
    dao = get_dao()

    # Get all teams and build league lookup
    console.print("[cyan]Loading teams and leagues...[/cyan]")

    # Query teams directly to get league_id (DAO method doesn't return it)
    connection = SupabaseConnection()
    teams_response = connection.client.table("teams").select("id, name, league_id").execute()
    all_teams = teams_response.data

    team_leagues = {}  # team_id -> league_name

    leagues = dao.get_all_leagues()
    league_names = {l["id"]: l["name"] for l in leagues}

    for team in all_teams:
        if team.get("league_id"):
            team_leagues[team["id"]] = league_names.get(team["league_id"], "Unknown")
        else:
            team_leagues[team["id"]] = "No League"

    # Get matches with filters
    console.print("[cyan]Loading matches...[/cyan]")
    filters = {}
    if season:
        seasons = {s["name"]: s["id"] for s in dao.get_all_seasons()}
        if season not in seasons:
            console.print(f"[red]Error: Season '{season}' not found.[/red]")
            raise typer.Exit(1)
        filters["season_id"] = seasons[season]

    if match_type:
        filters["match_type"] = match_type

    matches = dao.get_all_matches(**filters)

    # Filter by league if specified
    if league:
        matches = [m for m in matches if get_match_league_name(m) == league]

    console.print(f"[cyan]Analyzing {len(matches)} matches...[/cyan]\n")

    # Validate matches
    invalid_matches = []
    valid_matches = []

    for match in matches:
        match_league = get_match_league_name(match)
        match_type_name = match.get("match_type_name", "Unknown")
        home_team_id = match.get("home_team_id")
        away_team_id = match.get("away_team_id")

        home_league = team_leagues.get(home_team_id, "Unknown")
        away_league = team_leagues.get(away_team_id, "Unknown")

        # Validation logic depends on match type:
        # - For "League" matches: BOTH teams must be in the same league
        # - For other matches (Friendly, Tournament, etc.): At least one team must be in the match's league
        if match_type_name == "League":
            # Strict validation: both teams must be in the match's league
            is_valid = (home_league == match_league) and (away_league == match_league)
        else:
            # Lenient validation: at least one team must be in the match's league
            is_valid = (home_league == match_league) or (away_league == match_league)

        match_info = {
            "match_id": match["id"],
            "mls_id": match.get("match_id", "-"),
            "date": match["match_date"],
            "match_type": match_type_name,
            "match_league": match_league,
            "home_team": match["home_team_name"],
            "home_team_id": home_team_id,
            "home_league": home_league,
            "away_team": match["away_team_name"],
            "away_team_id": away_team_id,
            "away_league": away_league,
            "score": f"{match.get('home_score', 'TBD')}-{match.get('away_score', 'TBD')}",
            "is_valid": is_valid
        }

        if is_valid:
            valid_matches.append(match_info)
        else:
            invalid_matches.append(match_info)

    # Display results
    if invalid_matches:
        console.print(Panel(
            f"[red bold]Found {len(invalid_matches)} matches with league mismatches![/red bold]",
            border_style="red"
        ))
        console.print()

        # Create table for invalid matches
        table = Table(
            title="❌ Invalid League Assignments",
            show_header=True,
            header_style="bold red"
        )

        table.add_column("Match ID", style="cyan", width=8)
        table.add_column("MLS ID", style="dim", width=10)
        table.add_column("Date", style="yellow", width=10)
        table.add_column("Type", style="white", width=10)
        table.add_column("Match League", style="magenta", width=12)
        table.add_column("Home Team", style="green", width=20)
        table.add_column("Home League", style="dim", width=12)
        table.add_column("Away Team", style="blue", width=20)
        table.add_column("Away League", style="dim", width=12)

        for m in invalid_matches:
            table.add_row(
                str(m["match_id"]),
                m["mls_id"],
                m["date"],
                m["match_type"],
                m["match_league"],
                f"{m['home_team']} ({m['home_team_id']})",
                m["home_league"],
                f"{m['away_team']} ({m['away_team_id']})",
                m["away_league"]
            )

        console.print(table)
        console.print()
    else:
        console.print(Panel(
            f"[green bold]✓ All {len(matches)} matches have valid league assignments![/green bold]",
            border_style="green"
        ))

    # Show valid matches if requested
    if show_valid and valid_matches:
        console.print()
        table = Table(
            title="✓ Valid League Assignments",
            show_header=True,
            header_style="bold green"
        )

        table.add_column("Match ID", style="cyan", width=8)
        table.add_column("Date", style="yellow", width=10)
        table.add_column("Type", style="white", width=10)
        table.add_column("Match League", style="magenta", width=12)
        table.add_column("Home Team", style="green", width=20)
        table.add_column("Home League", style="dim", width=12)
        table.add_column("Away Team", style="blue", width=20)
        table.add_column("Away League", style="dim", width=12)

        for m in valid_matches[:20]:  # Show first 20
            table.add_row(
                str(m["match_id"]),
                m["date"],
                m["match_type"],
                m["match_league"],
                f"{m['home_team']} ({m['home_team_id']})",
                m["home_league"],
                f"{m['away_team']} ({m['away_team_id']})",
                m["away_league"]
            )

        console.print(table)
        if len(valid_matches) > 20:
            console.print(f"[dim]... and {len(valid_matches) - 20} more valid matches[/dim]")

    # Summary
    console.print()
    console.print(f"[bold]Summary:[/bold]")
    console.print(f"  Total matches: {len(matches)}")
    console.print(f"  [green]Valid:[/green] {len(valid_matches)}")
    console.print(f"  [red]Invalid:[/red] {len(invalid_matches)}")

    # Export if requested
    if export and invalid_matches:
        export_data = {
            "generated_at": datetime.now().isoformat(),
            "environment": env,
            "filters": {
                "league": league,
                "season": season,
                "match_type": match_type
            },
            "summary": {
                "total_matches": len(matches),
                "valid_matches": len(valid_matches),
                "invalid_matches": len(invalid_matches)
            },
            "invalid_matches": invalid_matches
        }

        with open(export, "w") as f:
            json.dump(export_data, f, indent=2)

        console.print(f"\n[green]✓[/green] Exported {len(invalid_matches)} invalid matches to [cyan]{export}[/cyan]")


if __name__ == "__main__":
    app()

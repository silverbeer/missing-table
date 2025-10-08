#!/usr/bin/env python3
"""
Database Inspector Tool

A powerful CLI tool for inspecting and troubleshooting database data.
Uses direct Supabase connection (bypassing DAOs) for raw data access.

Features:
- Browse age groups, divisions, teams, games
- Filter and search data
- Identify duplicates and data issues
- Beautiful rich table output
- Environment-aware (local/dev/prod)

Usage:
    python inspect_db.py teams --age-group U14
    python inspect_db.py games --team IFA --duplicates
    python inspect_db.py age-groups
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
from dotenv import load_dotenv
from supabase import create_client, Client

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

app = typer.Typer(help="Database Inspector - Direct database access for troubleshooting")
console = Console()


def print_sql_query(table: str, select: str = "*", filters: dict = None, order_by: str = None, limit: int = None):
    """Print the equivalent SQL query for reference"""
    query = f"SELECT {select}\nFROM {table}"

    if filters:
        where_clauses = []
        for key, value in filters.items():
            if isinstance(value, str):
                where_clauses.append(f"{key} = '{value}'")
            else:
                where_clauses.append(f"{key} = {value}")
        if where_clauses:
            query += f"\nWHERE {' AND '.join(where_clauses)}"

    if order_by:
        query += f"\nORDER BY {order_by}"

    if limit:
        query += f"\nLIMIT {limit}"

    console.print(f"\n[dim]SQL Query:[/dim]\n[dim italic]{query};[/dim italic]\n")


def load_environment():
    """Load environment variables from .env file based on APP_ENV"""
    app_env = os.getenv("APP_ENV", "local")
    env_file = Path(__file__).parent / f".env.{app_env}"

    if not env_file.exists():
        console.print(f"[yellow]Warning: {env_file} not found, using environment variables[/yellow]")
        return app_env

    load_dotenv(env_file)
    console.print(f"[green]✓[/green] Loaded environment: [cyan]{app_env}[/cyan]")
    return app_env


def get_supabase_client() -> Client:
    """Get direct Supabase client (bypassing DAOs)"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        console.print("[red]Error: SUPABASE_URL and SUPABASE_SERVICE_KEY/SUPABASE_ANON_KEY required[/red]")
        raise typer.Exit(1)

    return create_client(url, key)


@app.command()
def age_groups(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """List all age groups"""
    load_environment()
    supabase = get_supabase_client()

    response = supabase.table("age_groups").select("*").order("name").execute()

    table = Table(title="Age Groups", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    if verbose:
        table.add_column("Created", style="dim")

    for ag in response.data:
        row = [str(ag["id"]), ag["name"]]
        if verbose and ag.get("created_at"):
            row.append(ag["created_at"])
        table.add_row(*row)

    console.print(table)
    console.print(f"\n[green]Total:[/green] {len(response.data)} age groups")

    # Show SQL query reference
    console.print(f"\n[dim]PostgREST Query:[/dim]")
    console.print(f"[dim italic]GET /age_groups?select=*&order=name.asc[/dim italic]")


@app.command()
def divisions(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """List all divisions"""
    load_environment()
    supabase = get_supabase_client()

    response = supabase.table("divisions").select("*").order("name").execute()

    table = Table(title="Divisions", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    if verbose:
        table.add_column("Created", style="dim")

    for div in response.data:
        row = [str(div["id"]), div["name"]]
        if verbose and div.get("created_at"):
            row.append(div["created_at"])
        table.add_row(*row)

    console.print(table)
    console.print(f"\n[green]Total:[/green] {len(response.data)} divisions")

    # Show SQL query reference
    console.print(f"\n[dim]PostgREST Query:[/dim]")
    console.print(f"[dim italic]GET /divisions?select=*&order=name.asc[/dim italic]")


@app.command()
def teams(
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search team names"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """List teams with optional filtering"""
    load_environment()
    supabase = get_supabase_client()

    # Get teams - simplified query since age groups/divisions are on games, not teams
    query = supabase.table("teams").select("id, name, city, academy_team, created_at").order("name")

    response = query.execute()
    teams_data = response.data

    if search:
        teams_data = [t for t in teams_data if search.lower() in t["name"].lower()]

    # Create table
    table = Table(title=f"Teams ({len(teams_data)})", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", width=5)
    table.add_column("Name", style="green", width=30)
    table.add_column("City", style="yellow", width=15)
    if verbose:
        table.add_column("Academy", style="blue", width=10)
        table.add_column("Created", style="dim")

    for team in teams_data:
        row = [
            str(team["id"]),
            team["name"],
            team.get("city", "-") or "-"
        ]

        if verbose:
            row.append("Yes" if team.get("academy_team") else "No")
            if team.get("created_at"):
                row.append(team["created_at"][:10])

        table.add_row(*row)

    console.print(table)
    console.print(f"\n[green]Total:[/green] {len(teams_data)} teams")

    # Show SQL query reference
    console.print(f"\n[dim]PostgREST Query:[/dim]")
    query_str = "GET /teams?select=id,name,city,academy_team,created_at&order=name.asc"
    console.print(f"[dim italic]{query_str}[/dim italic]")

    if search:
        console.print(f"\n[dim]Additional Filters (applied client-side):[/dim]")
        console.print(f"[dim italic]  - name ILIKE '%{search}%'[/dim italic]")


@app.command()
def games(
    team: Optional[str] = typer.Option(None, "--team", "-t", help="Filter by team name"),
    age_group: Optional[str] = typer.Option(None, "--age-group", "-a", help="Filter by age group"),
    season: Optional[str] = typer.Option(None, "--season", "-s", help="Filter by season (e.g., 2025-2026)"),
    duplicates: bool = typer.Option(False, "--duplicates", "-d", help="Show only potential duplicates"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max number of games to show"),
):
    """List games with optional filtering"""
    load_environment()
    supabase = get_supabase_client()

    # Build query
    query = supabase.table("games").select(
        "id, game_date, home_score, away_score, match_status, source, "
        "home_team:teams!games_home_team_id_fkey(id, name), "
        "away_team:teams!games_away_team_id_fkey(id, name), "
        "age_groups(id, name), "
        "seasons(id, name), "
        "game_types(id, name)"
    ).order("game_date", desc=True).limit(limit)

    response = query.execute()
    games_data = response.data

    # Apply filters
    if team:
        games_data = [
            g for g in games_data
            if (g.get("home_team") and team.lower() in g["home_team"]["name"].lower()) or
               (g.get("away_team") and team.lower() in g["away_team"]["name"].lower())
        ]

    if age_group:
        games_data = [
            g for g in games_data
            if g.get("age_groups") and g["age_groups"]["name"] == age_group
        ]

    if season:
        games_data = [
            g for g in games_data
            if g.get("seasons") and season in g["seasons"]["name"]
        ]

    # Find duplicates if requested
    if duplicates:
        seen = {}
        duplicate_games = []

        for game in games_data:
            if not game.get("home_team") or not game.get("away_team"):
                continue

            # Create key for duplicate detection
            key = (
                game["game_date"],
                game.get("home_team", {}).get("id"),
                game.get("away_team", {}).get("id"),
                game.get("seasons", {}).get("id"),
                game.get("game_types", {}).get("id")
            )

            if key in seen:
                # Mark both as duplicates
                if seen[key] not in duplicate_games:
                    duplicate_games.append(seen[key])
                duplicate_games.append(game)
            else:
                seen[key] = game

        games_data = duplicate_games

    # Create table
    title = f"Games ({len(games_data)})"
    if duplicates:
        title = f"[red]Duplicate Games ({len(games_data)})[/red]"

    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", width=5)
    table.add_column("Date", style="green", width=12)
    table.add_column("Home Team", style="yellow", width=20)
    table.add_column("Away Team", style="yellow", width=20)
    table.add_column("Score", style="white", width=8)
    table.add_column("Age", style="blue", width=6)
    table.add_column("Season", style="magenta", width=10)
    table.add_column("Source", style="dim", width=8)

    for game in games_data:
        game_date = game["game_date"][:10] if game.get("game_date") else "-"
        home_team = game.get("home_team", {}).get("name", "?")
        away_team = game.get("away_team", {}).get("name", "?")
        score = f"{game.get('home_score', '-')} - {game.get('away_score', '-')}"
        age_group = game.get("age_groups", {}).get("name", "-")
        season = game.get("seasons", {}).get("name", "-")
        source = game.get("source", "manual")

        # Highlight duplicates
        style = "red" if duplicates else None

        table.add_row(
            str(game["id"]),
            game_date,
            home_team,
            away_team,
            score,
            age_group,
            season,
            source,
            style=style
        )

    console.print(table)

    if duplicates and games_data:
        console.print(f"\n[red]Warning:[/red] Found {len(games_data)} potential duplicate games")
        console.print("[yellow]Duplicates are based on: same date, teams, season, and game type[/yellow]")
    else:
        console.print(f"\n[green]Total:[/green] {len(games_data)} games")

    # Show SQL query reference
    select_clause = (
        "id, game_date, home_score, away_score, match_status, source, "
        "home_team:teams!games_home_team_id_fkey(id, name), "
        "away_team:teams!games_away_team_id_fkey(id, name), "
        "age_groups(id, name), seasons(id, name), game_types(id, name)"
    )
    filters = {}
    filter_notes = []

    if age_group:
        filter_notes.append(f"age_groups.name = '{age_group}' (post-filter)")
    if season:
        filter_notes.append(f"seasons.name LIKE '%{season}%' (post-filter)")
    if team:
        filter_notes.append(f"teams.name ILIKE '%{team}%' (post-filter)")

    console.print(f"\n[dim]PostgREST Query:[/dim]")
    console.print(f"[dim italic]GET /games?select={select_clause}&order=game_date.desc&limit={limit}[/dim italic]")

    if filter_notes:
        console.print(f"\n[dim]Additional Filters (applied client-side):[/dim]")
        for note in filter_notes:
            console.print(f"[dim italic]  - {note}[/dim italic]")


@app.command()
def game_detail(
    game_id: int = typer.Argument(..., help="Game ID to inspect"),
):
    """Show detailed information about a specific game"""
    load_environment()
    supabase = get_supabase_client()

    response = supabase.table("games").select(
        "*, "
        "home_team:teams!games_home_team_id_fkey(id, name), "
        "away_team:teams!games_away_team_id_fkey(id, name), "
        "age_groups(id, name), "
        "divisions(id, name), "
        "seasons(id, name), "
        "game_types(id, name)"
    ).eq("id", game_id).execute()

    if not response.data:
        console.print(f"[red]Error:[/red] Game {game_id} not found")
        raise typer.Exit(1)

    game = response.data[0]

    # Create detailed panel
    details = f"""
[cyan]Game ID:[/cyan] {game['id']}
[cyan]Date:[/cyan] {game.get('game_date', 'N/A')}
[cyan]Status:[/cyan] {game.get('match_status', 'scheduled')}
[cyan]Source:[/cyan] {game.get('source', 'manual')}

[yellow]Teams:[/yellow]
  Home: {game.get('home_team', {}).get('name', 'Unknown')} (ID: {game.get('home_team_id')})
  Away: {game.get('away_team', {}).get('name', 'Unknown')} (ID: {game.get('away_team_id')})

[yellow]Score:[/yellow]
  {game.get('home_score', 0)} - {game.get('away_score', 0)}

[yellow]Competition:[/yellow]
  Season: {game.get('seasons', {}).get('name', 'Unknown')}
  Age Group: {game.get('age_groups', {}).get('name', 'Unknown')}
  Division: {game.get('divisions', {}).get('name', 'Unknown') if game.get('divisions') else 'N/A'}
  Game Type: {game.get('game_types', {}).get('name', 'Unknown')}

[yellow]Metadata:[/yellow]
  Created: {game.get('created_at', 'N/A')}
  Updated: {game.get('updated_at', 'N/A')}
  Match ID: {game.get('match_id', 'N/A')}
"""

    console.print(Panel(details, title=f"Game {game_id} Details", border_style="green"))

    # Show SQL query reference
    select_clause = (
        "*, "
        "home_team:teams!games_home_team_id_fkey(id, name), "
        "away_team:teams!games_away_team_id_fkey(id, name), "
        "age_groups(id, name), divisions(id, name), seasons(id, name), game_types(id, name)"
    )
    console.print(f"\n[dim]PostgREST Query:[/dim]")
    console.print(f"[dim italic]GET /games?select={select_clause}&id=eq.{game_id}[/dim italic]")


@app.command()
def stats():
    """Show database statistics"""
    load_environment()
    supabase = get_supabase_client()

    # Get counts
    teams_count = len(supabase.table("teams").select("id", count="exact").execute().data)
    games_count = len(supabase.table("games").select("id", count="exact").execute().data)
    age_groups_count = len(supabase.table("age_groups").select("id", count="exact").execute().data)
    divisions_count = len(supabase.table("divisions").select("id", count="exact").execute().data)
    seasons_count = len(supabase.table("seasons").select("id", count="exact").execute().data)

    table = Table(title="Database Statistics", show_header=True, header_style="bold magenta")
    table.add_column("Table", style="cyan")
    table.add_column("Count", style="green", justify="right")

    table.add_row("Teams", str(teams_count))
    table.add_row("Games", str(games_count))
    table.add_row("Age Groups", str(age_groups_count))
    table.add_row("Divisions", str(divisions_count))
    table.add_row("Seasons", str(seasons_count))

    console.print(table)

    # Show SQL query reference
    console.print(f"\n[dim]PostgREST Queries:[/dim]")
    console.print(f"[dim italic]GET /teams?select=id&count=exact[/dim italic]")
    console.print(f"[dim italic]GET /games?select=id&count=exact[/dim italic]")
    console.print(f"[dim italic]GET /age_groups?select=id&count=exact[/dim italic]")
    console.print(f"[dim italic]GET /divisions?select=id&count=exact[/dim italic]")
    console.print(f"[dim italic]GET /seasons?select=id&count=exact[/dim italic]")


if __name__ == "__main__":
    app()

#!/usr/bin/env python3
"""
Database Inspector Tool

A powerful CLI tool for inspecting and troubleshooting database data.
Uses direct Supabase connection (bypassing DAOs) for raw data access.

Features:
- Browse age groups, divisions, teams, matches
- Filter and search data
- Identify duplicates and data issues
- Beautiful rich table output
- Environment-aware (local/dev/prod)

Usage:
    python inspect_db.py teams --age-group U14
    python inspect_db.py matches --team IFA --duplicates
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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    show_sql: bool = typer.Option(False, "--show-sql", help="Show SQL query for Supabase SQL Editor")
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
    if show_sql:
        sql_query = "SELECT *\nFROM age_groups\nORDER BY name ASC;"
        console.print(f"\n[cyan]SQL Query (copy to Supabase SQL Editor):[/cyan]")
        console.print(f"[white]{sql_query}[/white]")
    else:
        console.print(f"\n[dim]PostgREST Query:[/dim]")
        console.print(f"[dim italic]GET /age_groups?select=*&order=name.asc[/dim italic]")
        console.print(f"[dim]Tip: Use --show-sql to see SQL for Supabase SQL Editor[/dim]")


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
def matches(
    team: Optional[str] = typer.Option(None, "--team", "-t", help="Filter by team name"),
    age_group: Optional[str] = typer.Option(None, "--age-group", "-a", help="Filter by age group"),
    season: Optional[str] = typer.Option(None, "--season", "-s", help="Filter by season (e.g., 2025-2026)"),
    duplicates: bool = typer.Option(False, "--duplicates", "-d", help="Show only potential duplicates"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max number of matches to show"),
    show_sql: bool = typer.Option(False, "--show-sql", help="Show SQL query for Supabase SQL Editor"),
):
    """List matches with optional filtering"""
    load_environment()
    supabase = get_supabase_client()

    # Build query
    query = supabase.table("matches").select(
        "id, match_date, home_score, away_score, match_status, match_id, source, "
        "home_team:teams!matches_home_team_id_fkey(id, name), "
        "away_team:teams!matches_away_team_id_fkey(id, name), "
        "age_groups(id, name), "
        "seasons(id, name), "
        "match_types(id, name)"
    ).order("match_date", desc=True).limit(limit)

    response = query.execute()
    matches_data = response.data

    # Apply filters
    if team:
        matches_data = [
            m for m in matches_data
            if (m.get("home_team") and team.lower() in m["home_team"]["name"].lower()) or
               (m.get("away_team") and team.lower() in m["away_team"]["name"].lower())
        ]

    if age_group:
        matches_data = [
            m for m in matches_data
            if m.get("age_groups") and m["age_groups"]["name"] == age_group
        ]

    if season:
        matches_data = [
            m for m in matches_data
            if m.get("seasons") and season in m["seasons"]["name"]
        ]

    # Find duplicates if requested
    if duplicates:
        seen = {}
        duplicate_matches = []

        for match in matches_data:
            if not match.get("home_team") or not match.get("away_team"):
                continue

            # Create key for duplicate detection
            key = (
                match["match_date"],
                match.get("home_team", {}).get("id"),
                match.get("away_team", {}).get("id"),
                match.get("seasons", {}).get("id"),
                match.get("match_types", {}).get("id")
            )

            if key in seen:
                # Mark both as duplicates
                if seen[key] not in duplicate_matches:
                    duplicate_matches.append(seen[key])
                duplicate_matches.append(match)
            else:
                seen[key] = match

        matches_data = duplicate_matches

    # Create table
    title = f"Matches ({len(matches_data)})"
    if duplicates:
        title = f"[red]Duplicate Matches ({len(matches_data)})[/red]"

    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", width=5)
    table.add_column("Date", style="green", width=10)
    table.add_column("Home Team", style="yellow", width=18)
    table.add_column("Away Team", style="yellow", width=18)
    table.add_column("Score", style="white", width=7)
    table.add_column("Status", style="blue", width=9)
    table.add_column("Match ID", style="cyan", width=12)
    table.add_column("Age", style="blue", width=5)
    table.add_column("Season", style="magenta", width=9)
    table.add_column("Source", style="dim", width=7)

    for match in matches_data:
        match_date = match["match_date"][:10] if match.get("match_date") else "-"
        home_team_name = match.get("home_team", {}).get("name", "?")
        away_team_name = match.get("away_team", {}).get("name", "?")
        score = f"{match.get('home_score', '-')} - {match.get('away_score', '-')}"
        match_status = match.get("match_status", "scheduled")
        external_match_id = match.get("match_id", "-")
        age_group_name = match.get("age_groups", {}).get("name", "-")
        season_name = match.get("seasons", {}).get("name", "-")
        source_name = match.get("source", "manual")

        # Highlight duplicates
        style = "red" if duplicates else None

        table.add_row(
            str(match["id"]),
            match_date,
            home_team_name,
            away_team_name,
            score,
            match_status,
            str(external_match_id),
            age_group_name,
            season_name,
            source_name,
            style=style
        )

    console.print(table)

    if duplicates and matches_data:
        console.print(f"\n[red]Warning:[/red] Found {len(matches_data)} potential duplicate matches")
        console.print("[yellow]Duplicates are based on: same date, teams, season, and match type[/yellow]")
    else:
        console.print(f"\n[green]Total:[/green] {len(matches_data)} matches")

    # Show SQL query reference
    if show_sql:
        # Build SQL query
        sql_query = """SELECT
    m.id,
    m.match_date,
    m.home_score,
    m.away_score,
    m.match_status,
    m.match_id,
    m.source,
    ht.name AS home_team,
    at.name AS away_team,
    ag.name AS age_group,
    s.name AS season,
    mt.name AS match_type
FROM matches m
LEFT JOIN teams ht ON m.home_team_id = ht.id
LEFT JOIN teams at ON m.away_team_id = at.id
LEFT JOIN age_groups ag ON m.age_group_id = ag.id
LEFT JOIN seasons s ON m.season_id = s.id
LEFT JOIN match_types mt ON m.match_type_id = mt.id"""

        # Add WHERE clauses
        where_clauses = []
        if team:
            where_clauses.append(f"(ht.name ILIKE '%{team}%' OR at.name ILIKE '%{team}%')")
        if age_group:
            where_clauses.append(f"ag.name = '{age_group}'")
        if season:
            where_clauses.append(f"s.name LIKE '%{season}%'")

        if where_clauses:
            sql_query += "\nWHERE " + " AND ".join(where_clauses)

        sql_query += f"\nORDER BY m.match_date DESC\nLIMIT {limit};"

        console.print(f"\n[cyan]SQL Query (copy to Supabase SQL Editor):[/cyan]")
        console.print(f"[white]{sql_query}[/white]")
    else:
        select_clause = (
            "id, match_date, home_score, away_score, match_status, match_id, source, "
            "home_team:teams!matches_home_team_id_fkey(id, name), "
            "away_team:teams!matches_away_team_id_fkey(id, name), "
            "age_groups(id, name), seasons(id, name), match_types(id, name)"
        )
        filter_notes = []

        if age_group:
            filter_notes.append(f"age_groups.name = '{age_group}' (post-filter)")
        if season:
            filter_notes.append(f"seasons.name LIKE '%{season}%' (post-filter)")
        if team:
            filter_notes.append(f"teams.name ILIKE '%{team}%' (post-filter)")

        console.print(f"\n[dim]PostgREST Query:[/dim]")
        console.print(f"[dim italic]GET /matches?select={select_clause}&order=match_date.desc&limit={limit}[/dim italic]")

        if filter_notes:
            console.print(f"\n[dim]Additional Filters (applied client-side):[/dim]")
            for note in filter_notes:
                console.print(f"[dim italic]  - {note}[/dim italic]")

        console.print(f"[dim]Tip: Use --show-sql to see SQL for Supabase SQL Editor[/dim]")


@app.command()
def match_detail(
    match_id: int = typer.Argument(..., help="Match ID to inspect"),
    show_sql: bool = typer.Option(False, "--show-sql", help="Show SQL query for Supabase SQL Editor"),
):
    """Show detailed information about a specific match"""
    load_environment()
    supabase = get_supabase_client()

    response = supabase.table("matches").select(
        "*, "
        "home_team:teams!matches_home_team_id_fkey(id, name), "
        "away_team:teams!matches_away_team_id_fkey(id, name), "
        "age_groups(id, name), "
        "divisions(id, name), "
        "seasons(id, name), "
        "match_types(id, name)"
    ).eq("id", match_id).execute()

    if not response.data:
        console.print(f"[red]Error:[/red] Match {match_id} not found")
        raise typer.Exit(1)

    match = response.data[0]

    # Create detailed panel
    details = f"""
[cyan]Match ID:[/cyan] {match['id']}
[cyan]Date:[/cyan] {match.get('match_date', 'N/A')}
[cyan]Status:[/cyan] {match.get('match_status', 'scheduled')}
[cyan]Source:[/cyan] {match.get('source', 'manual')}

[yellow]Teams:[/yellow]
  Home: {match.get('home_team', {}).get('name', 'Unknown')} (ID: {match.get('home_team_id')})
  Away: {match.get('away_team', {}).get('name', 'Unknown')} (ID: {match.get('away_team_id')})

[yellow]Score:[/yellow]
  {match.get('home_score', 0)} - {match.get('away_score', 0)}

[yellow]Competition:[/yellow]
  Season: {match.get('seasons', {}).get('name', 'Unknown')}
  Age Group: {match.get('age_groups', {}).get('name', 'Unknown')}
  Division: {match.get('divisions', {}).get('name', 'Unknown') if match.get('divisions') else 'N/A'}
  Match Type: {match.get('match_types', {}).get('name', 'Unknown')}

[yellow]Metadata:[/yellow]
  Created: {match.get('created_at', 'N/A')}
  Updated: {match.get('updated_at', 'N/A')}
  Match ID: {match.get('match_id', 'N/A')}
"""

    console.print(Panel(details, title=f"Match {match_id} Details", border_style="green"))

    # Show SQL query reference
    if show_sql:
        sql_query = f"""SELECT
    m.*,
    ht.name AS home_team_name,
    at.name AS away_team_name,
    ag.name AS age_group_name,
    d.name AS division_name,
    s.name AS season_name,
    mt.name AS match_type_name
FROM matches m
LEFT JOIN teams ht ON m.home_team_id = ht.id
LEFT JOIN teams at ON m.away_team_id = at.id
LEFT JOIN age_groups ag ON m.age_group_id = ag.id
LEFT JOIN divisions d ON m.division_id = d.id
LEFT JOIN seasons s ON m.season_id = s.id
LEFT JOIN match_types mt ON m.match_type_id = mt.id
WHERE m.id = {match_id};"""
        console.print(f"\n[cyan]SQL Query (copy to Supabase SQL Editor):[/cyan]")
        console.print(f"[white]{sql_query}[/white]")
    else:
        select_clause = (
            "*, "
            "home_team:teams!matches_home_team_id_fkey(id, name), "
            "away_team:teams!matches_away_team_id_fkey(id, name), "
            "age_groups(id, name), divisions(id, name), seasons(id, name), match_types(id, name)"
        )
        console.print(f"\n[dim]PostgREST Query:[/dim]")
        console.print(f"[dim italic]GET /matches?select={select_clause}&id=eq.{match_id}[/dim italic]")
        console.print(f"[dim]Tip: Use --show-sql to see SQL for Supabase SQL Editor[/dim]")


@app.command()
def stats():
    """Show database statistics"""
    load_environment()
    supabase = get_supabase_client()

    # Get counts
    teams_count = len(supabase.table("teams").select("id", count="exact").execute().data)
    matches_count = len(supabase.table("matches").select("id", count="exact").execute().data)
    age_groups_count = len(supabase.table("age_groups").select("id", count="exact").execute().data)
    divisions_count = len(supabase.table("divisions").select("id", count="exact").execute().data)
    seasons_count = len(supabase.table("seasons").select("id", count="exact").execute().data)

    table = Table(title="Database Statistics", show_header=True, header_style="bold magenta")
    table.add_column("Table", style="cyan")
    table.add_column("Count", style="green", justify="right")

    table.add_row("Teams", str(teams_count))
    table.add_row("Matches", str(matches_count))
    table.add_row("Age Groups", str(age_groups_count))
    table.add_row("Divisions", str(divisions_count))
    table.add_row("Seasons", str(seasons_count))

    console.print(table)

    # Show SQL query reference
    console.print(f"\n[dim]PostgREST Queries:[/dim]")
    console.print(f"[dim italic]GET /teams?select=id&count=exact[/dim italic]")
    console.print(f"[dim italic]GET /matches?select=id&count=exact[/dim italic]")
    console.print(f"[dim italic]GET /age_groups?select=id&count=exact[/dim italic]")
    console.print(f"[dim italic]GET /divisions?select=id&count=exact[/dim italic]")
    console.print(f"[dim italic]GET /seasons?select=id&count=exact[/dim italic]")


if __name__ == "__main__":
    app()

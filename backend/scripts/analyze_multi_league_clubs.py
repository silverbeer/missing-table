#!/usr/bin/env python3
"""
Multi-League Club Analysis Script

Analyzes current database to identify clubs that appear in multiple leagues.
This helps determine which teams need to be split into parent club + child teams.

Usage:
    APP_ENV=local python scripts/analyze_multi_league_clubs.py
    APP_ENV=dev python scripts/analyze_multi_league_clubs.py
    python scripts/analyze_multi_league_clubs.py --env local --output report.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from supabase import create_client

app = typer.Typer()
console = Console()


def load_env_file(env: str) -> dict:
    """Load environment variables from .env.{env} file."""
    env_file = Path(__file__).parent.parent / f".env.{env}"

    if not env_file.exists():
        return {}

    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                value = value.strip().strip('"').strip("'")
                env_vars[key.strip()] = value

    return env_vars


def get_client(env: str):
    """Get Supabase client for environment."""
    env_vars = load_env_file(env)

    supabase_url = env_vars.get("SUPABASE_URL")
    supabase_key = (
        env_vars.get("SUPABASE_SERVICE_ROLE_KEY")
        or env_vars.get("SUPABASE_SERVICE_KEY")
        or env_vars.get("SUPABASE_KEY")
    )

    if not supabase_url or not supabase_key:
        return None

    return create_client(supabase_url, supabase_key)


def analyze_multi_league_clubs(client, env: str) -> dict:
    """Analyze database to find clubs in multiple leagues."""

    console.print(Panel.fit(f"[bold cyan]Multi-League Club Analysis: {env.upper()}[/bold cyan]", box=box.DOUBLE))

    analysis = {
        "environment": env,
        "timestamp": datetime.now().isoformat(),
        "summary": {},
        "teams": [],
        "multi_league_clubs": [],
        "standalone_teams": [],
        "recommendations": [],
    }

    # Check if leagues table exists
    has_leagues = False
    try:
        leagues_result = client.table("leagues").select("id, name").execute()
        has_leagues = True
        console.print("[green]✓ leagues table exists[/green]")
        analysis["summary"]["has_leagues_table"] = True
        analysis["summary"]["leagues"] = [{"id": l["id"], "name": l["name"]} for l in leagues_result.data]
    except Exception:
        console.print("[yellow]- leagues table does NOT exist[/yellow]")
        analysis["summary"]["has_leagues_table"] = False
        analysis["summary"]["leagues"] = []

    # Get all teams
    console.print("\n[bold]Fetching teams...[/bold]")
    teams_result = client.table("teams").select("id, name, city, academy_team").execute()
    teams = teams_result.data

    console.print(f"Found {len(teams)} teams")
    analysis["summary"]["total_teams"] = len(teams)

    # Get team mappings with divisions
    console.print("[bold]Analyzing team mappings...[/bold]")

    if has_leagues:
        # Query with leagues
        mappings_result = (
            client.table("team_mappings")
            .select("team_id, age_group_id, division_id, divisions(id, name, league_id, leagues(id, name))")
            .execute()
        )
    else:
        # Query without leagues
        mappings_result = (
            client.table("team_mappings").select("team_id, age_group_id, division_id, divisions(id, name)").execute()
        )

    mappings = mappings_result.data

    # Build team analysis
    team_info = {}
    for team in teams:
        team_id = team["id"]
        team_info[team_id] = {
            "id": team_id,
            "name": team["name"],
            "city": team["city"],
            "academy_team": team.get("academy_team", False),
            "divisions": [],
            "leagues": set(),
            "age_groups": set(),
        }

    # Process mappings
    for mapping in mappings:
        team_id = mapping["team_id"]
        if team_id not in team_info:
            continue

        division = mapping.get("divisions", {})
        if not division:
            continue

        division_name = division.get("name", "Unknown")

        if has_leagues:
            league = division.get("leagues", {})
            if league:
                league_name = league.get("name", "Unknown")
                team_info[team_id]["leagues"].add(league_name)
                team_info[team_id]["divisions"].append({"division": division_name, "league": league_name})
        else:
            team_info[team_id]["divisions"].append({"division": division_name, "league": "N/A"})

        team_info[team_id]["age_groups"].add(mapping.get("age_group_id"))

    # Identify multi-league clubs
    console.print("\n[bold]Identifying multi-league clubs...[/bold]")

    multi_league = []
    standalone = []

    for _team_id, info in team_info.items():
        info["leagues"] = list(info["leagues"])
        info["age_groups"] = list(info["age_groups"])
        info["league_count"] = len(info["leagues"]) if has_leagues else 0

        analysis["teams"].append(info)

        if has_leagues and len(info["leagues"]) > 1:
            multi_league.append(info)
        elif not info["divisions"]:
            standalone.append(info)
        else:
            standalone.append(info)

    # Display results
    console.print("\n[bold]Results:[/bold]")
    console.print(f"Total teams: {len(teams)}")
    console.print(f"Multi-league clubs: [cyan]{len(multi_league)}[/cyan]")
    console.print(f"Standalone/single-league teams: {len(standalone)}")

    analysis["summary"]["multi_league_count"] = len(multi_league)
    analysis["summary"]["standalone_count"] = len(standalone)
    analysis["multi_league_clubs"] = multi_league
    analysis["standalone_teams"] = standalone

    # Show multi-league clubs
    if multi_league:
        console.print("\n[bold yellow]⚠️  Clubs in Multiple Leagues:[/bold yellow]")

        table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        table.add_column("ID", style="dim")
        table.add_column("Team Name", style="bold")
        table.add_column("City")
        table.add_column("Leagues", style="yellow")
        table.add_column("# Divisions")

        for club in multi_league:
            table.add_row(
                str(club["id"]),
                club["name"],
                club["city"] or "N/A",
                ", ".join(club["leagues"]),
                str(len(club["divisions"])),
            )

        console.print(table)

        # Recommendations
        console.print("\n[bold]Recommendations:[/bold]")
        for club in multi_league:
            rec = f"Split '{club['name']}' into:"
            for league in club["leagues"]:
                rec += f"\n  - {club['name']} {league}"
            analysis["recommendations"].append(
                {
                    "team_id": club["id"],
                    "team_name": club["name"],
                    "action": "split",
                    "suggested_names": [f"{club['name']} {league}" for league in club["leagues"]],
                }
            )
            console.print(f"  • {rec}")
    else:
        console.print("\n[green]✓ No clubs found in multiple leagues[/green]")
        analysis["recommendations"].append({"message": "No multi-league clubs found. No data migration needed."})

    # Show sample of teams
    console.print("\n[bold]Sample Teams:[/bold]")
    sample_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    sample_table.add_column("ID", style="dim", width=5)
    sample_table.add_column("Name")
    sample_table.add_column("City")
    sample_table.add_column("Academy", width=8)
    sample_table.add_column("Leagues/Divisions")

    for team in list(team_info.values())[:10]:
        if has_leagues:
            leagues_str = ", ".join(team["leagues"]) if team["leagues"] else "None"
        else:
            leagues_str = f"{len(team['divisions'])} div(s)"

        sample_table.add_row(
            str(team["id"]),
            team["name"],
            team["city"] or "N/A",
            "✓" if team["academy_team"] else "",
            leagues_str,
        )

    console.print(sample_table)

    return analysis


@app.command()
def analyze(
    env: str = typer.Option("local", "--env", "-e", help="Environment to analyze"),
    output: str = typer.Option(None, "--output", "-o", help="Save JSON report to file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """Analyze database to identify clubs in multiple leagues."""

    client = get_client(env)
    if not client:
        console.print(f"[red]Could not connect to {env} environment[/red]")
        console.print("Make sure .env.{env} file exists with valid credentials")
        raise typer.Exit(1)

    # Run analysis
    analysis = analyze_multi_league_clubs(client, env)

    # Save to file if requested
    if output:
        output_path = Path(output)
        output_path.write_text(json.dumps(analysis, indent=2))
        console.print(f"\n[green]✓ Report saved to: {output}[/green]")

    # Show summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"Environment: {env}")
    console.print(f"Total teams: {analysis['summary']['total_teams']}")
    console.print(f"Multi-league clubs: {analysis['summary']['multi_league_count']}")

    if analysis["summary"]["multi_league_count"] > 0:
        console.print("\n[yellow]⚠️  Migration required for multi-league clubs[/yellow]")
        console.print("Run the migration script to split these clubs into parent + child teams")
    else:
        console.print("\n[green]✓ No migration needed[/green]")


if __name__ == "__main__":
    app()

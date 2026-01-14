#!/usr/bin/env python3
"""
Team Management CLI Tool

This tool manages teams via CSV import/export using the backend API.
Supports importing teams from CSV and exporting current teams to CSV.

Usage:
    python manage_teams.py export-teams <csv_file>    # Export teams to CSV
    python manage_teams.py import-teams <csv_file>    # Import teams from CSV
    python manage_teams.py list                       # List all teams
"""

import csv
import os
from pathlib import Path
from typing import Any

import requests
import typer
from rich import box
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

from models.teams import Team

# Initialize Typer app and Rich console
app = typer.Typer(help="Team Management CLI Tool")
console = Console()

# API Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")


# ============================================================================
# Authentication & API Helper Functions
# ============================================================================

def get_auth_token() -> str:
    """Get authentication token for API requests."""
    # For local development, use admin credentials
    env = os.getenv("APP_ENV", "local")

    # Load environment file from backend directory
    backend_dir = Path(__file__).parent
    env_file = backend_dir / f".env.{env}"

    if env_file.exists():
        # Load environment variables from file
        with open(env_file) as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

    # Try to login as admin user
    username = "tom"
    password = os.getenv("TEST_USER_PASSWORD_TOM", "admin123")

    response = requests.post(
        f"{API_URL}/api/auth/login",
        json={"username": username, "password": password},
        headers={"Content-Type": "application/json"}
    )

    if response.status_code == 200:
        data = response.json()
        return data["access_token"]
    else:
        console.print(f"[red]❌ Authentication failed: {response.text}[/red]")
        raise typer.Exit(code=1)


def api_request(
    method: str,
    endpoint: str,
    token: str,
    data: dict[str, Any] | None = None
) -> requests.Response:
    """Make an authenticated API request."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    url = f"{API_URL}{endpoint}"

    if method.upper() == "GET":
        response = requests.get(url, headers=headers)
    elif method.upper() == "POST":
        response = requests.post(url, headers=headers, json=data)
    elif method.upper() == "PUT":
        response = requests.put(url, headers=headers, json=data)
    elif method.upper() == "DELETE":
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")

    return response


# ============================================================================
# Data Fetching Functions
# ============================================================================

def get_all_teams(token: str) -> list[dict]:
    """Fetch all teams from the API."""
    response = api_request("GET", "/api/teams", token)
    if response.status_code == 200:
        return response.json()
    else:
        console.print(f"[red]❌ Failed to fetch teams: {response.text}[/red]")
        return []


def get_all_clubs(token: str) -> list[dict]:
    """Fetch all clubs for lookup."""
    response = api_request("GET", "/api/clubs", token)
    if response.status_code == 200:
        return response.json()
    else:
        console.print(f"[red]❌ Failed to fetch clubs: {response.text}[/red]")
        return []


def get_all_age_groups(token: str) -> list[dict]:
    """Fetch all age groups for lookup."""
    response = api_request("GET", "/api/age-groups", token)
    if response.status_code == 200:
        return response.json()
    else:
        console.print(f"[red]❌ Failed to fetch age groups: {response.text}[/red]")
        return []


def get_all_match_types(token: str) -> list[dict]:
    """Fetch all match types for lookup."""
    response = api_request("GET", "/api/match-types", token)
    if response.status_code == 200:
        return response.json()
    else:
        console.print(f"[red]❌ Failed to fetch match types: {response.text}[/red]")
        return []


# ============================================================================
# Export Functions
# ============================================================================

def determine_team_type(club_name: str, academy_team: bool) -> str:
    """Determine team type based on club affiliation and academy status."""
    if not club_name:
        return "Guest Team"
    elif academy_team:
        return "Tournament Team"  # Academy teams are typically tournament-focused
    else:
        return "League Team"


@app.command()
def export_teams(csv_file: str, club: str | None = typer.Option(None, "--club", help="Filter by club name (case-insensitive)")):
    """
    Export all teams to a CSV file.

    The CSV will contain: name,city,club_name,team_type,age_groups,match_types,academy_team

    Use --club to filter teams by club name (case-insensitive partial match).
    """
    console.print("[bold cyan]📤 Team Export Tool[/bold cyan]")
    console.print(f"📁 Exporting to: {csv_file}")
    if club:
        console.print(f"🏟️  Filtering by club: {club}")
    console.print("[bold cyan]📤 Team Export Tool[/bold cyan]")
    console.print(f"📁 Exporting to: {csv_file}")

    # Authenticate
    with console.status("[bold yellow]🔐 Authenticating...", spinner="dots"):
        token = get_auth_token()
    console.print("✅ Authenticated as admin")

    # Fetch all data
    with console.status("[bold yellow]📡 Fetching teams and related data...", spinner="dots"):
        teams = get_all_teams(token)
        clubs = get_all_clubs(token)
        age_groups = get_all_age_groups(token)
        match_types = get_all_match_types(token)

    console.print(f"✅ Found {len(teams)} teams, {len(clubs)} clubs, {len(age_groups)} age groups, {len(match_types)} match types")

    # Create lookup dictionaries
    club_lookup = {club["id"]: club["name"] for club in clubs}
    age_group_lookup = {ag["id"]: ag["name"] for ag in age_groups}
    match_type_lookup = {mt["id"]: mt["name"] for mt in match_types}

    # Filter teams by club if specified
    if club:
        original_count = len(teams)
        teams = [team for team in teams if club_lookup.get(team.get("club_id"), "").lower().find(club.lower()) != -1]
        console.print(f"✅ Filtered to {len(teams)} teams from clubs matching '{club}' (was {original_count})")

    if not teams:
        filter_msg = f" matching '{club}'" if club else ""
        console.print(f"[yellow]⚠️  No teams found{filter_msg} to export[/yellow]")
        return

    # Prepare CSV data
    csv_data = []
    processed_teams = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        task = progress.add_task("[cyan]Processing teams...", total=len(teams))

        for team in teams:
            team_id = team["id"]
            team_name = team["name"]
            city = team.get("city", "")
            club_id = team.get("club_id")
            academy_team = team.get("academy_team", False)

            # Get club name
            club_name = club_lookup.get(club_id, "") if club_id else ""

            # Get age group names from the team's age_groups array
            age_groups_list = team.get("age_groups", [])
            age_group_names = [ag["name"] for ag in age_groups_list]
            age_groups_str = ",".join(sorted(age_group_names))

            # Determine team type based on club and academy status
            team_type = determine_team_type(club_name, academy_team)

            # For now, default to "Friendly" for match types
            # TODO: Fetch actual match type data from team_match_types table
            match_types_str = "Friendly"

            # Add to CSV data
            csv_data.append({
                "name": team_name,
                "city": city,
                "club_name": club_name,
                "team_type": team_type,
                "age_groups": age_groups_str,
                "match_types": match_types_str,
                "academy_team": str(academy_team).lower()
            })

            processed_teams += 1
            progress.update(task, advance=1, description=f"[cyan]Processed {processed_teams}/{len(teams)} teams...")

    # Write to CSV
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            if csv_data:
                fieldnames = ["name", "city", "club_name", "team_type", "age_groups", "match_types", "academy_team"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_data)

        console.print(f"✅ Successfully exported {len(csv_data)} teams to {csv_file}")

        # Show sample of exported data
        if csv_data:
            console.print("\n[bold]Sample exported data:[/bold]")
            table = Table(box=box.ROUNDED)
            table.add_column("Name", style="cyan")
            table.add_column("City", style="magenta")
            table.add_column("Club", style="green")
            table.add_column("Team Type", style="yellow")
            table.add_column("Age Groups", style="blue")
            table.add_column("Match Types", style="red")

            for row in csv_data[:5]:  # Show first 5 rows
                table.add_row(
                    row["name"][:30] + "..." if len(row["name"]) > 30 else row["name"],
                    row["city"][:20] + "..." if len(row["city"]) > 20 else row["city"],
                    row["club_name"][:20] + "..." if len(row["club_name"]) > 20 else row["club_name"],
                    row["team_type"],
                    row["age_groups"],
                    row["match_types"]
                )
            console.print(table)

    except Exception as e:
        console.print(f"[red]❌ Failed to write CSV file: {e}[/red]")
        raise typer.Exit(code=1)


# ============================================================================
# List Command
# ============================================================================

@app.command()
def list():
    """List all teams in a table format."""
    console.print("[bold cyan]📋 Team List[/bold cyan]")

    # Authenticate
    with console.status("[bold yellow]🔐 Authenticating...", spinner="dots"):
        token = get_auth_token()
    console.print("✅ Authenticated as admin")

    # Fetch data
    with console.status("[bold yellow]📡 Fetching teams...", spinner="dots"):
        teams = get_all_teams(token)
        clubs = get_all_clubs(token)

    console.print(f"✅ Found {len(teams)} teams")

    if not teams:
        console.print("[yellow]⚠️  No teams found[/yellow]")
        return

    # Create lookup
    club_lookup = {club["id"]: club["name"] for club in clubs}

    # Display table
    table = Table(box=box.ROUNDED)
    table.add_column("ID", style="dim", width=6)
    table.add_column("Name", style="cyan", width=25)
    table.add_column("City", style="magenta", width=20)
    table.add_column("Club", style="green", width=20)
    table.add_column("Academy", style="yellow", width=8)

    for team in teams[:50]:  # Limit to first 50 for readability
        club_name = club_lookup.get(team.get("club_id"), "") if team.get("club_id") else ""
        academy = "Yes" if team.get("academy_team") else "No"

        table.add_row(
            str(team["id"]),
            team["name"][:24] + "..." if len(team["name"]) > 24 else team["name"],
            team.get("city", "")[:19] + "..." if len(team.get("city", "")) > 19 else team.get("city", ""),
            club_name[:19] + "..." if len(club_name) > 19 else club_name,
            academy
        )

    console.print(table)

    if len(teams) > 50:
        console.print(f"\n[dim]Showing first 50 of {len(teams)} teams[/dim]")


if __name__ == "__main__":
    app()
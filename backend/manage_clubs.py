#!/usr/bin/env python3
"""
Club and Team Management CLI Tool

This tool manages clubs and teams based on clubs.json file.
Uses the backend API to create, update, and delete clubs and teams.

Usage:
    python manage_clubs.py sync              # Sync clubs.json to database
    python manage_clubs.py list              # List all clubs and teams
    python manage_clubs.py delete-club <id>  # Delete a club
    python manage_clubs.py delete-team <id>  # Delete a team
"""

import json
import os
from pathlib import Path
from typing import Any

import requests
import typer
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

from models.clubs import ClubData, TeamData, load_clubs_from_json

# Initialize Typer app and Rich console
app = typer.Typer(help="Club and Team Management CLI Tool")
console = Console()

# API Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
CLUBS_JSON_PATH = Path(__file__).parent.parent / "clubs.json"


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
    load_dotenv(env_file)

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
# Data Loading Functions
# ============================================================================

def load_clubs_json() -> list[ClubData]:
    """Load and validate clubs data from clubs.json file."""
    if not CLUBS_JSON_PATH.exists():
        console.print(f"[red]❌ clubs.json not found at: {CLUBS_JSON_PATH}[/red]")
        raise typer.Exit(code=1)

    with open(CLUBS_JSON_PATH) as f:
        clubs_raw = json.load(f)

    try:
        clubs = load_clubs_from_json(clubs_raw)
        return clubs
    except Exception as e:
        console.print(f"[red]❌ Error parsing clubs.json: {e}[/red]")
        raise typer.Exit(code=1)


def get_league_id_by_name(token: str, league_name: str) -> int | None:
    """Get league ID by name."""
    response = api_request("GET", "/api/leagues", token)

    if response.status_code == 200:
        leagues = response.json()
        for league in leagues:
            if league["name"].lower() == league_name.lower():
                return league["id"]

    return None


def get_division_id_by_name_and_league(
    token: str,
    division_name: str,
    league_id: int
) -> int | None:
    """Get division ID by name within a specific league.

    Args:
        token: Authentication token
        division_name: Division name (e.g., "Northeast Division", "New England Conference")
        league_id: League ID to filter divisions

    Returns:
        Division ID if found, None otherwise
    """
    response = api_request("GET", f"/api/divisions?league_id={league_id}", token)

    if response.status_code == 200:
        divisions = response.json()
        for division in divisions:
            if division["name"].lower() == division_name.lower():
                return division["id"]

    return None


def get_age_group_ids_by_names(
    token: str,
    age_group_names: list[str]
) -> list[int]:
    """Get age group IDs by names.

    Args:
        token: Authentication token
        age_group_names: List of age group names (e.g., ["U13", "U14", "U15"])

    Returns:
        List of age group IDs that were found (may be shorter than input list)
    """
    response = api_request("GET", "/api/age-groups", token)

    if response.status_code == 200:
        age_groups = response.json()
        # Create a case-insensitive mapping
        age_group_map = {ag["name"].lower(): ag["id"] for ag in age_groups}

        # Look up each requested age group
        ids = []
        for name in age_group_names:
            ag_id = age_group_map.get(name.lower())
            if ag_id:
                ids.append(ag_id)
            else:
                console.print(f"[yellow]⚠️  Age group not found: {name}[/yellow]")

        return ids

    return []


# ============================================================================
# Club Management Functions
# ============================================================================

def get_all_clubs(token: str) -> list[dict[str, Any]]:
    """Fetch all clubs from the API."""
    # Note: include_teams may fail if teams.club_id column doesn't exist yet
    # Try without teams first as a fallback
    response = api_request("GET", "/api/clubs?include_teams=false", token)

    if response.status_code == 200:
        clubs = response.json()
        # Handle both list and dict responses
        if isinstance(clubs, dict):
            # If API returns a dict, it might be wrapped or have errors
            if 'data' in clubs:
                return clubs['data']
            elif 'clubs' in clubs:
                return clubs['clubs']
            else:
                # Log the unexpected format for debugging
                console.print(f"[yellow]⚠️  Unexpected clubs response format: {type(clubs)}[/yellow]")
                return []
        # Return clubs if it's a list, otherwise empty list
        if type(clubs).__name__ == 'list':
            return clubs
        return []
    else:
        console.print(f"[red]❌ Failed to fetch clubs (status {response.status_code}): {response.text}[/red]")
        return []


def find_club_by_name(token: str, club_name: str) -> dict[str, Any] | None:
    """Find a club by name."""
    clubs = get_all_clubs(token)
    for club in clubs:
        if club["name"].lower() == club_name.lower():
            return club
    return None


def create_club(token: str, club: ClubData) -> dict[str, Any] | None:
    """Create a new club."""
    payload = {
        "name": club.club_name,
        "city": club.location,
        "website": club.website,
        "description": f"Club based in {club.location}",
        "is_active": True
    }

    response = api_request("POST", "/api/clubs", token, data=payload)

    if response.status_code == 200:
        return response.json()
    elif "already exists" in response.text.lower():
        # Club already exists - this is OK for idempotent operation
        # Return a dummy club object so caller knows it exists
        return {"name": club.club_name, "exists": True}
    else:
        console.print(f"[red]❌ Failed to create club '{club.club_name}': {response.text}[/red]")
        return None


def update_club(token: str, club_id: int, club: ClubData) -> bool:
    """Update an existing club."""
    payload = {
        "name": club.club_name,
        "city": club.location,
        "website": club.website,
        "description": f"Club based in {club.location}",
        "is_active": True
    }

    response = api_request("PUT", f"/api/clubs/{club_id}", token, data=payload)

    if response.status_code == 200:
        return True
    else:
        console.print(f"[yellow]⚠️  Failed to update club (ID: {club_id}): {response.text}[/yellow]")
        return False


# ============================================================================
# Team Management Functions
# ============================================================================

def get_all_teams(token: str) -> list[dict[str, Any]]:
    """Fetch all teams from the API."""
    response = api_request("GET", "/api/teams?include_parent=true", token)

    if response.status_code == 200:
        return response.json()
    else:
        console.print(f"[red]❌ Failed to fetch teams: {response.text}[/red]")
        return []


def find_team_by_name_and_division(
    token: str,
    team_name: str,
    division_id: int,
    club_id: int | None = None
) -> dict[str, Any] | None:
    """Find a team by name and division ID.

    Teams are uniquely identified by (name, division_id).
    Optionally filter by club_id for additional specificity.
    """
    teams = get_all_teams(token)

    for team in teams:
        # Match by team name and division_id
        if (team["name"].lower() == team_name.lower() and
            team.get("division_id") == division_id):
            # If club_id specified, also match on that
            if club_id is not None:
                if team.get("club_id") == club_id:
                    return team
            else:
                return team

    return None


def create_team(
    token: str,
    team: TeamData,
    club_id: int,
    is_pro_academy: bool = False
) -> dict[str, Any] | None:
    """Create a new team with league, division, and age groups.

    Args:
        token: Authentication token
        team: TeamData model with all team information
        club_id: Parent club ID
        is_pro_academy: Whether this club is a Pro Academy (all teams inherit this)

    Returns:
        Created team data or None on failure
    """
    # Look up league ID
    league_id = get_league_id_by_name(token, team.league)
    if not league_id:
        console.print(f"[red]❌ League not found: {team.league}[/red]")
        return None

    # Look up division ID (required by API)
    division_name = team.division_or_conference
    if not division_name:
        console.print(f"[yellow]⚠️  No division/conference specified for team: {team.team_name}. Skipping team creation.[/yellow]")
        return None

    division_id = get_division_id_by_name_and_league(token, division_name, league_id)
    if not division_id:
        console.print(f"[red]❌ Division/conference not found: {division_name} (in league: {team.league})[/red]")
        return None

    # Look up age group IDs (required by API - at least one)
    if not team.age_groups:
        console.print(f"[yellow]⚠️  No age groups specified for team: {team.team_name}. Skipping team creation.[/yellow]")
        return None

    age_group_ids = get_age_group_ids_by_names(token, team.age_groups)
    if not age_group_ids:
        console.print(f"[yellow]⚠️  No valid age groups found for team: {team.team_name}. Skipping team creation.[/yellow]")
        return None

    # Build payload for team creation
    payload = {
        "name": team.team_name,
        "city": "",  # City will be inherited from club
        "age_group_ids": age_group_ids,
        "division_id": division_id,
        "club_id": club_id,  # Always set parent club - every team belongs to a club
        "academy_team": is_pro_academy  # Inherited from club level - only true for Pro Academy clubs
    }

    response = api_request("POST", "/api/teams", token, data=payload)

    if response.status_code == 200:
        result = response.json()
        return result
    elif response.status_code == 409 or "already exists" in response.text.lower() or "duplicate" in response.text.lower():
        # Team already exists - this is OK for idempotent operation
        return {"name": team.team_name, "exists": True}
    else:
        # Only print error if it's not a simple "already exists" situation
        console.print(f"[red]❌ Failed to create team '{team.team_name}': {response.text}[/red]")
        return None


def update_team(
    token: str,
    team_id: int,
    team_name: str,
    league_name: str,
    club_id: int,
    is_pro_academy: bool = False
) -> bool:
    """Update an existing team.

    Updates club_id relationship and academy_team flag.
    The academy_team flag is updated to match the club's is_pro_academy value.
    """
    payload = {
        "name": team_name,
        "city": "",  # Required field
        "club_id": club_id,
        "academy_team": is_pro_academy  # Update to match club's is_pro_academy value
    }

    response = api_request("PUT", f"/api/teams/{team_id}", token, data=payload)

    if response.status_code == 200:
        return True
    else:
        console.print(f"[yellow]⚠️  Failed to update team (ID: {team_id}): {response.text}[/yellow]")
        return False


# ============================================================================
# Sync Command - Main Logic
# ============================================================================

@app.command()
def sync(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without making changes")
):
    """
    Sync clubs and teams from clubs.json to the database.

    This command:
    1. Reads clubs.json
    2. Creates or updates clubs
    3. Creates or updates teams under each club
    4. Can be run repeatedly (idempotent)
    """
    console.print("[bold cyan]🔄 Club & Team Sync Tool[/bold cyan]")
    console.print(f"📁 Reading: {CLUBS_JSON_PATH}")

    if dry_run:
        console.print("[yellow]🏃 DRY RUN MODE - No changes will be made[/yellow]\n")

    # Load clubs data
    clubs_data = load_clubs_json()
    console.print(f"✅ Loaded {len(clubs_data)} clubs from JSON\n")

    # Authenticate
    with console.status("[bold yellow]🔐 Authenticating...", spinner="dots"):
        token = get_auth_token()
    console.print("✅ Authenticated as admin\n")

    # Fetch all clubs, teams, leagues, divisions, and age groups ONCE (optimization to prevent N+1 API calls)
    with console.status("[bold yellow]📡 Fetching existing data from API...", spinner="dots"):
        all_clubs = get_all_clubs(token)
        all_teams = get_all_teams(token)

        # Fetch leagues and create lookup dict
        leagues_response = api_request("GET", "/api/leagues", token)
        all_leagues = leagues_response.json() if leagues_response.status_code == 200 else []
        league_lookup = {league["name"].lower(): league["id"] for league in all_leagues}

        # Fetch all divisions (we'll filter by league as needed)
        divisions_response = api_request("GET", "/api/divisions", token)
        all_divisions = divisions_response.json() if divisions_response.status_code == 200 else []

        # Fetch age groups and create lookup dict
        age_groups_response = api_request("GET", "/api/age-groups", token)
        all_age_groups = age_groups_response.json() if age_groups_response.status_code == 200 else []
        age_group_lookup = {ag["name"].lower(): ag["id"] for ag in all_age_groups}

    console.print(f"✅ Found {len(all_clubs)} clubs, {len(all_teams)} teams, {len(all_leagues)} leagues, {len(all_divisions)} divisions\n")

    # Statistics
    stats = {
        "clubs_created": 0,
        "clubs_updated": 0,
        "clubs_unchanged": 0,
        "teams_created": 0,
        "teams_updated": 0,
        "teams_unchanged": 0,
        "errors": 0
    }

    # Process each club
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        task = progress.add_task("[cyan]Processing clubs...", total=len(clubs_data))

        for club in clubs_data:
            progress.update(task, description=f"[cyan]Processing {club.club_name}...")

            # Check if club exists (search in-memory cache)
            existing_club = next(
                (c for c in all_clubs if c["name"].lower() == club.club_name.lower()),
                None
            )

            if existing_club:
                # Club exists - check if update needed
                needs_update = (
                    existing_club.get("city") != club.location or
                    existing_club.get("website") != club.website
                )

                if needs_update and not dry_run:
                    if update_club(token, existing_club["id"], club):
                        console.print(f"  [blue]🔄 Updated club: {club.club_name}[/blue]")
                        stats["clubs_updated"] += 1
                    else:
                        stats["errors"] += 1
                elif needs_update and dry_run:
                    console.print(f"  [blue]🔄 Would update club: {club.club_name}[/blue]")
                    stats["clubs_updated"] += 1
                else:
                    console.print(f"  [dim]✓ Club unchanged: {club.club_name}[/dim]")
                    stats["clubs_unchanged"] += 1

                club_id = existing_club["id"]
            else:
                # Create new club
                if not dry_run:
                    new_club = create_club(token, club)
                    if new_club:
                        if new_club.get("exists"):
                            # Club already exists (caught the duplicate error)
                            console.print(f"  [dim]✓ Club already exists: {club.club_name}[/dim]")
                            stats["clubs_unchanged"] += 1
                            # Find the club to get its ID for team processing (search in-memory cache)
                            found_club = next(
                                (c for c in all_clubs if c["name"].lower() == club.club_name.lower()),
                                None
                            )
                            club_id = found_club["id"] if found_club else None
                        else:
                            console.print(f"  [green]✨ Created club: {club.club_name}[/green]")
                            stats["clubs_created"] += 1
                            club_id = new_club.get("id")
                    else:
                        stats["errors"] += 1
                        progress.update(task, advance=1)
                        continue
                else:
                    console.print(f"  [green]✨ Would create club: {club.club_name}[/green]")
                    stats["clubs_created"] += 1
                    club_id = None  # Can't process teams in dry run without club ID

            # Process teams for this club
            for team in club.teams:

                if dry_run and club_id is None:
                    console.print(f"    [dim]→ Would create team: {team.team_name} ({team.league})[/dim]")
                    stats["teams_created"] += 1
                    continue

                # Look up division_id for this team (use cached data)
                league_id = league_lookup.get(team.league.lower())
                if not league_id:
                    console.print(f"[yellow]⚠️  League not found: {team.league}. Skipping team: {team.team_name}[/yellow]")
                    stats["errors"] += 1
                    continue

                division_name = team.division_or_conference
                if not division_name:
                    console.print(f"[yellow]⚠️  No division/conference for team: {team.team_name}. Skipping.[/yellow]")
                    stats["errors"] += 1
                    continue

                # Find division in cached data
                division_id = None
                for div in all_divisions:
                    if div["name"].lower() == division_name.lower() and div.get("league_id") == league_id:
                        division_id = div["id"]
                        break

                if not division_id:
                    console.print(f"[yellow]⚠️  Division '{division_name}' not found in league '{team.league}'. Skipping team: {team.team_name}[/yellow]")
                    stats["errors"] += 1
                    continue

                # Check if team exists (search in-memory cache using division_id)
                existing_team = None
                for t in all_teams:
                    if (t["name"].lower() == team.team_name.lower() and
                        t.get("division_id") == division_id):
                        # If club_id specified, also match on that
                        if club_id is not None:
                            if t.get("club_id") == club_id:
                                existing_team = t
                                break
                        else:
                            existing_team = t
                            break

                if existing_team:
                    # Team exists - check if update needed
                    needs_update = (
                        existing_team.get("club_id") != club_id or
                        existing_team.get("academy_team") != club.is_pro_academy
                    )

                    if needs_update and not dry_run:
                        if update_team(token, existing_team["id"], team.team_name, team.league, club_id, club.is_pro_academy):
                            console.print(f"    [blue]🔄 Updated team: {team.team_name} ({team.league})[/blue]")
                            stats["teams_updated"] += 1
                        else:
                            stats["errors"] += 1
                    elif needs_update and dry_run:
                        console.print(f"    [blue]🔄 Would update team: {team.team_name} ({team.league})[/blue]")
                        stats["teams_updated"] += 1
                    else:
                        console.print(f"    [dim]✓ Team unchanged: {team.team_name} ({team.league})[/dim]")
                        stats["teams_unchanged"] += 1
                else:
                    # Create new team (use cached data to avoid N+1 API calls)
                    if not dry_run:
                        # Look up age group IDs from cached data
                        if not team.age_groups:
                            console.print(f"[yellow]⚠️  No age groups specified for team: {team.team_name}. Skipping team creation.[/yellow]")
                            stats["errors"] += 1
                            continue

                        age_group_ids = []
                        for ag_name in team.age_groups:
                            ag_id = age_group_lookup.get(ag_name.lower())
                            if ag_id:
                                age_group_ids.append(ag_id)
                            else:
                                console.print(f"[yellow]⚠️  Age group not found: {ag_name}[/yellow]")

                        if not age_group_ids:
                            console.print(f"[yellow]⚠️  No valid age groups found for team: {team.team_name}. Skipping team creation.[/yellow]")
                            stats["errors"] += 1
                            continue

                        # Build payload and create team directly
                        payload = {
                            "name": team.team_name,
                            "city": "",
                            "age_group_ids": age_group_ids,
                            "division_id": division_id,
                            "club_id": club_id,
                            "academy_team": club.is_pro_academy
                        }

                        response = api_request("POST", "/api/teams", token, data=payload)
                        new_team = response.json() if response.status_code == 200 else None

                        if response.status_code == 200 or response.status_code == 409 or "already exists" in response.text.lower():
                            if response.status_code == 409 or "already exists" in response.text.lower():
                                new_team = {"exists": True}

                        if new_team:
                            if new_team.get("exists"):
                                # Team already exists (caught the duplicate error)
                                # Need to update it to set club_id
                                console.print(f"    [dim]✓ Team already exists: {team.team_name} ({team.league})[/dim]")

                                # Find the existing team and update club_id if needed (search in-memory cache)
                                existing = None
                                for t in all_teams:
                                    if (t["name"].lower() == team.team_name.lower() and
                                        t.get("division_id") == division_id):
                                        existing = t
                                        break

                                if existing and existing.get("club_id") != club_id:
                                    if update_team(token, existing["id"], team.team_name, team.league, club_id, club.is_pro_academy):
                                        console.print("    [blue]  └─ Updated parent club link[/blue]")
                                        stats["teams_updated"] += 1
                                    else:
                                        stats["errors"] += 1
                                else:
                                    stats["teams_unchanged"] += 1
                            else:
                                # Team was newly created with club_id already set
                                console.print(f"    [green]✨ Created team: {team.team_name} ({team.league})[/green]")
                                stats["teams_created"] += 1
                        else:
                            stats["errors"] += 1
                    else:
                        console.print(f"    [green]✨ Would create team: {team.team_name} ({team.league})[/green]")
                        stats["teams_created"] += 1

            progress.update(task, advance=1)

    # Print summary
    console.print("\n[bold green]" + "=" * 60 + "[/bold green]")
    console.print("[bold green]📊 Sync Summary[/bold green]")
    console.print("[bold green]" + "=" * 60 + "[/bold green]")

    summary_table = Table(show_header=False, box=box.SIMPLE)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Count", style="green", justify="right")

    summary_table.add_row("Clubs Created", str(stats["clubs_created"]))
    summary_table.add_row("Clubs Updated", str(stats["clubs_updated"]))
    summary_table.add_row("Clubs Unchanged", str(stats["clubs_unchanged"]))
    summary_table.add_row("Teams Created", str(stats["teams_created"]))
    summary_table.add_row("Teams Updated", str(stats["teams_updated"]))
    summary_table.add_row("Teams Unchanged", str(stats["teams_unchanged"]))

    if stats["errors"] > 0:
        summary_table.add_row("Errors", f"[red]{stats['errors']}[/red]")

    console.print(summary_table)

    if dry_run:
        console.print("\n[yellow]💡 Run without --dry-run to apply changes[/yellow]")


# ============================================================================
# List Command
# ============================================================================

@app.command()
def list(
    show_teams: bool = typer.Option(True, "--show-teams/--no-teams", help="Show teams under each club")
):
    """List all clubs and their teams."""
    console.print("[bold cyan]📋 Clubs & Teams List[/bold cyan]\n")

    # Authenticate
    with console.status("[bold yellow]🔐 Authenticating...", spinner="dots"):
        token = get_auth_token()

    # Fetch clubs
    with console.status("[bold yellow]📡 Fetching clubs...", spinner="dots"):
        clubs = get_all_clubs(token)

    if not clubs:
        console.print("[yellow]No clubs found[/yellow]")
        return

    # Display clubs
    for club in clubs:
        club_table = Table(title=f"[bold]{club['name']}[/bold]", box=box.ROUNDED)
        club_table.add_column("Property", style="cyan")
        club_table.add_column("Value", style="white")

        club_table.add_row("ID", str(club["id"]))
        club_table.add_row("City", club.get("city", "N/A"))
        club_table.add_row("Website", club.get("website", "N/A"))
        club_table.add_row("Teams", str(club.get("team_count", 0)))
        club_table.add_row("Active", "✅" if club.get("is_active") else "❌")

        console.print(club_table)

        # Show teams if requested
        if show_teams and club.get("teams"):
            teams_table = Table(box=box.SIMPLE, show_header=True)
            teams_table.add_column("ID", style="dim")
            teams_table.add_column("Team Name", style="cyan")
            teams_table.add_column("League", style="yellow")
            teams_table.add_column("Type", style="magenta")

            for team in club["teams"]:
                team_type = "Academy" if team.get("academy_team") else "Homegrown"
                # Get league name from team_mappings
                leagues = [tm.get("league_name", "Unknown") for tm in team.get("team_mappings", [])]
                league_str = ", ".join(leagues) if leagues else "N/A"

                teams_table.add_row(
                    str(team["id"]),
                    team["name"],
                    league_str,
                    team_type
                )

            console.print(teams_table)

        console.print()  # Empty line between clubs


# ============================================================================
# Delete Commands
# ============================================================================

@app.command()
def delete_club(
    club_id: int = typer.Argument(..., help="Club ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt")
):
    """Delete a club by ID."""
    console.print(f"[bold red]🗑️  Delete Club (ID: {club_id})[/bold red]\n")

    # Authenticate
    token = get_auth_token()

    # Get club details
    clubs = get_all_clubs(token)
    club = next((c for c in clubs if c["id"] == club_id), None)

    if not club:
        console.print(f"[red]❌ Club with ID {club_id} not found[/red]")
        raise typer.Exit(code=1)

    # Show what will be deleted
    console.print("[yellow]⚠️  This will delete:[/yellow]")
    console.print(f"  • Club: {club['name']}")
    console.print(f"  • {club.get('team_count', 0)} associated teams")
    console.print()

    # Confirm deletion
    if not force:
        if not Confirm.ask("Are you sure you want to delete this club?"):
            console.print("[dim]Deletion cancelled[/dim]")
            raise typer.Exit()

    # Delete club
    response = api_request("DELETE", f"/api/clubs/{club_id}", token)

    if response.status_code == 200:
        console.print(f"[green]✅ Club '{club['name']}' deleted successfully[/green]")
    else:
        console.print(f"[red]❌ Failed to delete club: {response.text}[/red]")
        raise typer.Exit(code=1)


@app.command()
def delete_team(
    team_id: int = typer.Argument(..., help="Team ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt")
):
    """Delete a team by ID."""
    console.print(f"[bold red]🗑️  Delete Team (ID: {team_id})[/bold red]\n")

    # Authenticate
    token = get_auth_token()

    # Get team details
    teams = get_all_teams(token)
    team = next((t for t in teams if t["id"] == team_id), None)

    if not team:
        console.print(f"[red]❌ Team with ID {team_id} not found[/red]")
        raise typer.Exit(code=1)

    # Show what will be deleted
    console.print("[yellow]⚠️  This will delete:[/yellow]")
    console.print(f"  • Team: {team['name']}")
    console.print()

    # Confirm deletion
    if not force:
        if not Confirm.ask("Are you sure you want to delete this team?"):
            console.print("[dim]Deletion cancelled[/dim]")
            raise typer.Exit()

    # Delete team
    response = api_request("DELETE", f"/api/teams/{team_id}", token)

    if response.status_code == 200:
        console.print(f"[green]✅ Team '{team['name']}' deleted successfully[/green]")
    else:
        console.print(f"[red]❌ Failed to delete team: {response.text}[/red]")
        raise typer.Exit(code=1)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    app()

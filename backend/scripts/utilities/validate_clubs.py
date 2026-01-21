#!/usr/bin/env python3
"""
Validate clubs.json structure using Pydantic models.
Shows exactly what data is present or missing for each team.
"""

import json

# Add backend root directory to path for imports (scripts/utilities/ -> backend/)
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.clubs import load_clubs_from_json

console = Console()


def validate_clubs_json():
    """Parse and validate clubs.json."""
    # Path from scripts/utilities/ -> backend/ -> clubs.json
    clubs_json_path = Path(__file__).parent.parent.parent / "clubs.json"

    console.print("[bold cyan]📋 Validating clubs.json[/bold cyan]")
    console.print(f"File: {clubs_json_path}\n")

    # Load and parse JSON
    with open(clubs_json_path) as f:
        clubs_data = json.load(f)

    # Parse into Pydantic models using shared helper
    try:
        clubs = load_clubs_from_json(clubs_data)
        console.print(f"[green]✅ Successfully parsed {len(clubs)} clubs[/green]\n")
    except Exception as e:
        console.print(f"[red]❌ Validation failed: {e}[/red]")
        return

    # Create summary table
    table = Table(title="Teams Data Status")
    table.add_column("Club", style="cyan")
    table.add_column("Team", style="white")
    table.add_column("League", style="yellow")
    table.add_column("Division/Conference", style="magenta")
    table.add_column("Age Groups", style="blue")
    table.add_column("Status", style="bold")

    for club in clubs:
        for team in club.teams:
            # Check division/conference using model property
            div_conf = team.division_or_conference or "❌ MISSING"
            div_conf_style = "green" if team.division_or_conference else "red"

            # Check age groups
            if team.age_groups:
                age_groups_str = f"✅ {len(team.age_groups)} groups"
                age_groups_style = "green"
            else:
                age_groups_str = "❌ MISSING"
                age_groups_style = "red"

            # Overall status using model property
            status = "✅ COMPLETE" if team.is_complete else "⚠️  INCOMPLETE"
            status_style = "green" if team.is_complete else "red"

            table.add_row(
                club.club_name,
                team.team_name,
                team.league,
                f"[{div_conf_style}]{div_conf}[/{div_conf_style}]",
                f"[{age_groups_style}]{age_groups_str}[/{age_groups_style}]",
                f"[{status_style}]{status}[/{status_style}]",
            )

    console.print(table)

    # Summary
    console.print("\n[bold]Summary:[/bold]")
    total_teams = sum(len(club.teams) for club in clubs)
    complete_teams = sum(1 for club in clubs for team in club.teams if team.is_complete)
    incomplete_teams = total_teams - complete_teams

    console.print(f"  Total teams: {total_teams}")
    console.print(f"  [green]Complete: {complete_teams}[/green]")
    console.print(f"  [red]Incomplete: {incomplete_teams}[/red]")

    # Detailed breakdown for incomplete teams
    if incomplete_teams > 0:
        console.print("\n[bold yellow]⚠️  Incomplete Teams:[/bold yellow]")
        for club in clubs:
            for team in club.teams:
                if not team.is_complete:
                    missing = []
                    if not team.division_or_conference:
                        missing.append("division/conference")
                    if not team.age_groups:
                        missing.append("age_groups")

                    console.print(f"  • {club.club_name} - {team.team_name} ({team.league})")
                    console.print(f"    Missing: {', '.join(missing)}")


if __name__ == "__main__":
    validate_clubs_json()

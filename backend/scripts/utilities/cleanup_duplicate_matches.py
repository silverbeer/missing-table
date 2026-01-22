#!/usr/bin/env python3
"""
Interactive Duplicate Match Cleanup Tool

This tool identifies duplicate matches in the database and provides an interactive
interface to review and clean them up. It uses the same logic as the database
constraints to identify duplicates.

Usage:
    python scripts/utilities/cleanup_duplicate_matches.py --help
    python scripts/utilities/cleanup_duplicate_matches.py scan
    python scripts/utilities/cleanup_duplicate_matches.py clean --dry-run
    python scripts/utilities/cleanup_duplicate_matches.py clean
"""

import sys
from pathlib import Path

# Add backend root directory to path for imports (scripts/utilities/ -> backend/)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt
from rich.table import Table

from dao.match_dao import MatchDAO
from dao.match_dao import SupabaseConnection as DbConnectionHolder

app = typer.Typer(help="Interactive tool to find and clean up duplicate matches")
console = Console()


def get_data_access():
    """Initialize data access with current environment"""
    db_conn_holder_obj = DbConnectionHolder()
    return MatchDAO(db_conn_holder_obj)


def identify_duplicates(dao: MatchDAO) -> dict[str, list[dict[str, Any]]]:
    """
    Identify duplicate matches using the same criteria as database constraints:
    - Same teams, date, season, age group, match type, division (for manual matches)
    - Same match_id (for external matches)
    """
    console.print("🔍 Scanning for duplicate matches...", style="yellow")

    # Get all matches
    matches = dao.get_all_matches()

    # Group matches by duplicate criteria
    manual_match_groups = defaultdict(list)
    external_match_groups = defaultdict(list)

    for match in matches:
        # For matches with match_id, group by match_id
        if match.get("match_id"):
            key = f"match_id:{match['match_id']}"
            external_match_groups[key].append(match)
        else:
            # For manual matches, group by composite key
            key = (
                match["match_date"],
                match["home_team_id"],
                match["away_team_id"],
                match["season_id"],
                match["age_group_id"],
                match["match_type_id"],
                match.get("division_id", 0),  # Use 0 for NULL division_id
            )
            manual_match_groups[key].append(match)

    # Find groups with more than one match (duplicates)
    duplicates = {}

    # Check manual matches
    for key, matches_list in manual_match_groups.items():
        if len(matches_list) > 1:
            duplicates[f"manual_{hash(key)}"] = matches_list

    # Check external matches
    for key, matches_list in external_match_groups.items():
        if len(matches_list) > 1:
            duplicates[key] = matches_list

    return duplicates


def display_duplicate_summary(duplicates: dict[str, list[dict[str, Any]]]):
    """Display a summary of found duplicates"""
    if not duplicates:
        console.print("✅ No duplicate matches found!", style="green bold")
        return

    total_matches = sum(len(matches) for matches in duplicates.values())
    total_groups = len(duplicates)
    matches_to_remove = total_matches - total_groups  # Keep one from each group

    console.print(
        Panel(
            f"[red bold]Found {total_matches} duplicate matches in {total_groups} groups[/red bold]\n"
            f"[yellow]Recommended action: Remove {matches_to_remove} duplicate matches[/yellow]",
            title="🚨 Duplicate Matches Summary",
        )
    )


def display_duplicate_details(duplicates: dict[str, list[dict[str, Any]]]):
    """Display detailed information about duplicates"""
    if not duplicates:
        return

    for group_id, matches_list in duplicates.items():
        console.print(f"\n[bold blue]Duplicate Group: {group_id}[/bold blue]")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Date", width=12)
        table.add_column("Teams", width=40)
        table.add_column("Score", width=10)
        table.add_column("Season", width=12)
        table.add_column("Age/Division", width=15)
        table.add_column("Created", width=20)
        table.add_column("Match ID", width=10)

        # Sort by creation date (newest first)
        sorted_matches = sorted(matches_list, key=lambda x: x["created_at"], reverse=True)

        for i, match in enumerate(sorted_matches):
            style = "green" if i == 0 else "red"  # Highlight the one to keep
            mark = "👑 KEEP" if i == 0 else "❌ DELETE"

            table.add_row(
                f"{match['id']} {mark}",
                match["match_date"],
                f"{match['home_team_name']} vs {match['away_team_name']}",
                f"{match['home_score']}-{match['away_score']}",
                match["season_name"],
                f"{match['age_group_name']}/{match.get('division_name', 'None')}",
                match["created_at"][:19],
                str(match.get("match_id", "N/A")),
                style=style,
            )

        console.print(table)


def get_matches_to_delete(duplicates: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Get list of matches to delete (keeping the newest in each group)"""
    matches_to_delete = []

    for matches_list in duplicates.values():
        # Sort by creation date (newest first) and keep the first one
        sorted_matches = sorted(matches_list, key=lambda x: x["created_at"], reverse=True)
        matches_to_delete.extend(sorted_matches[1:])  # Skip the first (newest) one

    return matches_to_delete


@app.command()
def scan(
    format: str = typer.Option("table", help="Output format: table, json"),
    save: str | None = typer.Option(None, help="Save results to file"),
):
    """Scan for duplicate matches without making changes"""
    dao = get_data_access()
    duplicates = identify_duplicates(dao)

    display_duplicate_summary(duplicates)

    if format == "table":
        display_duplicate_details(duplicates)
    elif format == "json":
        console.print(json.dumps(duplicates, indent=2, default=str))

    if save:
        with open(save, "w") as f:
            json.dump(duplicates, f, indent=2, default=str)
        console.print(f"💾 Results saved to {save}", style="green")


@app.command()
def clean(
    dry_run: bool = typer.Option(True, help="Show what would be deleted without actually deleting"),
    auto: bool = typer.Option(False, help="Delete automatically without prompting"),
    backup: bool = typer.Option(True, help="Create backup before deletion"),
):
    """Clean up duplicate matches with interactive confirmation"""
    dao = get_data_access()
    duplicates = identify_duplicates(dao)

    if not duplicates:
        console.print("✅ No duplicate matches found!", style="green bold")
        return

    display_duplicate_summary(duplicates)
    display_duplicate_details(duplicates)

    matches_to_delete = get_matches_to_delete(duplicates)

    if dry_run:
        console.print(
            Panel(
                f"[yellow bold]DRY RUN MODE[/yellow bold]\n"
                f"Would delete {len(matches_to_delete)} matches:\n"
                + "\n".join(
                    [
                        f"  • Match {match['id']}: {match['home_team_name']} vs {match['away_team_name']} ({match['match_date']})"
                        for match in matches_to_delete[:10]
                    ]
                )
                + (f"\n  ... and {len(matches_to_delete) - 10} more" if len(matches_to_delete) > 10 else ""),
                title="🔍 Preview",
            )
        )
        console.print("\n💡 Run without --dry-run to actually perform the cleanup", style="cyan")
        return

    # Create backup if requested
    if backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_before_cleanup_{timestamp}.json"

        console.print(f"📦 Creating backup: {backup_file}")
        with open(backup_file, "w") as f:
            json.dump(
                {
                    "timestamp": timestamp,
                    "matches_to_delete": matches_to_delete,
                    "duplicates": duplicates,
                },
                f,
                indent=2,
                default=str,
            )

    # Confirm deletion
    if not auto and not Confirm.ask(f"\n⚠️  Delete {len(matches_to_delete)} duplicate matches?"):
        console.print("❌ Cleanup cancelled", style="yellow")
        return

    # Perform deletion
    console.print("\n🗑️  Deleting duplicate matches...", style="red")
    deleted_count = 0

    for match in matches_to_delete:
        try:
            dao.delete_match(match["id"])
            deleted_count += 1
            console.print(f"✅ Deleted match {match['id']}: {match['home_team_name']} vs {match['away_team_name']}")
        except Exception as e:
            console.print(f"❌ Failed to delete match {match['id']}: {e}", style="red")

    console.print(
        Panel(
            f"[green bold]Cleanup Complete![/green bold]\nSuccessfully deleted {deleted_count} duplicate matches",
            title="✅ Success",
        )
    )


@app.command()
def interactive():
    """Interactive mode for reviewing and cleaning duplicates"""
    dao = get_data_access()
    duplicates = identify_duplicates(dao)

    if not duplicates:
        console.print("✅ No duplicate matches found!", style="green bold")
        return

    display_duplicate_summary(duplicates)

    # Review each group
    for group_id, matches_list in duplicates.items():
        console.print(f"\n[bold blue]Reviewing Group: {group_id}[/bold blue]")

        # Display the group
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Date", width=12)
        table.add_column("Teams", width=40)
        table.add_column("Score", width=10)
        table.add_column("Created", width=20)

        sorted_matches = sorted(matches_list, key=lambda x: x["created_at"], reverse=True)

        for i, match in enumerate(sorted_matches):
            style = "green" if i == 0 else "dim"
            table.add_row(
                str(match["id"]),
                match["match_date"],
                f"{match['home_team_name']} vs {match['away_team_name']}",
                f"{match['home_score']}-{match['away_score']}",
                match["created_at"][:19],
                style=style,
            )

        console.print(table)

        # Ask what to do
        console.print("\nOptions:")
        console.print("1. Keep newest (default)")
        console.print("2. Choose which to keep")
        console.print("3. Skip this group")

        choice = IntPrompt.ask("What would you like to do?", default=1, choices=[1, 2, 3])

        if choice == 1:
            # Delete all but the newest
            matches_to_delete = sorted_matches[1:]
        elif choice == 2:
            # Let user choose which to keep
            console.print("\nWhich match would you like to KEEP?")
            for i, match in enumerate(sorted_matches):
                console.print(f"{i + 1}. Match {match['id']} (created {match['created_at'][:19]})")

            keep_idx = IntPrompt.ask("Enter number", choices=list(range(1, len(sorted_matches) + 1))) - 1
            matches_to_delete = [match for i, match in enumerate(sorted_matches) if i != keep_idx]
        else:
            # Skip this group
            console.print("⏭️  Skipping this group", style="yellow")
            continue

        # Delete the selected matches
        if matches_to_delete and Confirm.ask(f"Delete {len(matches_to_delete)} matches from this group?"):
            for match in matches_to_delete:
                try:
                    dao.delete_match(match["id"])
                    console.print(f"✅ Deleted match {match['id']}", style="green")
                except Exception as e:
                    console.print(f"❌ Failed to delete match {match['id']}: {e}", style="red")


@app.command()
def stats():
    """Show database statistics about matches and potential duplicates"""
    dao = get_data_access()

    # Get all matches
    matches = dao.get_all_matches()
    total_matches = len(matches)

    # Count by various dimensions
    by_season = Counter(match["season_name"] for match in matches)
    by_age_group = Counter(match["age_group_name"] for match in matches)
    by_team = Counter(match["home_team_name"] for match in matches)
    by_date = Counter(match["match_date"] for match in matches)

    # Count matches with match_id
    with_match_id = len([m for m in matches if m.get("match_id")])

    # Find potential duplicate dates (more than expected matches per day)
    high_match_days = {date: count for date, count in by_date.items() if count > 15}

    console.print(
        Panel(
            f"[bold]Total Matches:[/bold] {total_matches}\n"
            f"[bold]With Match ID:[/bold] {with_match_id}\n"
            f"[bold]Manual Matches:[/bold] {total_matches - with_match_id}\n"
            f"[bold]Seasons:[/bold] {len(by_season)}\n"
            f"[bold]Age Groups:[/bold] {len(by_age_group)}\n"
            f"[bold]Unique Teams:[/bold] {len(by_team)}",
            title="📊 Database Statistics",
        )
    )

    if high_match_days:
        console.print("\n[yellow]High match count days (potential batch duplicates):[/yellow]")
        for date, count in sorted(high_match_days.items(), key=lambda x: x[1], reverse=True):
            console.print(f"  {date}: {count} matches")


if __name__ == "__main__":
    app()

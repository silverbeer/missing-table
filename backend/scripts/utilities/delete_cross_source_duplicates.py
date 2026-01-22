#!/usr/bin/env python3
"""
Delete cross-source duplicate matches.

This script identifies and deletes manual matches that are duplicates of
match-scraper matches (same teams, same date, but different source).

When a match exists from both sources:
- Keep: match-scraper version (has external_match_id, correct status)
- Delete: manual version (no external_match_id, often wrong status)
"""

import typer
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from dao.match_dao import MatchDAO
from dao.match_dao import SupabaseConnection as DbConnectionHolder

app = typer.Typer(help="Delete cross-source duplicate matches")
console = Console()


def get_data_access():
    """Initialize data access with current environment"""
    db_conn_holder_obj = DbConnectionHolder()
    return MatchDAO(db_conn_holder_obj)


@app.command()
def scan():
    """Scan for cross-source duplicates without deleting"""
    dao = get_data_access()

    console.print("\n🔍 Scanning for cross-source duplicates...\n", style="yellow")

    # Get all matches
    all_matches = (
        dao.client.table("matches")
        .select("id, match_date, home_team_id, away_team_id, match_status, source, match_id, created_at")
        .execute()
    )

    # Also get team names for display
    teams = dao.client.table("teams").select("id, name").execute()
    team_dict = {t["id"]: t["name"] for t in teams.data}

    # Find duplicates
    duplicates = []
    matches_by_key = {}

    for match in all_matches.data:
        key = (match["match_date"], match["home_team_id"], match["away_team_id"])

        if key not in matches_by_key:
            matches_by_key[key] = []
        matches_by_key[key].append(match)

    # Find cross-source duplicates
    for _key, matches in matches_by_key.items():
        if len(matches) < 2:
            continue

        scraper_match = None
        manual_match = None

        for match in matches:
            if match["source"] == "match-scraper" and match["match_id"]:
                scraper_match = match
            elif match["source"] == "manual" and not match["match_id"]:
                manual_match = match

        if scraper_match and manual_match:
            duplicates.append(
                {
                    "scraper_id": scraper_match["id"],
                    "manual_id": manual_match["id"],
                    "match_date": scraper_match["match_date"],
                    "home_team": team_dict.get(scraper_match["home_team_id"], "Unknown"),
                    "away_team": team_dict.get(scraper_match["away_team_id"], "Unknown"),
                    "scraper_status": scraper_match["match_status"],
                    "manual_status": manual_match["match_status"],
                    "external_match_id": scraper_match["match_id"],
                }
            )

    if not duplicates:
        console.print("✅ No cross-source duplicates found!", style="green bold")
        return duplicates

    # Display results
    table = Table(title=f"Found {len(duplicates)} Cross-Source Duplicates")
    table.add_column("Scraper ID", style="green")
    table.add_column("Manual ID", style="red")
    table.add_column("Date")
    table.add_column("Match")
    table.add_column("Scraper Status", style="green")
    table.add_column("Manual Status", style="red")

    for dup in duplicates:
        table.add_row(
            str(dup["scraper_id"]),
            str(dup["manual_id"]),
            dup["match_date"][:10],
            f"{dup['home_team']} vs {dup['away_team']}",
            dup["scraper_status"],
            dup["manual_status"],
        )

    console.print(table)
    console.print(f"\n[yellow]Recommendation: Delete {len(duplicates)} manual duplicates[/yellow]")
    console.print(f"[green]Keep {len(duplicates)} match-scraper versions (have external IDs)[/green]\n")

    return duplicates


@app.command()
def delete(
    dry_run: bool = typer.Option(True, help="Preview changes without deleting"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete manual duplicates (keep match-scraper versions)"""
    dao = get_data_access()

    if dry_run:
        console.print("\n🔍 DRY RUN - No changes will be made\n", style="yellow bold")

    # Reuse scan logic to get duplicates
    duplicates = []
    all_matches = (
        dao.client.table("matches")
        .select("id, match_date, home_team_id, away_team_id, match_status, source, match_id, created_at")
        .execute()
    )

    teams = dao.client.table("teams").select("id, name").execute()
    team_dict = {t["id"]: t["name"] for t in teams.data}

    matches_by_key = {}
    for match in all_matches.data:
        key = (match["match_date"], match["home_team_id"], match["away_team_id"])
        if key not in matches_by_key:
            matches_by_key[key] = []
        matches_by_key[key].append(match)

    for _key, matches in matches_by_key.items():
        if len(matches) < 2:
            continue

        scraper_match = None
        manual_match = None

        for match in matches:
            if match["source"] == "match-scraper" and match["match_id"]:
                scraper_match = match
            elif match["source"] == "manual" and not match["match_id"]:
                manual_match = match

        if scraper_match and manual_match:
            duplicates.append(
                {
                    "scraper_id": scraper_match["id"],
                    "manual_id": manual_match["id"],
                    "home_team": team_dict.get(scraper_match["home_team_id"], "Unknown"),
                    "away_team": team_dict.get(scraper_match["away_team_id"], "Unknown"),
                }
            )

    if not duplicates:
        console.print("✅ No cross-source duplicates found!", style="green bold")
        return

    manual_ids = [dup["manual_id"] for dup in duplicates]

    # Show what will be deleted
    table = Table(title=f"Will Delete {len(manual_ids)} Manual Duplicates")
    table.add_column("Manual ID (DELETE)", style="red bold")
    table.add_column("Scraper ID (KEEP)", style="green bold")
    table.add_column("Match")

    for dup in duplicates:
        table.add_row(
            str(dup["manual_id"]),
            str(dup["scraper_id"]),
            f"{dup['home_team']} vs {dup['away_team']}",
        )

    console.print(table)

    if dry_run:
        console.print("\n[yellow]This was a dry run. Use --no-dry-run to actually delete.[/yellow]\n")
        return

    # Confirm deletion
    console.print(f"\n[red bold]⚠️  You are about to delete {len(manual_ids)} manual matches![/red bold]")
    console.print("[green]The match-scraper versions will be kept.[/green]\n")

    if not yes and not Confirm.ask("Are you sure you want to proceed?"):
        console.print("[yellow]Cancelled[/yellow]")
        return

    # Delete the manual duplicates one by one
    console.print("\n🗑️  Deleting manual duplicates...", style="yellow")

    deleted_count = 0
    for manual_id in manual_ids:
        try:
            dao.client.table("matches").delete().eq("id", manual_id).execute()
            deleted_count += 1
        except Exception as e:
            console.print(f"[red]Error deleting match {manual_id}: {e}[/red]")

    console.print(f"✅ Deleted {deleted_count} manual duplicate matches!", style="green bold")
    console.print(f"✅ Kept {len(manual_ids)} match-scraper versions\n", style="green bold")


if __name__ == "__main__":
    app()

#!/usr/bin/env python3
"""
Interactive Duplicate Game Cleanup Tool

This tool identifies duplicate games in the database and provides an interactive
interface to review and clean them up. It uses the same logic as the database
constraints to identify duplicates.

Usage:
    python cleanup_duplicate_games.py --help
    python cleanup_duplicate_games.py scan
    python cleanup_duplicate_games.py clean --dry-run
    python cleanup_duplicate_games.py clean
"""

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm, IntPrompt
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
from collections import defaultdict, Counter

from dao.enhanced_data_access_fixed import EnhancedSportsDAO
from dao.enhanced_data_access_fixed import SupabaseConnection as DbConnectionHolder

app = typer.Typer(help="Interactive tool to find and clean up duplicate games")
console = Console()

def get_data_access():
    """Initialize data access with current environment"""
    db_conn_holder_obj = DbConnectionHolder()
    return EnhancedSportsDAO(db_conn_holder_obj)

def identify_duplicates(dao: EnhancedSportsDAO) -> Dict[str, List[Dict[str, Any]]]:
    """
    Identify duplicate games using the same criteria as database constraints:
    - Same teams, date, season, age group, game type, division (for manual games)
    - Same match_id (for external games)
    """
    console.print("🔍 Scanning for duplicate games...", style="yellow")

    # Get all games
    games = dao.get_all_games()

    # Group games by duplicate criteria
    manual_game_groups = defaultdict(list)
    external_game_groups = defaultdict(list)

    for game in games:
        # For games with match_id, group by match_id
        if game.get('match_id'):
            key = f"match_id:{game['match_id']}"
            external_game_groups[key].append(game)
        else:
            # For manual games, group by composite key
            key = (
                game['game_date'],
                game['home_team_id'],
                game['away_team_id'],
                game['season_id'],
                game['age_group_id'],
                game['game_type_id'],
                game.get('division_id', 0)  # Use 0 for NULL division_id
            )
            manual_game_groups[key].append(game)

    # Find groups with more than one game (duplicates)
    duplicates = {}

    # Check manual games
    for key, games_list in manual_game_groups.items():
        if len(games_list) > 1:
            duplicates[f"manual_{hash(key)}"] = games_list

    # Check external games
    for key, games_list in external_game_groups.items():
        if len(games_list) > 1:
            duplicates[key] = games_list

    return duplicates

def display_duplicate_summary(duplicates: Dict[str, List[Dict[str, Any]]]):
    """Display a summary of found duplicates"""
    if not duplicates:
        console.print("✅ No duplicate games found!", style="green bold")
        return

    total_games = sum(len(games) for games in duplicates.values())
    total_groups = len(duplicates)
    games_to_remove = total_games - total_groups  # Keep one from each group

    console.print(Panel(
        f"[red bold]Found {total_games} duplicate games in {total_groups} groups[/red bold]\n"
        f"[yellow]Recommended action: Remove {games_to_remove} duplicate games[/yellow]",
        title="🚨 Duplicate Games Summary"
    ))

def display_duplicate_details(duplicates: Dict[str, List[Dict[str, Any]]]):
    """Display detailed information about duplicates"""
    if not duplicates:
        return

    for group_id, games_list in duplicates.items():
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
        sorted_games = sorted(games_list, key=lambda x: x['created_at'], reverse=True)

        for i, game in enumerate(sorted_games):
            style = "green" if i == 0 else "red"  # Highlight the one to keep
            mark = "👑 KEEP" if i == 0 else "❌ DELETE"

            table.add_row(
                f"{game['id']} {mark}",
                game['game_date'],
                f"{game['home_team_name']} vs {game['away_team_name']}",
                f"{game['home_score']}-{game['away_score']}",
                game['season_name'],
                f"{game['age_group_name']}/{game.get('division_name', 'None')}",
                game['created_at'][:19],
                str(game.get('match_id', 'N/A')),
                style=style
            )

        console.print(table)

def get_games_to_delete(duplicates: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Get list of games to delete (keeping the newest in each group)"""
    games_to_delete = []

    for games_list in duplicates.values():
        # Sort by creation date (newest first) and keep the first one
        sorted_games = sorted(games_list, key=lambda x: x['created_at'], reverse=True)
        games_to_delete.extend(sorted_games[1:])  # Skip the first (newest) one

    return games_to_delete

@app.command()
def scan(
    format: str = typer.Option("table", help="Output format: table, json"),
    save: Optional[str] = typer.Option(None, help="Save results to file")
):
    """Scan for duplicate games without making changes"""
    dao = get_data_access()
    duplicates = identify_duplicates(dao)

    display_duplicate_summary(duplicates)

    if format == "table":
        display_duplicate_details(duplicates)
    elif format == "json":
        console.print(json.dumps(duplicates, indent=2, default=str))

    if save:
        with open(save, 'w') as f:
            json.dump(duplicates, f, indent=2, default=str)
        console.print(f"💾 Results saved to {save}", style="green")

@app.command()
def clean(
    dry_run: bool = typer.Option(True, help="Show what would be deleted without actually deleting"),
    auto: bool = typer.Option(False, help="Delete automatically without prompting"),
    backup: bool = typer.Option(True, help="Create backup before deletion")
):
    """Clean up duplicate games with interactive confirmation"""
    dao = get_data_access()
    duplicates = identify_duplicates(dao)

    if not duplicates:
        console.print("✅ No duplicate games found!", style="green bold")
        return

    display_duplicate_summary(duplicates)
    display_duplicate_details(duplicates)

    games_to_delete = get_games_to_delete(duplicates)

    if dry_run:
        console.print(Panel(
            f"[yellow bold]DRY RUN MODE[/yellow bold]\n"
            f"Would delete {len(games_to_delete)} games:\n" +
            "\n".join([f"  • Game {game['id']}: {game['home_team_name']} vs {game['away_team_name']} ({game['game_date']})"
                      for game in games_to_delete[:10]]) +
            (f"\n  ... and {len(games_to_delete) - 10} more" if len(games_to_delete) > 10 else ""),
            title="🔍 Preview"
        ))
        console.print("\n💡 Run without --dry-run to actually perform the cleanup", style="cyan")
        return

    # Create backup if requested
    if backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_before_cleanup_{timestamp}.json"

        console.print(f"📦 Creating backup: {backup_file}")
        with open(backup_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'games_to_delete': games_to_delete,
                'duplicates': duplicates
            }, f, indent=2, default=str)

    # Confirm deletion
    if not auto:
        if not Confirm.ask(f"\n⚠️  Delete {len(games_to_delete)} duplicate games?"):
            console.print("❌ Cleanup cancelled", style="yellow")
            return

    # Perform deletion
    console.print("\n🗑️  Deleting duplicate games...", style="red")
    deleted_count = 0

    for game in games_to_delete:
        try:
            dao.delete_game(game['id'])
            deleted_count += 1
            console.print(f"✅ Deleted game {game['id']}: {game['home_team_name']} vs {game['away_team_name']}")
        except Exception as e:
            console.print(f"❌ Failed to delete game {game['id']}: {e}", style="red")

    console.print(Panel(
        f"[green bold]Cleanup Complete![/green bold]\n"
        f"Successfully deleted {deleted_count} duplicate games",
        title="✅ Success"
    ))

@app.command()
def interactive():
    """Interactive mode for reviewing and cleaning duplicates"""
    dao = get_data_access()
    duplicates = identify_duplicates(dao)

    if not duplicates:
        console.print("✅ No duplicate games found!", style="green bold")
        return

    display_duplicate_summary(duplicates)

    # Review each group
    for group_id, games_list in duplicates.items():
        console.print(f"\n[bold blue]Reviewing Group: {group_id}[/bold blue]")

        # Display the group
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Date", width=12)
        table.add_column("Teams", width=40)
        table.add_column("Score", width=10)
        table.add_column("Created", width=20)

        sorted_games = sorted(games_list, key=lambda x: x['created_at'], reverse=True)

        for i, game in enumerate(sorted_games):
            style = "green" if i == 0 else "dim"
            table.add_row(
                str(game['id']),
                game['game_date'],
                f"{game['home_team_name']} vs {game['away_team_name']}",
                f"{game['home_score']}-{game['away_score']}",
                game['created_at'][:19],
                style=style
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
            games_to_delete = sorted_games[1:]
        elif choice == 2:
            # Let user choose which to keep
            console.print("\nWhich game would you like to KEEP?")
            for i, game in enumerate(sorted_games):
                console.print(f"{i+1}. Game {game['id']} (created {game['created_at'][:19]})")

            keep_idx = IntPrompt.ask("Enter number", choices=list(range(1, len(sorted_games) + 1))) - 1
            games_to_delete = [game for i, game in enumerate(sorted_games) if i != keep_idx]
        else:
            # Skip this group
            console.print("⏭️  Skipping this group", style="yellow")
            continue

        # Delete the selected games
        if games_to_delete and Confirm.ask(f"Delete {len(games_to_delete)} games from this group?"):
            for game in games_to_delete:
                try:
                    dao.delete_game(game['id'])
                    console.print(f"✅ Deleted game {game['id']}", style="green")
                except Exception as e:
                    console.print(f"❌ Failed to delete game {game['id']}: {e}", style="red")

@app.command()
def stats():
    """Show database statistics about games and potential duplicates"""
    dao = get_data_access()

    # Get all games
    games = dao.get_all_games()
    total_games = len(games)

    # Count by various dimensions
    by_season = Counter(game['season_name'] for game in games)
    by_age_group = Counter(game['age_group_name'] for game in games)
    by_team = Counter(game['home_team_name'] for game in games)
    by_date = Counter(game['game_date'] for game in games)

    # Count games with match_id
    with_match_id = len([g for g in games if g.get('match_id')])

    # Find potential duplicate dates (more than expected games per day)
    high_game_days = {date: count for date, count in by_date.items() if count > 15}

    console.print(Panel(
        f"[bold]Total Games:[/bold] {total_games}\n"
        f"[bold]With Match ID:[/bold] {with_match_id}\n"
        f"[bold]Manual Games:[/bold] {total_games - with_match_id}\n"
        f"[bold]Seasons:[/bold] {len(by_season)}\n"
        f"[bold]Age Groups:[/bold] {len(by_age_group)}\n"
        f"[bold]Unique Teams:[/bold] {len(by_team)}",
        title="📊 Database Statistics"
    ))

    if high_game_days:
        console.print("\n[yellow]High game count days (potential batch duplicates):[/yellow]")
        for date, count in sorted(high_game_days.items(), key=lambda x: x[1], reverse=True):
            console.print(f"  {date}: {count} games")

if __name__ == "__main__":
    app()
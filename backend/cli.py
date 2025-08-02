#!/usr/bin/env python3
"""
CLI tool for managing the sports league.
Quick way to add games and manage data via the backend API.
"""

import sys
from datetime import datetime

import httpx
import typer
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

app = typer.Typer()
console = Console()

# API base URL - adjust if your backend runs on a different port
API_BASE_URL = "http://localhost:8000"


def get_teams():
    """Fetch all teams from the API."""
    try:
        response = httpx.get(f"{API_BASE_URL}/api/teams")
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as e:
        console.print(f"[red]Error connecting to API: {e}[/red]")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        console.print(f"[red]API error: {e}[/red]")
        sys.exit(1)


@app.command()
def add_game(
    date: str | None = typer.Option(None, "--date", "-d", help="Game date (YYYY-MM-DD)"),
    home_team: str | None = typer.Option(None, "--home", "-h", help="Home team name"),
    away_team: str | None = typer.Option(None, "--away", "-a", help="Away team name"),
    home_score: int | None = typer.Option(None, "--home-score", "-hs", help="Home team score"),
    away_score: int | None = typer.Option(None, "--away-score", "-as", help="Away team score"),
):
    """Add a new game to the league."""
    console.print("[bold cyan]Add New Game[/bold cyan]\n")

    # Get list of teams for validation and display
    teams = get_teams()
    team_names = [team["name"] for team in teams]

    # Interactive mode if not all parameters provided
    if not all([date, home_team, away_team, home_score is not None, away_score is not None]):
        # Show available teams
        table = Table(title="Available Teams")
        table.add_column("Team Name", style="cyan")
        table.add_column("City", style="green")

        for team in sorted(teams, key=lambda x: x["name"]):
            table.add_row(team["name"], team["city"])

        console.print(table)
        console.print()

        # Get game details interactively
        if not date:
            default_date = datetime.now().strftime("%Y-%m-%d")
            date = Prompt.ask("Game date (YYYY-MM-DD)", default=default_date)

        if not home_team:
            home_team = Prompt.ask("Home team", choices=team_names)

        if not away_team:
            # Filter out home team from choices
            away_choices = [t for t in team_names if t != home_team]
            away_team = Prompt.ask("Away team", choices=away_choices)

        if home_score is None:
            home_score = IntPrompt.ask("Home team score")

        if away_score is None:
            away_score = IntPrompt.ask("Away team score")

    # Validate teams
    if home_team not in team_names:
        console.print(f"[red]Error: '{home_team}' is not a valid team[/red]")
        return

    if away_team not in team_names:
        console.print(f"[red]Error: '{away_team}' is not a valid team[/red]")
        return

    if home_team == away_team:
        console.print("[red]Error: Home and away teams cannot be the same[/red]")
        return

    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        console.print("[red]Error: Invalid date format. Use YYYY-MM-DD[/red]")
        return

    # Display game summary
    console.print("\n[bold]Game Summary:[/bold]")
    console.print(f"Date: [cyan]{date}[/cyan]")
    console.print(f"Home: [green]{home_team}[/green] - Score: [yellow]{home_score}[/yellow]")
    console.print(f"Away: [blue]{away_team}[/blue] - Score: [yellow]{away_score}[/yellow]")

    # Confirm before submitting
    if not Confirm.ask("\nAdd this game?"):
        console.print("[yellow]Game not added.[/yellow]")
        return

    # Submit to API
    game_data = {
        "game_date": date,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
    }

    try:
        response = httpx.post(f"{API_BASE_URL}/api/games", json=game_data)
        response.raise_for_status()
        console.print("[green]✓ Game added successfully![/green]")
    except httpx.HTTPStatusError as e:
        console.print(f"[red]Error adding game: {e.response.text}[/red]")
    except httpx.RequestError as e:
        console.print(f"[red]Error connecting to API: {e}[/red]")


@app.command()
def list_teams():
    """List all teams in the league."""
    teams = get_teams()

    table = Table(title="League Teams")
    table.add_column("Team Name", style="cyan")
    table.add_column("City", style="green")

    for team in sorted(teams, key=lambda x: x["name"]):
        table.add_row(team["name"], team["city"])

    console.print(table)
    console.print(f"\n[dim]Total teams: {len(teams)}[/dim]")


@app.command()
def recent_games(limit: int = typer.Option(10, "--limit", "-l", help="Number of games to show")):
    """Show recent games."""
    try:
        response = httpx.get(f"{API_BASE_URL}/api/games")
        response.raise_for_status()
        games = response.json()

        # Sort by date and get recent games
        games.sort(key=lambda x: x["game_date"], reverse=True)
        recent = games[:limit]

        table = Table(title=f"Recent {limit} Games")
        table.add_column("Date", style="cyan")
        table.add_column("Home Team", style="green")
        table.add_column("Score", style="yellow", justify="center")
        table.add_column("Away Team", style="blue")

        for game in recent:
            score = f"{game['home_score']} - {game['away_score']}"
            table.add_row(game["game_date"], game["home_team"], score, game["away_team"])

        console.print(table)

    except httpx.RequestError as e:
        console.print(f"[red]Error connecting to API: {e}[/red]")
    except httpx.HTTPStatusError as e:
        console.print(f"[red]API error: {e}[/red]")


@app.command()
def table():
    """Show the current league table."""
    try:
        response = httpx.get(f"{API_BASE_URL}/api/table")
        response.raise_for_status()
        standings = response.json()

        table = Table(title="League Table")
        table.add_column("Pos", style="dim", width=4)
        table.add_column("Team", style="cyan")
        table.add_column("P", justify="right", width=4)
        table.add_column("W", justify="right", width=4)
        table.add_column("D", justify="right", width=4)
        table.add_column("L", justify="right", width=4)
        table.add_column("GF", justify="right", width=4)
        table.add_column("GA", justify="right", width=4)
        table.add_column("GD", justify="right", width=4)
        table.add_column("Pts", style="bold yellow", justify="right", width=4)

        for i, team in enumerate(standings, 1):
            table.add_row(
                str(i),
                team["team"],
                str(team["played"]),
                str(team["wins"]),
                str(team["draws"]),
                str(team["losses"]),
                str(team["goals_for"]),
                str(team["goals_against"]),
                str(team["goal_difference"]),
                str(team["points"]),
            )

        console.print(table)

    except httpx.RequestError as e:
        console.print(f"[red]Error connecting to API: {e}[/red]")
    except httpx.HTTPStatusError as e:
        console.print(f"[red]API error: {e}[/red]")


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()

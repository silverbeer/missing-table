#!/usr/bin/env python3
"""
Direct Schema Inspection Script

Queries information_schema directly to get accurate schema state.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import typer

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
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                env_vars[key.strip()] = value

    return env_vars


def get_client(env: str):
    """Get Supabase client for environment."""
    env_vars = load_env_file(env)

    supabase_url = env_vars.get("SUPABASE_URL")
    supabase_key = (env_vars.get("SUPABASE_SERVICE_ROLE_KEY") or
                   env_vars.get("SUPABASE_SERVICE_KEY") or
                   env_vars.get("SUPABASE_KEY"))

    if not supabase_url or not supabase_key:
        return None

    return create_client(supabase_url, supabase_key)


@app.command()
def inspect(env: str = typer.Argument("local", help="Environment to inspect")):
    """Inspect database schema directly."""

    console.print(Panel.fit(f"[bold cyan]Direct Schema Inspection: {env.upper()}[/bold cyan]", box=box.DOUBLE))

    client = get_client(env)
    if not client:
        console.print(f"[red]Could not connect to {env}[/red]")
        return

    # Check teams table columns by querying directly
    console.print("\n[bold]Teams Table Inspection:[/bold]")
    try:
        result = client.table("teams").select("*").limit(1).execute()
        if result.data and len(result.data) > 0:
            columns = list(result.data[0].keys())
            console.print(f"[cyan]Columns:[/cyan] {', '.join(columns)}")

            # Check for parent_club_id
            if "parent_club_id" in columns:
                console.print("[green]✓ parent_club_id column EXISTS[/green]")
            else:
                console.print("[red]✗ parent_club_id column MISSING[/red]")
        else:
            console.print("[yellow]Teams table is empty, trying schema query...[/yellow]")
            # Try with no data
            result = client.table("teams").select("parent_club_id").limit(0).execute()
            console.print("[green]✓ parent_club_id column EXISTS[/green]")
    except Exception as e:
        error_msg = str(e)
        if "parent_club_id" in error_msg or "column" in error_msg.lower():
            console.print("[red]✗ parent_club_id column MISSING[/red]")
        console.print(f"[dim]Error: {error_msg[:200]}[/dim]")

    # Check tables exist
    console.print("\n[bold]Table Existence Check:[/bold]")

    tables_to_check = [
        ("teams", True),  # Must exist
        ("leagues", False),
        ("schema_version", False),
        ("matches", True),
        ("age_groups", True),
        ("divisions", True),
        ("team_mappings", True),
    ]

    for table_name, required in tables_to_check:
        try:
            client.table(table_name).select("*").limit(0).execute()
            console.print(f"[green]✓ {table_name} EXISTS[/green]")
        except Exception as e:
            if required:
                console.print(f"[red]✗ {table_name} MISSING (REQUIRED!)[/red]")
            else:
                console.print(f"[yellow]- {table_name} MISSING (optional)[/yellow]")

    # Check for schema version if table exists
    console.print("\n[bold]Schema Version Info:[/bold]")
    try:
        result = client.table("schema_version").select("*").order("applied_at", desc=True).limit(5).execute()
        if result.data:
            table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
            table.add_column("Version")
            table.add_column("Migration")
            table.add_column("Applied")

            for row in result.data:
                table.add_row(
                    row.get("version", "?"),
                    row.get("migration_name", "?"),
                    row.get("applied_at", "?")[:10]
                )

            console.print(table)
        else:
            console.print("[yellow]schema_version table is empty[/yellow]")
    except Exception:
        console.print("[yellow]schema_version table doesn't exist or is inaccessible[/yellow]")

    # Check functions
    console.print("\n[bold]Function Check:[/bold]")
    functions = ["get_club_teams", "is_parent_club", "get_parent_club", "get_schema_version"]

    for func in functions:
        try:
            if func == "get_club_teams":
                client.rpc(func, {"p_club_id": 999999}).execute()
            elif func == "get_schema_version":
                client.rpc(func).execute()
            else:
                client.rpc(func, {"p_team_id": 999999}).execute()
            console.print(f"[green]✓ {func} EXISTS[/green]")
        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "does not exist" in error_msg or "pgrst202" in error_msg:
                console.print(f"[red]✗ {func} MISSING[/red]")
            else:
                # Function exists but call failed (expected with dummy data)
                console.print(f"[green]✓ {func} EXISTS[/green]")

    # Check views
    console.print("\n[bold]View Check:[/bold]")
    try:
        client.table("teams_with_parent").select("*").limit(0).execute()
        console.print("[green]✓ teams_with_parent view EXISTS[/green]")
    except Exception:
        console.print("[red]✗ teams_with_parent view MISSING[/red]")


if __name__ == "__main__":
    app()

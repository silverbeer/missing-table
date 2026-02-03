#!/usr/bin/env python3
"""
Schema Version Audit Script

Checks schema versions and migration status across all environments (local, prod).
Identifies schema drift and missing migrations.

Usage:
    APP_ENV=local python scripts/audit_schema_versions.py
    APP_ENV=prod python scripts/audit_schema_versions.py
    APP_ENV=prod python scripts/audit_schema_versions.py

Or run for all environments:
    python scripts/audit_schema_versions.py --all
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import typer

app = typer.Typer()
console = Console()


def get_supabase_client(env: str):
    """Get Supabase client for specified environment."""
    env_file = Path(__file__).parent.parent / f".env.{env}"

    if not env_file.exists():
        console.print(f"[red]Error: {env_file} not found[/red]")
        return None

    # Load environment variables from file
    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes and whitespace
                value = value.strip().strip('"').strip("'")
                env_vars[key.strip()] = value

    supabase_url = env_vars.get("SUPABASE_URL")
    # Try different key names used in the project
    supabase_key = (env_vars.get("SUPABASE_SERVICE_ROLE_KEY") or
                   env_vars.get("SUPABASE_SERVICE_KEY") or
                   env_vars.get("SUPABASE_KEY"))

    if not supabase_url:
        console.print(f"[red]Error: SUPABASE_URL not found in {env_file}[/red]")
        console.print(f"[dim]Found keys: {', '.join(env_vars.keys())}[/dim]")
        return None

    if not supabase_key:
        console.print(f"[red]Error: No Supabase service key found in {env_file}[/red]")
        console.print(f"[dim]Tried: SUPABASE_SERVICE_ROLE_KEY, SUPABASE_SERVICE_KEY, SUPABASE_KEY[/dim]")
        console.print(f"[dim]Found keys: {', '.join(env_vars.keys())}[/dim]")
        return None

    try:
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        console.print(f"[red]Error creating Supabase client: {str(e)}[/red]")
        return None


def check_schema_version(client, env: str) -> dict:
    """Check schema version and key features for an environment."""
    result = {
        "env": env,
        "schema_version": "Unknown",
        "schema_versions": [],
        "parent_club_id_exists": False,
        "leagues_table_exists": False,
        "functions": [],
        "views": [],
        "error": None
    }

    try:
        # Check schema_version table
        try:
            response = client.rpc("get_schema_version").execute()
            if response.data:
                result["schema_version"] = response.data.get("version", "Unknown")
        except Exception as e:
            result["error"] = f"schema_version function not found: {str(e)}"

        # Get all schema versions from history
        try:
            response = client.table("schema_version").select("*").order("applied_at", desc=True).execute()
            result["schema_versions"] = [
                f"{v['version']} - {v['migration_name']} ({v['applied_at'][:10]})"
                for v in response.data
            ]
        except Exception as e:
            result["schema_versions"] = [f"Error: {str(e)}"]

        # Check if parent_club_id column exists
        try:
            # Try to query teams with parent_club_id
            response = client.table("teams").select("id, name, parent_club_id").limit(1).execute()
            result["parent_club_id_exists"] = True
        except Exception:
            result["parent_club_id_exists"] = False

        # Check if leagues table exists
        try:
            response = client.table("leagues").select("id").limit(1).execute()
            result["leagues_table_exists"] = True
        except Exception:
            result["leagues_table_exists"] = False

        # Check for key functions
        functions_to_check = [
            "get_club_teams",
            "is_parent_club",
            "get_parent_club",
            "get_schema_version"
        ]

        for func in functions_to_check:
            try:
                # Try calling with dummy parameter (will fail but tells us if function exists)
                client.rpc(func, {"p_club_id": 1} if func == "get_club_teams" else {"p_team_id": 1} if func != "get_schema_version" else {}).execute()
                result["functions"].append(f"✓ {func}")
            except Exception as e:
                if "not found" in str(e).lower() or "does not exist" in str(e).lower():
                    result["functions"].append(f"✗ {func}")
                else:
                    # Function exists but call failed (expected)
                    result["functions"].append(f"✓ {func}")

        # Check for key views
        views_to_check = ["teams_with_parent"]

        for view in views_to_check:
            try:
                client.table(view).select("id").limit(1).execute()
                result["views"].append(f"✓ {view}")
            except Exception:
                result["views"].append(f"✗ {view}")

    except Exception as e:
        result["error"] = str(e)

    return result


@app.command()
def audit(
    env: str = typer.Option(None, "--env", "-e", help="Environment to audit (local, prod)"),
    all_envs: bool = typer.Option(False, "--all", "-a", help="Audit all environments")
):
    """Audit schema versions across environments."""

    if all_envs:
        environments = ["local", "prod"]
    elif env:
        environments = [env]
    else:
        # Use current environment from APP_ENV
        current_env = os.getenv("APP_ENV", "local")
        environments = [current_env]

    console.print(Panel.fit(
        "[bold cyan]Schema Version Audit[/bold cyan]\n"
        f"Checking: {', '.join(environments)}",
        box=box.DOUBLE
    ))

    results = []

    for environment in environments:
        console.print(f"\n[bold]Checking {environment.upper()} environment...[/bold]")
        client = get_supabase_client(environment)

        if client:
            result = check_schema_version(client, environment)
            results.append(result)

            # Display result
            if result["error"]:
                console.print(f"[red]Error: {result['error']}[/red]")
            else:
                console.print(f"[green]✓ Connected successfully[/green]")
                console.print(f"Schema Version: [cyan]{result['schema_version']}[/cyan]")
                console.print(f"parent_club_id exists: [{'green' if result['parent_club_id_exists'] else 'red'}]{result['parent_club_id_exists']}[/{'green' if result['parent_club_id_exists'] else 'red'}]")
                console.print(f"leagues table exists: [{'green' if result['leagues_table_exists'] else 'red'}]{result['leagues_table_exists']}[/{'green' if result['leagues_table_exists'] else 'red'}]")
        else:
            console.print(f"[red]✗ Could not connect to {environment}[/red]")

    # Summary table
    if len(results) > 1:
        console.print("\n[bold]Summary Comparison:[/bold]")

        table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        table.add_column("Environment", style="bold")
        table.add_column("Schema Version")
        table.add_column("parent_club_id")
        table.add_column("leagues table")
        table.add_column("Functions")
        table.add_column("Views")

        for result in results:
            table.add_row(
                result["env"].upper(),
                result["schema_version"],
                "✓" if result["parent_club_id_exists"] else "✗",
                "✓" if result["leagues_table_exists"] else "✗",
                f"{len([f for f in result['functions'] if '✓' in f])}/4",
                f"{len([v for v in result['views'] if '✓' in v])}/1"
            )

        console.print(table)

        # Detailed function/view status
        console.print("\n[bold]Detailed Status:[/bold]")
        for result in results:
            console.print(f"\n[bold cyan]{result['env'].upper()}:[/bold cyan]")
            console.print("Functions:")
            for func in result["functions"]:
                console.print(f"  {func}")
            console.print("Views:")
            for view in result["views"]:
                console.print(f"  {view}")

            if result["schema_versions"]:
                console.print("\nMigration History:")
                for version in result["schema_versions"][:5]:  # Show last 5
                    console.print(f"  • {version}")

    # Check for drift
    if len(results) > 1:
        console.print("\n[bold]Schema Drift Analysis:[/bold]")

        versions = [r["schema_version"] for r in results]
        parent_club_status = [r["parent_club_id_exists"] for r in results]
        leagues_status = [r["leagues_table_exists"] for r in results]

        if len(set(versions)) > 1:
            console.print("[yellow]⚠ Schema versions differ across environments[/yellow]")
            for result in results:
                console.print(f"  {result['env']}: {result['schema_version']}")
        else:
            console.print("[green]✓ All environments have same schema version[/green]")

        if len(set(parent_club_status)) > 1:
            console.print("[yellow]⚠ parent_club_id column status differs[/yellow]")
            for result in results:
                status = "exists" if result["parent_club_id_exists"] else "missing"
                console.print(f"  {result['env']}: {status}")

        if len(set(leagues_status)) > 1:
            console.print("[yellow]⚠ leagues table status differs[/yellow]")
            for result in results:
                status = "exists" if result["leagues_table_exists"] else "missing"
                console.print(f"  {result['env']}: {status}")

    console.print("\n[bold green]Audit complete![/bold green]")


if __name__ == "__main__":
    app()

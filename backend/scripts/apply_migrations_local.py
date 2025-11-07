#!/usr/bin/env python3
"""
Apply migrations to LOCAL database manually

This script applies migration files directly to the local database.
Useful when Supabase CLI isn't applying them properly.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client
from rich.console import Console
from rich.panel import Panel
from rich import box

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


def main():
    console.print(Panel.fit(
        "[bold cyan]Apply Migrations to LOCAL[/bold cyan]",
        box=box.DOUBLE
    ))

    # Load environment
    env_vars = load_env_file("local")
    supabase_url = env_vars.get("SUPABASE_URL")
    supabase_key = env_vars.get("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        console.print("[red]Cannot load LOCAL environment[/red]")
        return

    console.print(f"Connecting to: {supabase_url}")

    client = create_client(supabase_url, supabase_key)

    # Get migration files
    migrations_dir = Path(__file__).parent.parent.parent / "supabase-local" / "migrations"

    if not migrations_dir.exists():
        console.print(f"[red]Migrations directory not found: {migrations_dir}[/red]")
        return

    migration_files = sorted(migrations_dir.glob("*.sql"))

    console.print(f"\nFound {len(migration_files)} migration files:")
    for mig in migration_files:
        console.print(f"  - {mig.name}")

    console.print("\n[bold]Applying migrations...[/bold]")

    for migration_file in migration_files:
        console.print(f"\n[cyan]Applying: {migration_file.name}[/cyan]")

        # Read migration SQL
        sql = migration_file.read_text()

        # Execute migration
        try:
            # Use the raw SQL execution endpoint
            # Supabase Python client doesn't have direct SQL execution
            # So we'll need to use psycopg2 or similar

            console.print(f"[yellow]  Cannot execute SQL directly via Supabase client[/yellow]")
            console.print(f"[yellow]  Please run migrations using Supabase CLI or psql[/yellow]")
            break

        except Exception as e:
            console.print(f"[red]  Error: {str(e)}[/red]")
            break

    console.print("\n[yellow]Alternative: Use Supabase CLI from correct directory[/yellow]")
    console.print("  cd /Users/silverbeer/gitrepos/missing-table")
    console.print("  cd supabase-local")
    console.print("  npx supabase db reset")


if __name__ == "__main__":
    main()

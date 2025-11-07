#!/usr/bin/env python3
"""
Apply Migrations to PROD with SSL

Same as apply_migrations_to_env.py but with SSL support for Supabase.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
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
        "[bold cyan]Apply Migrations to PROD (with SSL)[/bold cyan]",
        box=box.DOUBLE
    ))

    # Load environment
    env_vars = load_env_file("prod")
    database_url = env_vars.get("DATABASE_URL")

    if not database_url:
        console.print("[red]DATABASE_URL not found in .env.prod[/red]")
        return 1

    # Add SSL mode if not present
    if "sslmode" not in database_url:
        database_url += "?sslmode=require"

    console.print(f"Database: {database_url[:50]}...")

    # Try to import psycopg2
    try:
        import psycopg2
    except ImportError:
        console.print("\n[red]psycopg2 not installed![/red]")
        return 1

    # Get migration files
    migrations_dir = Path(__file__).parent.parent.parent / "supabase-local" / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))

    console.print(f"\nFound {len(migration_files)} migration files")

    console.print(f"\n[bold]Connecting to PROD database with SSL...[/bold]")

    try:
        conn = psycopg2.connect(database_url, sslmode='require')
        conn.autocommit = False
        cursor = conn.cursor()

        console.print("[green]✓ Connected successfully[/green]")

        console.print("\n[bold]Applying migrations...[/bold]")

        for migration_file in migration_files:
            console.print(f"\n[cyan]Applying: {migration_file.name}[/cyan]")

            sql_content = migration_file.read_text()

            try:
                cursor.execute(sql_content)
                conn.commit()
                console.print(f"[green]  ✓ Applied successfully[/green]")

            except Exception as e:
                error_msg = str(e)

                if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                    console.print(f"[yellow]  ⚠ Already applied (skipping)[/yellow]")
                    conn.rollback()
                else:
                    console.print(f"[red]  ✗ Error: {error_msg[:200]}[/red]")
                    conn.rollback()
                    cursor.close()
                    conn.close()
                    return 1

        # Verify
        cursor.execute("SELECT version, migration_name FROM schema_version ORDER BY applied_at DESC LIMIT 5")
        recent = cursor.fetchall()

        console.print("\n[green]Recent migrations:[/green]")
        for version, name in recent:
            console.print(f"  • {version} - {name}")

        cursor.close()
        conn.close()

        console.print("\n[bold green]✓ All migrations applied successfully![/bold green]")
        return 0

    except Exception as e:
        console.print(f"\n[red]Connection error: {str(e)}[/red]")
        console.print("\n[yellow]Suggestion: PROD database might use connection pooling[/yellow]")
        console.print("[yellow]Try using the pooler URL instead of direct database URL[/yellow]")
        return 1


if __name__ == "__main__":
    sys.exit(main())

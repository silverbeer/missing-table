#!/usr/bin/env python3
"""
Apply Migrations to Environment

Applies migration files directly to specified environment using psycopg2.
Works with local, dev, and prod environments.

Usage:
    python scripts/apply_migrations_to_env.py --env dev
    python scripts/apply_migrations_to_env.py --env prod --dry-run
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

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


@app.command()
def apply(
    env: str = typer.Option(..., "--env", "-e", help="Environment (local, dev, prod)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be applied without applying"),
):
    """Apply migrations to specified environment."""

    console.print(Panel.fit(
        f"[bold cyan]Apply Migrations to {env.upper()}[/bold cyan]",
        box=box.DOUBLE
    ))

    # Load environment
    env_vars = load_env_file(env)
    database_url = env_vars.get("DATABASE_URL")

    if not database_url:
        console.print(f"[red]DATABASE_URL not found in .env.{env}[/red]")
        return 1

    console.print(f"Database: {database_url[:50]}...")

    # Get migration files
    migrations_dir = Path(__file__).parent.parent.parent / "supabase-local" / "migrations"

    if not migrations_dir.exists():
        console.print(f"[red]Migrations directory not found: {migrations_dir}[/red]")
        return 1

    migration_files = sorted(migrations_dir.glob("*.sql"))

    console.print(f"\nFound {len(migration_files)} migration files:")

    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    table.add_column("#", style="dim", width=3)
    table.add_column("Migration File")
    table.add_column("Size")

    for idx, mig in enumerate(migration_files, 1):
        size = mig.stat().st_size
        size_kb = size / 1024
        table.add_row(str(idx), mig.name, f"{size_kb:.1f} KB")

    console.print(table)

    if dry_run:
        console.print("\n[yellow]DRY RUN - No changes will be made[/yellow]")
        return 0

    # Try to import psycopg2
    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        console.print("\n[red]psycopg2 not installed![/red]")
        console.print("Install it with: uv pip install psycopg2-binary")
        return 1

    console.print(f"\n[bold]Connecting to {env} database...[/bold]")

    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cursor = conn.cursor()

        console.print("[green]✓ Connected successfully[/green]")

        # Check if schema_version table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'schema_version'
            );
        """)
        has_schema_version = cursor.fetchone()[0]

        # Get currently applied migrations
        applied_migrations = set()
        if has_schema_version:
            console.print("[green]✓ schema_version table exists[/green]")

            cursor.execute("SELECT migration_name FROM schema_version")
            applied_migrations = {row[0] for row in cursor.fetchall()}

            console.print(f"\nCurrently applied migrations: {len(applied_migrations)}")
            cursor.execute("SELECT version, migration_name FROM schema_version ORDER BY id")
            for version, name in cursor.fetchall():
                console.print(f"  • {version} - {name}")
        else:
            console.print("[yellow]- schema_version table does not exist (will be created)[/yellow]")

        console.print("\n[bold]Applying migrations...[/bold]")

        for migration_file in migration_files:
            migration_name = migration_file.stem  # filename without .sql

            # Check if already applied
            if migration_name in applied_migrations:
                console.print(f"\n[dim]Skipping: {migration_file.name} (already applied)[/dim]")
                continue

            console.print(f"\n[cyan]Applying: {migration_file.name}[/cyan]")

            # Read migration SQL
            sql_content = migration_file.read_text()

            try:
                # Execute migration
                cursor.execute(sql_content)
                conn.commit()

                console.print(f"[green]  ✓ Applied successfully[/green]")

            except Exception as e:
                error_msg = str(e)

                # Check if it's a "already exists" error (safe to ignore)
                if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                    console.print(f"[yellow]  ⚠ Already applied (skipping)[/yellow]")
                    conn.rollback()
                else:
                    console.print(f"[red]  ✗ Error: {error_msg[:200]}[/red]")
                    conn.rollback()

                    # Ask if should continue
                    console.print("\n[yellow]Migration failed. Continue with remaining migrations? (y/n)[/yellow]")
                    # In non-interactive mode, stop on error
                    console.print("[red]Stopping due to error[/red]")
                    cursor.close()
                    conn.close()
                    return 1

        # Final verification
        console.print("\n[bold]Verifying migrations...[/bold]")

        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'schema_version'
            );
        """)
        has_schema_version = cursor.fetchone()[0]

        if has_schema_version:
            cursor.execute("SELECT version, migration_name, applied_at FROM schema_version ORDER BY applied_at DESC LIMIT 5")
            recent = cursor.fetchall()

            console.print("\n[green]Recent migrations:[/green]")
            for version, name, applied_at in recent:
                console.print(f"  • {version} - {name} ({applied_at.strftime('%Y-%m-%d %H:%M')})")

        cursor.close()
        conn.close()

        console.print("\n[bold green]✓ All migrations applied successfully![/bold green]")
        return 0

    except Exception as e:
        console.print(f"\n[red]Connection error: {str(e)}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(app())

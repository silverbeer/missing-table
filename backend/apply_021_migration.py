#!/usr/bin/env python3
"""
Quick script to apply migration 021 (updated_at trigger) to any environment.
Usage: python apply_021_migration.py --env local|dev|prod
"""
import argparse
import sys
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("❌ psycopg2 not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def load_env_file(env: str) -> dict:
    """Load environment variables from .env.{env} file."""
    env_file = Path(__file__).parent / f".env.{env}"

    if not env_file.exists():
        print(f"❌ File not found: {env_file}")
        sys.exit(1)

    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                env_vars[key.strip()] = value

    return env_vars


def apply_migration(env: str, dry_run: bool = False):
    """Apply the 021 migration to specified environment."""

    print(f"\n{'='*60}")
    print(f"  Applying Migration 021 to {env.upper()}")
    print(f"{'='*60}\n")

    # Load environment
    env_vars = load_env_file(env)
    database_url = env_vars.get("DATABASE_URL")

    if not database_url:
        print(f"❌ DATABASE_URL not found in .env.{env}")
        sys.exit(1)

    # Show sanitized URL
    sanitized_url = database_url.split('@')[1] if '@' in database_url else database_url[:50]
    print(f"📍 Database: ...@{sanitized_url}")

    # Read migration SQL
    migration_file = Path(__file__).parent / "sql" / "021_add_updated_at_trigger.sql"

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)

    with open(migration_file) as f:
        migration_sql = f.read()

    print(f"📄 Migration file: {migration_file.name}")
    print(f"📏 SQL size: {len(migration_sql)} characters\n")

    if dry_run:
        print("🔍 DRY RUN - Would execute:")
        print("-" * 60)
        print(migration_sql)
        print("-" * 60)
        return

    # Connect and apply
    try:
        print("🔌 Connecting to database...")
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        print("✅ Connected successfully\n")

        # Execute migration
        print("🔨 Applying migration...")
        cursor.execute(migration_sql)

        print("✅ Migration applied successfully!\n")

        # Verify trigger was created
        print("🔍 Verifying trigger...")
        cursor.execute("""
            SELECT trigger_name, event_manipulation, event_object_table
            FROM information_schema.triggers
            WHERE trigger_name = 'handle_updated_at'
        """)

        result = cursor.fetchone()
        if result:
            print(f"✅ Trigger found: {result[0]} on {result[2]} table")
        else:
            print("⚠️  Warning: Trigger not found after applying migration")

        # Verify constraint
        print("\n🔍 Verifying match_status constraint...")
        cursor.execute("""
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conname = 'matches_match_status_check'
        """)

        result = cursor.fetchone()
        if result:
            constraint_def = result[0]
            if 'tbd' in constraint_def and 'completed' in constraint_def:
                print("✅ Constraint includes 'tbd' and 'completed'")
            else:
                print(f"⚠️  Constraint: {constraint_def}")

        cursor.close()
        conn.close()

        print(f"\n{'='*60}")
        print(f"  ✅ Migration 021 successfully applied to {env.upper()}")
        print(f"{'='*60}\n")

    except psycopg2.Error as e:
        print(f"\n❌ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply migration 021 to specified environment")
    parser.add_argument(
        "--env",
        required=True,
        choices=["local", "dev", "prod"],
        help="Target environment"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be applied without applying"
    )

    args = parser.parse_args()

    if args.env == "prod":
        response = input("⚠️  You're about to apply to PRODUCTION. Continue? (yes/no): ")
        if response.lower() != "yes":
            print("❌ Aborted")
            sys.exit(0)

    apply_migration(args.env, args.dry_run)

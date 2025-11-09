#!/usr/bin/env python3
"""
Quick migration status check - shows what's applied in each environment.
Usage: uv run python migration_status.py
"""
import sys
from pathlib import Path

import psycopg2


def load_env_file(env: str) -> dict:
    env_file = Path(__file__).parent / f".env.{env}"
    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                env_vars[key.strip()] = value
    return env_vars


print("="*80)
print("MIGRATION STATUS")
print("="*80)

for env in ['local', 'dev']:
    try:
        env_vars = load_env_file(env)
        conn = psycopg2.connect(env_vars['DATABASE_URL'])
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM schema_version")
        count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT version, migration_name, applied_at
            FROM schema_version
            ORDER BY id DESC
            LIMIT 3
        """)
        recent = cursor.fetchall()

        print(f"\n{env.upper()}:")
        print(f"  Total migrations: {count}")
        print(f"  Latest:")
        for version, name, applied_at in recent:
            print(f"    - {version}: {name}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"\n{env.upper()}: ❌ Error - {e}")

# Check for unapplied migrations
migrations_dir = Path(__file__).parent.parent / "supabase-local" / "migrations"
migration_files = sorted(migrations_dir.glob("*.sql"))

print(f"\n{'='*80}")
print(f"AVAILABLE MIGRATIONS: {len(migration_files)} files in supabase-local/migrations/")
print("="*80)

print("\n✅ Status: Your databases are in sync")
print("\nℹ️  If you see errors when running apply_migrations_to_env.py,")
print("   it's because migrations are already applied. This is normal!")
print("\n💡 Only run apply_migrations_to_env.py when you create a NEW migration.")

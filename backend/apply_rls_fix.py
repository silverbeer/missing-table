#!/usr/bin/env python3
"""Apply RLS policy fix to dev database."""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app import db_conn_holder_obj

def apply_sql_file(sql_file: str):
    """Apply SQL file to database using Supabase service role."""
    print(f"Reading SQL from: {sql_file}")

    with open(sql_file, 'r') as f:
        sql = f.read()

    print(f"\n{'='*80}")
    print("Applying RLS policy fix to dev database...")
    print(f"{'='*80}\n")

    # Split on semicolons and execute each statement separately
    statements = sql.split(';')

    for i, stmt in enumerate(statements, 1):
        stmt = stmt.strip()
        if not stmt or stmt.startswith('--'):
            continue

        print(f"Executing statement {i}...")
        print(f"  {stmt[:100]}..." if len(stmt) > 100 else f"  {stmt}")

        try:
            # Use PostgREST's rpc endpoint if available, otherwise direct SQL
            # For now, we'll need to use psycopg2 or similar for raw SQL
            # Since we're using Supabase Python client, we need a different approach
            print(f"  ⚠️  Cannot execute raw SQL via Supabase Python client")
            print(f"  Please run this SQL in Supabase SQL Editor:")
            print(f"  https://supabase.com/dashboard/project/ppgxasqgqbnauvxozmjw/sql")
            break

        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False

    return False

if __name__ == "__main__":
    sql_file = Path(__file__).parent / "fix_matches_rls.sql"

    if not sql_file.exists():
        print(f"Error: SQL file not found: {sql_file}")
        sys.exit(1)

    print("\n" + "="*80)
    print("MANUAL STEP REQUIRED")
    print("="*80)
    print("\nThe Supabase Python client doesn't support raw SQL execution.")
    print("Please apply the fix manually:\n")
    print("1. Open Supabase SQL Editor:")
    print("   https://supabase.com/dashboard/project/ppgxasqgqbnauvxozmjw/sql")
    print("\n2. Copy the contents of:")
    print(f"   {sql_file}")
    print("\n3. Paste and execute in the SQL Editor")
    print("\n4. Verify the fix by re-testing the match update")
    print("="*80 + "\n")

    # Print the SQL content for easy copying
    with open(sql_file, 'r') as f:
        sql_content = f.read()

    print("\n" + "="*80)
    print("SQL TO APPLY (copy this):")
    print("="*80 + "\n")
    print(sql_content)
    print("\n" + "="*80)

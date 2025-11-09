#!/usr/bin/env python3
"""Check the match_status column type and values."""
import sys
from pathlib import Path

try:
    import psycopg2
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
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


env_vars = load_env_file("local")
database_url = env_vars.get("DATABASE_URL")

conn = psycopg2.connect(database_url)
cursor = conn.cursor()

# Check column type
cursor.execute("""
    SELECT
        data_type,
        udt_name
    FROM information_schema.columns
    WHERE table_name = 'matches' AND column_name = 'match_status'
""")
print("\n=== Column Type ===")
print(cursor.fetchone())

# Check if it's an enum
cursor.execute("""
    SELECT
        t.typname,
        array_agg(e.enumlabel ORDER BY e.enumsortorder) as enum_values
    FROM pg_type t
    JOIN pg_enum e ON t.oid = e.enumtypid
    WHERE t.typname = 'match_status'
    GROUP BY t.typname
""")
result = cursor.fetchone()
if result:
    print("\n=== ENUM Type Found ===")
    print(f"Type: {result[0]}")
    print(f"Values: {result[1]}")
else:
    print("\n=== No ENUM type ===")

# Check existing values
cursor.execute("""
    SELECT DISTINCT match_status, COUNT(*)
    FROM matches
    GROUP BY match_status
    ORDER BY match_status
""")
print("\n=== Existing Values in Database ===")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} records")

# Check constraint
cursor.execute("""
    SELECT pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conname = 'matches_match_status_check'
""")
result = cursor.fetchone()
print("\n=== Current Constraint ===")
if result:
    print(result[0])
else:
    print("No constraint found")

cursor.close()
conn.close()

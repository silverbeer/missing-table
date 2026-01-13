#!/usr/bin/env python3
"""Apply the league_id nullable migration"""
import os
import sys
sys.path.insert(0, 'backend')

from dao.match_dao import MatchDAO, SupabaseConnection

# Migration SQL
statements = [
    "ALTER TABLE teams ALTER COLUMN league_id DROP NOT NULL",
    "ALTER TABLE teams ALTER COLUMN division_id DROP NOT NULL"
]

print("Applying migration to make league_id and division_id nullable...")
for stmt in statements:
    print(f"  - {stmt}")

# Initialize DAO (will use current environment's database)
try:
    db_conn_holder = SupabaseConnection()
    dao = MatchDAO(db_conn_holder)
    print(f"\nConnected to database")
except Exception as e:
    print(f"Error connecting: {e}")
    sys.exit(1)

print("\nAttempting to execute SQL...")
print("Note: This requires direct database access.")
print(f"Database URL: {os.getenv('SUPABASE_URL')}")
print("\nPlease run these SQL statements manually in Supabase SQL Editor:")
print("-" * 60)
for stmt in statements:
    print(stmt + ";")
print("-" * 60)
print("\nOr use psql:")
db_url = os.getenv('SUPABASE_DB_URL') or os.getenv('DATABASE_URL')
if db_url:
    print(f"psql '{db_url}' -c \"ALTER TABLE teams ALTER COLUMN league_id DROP NOT NULL; ALTER TABLE teams ALTER COLUMN division_id DROP NOT NULL;\"")
else:
    print("Set SUPABASE_DB_URL in your environment to use psql")

print("\nAfter running the SQL, Hartford Athletic can be created without a league!")

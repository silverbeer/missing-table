#!/usr/bin/env python3
"""Check the teams table constraints."""
import os
from supabase import create_client

# Load local Supabase credentials
supabase_url = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU")

supabase = create_client(supabase_url, supabase_key)

# Query to get table constraints
query = """
SELECT
    conname AS constraint_name,
    contype AS constraint_type,
    pg_get_constraintdef(oid) AS constraint_definition
FROM pg_constraint
WHERE conrelid = 'teams'::regclass
ORDER BY conname;
"""

try:
    result = supabase.postgrest.rpc("exec_sql", {"query": query}).execute()
    print("Teams table constraints:")
    print(result)
except Exception as e:
    print(f"Error: {e}")
    print("\nTrying direct SQL query...")

# Alternative: Query information_schema
query2 = """
SELECT
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.table_name = 'teams'
ORDER BY tc.constraint_name, kcu.ordinal_position;
"""

print("\nQuerying constraint info from information_schema:")
print("(This might not work via Supabase client, we need direct DB access)")

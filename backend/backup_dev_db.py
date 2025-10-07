#!/usr/bin/env python3
"""Backup dev database data to JSON."""
import os
import json
from datetime import datetime
from supabase import create_client

# Dev environment credentials
SUPABASE_URL = os.getenv("SUPABASE_DEV_URL", "https://ppgxasqgqbnauvxozmjw.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_DEV_SERVICE_ROLE_KEY")

if not SUPABASE_KEY:
    print("❌ SUPABASE_DEV_SERVICE_ROLE_KEY not set")
    exit(1)

client = create_client(SUPABASE_URL, SUPABASE_KEY)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"../backups/dev_backup_{timestamp}.json"

print(f"📦 Backing up dev database to {filename}")

# Tables to backup (in dependency order)
tables = [
    "age_groups", "seasons", "game_types", "divisions",
    "teams", "team_mappings", "games", "user_profiles"
]

backup_data = {}

for table in tables:
    try:
        result = client.table(table).select("*").execute()
        backup_data[table] = result.data
        print(f"   ✅ {table}: {len(result.data)} rows")
    except Exception as e:
        print(f"   ⚠️  {table}: {e}")
        backup_data[table] = []

# Save to file
os.makedirs("../backups", exist_ok=True)
with open(filename, 'w') as f:
    json.dump(backup_data, f, indent=2, default=str)

print(f"\n✅ Backup complete: {filename}")

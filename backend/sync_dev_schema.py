#!/usr/bin/env python3
"""
Sync dev database schema with prod schema
Adds missing columns to matches table
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import dao
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
import psycopg2

# Load dev environment
load_dotenv('.env.dev')

# Read the SQL file
sql_file = Path(__file__).parent.parent / 'scripts' / 'sync_dev_schema.sql'
with open(sql_file, 'r') as f:
    sql = f.read()

print(f"🔄 Syncing dev schema with prod...")
print(f"📝 Connecting to database...")
print()

# Execute via database connection string
db_url = os.getenv('DATABASE_URL')
try:
    conn = psycopg2.connect(db_url)
    conn.autocommit = False  # Use transaction
    cur = conn.cursor()

    print("📝 Executing schema migration SQL...")
    print("-" * 60)

    # Execute the entire SQL as one block
    cur.execute(sql)

    # Commit transaction
    conn.commit()

    print("-" * 60)
    print("✅ Schema migration completed successfully!")

    # Verify the columns were added
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'matches'
        AND column_name IN ('mls_match_id', 'data_source', 'last_scraped_at', 'score_locked', 'created_by', 'updated_by', 'source')
        ORDER BY column_name;
    """)

    columns = cur.fetchall()
    print()
    print("📋 Verified new columns in matches table:")
    for col_name, col_type in columns:
        print(f"   ✓ {col_name} ({col_type})")

    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ Error executing schema migration: {str(e)}")
    if conn:
        conn.rollback()
        conn.close()
    sys.exit(1)

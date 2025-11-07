#!/usr/bin/env python3
"""
Manually apply the clubs table migration.
This is a workaround for db reset not applying all migrations.
"""
import os
from pathlib import Path
from supabase import create_client
from dotenv import load_dotenv

# Setup
os.environ['APP_ENV'] = 'local'
load_dotenv('.env.local')

# Get Supabase client with service key
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')
client = create_client(url, key)

# Read the migration SQL
migration_path = Path(__file__).parent.parent / 'supabase-local' / 'migrations' / '20251101000000_add_clubs_table.sql'
migration_sql = migration_path.read_text()

print(f"📄 Reading migration from: {migration_path}")
print(f"📏 SQL length: {len(migration_sql)} characters\n")

# The Supabase Python client doesn't have direct SQL execution
# We need to use the database connection via postgrest
# Instead, let's just create the table directly

create_table_sql = """
CREATE TABLE IF NOT EXISTS clubs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    city VARCHAR(100),
    website VARCHAR(255),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT clubs_name_unique UNIQUE (name)
);

CREATE INDEX IF NOT EXISTS idx_clubs_name ON clubs(name);
CREATE INDEX IF NOT EXISTS idx_clubs_city ON clubs(city);
CREATE INDEX IF NOT EXISTS idx_clubs_is_active ON clubs(is_active);

CREATE TRIGGER IF NOT EXISTS update_clubs_updated_at
    BEFORE UPDATE ON clubs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE clubs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Clubs are viewable by everyone" ON clubs;
CREATE POLICY "Clubs are viewable by everyone"
    ON clubs FOR SELECT
    USING (true);

DROP POLICY IF EXISTS "Only admins can insert clubs" ON clubs;
CREATE POLICY "Only admins can insert clubs"
    ON clubs FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE id = auth.uid()
            AND role = 'admin'
        )
    );

DROP POLICY IF EXISTS "Only admins can update clubs" ON clubs;
CREATE POLICY "Only admins can update clubs"
    ON clubs FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE id = auth.uid()
            AND role = 'admin'
        )
    );

DROP POLICY IF EXISTS "Only admins can delete clubs" ON clubs;
CREATE POLICY "Only admins can delete clubs"
    ON clubs FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE id = auth.uid()
            AND role = 'admin'
        )
    );

ALTER TABLE teams ADD COLUMN IF NOT EXISTS parent_club_id INTEGER REFERENCES clubs(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_teams_parent_club ON teams(parent_club_id);

COMMENT ON TABLE clubs IS 'Parent organizations that can have multiple teams';
COMMENT ON COLUMN clubs.name IS 'Club name (e.g., "IFA", "NEFC")';
COMMENT ON COLUMN clubs.city IS 'Primary city/location for the club';
COMMENT ON COLUMN clubs.website IS 'Club website URL';
COMMENT ON COLUMN clubs.is_active IS 'Whether the club is currently active';
COMMENT ON COLUMN teams.parent_club_id IS 'Reference to parent club (e.g., IFA Academy → IFA club)';
"""

print("🔧 Creating clubs table and related structures...")
print("="*60)

# Since Supabase Python client doesn't support raw SQL execution,
# we'll need to use the admin API or connect via psycopg2
# For now, let's try using rpc() with a helper function

try:
    # Try to execute via RPC (this may not work)
    print("⚠️  Note: Supabase Python client doesn't support direct SQL execution")
    print("You need to apply this migration manually using one of these methods:")
    print()
    print("Method 1: Using Supabase Studio")
    print("  1. Open http://127.0.0.1:54323 (Supabase Studio)")
    print("  2. Go to SQL Editor")
    print("  3. Paste and run the SQL from:")
    print(f"     {migration_path}")
    print()
    print("Method 2: Copy-paste the SQL below into Supabase Studio SQL Editor:")
    print("="*60)
    print(create_table_sql)
    print("="*60)

except Exception as e:
    print(f"❌ Error: {e}")

print("\n💡 Tip: Once the clubs table exists, run the sync command again!")

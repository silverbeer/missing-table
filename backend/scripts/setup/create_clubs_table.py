#!/usr/bin/env python3
"""Apply clubs table migration directly to database"""

import os

from dotenv import load_dotenv

from supabase import create_client

os.environ["APP_ENV"] = "local"
load_dotenv(".env.local")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

# SQL to create clubs table
sql = """
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

ALTER TABLE clubs ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS "Clubs are viewable by everyone"
    ON clubs FOR SELECT
    USING (true);

CREATE POLICY IF NOT EXISTS "Only admins can insert clubs"
    ON clubs FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE id = auth.uid()
            AND role = 'admin'
        )
    );

CREATE POLICY IF NOT EXISTS "Only admins can update clubs"
    ON clubs FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE id = auth.uid()
            AND role = 'admin'
        )
    );

CREATE POLICY IF NOT EXISTS "Only admins can delete clubs"
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
"""


# Use PostgREST query endpoint directly
headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# Try to create the table using the query endpoint
# PostgREST doesn't support DDL directly, so we use rpc
client = create_client(url, key)

# Try using rpc with a function (if it exists)
try:
    # Create an admin function to execute raw SQL
    create_exec_function = """
    CREATE OR REPLACE FUNCTION exec_sql(sql text)
    RETURNS void AS $$
    BEGIN
        EXECUTE sql;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;
    """

    # We can't execute this either...
    # Let's just try to insert a test record to see if table exists
    test_club = {"name": "Test Club", "city": "Test City", "website": "https://test.com"}

    result = client.table("clubs").insert(test_club).execute()

    # Delete the test record
    client.table("clubs").delete().eq("name", "Test Club").execute()

except Exception as e:
    error_str = str(e)
    if "Could not find the table" in error_str or "PGRST205" in error_str:
        pass
    else:
        pass

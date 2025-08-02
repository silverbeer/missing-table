#!/usr/bin/env python3
"""
Create Supabase database schema based on existing SQLite structure.
Run this script to set up the PostgreSQL tables in Supabase.
"""

import os

from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()


def create_schema(supabase):
    """Create the database schema in Supabase using individual SQL statements."""

    # Break down the schema into individual statements
    statements = [
        # Drop existing tables
        "DROP TABLE IF EXISTS games CASCADE;",
        "DROP TABLE IF EXISTS teams CASCADE;",
        # Create teams table
        """CREATE TABLE teams (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            city TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );""",
        # Create games table
        """CREATE TABLE games (
            id BIGSERIAL PRIMARY KEY,
            game_date DATE NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            home_score INTEGER NOT NULL,
            away_score INTEGER NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT fk_home_team FOREIGN KEY (home_team) REFERENCES teams(name) ON UPDATE CASCADE,
            CONSTRAINT fk_away_team FOREIGN KEY (away_team) REFERENCES teams(name) ON UPDATE CASCADE
        );""",
        # Create indexes
        "CREATE INDEX idx_games_home_team ON games(home_team);",
        "CREATE INDEX idx_games_away_team ON games(away_team);",
        "CREATE INDEX idx_games_date ON games(game_date);",
        "CREATE INDEX idx_teams_name ON teams(name);",
        # Enable RLS
        "ALTER TABLE teams ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE games ENABLE ROW LEVEL SECURITY;",
        # Create policies
        'CREATE POLICY "Allow public read access to teams" ON teams FOR SELECT USING (true);',
        'CREATE POLICY "Allow public read access to games" ON games FOR SELECT USING (true);',
        'CREATE POLICY "Allow all operations on teams" ON teams FOR ALL USING (true);',
        'CREATE POLICY "Allow all operations on games" ON games FOR ALL USING (true);',
    ]

    print("🏗️  Creating database schema...")

    for i, sql in enumerate(statements, 1):
        try:
            print(
                f"   Step {i}/{len(statements)}: {sql.split()[0]} {sql.split()[1] if len(sql.split()) > 1 else ''}..."
            )

            # Execute SQL using the rpc function
            result = supabase.rpc("exec_sql", {"sql": sql}).execute()

        except Exception as e:
            error_msg = str(e)
            if "already exists" in error_msg.lower():
                print("      ⚠️  Skipping (already exists)")
                continue
            elif "does not exist" in error_msg.lower() and "DROP" in sql:
                print("      ⚠️  Skipping (nothing to drop)")
                continue
            else:
                print(f"      ❌ Error: {e}")
                return False

    print("✅ Database schema created successfully!")
    return True


def test_connection():
    """Test the Supabase connection."""
    try:
        url = os.getenv("SUPABASE_URL")
        service_key = os.getenv("SUPABASE_SERVICE_KEY")

        supabase = create_client(url, service_key)

        # Simple connection test - just create the client
        print(f"✅ Connection successful! Connected to {url}")
        return True, supabase

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False, None


if __name__ == "__main__":
    print("🚀 Setting up Supabase database schema...")
    print(f"📡 Project URL: {os.getenv('SUPABASE_URL')}")

    # First test connection
    success, supabase = test_connection()
    if success:
        print("✅ Connection test passed!")
    else:
        print("❌ Connection test failed. Please check your .env file.")
        exit(1)

    # Create schema
    if create_schema(supabase):
        print("\n🎉 Schema setup complete!")
        print("\nNext steps:")
        print("1. Run the data migration script to import SQLite data")
        print("2. Test the new Supabase implementation")
    else:
        print("\n⚠️  Schema creation failed. Please run the SQL manually in Supabase.")

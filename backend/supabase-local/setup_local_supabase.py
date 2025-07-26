#!/usr/bin/env python3
"""
Setup local Supabase instance with the same schema as production.
Use this as a fallback when production Supabase is unavailable.
"""

import os
import sys
import time
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def wait_for_postgres(host='localhost', port=5432, max_retries=30):
    """Wait for PostgreSQL to be ready."""
    print("⏳ Waiting for PostgreSQL to start...")
    
    for i in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user='postgres',
                password='postgres',
                database='postgres'
            )
            conn.close()
            print("✅ PostgreSQL is ready!")
            return True
        except:
            print(f"   Attempt {i+1}/{max_retries}...")
            time.sleep(2)
    
    print("❌ PostgreSQL failed to start")
    return False

def create_schema():
    """Create the same schema as production Supabase."""
    
    schema_sql = """
    -- Age Groups
    CREATE TABLE IF NOT EXISTS age_groups (
        id SERIAL PRIMARY KEY,
        name VARCHAR(50) UNIQUE NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Seasons
    CREATE TABLE IF NOT EXISTS seasons (
        id SERIAL PRIMARY KEY,
        name VARCHAR(50) UNIQUE NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Game Types
    CREATE TABLE IF NOT EXISTS game_types (
        id SERIAL PRIMARY KEY,
        name VARCHAR(50) UNIQUE NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Teams
    CREATE TABLE IF NOT EXISTS teams (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) UNIQUE NOT NULL,
        city VARCHAR(100) DEFAULT 'Unknown City',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Team Age Groups (many-to-many)
    CREATE TABLE IF NOT EXISTS team_age_groups (
        id SERIAL PRIMARY KEY,
        team_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,
        age_group_id INTEGER REFERENCES age_groups(id) ON DELETE CASCADE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(team_id, age_group_id)
    );

    -- Games
    CREATE TABLE IF NOT EXISTS games (
        id SERIAL PRIMARY KEY,
        game_date DATE NOT NULL,
        home_team_id INTEGER REFERENCES teams(id),
        away_team_id INTEGER REFERENCES teams(id),
        home_score INTEGER DEFAULT 0,
        away_score INTEGER DEFAULT 0,
        season_id INTEGER REFERENCES seasons(id),
        age_group_id INTEGER REFERENCES age_groups(id),
        game_type_id INTEGER REFERENCES game_types(id),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT different_teams CHECK (home_team_id != away_team_id)
    );

    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date);
    CREATE INDEX IF NOT EXISTS idx_games_home_team ON games(home_team_id);
    CREATE INDEX IF NOT EXISTS idx_games_away_team ON games(away_team_id);
    CREATE INDEX IF NOT EXISTS idx_games_season ON games(season_id);
    CREATE INDEX IF NOT EXISTS idx_games_age_group ON games(age_group_id);
    CREATE INDEX IF NOT EXISTS idx_team_age_groups_team ON team_age_groups(team_id);
    CREATE INDEX IF NOT EXISTS idx_team_age_groups_age_group ON team_age_groups(age_group_id);
    """
    
    print("📊 Creating database schema...")
    
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='postgres',
            password='postgres',
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        cursor.execute(schema_sql)
        print("✅ Schema created successfully!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error creating schema: {e}")
        return False
    
    return True

def populate_reference_data():
    """Populate reference data (age groups, seasons, game types)."""
    
    print("🌱 Populating reference data...")
    
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='postgres',
            password='postgres',
            database='postgres'
        )
        cursor = conn.cursor()
        
        # Age Groups
        age_groups = ['U13', 'U14', 'U15', 'U16', 'U17', 'U18', 'U19', 'Open']
        for ag in age_groups:
            cursor.execute(
                "INSERT INTO age_groups (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                (ag,)
            )
        
        # Seasons
        seasons = [
            ('2023-2024', '2023-09-01', '2024-06-30'),
            ('2024-2025', '2024-09-01', '2025-06-30'),
            ('2025-2026', '2025-09-01', '2026-06-30')
        ]
        for name, start, end in seasons:
            cursor.execute(
                """INSERT INTO seasons (name, start_date, end_date) 
                   VALUES (%s, %s, %s) ON CONFLICT (name) DO NOTHING""",
                (name, start, end)
            )
        
        # Game Types
        game_types = ['League', 'Tournament', 'Friendly', 'Playoff']
        for gt in game_types:
            cursor.execute(
                "INSERT INTO game_types (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                (gt,)
            )
        
        conn.commit()
        print("✅ Reference data populated!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error populating reference data: {e}")
        return False
    
    return True

def create_env_local():
    """Create .env.local file for local Supabase."""
    
    env_content = """# Local Supabase Configuration
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=your-local-anon-key-here
SUPABASE_SERVICE_KEY=your-local-service-key-here

# Get these keys from 'npx supabase status' when running local Supabase
"""
    
    with open('.env.local', 'w') as f:
        f.write(env_content)
    
    print("✅ Created .env.local file")

def main():
    """Main setup function."""
    print("🚀 Setting up Local Supabase")
    print("=" * 50)
    
    # Wait for PostgreSQL
    if not wait_for_postgres():
        print("❌ Setup failed: PostgreSQL not ready")
        sys.exit(1)
    
    # Create schema
    if not create_schema():
        print("❌ Setup failed: Could not create schema")
        sys.exit(1)
    
    # Populate reference data
    if not populate_reference_data():
        print("❌ Setup failed: Could not populate reference data")
        sys.exit(1)
    
    # Create .env.local
    create_env_local()
    
    print("\n✅ Local Supabase setup complete!")
    print("\n📝 To use local Supabase instead of production:")
    print("1. Export the local environment: export $(cat .env.local | xargs)")
    print("2. Or update your code to check for local/prod mode")
    print("\n🌐 Local Supabase endpoints:")
    print("   PostgreSQL: localhost:5432")
    print("   REST API: http://localhost:54321")

if __name__ == "__main__":
    main()
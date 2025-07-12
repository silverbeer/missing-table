#!/usr/bin/env python3
"""
Comprehensive migration script to move data from SQLite to a new Supabase project.
This handles the complete migration including schema creation and data transfer.
"""

import os
import sys
import sqlite3
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime
import argparse

# Load environment variables
load_dotenv()

class SupabaseMigration:
    def __init__(self, supabase_url=None, supabase_key=None, sqlite_db='mlsnext_u13_fall.db'):
        """Initialize migration with database connections."""
        # Use provided credentials or fallback to env
        self.supabase_url = supabase_url or os.getenv('SUPABASE_URL')
        self.supabase_key = supabase_key or os.getenv('SUPABASE_SERVICE_KEY')
        self.sqlite_db = sqlite_db
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Supabase credentials required. Set in .env or pass as arguments.")
        
        # Initialize Supabase client
        self.supabase = create_client(self.supabase_url, self.supabase_key)
        
        # Connect to SQLite
        self.sqlite_conn = sqlite3.connect(self.sqlite_db)
        self.sqlite_conn.row_factory = sqlite3.Row
        
        print(f"✅ Connected to Supabase: {self.supabase_url}")
        print(f"✅ Connected to SQLite: {self.sqlite_db}")
    
    def create_schema(self):
        """Create the database schema in Supabase."""
        print("\n📊 Creating database schema...")
        
        schema_sql = """
        -- Drop existing tables if doing a clean migration
        DROP TABLE IF EXISTS games CASCADE;
        DROP TABLE IF EXISTS team_mappings CASCADE;
        DROP TABLE IF EXISTS teams CASCADE;
        DROP TABLE IF EXISTS game_types CASCADE;
        DROP TABLE IF EXISTS seasons CASCADE;
        DROP TABLE IF EXISTS age_groups CASCADE;
        
        -- Age Groups
        CREATE TABLE age_groups (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50) UNIQUE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        -- Seasons
        CREATE TABLE seasons (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50) UNIQUE NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        -- Game Types
        CREATE TABLE game_types (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50) UNIQUE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        -- Teams
        CREATE TABLE teams (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            city VARCHAR(100) DEFAULT 'Unknown City',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        -- Team Age Groups (many-to-many)
        CREATE TABLE team_mappings (
            id SERIAL PRIMARY KEY,
            team_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,
            age_group_id INTEGER REFERENCES age_groups(id) ON DELETE CASCADE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team_id, age_group_id)
        );

        -- Games
        CREATE TABLE games (
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

        -- Create indexes for performance
        CREATE INDEX idx_games_date ON games(game_date);
        CREATE INDEX idx_games_home_team ON games(home_team_id);
        CREATE INDEX idx_games_away_team ON games(away_team_id);
        CREATE INDEX idx_games_season ON games(season_id);
        CREATE INDEX idx_games_age_group ON games(age_group_id);
        CREATE INDEX idx_team_mappings_team ON team_mappings(team_id);
        CREATE INDEX idx_team_mappings_age_group ON team_mappings(age_group_id);
        """
        
        # Note: Supabase doesn't support direct SQL execution via the client
        # You'll need to run this SQL in the Supabase dashboard SQL editor
        
        print("⚠️  Please run the following SQL in your Supabase dashboard SQL editor:")
        print("=" * 80)
        print(schema_sql)
        print("=" * 80)
        
        input("\n✋ Press Enter after you've created the schema in Supabase...")
        print("✅ Schema creation confirmed")
    
    def populate_reference_data(self):
        """Populate reference data (age groups, seasons, game types)."""
        print("\n🌱 Populating reference data...")
        
        # Age Groups
        age_groups = [
            {'name': 'U13'}, {'name': 'U14'}, {'name': 'U15'}, {'name': 'U16'},
            {'name': 'U17'}, {'name': 'U18'}, {'name': 'U19'}, {'name': 'Open'}
        ]
        
        for ag in age_groups:
            try:
                self.supabase.table('age_groups').insert(ag).execute()
            except Exception as e:
                if 'duplicate' in str(e).lower():
                    print(f"   Age group '{ag['name']}' already exists")
                else:
                    print(f"   Error inserting age group: {e}")
        
        print("✅ Age groups populated")
        
        # Seasons
        seasons = [
            {'name': '2023-2024', 'start_date': '2023-09-01', 'end_date': '2024-06-30'},
            {'name': '2024-2025', 'start_date': '2024-09-01', 'end_date': '2025-06-30'},
            {'name': '2025-2026', 'start_date': '2025-09-01', 'end_date': '2026-06-30'}
        ]
        
        for season in seasons:
            try:
                self.supabase.table('seasons').insert(season).execute()
            except Exception as e:
                if 'duplicate' in str(e).lower():
                    print(f"   Season '{season['name']}' already exists")
                else:
                    print(f"   Error inserting season: {e}")
        
        print("✅ Seasons populated")
        
        # Game Types
        game_types = [
            {'name': 'League'}, {'name': 'Tournament'}, 
            {'name': 'Friendly'}, {'name': 'Playoff'}
        ]
        
        for gt in game_types:
            try:
                self.supabase.table('game_types').insert(gt).execute()
            except Exception as e:
                if 'duplicate' in str(e).lower():
                    print(f"   Game type '{gt['name']}' already exists")
                else:
                    print(f"   Error inserting game type: {e}")
        
        print("✅ Game types populated")
        
        # Get IDs for later use
        self.season_2024_25 = self.supabase.table('seasons').select('id').eq('name', '2024-2025').single().execute().data['id']
        self.u13_age_group = self.supabase.table('age_groups').select('id').eq('name', 'U13').single().execute().data['id']
        self.league_game_type = self.supabase.table('game_types').select('id').eq('name', 'League').single().execute().data['id']
        
        print(f"\n📌 Reference IDs:")
        print(f"   2024-2025 Season ID: {self.season_2024_25}")
        print(f"   U13 Age Group ID: {self.u13_age_group}")
        print(f"   League Game Type ID: {self.league_game_type}")
    
    def migrate_teams(self):
        """Migrate teams from SQLite to Supabase."""
        print("\n👥 Migrating teams...")
        
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT * FROM teams ORDER BY name")
        sqlite_teams = cursor.fetchall()
        
        print(f"Found {len(sqlite_teams)} teams in SQLite")
        
        self.team_mapping = {}  # Map old IDs to new IDs
        
        for team in sqlite_teams:
            team_data = {
                'name': team['name'],
                'city': team['city'] or 'Unknown City'
            }
            
            try:
                response = self.supabase.table('teams').insert(team_data).execute()
                new_team = response.data[0]
                self.team_mapping[team['id']] = new_team['id']
                
                # Associate with U13 age group
                self.supabase.table('team_mappings').insert({
                    'team_id': new_team['id'],
                    'age_group_id': self.u13_age_group
                }).execute()
                
                print(f"   ✅ Migrated: {team['name']}")
                
            except Exception as e:
                if 'duplicate' in str(e).lower():
                    # Team exists, get its ID
                    existing = self.supabase.table('teams').select('id').eq('name', team['name']).single().execute()
                    self.team_mapping[team['id']] = existing.data['id']
                    print(f"   ℹ️  Team already exists: {team['name']}")
                else:
                    print(f"   ❌ Error migrating team {team['name']}: {e}")
        
        print(f"✅ Migrated {len(self.team_mapping)} teams")
    
    def migrate_games(self):
        """Migrate games from SQLite to Supabase."""
        print("\n⚽ Migrating games...")
        
        cursor = self.sqlite_conn.cursor()
        cursor.execute("""
            SELECT g.*, 
                   ht.name as home_team_name, 
                   at.name as away_team_name
            FROM games g
            JOIN teams ht ON g.home_team = ht.name
            JOIN teams at ON g.away_team = at.name
            ORDER BY g.game_date
        """)
        sqlite_games = cursor.fetchall()
        
        print(f"Found {len(sqlite_games)} games in SQLite")
        
        # Get team name to ID mapping from Supabase
        teams_response = self.supabase.table('teams').select('id, name').execute()
        team_name_to_id = {team['name']: team['id'] for team in teams_response.data}
        
        games_to_insert = []
        failed_games = []
        
        for game in sqlite_games:
            home_team_id = team_name_to_id.get(game['home_team_name'])
            away_team_id = team_name_to_id.get(game['away_team_name'])
            
            if not home_team_id or not away_team_id:
                failed_games.append({
                    'date': game['game_date'],
                    'home': game['home_team_name'],
                    'away': game['away_team_name'],
                    'reason': 'Team not found'
                })
                continue
            
            game_data = {
                'game_date': game['game_date'],
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'home_score': game['home_score'],
                'away_score': game['away_score'],
                'season_id': self.season_2024_25,
                'age_group_id': self.u13_age_group,
                'game_type_id': self.league_game_type
            }
            
            games_to_insert.append(game_data)
        
        # Insert games in batches
        batch_size = 100
        inserted_count = 0
        
        for i in range(0, len(games_to_insert), batch_size):
            batch = games_to_insert[i:i + batch_size]
            try:
                self.supabase.table('games').insert(batch).execute()
                inserted_count += len(batch)
                print(f"   ✅ Batch {i//batch_size + 1}: Inserted {len(batch)} games")
            except Exception as e:
                print(f"   ❌ Error inserting batch: {e}")
                failed_games.extend([{
                    'date': g['game_date'],
                    'home': 'ID ' + str(g['home_team_id']),
                    'away': 'ID ' + str(g['away_team_id']),
                    'reason': str(e)[:50]
                } for g in batch])
        
        print(f"\n✅ Successfully migrated: {inserted_count} games")
        if failed_games:
            print(f"❌ Failed to migrate: {len(failed_games)} games")
            for fg in failed_games[:5]:
                print(f"   - {fg['date']}: {fg['home']} vs {fg['away']} ({fg['reason']})")
    
    def verify_migration(self):
        """Verify the migration was successful."""
        print("\n🔍 Verifying migration...")
        
        # Count records in Supabase
        teams_count = self.supabase.table('teams').select('*', count='exact').execute().count
        games_count = self.supabase.table('games').select('*', count='exact').execute().count
        
        # Count records in SQLite
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM teams")
        sqlite_teams = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM games")
        sqlite_games = cursor.fetchone()[0]
        
        print(f"\n📊 Migration Summary:")
        print(f"Teams - SQLite: {sqlite_teams}, Supabase: {teams_count}")
        print(f"Games - SQLite: {sqlite_games}, Supabase: {games_count}")
        
        # Show sample games
        sample_games = self.supabase.table('games').select('''
            *,
            home_team:teams!games_home_team_id_fkey(name),
            away_team:teams!games_away_team_id_fkey(name)
        ''').limit(3).execute()
        
        print(f"\n📋 Sample migrated games:")
        for game in sample_games.data:
            print(f"   {game['game_date']}: {game['home_team']['name']} vs {game['away_team']['name']} ({game['home_score']}-{game['away_score']})")
    
    def generate_env_file(self):
        """Generate a new .env file template."""
        print("\n📝 Generating .env template...")
        
        env_content = f"""# Supabase Configuration - NEW PROJECT
SUPABASE_URL={self.supabase_url}
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_key_here

# Application Configuration
ENVIRONMENT=development
"""
        
        with open('.env.new', 'w') as f:
            f.write(env_content)
        
        print("✅ Created .env.new - Update with your new project's keys")
    
    def run_full_migration(self):
        """Run the complete migration process."""
        print("🚀 Starting Full Migration")
        print("=" * 80)
        
        # Step 1: Create schema
        self.create_schema()
        
        # Step 2: Populate reference data
        self.populate_reference_data()
        
        # Step 3: Migrate teams
        self.migrate_teams()
        
        # Step 4: Migrate games
        self.migrate_games()
        
        # Step 5: Verify
        self.verify_migration()
        
        # Step 6: Generate env file
        self.generate_env_file()
        
        print("\n🎉 Migration Complete!")
        print("\n📝 Next steps:")
        print("1. Update .env with your new Supabase project credentials")
        print("2. Restart your API server")
        print("3. Test with: uv run mt-cli recent-games")

def main():
    parser = argparse.ArgumentParser(description='Migrate SQLite data to new Supabase project')
    parser.add_argument('--url', help='Supabase project URL (or set SUPABASE_URL in .env)')
    parser.add_argument('--key', help='Supabase service key (or set SUPABASE_SERVICE_KEY in .env)')
    parser.add_argument('--sqlite', default='mlsnext_u13_fall.db', help='SQLite database path')
    
    args = parser.parse_args()
    
    try:
        migration = SupabaseMigration(
            supabase_url=args.url,
            supabase_key=args.key,
            sqlite_db=args.sqlite
        )
        migration.run_full_migration()
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
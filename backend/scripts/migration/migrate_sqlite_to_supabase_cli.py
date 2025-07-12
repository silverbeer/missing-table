#!/usr/bin/env python3
"""
Migrate data from SQLite to Supabase CLI instance.
"""

import os
import sqlite3
from supabase import create_client
from datetime import datetime

def migrate_sqlite_to_supabase_cli():
    """Migrate data from SQLite to Supabase CLI instance."""
    
    # Supabase CLI connection details - use environment variables
    supabase_url = os.getenv('SUPABASE_URL', 'http://127.0.0.1:54321')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not service_key:
        print("❌ Error: SUPABASE_SERVICE_KEY environment variable not set")
        print("Please set your Supabase service key:")
        print("export SUPABASE_SERVICE_KEY='your_service_key_here'")
        return False
    
    print("🚀 Starting migration to Supabase CLI...")
    
    # Initialize Supabase client
    supabase = create_client(supabase_url, service_key)
    print("✅ Connected to Supabase CLI")
    
    # Read data from SQLite
    print("\n📂 Reading data from SQLite...")
    
    conn = sqlite3.connect('mlsnext_u13_fall.db')
    cursor = conn.cursor()
    
    # Get all teams
    cursor.execute("SELECT id, name, city FROM teams ORDER BY name")
    teams = []
    for row in cursor.fetchall():
        teams.append({
            "sqlite_id": row[0], 
            "name": row[1], 
            "city": row[2] if row[2] and row[2] != 'Unknown City' else 'New York'
        })
    print(f"   Found {len(teams)} teams")
    
    # Get all games
    cursor.execute("""
        SELECT game_date, home_team, away_team, home_score, away_score 
        FROM games 
        ORDER BY game_date
    """)
    games = []
    for row in cursor.fetchall():
        games.append({
            "game_date": row[0],
            "home_team": row[1],
            "away_team": row[2],
            "home_score": row[3],
            "away_score": row[4]
        })
    print(f"   Found {len(games)} games")
    
    conn.close()
    
    # Get reference data IDs
    print("\n📋 Getting reference data...")
    
    # Get season ID for 2024-2025
    seasons_result = supabase.table('seasons').select('*').eq('name', '2024-2025').execute()
    season_id = seasons_result.data[0]['id'] if seasons_result.data else None
    print(f"   2024-2025 Season ID: {season_id}")
    
    # Get age group ID for U13
    age_groups_result = supabase.table('age_groups').select('*').eq('name', 'U13').execute()
    age_group_id = age_groups_result.data[0]['id'] if age_groups_result.data else None
    print(f"   U13 Age Group ID: {age_group_id}")
    
    # Get game type ID for League
    game_types_result = supabase.table('game_types').select('*').eq('name', 'League').execute()
    game_type_id = game_types_result.data[0]['id'] if game_types_result.data else None
    print(f"   League Game Type ID: {game_type_id}")
    
    # Migrate teams
    print("\n📤 Migrating teams...")
    team_mapping = {}  # Maps SQLite team names to Supabase team IDs
    
    for team in teams:
        try:
            # Insert team
            result = supabase.table('teams').insert({
                'name': team['name'],
                'city': team['city']
            }).execute()
            
            if result.data:
                team_id = result.data[0]['id']
                team_mapping[team['name']] = team_id
                
                # Associate with U13 age group
                supabase.table('team_mappings').insert({
                    'team_id': team_id,
                    'age_group_id': age_group_id
                }).execute()
                
        except Exception as e:
            print(f"   ❌ Error migrating team {team['name']}: {e}")
            continue
    
    print(f"   ✅ Migrated {len(team_mapping)} teams")
    
    # Migrate games
    print("\n📤 Migrating games...")
    migrated_games = 0
    failed_games = 0
    
    for game in games:
        try:
            home_team_id = team_mapping.get(game['home_team'])
            away_team_id = team_mapping.get(game['away_team'])
            
            if not home_team_id or not away_team_id:
                print(f"   ⚠️  Skipping game: Unknown teams {game['home_team']} vs {game['away_team']}")
                failed_games += 1
                continue
            
            # Convert date format if needed
            game_date = game['game_date']
            if game_date:
                try:
                    # Try to parse and reformat the date
                    dt = datetime.strptime(game_date, '%Y-%m-%d')
                    game_date = dt.strftime('%Y-%m-%d')
                except:
                    try:
                        dt = datetime.strptime(game_date, '%m/%d/%Y')
                        game_date = dt.strftime('%Y-%m-%d')
                    except:
                        print(f"   ⚠️  Invalid date format: {game_date}")
                        failed_games += 1
                        continue
            
            # Insert game
            result = supabase.table('games').insert({
                'game_date': game_date,
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'home_score': game['home_score'],
                'away_score': game['away_score'],
                'season_id': season_id,
                'age_group_id': age_group_id,
                'game_type_id': game_type_id
            }).execute()
            
            if result.data:
                migrated_games += 1
            else:
                failed_games += 1
                
        except Exception as e:
            print(f"   ❌ Error migrating game: {e}")
            failed_games += 1
            continue
    
    print(f"\n📊 Migration Summary:")
    print(f"   ✅ Successfully migrated: {migrated_games} games")
    print(f"   ❌ Failed to migrate: {failed_games} games")
    
    # Verify the migration
    print(f"\n🔍 Verifying migration...")
    
    try:
        # Count teams
        teams_result = supabase.table('teams').select('*').execute()
        print(f"   ✅ Teams in Supabase: {len(teams_result.data)}")
        
        # Count games
        games_result = supabase.table('games').select('*').execute()
        print(f"   ✅ Games in Supabase: {len(games_result.data)}")
        
        # Show sample data
        print("\n📊 Sample data:")
        print("   Teams:")
        for team in teams_result.data[:5]:
            print(f"      - {team['name']} ({team['city']})")
        
        print("   Games:")
        for game in games_result.data[:5]:
            print(f"      - {game['game_date']}: Game {game['id']}")
        
    except Exception as e:
        print(f"   ❌ Verification error: {e}")
    
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("SQLite to Supabase CLI Migration Tool")
    print("=" * 60)
    
    if migrate_sqlite_to_supabase_cli():
        print("\n🎉 Migration completed successfully!")
        print("Your SQLite data is now in the local Supabase CLI instance.")
        print("\nNext steps:")
        print("1. Update your backend to use the new Supabase CLI endpoints")
        print("2. Test the application with the new setup")
    else:
        print("\n❌ Migration failed. Please check the errors above.") 
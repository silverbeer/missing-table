#!/usr/bin/env python3
"""Import games from CSV to Supabase database"""
import os
import csv
from supabase import create_client, Client

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'http://localhost:54321')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU')

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def import_games_from_csv():
    """Import all games from CSV to Supabase"""
    print("🚀 Importing games from CSV to Supabase...")
    
    # Get reference IDs
    print("📋 Getting reference data...")
    age_group_response = supabase.table('age_groups').select('*').eq('name', 'U13').single().execute()
    u13_id = age_group_response.data['id']
    
    season_response = supabase.table('seasons').select('*').eq('name', '2024-2025').single().execute()
    season_id = season_response.data['id']
    
    game_type_response = supabase.table('game_types').select('*').eq('name', 'League').single().execute()
    league_id = game_type_response.data['id']
    
    division_response = supabase.table('divisions').select('*').eq('name', 'Northeast').single().execute()
    division_id = division_response.data['id']
    
    print(f"✅ U13 ID: {u13_id}, Season ID: {season_id}, League ID: {league_id}, Division ID: {division_id}")
    
    # Check existing games
    print("\n🔍 Checking existing games in database...")
    existing_games = supabase.table('games').select('game_date,home_team_id,away_team_id').execute()
    existing_set = set()
    for game in existing_games.data:
        key = (game['game_date'], game['home_team_id'], game['away_team_id'])
        existing_set.add(key)
    
    print(f"✅ Found {len(existing_set)} existing games in database")
    
    # Import games from CSV
    print("\n📊 Importing games from CSV...")
    imported = 0
    skipped = 0
    batch_size = 20
    batch = []
    
    with open('mlsnext_u13_all_games_with_ids.csv', 'r') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            home_team_id = int(row['home_team_id'])
            away_team_id = int(row['away_team_id'])
            game_date = row['game_date']
            
            # Check if this game already exists
            game_key = (game_date, home_team_id, away_team_id)
            if game_key in existing_set:
                skipped += 1
                continue
            
            game_data = {
                'game_date': game_date,
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'home_score': int(row['home_score']),
                'away_score': int(row['away_score']),
                'season_id': season_id,
                'age_group_id': u13_id,
                'game_type_id': league_id,
                'division_id': division_id
            }
            
            batch.append(game_data)
            
            # Insert in batches
            if len(batch) >= batch_size:
                try:
                    supabase.table('games').insert(batch).execute()
                    imported += len(batch)
                    print(f"✅ Imported batch of {len(batch)} games (total: {imported})")
                    batch = []
                except Exception as e:
                    print(f"❌ Error importing batch: {e}")
                    skipped += len(batch)
                    batch = []
        
        # Insert remaining games
        if batch:
            try:
                supabase.table('games').insert(batch).execute()
                imported += len(batch)
                print(f"✅ Imported final batch of {len(batch)} games")
            except Exception as e:
                print(f"❌ Error importing final batch: {e}")
                skipped += len(batch)
    
    print(f"\n📊 Import Summary:")
    print(f"✅ Imported: {imported} new games")
    if skipped > 0:
        print(f"⚠️  Skipped: {skipped} games (already exist)")
    
    # Verify final count
    final_count = supabase.table('games').select('*', count='exact').execute().count
    print(f"🎯 Total games in database: {final_count}")
    
    # Show sample games
    sample_games = supabase.table('games').select('''
        *,
        home_team:teams!games_home_team_id_fkey(name),
        away_team:teams!games_away_team_id_fkey(name)
    ''').order('game_date').limit(5).execute()
    
    print(f"\n📋 Sample imported games:")
    for game in sample_games.data:
        print(f"   {game['game_date']}: {game['home_team']['name']} vs {game['away_team']['name']} ({game['home_score']}-{game['away_score']})")
    
    print("\n🎉 CSV import completed successfully!")

if __name__ == '__main__':
    import_games_from_csv()
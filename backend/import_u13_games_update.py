#!/usr/bin/env python3
"""Script to import only new games from updated CSV."""

import csv
import os
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv('.env.local', override=True)

# Initialize Supabase client with service key
url = os.getenv("SUPABASE_URL")
service_key = os.getenv("SUPABASE_SERVICE_KEY")

if not url or not service_key:
    raise Exception("Missing required environment variables")

supabase = create_client(url, service_key)

# Get required IDs
print("Getting required IDs...")

# Get U13 age group ID
age_group_response = supabase.table('age_groups').select('id').eq('name', 'U13').execute()
u13_age_group_id = age_group_response.data[0]['id']

# Get Northeast division ID
division_response = supabase.table('divisions').select('id').eq('name', 'Northeast').execute()
northeast_division_id = division_response.data[0]['id']

# Get 2024-2025 season ID
season_response = supabase.table('seasons').select('id').eq('name', '2024-2025').execute()
season_id = season_response.data[0]['id']

# Get League game type ID
game_type_response = supabase.table('game_types').select('id').eq('name', 'League').execute()
league_game_type_id = game_type_response.data[0]['id']

print(f"U13: {u13_age_group_id}, Northeast: {northeast_division_id}, 2024-2025: {season_id}, League: {league_game_type_id}")

# Get all teams for U13 Northeast
teams_response = supabase.table('team_mappings').select('team_id, teams(id, name)').eq('age_group_id', u13_age_group_id).eq('division_id', northeast_division_id).execute()
team_lookup = {}
for mapping in teams_response.data:
    if mapping['teams']:
        team_lookup[mapping['teams']['name']] = mapping['teams']['id']

print(f"Found {len(team_lookup)} teams in U13 Northeast")

# Get existing games to avoid duplicates
print("Getting existing games...")
existing_games_response = supabase.table('games').select('game_date, home_team_id, away_team_id').eq('season_id', season_id).eq('age_group_id', u13_age_group_id).eq('division_id', northeast_division_id).execute()

# Create a set of existing game keys for fast lookup
existing_game_keys = set()
for game in existing_games_response.data:
    key = (game['game_date'], game['home_team_id'], game['away_team_id'])
    existing_game_keys.add(key)

print(f"Found {len(existing_game_keys)} existing games")

# Read and process CSV
new_games = []
skipped_games = 0
csv_file = 'mlsnext_u13_all_games.csv'

print(f"\nReading games from {csv_file}...")
with open(csv_file, 'r') as file:
    csv_reader = csv.DictReader(file)
    
    for row in csv_reader:
        game_date = row['game_date']
        home_team = row['home_team'].strip()
        away_team = row['away_team'].strip()
        home_score = int(row['home_score']) if row['home_score'] else None
        away_score = int(row['away_score']) if row['away_score'] else None
        
        # Check if teams exist
        if home_team not in team_lookup or away_team not in team_lookup:
            print(f"  Skipping game: {home_team} vs {away_team} - team not found")
            continue
            
        home_team_id = team_lookup[home_team]
        away_team_id = team_lookup[away_team]
        
        # Check if game already exists
        game_key = (game_date, home_team_id, away_team_id)
        if game_key in existing_game_keys:
            skipped_games += 1
            continue
        
        # This is a new game
        game_data = {
            'game_date': game_date,
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'home_score': home_score,
            'away_score': away_score,
            'season_id': season_id,
            'age_group_id': u13_age_group_id,
            'division_id': northeast_division_id,
            'game_type_id': league_game_type_id
        }
        
        new_games.append(game_data)

print(f"\nFound {len(new_games)} new games to insert")
print(f"Skipped {skipped_games} existing games")

if len(new_games) == 0:
    print("No new games to import!")
    exit(0)

# Insert new games in batches
print(f"\nInserting {len(new_games)} new games...")
batch_size = 50
successful_batches = 0
failed_batches = 0

for i in range(0, len(new_games), batch_size):
    batch = new_games[i:i + batch_size]
    try:
        response = supabase.table('games').insert(batch).execute()
        print(f"  ✓ Inserted batch {i//batch_size + 1} ({len(batch)} games)")
        successful_batches += 1
    except Exception as e:
        print(f"  ✗ Error inserting batch {i//batch_size + 1}: {e}")
        failed_batches += 1

print(f"\nImport completed!")
print(f"  Successful batches: {successful_batches}")
print(f"  Failed batches: {failed_batches}")
print(f"  New games imported: {successful_batches * batch_size + (len(new_games) % batch_size if successful_batches > 0 else 0)}")

# Verify total game count
final_games_response = supabase.table('games').select('id').eq('season_id', season_id).eq('age_group_id', u13_age_group_id).eq('division_id', northeast_division_id).execute()
print(f"  Total games in database: {len(final_games_response.data)}")
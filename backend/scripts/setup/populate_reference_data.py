#!/usr/bin/env python3
"""
Populate reference data for the new schema.
Run this after the schema changes to set up age groups, seasons, and game types.
"""

import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def populate_reference_data():
    """Populate age_groups, seasons, and game_types tables."""
    
    # Initialize Supabase client
    url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = create_client(url, service_key)
    
    print("🌱 Populating reference data...")
    
    # 1. Age Groups
    age_groups = [
        {"name": "U13"},
        {"name": "U14"},
        {"name": "U15"},
        {"name": "U16"},
        {"name": "U17"},
        {"name": "U18"},
        {"name": "U19"},
        {"name": "Open"}
    ]
    
    try:
        result = supabase.table('age_groups').insert(age_groups).execute()
        print(f"✅ Inserted {len(age_groups)} age groups")
    except Exception as e:
        print(f"⚠️  Age groups may already exist: {e}")
    
    # 2. Seasons
    seasons = [
        {"name": "2023-2024", "start_date": "2023-09-01", "end_date": "2024-06-30"},
        {"name": "2024-2025", "start_date": "2024-09-01", "end_date": "2025-06-30"},
        {"name": "2025-2026", "start_date": "2025-09-01", "end_date": "2026-06-30"}
    ]
    
    try:
        result = supabase.table('seasons').insert(seasons).execute()
        print(f"✅ Inserted {len(seasons)} seasons")
    except Exception as e:
        print(f"⚠️  Seasons may already exist: {e}")
    
    # 3. Game Types
    game_types = [
        {"name": "League"},
        {"name": "Tournament"},
        {"name": "Friendly"},
        {"name": "Playoff"}
    ]
    
    try:
        result = supabase.table('game_types').insert(game_types).execute()
        print(f"✅ Inserted {len(game_types)} game types")
    except Exception as e:
        print(f"⚠️  Game types may already exist: {e}")
    
    print("\n🎉 Reference data population complete!")
    
    # Show what was created
    print("\n📊 Current reference data:")
    
    # Age groups
    age_groups_result = supabase.table('age_groups').select('*').execute()
    print(f"Age Groups: {[ag['name'] for ag in age_groups_result.data]}")
    
    # Seasons  
    seasons_result = supabase.table('seasons').select('*').execute()
    print(f"Seasons: {[s['name'] for s in seasons_result.data]}")
    
    # Game types
    game_types_result = supabase.table('game_types').select('*').execute()
    print(f"Game Types: {[gt['name'] for gt in game_types_result.data]}")

if __name__ == '__main__':
    populate_reference_data()
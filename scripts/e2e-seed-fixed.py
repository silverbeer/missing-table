#!/usr/bin/env python3
"""
Fixed E2E database seeding script that matches the actual schema
"""
import os
import sys
from supabase import create_client

def seed_test_teams():
    """Seed test teams compatible with e2e schema"""
    
    url = os.getenv('SUPABASE_URL', 'http://127.0.0.1:54321')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not key:
        print("❌ SUPABASE_SERVICE_KEY not found in environment")
        return False
        
    client = create_client(url, key)
    
    try:
        print("🏆 Seeding test teams...")
        
        # Get reference data IDs
        age_groups = client.table('age_groups').select('id, name').execute()
        seasons = client.table('seasons').select('id, name').limit(1).execute()
        
        if not age_groups.data or not seasons.data:
            print("❌ Reference data not found")
            return False
            
        age_group_id = age_groups.data[0]['id']  # U13
        season_id = seasons.data[0]['id']
        
        # Create test teams with correct schema (no age_group_id, season_id, coach, contact_email)
        teams = [
            {
                "name": "Test FC Alpha",
                "city": "Test City Alpha",
                "academy_team": False
            },
            {
                "name": "Test FC Beta", 
                "city": "Test City Beta",
                "academy_team": False
            },
            {
                "name": "Test FC Gamma",
                "city": "Test City Gamma",
                "academy_team": False
            }
        ]
        
        created_teams = []
        for team in teams:
            try:
                result = client.table('teams').upsert(team, on_conflict='name').execute()
                if result.data:
                    created_teams.append(result.data[0])
                    print(f"✅ Team: {team['name']}")
                else:
                    # Try to get existing team
                    existing = client.table('teams').select('*').eq('name', team['name']).execute()
                    if existing.data:
                        created_teams.append(existing.data[0])
                        print(f"✅ Team: {team['name']} (existing)")
            except Exception as e:
                print(f"⚠️  Team {team['name']}: {e}")
        
        # Create team_mappings to link teams to age groups
        print("🔗 Creating team mappings...")
        for team in created_teams:
            try:
                mapping = {
                    "team_id": team['id'],
                    "age_group_id": age_group_id
                }
                result = client.table('team_mappings').upsert(mapping, on_conflict='team_id,age_group_id').execute()
                print(f"✅ Mapping: {team['name']} -> U13")
            except Exception as e:
                print(f"⚠️  Mapping for {team['name']}: {e}")
                
        return len(created_teams) >= 2
        
    except Exception as e:
        print(f"❌ Error seeding test teams: {e}")
        return False

def seed_test_games():
    """Seed test games with proper schema"""
    
    url = os.getenv('SUPABASE_URL', 'http://127.0.0.1:54321')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    client = create_client(url, key)
    
    try:
        print("⚽ Seeding test games...")
        
        # Get teams and reference data
        teams = client.table('teams').select('id, name').limit(3).execute()
        seasons = client.table('seasons').select('id').limit(1).execute()
        age_groups = client.table('age_groups').select('id').limit(1).execute()
        game_types = client.table('game_types').select('id').limit(1).execute()
        
        if len(teams.data) < 2:
            print("❌ Need at least 2 teams to create games")
            return False
            
        team1_id = teams.data[0]['id']
        team2_id = teams.data[1]['id']
        season_id = seasons.data[0]['id']
        age_group_id = age_groups.data[0]['id']
        game_type_id = game_types.data[0]['id']
        
        # Create test games
        games = [
            {
                "game_date": "2024-10-15",
                "home_team_id": team1_id,
                "away_team_id": team2_id,
                "home_score": 2,
                "away_score": 1,
                "season_id": season_id,
                "age_group_id": age_group_id,
                "game_type_id": game_type_id
            },
            {
                "game_date": "2024-10-22",
                "home_team_id": team2_id,
                "away_team_id": team1_id,
                "home_score": 0,
                "away_score": 3,
                "season_id": season_id,
                "age_group_id": age_group_id,
                "game_type_id": game_type_id
            }
        ]
        
        if len(teams.data) >= 3:
            team3_id = teams.data[2]['id']
            games.append({
                "game_date": "2024-10-29",
                "home_team_id": team1_id,
                "away_team_id": team3_id,
                "home_score": None,
                "away_score": None,
                "season_id": season_id,
                "age_group_id": age_group_id,
                "game_type_id": game_type_id
            })
        
        for i, game in enumerate(games):
            try:
                result = client.table('games').insert(game).execute()
                print(f"✅ Game {i+1}: {teams.data[0]['name'] if game['home_team_id'] == team1_id else teams.data[1]['name']} vs {teams.data[1]['name'] if game['away_team_id'] == team2_id else teams.data[0]['name']}")
            except Exception as e:
                print(f"⚠️  Game {i+1}: {e}")
                
        return True
        
    except Exception as e:
        print(f"❌ Error seeding test games: {e}")
        return False

if __name__ == "__main__":
    # Load environment from .env.e2e
    if os.path.exists('.env.e2e'):
        with open('.env.e2e', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    print("🌱 Fixed E2E Test Database Seeding")
    print("=" * 40)
    
    success = True
    success &= seed_test_teams()
    success &= seed_test_games()
    
    if success:
        print("\n✅ E2E database seeding completed successfully!")
        print("🚀 Ready to run e2e tests: cd backend && uv run pytest -m e2e")
    else:
        print("\n❌ Some errors occurred during seeding")
        sys.exit(1)
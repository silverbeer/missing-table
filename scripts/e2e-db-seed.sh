#!/bin/bash
# E2E Test Database Seeding Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if E2E database is running
check_database() {
    if ! curl -s http://127.0.0.1:54321/rest/v1/ &> /dev/null; then
        print_error "E2E Supabase instance is not running"
        print_warning "Start it with: ./scripts/e2e-db-setup.sh"
        exit 1
    fi
    print_success "E2E database is running"
}

# Seed minimal test data
seed_test_data() {
    print_header "Seeding E2E Test Database"
    
    cd "$PROJECT_ROOT/backend" || exit 1
    
    # Load e2e environment
    export $(grep -v '^#' "$PROJECT_ROOT/.env.e2e" | xargs)
    
    print_warning "Creating minimal test data for e2e tests..."
    
    # Create a simple Python script to seed basic test data
    cat > seed_e2e_data.py << 'EOF'
#!/usr/bin/env python3
"""
Seed minimal test data for E2E tests
"""
import os
import sys
from supabase import create_client
from datetime import datetime, date

def seed_reference_data():
    """Seed minimal reference data needed for tests"""
    
    # Connect to e2e database
    url = os.getenv('SUPABASE_URL', 'http://127.0.0.1:54321')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not key:
        print("❌ SUPABASE_SERVICE_KEY not found in environment")
        return False
        
    client = create_client(url, key)
    
    try:
        print("🌱 Seeding reference data...")
        
        # Seed age groups
        age_groups = [
            {"name": "U13", "description": "Under 13"},
            {"name": "U15", "description": "Under 15"},
            {"name": "U17", "description": "Under 17"}
        ]
        
        for age_group in age_groups:
            try:
                result = client.table('age_groups').upsert(age_group, on_conflict='name').execute()
                print(f"✅ Age group: {age_group['name']}")
            except Exception as e:
                print(f"⚠️  Age group {age_group['name']} may already exist")
        
        # Seed seasons
        seasons = [
            {
                "name": "2024-2025", 
                "start_date": "2024-09-01",
                "end_date": "2025-06-30",
                "is_active": True
            },
            {
                "name": "2025-2026", 
                "start_date": "2025-09-01", 
                "end_date": "2026-06-30",
                "is_active": False
            }
        ]
        
        for season in seasons:
            try:
                result = client.table('seasons').upsert(season, on_conflict='name').execute()
                print(f"✅ Season: {season['name']}")
            except Exception as e:
                print(f"⚠️  Season {season['name']} may already exist")
        
        # Seed game types
        game_types = [
            {"name": "Regular Season", "description": "Regular season games"},
            {"name": "Playoff", "description": "Playoff games"},
            {"name": "Tournament", "description": "Tournament games"}
        ]
        
        for game_type in game_types:
            try:
                result = client.table('game_types').upsert(game_type, on_conflict='name').execute()
                print(f"✅ Game type: {game_type['name']}")
            except Exception as e:
                print(f"⚠️  Game type {game_type['name']} may already exist")
        
        # Seed divisions
        divisions = [
            {"name": "Premier", "level": 1},
            {"name": "Division 1", "level": 2},
            {"name": "Division 2", "level": 3}
        ]
        
        for division in divisions:
            try:
                result = client.table('divisions').upsert(division, on_conflict='name').execute()
                print(f"✅ Division: {division['name']}")
            except Exception as e:
                print(f"⚠️  Division {division['name']} may already exist")
        
        return True
        
    except Exception as e:
        print(f"❌ Error seeding reference data: {e}")
        return False

def seed_test_teams():
    """Seed minimal test teams"""
    
    url = os.getenv('SUPABASE_URL', 'http://127.0.0.1:54321')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    client = create_client(url, key)
    
    try:
        print("🏆 Seeding test teams...")
        
        # Get reference data IDs
        age_groups = client.table('age_groups').select('id, name').execute()
        seasons = client.table('seasons').select('id, name').limit(1).execute()
        
        if not age_groups.data or not seasons.data:
            print("❌ Reference data not found. Run reference data seeding first.")
            return False
            
        age_group_id = age_groups.data[0]['id']
        season_id = seasons.data[0]['id']
        
        # Create test teams
        teams = [
            {
                "name": "Test FC Alpha",
                "city": "Test City Alpha", 
                "age_group_id": age_group_id,
                "season_id": season_id,
                "coach": "Coach Alpha",
                "contact_email": "alpha@testteam.com"
            },
            {
                "name": "Test FC Beta",
                "city": "Test City Beta",
                "age_group_id": age_group_id,
                "season_id": season_id, 
                "coach": "Coach Beta",
                "contact_email": "beta@testteam.com"
            },
            {
                "name": "Test FC Gamma",
                "city": "Test City Gamma",
                "age_group_id": age_group_id,
                "season_id": season_id,
                "coach": "Coach Gamma", 
                "contact_email": "gamma@testteam.com"
            }
        ]
        
        for team in teams:
            try:
                result = client.table('teams').upsert(team, on_conflict='name,season_id').execute()
                print(f"✅ Team: {team['name']}")
            except Exception as e:
                print(f"⚠️  Team {team['name']} may already exist")
                
        return True
        
    except Exception as e:
        print(f"❌ Error seeding test teams: {e}")
        return False

def seed_test_games():
    """Seed minimal test games"""
    
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
                "game_type_id": game_type_id,
                "venue": "Test Stadium Alpha"
            },
            {
                "game_date": "2024-10-22",
                "home_team_id": team2_id,
                "away_team_id": team1_id,
                "home_score": 0,
                "away_score": 3,
                "season_id": season_id,
                "age_group_id": age_group_id, 
                "game_type_id": game_type_id,
                "venue": "Test Stadium Beta"
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
                "game_type_id": game_type_id,
                "venue": "Test Stadium Gamma"
            })
        
        for i, game in enumerate(games):
            try:
                result = client.table('games').insert(game).execute()
                print(f"✅ Game {i+1}: {teams.data[0]['name'] if game['home_team_id'] == team1_id else teams.data[1]['name']} vs {teams.data[1]['name'] if game['away_team_id'] == team2_id else teams.data[0]['name']}")
            except Exception as e:
                print(f"⚠️  Game {i+1} may already exist or failed to create")
                
        return True
        
    except Exception as e:
        print(f"❌ Error seeding test games: {e}")
        return False

if __name__ == "__main__":
    print("🌱 Seeding E2E Test Database")
    print("=" * 40)
    
    success = True
    success &= seed_reference_data()
    success &= seed_test_teams()
    success &= seed_test_games()
    
    if success:
        print("\n✅ E2E database seeding completed successfully!")
        print("🚀 Ready to run e2e tests: cd backend && uv run pytest -m e2e")
    else:
        print("\n❌ Some errors occurred during seeding")
        sys.exit(1)
EOF

    # Run the seeding script
    if command -v uv &> /dev/null; then
        uv run python seed_e2e_data.py
    else
        python3 seed_e2e_data.py
    fi
    
    # Clean up temporary script
    rm -f seed_e2e_data.py
    
    if [ $? -eq 0 ]; then
        print_success "E2E database seeded successfully"
    else
        print_error "Failed to seed E2E database"
        exit 1
    fi
}

# Reset database (clear all data)
reset_database() {
    print_header "Resetting E2E Database"
    
    cd "$PROJECT_ROOT" || exit 1
    
    print_warning "This will reset the E2E database and lose all data!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Resetting E2E database..."
        supabase db reset --workdir supabase-e2e
        
        if [ $? -eq 0 ]; then
            print_success "E2E database reset successfully"
            print_warning "Run: $0 to seed test data"
        else
            print_error "Failed to reset E2E database"
            exit 1
        fi
    else
        print_warning "Database reset cancelled"
    fi
}

# Show usage information
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Seed E2E test database with minimal test data"
    echo
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -r, --reset    Reset database (clear all data)"
    echo
    echo "Examples:"
    echo "  $0             # Seed test data"
    echo "  $0 --reset     # Reset database"
}

# Main execution
main() {
    case "${1:-}" in
        -h|--help)
            show_usage
            exit 0
            ;;
        -r|--reset)
            reset_database
            exit 0
            ;;
        "")
            # Default: seed database
            check_database
            seed_test_data
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
# -*- coding: utf-8 -*-
import logging
from fastapi import FastAPI, HTTPException, Query, Depends
from dao.enhanced_data_access_fixed import EnhancedSportsDAO, SupabaseConnection as DbConnectionHolder
from dao.local_data_access import LocalSportsDAO, LocalSupabaseConnection
from collections import defaultdict
import os
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
from auth import AuthManager, get_current_user_optional, get_current_user_required, require_admin, require_team_manager_or_admin

# Load environment variables
load_dotenv()  # Load .env first
load_dotenv('.env.local', override=True)  # Override with .env.local if it exists

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Enhanced Sports League API", version="2.0.0")

# Configure CORS
origins = [
    "http://localhost:8080",
    "http://localhost:8081",
    "http://192.168.1.2:8080",
    "http://192.168.1.2:8081",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase connection - use CLI for local development
supabase_url = os.getenv('SUPABASE_URL', '')
if 'localhost' in supabase_url or '127.0.0.1' in supabase_url:
    print("Using Supabase CLI local development: " + supabase_url)
    # Use the regular connection for Supabase CLI
    db_conn_holder_obj = DbConnectionHolder()
    sports_dao = EnhancedSportsDAO(db_conn_holder_obj)
else:
    print("Using enhanced Supabase connection")
    db_conn_holder_obj = DbConnectionHolder()
    sports_dao = EnhancedSportsDAO(db_conn_holder_obj)

# Initialize Authentication Manager
auth_manager = AuthManager(db_conn_holder_obj.client)

# Enhanced Pydantic models
class EnhancedGame(BaseModel):
    game_date: str
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int
    season_id: int
    age_group_id: int
    game_type_id: int
    division_id: Optional[int] = None

class Team(BaseModel):
    name: str
    city: str
    age_group_ids: List[int]
    division_ids: Optional[List[int]] = None
    academy_team: Optional[bool] = False

# Auth-related models
class UserSignup(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserProfile(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    team_id: Optional[int] = None

class RoleUpdate(BaseModel):
    user_id: str
    role: str
    team_id: Optional[int] = None

# === Authentication Endpoints ===

@app.post("/api/auth/signup")
async def signup(user_data: UserSignup):
    """User signup endpoint."""
    try:
        response = db_conn_holder_obj.client.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": {
                    "display_name": user_data.display_name or user_data.email.split('@')[0]
                }
            }
        })
        
        if response.user:
            return {
                "message": "User created successfully. Please check your email for verification.",
                "user_id": response.user.id
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to create user")
            
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/login")
async def login(user_data: UserLogin):
    """User login endpoint."""
    try:
        response = db_conn_holder_obj.client.auth.sign_in_with_password({
            "email": user_data.email,
            "password": user_data.password
        })
        
        if response.user and response.session:
            # Get user profile
            profile_response = db_conn_holder_obj.client.table('user_profiles').select('*').eq('id', response.user.id).single().execute()
            
            profile = profile_response.data if profile_response.data else {}
            
            return {
                "access_token": response.session.access_token,
                "token_type": "bearer",
                "user": {
                    "id": response.user.id,
                    "email": response.user.email,
                    "role": profile.get('role', 'team-fan'),
                    "team_id": profile.get('team_id'),
                    "display_name": profile.get('display_name')
                }
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/auth/logout")
async def logout(current_user: Dict[str, Any] = Depends(get_current_user_required)):
    """User logout endpoint."""
    try:
        db_conn_holder_obj.client.auth.sign_out()
        return {"message": "Logged out successfully"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")

@app.get("/api/auth/profile")
async def get_profile(current_user: Dict[str, Any] = Depends(get_current_user_required)):
    """Get current user's profile."""
    try:
        profile_response = db_conn_holder_obj.client.table('user_profiles').select('''
            *,
            team:teams(id, name, city)
        ''').eq('id', current_user['user_id']).single().execute()
        
        if profile_response.data:
            profile = profile_response.data
            return {
                "id": profile['id'],
                "role": profile['role'],
                "team_id": profile.get('team_id'),
                "team": profile.get('team'),
                "display_name": profile.get('display_name'),
                "created_at": profile.get('created_at')
            }
        else:
            raise HTTPException(status_code=404, detail="Profile not found")
            
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get profile")

@app.put("/api/auth/profile")
async def update_profile(
    profile_data: UserProfile, 
    current_user: Dict[str, Any] = Depends(get_current_user_required)
):
    """Update current user's profile."""
    try:
        update_data = {}
        if profile_data.display_name is not None:
            update_data['display_name'] = profile_data.display_name
        if profile_data.team_id is not None:
            update_data['team_id'] = profile_data.team_id
            
        # Only allow role updates by admins
        if profile_data.role is not None:
            if current_user.get('role') != 'admin':
                raise HTTPException(status_code=403, detail="Only admins can change roles")
            update_data['role'] = profile_data.role
        
        if update_data:
            update_data['updated_at'] = 'NOW()'
            db_conn_holder_obj.client.table('user_profiles').update(update_data).eq('id', current_user['user_id']).execute()
        
        return {"message": "Profile updated successfully"}
        
    except Exception as e:
        logger.error(f"Update profile error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")

@app.get("/api/auth/users")
async def get_users(current_user: Dict[str, Any] = Depends(require_admin)):
    """Get all users (admin only)."""
    try:
        response = db_conn_holder_obj.client.table('user_profiles').select('''
            *,
            team:teams(id, name, city)
        ''').order('created_at', desc=True).execute()
        
        return response.data
        
    except Exception as e:
        logger.error(f"Get users error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get users")

@app.put("/api/auth/users/role")
async def update_user_role(
    role_data: RoleUpdate, 
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Update user role (admin only)."""
    try:
        update_data = {
            'role': role_data.role,
            'updated_at': 'NOW()'
        }
        
        if role_data.team_id:
            update_data['team_id'] = role_data.team_id
        
        db_conn_holder_obj.client.table('user_profiles').update(update_data).eq('id', role_data.user_id).execute()
        
        return {"message": "User role updated successfully"}
        
    except Exception as e:
        logger.error(f"Update user role error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user role")

# === Reference Data Endpoints ===

@app.get("/api/age-groups")
async def get_age_groups():
    """Get all age groups."""
    try:
        age_groups = sports_dao.get_all_age_groups()
        return age_groups
    except Exception as e:
        logger.error(f"Error retrieving age groups: {str(e)}")
        raise HTTPException(status_code=503, detail="Database connection failed. Please check Supabase connection.")

@app.get("/api/seasons")
async def get_seasons():
    """Get all seasons."""
    try:
        seasons = sports_dao.get_all_seasons()
        return seasons
    except Exception as e:
        logger.error(f"Error retrieving seasons: {str(e)}")
        raise HTTPException(status_code=503, detail="Database connection failed. Please check Supabase connection.")

@app.get("/api/current-season")
async def get_current_season():
    """Get the current active season."""
    try:
        current_season = sports_dao.get_current_season()
        if not current_season:
            # Default to 2024-2025 season if no current season found
            seasons = sports_dao.get_all_seasons()
            current_season = next((s for s in seasons if s['name'] == '2024-2025'), seasons[0] if seasons else None)
        return current_season
    except Exception as e:
        logger.error(f"Error retrieving current season: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/active-seasons")
async def get_active_seasons():
    """Get active seasons (current and future) for scheduling new games."""
    try:
        active_seasons = sports_dao.get_active_seasons()
        return active_seasons
    except Exception as e:
        logger.error(f"Error retrieving active seasons: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/game-types")
async def get_game_types():
    """Get all game types."""
    try:
        game_types = sports_dao.get_all_game_types()
        return game_types
    except Exception as e:
        logger.error(f"Error retrieving game types: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/divisions")
async def get_divisions():
    """Get all divisions."""
    try:
        divisions = sports_dao.get_all_divisions()
        return divisions
    except Exception as e:
        logger.error(f"Error retrieving divisions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# === Enhanced Team Endpoints ===

@app.get("/api/teams")
async def get_teams(game_type_id: Optional[int] = None, age_group_id: Optional[int] = None):
    """Get teams, optionally filtered by game type and age group."""
    try:
        if game_type_id and age_group_id:
            teams = sports_dao.get_teams_by_game_type_and_age_group(game_type_id, age_group_id)
        else:
            teams = sports_dao.get_all_teams()
        return teams
    except Exception as e:
        logger.error(f"Error retrieving teams: {str(e)}")
        raise HTTPException(status_code=503, detail="Database connection failed. Please check Supabase connection.")

@app.post("/api/teams")
async def add_team(team: Team):
    """Add a new team with age groups and optionally divisions."""
    try:
        success = sports_dao.add_team(team.name, team.city, team.age_group_ids, team.division_ids, team.academy_team)
        if success:
            return {"message": "Team added successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add team")
    except Exception as e:
        logger.error(f"Error adding team: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# === Enhanced Game Endpoints ===

@app.get("/api/games")
async def get_games(
    season_id: Optional[int] = Query(None, description="Filter by season ID"),
    age_group_id: Optional[int] = Query(None, description="Filter by age group ID"),
    division_id: Optional[int] = Query(None, description="Filter by division ID"),
    game_type: Optional[str] = Query(None, description="Filter by game type name")
):
    """Get all games with optional filters."""
    try:
        games = sports_dao.get_all_games(season_id=season_id)
        return games
    except Exception as e:
        logger.error(f"Error retrieving games: {str(e)}")
        raise HTTPException(status_code=503, detail="Database connection failed. Please check Supabase connection.")

@app.post("/api/games")
async def add_game(game: EnhancedGame):
    """Add a new game with enhanced schema."""
    try:
        
        success = sports_dao.add_game(
            home_team_id=game.home_team_id,
            away_team_id=game.away_team_id,
            game_date=game.game_date,
            home_score=game.home_score,
            away_score=game.away_score,
            season_id=game.season_id,
            age_group_id=game.age_group_id,
            game_type_id=game.game_type_id,
            division_id=game.division_id
        )
        if success:
            return {"message": "Game added successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add game")
    except Exception as e:
        logger.error(f"Error adding game: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/games/{game_id}")
async def update_game(game_id: int, game: EnhancedGame, current_user: Dict[str, Any] = Depends(require_admin)):
    """Update an existing game (admin only)."""
    try:
        success = sports_dao.update_game(
            game_id=game_id,
            home_team_id=game.home_team_id,
            away_team_id=game.away_team_id,
            game_date=game.game_date,
            home_score=game.home_score,
            away_score=game.away_score,
            season_id=game.season_id,
            age_group_id=game.age_group_id,
            game_type_id=game.game_type_id,
            division_id=game.division_id
        )
        if success:
            return {"message": "Game updated successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update game")
    except Exception as e:
        logger.error(f"Error updating game: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/games/{game_id}")
async def delete_game(game_id: int, current_user: Dict[str, Any] = Depends(require_admin)):
    """Delete a game (admin only)."""
    try:
        success = sports_dao.delete_game(game_id)
        if success:
            return {"message": "Game deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete game")
    except Exception as e:
        logger.error(f"Error deleting game: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/games/team/{team_id}")
async def get_games_by_team(
    team_id: int,
    season_id: Optional[int] = Query(None, description="Filter by season ID")
):
    """Get games for a specific team."""
    try:
        games = sports_dao.get_games_by_team(team_id, season_id=season_id)
        if not games:
            raise HTTPException(status_code=404, detail="No games found for this team.")
        return games
    except Exception as e:
        logger.error(f"Error retrieving games for team '{team_id}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# === Enhanced League Table Endpoint ===

@app.get("/api/table")
async def get_table(
    season_id: Optional[int] = Query(None, description="Filter by season ID"),
    age_group_id: Optional[int] = Query(None, description="Filter by age group ID"),
    division_id: Optional[int] = Query(None, description="Filter by division ID"),
    game_type: Optional[str] = Query("League", description="Game type (League, Tournament, etc.)")
):
    """Get league table with enhanced filtering."""
    try:
        # If no season specified, use current/default season
        if not season_id:
            current_season = sports_dao.get_current_season()
            if current_season:
                season_id = current_season['id']
            else:
                # Default to 2024-2025 season
                seasons = sports_dao.get_all_seasons()
                default_season = next((s for s in seasons if s['name'] == '2024-2025'), seasons[0] if seasons else None)
                if default_season:
                    season_id = default_season['id']
        
        # If no age group specified, use U13
        if not age_group_id:
            age_groups = sports_dao.get_all_age_groups()
            u13_age_group = next((ag for ag in age_groups if ag['name'] == 'U13'), age_groups[0] if age_groups else None)
            if u13_age_group:
                age_group_id = u13_age_group['id']
        
        table = sports_dao.get_league_table(
            season_id=season_id,
            age_group_id=age_group_id,
            division_id=division_id,
            game_type=game_type
        )
        
        return table
    except Exception as e:
        logger.error(f"Error generating league table: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# === Admin CRUD Endpoints ===

# Age Groups CRUD
class AgeGroupCreate(BaseModel):
    name: str

class AgeGroupUpdate(BaseModel):
    name: str

@app.post("/api/age-groups")
async def create_age_group(age_group: AgeGroupCreate, current_user: Dict[str, Any] = Depends(require_admin)):
    """Create a new age group (admin only)."""
    try:
        result = sports_dao.create_age_group(age_group.name)
        return result
    except Exception as e:
        logger.error(f"Error creating age group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/age-groups/{age_group_id}")
async def update_age_group(age_group_id: int, age_group: AgeGroupUpdate, current_user: Dict[str, Any] = Depends(require_admin)):
    """Update an age group (admin only)."""
    try:
        result = sports_dao.update_age_group(age_group_id, age_group.name)
        if not result:
            raise HTTPException(status_code=404, detail="Age group not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating age group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/age-groups/{age_group_id}")
async def delete_age_group(age_group_id: int, current_user: Dict[str, Any] = Depends(require_admin)):
    """Delete an age group (admin only)."""
    try:
        result = sports_dao.delete_age_group(age_group_id)
        if not result:
            raise HTTPException(status_code=404, detail="Age group not found")
        return {"message": "Age group deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting age group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Seasons CRUD
class SeasonCreate(BaseModel):
    name: str
    start_date: str
    end_date: str

class SeasonUpdate(BaseModel):
    name: str
    start_date: str
    end_date: str

@app.post("/api/seasons")
async def create_season(season: SeasonCreate, current_user: Dict[str, Any] = Depends(require_admin)):
    """Create a new season (admin only)."""
    try:
        result = sports_dao.create_season(season.name, season.start_date, season.end_date)
        return result
    except Exception as e:
        logger.error(f"Error creating season: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/seasons/{season_id}")
async def update_season(season_id: int, season: SeasonUpdate, current_user: Dict[str, Any] = Depends(require_admin)):
    """Update a season (admin only)."""
    try:
        result = sports_dao.update_season(season_id, season.name, season.start_date, season.end_date)
        if not result:
            raise HTTPException(status_code=404, detail="Season not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating season: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/seasons/{season_id}")
async def delete_season(season_id: int, current_user: Dict[str, Any] = Depends(require_admin)):
    """Delete a season (admin only)."""
    try:
        result = sports_dao.delete_season(season_id)
        if not result:
            raise HTTPException(status_code=404, detail="Season not found")
        return {"message": "Season deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting season: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Divisions CRUD
class DivisionCreate(BaseModel):
    name: str
    description: Optional[str] = None

class DivisionUpdate(BaseModel):
    name: str
    description: Optional[str] = None

@app.post("/api/divisions")
async def create_division(division: DivisionCreate, current_user: Dict[str, Any] = Depends(require_admin)):
    """Create a new division (admin only)."""
    try:
        result = sports_dao.create_division(division.name, division.description)
        return result
    except Exception as e:
        logger.error(f"Error creating division: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/divisions/{division_id}")
async def update_division(division_id: int, division: DivisionUpdate, current_user: Dict[str, Any] = Depends(require_admin)):
    """Update a division (admin only)."""
    try:
        result = sports_dao.update_division(division_id, division.name, division.description)
        if not result:
            raise HTTPException(status_code=404, detail="Division not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating division: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/divisions/{division_id}")
async def delete_division(division_id: int, current_user: Dict[str, Any] = Depends(require_admin)):
    """Delete a division (admin only)."""
    try:
        result = sports_dao.delete_division(division_id)
        if not result:
            raise HTTPException(status_code=404, detail="Division not found")
        return {"message": "Division deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting division: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Teams CRUD (update existing)
class TeamUpdate(BaseModel):
    name: str
    city: str
    academy_team: Optional[bool] = False

class TeamGameTypeMapping(BaseModel):
    game_type_id: int
    age_group_id: int

@app.put("/api/teams/{team_id}")
async def update_team(team_id: int, team: TeamUpdate, current_user: Dict[str, Any] = Depends(require_admin)):
    """Update a team (admin only)."""
    try:
        result = sports_dao.update_team(team_id, team.name, team.city, team.academy_team)
        if not result:
            raise HTTPException(status_code=404, detail="Team not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating team: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/teams/{team_id}")
async def delete_team(team_id: int, current_user: Dict[str, Any] = Depends(require_admin)):
    """Delete a team (admin only)."""
    try:
        result = sports_dao.delete_team(team_id)
        if not result:
            raise HTTPException(status_code=404, detail="Team not found")
        return {"message": "Team deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting team: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/teams/{team_id}/game-types")
async def add_team_game_type_participation(
    team_id: int, 
    mapping: TeamGameTypeMapping,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Add a team's participation in a specific game type and age group (admin only)."""
    try:
        success = sports_dao.add_team_game_type_participation(team_id, mapping.game_type_id, mapping.age_group_id)
        if success:
            return {"message": "Team game type participation added successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add team game type participation")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding team game type participation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/teams/{team_id}/game-types/{game_type_id}/{age_group_id}")
async def remove_team_game_type_participation(
    team_id: int, 
    game_type_id: int, 
    age_group_id: int,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Remove a team's participation in a specific game type and age group (admin only)."""
    try:
        success = sports_dao.remove_team_game_type_participation(team_id, game_type_id, age_group_id)
        if success:
            return {"message": "Team game type participation removed successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to remove team game type participation")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing team game type participation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Team Mappings CRUD
class TeamMappingCreate(BaseModel):
    team_id: int
    age_group_id: int
    division_id: int

@app.post("/api/team-mappings")
async def create_team_mapping(mapping: TeamMappingCreate, current_user: Dict[str, Any] = Depends(require_admin)):
    """Create a team mapping (admin only)."""
    try:
        result = sports_dao.create_team_mapping(mapping.team_id, mapping.age_group_id, mapping.division_id)
        return result
    except Exception as e:
        logger.error(f"Error creating team mapping: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/team-mappings/{team_id}/{age_group_id}/{division_id}")
async def delete_team_mapping(team_id: int, age_group_id: int, division_id: int, current_user: Dict[str, Any] = Depends(require_admin)):
    """Delete a team mapping (admin only)."""
    try:
        result = sports_dao.delete_team_mapping(team_id, age_group_id, division_id)
        if not result:
            raise HTTPException(status_code=404, detail="Team mapping not found")
        return {"message": "Team mapping deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting team mapping: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# === Backward Compatibility Endpoints ===

@app.get("/api/check-game")
async def check_game(date: str, homeTeam: str, awayTeam: str):
    """Check if a game exists (backward compatibility)."""
    try:
        # Check if a game already exists for this date and teams
        games = sports_dao.get_all_games()
        for game in games:
            if (str(game.get('game_date')) == date and 
                str(game.get('home_team_id')) == homeTeam and 
                str(game.get('away_team_id')) == awayTeam):
                return {"exists": True}
        return {"exists": False}
    except Exception as e:
        logger.error(f"Error checking game: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "2.0.0", "schema": "enhanced"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
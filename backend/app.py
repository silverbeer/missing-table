# -*- coding: utf-8 -*-
import logging
from fastapi import FastAPI, HTTPException, Query
from dao.enhanced_data_access_fixed import EnhancedSportsDAO, SupabaseConnection as DbConnectionHolder
from dao.local_data_access import LocalSportsDAO, LocalSupabaseConnection
from collections import defaultdict
import os
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional, List

load_dotenv()

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
async def get_teams():
    """Get all teams with their age groups."""
    try:
        teams = sports_dao.get_all_teams()
        return teams
    except Exception as e:
        logger.error(f"Error retrieving teams: {str(e)}")
        raise HTTPException(status_code=503, detail="Database connection failed. Please check Supabase connection.")

@app.post("/api/teams")
async def add_team(team: Team):
    """Add a new team with age groups and optionally divisions."""
    try:
        success = sports_dao.add_team(team.name, team.city, team.age_group_ids, team.division_ids)
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

# === Backward Compatibility Endpoints ===

@app.get("/api/check-game")
async def check_game(game_date: str, home_team: str, away_team: str):
    """Check if a game exists (backward compatibility)."""
    try:
        # This endpoint is for backward compatibility with old UI
        # For now, just return false to allow new games
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
import logging
from fastapi import FastAPI, HTTPException
from dao.data_access import SportsDAO, DbConnectionHolder
from collections import defaultdict
import os
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
    handlers=[
        logging.StreamHandler()  # Output logs to the console
    ]
)

logger = logging.getLogger(__name__)  # Create a logger for this module

app = FastAPI()

# Configure CORS
origins = [
    "http://localhost:8080",
    "http://192.168.1.2:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # List of allowed origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Path to your SQLite database
DB_FILE = 'mlsnext_u13_fall.db'
db_conn_holder_obj = DbConnectionHolder(db_file=DB_FILE)
sports_dao = SportsDAO(db_conn_holder_obj)  # Create an instance of SportsDAO

class Game(BaseModel):
    game_date: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int

@app.get("/api/games")
async def get_games():
    try:
        games = sports_dao.get_all_games()  # Use SportsDAO to get all games
        return games
    except Exception as e:
        logger.error(f"Error retrieving games: {str(e)}")  # Log the error
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/games")
async def create_game(game_info: Game):
    """Endpoint to add or update a game."""
    try:
        # Extract the information from the Pydantic model
        game_date = game_info.game_date
        home_team = game_info.home_team
        away_team = game_info.away_team
        home_score = game_info.home_score
        away_score = game_info.away_score
        
        logger.debug(f"Processing game: {game_date}, {home_team}, {away_team}, {home_score}, {away_score}")

        # Check if the game already exists
        existing_game = sports_dao.get_game_by_date_and_teams(game_date, home_team, away_team)

        if existing_game:
            # Update the existing game
            logger.debug(f"Updating existing game: {existing_game}")
            sports_dao.update_game(existing_game['id'], game_date, home_team, away_team, home_score, away_score)
            return {"message": "Game updated successfully"}
        else:
            # Add the new game
            logger.debug(f"Adding new game: {game_date}, {home_team}, {away_team}, {home_score}, {away_score}")
            sports_dao.add_game(game_date, home_team, away_team, home_score, away_score)
            return {"message": "Game created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing game: {str(e)}")

@app.get("/api/games/team/{team_name}")
async def get_games_by_team(team_name: str):
    try:
        logger.debug(f"Getting games for team: {team_name}")
        games = sports_dao.get_games_by_team(team_name)  # Use SportsDAO to get games by team
        if not games:
            logger.warning(f"No games found for team: {team_name}")  # Log a warning
            raise HTTPException(status_code=404, detail="No games found for this team.")
        return games
    except Exception as e:
        logger.error(f"Error retrieving games for team '{team_name}': {str(e)}")  # Log the error
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/teams")
async def get_teams():
    try:
        teams = sports_dao.get_all_teams()  # Use SportsDAO to get all teams
        return teams
    except Exception as e:
        logger.error(f"Error retrieving teams: {str(e)}")  # Log the error
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/table")
async def get_table():
    table = defaultdict(lambda: {
        'played': 0,
        'wins': 0,
        'draws': 0,
        'losses': 0,
        'goals_for': 0,
        'goals_against': 0,
        'goal_difference': 0,
        'points': 0
    })
    
    try:
        logger.debug("Fetching all games from the database...")
        games = sports_dao.get_all_games()
        logger.debug(f"Number of games retrieved: {len(games)}")  # Debug: Number of games retrieved
        
        current_date = datetime.now()  # Get the current date and time
        
        # Filter out games with a future game_date
        games = [game for game in games if datetime.strptime(game['game_date'], '%Y-%m-%d') <= current_date]
        
        logger.debug(f"Number of games after filtering: {len(games)}")  # Debug: Number of games after filtering
        
        for game in games:
            logger.debug(f"Processing game: {game}")  # Debug: Show each game being processed
            home_team = game['home_team']
            away_team = game['away_team']
            home_score = int(game['home_score'])
            away_score = int(game['away_score'])
            
            # Update home team stats
            table[home_team]['played'] += 1
            table[home_team]['goals_for'] += home_score
            table[home_team]['goals_against'] += away_score
            
            # Update away team stats
            table[away_team]['played'] += 1
            table[away_team]['goals_for'] += away_score
            table[away_team]['goals_against'] += home_score
            
            if home_score > away_score:
                table[home_team]['wins'] += 1
                table[away_team]['losses'] += 1
                table[home_team]['points'] += 3
            elif away_score > home_score:
                table[away_team]['wins'] += 1
                table[home_team]['losses'] += 1
                table[away_team]['points'] += 3
            else:
                table[home_team]['draws'] += 1
                table[away_team]['draws'] += 1
                table[home_team]['points'] += 1
                table[away_team]['points'] += 1
        
        # Calculate goal differences and convert to list
        table_list = []
        for team, stats in table.items():
            stats['goal_difference'] = stats['goals_for'] - stats['goals_against']
            table_list.append({
                'team': team,
                **stats
            })
        
        # Sort by points, then goal difference, then goals scored
        sorted_table = sorted(
            table_list,
            key=lambda x: (
                x['points'],
                x['goal_difference'],
                x['goals_for']
            ),
            reverse=True
        )
        
        logger.debug("Final sorted table:")
        for entry in sorted_table:  # Debug: Show the final sorted table
            logger.debug(entry)
        
        return sorted_table
        
    except Exception as e:
        logger.error(f"Error occurred while generating the table: {str(e)}")  # Log the error
        raise HTTPException(status_code=500, detail=str(e))
"""
Supabase implementation of data access layer.
This replaces the SQLite implementation with Supabase Python client.
"""

import os
from supabase import create_client
from dotenv import load_dotenv
from typing import List, Dict, Optional

# Load environment variables
load_dotenv()


class SupabaseConnection:
    """Manage the connection to Supabase."""
    
    def __init__(self):
        """Initialize Supabase client."""
        self.url = os.getenv('SUPABASE_URL')
        self.key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env file")
        
        self.client = create_client(self.url, self.key)
        print(f"Connection to Supabase established.")
    
    def get_client(self):
        """Get the Supabase client instance."""
        return self.client


class SportsDAO:
    """Data Access Object for sports data using Supabase."""
    
    def __init__(self, connection_holder):
        """Initialize with a SupabaseConnection."""
        if not isinstance(connection_holder, SupabaseConnection):
            raise TypeError("connection_holder must be a SupabaseConnection instance")
        self.connection_holder = connection_holder
        self.client = connection_holder.get_client()
    
    # Team Methods
    def get_all_teams(self) -> List[Dict]:
        """Query all rows in the teams table."""
        try:
            response = self.client.table('teams').select('*').order('name').execute()
            return response.data
        except Exception as e:
            print(f"Error querying teams: {e}")
            return []
    
    def add_team(self, name: str, city: str) -> bool:
        """Add a new team to the teams table."""
        try:
            data = {"name": name, "city": city}
            response = self.client.table('teams').insert(data).execute()
            print(f"Team '{name}' added successfully.")
            return True
        except Exception as e:
            print(f"Error adding team: {e}")
            return False
    
    # Game Methods
    def get_all_games(self) -> List[Dict]:
        """Query all rows in the games table."""
        print("Getting all games")
        try:
            response = self.client.table('games').select('*').execute()
            games = []
            for row in response.data:
                print(row)
                games.append({
                    'game_date': row['game_date'],
                    'home_team': row['home_team'],
                    'away_team': row['away_team'],
                    'home_score': row['home_score'],
                    'away_score': row['away_score']
                })
            return games
        except Exception as e:
            print(f"Error querying games: {e}")
            return []
    
    def get_games_by_team(self, team_name: str) -> List[Dict]:
        """Query games for a specific team."""
        print(f"Getting games for team: {team_name}")
        try:
            # Query for games where team is either home or away
            response = self.client.table('games').select('*').or_(
                f"home_team.eq.{team_name},away_team.eq.{team_name}"
            ).order('game_date').execute()
            
            print(response.data)
            
            games = []
            for row in response.data:
                games.append({
                    'game_date': row['game_date'],
                    'home_team': row['home_team'],
                    'away_team': row['away_team'],
                    'home_score': row['home_score'],
                    'away_score': row['away_score']
                })
            return games
        except Exception as e:
            print(f"Error querying games for team '{team_name}': {e}")
            return []
    
    def add_game(self, game_date: str, home_team: str, away_team: str, 
                 home_score: int, away_score: int) -> bool:
        """Add a new game to the database."""
        try:
            data = {
                "game_date": game_date,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score
            }
            response = self.client.table('games').insert(data).execute()
            print(f"Game added successfully: {home_team} vs {away_team} on {game_date}")
            return True
        except Exception as e:
            print(f"Error adding game: {e}")
            return False
    
    def get_game_by_date_and_teams(self, game_date: str, home_team: str, away_team: str) -> bool:
        """Check if a game exists with the given date and teams."""
        print(f"Checking for game: {game_date}, {home_team} vs {away_team}")
        
        try:
            response = self.client.table('games').select('*').eq(
                'game_date', game_date
            ).eq(
                'home_team', home_team
            ).eq(
                'away_team', away_team
            ).execute()
            
            if response.data:
                print(f"Game found: {response.data[0]}")
                return True
            else:
                print("No game found.")
                return False
        except Exception as e:
            print(f"Error occurred while fetching game: {str(e)}")
            return False
    
    def update_game(self, game_id: int, game_date: str, home_team: str, 
                    away_team: str, home_score: int, away_score: int) -> bool:
        """Update an existing game."""
        try:
            data = {
                "game_date": game_date,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score
            }
            response = self.client.table('games').update(data).eq('id', game_id).execute()
            print(f"Game with ID {game_id} updated successfully.")
            return True
        except Exception as e:
            print(f"Error occurred while updating game with ID {game_id}: {str(e)}")
            return False


# Compatibility aliases for gradual migration
DbConnectionHolder = SupabaseConnection


if __name__ == '__main__':
    # Test the DAO methods
    print("Testing Supabase implementation...")
    
    try:
        db_conn_holder_obj = SupabaseConnection()
        dao = SportsDAO(db_conn_holder_obj)
        
        print("\nAll Teams:")
        teams = dao.get_all_teams()
        for team in teams[:3]:  # Show first 3 teams
            print(f"  - {team['name']} ({team['city']})")
        
        print(f"\nTotal teams: {len(teams)}")
        
        print("\nAll Games:")
        games = dao.get_all_games()
        for game in games[:3]:  # Show first 3 games
            print(f"  - {game['game_date']}: {game['home_team']} vs {game['away_team']} ({game['home_score']}-{game['away_score']})")
        
        print(f"\nTotal games: {len(games)}")
        
        if teams:
            print(f"\nGames for '{teams[0]['name']}':")
            team_games = dao.get_games_by_team(teams[0]['name'])
            print(f"  Found {len(team_games)} games")
        
    except Exception as e:
        print(f"Error: {e}")
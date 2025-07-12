"""
Enhanced Supabase data access layer for the new normalized schema.
Supports seasons, age groups, game types, and team relationships.
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


class EnhancedSportsDAO:
    """Enhanced Data Access Object for sports data using new normalized schema."""
    
    def __init__(self, connection_holder):
        """Initialize with a SupabaseConnection."""
        if not isinstance(connection_holder, SupabaseConnection):
            raise TypeError("connection_holder must be a SupabaseConnection instance")
        self.connection_holder = connection_holder
        self.client = connection_holder.get_client()
    
    # === Reference Data Methods ===
    
    def get_all_age_groups(self) -> List[Dict]:
        """Get all age groups."""
        try:
            response = self.client.table('age_groups').select('*').order('name').execute()
            return response.data
        except Exception as e:
            print(f"Error querying age groups: {e}")
            return []
    
    def get_all_seasons(self) -> List[Dict]:
        """Get all seasons."""
        try:
            response = self.client.table('seasons').select('*').order('start_date', desc=True).execute()
            return response.data
        except Exception as e:
            print(f"Error querying seasons: {e}")
            return []
    
    def get_current_season(self) -> Optional[Dict]:
        """Get the current active season based on today's date."""
        try:
            from datetime import date
            today = date.today().isoformat()
            
            response = self.client.table('seasons').select('*').lte(
                'start_date', today
            ).gte(
                'end_date', today
            ).single().execute()
            
            return response.data
        except Exception as e:
            print(f"No current season found: {e}")
            return None
    
    def get_all_game_types(self) -> List[Dict]:
        """Get all game types."""
        try:
            response = self.client.table('game_types').select('*').order('name').execute()
            return response.data
        except Exception as e:
            print(f"Error querying game types: {e}")
            return []
    
    # === Team Methods ===
    
    def get_all_teams(self) -> List[Dict]:
        """Get all teams with their age groups."""
        try:
            response = self.client.table('teams').select('''
                *,
                team_mappings (
                    age_groups (
                        id,
                        name
                    )
                )
            ''').order('name').execute()
            
            # Flatten the age groups for easier use
            teams = []
            for team in response.data:
                team_data = {
                    'id': team['id'],
                    'name': team['name'],
                    'city': team['city'],
                    'created_at': team['created_at'],
                    'updated_at': team['updated_at'],
                    'age_groups': [ag['age_groups']['name'] for ag in team['team_mappings']]
                }
                teams.append(team_data)
            
            return teams
        except Exception as e:
            print(f"Error querying teams: {e}")
            return []
    
    def add_team(self, name: str, city: str, age_group_ids: List[int]) -> bool:
        """Add a new team with associated age groups."""
        try:
            # First, create the team
            team_data = {"name": name, "city": city}
            team_response = self.client.table('teams').insert(team_data).execute()
            
            if not team_response.data:
                print("Failed to create team")
                return False
            
            team_id = team_response.data[0]['id']
            
            # Then, associate with age groups
            team_age_group_data = [
                {"team_id": team_id, "age_group_id": age_group_id}
                for age_group_id in age_group_ids
            ]
            
            if team_age_group_data:
                self.client.table('team_mappings').insert(team_age_group_data).execute()
            
            print(f"Team '{name}' added successfully with {len(age_group_ids)} age groups.")
            return True
        except Exception as e:
            print(f"Error adding team: {e}")
            return False
    
    # === Game Methods ===
    
    def get_all_games(self, season_id: Optional[int] = None) -> List[Dict]:
        """Get all games, optionally filtered by season."""
        try:
            query = self.client.table('games').select('''
                *,
                home_team:teams!games_home_team_id_fkey(id, name),
                away_team:teams!games_away_team_id_fkey(id, name),
                season:seasons(id, name),
                age_group:age_groups(id, name),
                game_type:game_types(id, name)
            ''').order('game_date', desc=True)
            
            if season_id:
                query = query.eq('season_id', season_id)
            
            response = query.execute()
            
            # Flatten the response for easier use
            games = []
            for game in response.data:
                game_data = {
                    'id': game['id'],
                    'game_date': game['game_date'],
                    'home_score': game['home_score'],
                    'away_score': game['away_score'],
                    'home_team_id': game['home_team_id'],
                    'away_team_id': game['away_team_id'],
                    'home_team': game['home_team']['name'] if game['home_team'] else None,
                    'away_team': game['away_team']['name'] if game['away_team'] else None,
                    'season': game['season']['name'] if game['season'] else None,
                    'age_group': game['age_group']['name'] if game['age_group'] else None,
                    'game_type': game['game_type']['name'] if game['game_type'] else None
                }
                games.append(game_data)
            
            return games
        except Exception as e:
            print(f"Error querying games: {e}")
            return []
    
    def get_games_by_team(self, team_id: int, season_id: Optional[int] = None) -> List[Dict]:
        """Get games for a specific team."""
        try:
            query = self.client.table('games').select('''
                *,
                home_team:teams!games_home_team_id_fkey(id, name),
                away_team:teams!games_away_team_id_fkey(id, name),
                season:seasons(id, name),
                age_group:age_groups(id, name),
                game_type:game_types(id, name)
            ''').or_(
                f"home_team_id.eq.{team_id},away_team_id.eq.{team_id}"
            ).order('game_date')
            
            if season_id:
                query = query.eq('season_id', season_id)
            
            response = query.execute()
            
            # Flatten the response
            games = []
            for game in response.data:
                game_data = {
                    'id': game['id'],
                    'game_date': game['game_date'],
                    'home_score': game['home_score'],
                    'away_score': game['away_score'],
                    'home_team': game['home_team']['name'] if game['home_team'] else None,
                    'away_team': game['away_team']['name'] if game['away_team'] else None,
                    'season': game['season']['name'] if game['season'] else None,
                    'age_group': game['age_group']['name'] if game['age_group'] else None,
                    'game_type': game['game_type']['name'] if game['game_type'] else None
                }
                games.append(game_data)
            
            return games
        except Exception as e:
            print(f"Error querying games for team {team_id}: {e}")
            return []
    
    def add_game(self, home_team_id: int, away_team_id: int, game_date: str,
                 home_score: int, away_score: int, season_id: int,
                 age_group_id: int, game_type_id: int) -> bool:
        """Add a new game with the enhanced schema."""
        try:
            data = {
                "game_date": game_date,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_score": home_score,
                "away_score": away_score,
                "season_id": season_id,
                "age_group_id": age_group_id,
                "game_type_id": game_type_id
            }
            response = self.client.table('games').insert(data).execute()
            print(f"Game added successfully: {home_team_id} vs {away_team_id} on {game_date}")
            return True
        except Exception as e:
            print(f"Error adding game: {e}")
            return False
    
    def get_league_table(self, season_id: Optional[int] = None, 
                        age_group_id: Optional[int] = None,
                        game_type: str = "League") -> List[Dict]:
        """Generate league table for specified filters."""
        try:
            # Get game type ID
            game_type_response = self.client.table('game_types').select('id').eq('name', game_type).single().execute()
            game_type_id = game_type_response.data['id']
            
            # Build query
            query = self.client.table('games').select('''
                *,
                home_team:teams!games_home_team_id_fkey(id, name),
                away_team:teams!games_away_team_id_fkey(id, name)
            ''').eq('game_type_id', game_type_id)
            
            if season_id:
                query = query.eq('season_id', season_id)
            if age_group_id:
                query = query.eq('age_group_id', age_group_id)
            
            response = query.execute()
            games = response.data
            
            # Calculate standings
            standings = {}
            for game in games:
                home_team = game['home_team']['name']
                away_team = game['away_team']['name']
                home_score = game['home_score']
                away_score = game['away_score']
                
                # Initialize team records
                for team in [home_team, away_team]:
                    if team not in standings:
                        standings[team] = {
                            'team': team,
                            'played': 0,
                            'wins': 0,
                            'draws': 0,
                            'losses': 0,
                            'goals_for': 0,
                            'goals_against': 0,
                            'goal_difference': 0,
                            'points': 0
                        }
                
                # Update stats
                standings[home_team]['played'] += 1
                standings[away_team]['played'] += 1
                standings[home_team]['goals_for'] += home_score
                standings[home_team]['goals_against'] += away_score
                standings[away_team]['goals_for'] += away_score
                standings[away_team]['goals_against'] += home_score
                
                # Win/Loss/Draw
                if home_score > away_score:
                    standings[home_team]['wins'] += 1
                    standings[home_team]['points'] += 3
                    standings[away_team]['losses'] += 1
                elif away_score > home_score:
                    standings[away_team]['wins'] += 1
                    standings[away_team]['points'] += 3
                    standings[home_team]['losses'] += 1
                else:
                    standings[home_team]['draws'] += 1
                    standings[away_team]['draws'] += 1
                    standings[home_team]['points'] += 1
                    standings[away_team]['points'] += 1
            
            # Calculate goal difference and sort
            table = []
            for team_stats in standings.values():
                team_stats['goal_difference'] = team_stats['goals_for'] - team_stats['goals_against']
                table.append(team_stats)
            
            # Sort by points, then goal difference, then goals for
            table.sort(key=lambda x: (x['points'], x['goal_difference'], x['goals_for']), reverse=True)
            
            return table
            
        except Exception as e:
            print(f"Error generating league table: {e}")
            return []


# Compatibility aliases for gradual migration
DbConnectionHolder = SupabaseConnection
SportsDAO = EnhancedSportsDAO


if __name__ == '__main__':
    # Test the enhanced DAO
    print("Testing Enhanced Sports DAO...")
    
    try:
        conn = SupabaseConnection()
        dao = EnhancedSportsDAO(conn)
        
        print("\n=== Reference Data ===")
        
        age_groups = dao.get_all_age_groups()
        print(f"Age Groups: {[ag['name'] for ag in age_groups]}")
        
        seasons = dao.get_all_seasons()
        print(f"Seasons: {[s['name'] for s in seasons]}")
        
        current_season = dao.get_current_season()
        print(f"Current Season: {current_season['name'] if current_season else 'None'}")
        
        game_types = dao.get_all_game_types()
        print(f"Game Types: {[gt['name'] for gt in game_types]}")
        
        print("\n=== Teams ===")
        teams = dao.get_all_teams()
        for team in teams[:3]:  # Show first 3
            print(f"  - {team['name']} ({team['city']}) - Age Groups: {team['age_groups']}")
        
        print(f"\nTotal teams: {len(teams)}")
        
        print("\n=== Games ===")
        games = dao.get_all_games()
        for game in games[:3]:  # Show first 3
            print(f"  - {game['game_date']}: {game['home_team']} vs {game['away_team']} ({game['home_score']}-{game['away_score']}) [{game['game_type']}]")
        
        print(f"\nTotal games: {len(games)}")
        
    except Exception as e:
        print(f"Error: {e}")
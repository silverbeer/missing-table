"""
Local data access layer that bypasses Supabase authentication for local development.
Uses direct HTTP requests to PostgREST API.
"""

import os
from datetime import date

import httpx


class LocalSupabaseConnection:
    """Local connection that uses direct HTTP requests to PostgREST."""

    def __init__(self):
        """Initialize with local PostgREST URL."""
        self.base_url = os.getenv("SUPABASE_URL", "http://localhost:54321")
        self.client = httpx.Client(base_url=self.base_url, timeout=30.0)

    def get_client(self):
        """Get the HTTP client instance."""
        return self.client


class LocalSportsDAO:
    """Local Data Access Object that uses direct HTTP requests."""

    def __init__(self, connection_holder):
        """Initialize with a LocalSupabaseConnection."""
        self.connection_holder = connection_holder
        self.client = connection_holder.get_client()

    def _get_json(self, endpoint: str, params: dict = None) -> list[dict]:
        """Make a GET request and return JSON data."""
        try:
            response = self.client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error querying {endpoint}: {e}")
            return []

    def _post_json(self, endpoint: str, data: dict) -> dict:
        """Make a POST request and return JSON data."""
        try:
            response = self.client.post(endpoint, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error posting to {endpoint}: {e}")
            return {}

    # === Reference Data Methods ===

    def get_all_age_groups(self) -> list[dict]:
        """Get all age groups."""
        return self._get_json("/age_groups", {"order": "name"})

    def get_all_seasons(self) -> list[dict]:
        """Get all seasons."""
        return self._get_json("/seasons", {"order": "start_date.desc"})

    def get_current_season(self) -> dict | None:
        """Get the current active season based on today's date."""
        try:
            today = date.today().isoformat()
            params = {"start_date": f"lte.{today}", "end_date": f"gte.{today}"}
            seasons = self._get_json("/seasons", params)
            return seasons[0] if seasons else None
        except Exception as e:
            print(f"No current season found: {e}")
            return None

    def get_all_game_types(self) -> list[dict]:
        """Get all game types."""
        return self._get_json("/game_types", {"order": "name"})

    # === Team Methods ===

    def get_all_teams(self) -> list[dict]:
        """Get all teams with their age groups."""
        # This would require a more complex query with joins
        # For now, return basic teams
        return self._get_json("/teams", {"order": "name"})

    def add_team(self, name: str, city: str, age_group_ids: list[int]) -> bool:
        """Add a new team with age groups."""
        try:
            # Insert team
            team_data = {"name": name, "city": city}
            team_result = self._post_json("/teams", team_data)

            if not team_result:
                return False

            # For now, skip age group associations as they require more complex setup
            return True

        except Exception as e:
            print(f"Error adding team: {e}")
            return False

    # === Game Methods ===

    def get_all_games(self, season_id: int | None = None) -> list[dict]:
        """Get all games with optional season filter."""
        params = {"order": "game_date.desc"}
        if season_id:
            params["season_id"] = f"eq.{season_id}"

        return self._get_json("/games", params)

    def get_games_by_team(self, team_id: int, season_id: int | None = None) -> list[dict]:
        """Get games for a specific team."""
        params = {
            "or": f"(home_team_id.eq.{team_id},away_team_id.eq.{team_id})",
            "order": "game_date.desc",
        }
        if season_id:
            params["season_id"] = f"eq.{season_id}"

        return self._get_json("/games", params)

    def add_game(
        self,
        home_team_id: int,
        away_team_id: int,
        game_date: str,
        home_score: int,
        away_score: int,
        season_id: int,
        age_group_id: int,
        game_type_id: int,
    ) -> bool:
        """Add a new game."""
        try:
            game_data = {
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "game_date": game_date,
                "home_score": home_score,
                "away_score": away_score,
                "season_id": season_id,
                "age_group_id": age_group_id,
                "game_type_id": game_type_id,
            }

            result = self._post_json("/games", game_data)
            return bool(result)

        except Exception as e:
            print(f"Error adding game: {e}")
            return False

    def get_league_table(
        self,
        season_id: int | None = None,
        age_group_id: int | None = None,
        game_type: str = "League",
    ) -> list[dict]:
        """Get league table with calculated statistics."""
        try:
            # Build filters
            params = {}
            if season_id:
                params["season_id"] = f"eq.{season_id}"
            if age_group_id:
                params["age_group_id"] = f"eq.{age_group_id}"

            # Get games
            games = self._get_json("/games", params)

            # Get teams to build team name lookup
            teams = self._get_json("/teams")
            team_lookup = {team["id"]: team["name"] for team in teams}

            # Calculate statistics for each team
            stats = {}

            for game in games:
                home_team_id = game["home_team_id"]
                away_team_id = game["away_team_id"]
                home_score = game["home_score"]
                away_score = game["away_score"]

                # Initialize team stats if not exists
                for team_id in [home_team_id, away_team_id]:
                    if team_id not in stats:
                        stats[team_id] = {
                            "team_id": team_id,
                            "team_name": team_lookup.get(team_id, "Unknown"),
                            "games_played": 0,
                            "wins": 0,
                            "draws": 0,
                            "losses": 0,
                            "goals_for": 0,
                            "goals_against": 0,
                            "goal_difference": 0,
                            "points": 0,
                        }

                # Update stats for both teams
                stats[home_team_id]["games_played"] += 1
                stats[away_team_id]["games_played"] += 1

                stats[home_team_id]["goals_for"] += home_score
                stats[home_team_id]["goals_against"] += away_score

                stats[away_team_id]["goals_for"] += away_score
                stats[away_team_id]["goals_against"] += home_score

                # Determine result
                if home_score > away_score:
                    # Home win
                    stats[home_team_id]["wins"] += 1
                    stats[home_team_id]["points"] += 3
                    stats[away_team_id]["losses"] += 1
                elif away_score > home_score:
                    # Away win
                    stats[away_team_id]["wins"] += 1
                    stats[away_team_id]["points"] += 3
                    stats[home_team_id]["losses"] += 1
                else:
                    # Draw
                    stats[home_team_id]["draws"] += 1
                    stats[home_team_id]["points"] += 1
                    stats[away_team_id]["draws"] += 1
                    stats[away_team_id]["points"] += 1

            # Calculate goal difference
            for team_stats in stats.values():
                team_stats["goal_difference"] = (
                    team_stats["goals_for"] - team_stats["goals_against"]
                )

            # Convert to list and sort by points (then by goal difference)
            table = list(stats.values())
            table.sort(key=lambda x: (-x["points"], -x["goal_difference"], -x["goals_for"]))

            # Add position
            for i, team in enumerate(table):
                team["position"] = i + 1

            return table

        except Exception as e:
            print(f"Error calculating league table: {e}")
            return []

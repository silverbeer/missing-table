"""
Enhanced Supabase data access layer with SSL fix.
"""

import os

import httpx
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()


class SupabaseConnection:
    """Manage the connection to Supabase with SSL workaround."""

    def __init__(self):
        """Initialize Supabase client with custom SSL configuration."""
        self.url = os.getenv("SUPABASE_URL")
        # For local development, prefer ANON_KEY over SERVICE_KEY
        self.key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_KEY")

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_SERVICE_KEY) must be set in .env file")
        
        # Debug output
        print(f"DEBUG: Connecting to Supabase URL: {self.url}")
        print(f"DEBUG: Using key type: {'SERVICE_KEY' if 'SUPABASE_SERVICE_KEY' in os.environ and self.key == os.getenv('SUPABASE_SERVICE_KEY') else 'ANON_KEY'}")
        
        try:
            # Try with custom httpx client
            transport = httpx.HTTPTransport(retries=3)
            timeout = httpx.Timeout(30.0, connect=10.0)

            # Create custom client with extended timeout and retries
            http_client = httpx.Client(transport=transport, timeout=timeout, follow_redirects=True)

            # Create Supabase client with custom HTTP client
            self.client = create_client(self.url, self.key, options={"httpx_client": http_client})
            print("Connection to Supabase established.")

        except Exception:
            # Fallback to standard client
            self.client = create_client(self.url, self.key)
            print("Connection to Supabase established.")

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

    def get_all_age_groups(self) -> list[dict]:
        """Get all age groups."""
        try:
            response = self.client.table("age_groups").select("*").order("name").execute()
            return response.data
        except Exception as e:
            print(f"Error querying age groups: {e}")
            return []

    def get_all_seasons(self) -> list[dict]:
        """Get all seasons."""
        try:
            response = (
                self.client.table("seasons").select("*").order("start_date", desc=True).execute()
            )
            return response.data
        except Exception as e:
            print(f"Error querying seasons: {e}")
            return []

    def get_current_season(self) -> dict | None:
        """Get the current active season based on today's date."""
        try:
            from datetime import date

            today = date.today().isoformat()

            response = (
                self.client.table("seasons")
                .select("*")
                .lte("start_date", today)
                .gte("end_date", today)
                .single()
                .execute()
            )

            return response.data
        except Exception as e:
            print(f"No current season found: {e}")
            return None

    def get_active_seasons(self) -> list[dict]:
        """Get active seasons (current and future) for scheduling new games."""
        try:
            from datetime import date

            today = date.today().isoformat()

            response = (
                self.client.table("seasons")
                .select("*")
                .gte("end_date", today)
                .order("start_date", desc=False)
                .execute()
            )

            return response.data
        except Exception as e:
            print(f"Error querying active seasons: {e}")
            return []

    def get_all_game_types(self) -> list[dict]:
        """Get all game types."""
        try:
            response = self.client.table("game_types").select("*").order("name").execute()
            return response.data
        except Exception as e:
            print(f"Error querying game types: {e}")
            return []

    def get_all_divisions(self) -> list[dict]:
        """Get all divisions."""
        try:
            response = self.client.table("divisions").select("*").order("name").execute()
            return response.data
        except Exception as e:
            print(f"Error querying divisions: {e}")
            return []

    # === Team Methods ===

    def get_all_teams(self) -> list[dict]:
        """Get all teams with their age groups."""
        try:
            response = (
                self.client.table("teams")
                .select("""
                *,
                team_mappings (
                    age_groups (
                        id,
                        name
                    ),
                    divisions (
                        id,
                        name
                    )
                )
            """)
                .order("name")
                .execute()
            )

            # Flatten the age groups and divisions for each team
            teams = []
            for team in response.data:
                age_groups = []
                divisions_by_age_group = {}
                if "team_mappings" in team:
                    for tag in team["team_mappings"]:
                        if tag.get("age_groups"):
                            age_group = tag["age_groups"]
                            age_groups.append(age_group)
                            if tag.get("divisions"):
                                divisions_by_age_group[age_group["id"]] = tag["divisions"]
                team["age_groups"] = age_groups
                team["divisions_by_age_group"] = divisions_by_age_group
                teams.append(team)

            return teams
        except Exception as e:
            print(f"Error querying teams: {e}")
            return []

    def get_teams_by_game_type_and_age_group(
        self, game_type_id: int, age_group_id: int
    ) -> list[dict]:
        """Get teams that can participate in a specific game type and age group."""
        try:
            response = (
                self.client.table("teams")
                .select("""
                *,
                team_mappings (
                    age_groups (
                        id,
                        name
                    ),
                    divisions (
                        id,
                        name
                    )
                ),
                team_game_types!inner (
                    game_type_id,
                    age_group_id,
                    is_active
                )
            """)
                .eq("team_game_types.game_type_id", game_type_id)
                .eq("team_game_types.age_group_id", age_group_id)
                .eq("team_game_types.is_active", True)
                .order("name")
                .execute()
            )

            # Flatten the age groups and divisions for each team
            teams = []
            for team in response.data:
                age_groups = []
                divisions_by_age_group = {}
                if "team_mappings" in team:
                    for tag in team["team_mappings"]:
                        if tag.get("age_groups"):
                            age_group = tag["age_groups"]
                            age_groups.append(age_group)
                            if tag.get("divisions"):
                                divisions_by_age_group[age_group["id"]] = tag["divisions"]
                team["age_groups"] = age_groups
                team["divisions_by_age_group"] = divisions_by_age_group
                teams.append(team)

            return teams
        except Exception as e:
            print(f"Error querying teams by game type and age group: {e}")
            return []

    def add_team_game_type_participation(
        self, team_id: int, game_type_id: int, age_group_id: int
    ) -> bool:
        """Add a team's participation in a specific game type and age group."""
        try:
            self.client.table("team_game_types").insert(
                {
                    "team_id": team_id,
                    "game_type_id": game_type_id,
                    "age_group_id": age_group_id,
                    "is_active": True,
                }
            ).execute()
            return True
        except Exception as e:
            print(f"Error adding team game type participation: {e}")
            return False

    def remove_team_game_type_participation(
        self, team_id: int, game_type_id: int, age_group_id: int
    ) -> bool:
        """Remove a team's participation in a specific game type and age group."""
        try:
            self.client.table("team_game_types").update({"is_active": False}).eq(
                "team_id", team_id
            ).eq("game_type_id", game_type_id).eq("age_group_id", age_group_id).execute()
            return True
        except Exception as e:
            print(f"Error removing team game type participation: {e}")
            return False

    def add_team(
        self,
        name: str,
        city: str,
        age_group_ids: list[int],
        division_ids: list[int] | None = None,
        academy_team: bool = False,
    ) -> bool:
        """Add a new team with age groups and optionally divisions."""
        try:
            # Insert team
            team_response = (
                self.client.table("teams")
                .insert({"name": name, "city": city, "academy_team": academy_team})
                .execute()
            )

            if not team_response.data:
                return False

            team_id = team_response.data[0]["id"]

            # Add age group associations with divisions
            for i, age_group_id in enumerate(age_group_ids):
                data = {"team_id": team_id, "age_group_id": age_group_id}
                # Add division if provided
                if division_ids and i < len(division_ids) and division_ids[i]:
                    data["division_id"] = division_ids[i]

                self.client.table("team_mappings").insert(data).execute()

            return True

        except Exception as e:
            print(f"Error adding team: {e}")
            return False

    def update_team_division(self, team_id: int, age_group_id: int, division_id: int) -> bool:
        """Update the division for a team in a specific age group."""
        try:
            response = (
                self.client.table("team_mappings")
                .update({"division_id": division_id})
                .eq("team_id", team_id)
                .eq("age_group_id", age_group_id)
                .execute()
            )

            return bool(response.data)

        except Exception as e:
            print(f"Error updating team division: {e}")
            return False

    # === Game Methods ===

    def get_all_games(
        self,
        season_id: int | None = None,
        age_group_id: int | None = None,
        division_id: int | None = None,
        game_type: str | None = None,
    ) -> list[dict]:
        """Get all games with optional filters."""
        try:
            query = self.client.table("games").select("""
                *,
                home_team:teams!games_home_team_id_fkey(id, name),
                away_team:teams!games_away_team_id_fkey(id, name),
                season:seasons(id, name),
                age_group:age_groups(id, name),
                game_type:game_types(id, name),
                division:divisions(id, name)
            """)

            # Apply filters
            if season_id:
                query = query.eq("season_id", season_id)
            if age_group_id:
                query = query.eq("age_group_id", age_group_id)
            if division_id:
                query = query.eq("division_id", division_id)

            response = query.order("game_date", desc=True).execute()

            # Filter by game_type name if specified (post-query filtering)
            filtered_games = response.data
            if game_type:
                filtered_games = [
                    game
                    for game in response.data
                    if game.get("game_type", {}).get("name") == game_type
                ]

            # Flatten the response for easier use
            games = []
            for game in filtered_games:
                flat_game = {
                    "id": game["id"],
                    "game_date": game["game_date"],
                    "home_team_id": game["home_team_id"],
                    "away_team_id": game["away_team_id"],
                    "home_team_name": game["home_team"]["name"]
                    if game.get("home_team")
                    else "Unknown",
                    "away_team_name": game["away_team"]["name"]
                    if game.get("away_team")
                    else "Unknown",
                    "home_score": game["home_score"],
                    "away_score": game["away_score"],
                    "season_id": game["season_id"],
                    "season_name": game["season"]["name"] if game.get("season") else "Unknown",
                    "age_group_id": game["age_group_id"],
                    "age_group_name": game["age_group"]["name"]
                    if game.get("age_group")
                    else "Unknown",
                    "game_type_id": game["game_type_id"],
                    "game_type_name": game["game_type"]["name"]
                    if game.get("game_type")
                    else "Unknown",
                    "division_id": game.get("division_id"),
                    "division_name": game["division"]["name"]
                    if game.get("division")
                    else "Unknown",
                    "created_at": game["created_at"],
                    "updated_at": game["updated_at"],
                }
                games.append(flat_game)

            return games

        except Exception as e:
            print(f"Error querying games: {e}")
            return []

    def get_games_by_team(self, team_id: int, season_id: int | None = None) -> list[dict]:
        """Get all games for a specific team."""
        try:
            query = (
                self.client.table("games")
                .select("""
                *,
                home_team:teams!games_home_team_id_fkey(id, name),
                away_team:teams!games_away_team_id_fkey(id, name),
                season:seasons(id, name),
                age_group:age_groups(id, name),
                game_type:game_types(id, name),
                division:divisions(id, name)
            """)
                .or_(f"home_team_id.eq.{team_id},away_team_id.eq.{team_id}")
            )

            if season_id:
                query = query.eq("season_id", season_id)

            response = query.order("game_date", desc=True).execute()

            # Flatten response (same as get_all_games)
            games = []
            for game in response.data:
                flat_game = {
                    "id": game["id"],
                    "game_date": game["game_date"],
                    "home_team_id": game["home_team_id"],
                    "away_team_id": game["away_team_id"],
                    "home_team_name": game["home_team"]["name"]
                    if game.get("home_team")
                    else "Unknown",
                    "away_team_name": game["away_team"]["name"]
                    if game.get("away_team")
                    else "Unknown",
                    "home_score": game["home_score"],
                    "away_score": game["away_score"],
                    "season_id": game["season_id"],
                    "season_name": game["season"]["name"] if game.get("season") else "Unknown",
                    "age_group_id": game["age_group_id"],
                    "age_group_name": game["age_group"]["name"]
                    if game.get("age_group")
                    else "Unknown",
                    "game_type_id": game["game_type_id"],
                    "game_type_name": game["game_type"]["name"]
                    if game.get("game_type")
                    else "Unknown",
                    "division_id": game.get("division_id"),
                    "division_name": game["division"]["name"]
                    if game.get("division")
                    else "Unknown",
                }
                games.append(flat_game)

            return games

        except Exception as e:
            print(f"Error querying games by team: {e}")
            return []

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
        division_id: int | None = None,
    ) -> bool:
        """Add a new game."""
        try:
            data = {
                "game_date": game_date,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_score": home_score,
                "away_score": away_score,
                "season_id": season_id,
                "age_group_id": age_group_id,
                "game_type_id": game_type_id,
            }

            # Add division if provided
            if division_id:
                data["division_id"] = division_id

            response = self.client.table("games").insert(data).execute()

            return bool(response.data)

        except Exception as e:
            print(f"Error adding game: {e}")
            return False

    def update_game(
        self,
        game_id: int,
        home_team_id: int,
        away_team_id: int,
        game_date: str,
        home_score: int,
        away_score: int,
        season_id: int,
        age_group_id: int,
        game_type_id: int,
        division_id: int | None = None,
    ) -> bool:
        """Update an existing game."""
        try:
            data = {
                "game_date": game_date,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_score": home_score,
                "away_score": away_score,
                "season_id": season_id,
                "age_group_id": age_group_id,
                "game_type_id": game_type_id,
                "division_id": division_id,
            }

            response = self.client.table("games").update(data).eq("id", game_id).execute()

            return bool(response.data)

        except Exception as e:
            print(f"Error updating game: {e}")
            return False

    def delete_game(self, game_id: int) -> bool:
        """Delete a game."""
        try:
            response = self.client.table("games").delete().eq("id", game_id).execute()

            return True  # Supabase delete returns empty data even on success

        except Exception as e:
            print(f"Error deleting game: {e}")
            return False

    def get_league_table(
        self,
        season_id: int | None = None,
        age_group_id: int | None = None,
        division_id: int | None = None,
        game_type: str = "League",
    ) -> list[dict]:
        """Generate league table with optional filters."""
        try:
            # Build query
            query = self.client.table("games").select("""
                *,
                home_team:teams!games_home_team_id_fkey(id, name),
                away_team:teams!games_away_team_id_fkey(id, name),
                game_type:game_types(id, name)
            """)

            # Apply filters
            if season_id:
                query = query.eq("season_id", season_id)
            if age_group_id:
                query = query.eq("age_group_id", age_group_id)
            if division_id:
                query = query.eq("division_id", division_id)

            # Get games
            response = query.execute()

            # Filter by game type name
            games = [g for g in response.data if g.get("game_type", {}).get("name") == game_type]

            # Calculate standings
            from collections import defaultdict

            standings = defaultdict(
                lambda: {
                    "played": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "goal_difference": 0,
                    "points": 0,
                }
            )

            for game in games:
                home_team = game["home_team"]["name"]
                away_team = game["away_team"]["name"]
                home_score = game["home_score"]
                away_score = game["away_score"]

                # Update stats
                standings[home_team]["played"] += 1
                standings[away_team]["played"] += 1
                standings[home_team]["goals_for"] += home_score
                standings[home_team]["goals_against"] += away_score
                standings[away_team]["goals_for"] += away_score
                standings[away_team]["goals_against"] += home_score

                if home_score > away_score:
                    standings[home_team]["wins"] += 1
                    standings[home_team]["points"] += 3
                    standings[away_team]["losses"] += 1
                elif away_score > home_score:
                    standings[away_team]["wins"] += 1
                    standings[away_team]["points"] += 3
                    standings[home_team]["losses"] += 1
                else:
                    standings[home_team]["draws"] += 1
                    standings[away_team]["draws"] += 1
                    standings[home_team]["points"] += 1
                    standings[away_team]["points"] += 1

            # Convert to list and calculate goal difference
            table = []
            for team, stats in standings.items():
                stats["goal_difference"] = stats["goals_for"] - stats["goals_against"]
                stats["team"] = team
                table.append(stats)

            # Sort by points, goal difference, goals scored
            table.sort(
                key=lambda x: (x["points"], x["goal_difference"], x["goals_for"]), reverse=True
            )

            return table

        except Exception as e:
            print(f"Error generating league table: {e}")
            return []

    # === Admin CRUD Methods ===

    def create_age_group(self, name: str) -> dict:
        """Create a new age group."""
        try:
            result = self.client.table("age_groups").insert({"name": name}).execute()
            return result.data[0]
        except Exception as e:
            print(f"Error creating age group: {e}")
            raise e

    def update_age_group(self, age_group_id: int, name: str) -> dict | None:
        """Update an age group."""
        try:
            result = (
                self.client.table("age_groups")
                .update({"name": name})
                .eq("id", age_group_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error updating age group: {e}")
            raise e

    def delete_age_group(self, age_group_id: int) -> bool:
        """Delete an age group."""
        try:
            result = self.client.table("age_groups").delete().eq("id", age_group_id).execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"Error deleting age group: {e}")
            raise e

    def create_season(self, name: str, start_date: str, end_date: str) -> dict:
        """Create a new season."""
        try:
            result = (
                self.client.table("seasons")
                .insert({"name": name, "start_date": start_date, "end_date": end_date})
                .execute()
            )
            return result.data[0]
        except Exception as e:
            print(f"Error creating season: {e}")
            raise e

    def update_season(
        self, season_id: int, name: str, start_date: str, end_date: str
    ) -> dict | None:
        """Update a season."""
        try:
            result = (
                self.client.table("seasons")
                .update({"name": name, "start_date": start_date, "end_date": end_date})
                .eq("id", season_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error updating season: {e}")
            raise e

    def delete_season(self, season_id: int) -> bool:
        """Delete a season."""
        try:
            result = self.client.table("seasons").delete().eq("id", season_id).execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"Error deleting season: {e}")
            raise e

    def create_division(self, name: str, description: str | None = None) -> dict:
        """Create a new division."""
        try:
            data = {
                "name": name,
                "description": description or "",  # Always include description, even if empty
            }
            print(f"Creating division with data: {data}")
            result = self.client.table("divisions").insert(data).execute()
            print(f"Division created successfully: {result.data[0]}")
            return result.data[0]
        except Exception as e:
            print(f"Error creating division: {e}")
            raise e

    def update_division(
        self, division_id: int, name: str, description: str | None = None
    ) -> dict | None:
        """Update a division."""
        try:
            data = {"name": name}
            if description is not None:
                data["description"] = description
            result = self.client.table("divisions").update(data).eq("id", division_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error updating division: {e}")
            raise e

    def delete_division(self, division_id: int) -> bool:
        """Delete a division."""
        try:
            result = self.client.table("divisions").delete().eq("id", division_id).execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"Error deleting division: {e}")
            raise e

    def update_team(
        self, team_id: int, name: str, city: str, academy_team: bool = False
    ) -> dict | None:
        """Update a team."""
        try:
            result = (
                self.client.table("teams")
                .update({"name": name, "city": city, "academy_team": academy_team})
                .eq("id", team_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error updating team: {e}")
            raise e

    def delete_team(self, team_id: int) -> bool:
        """Delete a team."""
        try:
            result = self.client.table("teams").delete().eq("id", team_id).execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"Error deleting team: {e}")
            raise e

    def create_team_mapping(self, team_id: int, age_group_id: int, division_id: int) -> dict:
        """Create a team mapping."""
        try:
            result = (
                self.client.table("team_mappings")
                .insert(
                    {"team_id": team_id, "age_group_id": age_group_id, "division_id": division_id}
                )
                .execute()
            )
            return result.data[0]
        except Exception as e:
            print(f"Error creating team mapping: {e}")
            raise e

    def delete_team_mapping(self, team_id: int, age_group_id: int, division_id: int) -> bool:
        """Delete a team mapping."""
        try:
            result = (
                self.client.table("team_mappings")
                .delete()
                .eq("team_id", team_id)
                .eq("age_group_id", age_group_id)
                .eq("division_id", division_id)
                .execute()
            )
            return len(result.data) > 0
        except Exception as e:
            print(f"Error deleting team mapping: {e}")
            raise e

#!/usr/bin/env python3
"""
Comprehensive migration script to move data from SQLite to a new Supabase project.
This handles the complete migration including schema creation and data transfer.
"""

import argparse
import os
import sqlite3
import sys

from dotenv import load_dotenv

from supabase import create_client

# Load environment variables
load_dotenv()


class SupabaseMigration:
    def __init__(self, supabase_url=None, supabase_key=None, sqlite_db="mlsnext_u13_fall.db"):
        """Initialize migration with database connections."""
        # Use provided credentials or fallback to env
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_SERVICE_KEY")
        self.sqlite_db = sqlite_db

        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Supabase credentials required. Set in .env or pass as arguments.")

        # Initialize Supabase client
        self.supabase = create_client(self.supabase_url, self.supabase_key)

        # Connect to SQLite
        self.sqlite_conn = sqlite3.connect(self.sqlite_db)
        self.sqlite_conn.row_factory = sqlite3.Row

    def create_schema(self):
        """Create the database schema in Supabase."""

        # Note: Supabase doesn't support direct SQL execution via the client
        # You'll need to run this SQL in the Supabase dashboard SQL editor

        input("\n✋ Press Enter after you've created the schema in Supabase...")

    def populate_reference_data(self):
        """Populate reference data (age groups, seasons, game types)."""

        # Age Groups
        age_groups = [
            {"name": "U13"},
            {"name": "U14"},
            {"name": "U15"},
            {"name": "U16"},
            {"name": "U17"},
            {"name": "U18"},
            {"name": "U19"},
            {"name": "Open"},
        ]

        for ag in age_groups:
            try:
                self.supabase.table("age_groups").insert(ag).execute()
            except Exception as e:
                if "duplicate" in str(e).lower():
                    pass
                else:
                    pass

        # Seasons
        seasons = [
            {"name": "2023-2024", "start_date": "2023-09-01", "end_date": "2024-06-30"},
            {"name": "2024-2025", "start_date": "2024-09-01", "end_date": "2025-06-30"},
            {"name": "2025-2026", "start_date": "2025-09-01", "end_date": "2026-06-30"},
        ]

        for season in seasons:
            try:
                self.supabase.table("seasons").insert(season).execute()
            except Exception as e:
                if "duplicate" in str(e).lower():
                    pass
                else:
                    pass

        # Game Types
        game_types = [
            {"name": "League"},
            {"name": "Tournament"},
            {"name": "Friendly"},
            {"name": "Playoff"},
        ]

        for gt in game_types:
            try:
                self.supabase.table("game_types").insert(gt).execute()
            except Exception as e:
                if "duplicate" in str(e).lower():
                    pass
                else:
                    pass

        # Get IDs for later use
        self.season_2024_25 = (
            self.supabase.table("seasons").select("id").eq("name", "2024-2025").single().execute().data["id"]
        )
        self.u13_age_group = (
            self.supabase.table("age_groups").select("id").eq("name", "U13").single().execute().data["id"]
        )
        self.league_game_type = (
            self.supabase.table("game_types").select("id").eq("name", "League").single().execute().data["id"]
        )

    def migrate_teams(self):
        """Migrate teams from SQLite to Supabase."""

        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT * FROM teams ORDER BY name")
        sqlite_teams = cursor.fetchall()

        self.team_mapping = {}  # Map old IDs to new IDs

        for team in sqlite_teams:
            team_data = {"name": team["name"], "city": team["city"] or "Unknown City"}

            try:
                response = self.supabase.table("teams").insert(team_data).execute()
                new_team = response.data[0]
                self.team_mapping[team["id"]] = new_team["id"]

                # Associate with U13 age group
                self.supabase.table("team_mappings").insert(
                    {"team_id": new_team["id"], "age_group_id": self.u13_age_group}
                ).execute()

            except Exception as e:
                if "duplicate" in str(e).lower():
                    # Team exists, get its ID
                    existing = self.supabase.table("teams").select("id").eq("name", team["name"]).single().execute()
                    self.team_mapping[team["id"]] = existing.data["id"]
                else:
                    pass

    def migrate_games(self):
        """Migrate games from SQLite to Supabase."""

        cursor = self.sqlite_conn.cursor()
        cursor.execute("""
            SELECT g.*,
                   ht.name as home_team_name,
                   at.name as away_team_name
            FROM games g
            JOIN teams ht ON g.home_team = ht.name
            JOIN teams at ON g.away_team = at.name
            ORDER BY g.game_date
        """)
        sqlite_games = cursor.fetchall()

        # Get team name to ID mapping from Supabase
        teams_response = self.supabase.table("teams").select("id, name").execute()
        team_name_to_id = {team["name"]: team["id"] for team in teams_response.data}

        games_to_insert = []
        failed_games = []

        for game in sqlite_games:
            home_team_id = team_name_to_id.get(game["home_team_name"])
            away_team_id = team_name_to_id.get(game["away_team_name"])

            if not home_team_id or not away_team_id:
                failed_games.append(
                    {
                        "date": game["game_date"],
                        "home": game["home_team_name"],
                        "away": game["away_team_name"],
                        "reason": "Team not found",
                    }
                )
                continue

            game_data = {
                "game_date": game["game_date"],
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_score": game["home_score"],
                "away_score": game["away_score"],
                "season_id": self.season_2024_25,
                "age_group_id": self.u13_age_group,
                "game_type_id": self.league_game_type,
            }

            games_to_insert.append(game_data)

        # Insert games in batches
        batch_size = 100
        inserted_count = 0

        for i in range(0, len(games_to_insert), batch_size):
            batch = games_to_insert[i : i + batch_size]
            try:
                self.supabase.table("games").insert(batch).execute()
                inserted_count += len(batch)
            except Exception as e:
                failed_games.extend(
                    [
                        {
                            "date": g["game_date"],
                            "home": "ID " + str(g["home_team_id"]),
                            "away": "ID " + str(g["away_team_id"]),
                            "reason": str(e)[:50],
                        }
                        for g in batch
                    ]
                )

        if failed_games:
            for _fg in failed_games[:5]:
                pass

    def verify_migration(self):
        """Verify the migration was successful."""

        # Count records in Supabase
        supabase_teams = self.supabase.table("teams").select("*", count="exact").execute().count
        supabase_games = self.supabase.table("games").select("*", count="exact").execute().count

        # Count records in SQLite
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM teams")
        sqlite_teams = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM games")
        sqlite_games = cursor.fetchone()[0]

        # Log migration counts
        print(f"Migration verification: teams={supabase_teams}/{sqlite_teams}, games={supabase_games}/{sqlite_games}")

    def generate_env_file(self):
        """Generate a new .env file template."""

        env_content = f"""# Supabase Configuration - NEW PROJECT
SUPABASE_URL={self.supabase_url}
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_key_here

# Application Configuration
ENVIRONMENT=development
"""

        with open(".env.new", "w") as f:
            f.write(env_content)

    def run_full_migration(self):
        """Run the complete migration process."""

        # Step 1: Create schema
        self.create_schema()

        # Step 2: Populate reference data
        self.populate_reference_data()

        # Step 3: Migrate teams
        self.migrate_teams()

        # Step 4: Migrate games
        self.migrate_games()

        # Step 5: Verify
        self.verify_migration()

        # Step 6: Generate env file
        self.generate_env_file()


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite data to new Supabase project")
    parser.add_argument("--url", help="Supabase project URL (or set SUPABASE_URL in .env)")
    parser.add_argument("--key", help="Supabase service key (or set SUPABASE_SERVICE_KEY in .env)")
    parser.add_argument("--sqlite", default="mlsnext_u13_fall.db", help="SQLite database path")

    args = parser.parse_args()

    try:
        migration = SupabaseMigration(supabase_url=args.url, supabase_key=args.key, sqlite_db=args.sqlite)
        migration.run_full_migration()

    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()

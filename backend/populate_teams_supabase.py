#!/usr/bin/env python3
"""Script to populate teams and team-game type mappings using Supabase client."""

import csv
import os

from dotenv import load_dotenv
from supabase import Client, create_client

# Load environment variables
load_dotenv(".env.local", override=True)

# Initialize Supabase client
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

print(f"URL: {url}")
print(f"Key: {key[:20]}..." if key else "Key: None")

if not url or not key:
    raise Exception("Missing required environment variables: SUPABASE_URL and SUPABASE_SERVICE_KEY")

supabase: Client = create_client(url, key)


def populate_teams():
    """Populate teams from CSV and create game type mappings."""

    # Read teams from CSV
    teams = []
    csv_path = "/Users/tdrake/silverbeer/missing-table/backend/mlsnext_u13_teams.csv"

    try:
        with open(csv_path) as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["name"].strip():  # Skip empty rows
                    teams.append(
                        {
                            "name": row["name"].strip(),
                            "city": row["city"].strip(),
                            "academy_team": False,
                        }
                    )
    except FileNotFoundError:
        print(f"CSV file not found at {csv_path}")
        print("Creating some sample teams instead...")
        teams = [
            {"name": "IFA", "city": "New York", "academy_team": False},
            {"name": "NYRB", "city": "Harrison", "academy_team": True},
            {"name": "Manhattan SC", "city": "New York", "academy_team": False},
            {"name": "Brooklyn FC", "city": "Brooklyn", "academy_team": False},
            {"name": "Queens United", "city": "Queens", "academy_team": False},
        ]

    print(f"Found {len(teams)} teams to insert")

    # Insert teams
    inserted_teams = []
    try:
        result = supabase.table("teams").insert(teams).execute()
        inserted_teams = result.data
        print(f"Inserted {len(inserted_teams)} teams")

        for team in inserted_teams:
            print(f"  - {team['name']} ({team['city']}) - ID: {team['id']}")

    except Exception as e:
        print(f"Error inserting teams: {e}")
        return

    # Get Homegrown league and default division
    print("\n🔍 Looking up Homegrown league...")
    try:
        homegrown_league = supabase.table("leagues").select("id").eq("name", "Homegrown").execute()
        if not homegrown_league.data:
            print("❌ Error: Homegrown league not found")
            return

        league_id = homegrown_league.data[0]["id"]
        print(f"✅ Found Homegrown league (ID: {league_id})")

        # Get or create default division for Homegrown league
        divisions = supabase.table("divisions").select("id").eq("name", "Default").eq("league_id", league_id).execute()
        if divisions.data:
            division_id = divisions.data[0]["id"]
            print(f"✅ Using existing Default division (ID: {division_id})")
        else:
            # Create default division if it doesn't exist
            print("Creating Default division for Homegrown league...")
            new_div = supabase.table("divisions").insert({
                "name": "Default",
                "description": "Default division for Homegrown league",
                "league_id": league_id
            }).execute()
            division_id = new_div.data[0]["id"]
            print(f"✅ Created Default division (ID: {division_id})")
    except Exception as e:
        print(f"❌ Error setting up division: {e}")
        return

    # Add team mappings and game type participations
    team_mappings = []
    team_game_types = []

    for team in inserted_teams:
        team_id = team["id"]

        # Add team mapping for U14 age group with league-aware division
        team_mappings.append(
            {
                "team_id": team_id,
                "age_group_id": 2,  # U14
                "division_id": division_id,  # League-aware division
            }
        )

        # Add team-game type participations for all game types and U14 age group
        for game_type_id in [1, 2, 3, 4]:  # League, Tournament, Friendly, Playoff
            team_game_types.append(
                {
                    "team_id": team_id,
                    "game_type_id": game_type_id,
                    "age_group_id": 2,  # U14
                    "is_active": True,
                }
            )

    # Insert team mappings
    try:
        if team_mappings:
            result = supabase.table("team_mappings").insert(team_mappings).execute()
            print(f"Inserted {len(result.data)} team mappings")
    except Exception as e:
        print(f"Error inserting team mappings: {e}")

    # Insert team-game type participations
    try:
        if team_game_types:
            result = supabase.table("team_game_types").insert(team_game_types).execute()
            print(f"Inserted {len(result.data)} team-game type mappings")
    except Exception as e:
        print(f"Error inserting team-game type mappings: {e}")

    # Verify the data
    try:
        teams_count = supabase.table("teams").select("id").execute()
        mappings_count = supabase.table("team_game_types").select("id").execute()

        print("\nVerification:")
        print(f"Total teams in database: {len(teams_count.data)}")
        print(f"Total team-game type mappings: {len(mappings_count.data)}")

    except Exception as e:
        print(f"Error during verification: {e}")


def populate_seasons():
    """Add current and future seasons."""
    seasons = [
        {"name": "2024-2025", "start_date": "2024-08-01", "end_date": "2025-07-31"},
        {"name": "2025-2026", "start_date": "2025-08-01", "end_date": "2026-07-31"},
    ]

    try:
        result = supabase.table("seasons").insert(seasons).execute()
        print(f"Inserted {len(result.data)} seasons")
        for season in result.data:
            print(f"  - {season['name']}")
    except Exception as e:
        print(f"Error inserting seasons: {e}")


def make_user_admin(email: str):
    """Make a user an admin."""
    try:
        # First get user ID from auth.users table by email
        auth_users = supabase.table("auth.users").select("id").eq("email", email).execute()

        if not auth_users.data:
            print(f"User {email} not found in auth.users")
            return

        user_id = auth_users.data[0]["id"]

        # Update user role to admin in user_profiles
        result = (
            supabase.table("user_profiles").update({"role": "admin"}).eq("id", user_id).execute()
        )

        if result.data:
            print(f"Made {email} an admin (ID: {user_id})")
        else:
            print(f"Failed to update {email}")

    except Exception as e:
        print(f"Error making user admin: {e}")
        print("Note: You may need to create the user account first by signing up")


if __name__ == "__main__":
    try:
        print("=== Populating Teams ===")
        populate_teams()

        print("\n=== Populating Seasons ===")
        populate_seasons()

        print("\n=== Making tdrake13@gmail.com Admin ===")
        make_user_admin("tdrake13@gmail.com")

        print("\n=== Population Complete ===")

    except Exception as e:
        print(f"Error: {e}")

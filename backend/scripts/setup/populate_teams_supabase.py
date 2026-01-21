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
        teams = [
            {"name": "IFA", "city": "New York", "academy_team": False},
            {"name": "NYRB", "city": "Harrison", "academy_team": True},
            {"name": "Manhattan SC", "city": "New York", "academy_team": False},
            {"name": "Brooklyn FC", "city": "Brooklyn", "academy_team": False},
            {"name": "Queens United", "city": "Queens", "academy_team": False},
        ]

    # Insert teams
    inserted_teams = []
    try:
        result = supabase.table("teams").insert(teams).execute()
        inserted_teams = result.data

        for _team in inserted_teams:
            pass

    except Exception:
        return

    # Get Homegrown league and default division
    try:
        homegrown_league = supabase.table("leagues").select("id").eq("name", "Homegrown").execute()
        if not homegrown_league.data:
            return

        league_id = homegrown_league.data[0]["id"]

        # Get or create default division for Homegrown league
        divisions = supabase.table("divisions").select("id").eq("name", "Default").eq("league_id", league_id).execute()
        if divisions.data:
            division_id = divisions.data[0]["id"]
        else:
            # Create default division if it doesn't exist
            new_div = (
                supabase.table("divisions")
                .insert(
                    {
                        "name": "Default",
                        "description": "Default division for Homegrown league",
                        "league_id": league_id,
                    }
                )
                .execute()
            )
            division_id = new_div.data[0]["id"]
    except Exception:
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
    except Exception:
        pass

    # Insert team-game type participations
    try:
        if team_game_types:
            result = supabase.table("team_game_types").insert(team_game_types).execute()
    except Exception:
        pass

    # Verify the data
    try:
        supabase.table("teams").select("id").execute()
        supabase.table("team_game_types").select("id").execute()

    except Exception:
        pass


def populate_seasons():
    """Add current and future seasons."""
    seasons = [
        {"name": "2024-2025", "start_date": "2024-08-01", "end_date": "2025-07-31"},
        {"name": "2025-2026", "start_date": "2025-08-01", "end_date": "2026-07-31"},
    ]

    try:
        result = supabase.table("seasons").insert(seasons).execute()
        for _season in result.data:
            pass
    except Exception:
        pass


def make_user_admin(email: str):
    """Make a user an admin."""
    try:
        # First get user ID from auth.users table by email
        auth_users = supabase.table("auth.users").select("id").eq("email", email).execute()

        if not auth_users.data:
            return

        user_id = auth_users.data[0]["id"]

        # Update user role to admin in user_profiles
        result = supabase.table("user_profiles").update({"role": "admin"}).eq("id", user_id).execute()

        if result.data:
            pass
        else:
            pass

    except Exception:
        pass


if __name__ == "__main__":
    try:
        populate_teams()

        populate_seasons()

        make_user_admin("tdrake13@gmail.com")

    except Exception:
        pass

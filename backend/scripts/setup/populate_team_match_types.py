#!/usr/bin/env python3
"""Populate team_match_types table to fix Add Match team dropdown."""

import os

from dotenv import load_dotenv

from supabase import Client, create_client


def load_environment():
    """Load environment variables based on APP_ENV or default to dev."""
    load_dotenv()
    app_env = os.getenv("APP_ENV", "dev")
    env_file = f".env.{app_env}"
    if os.path.exists(env_file):
        load_dotenv(env_file, override=True)
    else:
        pass


# Load environment
load_environment()

# Initialize Supabase client
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

supabase: Client = create_client(url, key)


def populate_team_match_types():
    """Populate team_match_types table based on team_mappings and match_types."""

    # Check current state
    try:
        current_data = supabase.table("team_match_types").select("*").execute()

        if len(current_data.data) > 0:
            supabase.table("team_match_types").delete().neq("id", 0).execute()

    except Exception:
        return False

    # Get all team mappings
    try:
        team_mappings = supabase.table("team_mappings").select("team_id, age_group_id").execute()

        if not team_mappings.data:
            return False

    except Exception:
        return False

    # Get all match types
    try:
        match_types = supabase.table("match_types").select("id, name").execute()

        for _mt in match_types.data:
            pass

    except Exception:
        return False

    # Create team_match_types entries for each combination

    team_match_types_data = []

    for tm in team_mappings.data:
        for mt in match_types.data:
            entry = {
                "team_id": tm["team_id"],
                "match_type_id": mt["id"],
                "age_group_id": tm["age_group_id"],
                "is_active": True,
            }
            team_match_types_data.append(entry)

    # Insert in batches
    batch_size = 100
    total_inserted = 0

    try:
        for i in range(0, len(team_match_types_data), batch_size):
            batch = team_match_types_data[i : i + batch_size]
            result = supabase.table("team_match_types").insert(batch).execute()
            total_inserted += len(result.data)

    except Exception:
        return False

    # Verify the fix

    try:
        # Test the specific query that was failing
        verification_query = (
            supabase.table("team_match_types").select("*").eq("match_type_id", 1).eq("age_group_id", 1).execute()
        )

        return len(verification_query.data) > 0

    except Exception:
        return False


if __name__ == "__main__":
    success = populate_team_match_types()

    if success:
        pass
    else:
        pass

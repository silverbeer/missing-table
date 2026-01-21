#!/usr/bin/env python3
"""
Populate reference data for the new schema.
Run this after the schema changes to set up age groups, seasons, and game types.
"""

import contextlib
import os

from dotenv import load_dotenv

from supabase import create_client

load_dotenv()


def populate_reference_data():
    """Populate age_groups, seasons, and game_types tables."""

    # Initialize Supabase client
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    supabase = create_client(url, service_key)

    # 1. Age Groups
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

    with contextlib.suppress(Exception):
        supabase.table("age_groups").insert(age_groups).execute()

    # 2. Seasons
    seasons = [
        {"name": "2023-2024", "start_date": "2023-09-01", "end_date": "2024-06-30"},
        {"name": "2024-2025", "start_date": "2024-09-01", "end_date": "2025-06-30"},
        {"name": "2025-2026", "start_date": "2025-09-01", "end_date": "2026-06-30"},
    ]

    with contextlib.suppress(Exception):
        supabase.table("seasons").insert(seasons).execute()

    # 3. Game Types
    game_types = [
        {"name": "League"},
        {"name": "Tournament"},
        {"name": "Friendly"},
        {"name": "Playoff"},
    ]

    with contextlib.suppress(Exception):
        supabase.table("game_types").insert(game_types).execute()

    # Show what was created

    # Age groups
    supabase.table("age_groups").select("*").execute()

    # Seasons
    supabase.table("seasons").select("*").execute()

    # Game types
    supabase.table("game_types").select("*").execute()


if __name__ == "__main__":
    populate_reference_data()

#!/usr/bin/env python3
"""
Create sample games using the new schema for testing.
"""

import os
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()


def create_sample_games():
    """Create sample games for testing the new schema."""

    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    supabase = create_client(url, service_key)

    print("🎮 Creating sample games...")

    # Get reference data
    teams = supabase.table("teams").select("*").execute().data
    seasons = supabase.table("seasons").select("*").execute().data
    age_groups = supabase.table("age_groups").select("*").execute().data
    game_types = supabase.table("game_types").select("*").execute().data

    # Find current season and relevant IDs
    current_season = next((s for s in seasons if s["name"] == "2024-2025"), seasons[0])
    u13_age_group = next((ag for ag in age_groups if ag["name"] == "U13"), age_groups[0])
    league_game_type = next((gt for gt in game_types if gt["name"] == "League"), game_types[0])
    tournament_game_type = next(
        (gt for gt in game_types if gt["name"] == "Tournament"), game_types[0]
    )

    print(f"Using season: {current_season['name']}")
    print(f"Using age group: {u13_age_group['name']}")

    # Create sample games
    sample_games = []

    # Generate 10 league games
    for i in range(10):
        home_team = random.choice(teams)
        away_team = random.choice([t for t in teams if t["id"] != home_team["id"]])

        # Random date in the current season
        base_date = datetime(2024, 9, 1)  # Season start
        random_days = random.randint(0, 200)
        game_date = (base_date + timedelta(days=random_days)).date()

        # Random scores
        home_score = random.randint(0, 5)
        away_score = random.randint(0, 5)

        sample_games.append(
            {
                "game_date": game_date.isoformat(),
                "home_team_id": home_team["id"],
                "away_team_id": away_team["id"],
                "home_score": home_score,
                "away_score": away_score,
                "season_id": current_season["id"],
                "age_group_id": u13_age_group["id"],
                "game_type_id": league_game_type["id"],
            }
        )

    # Generate 3 tournament games
    for i in range(3):
        home_team = random.choice(teams)
        away_team = random.choice([t for t in teams if t["id"] != home_team["id"]])

        base_date = datetime(2025, 3, 1)  # Tournament time
        random_days = random.randint(0, 30)
        game_date = (base_date + timedelta(days=random_days)).date()

        home_score = random.randint(0, 4)
        away_score = random.randint(0, 4)

        sample_games.append(
            {
                "game_date": game_date.isoformat(),
                "home_team_id": home_team["id"],
                "away_team_id": away_team["id"],
                "home_score": home_score,
                "away_score": away_score,
                "season_id": current_season["id"],
                "age_group_id": u13_age_group["id"],
                "game_type_id": tournament_game_type["id"],
            }
        )

    # Insert sample games
    try:
        response = supabase.table("games").insert(sample_games).execute()
        print(f"✅ Created {len(sample_games)} sample games")

        # Show some examples
        print("\n📋 Sample games created:")
        for game in sample_games[:5]:
            home_name = next(t["name"] for t in teams if t["id"] == game["home_team_id"])
            away_name = next(t["name"] for t in teams if t["id"] == game["away_team_id"])
            game_type = "League" if game["game_type_id"] == league_game_type["id"] else "Tournament"
            print(
                f"  - {game['game_date']}: {home_name} vs {away_name} ({game['home_score']}-{game['away_score']}) [{game_type}]"
            )

        if len(sample_games) > 5:
            print(f"  ... and {len(sample_games) - 5} more")

    except Exception as e:
        print(f"❌ Error creating sample games: {e}")


if __name__ == "__main__":
    create_sample_games()

#!/usr/bin/env python3
"""
Migrate MLS Next U13 Northeast data from SQLite to Supabase
"""

import os
import sqlite3

from supabase import Client, create_client

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables are required. "
        "Please set them in your .env file."
    )

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def migrate_data():
    print("🚀 Starting MLS Next U13 Northeast data migration...")

    # Connect to SQLite
    sqlite_path = "data/mlsnext_u13_fall.db"
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get reference IDs from Supabase
    print("\n📋 Getting reference data...")

    # Get U13 age group ID
    age_group_response = (
        supabase.table("age_groups").select("*").eq("name", "U13").single().execute()
    )
    u13_id = age_group_response.data["id"]
    print(f"✅ U13 age group ID: {u13_id}")

    # Get 2024-2025 season ID
    season_response = (
        supabase.table("seasons").select("*").eq("name", "2024-2025").single().execute()
    )
    season_id = season_response.data["id"]
    print(f"✅ 2024-2025 season ID: {season_id}")

    # Get League game type ID
    game_type_response = (
        supabase.table("game_types").select("*").eq("name", "League").single().execute()
    )
    league_id = game_type_response.data["id"]
    print(f"✅ League game type ID: {league_id}")

    # Get Northeast division ID
    # IMPORTANT: After league layer implementation, "Northeast" may exist in multiple leagues.
    # This assumes Homegrown league. For production use, filter by league_id:
    # .eq("league_id", homegrown_league_id)
    division_response = (
        supabase.table("divisions").select("*").eq("name", "Northeast").single().execute()
    )
    division_id = division_response.data["id"]
    print(f"✅ Northeast division ID: {division_id}")
    print(f"⚠️  Note: Assuming Homegrown league (first match)")

    # Migrate Teams
    print("\n👥 Migrating teams...")
    cursor.execute("SELECT * FROM teams ORDER BY name")
    sqlite_teams = cursor.fetchall()

    team_mapping = {}  # Map SQLite team names to Supabase IDs

    for team in sqlite_teams:
        # Insert team
        team_data = {
            "name": team["name"],
            "city": "Northeast",  # Using region as city since all are "Unknown City"
        }

        try:
            response = supabase.table("teams").insert(team_data).execute()
            new_team_id = response.data[0]["id"]
            team_mapping[team["name"]] = new_team_id

            # Create team mapping for U13 Northeast
            mapping_data = {
                "team_id": new_team_id,
                "age_group_id": u13_id,
                "division_id": division_id,
            }
            supabase.table("team_mappings").insert(mapping_data).execute()

            print(f"✅ Migrated: {team['name']}")

        except Exception as e:
            if "duplicate" in str(e):
                # Team exists, get its ID
                existing = (
                    supabase.table("teams").select("id").eq("name", team["name"]).single().execute()
                )
                team_mapping[team["name"]] = existing.data["id"]
                print(f"ℹ️  Team exists: {team['name']}")
            else:
                print(f"❌ Error migrating team {team['name']}: {e}")

    print(f"\n✅ Migrated {len(team_mapping)} teams")

    # Migrate Games
    print("\n⚽ Migrating games...")
    cursor.execute("SELECT * FROM games ORDER BY game_date")
    sqlite_games = cursor.fetchall()

    games_migrated = 0
    games_skipped = 0

    for game in sqlite_games:
        home_team_id = team_mapping.get(game["home_team"])
        away_team_id = team_mapping.get(game["away_team"])

        if not home_team_id or not away_team_id:
            print(f"⚠️  Skipping game: {game['home_team']} vs {game['away_team']} - team not found")
            games_skipped += 1
            continue

        game_data = {
            "game_date": game["game_date"],
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "home_score": game["home_score"],
            "away_score": game["away_score"],
            "season_id": season_id,
            "age_group_id": u13_id,
            "game_type_id": league_id,
            "division_id": division_id,
        }

        try:
            supabase.table("games").insert(game_data).execute()
            games_migrated += 1

        except Exception as e:
            print(
                f"❌ Error migrating game {game['game_date']}: {game['home_team']} vs {game['away_team']} - {e}"
            )
            games_skipped += 1

    print(f"\n✅ Migrated {games_migrated} games")
    if games_skipped > 0:
        print(f"⚠️  Skipped {games_skipped} games")

    # Verify migration
    print("\n🔍 Verifying migration...")

    teams_count = supabase.table("teams").select("*", count="exact").execute().count
    games_count = supabase.table("games").select("*", count="exact").execute().count

    print("\n📊 Migration Summary:")
    print(f"Teams in Supabase: {teams_count}")
    print(f"Games in Supabase: {games_count}")

    # Show sample games
    sample_games = (
        supabase.table("games")
        .select("""
        *,
        home_team:teams!games_home_team_id_fkey(name),
        away_team:teams!games_away_team_id_fkey(name)
    """)
        .limit(3)
        .execute()
    )

    print("\n📋 Sample migrated games:")
    for game in sample_games.data:
        print(
            f"   {game['game_date']}: {game['home_team']['name']} vs {game['away_team']['name']} ({game['home_score']}-{game['away_score']})"
        )

    conn.close()
    print("\n🎉 Migration complete!")


if __name__ == "__main__":
    try:
        migrate_data()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()

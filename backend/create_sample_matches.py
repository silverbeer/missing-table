#!/usr/bin/env python3
"""Create sample matches for testing the league layer implementation."""

from dao.match_dao import MatchDAO, SupabaseConnection
from datetime import datetime, timedelta
import random


def create_sample_matches():
    """Create sample matches with the new league-aware schema."""
    conn = SupabaseConnection()
    dao = MatchDAO(conn)

    # Get current data
    teams = dao.get_all_teams()
    seasons = dao.get_all_seasons()
    age_groups = dao.get_all_age_groups()
    divisions = dao.get_all_divisions()
    match_types = dao.get_all_match_types()

    print(f"Found {len(teams)} teams")
    print(f"Found {len(seasons)} seasons")
    print(f"Found {len(age_groups)} age groups")
    print(f"Found {len(divisions)} divisions")
    print(f"Found {len(match_types)} match types")

    # Create some sample matches
    if teams and seasons and divisions and match_types:
        season_name = seasons[0]["name"]
        division_name = divisions[0]["name"]

        # Get teams that have mappings
        teams_with_mappings = [t for t in teams if t.get("age_groups")]

        print(f"\nCreating matches for {len(teams_with_mappings)} teams...")

        matches_created = 0
        for i in range(0, len(teams_with_mappings), 2):
            if i + 1 >= len(teams_with_mappings):
                break

            home_team = teams_with_mappings[i]
            away_team = teams_with_mappings[i + 1]

            # Get age group from first mapping
            if home_team["age_groups"] and away_team["age_groups"]:
                age_group_name = home_team["age_groups"][0]["name"]

                # Create a match
                match_date = datetime.now() - timedelta(days=random.randint(1, 30))

                match_data = {
                    "home_team_id": home_team["id"],
                    "away_team_id": away_team["id"],
                    "match_date": match_date.isoformat(),
                    "season": season_name,
                    "age_group": age_group_name,
                    "division": division_name,
                    "home_score": random.randint(0, 5),
                    "away_score": random.randint(0, 5),
                    "match_status": "completed",
                }

                try:
                    result = dao.create_match(**match_data)
                    if result:
                        matches_created += 1
                        print(
                            f'  ✓ Created match: {home_team["name"]} vs {away_team["name"]}'
                        )
                except Exception as e:
                    print(f"  ✗ Error creating match: {e}")

        print(f"\n✅ Created {matches_created} matches")
    else:
        print("Missing required data to create matches")


if __name__ == "__main__":
    create_sample_matches()

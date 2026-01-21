#!/usr/bin/env python3
"""Create sample matches for testing the league layer implementation."""

import sys
from pathlib import Path

# Add backend root directory to path for imports (scripts/setup/ -> backend/)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import random
from datetime import datetime, timedelta

from dao.match_dao import MatchDAO, SupabaseConnection


def create_sample_matches():
    """Create sample matches with the new league-aware schema."""
    conn = SupabaseConnection()
    dao = MatchDAO(conn)

    # Get current data
    teams = dao.get_all_teams()
    seasons = dao.get_all_seasons()
    dao.get_all_age_groups()
    divisions = dao.get_all_divisions()
    match_types = dao.get_all_match_types()

    # Create some sample matches
    if teams and seasons and divisions and match_types:
        season_name = seasons[0]["name"]
        division_name = divisions[0]["name"]

        # Get teams that have mappings
        teams_with_mappings = [t for t in teams if t.get("age_groups")]

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
                except Exception:
                    pass

    else:
        pass


if __name__ == "__main__":
    create_sample_matches()

#!/usr/bin/env python3
"""Create sample matches for testing the league layer implementation."""

import sys
from pathlib import Path

# Add backend root directory to path for imports (scripts/setup/ -> backend/)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import random
from datetime import datetime, timedelta

from dao.league_dao import LeagueDAO
from dao.match_dao import MatchDAO, SupabaseConnection
from dao.season_dao import SeasonDAO
from dao.team_dao import TeamDAO


def create_sample_matches():
    """Create sample matches with the new league-aware schema."""
    conn = SupabaseConnection()
    match_dao = MatchDAO(conn)
    team_dao = TeamDAO(conn)
    season_dao = SeasonDAO(conn)
    league_dao = LeagueDAO(conn)

    # Get current data
    teams = team_dao.get_all_teams()
    seasons = season_dao.get_all_seasons()
    divisions = league_dao.get_all_divisions()

    # Create some sample matches
    if teams and seasons and divisions:
        season_id = seasons[0]["id"]
        division_id = divisions[0]["id"]

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
                age_group_id = home_team["age_groups"][0]["id"]

                # Create a match
                match_date = datetime.now() - timedelta(days=random.randint(1, 30))

                match_data = {
                    "home_team_id": home_team["id"],
                    "away_team_id": away_team["id"],
                    "match_date": match_date.isoformat(),
                    "season_id": season_id,
                    "age_group_id": age_group_id,
                    "division_id": division_id,
                    "home_score": random.randint(0, 5),
                    "away_score": random.randint(0, 5),
                    "match_status": "completed",
                }

                try:
                    result = match_dao.create_match(**match_data)
                    if result:
                        matches_created += 1
                except Exception:
                    pass


if __name__ == "__main__":
    create_sample_matches()

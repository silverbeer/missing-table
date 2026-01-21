#!/usr/bin/env python3
"""
Populate sample teams and games data in local Supabase.
"""

import psycopg2


def populate_sample_data():
    """Populate sample teams and games."""
    try:
        conn = psycopg2.connect(host="localhost", port=5432, user="postgres", password="postgres", database="postgres")
        cursor = conn.cursor()

        # Sample teams for U13 league
        teams = [
            ("Eagles", "Philadelphia"),
            ("Lions", "Detroit"),
            ("Bears", "Chicago"),
            ("Ravens", "Baltimore"),
            ("Falcons", "Atlanta"),
            ("Cardinals", "Arizona"),
            ("Seahawks", "Seattle"),
            ("Panthers", "Carolina"),
        ]

        # Insert teams
        team_ids = []
        for name, city in teams:
            cursor.execute("INSERT INTO teams (name, city) VALUES (%s, %s) RETURNING id", (name, city))
            team_id = cursor.fetchone()[0]
            team_ids.append(team_id)

            # Associate with U13 age group (id=1)
            cursor.execute(
                "INSERT INTO team_mappings (team_id, age_group_id) VALUES (%s, %s)",
                (team_id, 1),  # U13 age group
            )

        # Add some sample games for current season (2024-2025, id=2)
        games = [
            (team_ids[0], team_ids[1], "2024-10-15", 2, 1),  # Eagles vs Lions
            (team_ids[2], team_ids[3], "2024-10-15", 1, 3),  # Bears vs Ravens
            (team_ids[4], team_ids[5], "2024-10-22", 0, 2),  # Falcons vs Cardinals
            (team_ids[6], team_ids[7], "2024-10-22", 3, 1),  # Seahawks vs Panthers
            (team_ids[1], team_ids[2], "2024-10-29", 2, 2),  # Lions vs Bears
            (team_ids[3], team_ids[0], "2024-10-29", 1, 4),  # Ravens vs Eagles
            (team_ids[5], team_ids[4], "2024-11-05", 3, 0),  # Cardinals vs Falcons
            (team_ids[7], team_ids[6], "2024-11-05", 1, 2),  # Panthers vs Seahawks
        ]

        for home_id, away_id, game_date, home_score, away_score in games:
            cursor.execute(
                """
                INSERT INTO games (
                    game_date, home_team_id, away_team_id,
                    home_score, away_score, season_id, age_group_id, game_type_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (game_date, home_id, away_id, home_score, away_score, 2, 1, 1),
            )  # Season 2024-2025, U13, League

        conn.commit()
        cursor.close()
        conn.close()

        return True

    except Exception:
        return False


if __name__ == "__main__":
    populate_sample_data()

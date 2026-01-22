#!/usr/bin/env python3
"""Script to populate teams and team-game type mappings from CSV data."""

import csv

import psycopg2

# Database connection
conn = psycopg2.connect(host="127.0.0.1", port="54322", database="postgres", user="postgres", password="postgres")


def populate_teams():
    """Populate teams from CSV and create game type mappings."""
    cursor = conn.cursor()

    # Read teams from CSV (path relative to backend root)
    from pathlib import Path

    backend_root = Path(__file__).parent.parent.parent
    csv_path = backend_root / "mlsnext_u13_teams.csv"

    teams = []
    with open(csv_path) as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["name"].strip():  # Skip empty rows
                teams.append((row["name"].strip(), row["city"].strip()))

    # Insert teams
    for name, city in teams:
        cursor.execute(
            """
            INSERT INTO teams (name, city, academy_team, created_at, updated_at)
            VALUES (%s, %s, false, NOW(), NOW())
            RETURNING id
        """,
            (name, city),
        )
        team_id = cursor.fetchone()[0]

        # Add team mappings for U14 age group with default division
        cursor.execute(
            """
            INSERT INTO team_mappings (team_id, age_group_id, division_id, created_at)
            VALUES (%s, 2, 1, NOW())
        """,
            (team_id,),
        )

        # Add team-game type participations for all game types and U14 age group
        for game_type_id in [1, 2, 3, 4]:  # League, Tournament, Friendly, Playoff
            cursor.execute(
                """
                INSERT INTO team_game_types (team_id, game_type_id, age_group_id, is_active, created_at, updated_at)
                VALUES (%s, %s, 2, true, NOW(), NOW())
            """,
                (team_id, game_type_id),
            )

    # Commit all changes
    conn.commit()

    # Verify the data
    cursor.execute("SELECT COUNT(*) FROM teams")
    cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM team_game_types")
    cursor.fetchone()[0]

    cursor.close()


if __name__ == "__main__":
    try:
        populate_teams()
    except Exception:
        conn.rollback()
    finally:
        conn.close()

#!/usr/bin/env python3
"""Script to populate teams and team-game type mappings from CSV data."""

import csv

import psycopg2

# Database connection
conn = psycopg2.connect(
    host="127.0.0.1", port="54322", database="postgres", user="postgres", password="postgres"
)


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

    print(f"Found {len(teams)} teams to insert")

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
        print(f"Inserted team: {name} (ID: {team_id})")

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

        print(f"  Added mappings and game type participations for {name}")

    # Commit all changes
    conn.commit()
    print(f"\nSuccessfully populated {len(teams)} teams with game type mappings")

    # Verify the data
    cursor.execute("SELECT COUNT(*) FROM teams")
    team_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM team_game_types")
    mapping_count = cursor.fetchone()[0]

    print(f"Total teams in database: {team_count}")
    print(f"Total team-game type mappings: {mapping_count}")

    cursor.close()


if __name__ == "__main__":
    try:
        populate_teams()
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

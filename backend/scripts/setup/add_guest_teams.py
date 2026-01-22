#!/usr/bin/env python3
"""Script to add guest teams that only play friendlies."""

import psycopg2

# Database connection
conn = psycopg2.connect(host="127.0.0.1", port="54322", database="postgres", user="postgres", password="postgres")


def add_guest_teams():
    """Add guest teams that only participate in friendly games."""
    cursor = conn.cursor()

    # Guest teams to add
    guest_teams = [
        ("Boston Guest FC", "Northeast"),
        ("Philadelphia United Guest", "Northeast"),
        ("DC Metro Guest", "Northeast"),
        ("Miami Select Guest", "Southeast"),
        ("Atlanta Guest FC", "Southeast"),
    ]

    # Get the Friendly game type ID
    cursor.execute("SELECT id FROM game_types WHERE name = 'Friendly'")
    friendly_id = cursor.fetchone()[0]

    for name, city in guest_teams:
        # Insert team
        cursor.execute(
            """
            INSERT INTO teams (name, city, academy_team, created_at, updated_at)
            VALUES (%s, %s, false, NOW(), NOW())
            RETURNING id
        """,
            (name, city),
        )
        team_id = cursor.fetchone()[0]

        # Add team mapping for U14 age group
        cursor.execute(
            """
            INSERT INTO team_mappings (team_id, age_group_id, division_id, created_at)
            VALUES (%s, 2, 1, NOW())
        """,
            (team_id,),
        )

        # Add team-game type participation for Friendly only
        cursor.execute(
            """
            INSERT INTO team_game_types (team_id, game_type_id, age_group_id, is_active, created_at, updated_at)
            VALUES (%s, %s, 2, true, NOW(), NOW())
        """,
            (team_id, friendly_id),
        )

    conn.commit()

    # Verify the guest teams
    cursor.execute("""
        SELECT t.name, array_agg(gt.name) as game_types
        FROM teams t
        JOIN team_game_types tgt ON t.id = tgt.team_id
        JOIN game_types gt ON tgt.game_type_id = gt.id
        WHERE t.name LIKE '%Guest%'
        GROUP BY t.name
    """)

    for _row in cursor.fetchall():
        pass

    cursor.close()


if __name__ == "__main__":
    try:
        add_guest_teams()
    except Exception:
        conn.rollback()
    finally:
        conn.close()

#!/usr/bin/env python3
"""
Create admin invite for tdrake13@gmail.com
This script creates an invite directly in the database bypassing RLS
"""

import secrets
from datetime import datetime, timedelta

import psycopg2


def create_admin_invite():
    """Create admin invite directly via PostgreSQL connection"""

    # Generate invite code
    code_chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    invite_code = "".join(secrets.choice(code_chars) for _ in range(12))

    # Database connection details (from Supabase local)
    conn_params = {
        "host": "localhost",
        "port": 54322,
        "database": "postgres",
        "user": "postgres",
        "password": "postgres",
    }

    try:
        # Connect to PostgreSQL directly
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()

        # Insert admin invite
        sql = """
        INSERT INTO public.invitations (
            invite_code,
            invite_type,
            team_id,
            age_group_id,
            email,
            status,
            expires_at,
            created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s
        ) RETURNING invite_code, email;
        """

        # Calculate expiration (30 days from now)
        expires_at = datetime.now() + timedelta(days=30)
        created_at = datetime.now()

        cursor.execute(
            sql,
            (
                invite_code,
                "team_manager",
                1,  # First team
                1,  # First age group
                "tdrake13@gmail.com",
                "pending",
                expires_at,
                created_at,
            ),
        )

        result = cursor.fetchone()
        conn.commit()

        cursor.close()
        conn.close()

        return result[0]

    except Exception:
        return None


if __name__ == "__main__":
    create_admin_invite()

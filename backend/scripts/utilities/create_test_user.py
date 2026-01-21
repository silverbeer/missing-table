#!/usr/bin/env python3
"""Create a test non-admin user for testing role-based access."""

import os

from dotenv import load_dotenv

from supabase import create_client

load_dotenv(".env.local", override=True)
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

client = create_client(url, key)

# Get IFA team
teams = client.table("teams").select("*").eq("name", "IFA").execute()
if not teams.data:
    exit(1)

ifa_team = teams.data[0]

# Create test user credentials
username = "team_manager"
password = "test123"
email = f"{username}@missingtable.local"
display_name = "IFA Team Manager"


# Sign up user via Supabase Auth
try:
    auth_response = client.auth.sign_up(
        {
            "email": email,
            "password": password,
        }
    )

    if auth_response.user:
        user_id = auth_response.user.id

        # Update user profile with role, team, and username
        profile_update = (
            client.table("user_profiles")
            .update(
                {
                    "role": "team-manager",
                    "team_id": ifa_team["id"],
                    "username": username,
                    "display_name": display_name,
                }
            )
            .eq("id", user_id)
            .execute()
        )

        if profile_update.data:
            pass
        else:
            pass
    else:
        pass

except Exception:
    # User might already exist, try to find and update
    try:
        profiles = client.table("user_profiles").select("*").eq("username", username).execute()
        if profiles.data:
            user_id = profiles.data[0]["id"]

            # Update to team-manager role
            update_result = (
                client.table("user_profiles")
                .update(
                    {
                        "role": "team-manager",
                        "team_id": ifa_team["id"],
                        "display_name": display_name,
                    }
                )
                .eq("id", user_id)
                .execute()
            )

            if update_result.data:
                pass
    except Exception:
        pass

#!/usr/bin/env python3
"""
Setup audit trail for games table.
Creates match-scraper service account and backfills existing games.
Run this AFTER migration 014_add_game_audit_fields.sql completes.
"""

import os

from supabase import create_client

# Use local Supabase by default
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
SUPABASE_KEY = os.getenv(  # pragma: allowlist secret
    "SUPABASE_SERVICE_ROLE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU",  # noqa: S105 - Local Supabase demo key
)


def main():
    """Setup audit trail."""
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Step 1: Create service account via Supabase Auth API

    try:
        # Check if service account already exists in user_profiles
        result = client.table("user_profiles").select("*").eq("display_name", "Match Scraper Service").execute()

        if result.data and len(result.data) > 0:
            scraper_user_id = result.data[0]["id"]
        else:
            # Use admin API to create the service account user

            import requests

            # Create user via admin API
            admin_url = f"{SUPABASE_URL}/auth/v1/admin/users"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
            }

            payload = {
                "email": "match-scraper@service.missingtable.com",
                "password": "service-account-no-password-" + os.urandom(16).hex(),  # pragma: allowlist secret
                "email_confirm": True,
                "user_metadata": {"display_name": "Match Scraper Service", "service_account": True},
            }

            response = requests.post(admin_url, headers=headers, json=payload)

            if response.status_code == 200 or response.status_code == 201:
                user_data = response.json()
                scraper_user_id = user_data["id"]

                # Promote to admin (user_profile should be auto-created by trigger)
                import time

                time.sleep(1)  # Wait for trigger to fire

                client.table("user_profiles").update({"role": "admin"}).eq("id", scraper_user_id).execute()

            else:
                return False

    except Exception:
        import traceback

        traceback.print_exc()
        return False

    # Step 2: Backfill existing games

    try:
        # Get all games without audit trail
        # Don't select mls_match_id as it might not exist in all environments
        games = client.table("games").select("id").is_("created_by", "null").execute()

        if not games.data:
            pass
        else:
            # Update all games - set source to 'import' for legacy data
            # (we can't distinguish between match-scraper and manual without mls_match_id)
            client.table("games").update(
                {"created_by": scraper_user_id, "updated_by": scraper_user_id, "source": "import"}
            ).is_("created_by", "null").execute()

    except Exception:
        return False

    # Step 3: Verify

    try:
        all_games = client.table("games").select("id, source, created_by").execute()

        [g for g in all_games.data if g.get("created_by")]
        games_without_audit = [g for g in all_games.data if not g.get("created_by")]

        if games_without_audit:
            pass
        else:
            pass

    except Exception:
        return False

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

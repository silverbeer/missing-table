#!/usr/bin/env python3
"""
Create a service user for the match-scraper integration.
This user will be used by the match-scraper to authenticate with the API.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

from supabase import create_client

# Load environment variables
load_dotenv()


async def create_scraper_service_user():
    """Create a service user for the match-scraper"""

    # Initialize Supabase client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        return False

    client = create_client(url, key)

    # Service user credentials from environment
    email = os.getenv("SCRAPER_USER_EMAIL", "scraper-service@missing-table.local")
    password = os.getenv("SCRAPER_USER_PASSWORD")

    if not password:
        return False

    try:
        # Create the user account
        auth_response = client.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,  # Skip email confirmation for service user
            }
        )

        if auth_response.user:
            user_id = auth_response.user.id

            # Create user profile with admin role
            profile_data = {
                "id": user_id,
                "email": email,
                "role": "admin",  # Give admin permissions for full API access
                "full_name": "Match Scraper Service",
                "created_at": "now()",
                "updated_at": "now()",
            }

            profile_response = client.table("user_profiles").insert(profile_data).execute()

            return bool(profile_response.data)
        else:
            return False

    except Exception:
        return False


async def main():
    """Main function"""
    success = await create_scraper_service_user()
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

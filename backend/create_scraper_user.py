#!/usr/bin/env python3
"""
Create a service user for the match-scraper integration.
This user will be used by the match-scraper to authenticate with the API.
"""

import asyncio
import sys
from supabase import create_client
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()


async def create_scraper_service_user():
    """Create a service user for the match-scraper"""

    # Initialize Supabase client
    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
    key = os.getenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU")

    client = create_client(url, key)

    # Service user credentials
    email = "scraper-service@missing-table.local"
    password = "scraper-service-password-change-in-production"

    try:
        print("🤖 Creating match-scraper service user...")

        # Create the user account
        auth_response = client.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True  # Skip email confirmation for service user
        })

        if auth_response.user:
            user_id = auth_response.user.id
            print(f"✅ Created service user with ID: {user_id}")

            # Create user profile with admin role
            profile_data = {
                "id": user_id,
                "email": email,
                "role": "admin",  # Give admin permissions for full API access
                "full_name": "Match Scraper Service",
                "created_at": "now()",
                "updated_at": "now()"
            }

            profile_response = client.table("user_profiles").insert(profile_data).execute()

            if profile_response.data:
                print("✅ Created user profile with admin role")
                print("\n📋 Service User Details:")
                print(f"   Email: {email}")
                print(f"   Password: {password}")
                print(f"   Role: admin")
                print(f"   User ID: {user_id}")

                print("\n🔐 For your match-scraper environment:")
                print(f"   MISSING_TABLE_API_URL=http://localhost:8000")
                print(f"   SCRAPER_USER_EMAIL={email}")
                print(f"   SCRAPER_USER_PASSWORD={password}")

                print("\n⚠️  IMPORTANT: Change the password in production!")
                return True
            else:
                print("❌ Failed to create user profile")
                return False
        else:
            print("❌ Failed to create service user")
            return False

    except Exception as e:
        print(f"❌ Error creating service user: {e}")
        return False


async def main():
    """Main function"""
    success = await create_scraper_service_user()
    if not success:
        sys.exit(1)
    print("\n🎉 Service user created successfully!")


if __name__ == "__main__":
    asyncio.run(main())
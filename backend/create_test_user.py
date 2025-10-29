#!/usr/bin/env python3
"""Create a test non-admin user for testing role-based access."""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('.env.local', override=True)
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')

client = create_client(url, key)

# Get IFA team
teams = client.table('teams').select('*').eq('name', 'IFA').execute()
if not teams.data:
    print("❌ IFA team not found")
    exit(1)

ifa_team = teams.data[0]
print(f"✓ Found IFA team (ID: {ifa_team['id']})")

# Create test user credentials
username = "team_manager"
password = "test123"
email = f"{username}@missingtable.local"
display_name = "IFA Team Manager"

print(f"\nCreating user: {username}")

# Sign up user via Supabase Auth
try:
    auth_response = client.auth.sign_up({
        "email": email,
        "password": password,
    })

    if auth_response.user:
        user_id = auth_response.user.id
        print(f"✓ Created auth user (ID: {user_id})")

        # Update user profile with role, team, and username
        profile_update = client.table('user_profiles').update({
            'role': 'team-manager',
            'team_id': ifa_team['id'],
            'username': username,
            'display_name': display_name,
        }).eq('id', user_id).execute()

        if profile_update.data:
            print(f"✓ Updated profile:")
            print(f"    Username: {username}")
            print(f"    Password: {password}")
            print(f"    Role: team-manager")
            print(f"    Team: {ifa_team['name']} (ID: {ifa_team['id']})")
            print(f"    Display Name: {display_name}")
            print("\n✅ Test user created successfully!")
            print("\nLogin credentials:")
            print(f"  Username: {username}")
            print(f"  Password: {password}")
        else:
            print("❌ Failed to update user profile")
    else:
        print("❌ Failed to create auth user")

except Exception as e:
    print(f"❌ Error: {e}")
    # User might already exist, try to find and update
    print("\nTrying to find existing user...")
    try:
        profiles = client.table('user_profiles').select('*').eq('username', username).execute()
        if profiles.data:
            user_id = profiles.data[0]['id']
            print(f"✓ Found existing user (ID: {user_id})")

            # Update to team-manager role
            update_result = client.table('user_profiles').update({
                'role': 'team-manager',
                'team_id': ifa_team['id'],
                'display_name': display_name,
            }).eq('id', user_id).execute()

            if update_result.data:
                print(f"✓ Updated existing user:")
                print(f"    Username: {username}")
                print(f"    Password: {password}")
                print(f"    Role: team-manager")
                print(f"    Team: {ifa_team['name']} (ID: {ifa_team['id']})")
                print("\n✅ User updated successfully!")
                print("\nLogin credentials:")
                print(f"  Username: {username}")
                print(f"  Password: {password}")
    except Exception as e2:
        print(f"❌ Error finding/updating existing user: {e2}")

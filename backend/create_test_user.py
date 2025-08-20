#!/usr/bin/env python3
"""
Create a test user profile for e2e testing.
"""

import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment
load_dotenv('.env.local', override=True)

# Initialize Supabase client with service role
url = os.getenv("SUPABASE_URL")
service_key = os.getenv("SUPABASE_SERVICE_KEY")

if not url or not service_key:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    exit(1)

supabase = create_client(url, service_key)

# Create test user profile
test_user_id = "550e8400-e29b-41d4-a716-446655440001"
test_profile = {
    "id": test_user_id,
    "role": "admin",
    "display_name": "Test Admin"
}

try:
    # First create the auth user (using raw SQL since Supabase auth is complex)
    print("Creating auth user...")
    auth_user_sql = f"""
    INSERT INTO auth.users (id, email, encrypted_password, email_confirmed_at, created_at, updated_at, instance_id, aud, role)
    VALUES (
        '{test_user_id}',
        'testadmin@example.com',
        crypt('testpassword123', gen_salt('bf')),
        now(),
        now(),
        now(),
        '00000000-0000-0000-0000-000000000000'::uuid,
        'authenticated',
        'authenticated'
    )
    ON CONFLICT (id) DO NOTHING;
    """
    
    supabase.rpc("exec_sql", {"sql": auth_user_sql}).execute()
    
    # Now create the user profile
    print("Creating user profile...")
    result = supabase.table("user_profiles").insert(test_profile).execute()
    
    if result.data:
        print("✅ Test user and profile created successfully!")
        print(f"👤 User ID: {test_user_id}")
        print(f"👑 Role: admin")
        print(f"📧 Email: testadmin@example.com")
        print(f"📧 Display Name: Test Admin")
        print(f"🔑 Password: testpassword123")
    else:
        print("❌ Failed to create test user profile")
        
except Exception as e:
    print(f"❌ Error creating test user: {e}")
    # Try just the profile in case auth user already exists
    try:
        print("Trying to create just the profile...")
        result = supabase.table("user_profiles").insert(test_profile).execute()
        if result.data:
            print("✅ Test user profile created successfully!")
    except Exception as e2:
        print(f"❌ Profile creation also failed: {e2}")
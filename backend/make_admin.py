#!/usr/bin/env python3
"""Script to make a user an admin."""

import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local', override=True)

# Initialize Supabase client with service key (needed for admin operations)
url = os.getenv("SUPABASE_URL")
service_key = os.getenv("SUPABASE_SERVICE_KEY")

if not url or not service_key:
    raise Exception("Missing required environment variables: SUPABASE_URL and SUPABASE_SERVICE_KEY")

supabase = create_client(url, service_key)

# Email to make admin
email = "tdrake13@gmail.com"

# First, get the user's auth ID
auth_response = supabase.auth.admin.list_users()
user_id = None

for user in auth_response:
    if user.email == email:
        user_id = user.id
        break

if not user_id:
    print(f"User with email {email} not found")
    exit(1)

print(f"Found user: {email} with ID: {user_id}")

# Update the user's role in user_profiles table
try:
    response = supabase.table('user_profiles').update({
        'role': 'admin'
    }).eq('id', user_id).execute()
    
    if response.data:
        print(f"Successfully updated {email} to admin role")
    else:
        print(f"No user profile found for {email}")
        # Create profile if it doesn't exist
        response = supabase.table('user_profiles').insert({
            'id': user_id,
            'email': email,
            'role': 'admin'
        }).execute()
        print(f"Created admin profile for {email}")
        
except Exception as e:
    print(f"Error updating user role: {e}")
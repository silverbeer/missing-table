#!/usr/bin/env python3

import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Load env from current directory (should be run from backend dir)
load_dotenv()

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')
client = create_client(url, key)

print('Checking for users and their emails...')
print('=' * 50)

# Check user_profiles table first
try:
    profiles = client.table('user_profiles').select('*').execute()
    print(f'Found {len(profiles.data or [])} user profiles:')
    
    found_target = False
    for profile in profiles.data or []:
        user_id = profile.get('id')
        name = profile.get('name', 'Unknown')
        role = profile.get('role', 'Unknown')
        
        print(f'\nUser: {name}')
        print(f'  ID: {user_id}')
        print(f'  Role: {role}')
        
        # Try to get email from auth.users
        try:
            auth_user = client.auth.admin.get_user_by_id(user_id)
            if auth_user and auth_user.user and auth_user.user.email:
                email = auth_user.user.email
                print(f'  Email: {email}')
                if email == 'tdrake13@gmail.com':
                    print('  *** FOUND tdrake13@gmail.com! ***')
                    found_target = True
            else:
                print('  Email: Not found in auth system')
        except Exception as e:
            print(f'  Email: Error fetching - {str(e)[:80]}...')
    
    print('\n' + '=' * 50)
    if found_target:
        print('✅ tdrake13@gmail.com exists in the system')
    else:
        print('❌ tdrake13@gmail.com not found in the system')
            
except Exception as e:
    print(f'Error querying database: {e}')
#!/usr/bin/env python3
"""
Create uptime test user in Supabase for login testing.
This user will be used by the uptime monitoring system to verify login functionality.
"""

import os
import sys
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
load_dotenv('.env.local', override=True)

def create_test_user():
    """Create the uptime_test user in Supabase."""
    
    # Initialize Supabase client with service key (has admin privileges)
    url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not url or not service_key:
        print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables")
        return False
    
    try:
        supabase = create_client(url, service_key)
        
        print("🔍 Checking if uptime_test user already exists...")
        
        # Check if user already exists
        try:
            # Try to get existing user by email
            response = supabase.auth.admin.list_users()
            existing_users = response.users if hasattr(response, 'users') else []
            
            uptime_user = None
            for user in existing_users:
                if user.email == 'uptime_test@example.com':
                    uptime_user = user
                    break
            
            if uptime_user:
                print("✅ uptime_test user already exists")
                print(f"   User ID: {uptime_user.id}")
                print(f"   Email: {uptime_user.email}")
                return True
                
        except Exception as e:
            print(f"⚠️  Could not check existing users: {e}")
        
        print("👤 Creating uptime_test user...")
        
        # Create the user
        user_response = supabase.auth.admin.create_user({
            'email': 'uptime_test@example.com',
            'password': 'Changeme!',
            'email_confirm': True,  # Auto-confirm email
            'user_metadata': {
                'role': 'user',
                'name': 'Uptime Test User',
                'created_for': 'automated_testing'
            }
        })
        
        if user_response.user:
            user_id = user_response.user.id
            print(f"✅ User created successfully!")
            print(f"   User ID: {user_id}")
            print(f"   Email: uptime_test@example.com")
            print(f"   Password: Changeme!")
            
            # Create user profile entry
            try:
                print("📝 Creating user profile...")
                profile_response = supabase.table('user_profiles').insert({
                    'id': user_id,
                    'email': 'uptime_test@example.com',
                    'role': 'user',
                    'name': 'Uptime Test User'
                }).execute()
                
                if profile_response.data:
                    print("✅ User profile created successfully")
                else:
                    print("⚠️  User profile creation may have failed, but user exists")
                    
            except Exception as e:
                print(f"⚠️  Could not create user profile: {e}")
                print("   User still exists and can be used for login testing")
            
            return True
        else:
            print("❌ Failed to create user")
            return False
            
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return False

def main():
    """Main function."""
    print("🚀 Creating uptime test user for login verification")
    print("=" * 50)
    
    success = create_test_user()
    
    if success:
        print("\n🎉 Setup complete!")
        print("Test credentials:")
        print("  Email: uptime_test@example.com")
        print("  Password: Changeme!")
        print("\nThis user can now be used for automated login testing.")
    else:
        print("\n❌ Setup failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
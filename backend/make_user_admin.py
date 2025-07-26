#!/usr/bin/env python3
"""
Script to make a user an admin by updating their role in user_profiles.
Can work with either email (if they signed up) or profile ID.
"""

import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local', override=True)

# Initialize Supabase client
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

if not url or not key:
    raise Exception("Missing required environment variables: SUPABASE_URL and SUPABASE_SERVICE_KEY")

supabase: Client = create_client(url, key)

def list_users():
    """List all user profiles."""
    try:
        profiles = supabase.table('user_profiles').select('*').execute()
        
        if not profiles.data:
            print("No user profiles found.")
            print("Users need to sign up through the application UI first.")
            return []
        
        print("Current user profiles:")
        print("-" * 60)
        
        for i, profile in enumerate(profiles.data, 1):
            role = profile.get('role', 'no role')
            display_name = profile.get('display_name', 'No name')
            team_id = profile.get('team_id', 'No team')
            created = profile.get('created_at', 'Unknown')[:10]  # Just date part
            
            print(f"{i}. ID: {profile['id']}")
            print(f"   Name: {display_name}")
            print(f"   Role: {role}")
            print(f"   Team ID: {team_id}")
            print(f"   Created: {created}")
            print()
        
        return profiles.data
        
    except Exception as e:
        print(f"Error listing users: {e}")
        return []

def make_user_admin(user_id: str):
    """Make a user an admin by their profile ID."""
    try:
        # First check if user exists
        user_check = supabase.table('user_profiles').select('*').eq('id', user_id).execute()
        
        if not user_check.data:
            print(f"❌ User with ID {user_id} not found")
            return False
        
        current_user = user_check.data[0]
        current_role = current_user.get('role', 'no role')
        display_name = current_user.get('display_name', 'Unknown')
        
        print(f"Found user: {display_name} (current role: {current_role})")
        
        # Update to admin
        result = supabase.table('user_profiles').update({
            'role': 'admin'
        }).eq('id', user_id).execute()
        
        if result.data:
            print(f"✅ Successfully made user {display_name} an admin!")
            return True
        else:
            print(f"❌ Failed to update user {display_name}")
            return False
            
    except Exception as e:
        print(f"❌ Error making user admin: {e}")
        return False

def interactive_mode():
    """Interactive mode to select and update users."""
    users = list_users()
    
    if not users:
        return
    
    print("Select a user to make admin:")
    
    try:
        choice = input("Enter user number (or 'q' to quit): ").strip()
        
        if choice.lower() == 'q':
            print("Cancelled.")
            return
        
        user_index = int(choice) - 1
        
        if 0 <= user_index < len(users):
            user = users[user_index]
            confirm = input(f"Make '{user.get('display_name', 'Unknown')}' an admin? (y/N): ")
            
            if confirm.lower() == 'y':
                make_user_admin(user['id'])
            else:
                print("Cancelled.")
        else:
            print("Invalid selection.")
            
    except (ValueError, KeyboardInterrupt):
        print("\nCancelled.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Make a user an admin")
    parser.add_argument('--list', action='store_true', help='List all users')
    parser.add_argument('--user-id', help='User ID to make admin')
    parser.add_argument('--interactive', action='store_true', help='Interactive mode to select user')
    
    args = parser.parse_args()
    
    try:
        if args.list:
            list_users()
        elif args.user_id:
            make_user_admin(args.user_id)
        elif args.interactive or len(sys.argv) == 1:
            interactive_mode()
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
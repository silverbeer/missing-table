"""
Remove foreign key constraints to auth.users table in production
"""
import os
from supabase import create_client

def remove_fk_constraints():
    """Remove FK constraints that reference auth.users"""
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Missing credentials")
        return False
    
    print("✓ Loaded environment: prod")
    
    # Create client
    supabase = create_client(supabase_url, supabase_key)
    
    print("\n📋 Foreign key constraints to remove:")
    print("  1. user_profiles_id_fkey (user_profiles.id → auth.users.id)")
    print("  2. matches_created_by_fkey (matches.created_by → auth.users.id)")  
    print("  3. matches_updated_by_fkey (matches.updated_by → auth.users.id)")
    
    print("\n⚠️  These constraints must be removed via SQL Editor in Supabase Dashboard")
    print("\nSQL to run:")
    print("-" * 60)
    print("ALTER TABLE user_profiles DROP CONSTRAINT IF EXISTS user_profiles_id_fkey;")
    print("ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_created_by_fkey;")
    print("ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_updated_by_fkey;")
    print("-" * 60)
    print("\n💡 After running this SQL, retry the restore operation.")
    
    return True

if __name__ == "__main__":
    remove_fk_constraints()

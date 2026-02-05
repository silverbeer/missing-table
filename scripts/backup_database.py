#!/usr/bin/env python3
"""
Comprehensive database backup script for MLS Next development.
Creates JSON backups of all tables with timestamp.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Add backend to path for shared modules
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.append(str(backend_path))

# Load environment variables based on APP_ENV
app_env = os.getenv('APP_ENV', 'local')
env_file = f'.env.{app_env}'
env_path = backend_path / env_file

if not env_path.exists():
    # Fallback to .env if specific env file doesn't exist
    env_path = backend_path / '.env'

load_dotenv(env_path, override=True)
print(f"✓ Loaded environment: {app_env}")

# Initialize Supabase client
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

if not url or not key:
    raise Exception("Missing required environment variables: SUPABASE_URL and SUPABASE_SERVICE_KEY")

supabase: Client = create_client(url, key)
db_url = os.getenv("DATABASE_URL")

# Tables intentionally excluded from backups
EXCLUDED_TABLES = {
    'user_profiles',    # Managed per-environment (different auth.users UUIDs)
    'schema_version',   # Internal tracking, recreated by migrations
    'service_accounts', # Contains API keys - managed per-environment
}


def check_for_new_tables(tables_to_backup: list) -> list:
    """
    Check if there are tables in the database not included in the backup list.
    Returns list of tables that are missing from backups.
    """
    try:
        import psycopg2
        if not db_url:
            print("  ⚠ Cannot check for new tables: DATABASE_URL not set")
            return []

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
        """)
        db_tables = {row[0] for row in cur.fetchall()}
        conn.close()

        backup_set = set(tables_to_backup) | EXCLUDED_TABLES
        missing = db_tables - backup_set

        if missing:
            print("=" * 60)
            print("⚠️  WARNING: Tables exist in database but NOT in backup list:")
            for table in sorted(missing):
                print(f"    - {table}")
            print()
            print("  Add these to 'tables_to_backup' in backup_database.py")
            print("  Or add to 'EXCLUDED_TABLES' if intentionally skipped.")
            print("=" * 60)
            print()

        return list(missing)

    except ImportError:
        print("  ⚠ psycopg2 not available, skipping table check")
        return []
    except Exception as e:
        print(f"  ⚠ Could not check for new tables: {e}")
        return []


def backup_table(table_name: str, select_columns: str = '*'):
    """Backup a single table to JSON."""
    try:
        print(f"Backing up {table_name}...")
        result = supabase.table(table_name).select(select_columns).execute()
        
        if result.data:
            print(f"  ✓ {len(result.data)} records")
            return result.data
        else:
            print(f"  ✓ 0 records (empty table)")
            return []
            
    except Exception as e:
        print(f"  ✗ Error backing up {table_name}: {e}")
        return None

def create_backup():
    """Create a complete database backup."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(__file__).parent.parent / 'backups'
    backup_dir.mkdir(exist_ok=True)
    
    backup_file = backup_dir / f"database_backup_{timestamp}.json"
    
    print(f"Creating database backup: {backup_file}")
    print("=" * 50)
    
    # Define tables to backup in order of dependencies
    # NOTE: user_profiles is EXCLUDED from backups
    # Reason: Users and profiles are managed per-environment, not synced between dev/prod
    # - Each environment has its own auth.users with different UUIDs
    # - user_profiles.id must match auth.users.id (no FK constraint but logical requirement)
    # - Restoring user_profiles from another environment causes UUID mismatches
    # - See docs/FOREIGN_KEY_DECISION.md for details
    # - Use backend/manage_users.py to create users in each environment
    tables_to_backup = [
        # Reference data (no dependencies)
        'age_groups',
        'leagues',  # Added for league layer support - must come before divisions
        'divisions',  # Now depends on leagues
        'match_types',
        'seasons',

        # Clubs (before teams - teams have club_id foreign key)
        'clubs',

        # Teams and mappings
        'teams',
        'team_mappings',
        'team_match_types',
        'team_aliases',

        # Team management
        'team_manager_assignments',

        # Players
        'players',
        'player_team_history',

        # Matches
        'matches',

        # Playoff brackets (depends on matches)
        'playoff_bracket_slots',

        # Match-related data
        'match_events',
        'match_lineups',
        'player_match_stats',

        # Invitations
        'invitations',
        'invite_requests',

        # Intentionally excluded (see EXCLUDED_TABLES):
        # - user_profiles: managed per-environment (different auth.users UUIDs)
        # - service_accounts: contains API keys, managed per-environment
        # - schema_version: internal tracking, recreated by migrations
    ]

    # Safety check: warn if database has tables not in backup list
    check_for_new_tables(tables_to_backup)

    backup_data = {
        'backup_info': {
            'timestamp': timestamp,
            'created_at': datetime.now().isoformat(),
            'version': '1.0',
            'supabase_url': url
        },
        'tables': {}
    }
    
    # Backup each table
    for table in tables_to_backup:
        data = backup_table(table)
        if data is not None:
            backup_data['tables'][table] = data
    
    # Special handling for auth.users (metadata only, no sensitive data)
    print("Backing up auth.users metadata...")
    try:
        auth_users = supabase.table('auth.users').select('id, email, created_at, last_sign_in_at').execute()
        if auth_users.data:
            print(f"  ✓ {len(auth_users.data)} user records (metadata only)")
            backup_data['tables']['auth_users_metadata'] = auth_users.data
    except Exception as e:
        print(f"  ✗ Error backing up auth users: {e}")
    
    # Save backup to file
    try:
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        print("=" * 50)
        print(f"✅ Backup completed successfully!")
        print(f"📁 File: {backup_file}")
        print(f"📊 Size: {backup_file.stat().st_size / 1024:.1f} KB")
        
        # Backup summary
        total_records = sum(len(data) for data in backup_data['tables'].values() if isinstance(data, list))
        print(f"📈 Total records: {total_records}")
        print(f"📋 Tables backed up: {len(backup_data['tables'])}")
        
        return backup_file
        
    except Exception as e:
        print(f"❌ Error saving backup file: {e}")
        return None

def list_backups():
    """List all available backups."""
    backup_dir = Path(__file__).parent.parent / 'backups'

    if not backup_dir.exists():
        print("No backups directory found.")
        return []

    # Only match timestamp-formatted backups (YYYYMMDD_HHMMSS)
    backup_files = list(backup_dir.glob("database_backup_[0-9]*.json"))
    backup_files.sort(reverse=True)  # Most recent first
    
    if not backup_files:
        print("No backup files found.")
        return []
    
    print("Available backups:")
    print("-" * 40)
    
    for i, backup_file in enumerate(backup_files):
        try:
            with open(backup_file, 'r') as f:
                data = json.load(f)
                info = data.get('backup_info', {})
                created = info.get('created_at', 'Unknown')
                total_records = sum(len(table_data) for table_data in data.get('tables', {}).values() if isinstance(table_data, list))
                
                print(f"{i+1}. {backup_file.name}")
                print(f"   📅 Created: {created}")
                print(f"   📊 Records: {total_records}")
                print(f"   💾 Size: {backup_file.stat().st_size / 1024:.1f} KB")
                print()
                
        except Exception as e:
            print(f"{i+1}. {backup_file.name} (corrupted - {e})")
    
    return backup_files

def cleanup_old_backups(keep_count: int = 10):
    """Keep only the most recent N backups."""
    backup_dir = Path(__file__).parent.parent / 'backups'

    if not backup_dir.exists():
        return

    # Only match timestamp-formatted backups (YYYYMMDD_HHMMSS)
    backup_files = list(backup_dir.glob("database_backup_[0-9]*.json"))
    backup_files.sort(reverse=True)  # Most recent first
    
    if len(backup_files) <= keep_count:
        print(f"Only {len(backup_files)} backups found, keeping all.")
        return
    
    files_to_delete = backup_files[keep_count:]
    print(f"Cleaning up {len(files_to_delete)} old backup files...")
    
    for backup_file in files_to_delete:
        try:
            backup_file.unlink()
            print(f"  ✓ Deleted {backup_file.name}")
        except Exception as e:
            print(f"  ✗ Error deleting {backup_file.name}: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database backup utility")
    parser.add_argument('--list', action='store_true', help='List available backups')
    parser.add_argument('--cleanup', type=int, metavar='N', help='Keep only N most recent backups')
    
    args = parser.parse_args()
    
    try:
        if args.list:
            list_backups()
        elif args.cleanup:
            cleanup_old_backups(args.cleanup)
        else:
            # Default: create backup
            backup_file = create_backup()
            if backup_file:
                print(f"\n💡 To restore this backup, run:")
                print(f"   python scripts/restore_database.py {backup_file.name}")
                
    except KeyboardInterrupt:
        print("\n❌ Backup cancelled by user")
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        sys.exit(1)
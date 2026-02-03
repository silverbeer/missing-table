#!/usr/bin/env python3
"""
Database restore script for MLS Next development.
Restores database from JSON backup files.
"""

import json
import os
import sys
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

def clear_table(table_name: str):
    """Clear all data from a table."""
    try:
        print(f"Clearing {table_name}...")
        
        # First, get all records to delete them by ID
        result = supabase.table(table_name).select('id').execute()
        
        if result.data:
            # Delete in batches to avoid timeout
            batch_size = 100
            total_records = len(result.data)
            
            for i in range(0, total_records, batch_size):
                batch = result.data[i:i + batch_size]
                ids = [record['id'] for record in batch]
                
                delete_result = supabase.table(table_name).delete().in_('id', ids).execute()
                print(f"  ✓ Deleted {len(ids)} records from {table_name}")
                
            print(f"  ✓ Cleared {total_records} total records from {table_name}")
        else:
            print(f"  ✓ {table_name} was already empty")
            
    except Exception as e:
        print(f"  ✗ Error clearing {table_name}: {e}")

def validate_records(table_name: str, data: list) -> list:
    """Filter out records with null values in NOT NULL columns.

    Returns the list of valid records and prints warnings for skipped ones.
    """
    # NOT NULL columns per table (excluding 'id' which is auto-generated)
    required_fields = {
        'team_match_types': ['team_id', 'match_type_id', 'age_group_id'],
        'teams': ['name'],
        'matches': ['home_team_id', 'away_team_id', 'season_id'],
        'clubs': ['name'],
        'divisions': ['name'],
        'leagues': ['name'],
    }

    fields = required_fields.get(table_name)
    if not fields:
        return data

    valid = []
    skipped = 0
    for record in data:
        missing = [f for f in fields if record.get(f) is None]
        if missing:
            skipped += 1
            record_id = record.get('id', '?')
            print(f"  ⚠ Skipping record id={record_id}: null value in {', '.join(missing)}")
        else:
            valid.append(record)

    if skipped:
        print(f"  ⚠ Filtered out {skipped} invalid record(s) from {table_name}")

    return valid


def restore_table(table_name: str, data: list):
    """Restore data to a single table."""
    if not data:
        print(f"Skipping {table_name} (no data)")
        return True

    try:
        print(f"Restoring {table_name} ({len(data)} records)...")

        # Filter out records that would violate NOT NULL constraints
        data = validate_records(table_name, data)
        if not data:
            print(f"  ⚠ No valid records to restore for {table_name}")
            return True

        # Insert in batches to avoid timeout
        batch_size = 100
        total_inserted = 0

        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]

            result = supabase.table(table_name).insert(batch).execute()

            if result.data:
                total_inserted += len(result.data)
                print(f"  ✓ Inserted batch {i//batch_size + 1}: {len(result.data)} records")
            else:
                print(f"  ⚠ Batch {i//batch_size + 1} returned no data")

        print(f"  ✅ Successfully restored {total_inserted} records to {table_name}")
        return True

    except Exception as e:
        print(f"  ❌ Error restoring {table_name}: {e}")
        return False

def reset_sequences():
    """Reset all PostgreSQL sequences to match max IDs in tables.

    This prevents 'duplicate key' errors after data restoration by ensuring
    all sequences are synchronized with the actual max IDs.
    """
    try:
        print("🔄 Resetting PostgreSQL sequences...")

        # Call the reset_all_sequences() function created in migration
        result = supabase.rpc('reset_all_sequences').execute()

        if result.data is not None:
            sequences_reset = result.data
            print(f"  ✅ Reset {sequences_reset} sequence(s)")
            return True
        else:
            print("  ⚠️ Sequence reset function returned no data")
            return True  # Don't fail restore if sequence reset has issues

    except Exception as e:
        print(f"  ⚠️ Warning: Could not reset sequences: {e}")
        print("  ℹ️  You may need to manually run: SELECT reset_all_sequences();")
        return True  # Don't fail the entire restore

def restore_from_backup(backup_file: Path, clear_existing: bool = True):
    """Restore database from a backup file."""
    
    if not backup_file.exists():
        print(f"❌ Backup file not found: {backup_file}")
        return False
    
    try:
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading backup file: {e}")
        return False
    
    # Validate backup file
    if 'backup_info' not in backup_data or 'tables' not in backup_data:
        print("❌ Invalid backup file format")
        return False
    
    backup_info = backup_data['backup_info']
    tables_data = backup_data['tables']
    
    print(f"Restoring database from backup:")
    print(f"📁 File: {backup_file.name}")
    print(f"📅 Created: {backup_info.get('created_at', 'Unknown')}")
    print(f"📋 Tables: {len(tables_data)}")
    print("=" * 50)
    
    # Define restoration order (respecting foreign key dependencies)
    # NOTE: user_profiles is EXCLUDED from restoration
    # Reason: Users and profiles are managed per-environment, not synced between dev/prod
    # - Each environment has its own auth.users with different UUIDs
    # - Restoring user_profiles from backup will cause UUID mismatches with auth.users
    # - See docs/FOREIGN_KEY_DECISION.md for details
    # - Use backend/manage_users.py to create users in each environment
    # Restoration order respects FK dependencies for INSERT
    # Clearing happens in REVERSE order to respect FK dependencies for DELETE
    restoration_order = [
        # 1. Reference data first (no dependencies)
        'age_groups',
        'leagues',  # leagues before divisions
        'divisions',
        'match_types',
        'seasons',

        # 2. Clubs (before teams - teams have club_id FK)
        'clubs',

        # 3. Teams (depend on clubs, divisions, age_groups)
        'teams',
        'team_mappings',
        'team_match_types',
        'team_aliases',

        # 4. Team management
        'team_manager_assignments',

        # 5. Players (may depend on teams)
        'players',
        'player_team_history',

        # 6. Matches (depend on teams, seasons, etc.)
        'matches',

        # 7. Tables that depend on matches/teams/clubs/players
        # These are cleared FIRST (reverse order) before their parents
        'match_events',
        'match_lineups',
        'player_match_stats',
        'invitations',      # depends on clubs, teams, players
        'invite_requests',  # depends on auth.users

        # Excluded - manage separately per environment:
        # - user_profiles (different auth.users UUIDs per env)
        # - service_accounts (contains API keys)
    ]
    
    success_count = 0
    total_tables = len([table for table in restoration_order if table in tables_data])
    
    # Clear existing data if requested
    if clear_existing:
        print("🧹 Clearing existing data...")
        # Clear in reverse order to respect foreign keys
        # Clear ALL tables in restoration_order (not just ones in backup)
        # This ensures FK dependencies are cleared even if table isn't being restored
        for table in reversed(restoration_order):
            clear_table(table)
        print()
    
    # Restore tables in order
    print("📥 Restoring data...")
    for table in restoration_order:
        if table in tables_data:
            if restore_table(table, tables_data[table]):
                success_count += 1
        else:
            print(f"Skipping {table} (not in backup)")
    
    print("=" * 50)

    # Reset all sequences after data restoration
    # This is CRITICAL to prevent "duplicate key" errors when inserting new records
    print()
    reset_sequences()
    print()

    if success_count == total_tables:
        print(f"✅ Restoration completed successfully!")
        print(f"📊 Restored {success_count}/{total_tables} tables")

        # Summary of restored data
        total_records = 0
        for table, data in tables_data.items():
            if isinstance(data, list) and table != 'auth_users_metadata':
                total_records += len(data)

        print(f"📈 Total records restored: {total_records}")
        return True
    else:
        print(f"⚠️ Restoration completed with errors")
        print(f"📊 Restored {success_count}/{total_tables} tables")
        return False

def list_available_backups():
    """List available backup files."""
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
    
    print("Available backup files:")
    print("-" * 40)
    
    for i, backup_file in enumerate(backup_files):
        try:
            with open(backup_file, 'r') as f:
                data = json.load(f)
                info = data.get('backup_info', {})
                created = info.get('created_at', 'Unknown')
                
                print(f"{i+1}. {backup_file.name}")
                print(f"   📅 {created}")
                print(f"   💾 {backup_file.stat().st_size / 1024:.1f} KB")
                
        except Exception as e:
            print(f"{i+1}. {backup_file.name} (corrupted)")
    
    return backup_files

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database restore utility")
    parser.add_argument('backup_file', nargs='?', help='Backup file to restore from')
    parser.add_argument('--list', action='store_true', help='List available backup files')
    parser.add_argument('--no-clear', action='store_true', help='Don\'t clear existing data before restore')
    parser.add_argument('--latest', action='store_true', help='Restore from the most recent backup')
    
    args = parser.parse_args()
    
    try:
        if args.list:
            list_available_backups()
            
        elif args.latest:
            backup_dir = Path(__file__).parent.parent / 'backups'
            # Only match timestamp-formatted backups (YYYYMMDD_HHMMSS)
            # This avoids picking up old manually-named files like database_backup_prod_mapped.json
            backup_files = list(backup_dir.glob("database_backup_[0-9]*.json"))

            if not backup_files:
                print("❌ No backup files found")
                sys.exit(1)

            # Get most recent backup by sorting filenames (timestamps sort correctly)
            backup_files.sort(reverse=True)
            latest_backup = backup_files[0]
            
            print(f"Using latest backup: {latest_backup.name}")
            clear_existing = not args.no_clear
            restore_from_backup(latest_backup, clear_existing)
            
        elif args.backup_file:
            backup_dir = Path(__file__).parent.parent / 'backups'
            
            # Handle both full path and just filename
            if '/' in args.backup_file:
                backup_file = Path(args.backup_file)
            else:
                backup_file = backup_dir / args.backup_file
            
            clear_existing = not args.no_clear
            restore_from_backup(backup_file, clear_existing)
            
        else:
            print("❌ Please specify a backup file or use --list to see available backups")
            print("Usage examples:")
            print("  python scripts/restore_database.py --list")
            print("  python scripts/restore_database.py --latest")
            print("  python scripts/restore_database.py database_backup_20231220_143022.json")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n❌ Restore cancelled by user")
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        sys.exit(1)
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

def restore_table(table_name: str, data: list):
    """Restore data to a single table."""
    if not data:
        print(f"Skipping {table_name} (no data)")
        return True
        
    try:
        print(f"Restoring {table_name} ({len(data)} records)...")
        
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
    restoration_order = [
        # Reference data first (no dependencies)
        'age_groups',
        'divisions',
        'match_types',  # Updated from game_types
        'seasons',

        # Teams (depend on divisions, age_groups)
        'teams',
        'team_mappings',
        'team_match_types',  # Updated from team_game_types

        # User profiles (special handling - skip auth.users)
        'user_profiles',

        # Matches (depend on teams, seasons, etc.) - Updated from games
        'matches',
    ]
    
    success_count = 0
    total_tables = len([table for table in restoration_order if table in tables_data])
    
    # Clear existing data if requested
    if clear_existing:
        print("🧹 Clearing existing data...")
        # Clear in reverse order to respect foreign keys
        for table in reversed(restoration_order):
            if table in tables_data:
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
    
    backup_files = list(backup_dir.glob("database_backup_*.json"))
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
            backup_files = list(backup_dir.glob("database_backup_*.json"))
            
            if not backup_files:
                print("❌ No backup files found")
                sys.exit(1)
            
            # Get most recent backup
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
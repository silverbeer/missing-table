#!/usr/bin/env python3
"""
Database restore script for MLS Next development.
Restores database from JSON backup files.
"""

import gzip
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

def get_local_user_profile_ids() -> set:
    """Fetch all user_profile IDs that exist in the local database."""
    try:
        result = supabase.table("user_profiles").select("id").execute()
        return {r["id"] for r in (result.data or [])}
    except Exception as e:
        print(f"  ⚠ Could not fetch local user_profiles: {e}")
        return set()


# UUID columns per table that reference user_profiles.
# nullable=True  → safe to null out when the UUID isn't present locally
# nullable=False → record must be dropped entirely (column is NOT NULL)
USER_PROFILE_FK_COLUMNS: dict[str, list[tuple[str, bool]]] = {
    'players':                  [('created_by', True), ('user_profile_id', True)],
    'player_team_history':      [('player_id', False)],   # NOT NULL — drop record
    'match_lineups':            [('created_by', True), ('updated_by', True)],
    'match_events':             [('created_by', True)],
    'player_match_stats':       [('player_id', False)],   # NOT NULL — drop record
    'team_manager_assignments': [('user_id', False)],     # NOT NULL — drop record
    'invitations':              [('created_by', True), ('claimed_by', True)],
    'invite_requests':          [('user_id', False)],     # NOT NULL — drop record
}


def sanitize_user_profile_refs(table_name: str, data: list, local_ids: set) -> list:
    """Null out or drop records with user_profile FK refs not present locally.

    Prod and local have different auth.users UUIDs. For nullable FK columns we
    set the value to None. For NOT NULL FK columns the record must be dropped —
    inserting NULL would violate the constraint.
    """
    columns = USER_PROFILE_FK_COLUMNS.get(table_name)
    if not columns:
        return data

    kept = []
    nulled_count = 0
    dropped_count = 0

    for record in data:
        drop = False
        for col, nullable in columns:
            val = record.get(col)
            if val and val not in local_ids:
                if nullable:
                    record[col] = None
                    nulled_count += 1
                else:
                    drop = True
                    break
        if drop:
            dropped_count += 1
        else:
            kept.append(record)

    if nulled_count:
        print(f"  ℹ️  Cleared {nulled_count} nullable user_profile reference(s) not found locally")
    if dropped_count:
        print(f"  ℹ️  Dropped {dropped_count} record(s) with non-nullable user_profile ref not found locally")

    return kept


def clear_table(table_name: str):
    """Clear all data from a table, paginating to handle >1000 rows."""
    try:
        print(f"Clearing {table_name}...")
        total_deleted = 0
        page_size = 1000

        while True:
            # Fetch up to page_size IDs at a time (Supabase caps at 1000 per request)
            result = supabase.table(table_name).select('id').limit(page_size).execute()
            if not result.data:
                break

            ids = [record['id'] for record in result.data]
            # Delete in sub-batches to avoid URI length limits
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                chunk = ids[i:i + batch_size]
                supabase.table(table_name).delete().in_('id', chunk).execute()
                total_deleted += len(chunk)
                print(f"  ✓ Deleted {len(chunk)} records from {table_name}")

            if len(result.data) < page_size:
                break  # no more rows

        if total_deleted:
            print(f"  ✓ Cleared {total_deleted} total records from {table_name}")
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


def restore_table(table_name: str, data: list, local_profile_ids: set | None = None):
    """Restore data to a single table."""
    if not data:
        print(f"Skipping {table_name} (no data)")
        return True

    try:
        print(f"Restoring {table_name} ({len(data)} records)...")

        # Filter out records that would violate NOT NULL constraints
        data = validate_records(table_name, data)

        # Null out user_profile FK references that don't exist locally
        if local_profile_ids is not None:
            data = sanitize_user_profile_refs(table_name, data, local_profile_ids)
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
        if backup_file.suffix == '.gz':
            with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
                backup_data = json.load(f)
        else:
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

        # 6. Tournaments (matches may reference tournaments via tournament_id FK)
        'tournaments',
        'tournament_age_groups',

        # 7. Matches (depend on teams, seasons, tournaments)
        'matches',

        # 8. Playoff brackets (depend on matches)
        'playoff_bracket_slots',

        # 9. Tables that depend on matches/teams/clubs/players
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
    
    # Fetch local user_profile IDs so we can sanitize FK references
    print("🔍 Fetching local user_profile IDs for FK sanitization...")
    local_profile_ids = get_local_user_profile_ids()
    print(f"  Found {len(local_profile_ids)} local user profile(s)")
    print()

    # Restore tables in order
    print("📥 Restoring data...")
    for table in restoration_order:
        if table in tables_data:
            if restore_table(table, tables_data[table], local_profile_ids):
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
    
    # Default backup dir matches backup_database.py default: ~/backups/missing-table
    DEFAULT_BACKUP_DIR = Path.home() / 'backups' / 'missing-table'

    parser = argparse.ArgumentParser(description="Database restore utility")
    parser.add_argument('backup_file', nargs='?', help='Backup file to restore from')
    parser.add_argument('--list', action='store_true', help='List available backup files')
    parser.add_argument('--no-clear', action='store_true', help="Don't clear existing data before restore")
    parser.add_argument('--latest', action='store_true', help='Restore from the most recent backup')
    parser.add_argument(
        '--backup-dir',
        type=Path,
        default=DEFAULT_BACKUP_DIR,
        help=f'Directory containing backup files (default: {DEFAULT_BACKUP_DIR})',
    )

    args = parser.parse_args()
    backup_dir: Path = args.backup_dir

    def find_latest_backup(directory: Path) -> Path | None:
        """Find the most recent timestamped backup (.json.gz or .json)."""
        candidates = sorted(
            list(directory.glob("database_backup_[0-9]*.json.gz")) +
            list(directory.glob("database_backup_[0-9]*.json")),
            reverse=True,
        )
        return candidates[0] if candidates else None

    try:
        if args.list:
            list_available_backups()

        elif args.latest:
            latest_backup = find_latest_backup(backup_dir)
            if not latest_backup:
                print(f"❌ No backup files found in {backup_dir}")
                sys.exit(1)
            print(f"Using latest backup: {latest_backup.name}")
            clear_existing = not args.no_clear
            restore_from_backup(latest_backup, clear_existing)

        elif args.backup_file:
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
            print(f"  python scripts/restore_database.py --backup-dir {DEFAULT_BACKUP_DIR} --latest")
            print("  python scripts/restore_database.py database_backup_20231220_143022.json.gz")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n❌ Restore cancelled by user")
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        sys.exit(1)
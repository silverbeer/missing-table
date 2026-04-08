#!/usr/bin/env python3
"""
Comprehensive database backup script for MLS Next development.
Creates JSON backups of all tables with timestamp.
"""

import gzip
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
    # FreeRADIUS tables were dropped in migration 20260404201640_drop_radius_tables.sql
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
    """Backup a single table to JSON, paginating to fetch all rows."""
    try:
        print(f"Backing up {table_name}...")
        all_data = []
        page_size = 1000
        offset = 0

        while True:
            result = (
                supabase.table(table_name)
                .select(select_columns)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            if not result.data:
                break
            all_data.extend(result.data)
            if len(result.data) < page_size:
                break
            offset += page_size

        print(f"  ✓ {len(all_data)} records")
        return all_data

    except Exception as e:
        print(f"  ✗ Error backing up {table_name}: {e}")
        return None

def create_backup(backup_dir: Path | None = None):
    """Create a complete database backup."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if backup_dir is None:
        backup_dir = Path(__file__).parent.parent / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    backup_file = backup_dir / f"database_backup_{timestamp}.json.gz"
    
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

        # Tournaments (depends on seasons, age_groups, leagues)
        'tournaments',
        'tournament_age_groups',

        # Audit and activity logs
        'audit_events',
        'audit_teams',
        'login_events',

        # Invitations
        'invitations',
        'invite_requests',

        # Channel access requests (Telegram/Discord)
        'channel_access_requests',

        # Intentionally excluded (see EXCLUDED_TABLES):
        # - user_profiles: managed per-environment (different auth.users UUIDs)
        # - service_accounts: contains API keys, managed per-environment
        # - schema_version: internal tracking, recreated by migrations
        # - rad* tables: FreeRADIUS protocol tables, not application data
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
    
    # Special handling for auth.users via Admin API (not accessible via REST)
    print("Backing up auth.users...")
    try:
        all_users = []
        page = 1
        per_page = 1000
        while True:
            response = supabase.auth.admin.list_users(page=page, per_page=per_page)
            # SDK returns a list of User objects
            users = response if isinstance(response, list) else getattr(response, 'users', [])
            if not users:
                break
            for u in users:
                # Serialize to dict, keeping only non-sensitive identity fields
                all_users.append({
                    'id': str(u.id),
                    'email': u.email,
                    'role': getattr(u, 'role', None),
                    'email_confirmed_at': str(u.email_confirmed_at) if u.email_confirmed_at else None,
                    'created_at': str(u.created_at) if u.created_at else None,
                    'last_sign_in_at': str(u.last_sign_in_at) if u.last_sign_in_at else None,
                    'user_metadata': getattr(u, 'user_metadata', {}),
                    'app_metadata': getattr(u, 'app_metadata', {}),
                })
            if len(users) < per_page:
                break
            page += 1
        print(f"  ✓ {len(all_users)} auth users")
        backup_data['tables']['auth_users'] = all_users
    except Exception as e:
        print(f"  ✗ Error backing up auth.users: {e}")
    
    # Save backup to file (gzip compressed)
    try:
        with gzip.open(backup_file, 'wt', encoding='utf-8') as f:
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
    backup_files = list(backup_dir.glob("database_backup_[0-9]*.json.gz"))
    backup_files.sort(reverse=True)  # Most recent first
    
    if not backup_files:
        print("No backup files found.")
        return []
    
    print("Available backups:")
    print("-" * 40)
    
    for i, backup_file in enumerate(backup_files):
        try:
            with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
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

def cleanup_old_backups(
    backup_dir: Path | None = None,
    keep_days: int = 30,
    keep_monthly: bool = True,
):
    """
    Retention policy:
      - Keep all backups from the last `keep_days` days.
      - For older backups, keep one per calendar month (the most recent of that month).
      - Delete everything else.

    Both `keep_days` and `keep_monthly` are configurable.
    """
    import re
    from datetime import timedelta

    if backup_dir is None:
        backup_dir = Path(__file__).parent.parent / 'backups'

    if not backup_dir.exists():
        return

    backup_files = sorted(
        backup_dir.glob("database_backup_[0-9]*.json.gz"),
        reverse=True,  # most recent first
    )

    if not backup_files:
        print("No backups to clean up.")
        return

    cutoff = datetime.now() - timedelta(days=keep_days)
    monthly_kept: dict[str, Path] = {}  # "YYYY-MM" -> file to keep
    to_delete: list[Path] = []

    for f in backup_files:
        m = re.match(r'database_backup_(\d{4})(\d{2})(\d{2})_', f.name)
        if not m:
            continue
        file_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))

        if file_date >= cutoff:
            continue  # within daily retention window — always keep

        if keep_monthly:
            month_key = f"{m.group(1)}-{m.group(2)}"
            if month_key not in monthly_kept:
                monthly_kept[month_key] = f  # keep most recent of this month
                continue

        to_delete.append(f)

    if not to_delete:
        print(f"No backups to delete (keeping {len(backup_files)} files).")
        return

    print(f"Cleaning up {len(to_delete)} backup(s) outside retention policy...")
    for f in to_delete:
        try:
            f.unlink()
            print(f"  ✓ Deleted {f.name}")
        except Exception as e:
            print(f"  ✗ Error deleting {f.name}: {e}")

    kept = len(backup_files) - len(to_delete)
    print(f"Retention: {kept} backup(s) kept ({keep_days}-day daily + {'monthly archive' if keep_monthly else 'no monthly archive'})")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database backup utility")
    parser.add_argument('--list', action='store_true', help='List available backups')
    parser.add_argument('--cleanup', action='store_true', help='Run retention cleanup')
    parser.add_argument(
        '--backup-dir',
        type=Path,
        default=None,
        help='Directory to store backups (default: ~/backups/missing-table)',
    )
    parser.add_argument(
        '--keep-days',
        type=int,
        default=30,
        help='Number of days to keep daily backups (default: 30)',
    )
    parser.add_argument(
        '--no-monthly',
        action='store_true',
        help='Disable monthly archive retention',
    )

    args = parser.parse_args()

    # Resolve backup directory
    backup_dir = args.backup_dir or Path.home() / 'backups' / 'missing-table'

    try:
        if args.list:
            list_backups()
        elif args.cleanup:
            cleanup_old_backups(
                backup_dir=backup_dir,
                keep_days=args.keep_days,
                keep_monthly=not args.no_monthly,
            )
        else:
            # Default: create backup then clean up
            backup_file = create_backup(backup_dir=backup_dir)
            if backup_file:
                print(f"\n💡 To restore this backup, run:")
                print(f"   python scripts/restore_database.py {backup_file.name}")
                print()
                cleanup_old_backups(
                    backup_dir=backup_dir,
                    keep_days=args.keep_days,
                    keep_monthly=not args.no_monthly,
                )

    except KeyboardInterrupt:
        print("\n❌ Backup cancelled by user")
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        sys.exit(1)
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

from dotenv import load_dotenv

from supabase import Client, create_client

# Add backend to path for shared modules
backend_path = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_path))
sys.path.insert(0, str(Path(__file__).parent))

# One definition of "can this backup be restored from", shared with the backup
# script rather than copied (SB-1072). Importing it is safe: backup_database
# does nothing at import but define constants.
from backup_database import usability_problems

# Load environment variables based on APP_ENV
app_env = os.getenv("APP_ENV", "local")
env_file = f".env.{app_env}"
env_path = backend_path / env_file

if not env_path.exists():
    # Fallback to .env if specific env file doesn't exist
    env_path = backend_path / ".env"

load_dotenv(env_path, override=True)
print(f"✓ Loaded environment: {app_env}")

# Initialize Supabase client
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

if not url or not key:
    raise Exception(
        "Missing required environment variables: SUPABASE_URL and SUPABASE_SERVICE_KEY"
    )

supabase: Client = create_client(url, key)
db_url = os.getenv("DATABASE_URL")


def get_local_user_profile_ids() -> set:
    """Fetch all user_profile IDs that exist in the local database."""
    try:
        result = supabase.table("user_profiles").select("id").execute()
        return {r["id"] for r in (result.data or [])}
    except Exception as e:
        print(f"  ⚠ Could not fetch local user_profiles: {e}")
        return set()


# Rows that mean nothing without their user, whatever the column allows.
# A manager assignment with no manager is not an assignment; everything else is
# decided by the column's own nullability.
DROP_EVEN_IF_NULLABLE = {("team_manager_assignments", "user_id")}


def user_reference_columns(
    catalog_rows, overrides: set[tuple[str, str]] = DROP_EVEN_IF_NULLABLE
) -> dict[str, list[tuple[str, bool]]]:
    """{table: [(column, null_it_out)]} from foreign keys to user_profiles/auth.users.

    True  → null the value out when that user is absent here
    False → drop the record (NOT NULL, or listed in `overrides`)

    Derived rather than written down (SB-1076). The hand-kept map drifted from
    the schema: it named invitation columns that did not exist, missed
    matches.created_by/updated_by, and treated player_match_stats.player_id —
    an integer reference to players — as a user uuid, so a restore silently
    dropped every goal and assist (SB-1071).
    """
    columns: dict[str, list[tuple[str, bool]]] = {}
    for table, column, nullable in catalog_rows:
        null_it_out = bool(nullable) and (table, column) not in overrides
        columns.setdefault(table, []).append((column, null_it_out))
    return {table: sorted(cols) for table, cols in columns.items()}


def read_user_reference_catalog(database_url: str):
    """Foreign keys to user_profiles/auth.users, as (table, column, nullable).

    Raises rather than returning a guess: restoring with the wrong idea of which
    columns reference a user is how rows get dropped or rejected in silence.
    """
    import psycopg2

    query = """
        SELECT con.conrelid::regclass::text AS table_name,
               att.attname AS column_name,
               NOT att.attnotnull AS nullable
          FROM pg_constraint con
          JOIN unnest(con.conkey) AS k(attnum) ON true
          JOIN pg_attribute att
            ON att.attrelid = con.conrelid AND att.attnum = k.attnum
         WHERE con.contype = 'f'
           AND con.connamespace = 'public'::regnamespace
           AND con.confrelid IN ('public.user_profiles'::regclass, 'auth.users'::regclass)
    """
    with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(query)
        return [(table, column, nullable) for table, column, nullable in cur.fetchall()]


# Restoration order respects FK dependencies for INSERT; clearing runs in
# REVERSE order to respect them for DELETE.
#
# NOTE: user_profiles is not backed up or restored. Users and profiles are
# managed per environment (different auth.users UUIDs); see
# docs/FOREIGN_KEY_DECISION.md and backend/manage_users.py.
#
# backend/tests/unit/test_backup_coverage.py fails CI when a backed-up table is
# in neither RESTORATION_ORDER nor RESTORE_SKIPPED.
RESTORATION_ORDER = [
    # 1. Reference data first (no dependencies)
    "age_groups",
    # match_types before leagues: `leagues.match_type_id` references it. The two
    # were the other way round, which stayed invisible for as long as every
    # league had a null match_type_id. The first league that set one (Flex)
    # failed to insert, and because clearing runs in reverse, match_types could
    # not be emptied either while those leagues still pointed at it — so the
    # seeded rows survived and the backup's collided with them, taking leagues,
    # divisions and division_age_groups down with them (SB-1104).
    "match_types",
    "leagues",  # leagues before divisions
    "divisions",
    "seasons",
    "division_age_groups",  # divisions, age_groups, seasons
    # 2. Clubs (before teams - teams have club_id FK)
    "clubs",
    "club_notification_channels",  # clubs
    # 3. Teams (depend on clubs, divisions, age_groups)
    "teams",
    "team_mappings",
    "team_match_types",
    "team_aliases",
    "qop_snapshots",  # divisions, age_groups
    "qop_rankings",  # qop_snapshots, teams
    # 4. Team management
    "team_manager_assignments",
    # 5. Players (may depend on teams)
    "players",
    "player_team_history",
    # 6. Tournaments (matches may reference tournaments via tournament_id FK)
    "tournaments",
    "tournament_age_groups",
    # 7. Matches (depend on teams, seasons, tournaments)
    "matches",
    # 8. Playoff brackets (depend on matches)
    "playoff_bracket_slots",
    # 9. Tables that depend on matches/teams/clubs/players
    "match_of_the_week",
    "match_events",
    "match_lineups",
    "player_match_stats",
    "invitations",  # depends on clubs, teams, players
    "invite_requests",  # depends on auth.users
    "channel_access_requests",  # teams, user_profiles
    # 10. Users' own data — rows for users absent here are dropped
    "user_team_follows",  # teams
    "user_bracket_follows",  # tournaments, age_groups
    "user_notification_preferences",
    # 11. Support inbox
    "email_threads",
    "email_messages",  # email_threads
    # 12. Audit and activity logs (no foreign keys)
    "audit_events",
    "audit_teams",
    "login_events",
    "admin_user_audit_log",
]

# In the backup, deliberately never restored — each with its reason.
RESTORE_SKIPPED = {
    "push_subscriptions": (
        "device push credentials. The prod user sync keeps user ids, so restoring "
        "them locally would let a local server push to real phones. Backed up for "
        "production recovery only; restore by hand."
    ),
    "auth_users": "identity snapshot from the Admin API; users are managed per environment",
}

# Tables without an `id` column. PostgREST refuses an unfiltered DELETE, and
# clear_table() otherwise pages through ids — which failed for these, printed a
# ✗ and carried on, so the restore then hit duplicate keys (SB-1071). Each is
# cleared by filtering on a NOT NULL key column instead.
CLEAR_BY_COLUMN = {
    "tournament_age_groups": "tournament_id",
    "user_team_follows": "user_id",
    "user_bracket_follows": "user_id",
    "user_notification_preferences": "user_id",
}


def sanitize_user_profile_refs(
    table_name: str,
    data: list,
    local_ids: set,
    user_columns: dict[str, list[tuple[str, bool]]],
) -> list:
    """Null out or drop records with user references not present in the target.

    Prod and local have different auth.users UUIDs. Nullable columns are set to
    None; the record is dropped when the column is NOT NULL, or when the row
    means nothing without its user. `user_columns` comes from the target
    database's own catalog (SB-1076), never from a list kept by hand.
    """
    columns = user_columns.get(table_name)
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
        print(
            f"  ℹ️  Cleared {nulled_count} nullable user_profile reference(s) not found locally"
        )
    if dropped_count:
        print(
            f"  ℹ️  Dropped {dropped_count} record(s) with non-nullable user_profile ref not found locally"
        )

    return kept


def clear_table(table_name: str):
    """Clear all data from a table, paginating to handle >1000 rows."""
    key_column = CLEAR_BY_COLUMN.get(table_name)
    if key_column:
        try:
            print(f"Clearing {table_name}...")
            result = (
                supabase.table(table_name)
                .delete()
                .filter(key_column, "not.is", "null")
                .execute()
            )
            print(f"  ✓ Cleared {len(result.data or [])} records from {table_name}")
        except Exception as e:
            print(f"  ✗ Error clearing {table_name}: {e}")
        return

    try:
        print(f"Clearing {table_name}...")
        total_deleted = 0
        page_size = 1000

        while True:
            # Fetch up to page_size IDs at a time (Supabase caps at 1000 per request)
            result = supabase.table(table_name).select("id").limit(page_size).execute()
            if not result.data:
                break

            ids = [record["id"] for record in result.data]
            # Delete in sub-batches to avoid URI length limits
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                chunk = ids[i : i + batch_size]
                supabase.table(table_name).delete().in_("id", chunk).execute()
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
        "team_match_types": ["team_id", "match_type_id", "age_group_id"],
        "teams": ["name"],
        # age_group_id and match_type_id are NOT NULL locally but nullable in
        # prod (SB-916), so a prod row missing one would be rejected by the
        # database rather than caught here.
        "matches": [
            "home_team_id",
            "away_team_id",
            "season_id",
            "age_group_id",
            "match_type_id",
        ],
        "clubs": ["name"],
        "divisions": ["name"],
        "leagues": ["name"],
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
            record_id = record.get("id", "?")
            print(
                f"  ⚠ Skipping record id={record_id}: null value in {', '.join(missing)}"
            )
        else:
            valid.append(record)

    if skipped:
        print(f"  ⚠ Filtered out {skipped} invalid record(s) from {table_name}")

    return valid


class TableResult:
    """What actually happened to one table (SB-917).

    The old code returned a bare bool and counted the backup file's records as
    though they were rows that landed. Both halves of that lied: a rejected
    batch abandoned every later batch in the table, and the summary still
    reported the file's totals.
    """

    def __init__(self, table_name: str, attempted: int):
        self.table_name = table_name
        self.attempted = attempted
        self.inserted = 0
        self.failures: list[tuple] = []  # (record_id, error)
        self.skipped_invalid = 0

    @property
    def ok(self) -> bool:
        return not self.failures

    def __bool__(self) -> bool:
        return self.ok


def _insert_rows_individually(table_name: str, batch: list, result: TableResult):
    """Retry a failed batch one row at a time.

    PostgREST rejects a whole batch when any row in it is bad, so a single
    unusable record used to cost the other 99 — and every batch after it. One
    bad row should cost one row, and should be named.
    """
    for record in batch:
        try:
            inserted = supabase.table(table_name).insert(record).execute()
            result.inserted += len(inserted.data or [])
        except Exception as row_error:
            record_id = record.get("id", "?")
            result.failures.append((record_id, str(row_error)))
            print(f"  ❌ {table_name} id={record_id}: {row_error}")


def restore_table(
    table_name: str,
    data: list,
    local_profile_ids: set | None = None,
    user_columns: dict[str, list[tuple[str, bool]]] | None = None,
) -> TableResult:
    """Restore data to a single table."""
    result = TableResult(table_name, len(data))

    if not data:
        print(f"Skipping {table_name} (no data)")
        return result

    print(f"Restoring {table_name} ({len(data)} records)...")

    # Filter out records that would violate NOT NULL constraints
    validated = validate_records(table_name, data)
    result.skipped_invalid = len(data) - len(validated)
    data = validated

    # Null out user references that don't exist in the target database
    if local_profile_ids is not None and user_columns is not None:
        data = sanitize_user_profile_refs(
            table_name, data, local_profile_ids, user_columns
        )
    if not data:
        print(f"  ⚠ No valid records to restore for {table_name}")
        return result

    # Insert in batches to avoid timeout
    batch_size = 100

    for i in range(0, len(data), batch_size):
        batch = data[i : i + batch_size]
        batch_number = i // batch_size + 1

        try:
            inserted = supabase.table(table_name).insert(batch).execute()
            count = len(inserted.data or [])
            result.inserted += count
            if count:
                print(f"  ✓ Inserted batch {batch_number}: {count} records")
            else:
                print(f"  ⚠ Batch {batch_number} returned no data")
        except Exception as batch_error:
            # Do NOT abandon the table. Find the row (or rows) at fault, keep
            # the rest, and carry on into the following batches.
            print(
                f"  ⚠ Batch {batch_number} failed ({batch_error}); retrying row by row"
            )
            _insert_rows_individually(table_name, batch, result)

    if result.ok:
        print(
            f"  ✅ Successfully restored {result.inserted}/{result.attempted} records to {table_name}"
        )
    else:
        print(
            f"  ❌ Restored {result.inserted}/{result.attempted} records to {table_name}"
            f" — {len(result.failures)} rejected"
        )
    return result


def reset_sequences():
    """Reset all PostgreSQL sequences to match max IDs in tables.

    This prevents 'duplicate key' errors after data restoration by ensuring
    all sequences are synchronized with the actual max IDs.
    """
    try:
        print("🔄 Resetting PostgreSQL sequences...")

        # Call the reset_all_sequences() function created in migration
        result = supabase.rpc("reset_all_sequences").execute()

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


def read_backup(backup_file: Path) -> dict | None:
    """A backup file's contents, or None with the reason printed."""
    if not backup_file.exists():
        print(f"❌ Backup file not found: {backup_file}")
        return None

    try:
        opener = gzip.open if backup_file.suffix == ".gz" else open
        with opener(backup_file, "rt", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading backup file: {e}")
        return None

    if not isinstance(data, dict) or "backup_info" not in data or "tables" not in data:
        print("❌ Invalid backup file format")
        return None
    return data


def restore_from_backup(backup_file: Path, clear_existing: bool = True):
    """Restore database from a backup file."""

    backup_data = read_backup(backup_file)
    if backup_data is None:
        return False

    # Refuse before touching anything. A restore clears tables first, so an
    # empty or corrupt backup would empty the database and put nothing back —
    # which is what the 206-byte backups of 2026-09-14 would have done
    # (SB-1072). Judged on usability alone, never on today's table list: a
    # backup taken before a table existed is still a good backup of its day.
    problems = usability_problems(backup_data)
    if problems:
        print(
            f"❌ Refusing to restore from {backup_file.name}: it cannot be restored from."
        )
        for problem in problems:
            print(f"   - {problem}")
        print("   Nothing was cleared. Pick another backup:")
        print("     uv run python ../scripts/restore_database.py --list")
        return False

    backup_info = backup_data["backup_info"]
    tables_data = backup_data["tables"]

    print("Restoring database from backup:")
    print(f"📁 File: {backup_file.name}")
    print(f"📅 Created: {backup_info.get('created_at', 'Unknown')}")
    print(f"📋 Tables: {len(tables_data)}")
    print("=" * 50)

    restoration_order = RESTORATION_ORDER

    success_count = 0
    total_tables = len([table for table in restoration_order if table in tables_data])

    # Which columns reference a user, according to this database (SB-1076).
    print("🔍 Reading user references from the database catalog...")
    if not db_url:
        print("❌ DATABASE_URL is not set, so which columns reference a user cannot be")
        print(
            f"   read from the database. Set it in backend/.env.{app_env} and try again."
        )
        return False
    try:
        user_columns = user_reference_columns(read_user_reference_catalog(db_url))
    except Exception as e:
        print(f"❌ Could not read the database catalog: {e}")
        print("   Refusing to guess which columns reference a user.")
        return False
    print(f"  Found user references in {len(user_columns)} table(s)")

    # Clear existing data if requested
    if clear_existing:
        print("🧹 Clearing existing data...")
        # Only what this backup can put back. Clearing every table in the order
        # emptied tables the backup did not contain — an older backup, taken
        # before a table existed, silently wiped it (SB-1072). Reverse order
        # still puts children before parents.
        untouched = [t for t in restoration_order if t not in tables_data]
        for table in reversed(restoration_order):
            if table in tables_data:
                clear_table(table)
        if untouched:
            print(f"  ℹ️  Left alone (not in this backup): {', '.join(untouched)}")
        print()

    # Fetch local user_profile IDs so we can sanitize those references
    print("🔍 Fetching local user_profile IDs for FK sanitization...")
    local_profile_ids = get_local_user_profile_ids()
    print(f"  Found {len(local_profile_ids)} local user profile(s)")
    print()

    # Restore tables in order
    print("📥 Restoring data...")
    results = []
    for table in restoration_order:
        if table in tables_data:
            result = restore_table(
                table, tables_data[table], local_profile_ids, user_columns
            )
            results.append(result)
            if result.ok:
                success_count += 1
        else:
            print(f"Skipping {table} (not in backup)")

    for table in tables_data:
        if table in RESTORE_SKIPPED:
            print(f"Not restoring {table}: {RESTORE_SKIPPED[table]}")
        elif table not in restoration_order:
            print(
                f"⚠️  {table} is in the backup but not in RESTORATION_ORDER; not restored"
            )

    print("=" * 50)

    # Reset all sequences after data restoration
    # This is CRITICAL to prevent "duplicate key" errors when inserting new records
    print()
    reset_sequences()
    print()

    # Counts come from rows that actually landed, not from the backup file —
    # the old summary agreed with itself no matter what happened (SB-917).
    inserted = sum(r.inserted for r in results)
    attempted = sum(r.attempted for r in results)
    rejected = [(r.table_name, rid, err) for r in results for rid, err in r.failures]
    skipped_invalid = sum(r.skipped_invalid for r in results)

    if success_count == total_tables:
        print("✅ Restoration completed successfully!")
        print(f"📊 Restored {success_count}/{total_tables} tables")
        print(f"📈 Records inserted: {inserted}/{attempted}")
        if skipped_invalid:
            print(f"⚠️  Skipped {skipped_invalid} record(s) failing a NOT NULL guard")
        return True

    print("⚠️ Restoration completed with errors")
    print(f"📊 Restored {success_count}/{total_tables} tables")
    print(f"📈 Records inserted: {inserted}/{attempted}")
    print(f"❌ Rejected {len(rejected)} record(s):")
    for table_name, record_id, err in rejected[:20]:
        print(f"   {table_name} id={record_id}: {err}")
    if len(rejected) > 20:
        print(f"   … and {len(rejected) - 20} more")
    return False


# Matches backup_database.py's default.
DEFAULT_BACKUP_DIR = Path.home() / "backups" / "missing-table"


def find_latest_backup(directory: Path) -> Path | None:
    """Find the most recent timestamped backup (.json.gz or .json)."""
    candidates = sorted(
        list(directory.glob("database_backup_[0-9]*.json.gz"))
        + list(directory.glob("database_backup_[0-9]*.json")),
        reverse=True,
    )
    return candidates[0] if candidates else None


def find_latest_usable_backup(directory: Path) -> Path | None:
    """The most recent backup that can be restored from, saying what it skipped.

    `--latest` used to take the newest file whatever it held, so one failed
    backup at the top of the list stood between a restore and the last good
    copy underneath it (SB-1072).
    """
    candidates = sorted(
        list(directory.glob("database_backup_[0-9]*.json.gz"))
        + list(directory.glob("database_backup_[0-9]*.json")),
        reverse=True,
    )
    for candidate in candidates:
        try:
            opener = gzip.open if candidate.suffix == ".gz" else open
            with opener(candidate, "rt", encoding="utf-8") as f:
                data = json.load(f)
            problems = (
                usability_problems(data)
                if isinstance(data, dict)
                else ["not a backup object"]
            )
        except Exception as e:
            problems = [f"unreadable: {e}"]
        if not problems:
            return candidate
        print(f"  ⏭  Skipping {candidate.name}: {'; '.join(problems)}")
    return None


def list_available_backups(backup_dir: Path | None = None):
    """List available backup files."""
    backup_dir = backup_dir or DEFAULT_BACKUP_DIR

    if not backup_dir.exists():
        print("No backups directory found.")
        return []

    # Only match timestamp-formatted backups (YYYYMMDD_HHMMSS)
    backup_files = list(backup_dir.glob("database_backup_[0-9]*.json.gz")) + list(
        backup_dir.glob("database_backup_[0-9]*.json")
    )
    backup_files.sort(reverse=True)  # Most recent first

    if not backup_files:
        print("No backup files found.")
        return []

    print("Available backup files:")
    print("-" * 40)

    for i, backup_file in enumerate(backup_files):
        try:
            opener = gzip.open if backup_file.suffix == ".gz" else open
            with opener(backup_file, "rt", encoding="utf-8") as f:
                data = json.load(f)
                info = data.get("backup_info", {})
                created = info.get("created_at", "Unknown")

                print(f"{i+1}. {backup_file.name}")
                print(f"   📅 {created}")
                print(f"   💾 {backup_file.stat().st_size / 1024:.1f} KB")

        except Exception:
            print(f"{i+1}. {backup_file.name} (corrupted)")

    return backup_files


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code.

    Split out of the __main__ block so the exit code is testable (SB-917): a
    partial restore has to report failure, and that is exactly the behaviour
    that was silently wrong — `setup-local-db.sh` checks this code before it
    carries on over the restored data.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Database restore utility")
    parser.add_argument("backup_file", nargs="?", help="Backup file to restore from")
    parser.add_argument(
        "--list", action="store_true", help="List available backup files"
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear existing data before restore",
    )
    parser.add_argument(
        "--latest", action="store_true", help="Restore from the most recent backup"
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=DEFAULT_BACKUP_DIR,
        help=f"Directory containing backup files (default: {DEFAULT_BACKUP_DIR})",
    )

    args = parser.parse_args(argv)
    backup_dir: Path = args.backup_dir

    try:
        if args.list:
            list_available_backups(backup_dir)
            return 0

        if args.latest:
            latest_backup = find_latest_usable_backup(backup_dir)
            if not latest_backup:
                print(f"❌ No usable backup files found in {backup_dir}")
                return 1
            print(f"Using latest backup: {latest_backup.name}")
            return 0 if restore_from_backup(latest_backup, not args.no_clear) else 1

        if args.backup_file:
            # Handle both full path and just filename
            if "/" in args.backup_file:
                backup_file = Path(args.backup_file)
            else:
                backup_file = backup_dir / args.backup_file
            return 0 if restore_from_backup(backup_file, not args.no_clear) else 1

        print("❌ Please specify a backup file or use --list to see available backups")
        print("Usage examples:")
        print("  python scripts/restore_database.py --list")
        print("  python scripts/restore_database.py --latest")
        print(
            f"  python scripts/restore_database.py --backup-dir {DEFAULT_BACKUP_DIR} --latest"
        )
        print(
            "  python scripts/restore_database.py database_backup_20231220_143022.json.gz"
        )
        return 1

    except KeyboardInterrupt:
        print("\n❌ Restore cancelled by user")
        return 130
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

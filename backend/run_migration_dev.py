#!/usr/bin/env python3
"""
Run migration to remove unused mls_match_id column on dev database.

This script:
1. Connects to dev database
2. Verifies mls_match_id is unused (all NULL)
3. Executes the migration to drop the column and index
4. Verifies the column is removed
"""

import os
import sys

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2


# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.ppgxasqgqbnauvxozmjw:8DeHOpTEThgoqzxv@aws-0-us-east-1.pooler.supabase.com:6543/postgres"  # pragma: allowlist secret
)

MIGRATION_FILE = "/Users/silverbeer/gitrepos/missing-table/supabase-local/migrations/20251111120000_remove_unused_mls_match_id.sql"


def print_header(title):
    """Print a formatted header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def print_section(title):
    """Print a formatted section header."""
    print(f"\n--- {title} ---")


def confirm_action(prompt):
    """Prompt user for confirmation."""
    response = input(f"\n{prompt} (type 'yes' to confirm): ").strip().lower()
    return response == 'yes'


def phase_1_validation(cursor):
    """Phase 1: Validation - verify column is unused."""
    print_header("PHASE 1: VALIDATION (READ-ONLY)")

    # Verify we're in dev database
    cursor.execute("SELECT current_database()")
    db_name = cursor.fetchone()[0]
    print(f"✓ Connected to database: {db_name}")

    # Check if mls_match_id column exists
    print_section("Checking mls_match_id Column")
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'matches'
          AND column_name = 'mls_match_id'
    """)

    column = cursor.fetchone()
    if column:
        col_name, data_type, is_nullable = column
        print(f"✓ Column exists:")
        print(f"  Name: {col_name}")
        print(f"  Type: {data_type}")
        print(f"  Nullable: {is_nullable}")
    else:
        print("✗ Column 'mls_match_id' does not exist in matches table!")
        return False

    # Check if column is unused (all NULL)
    print_section("Checking Column Usage")
    cursor.execute("""
        SELECT
            COUNT(*) as total_matches,
            COUNT(mls_match_id) as non_null_count
        FROM matches
    """)

    total, non_null = cursor.fetchone()
    print(f"Total matches: {total}")
    print(f"Non-NULL mls_match_id: {non_null}")

    if non_null > 0:
        print(f"\n⚠️  WARNING: Found {non_null} matches with non-NULL mls_match_id!")
        print("This column may be in use. Aborting.")
        return False
    else:
        print("\n✓ Column is completely unused (100% NULL)")

    # Check if index exists
    print_section("Checking Index")
    cursor.execute("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'matches'
          AND indexname = 'idx_matches_mls_match_id'
    """)

    index = cursor.fetchone()
    if index:
        print(f"✓ Index exists: {index[0]}")
    else:
        print("  No index 'idx_matches_mls_match_id' found (may have been dropped already)")

    # Show match_id column (the one that's actually used)
    print_section("Verifying match_id Column (The One We Keep)")
    cursor.execute("""
        SELECT
            COUNT(*) as total_matches,
            COUNT(match_id) as with_match_id
        FROM matches
        WHERE source = 'match-scraper'
    """)

    total, with_id = cursor.fetchone()
    print(f"Match-scraper matches: {total}")
    print(f"With match_id populated: {with_id} ({100*with_id/total:.1f}%)" if total > 0 else "No match-scraper matches")

    return True


def phase_2_execute(cursor, conn, auto_confirm=False):
    """Phase 2: Execute the migration."""
    print_header("PHASE 2: MIGRATION EXECUTION")

    print("Migration steps:")
    print("  1. DROP INDEX idx_matches_mls_match_id")
    print("  2. ALTER TABLE matches DROP COLUMN mls_match_id")
    print("  3. Add comment to match_id column")

    if auto_confirm:
        print("\n⏩ Auto-confirming migration execution (--yes flag)")
    elif not confirm_action("Proceed with migration?"):
        print("\n❌ Migration cancelled by user")
        return False

    print("\n⏳ Reading migration file...")
    with open(MIGRATION_FILE, 'r') as f:
        migration_sql = f.read()

    print("⏳ Executing migration...")

    try:
        cursor.execute(migration_sql)
        conn.commit()
        print("✅ Migration executed successfully")
        return True
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return False


def phase_3_verification(cursor):
    """Phase 3: Verify the migration was successful."""
    print_header("PHASE 3: VERIFICATION")

    # Verify column is gone
    print_section("Verifying Column Removal")
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'matches'
          AND column_name = 'mls_match_id'
    """)

    if cursor.fetchone():
        print("❌ Column 'mls_match_id' still exists!")
        return False
    else:
        print("✓ Column 'mls_match_id' successfully removed")

    # Verify index is gone
    print_section("Verifying Index Removal")
    cursor.execute("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'matches'
          AND indexname = 'idx_matches_mls_match_id'
    """)

    if cursor.fetchone():
        print("❌ Index 'idx_matches_mls_match_id' still exists!")
        return False
    else:
        print("✓ Index 'idx_matches_mls_match_id' successfully removed")

    # Show remaining match-related columns
    print_section("Remaining Match Columns")
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'matches'
          AND column_name LIKE '%match%'
        ORDER BY ordinal_position
    """)

    print(f"\n{'Column Name':<25} {'Data Type':<20} {'Nullable':<10}")
    print("-" * 60)
    for row in cursor.fetchall():
        col_name, data_type, is_nullable = row
        print(f"{col_name:<25} {data_type:<20} {is_nullable:<10}")

    return True


def main():
    """Main execution flow."""
    print_header("REMOVE UNUSED mls_match_id COLUMN MIGRATION")

    # Check for --yes flag to skip confirmation
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv

    print(f"Database: {DATABASE_URL.split('@')[1].split('/')[0]}")
    print(f"Migration File: {MIGRATION_FILE}")
    if auto_confirm:
        print("Auto-confirm mode: --yes flag provided")

    try:
        # Connect to database
        print("\n⏳ Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        print("✅ Connected successfully")

        # Phase 1: Validation
        if not phase_1_validation(cursor):
            print("\n❌ Validation failed. Aborting.")
            return 1

        # Phase 2: Execute
        # Pass auto_confirm flag to phase 2
        if not phase_2_execute(cursor, conn, auto_confirm):
            return 1

        # Phase 3: Verification
        success = phase_3_verification(cursor)

        # Cleanup
        cursor.close()
        conn.close()

        print_header("MIGRATION COMPLETE")

        if success:
            print("✅ Column mls_match_id successfully removed from matches table!")
            return 0
        else:
            print("⚠️  Migration completed but verification failed")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

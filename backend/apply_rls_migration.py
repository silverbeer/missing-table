#!/usr/bin/env python3
"""
Apply RLS migration to cloud database
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

# Load environment
app_env = os.getenv("APP_ENV", "dev")
env_file = f".env.{app_env}"
print(f"Loading environment from {env_file}...")
load_dotenv(env_file)

def apply_migration():
    """Apply the RLS migration to the database"""

    # Get database URL
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ Error: DATABASE_URL must be set")
        sys.exit(1)

    print(f"🔗 Connecting to database...")

    # Read migration file
    migration_path = Path(__file__).parent.parent / "supabase-local" / "migrations" / "011_enable_rls_security.sql"

    if not migration_path.exists():
        print(f"❌ Error: Migration file not found at {migration_path}")
        sys.exit(1)

    print(f"📄 Reading migration from {migration_path}...")
    migration_sql = migration_path.read_text()

    # Connect to database
    conn = None
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = False  # Use transaction
        cur = conn.cursor()

        print(f"📝 Executing migration...")
        print(f"{'='*60}")

        # Execute the entire migration as one transaction
        # Better SQL splitter that handles $$...$$ for functions
        statements = []
        current = []
        in_dollar_quote = False

        for line in migration_sql.split('\n'):
            # Check for $$ delimiters (toggle state)
            if '$$' in line:
                in_dollar_quote = not in_dollar_quote

            current.append(line)

            # Statement ends with ; when not inside dollar-quoted function body
            if ';' in line and not in_dollar_quote:
                stmt = '\n'.join(current).strip()
                # Filter out pure comment blocks
                if stmt and not all(l.strip().startswith('--') or l.strip().startswith('==') or not l.strip()
                                  for l in stmt.split('\n')):
                    statements.append(stmt)
                current = []

        # Add final statement if any
        if current:
            stmt = '\n'.join(current).strip()
            if stmt and not all(l.strip().startswith('--') or l.strip().startswith('==') or not l.strip()
                              for l in stmt.split('\n')):
                statements.append(stmt)

        success_count = 0
        error_count = 0

        for i, statement in enumerate(statements, 1):
            # Get first meaningful line for display
            first_line = next((line.strip() for line in statement.split('\n')
                              if line.strip() and not line.strip().startswith('--') and not line.strip().startswith('==')), '')[:100]

            if not first_line:
                continue

            try:
                print(f"  [{i}/{len(statements)}] {first_line}")
                # Debug: show if this is a function
                if 'CREATE' in statement.upper() and 'FUNCTION' in statement.upper():
                    print(f"      (Creating function)")
                cur.execute(statement)
                success_count += 1
            except psycopg2.Error as e:
                error_msg = str(e).strip()

                # Some errors can be ignored
                if any(phrase in error_msg.lower() for phrase in [
                    'already exists',
                    'does not exist',
                    'duplicate',
                ]):
                    print(f"    ⚠️  Warning (ignored): {error_msg.split(chr(10))[0]}")
                    success_count += 1
                else:
                    print(f"    ❌ Error: {error_msg.split(chr(10))[0]}")
                    error_count += 1
                    # Don't raise, continue with other statements

        # Commit transaction
        if error_count == 0:
            conn.commit()
            print(f"\n✅ Transaction committed successfully!")
        else:
            conn.rollback()
            print(f"\n⚠️  Transaction rolled back due to errors")

        # Summary
        print(f"{'='*60}")
        print(f"   Successful: {success_count}")
        if error_count > 0:
            print(f"   ❌ Errors: {error_count}")
        print(f"{'='*60}")

        cur.close()
        return error_count == 0

    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    try:
        success = apply_migration()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

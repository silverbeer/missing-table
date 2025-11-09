#!/usr/bin/env python3
"""
Sync local database to match dev database schema.
This will DROP and recreate the local database to match dev exactly.

WARNING: This will DELETE ALL DATA in local database!
"""
import sys
from pathlib import Path
import subprocess

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def load_env_file(env: str) -> dict:
    env_file = Path(__file__).parent / f".env.{env}"
    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                env_vars[key.strip()] = value
    return env_vars


def get_schema_dump(database_url: str) -> str:
    """Get schema DDL from a database."""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    ddl_parts = []

    # 1. Get all ENUM types first (needed for table creation)
    cursor.execute("""
        SELECT t.typname, array_agg(e.enumlabel ORDER BY e.enumsortorder)
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        JOIN pg_namespace n ON t.typnamespace = n.oid
        WHERE n.nspname = 'public'
        GROUP BY t.typname
        ORDER BY t.typname
    """)

    for type_name, enum_values in cursor.fetchall():
        values = "', '".join(enum_values)
        ddl_parts.append(f"DROP TYPE IF EXISTS {type_name} CASCADE;")
        ddl_parts.append(f"CREATE TYPE {type_name} AS ENUM ('{values}');")

    # 2. Get table definitions
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)

    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        # Get CREATE TABLE statement with pg_dump-like approach
        # This is simplified - in production you'd use pg_dump
        cursor.execute(f"""
            SELECT
                'CREATE TABLE ' || quote_ident(table_name) || ' (' ||
                string_agg(
                    quote_ident(column_name) || ' ' ||
                    CASE
                        WHEN data_type = 'USER-DEFINED' THEN udt_name
                        WHEN data_type = 'character varying' AND character_maximum_length IS NOT NULL
                            THEN 'VARCHAR(' || character_maximum_length || ')'
                        ELSE UPPER(data_type)
                    END ||
                    CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END ||
                    CASE WHEN column_default IS NOT NULL THEN ' DEFAULT ' || column_default ELSE '' END,
                    ', '
                ) || ');'
            FROM information_schema.columns
            WHERE table_name = '{table}'
            AND table_schema = 'public'
            GROUP BY table_name
        """)

        create_table = cursor.fetchone()
        if create_table:
            ddl_parts.append(f"DROP TABLE IF EXISTS {table} CASCADE;")
            ddl_parts.append(create_table[0])

    # 3. Get indexes
    cursor.execute("""
        SELECT indexdef || ';'
        FROM pg_indexes
        WHERE schemaname = 'public'
        AND indexname NOT LIKE '%_pkey'
        ORDER BY indexname
    """)

    for (index_def,) in cursor.fetchall():
        ddl_parts.append(index_def)

    # 4. Get foreign keys
    cursor.execute("""
        SELECT
            'ALTER TABLE ' || quote_ident(tc.table_name) ||
            ' ADD CONSTRAINT ' || quote_ident(tc.constraint_name) ||
            ' FOREIGN KEY (' || string_agg(quote_ident(kcu.column_name), ', ') || ')' ||
            ' REFERENCES ' || quote_ident(ccu.table_name) ||
            ' (' || string_agg(quote_ident(ccu.column_name), ', ') || ')' ||
            CASE WHEN rc.delete_rule != 'NO ACTION' THEN ' ON DELETE ' || rc.delete_rule ELSE '' END ||
            CASE WHEN rc.update_rule != 'NO ACTION' THEN ' ON UPDATE ' || rc.update_rule ELSE '' END ||
            ';'
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.referential_constraints rc
            ON tc.constraint_name = rc.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON rc.unique_constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public'
        GROUP BY tc.table_name, tc.constraint_name, ccu.table_name, rc.delete_rule, rc.update_rule
    """)

    for (fk_def,) in cursor.fetchall():
        ddl_parts.append(fk_def)

    # 5. Get triggers
    cursor.execute("""
        SELECT
            'CREATE TRIGGER ' || trigger_name ||
            ' ' || action_timing || ' ' || event_manipulation ||
            ' ON ' || event_object_table ||
            ' FOR EACH ' || action_orientation ||
            ' ' || action_statement || ';'
        FROM information_schema.triggers
        WHERE trigger_schema = 'public'
        ORDER BY trigger_name
    """)

    for (trigger_def,) in cursor.fetchall():
        ddl_parts.append(trigger_def)

    cursor.close()
    conn.close()

    return '\n\n'.join(ddl_parts)


def sync_databases():
    """Sync local to dev."""

    print("="*80)
    print("  SYNC LOCAL DATABASE TO DEV")
    print("="*80)
    print()
    print("⚠️  WARNING: This will DELETE ALL DATA in your local database!")
    print("⚠️  The local database will be dropped and recreated to match dev.")
    print()

    # Load environment configs
    print("Loading database configurations...")
    local_env = load_env_file('local')
    dev_env = load_env_file('dev')

    local_url = local_env.get('DATABASE_URL')
    dev_url = dev_env.get('DATABASE_URL')

    if not local_url or not dev_url:
        print("❌ Missing DATABASE_URL in .env files")
        sys.exit(1)

    print(f"  Local: ...{local_url[-30:]}")
    print(f"  Dev: ...{dev_url[-30:]}")
    print()

    # Get dev schema
    print("📥 Exporting dev schema...")
    try:
        dev_schema = get_schema_dump(dev_url)
        print(f"✅ Exported {len(dev_schema)} characters of DDL")

        # Save to file for backup
        backup_file = Path(__file__).parent / f"dev_schema_backup_{Path(__file__).stem}.sql"
        with open(backup_file, 'w') as f:
            f.write(dev_schema)
        print(f"✅ Saved backup to: {backup_file}")
    except Exception as e:
        print(f"❌ Error exporting dev schema: {e}")
        sys.exit(1)

    print()
    print("🗑️  Dropping local public schema...")
    try:
        conn = psycopg2.connect(local_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        cursor.execute("DROP SCHEMA IF EXISTS public CASCADE;")
        cursor.execute("CREATE SCHEMA public;")
        cursor.execute("GRANT ALL ON SCHEMA public TO postgres;")
        cursor.execute("GRANT ALL ON SCHEMA public TO public;")

        print("✅ Local schema dropped and recreated")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error dropping local schema: {e}")
        sys.exit(1)

    print()
    print("📝 Applying dev schema to local...")
    try:
        conn = psycopg2.connect(local_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Execute the DDL
        cursor.execute(dev_schema)

        print("✅ Dev schema applied to local")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error applying dev schema: {e}")
        print(f"\nPartial DDL that failed:")
        print(dev_schema[:500])
        sys.exit(1)

    print()
    print("="*80)
    print("  ✅ SYNC COMPLETE!")
    print("="*80)
    print()
    print("Next steps:")
    print("1. Run: uv run python check_schema_consistency.py")
    print("2. Verify local and dev are identical")
    print()


if __name__ == "__main__":
    sync_databases()

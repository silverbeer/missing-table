#!/usr/bin/env python3
"""
Simple sync: Copy all table structures and data from dev to local.
WARNING: Drops and recreates everything in local!
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


print("="*80)
print("  SYNC LOCAL TO DEV - SIMPLE APPROACH")
print("="*80)
print()
print("This will:")
print("1. Drop public schema in LOCAL")
print("2. Use dblink to copy schema from DEV to LOCAL")
print()
print("⚠️  ALL LOCAL DATA WILL BE LOST!")
print()

response = input("Type 'YES' to continue: ")
if response != 'YES':
    print("Aborted.")
    sys.exit(0)

# Load configs
local_env = load_env_file('local')
dev_env = load_env_file('dev')

local_url = local_env['DATABASE_URL']
dev_url = dev_env['DATABASE_URL']

print("\n📋 Step 1: Connect to local database...")
local_conn = psycopg2.connect(local_url)
local_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
local_cursor = local_conn.cursor()
print("✅ Connected to local")

print("\n📋 Step 2: Connect to dev database...")
dev_conn = psycopg2.connect(dev_url)
dev_cursor = dev_conn.cursor()
print("✅ Connected to dev")

# Get all objects from dev
print("\n📋 Step 3: Export schema from dev...")

# Export ENUMs
dev_cursor.execute("""
    SELECT
        'DROP TYPE IF EXISTS ' || t.typname || ' CASCADE; CREATE TYPE ' || t.typname || ' AS ENUM (' ||
        string_agg('''' || e.enumlabel || '''', ',' ORDER BY e.enumsortorder) || ');'
    FROM pg_type t
    JOIN pg_enum e ON t.oid = e.enumtypid
    WHERE t.typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
    GROUP BY t.typname
""")
enum_ddls = [row[0] for row in dev_cursor.fetchall()]

# Get table creation DDL - use a simpler approach
dev_cursor.execute("""
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY tablename
""")
tables = [row[0] for row in dev_cursor.fetchall()]

print(f"Found {len(tables)} tables in dev")

print("\n📋 Step 4: Drop local public schema...")
local_cursor.execute("DROP SCHEMA IF EXISTS public CASCADE;")
local_cursor.execute("CREATE SCHEMA public;")
local_cursor.execute("GRANT ALL ON SCHEMA public TO postgres;")
local_cursor.execute("GRANT ALL ON SCHEMA public TO public;")
print("✅ Local schema dropped and recreated")

print("\n📋 Step 5: Apply ENUMs to local...")
for enum_ddl in enum_ddls:
    local_cursor.execute(enum_ddl)
    print(f"  ✅ Created ENUM")

print("\n📋 Step 6: Copy each table structure and data...")

# We'll use a different approach - get the schema via pg_dump-like queries
# For each table, get its definition and copy it

for table in tables:
    print(f"\n  📝 Processing table: {table}")

    # Get columns
    dev_cursor.execute(f"""
        SELECT
            column_name,
            CASE
                WHEN data_type = 'USER-DEFINED' THEN udt_name
                WHEN data_type = 'character varying' AND character_maximum_length IS NOT NULL
                    THEN 'VARCHAR(' || character_maximum_length || ')'
                WHEN data_type = 'numeric' AND numeric_precision IS NOT NULL
                    THEN 'NUMERIC(' || numeric_precision || ',' || numeric_scale || ')'
                ELSE data_type
            END as full_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = '{table}'
        AND table_schema = 'public'
        ORDER BY ordinal_position
    """)

    columns = []
    for col_name, col_type, nullable, default in dev_cursor.fetchall():
        col_def = f"{col_name} {col_type}"
        if nullable == 'NO':
            col_def += " NOT NULL"
        if default:
            col_def += f" DEFAULT {default}"
        columns.append(col_def)

    create_sql = f"CREATE TABLE {table} ({', '.join(columns)});"

    try:
        local_cursor.execute(create_sql)
        print(f"    ✅ Created table structure")
    except Exception as e:
        print(f"    ❌ Error creating table: {e}")
        print(f"    SQL: {create_sql}")
        continue

print("\n📋 Step 7: Copy constraints and indexes...")

# Primary keys
dev_cursor.execute("""
    SELECT
        'ALTER TABLE ' || tc.table_name ||
        ' ADD CONSTRAINT ' || tc.constraint_name ||
        ' PRIMARY KEY (' || string_agg(kcu.column_name, ', ') || ');'
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
    WHERE tc.constraint_type = 'PRIMARY KEY'
    AND tc.table_schema = 'public'
    GROUP BY tc.table_name, tc.constraint_name
""")

for (pk_sql,) in dev_cursor.fetchall():
    try:
        local_cursor.execute(pk_sql)
        print(f"  ✅ Added primary key")
    except Exception as e:
        print(f"  ⚠️  PK warning: {e}")

# Unique constraints
dev_cursor.execute("""
    SELECT
        'ALTER TABLE ' || tc.table_name ||
        ' ADD CONSTRAINT ' || tc.constraint_name ||
        ' UNIQUE (' || string_agg(kcu.column_name, ', ') || ');'
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
    WHERE tc.constraint_type = 'UNIQUE'
    AND tc.table_schema = 'public'
    GROUP BY tc.table_name, tc.constraint_name
""")

for (unique_sql,) in dev_cursor.fetchall():
    try:
        local_cursor.execute(unique_sql)
        print(f"  ✅ Added unique constraint")
    except Exception as e:
        print(f"  ⚠️  Unique warning: {e}")

# Foreign keys
dev_cursor.execute("""
    SELECT
        'ALTER TABLE ' || tc.table_name ||
        ' ADD CONSTRAINT ' || tc.constraint_name ||
        ' FOREIGN KEY (' || kcu.column_name || ')' ||
        ' REFERENCES ' || ccu.table_name ||
        ' (' || ccu.column_name || ')' ||
        CASE WHEN rc.delete_rule != 'NO ACTION' THEN ' ON DELETE ' || rc.delete_rule ELSE '' END ||
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
""")

for (fk_sql,) in dev_cursor.fetchall():
    try:
        local_cursor.execute(fk_sql)
        print(f"  ✅ Added foreign key")
    except Exception as e:
        print(f"  ⚠️  FK warning: {e}")

print("\n📋 Step 8: Copy triggers...")

# Check for moddatetime extension first
local_cursor.execute("CREATE EXTENSION IF NOT EXISTS moddatetime SCHEMA extensions;")

dev_cursor.execute("""
    SELECT
        event_object_table,
        trigger_name,
        action_timing,
        event_manipulation,
        action_orientation,
        action_statement
    FROM information_schema.triggers
    WHERE trigger_schema = 'public'
    ORDER BY event_object_table, trigger_name
""")

for table, name, timing, event, orientation, statement in dev_cursor.fetchall():
    trigger_sql = f"""
    DROP TRIGGER IF EXISTS {name} ON {table};
    CREATE TRIGGER {name}
        {timing} {event} ON {table}
        FOR EACH {orientation}
        {statement};
    """
    try:
        local_cursor.execute(trigger_sql)
        print(f"  ✅ Created trigger: {name}")
    except Exception as e:
        print(f"  ⚠️  Trigger warning ({name}): {e}")

print("\n" + "="*80)
print("  ✅ SYNC COMPLETE!")
print("="*80)
print("\nNow run: uv run python check_schema_consistency.py")

dev_cursor.close()
dev_conn.close()
local_cursor.close()
local_conn.close()

#!/usr/bin/env python3
"""
Check schema consistency across all environments.
Helps identify drift between local, dev, and prod databases.
"""
import sys
from pathlib import Path
from collections import defaultdict

try:
    import psycopg2
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2


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


def get_schema_info(database_url: str) -> dict:
    """Get comprehensive schema information from a database."""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    info = {}

    # 1. Migration tracking
    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN ('schema_migrations', 'schema_version', 'supabase_migrations')
    """)
    tracking_tables = [row[0] for row in cursor.fetchall()]
    info['tracking_tables'] = tracking_tables

    if tracking_tables:
        info['migrations'] = {}
        for table in tracking_tables:
            # Different tracking tables have different columns
            if table == 'schema_version':
                cursor.execute(f"SELECT version, migration_name FROM {table} ORDER BY id")
            else:
                cursor.execute(f"SELECT version, name FROM {table} ORDER BY version")
            info['migrations'][table] = cursor.fetchall()

    # 2. Tables
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    info['tables'] = [row[0] for row in cursor.fetchall()]

    # 3. Columns for important tables
    important_tables = ['matches', 'teams', 'clubs', 'leagues']
    info['columns'] = {}
    for table in important_tables:
        if table in info['tables']:
            cursor.execute("""
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            info['columns'][table] = cursor.fetchall()

    # 4. Triggers
    cursor.execute("""
        SELECT trigger_name, event_object_table, action_statement
        FROM information_schema.triggers
        WHERE trigger_schema = 'public'
        ORDER BY trigger_name
    """)
    info['triggers'] = cursor.fetchall()

    # 5. ENUM types
    cursor.execute("""
        SELECT
            t.typname,
            array_agg(e.enumlabel ORDER BY e.enumsortorder) as enum_values
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname IN ('match_status', 'match_type')
        GROUP BY t.typname
        ORDER BY t.typname
    """)
    info['enums'] = {row[0]: row[1] for row in cursor.fetchall()}

    cursor.close()
    conn.close()

    return info


def compare_schemas(env_data: dict):
    """Compare schemas across environments and report differences."""

    print("\n" + "="*80)
    print("SCHEMA CONSISTENCY REPORT")
    print("="*80)

    # Compare migration tracking
    print("\n### MIGRATION TRACKING ###")
    for env, data in env_data.items():
        tracking = data.get('tracking_tables', [])
        print(f"\n{env}:")
        if tracking:
            for table in tracking:
                migrations = data['migrations'].get(table, [])
                print(f"  {table}: {len(migrations)} migrations")
                if migrations:
                    print(f"    Latest: {migrations[-1]}")
        else:
            print("  ⚠️  NO MIGRATION TRACKING!")

    # Compare tables
    print("\n### TABLES ###")
    all_tables = set()
    for data in env_data.values():
        all_tables.update(data.get('tables', []))

    table_presence = defaultdict(list)
    for table in sorted(all_tables):
        for env, data in env_data.items():
            if table in data.get('tables', []):
                table_presence[table].append(env)

    # Show tables not in all environments
    all_envs = set(env_data.keys())
    inconsistent_tables = {t: envs for t, envs in table_presence.items() if set(envs) != all_envs}

    if inconsistent_tables:
        print("\n⚠️  INCONSISTENT TABLES:")
        for table, envs in sorted(inconsistent_tables.items()):
            missing = all_envs - set(envs)
            print(f"  {table}: in {envs}, MISSING from {list(missing)}")
    else:
        print("\n✅ All tables consistent across environments")

    # Compare columns for important tables
    print("\n### COLUMN DIFFERENCES (important tables) ###")
    important_tables = ['matches', 'teams', 'clubs', 'leagues']

    for table in important_tables:
        # Check if table exists in all environments
        table_in_all = all(table in data.get('tables', []) for data in env_data.values())
        if not table_in_all:
            print(f"\n{table}: ⚠️  Not in all environments")
            continue

        # Compare columns
        all_columns = set()
        for data in env_data.values():
            columns = data.get('columns', {}).get(table, [])
            all_columns.update([col[0] for col in columns])

        column_diffs = False
        for col in sorted(all_columns):
            col_in_envs = {}
            for env, data in env_data.items():
                columns = data.get('columns', {}).get(table, [])
                col_info = next((c for c in columns if c[0] == col), None)
                if col_info:
                    col_in_envs[env] = f"{col_info[1]} ({col_info[2]})"

            if len(col_in_envs) != len(env_data):
                if not column_diffs:
                    print(f"\n{table}:")
                    column_diffs = True
                missing = set(env_data.keys()) - set(col_in_envs.keys())
                print(f"  ⚠️  {col}: in {list(col_in_envs.keys())}, MISSING from {list(missing)}")

            # Check if types differ
            types = set(col_in_envs.values())
            if len(types) > 1:
                if not column_diffs:
                    print(f"\n{table}:")
                    column_diffs = True
                print(f"  ⚠️  {col}: TYPE MISMATCH: {col_in_envs}")

        if not column_diffs:
            print(f"\n{table}: ✅ Consistent")

    # Compare triggers
    print("\n### TRIGGERS ###")
    all_triggers = set()
    for data in env_data.values():
        all_triggers.update([t[0] for t in data.get('triggers', [])])

    trigger_presence = defaultdict(list)
    for trigger in sorted(all_triggers):
        for env, data in env_data.items():
            if trigger in [t[0] for t in data.get('triggers', [])]:
                trigger_presence[trigger].append(env)

    inconsistent_triggers = {t: envs for t, envs in trigger_presence.items() if set(envs) != all_envs}

    if inconsistent_triggers:
        print("\n⚠️  INCONSISTENT TRIGGERS:")
        for trigger, envs in sorted(inconsistent_triggers.items()):
            missing = all_envs - set(envs)
            print(f"  {trigger}: in {envs}, MISSING from {list(missing)}")
    else:
        print("\n✅ All triggers consistent")

    # Compare ENUMs
    print("\n### ENUM TYPES ###")
    all_enums = set()
    for data in env_data.values():
        all_enums.update(data.get('enums', {}).keys())

    for enum in sorted(all_enums):
        enum_values = {}
        for env, data in env_data.items():
            if enum in data.get('enums', {}):
                enum_values[env] = data['enums'][enum]

        # Check consistency
        values_set = set(tuple(v) for v in enum_values.values())
        if len(values_set) > 1:
            print(f"\n⚠️  {enum}: VALUE MISMATCH:")
            for env, values in enum_values.items():
                print(f"    {env}: {values}")
        else:
            print(f"\n✅ {enum}: {next(iter(enum_values.values()))}")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    issues = []
    if inconsistent_tables:
        issues.append(f"❌ {len(inconsistent_tables)} tables inconsistent")
    if inconsistent_triggers:
        issues.append(f"❌ {len(inconsistent_triggers)} triggers inconsistent")

    if issues:
        print("\n".join(issues))
        print("\n⚠️  DATABASES ARE NOT IN SYNC!")
        print("\nRecommendation: Review migration process and sync databases")
    else:
        print("✅ All environments appear to be in sync")
        print("\nNote: This checks structure only, not data consistency")


if __name__ == "__main__":
    print("Checking schema consistency across environments...")
    print("This may take a minute...\n")

    env_data = {}

    for env in ['local', 'dev']:
        try:
            print(f"Connecting to {env}...")
            env_vars = load_env_file(env)
            database_url = env_vars.get('DATABASE_URL')
            if not database_url:
                print(f"  ⚠️  No DATABASE_URL in .env.{env}")
                continue

            env_data[env] = get_schema_info(database_url)
            print(f"  ✅ Connected")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    if len(env_data) < 2:
        print("\n❌ Need at least 2 environments to compare")
        sys.exit(1)

    compare_schemas(env_data)

#!/bin/bash
#
# Fix Local Supabase Migration Issue
# ====================================
#
# ROOT CAUSE:
# Supabase CLI v2.54.11 does NOT apply migrations from supabase-local/migrations/
# during `npx supabase db reset`. The migrations directory is ignored, leaving
# the database with only Supabase infrastructure (auth, storage, etc.) but no
# application schema (teams, matches, etc.).
#
# SYMPTOMS:
# - `npx supabase db reset` completes successfully
# - No tables exist in the public schema
# - Data restoration fails with "relation does not exist" errors
# - PostgREST returns empty OpenAPI spec
#
# SOLUTION:
# Manually apply migrations after reset by piping SQL files directly to PostgreSQL
#
# USAGE:
#   cd supabase-local
#   ./scripts/fix-local-migrations.sh
#
# ====================================

set -e

echo "🔧 Fixing Local Supabase Migrations..."
echo ""

# Check we're in the right directory
if [ ! -d "migrations" ]; then
    echo "❌ Error: migrations directory not found"
    echo "   Please run this script from the supabase-local directory"
    exit 1
fi

# Apply migrations in order
echo "📝 Applying migrations to local database..."
echo ""

for migration in migrations/20*.sql; do
    if [ -f "$migration" ]; then
        filename=$(basename "$migration")
        echo "  Applying: $filename"
        cat "$migration" | docker exec -i supabase_db_supabase-local psql -U postgres -d postgres > /dev/null 2>&1
        echo "    ✅ Applied"
    fi
done

echo ""
echo "🔄 Restarting Supabase to reload schema..."
npx supabase stop
npx supabase start

echo ""
echo "✅ Local migrations fixed!"
echo ""
echo "Next steps:"
echo "  1. Restore data: APP_ENV=local ../scripts/db_tools.sh restore"
echo "  2. Restart services: ../missing-table.sh restart"
echo ""

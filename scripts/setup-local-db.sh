#!/bin/bash
##############################################################################
# Local Database Setup Script
##############################################################################
# One command to go from zero to a working local database with seeded data.
#
# What it does:
#   1. Resets local Supabase database (applies schema.sql + seed.sql)
#   2. Optionally restores match/team data from a backup
#   3. Optionally syncs users from prod (with role-based passwords)
#   4. Seeds test users (tom, tom_ifa, tom_ifa_fan, tom_club)
#
# Usage:
#   ./scripts/setup-local-db.sh              # Reset + seed reference data + test users
#   ./scripts/setup-local-db.sh --restore    # Also restore match/team data from backup
#   ./scripts/setup-local-db.sh --from-prod  # Full refresh: backup + restore + sync users
#
# User passwords when synced from prod (based on role):
#   admin        -> admin123
#   team_manager -> team123
#   team_player  -> play123
#   team_fan     -> fan123
#
# Prerequisites:
#   - Local Supabase must be running: cd supabase-local && npx supabase start
#   - Node.js/npx available (for supabase CLI)
#   - uv available (for backend user management scripts)
##############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

RESTORE_DATA=false
FROM_PROD=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --from-prod)
            FROM_PROD=true
            RESTORE_DATA=true  # --from-prod implies --restore
            ;;
        --restore)
            RESTORE_DATA=true
            ;;
        --help|-h)
            echo "Usage: $0 [--restore] [--from-prod]"
            echo ""
            echo "Options:"
            echo "  --restore    Restore match/team data from backup after schema reset"
            echo "  --from-prod  Full refresh from prod: backup, restore data, AND sync users"
            echo "  --help       Show this help message"
            echo ""
            echo "User passwords (when synced from prod):"
            echo "  admin        -> admin123"
            echo "  team_manager -> team123"
            echo "  team_player  -> play123"
            echo "  team_fan     -> fan123"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown argument: $arg${NC}"
            echo "Usage: $0 [--restore] [--from-prod]"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Local Database Setup${NC}"
echo -e "${BLUE}========================================${NC}"
if [ "$FROM_PROD" = true ]; then
    echo -e "${YELLOW}Mode: Fresh backup from prod + restore${NC}"
fi
echo ""

##############################################################################
# Step 0: If --from-prod, create fresh backup first
##############################################################################
if [ "$FROM_PROD" = true ]; then
    echo -e "${BLUE}Step 0: Creating fresh backup from prod...${NC}"
    cd "$PROJECT_ROOT"
    APP_ENV=prod bash "$SCRIPT_DIR/db_tools.sh" backup
    echo -e "${GREEN}Backup from prod complete${NC}"
    echo ""
fi

##############################################################################
# Step 1: Check prerequisites
##############################################################################
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v npx &> /dev/null; then
    echo -e "${RED}npx not found. Please install Node.js first.${NC}"
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo -e "${RED}uv not found. Please install uv first.${NC}"
    exit 1
fi

# Check if Supabase is running using docker exec (works without local psql)
DB_CONTAINER=""
for container in "supabase_db_supabase-local" "supabase_db_missing-table" "supabase_db_backend"; do
    if docker exec "$container" psql -U postgres -c "SELECT 1" &>/dev/null; then
        DB_CONTAINER="$container"
        break
    fi
done

if [ -z "$DB_CONTAINER" ]; then
    echo -e "${RED}Local Supabase is not running.${NC}"
    echo -e "${YELLOW}Start it with: cd supabase-local && npx supabase start${NC}"
    exit 1
fi
echo -e "${GREEN}Found Supabase container: $DB_CONTAINER${NC}"

echo -e "${GREEN}Prerequisites OK${NC}"
echo ""

##############################################################################
# Step 2: Check for recent backup (less than 4 hours old)
##############################################################################
# Skip this check if --from-prod was used (we just created a fresh backup)
if [ "$FROM_PROD" = true ]; then
    echo -e "${GREEN}Fresh backup created from prod - skipping age check${NC}"
    echo ""
else
    echo -e "${YELLOW}Checking for recent backup...${NC}"

    BACKUP_DIR="$PROJECT_ROOT/backups"
    MAX_AGE_MINUTES=240  # 4 hours

    # Only match timestamp-formatted backups (database_backup_[0-9]*.json)
    recent_backup=""
    if [ -d "$BACKUP_DIR" ]; then
        recent_backup=$(find "$BACKUP_DIR" -maxdepth 1 -name "database_backup_[0-9]*.json" -mmin -${MAX_AGE_MINUTES} 2>/dev/null | sort -r | head -1)
    fi

    if [ -z "$recent_backup" ]; then
        echo -e "${RED}No backup less than 4 hours old found. Aborting reset.${NC}"
        latest_backup=$(ls -t "$BACKUP_DIR"/database_backup_[0-9]*.json 2>/dev/null | head -1)
        if [ -n "$latest_backup" ]; then
            file_age_seconds=$(( $(date +%s) - $(stat -f %m "$latest_backup") ))
            hours=$(( file_age_seconds / 3600 ))
            minutes=$(( (file_age_seconds % 3600) / 60 ))
            echo -e "${RED}Latest backup is ${hours}h ${minutes}m old: $(basename "$latest_backup")${NC}"
        else
            echo -e "${RED}No backups found at all in $BACKUP_DIR${NC}"
        fi
        echo ""
        echo "Create a backup first:"
        echo "  ./scripts/db_tools.sh backup"
        echo ""
        echo "Or use --from-prod to backup from production:"
        echo "  $0 --from-prod"
        exit 1
    fi

    echo -e "${GREEN}Recent backup found: $(basename "$recent_backup")${NC}"
    echo ""
fi

##############################################################################
# Step 3: Reset database (applies schema + seed)
##############################################################################
echo -e "${BLUE}Step 1: Resetting database (schema + seed data)...${NC}"
cd "$PROJECT_ROOT/supabase-local"
npx supabase db reset
echo -e "${GREEN}Database reset complete${NC}"
echo ""

##############################################################################
# Step 3: Optionally restore match/team data from backup
##############################################################################
if [ "$RESTORE_DATA" = true ]; then
    echo -e "${BLUE}Step 2: Restoring match/team data from backup...${NC}"
    cd "$PROJECT_ROOT"
    if [ -f "$SCRIPT_DIR/db_tools.sh" ]; then
        # CRITICAL: Explicitly set APP_ENV=local to prevent accidental prod writes
        APP_ENV=local bash "$SCRIPT_DIR/db_tools.sh" restore
        echo -e "${GREEN}Data restore complete${NC}"

        # Fix sport_type for Futsal leagues (backup may not have this set)
        echo -e "${YELLOW}Setting sport_type for Futsal leagues...${NC}"
        docker exec "$DB_CONTAINER" psql -U postgres -d postgres \
            -c "UPDATE public.leagues SET sport_type = 'futsal' WHERE LOWER(name) LIKE '%futsal%' AND sport_type != 'futsal';" \
            2>/dev/null && echo -e "${GREEN}Futsal leagues updated${NC}" || echo -e "${YELLOW}Could not update Futsal leagues${NC}"
    else
        echo -e "${YELLOW}db_tools.sh not found, skipping data restore${NC}"
    fi
    echo ""
else
    echo -e "${YELLOW}Step 2: Skipping data restore (use --restore to include)${NC}"
    echo ""
fi

##############################################################################
# Step 3: Flush Redis cache (stale cache can serve old/empty data)
##############################################################################
echo -e "${BLUE}Step 3: Flushing Redis cache...${NC}"

# Read kubectl context from .mt-config if available
MT_CONFIG_FILE="$PROJECT_ROOT/.mt-config"
K3S_CONTEXT="rancher-desktop"
if [ -f "$MT_CONFIG_FILE" ]; then
    config_context=$(grep "^local_context=" "$MT_CONFIG_FILE" 2>/dev/null | head -1 | cut -d'=' -f2-)
    if [ -n "$config_context" ]; then
        K3S_CONTEXT="$config_context"
    fi
fi

if kubectl --context="$K3S_CONTEXT" exec -n missing-table svc/missing-table-redis -- redis-cli FLUSHALL &>/dev/null; then
    echo -e "${GREEN}Redis cache flushed${NC}"
else
    echo -e "${YELLOW}Redis not available — skipping cache flush${NC}"
fi
echo ""

##############################################################################
# Step 4: Sync users from prod (only when --from-prod)
##############################################################################
if [ "$FROM_PROD" = true ]; then
    echo -e "${BLUE}Step 4: Syncing users from prod...${NC}"
    cd "$PROJECT_ROOT/backend"
    if [ -f "scripts/sync_users_to_local.py" ]; then
        # Sync all non-test users from prod with force to overwrite existing
        uv run python scripts/sync_users_to_local.py sync --from prod --force
        echo -e "${GREEN}Users synced from prod${NC}"
    else
        echo -e "${YELLOW}sync_users_to_local.py not found, skipping user sync${NC}"
    fi
    echo ""
else
    echo -e "${YELLOW}Step 4: Skipping user sync (only with --from-prod)${NC}"
    echo ""
fi

##############################################################################
# Step 5: Seed test users
##############################################################################
echo -e "${BLUE}Step 5: Seeding test users...${NC}"
cd "$PROJECT_ROOT"
if [ -f "$SCRIPT_DIR/seed_test_users.sh" ]; then
    bash "$SCRIPT_DIR/seed_test_users.sh" local
    echo -e "${GREEN}Test users seeded${NC}"
else
    echo -e "${YELLOW}seed_test_users.sh not found, skipping user seeding${NC}"
fi
echo ""

##############################################################################
# Summary
##############################################################################
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Local Database Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}What was set up:${NC}"
echo "  - Schema applied (all tables, functions, RLS policies)"
echo "  - Reference data seeded (age_groups, seasons, match_types, leagues, divisions)"
if [ "$RESTORE_DATA" = true ]; then
    echo "  - Match/team data restored from backup"
fi
if [ "$FROM_PROD" = true ]; then
    echo "  - Users synced from prod (with role-based passwords)"
fi
echo "  - Test users created (tom, tom_ifa, tom_ifa_fan, tom_club)"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  - Start backend: cd backend && APP_ENV=local uv run python app.py"
echo "  - Start frontend: cd frontend && npm run serve"
echo "  - Or use: ./missing-table.sh start --watch"
echo ""

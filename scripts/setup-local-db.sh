#!/bin/bash
##############################################################################
# Local Database Setup Script
##############################################################################
# One command to go from zero to a working local database with seeded data.
#
# What it does:
#   1. Resets local Supabase database (applies schema.sql + seed.sql)
#   2. Optionally restores match/team data from a backup
#   3. Seeds test users (tom, tom_ifa, tom_ifa_fan, tom_club)
#
# Usage:
#   ./scripts/setup-local-db.sh              # Reset + seed reference data + test users
#   ./scripts/setup-local-db.sh --restore    # Also restore match/team data from backup
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

# Parse arguments
for arg in "$@"; do
    case $arg in
        --restore)
            RESTORE_DATA=true
            ;;
        --help|-h)
            echo "Usage: $0 [--restore]"
            echo ""
            echo "Options:"
            echo "  --restore    Restore match/team data from backup after schema reset"
            echo "  --help       Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown argument: $arg${NC}"
            echo "Usage: $0 [--restore]"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Local Database Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

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

# Check if Supabase is running
if ! PGPASSWORD=postgres psql -h 127.0.0.1 -p 54332 -U postgres -d postgres -c "SELECT 1" &>/dev/null; then
    echo -e "${RED}Local Supabase is not running.${NC}"
    echo -e "${YELLOW}Start it with: cd supabase-local && npx supabase start${NC}"
    exit 1
fi

echo -e "${GREEN}Prerequisites OK${NC}"
echo ""

##############################################################################
# Step 2: Check for recent backup (less than 4 hours old)
##############################################################################
echo -e "${YELLOW}Checking for recent backup...${NC}"

BACKUP_DIR="$PROJECT_ROOT/backups"
MAX_AGE_MINUTES=240  # 4 hours

recent_backup=""
if [ -d "$BACKUP_DIR" ]; then
    recent_backup=$(find "$BACKUP_DIR" -maxdepth 1 -name "database_backup_*.json" -mmin -${MAX_AGE_MINUTES} 2>/dev/null | sort -r | head -1)
fi

if [ -z "$recent_backup" ]; then
    echo -e "${RED}No backup less than 4 hours old found. Aborting reset.${NC}"
    latest_backup=$(ls -t "$BACKUP_DIR"/database_backup_*.json 2>/dev/null | head -1)
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
    exit 1
fi

echo -e "${GREEN}Recent backup found: $(basename "$recent_backup")${NC}"
echo ""

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
        bash "$SCRIPT_DIR/db_tools.sh" restore
        echo -e "${GREEN}Data restore complete${NC}"
    else
        echo -e "${YELLOW}db_tools.sh not found, skipping data restore${NC}"
    fi
    echo ""
else
    echo -e "${YELLOW}Step 2: Skipping data restore (use --restore to include)${NC}"
    echo ""
fi

##############################################################################
# Step 4: Seed test users
##############################################################################
echo -e "${BLUE}Step 3: Seeding test users...${NC}"
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
echo "  - Test users created (tom, tom_ifa, tom_ifa_fan, tom_club)"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  - Start backend: cd backend && APP_ENV=local uv run python app.py"
echo "  - Start frontend: cd frontend && npm run serve"
echo "  - Or use: ./missing-table.sh dev"
echo ""

#!/bin/bash
##############################################################################
# Seed Test Users Script
##############################################################################
# Purpose: Create/update key test users after database restore
# Users:
#   - tom (admin) - Full admin access
#   - tom_ifa (team_manager) - Manager for IFA team
#   - tom_ifa_fan (user) - Regular user/fan for IFA team
#   - tom_club (club_manager) - Manager for IFA Club
#
# Usage:
#   ./scripts/seed_test_users.sh [local|dev|prod]
#
# This script should be run after:
#   - Database restore (./scripts/db_tools.sh restore)
#   - Fresh database setup
#   - Any time test users need to be recreated
##############################################################################

set -e  # Exit on error

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Determine environment
ENVIRONMENT="${1:-local}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Seeding Test Users${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Environment: ${GREEN}${ENVIRONMENT}${NC}"
echo ""

# Set APP_ENV
export APP_ENV="${ENVIRONMENT}"

cd "$(dirname "$0")/../backend" || exit 1

# Load environment variables from .env file
ENV_FILE=".env.${ENVIRONMENT}"
if [ -f "$ENV_FILE" ]; then
    echo -e "${BLUE}Loading passwords from ${ENV_FILE}${NC}"
    # Source the env file to get password variables
    set -a  # automatically export all variables
    source "$ENV_FILE"
    set +a
else
    echo -e "${YELLOW}Warning: ${ENV_FILE} not found, using defaults${NC}"
fi

# Get passwords from environment variables or use defaults
PASSWORD_TOM="${TEST_USER_PASSWORD_TOM:-testpass123}"
PASSWORD_TOM_IFA="${TEST_USER_PASSWORD_TOM_IFA:-testpass123}"
PASSWORD_TOM_IFA_FAN="${TEST_USER_PASSWORD_TOM_IFA_FAN:-testpass123}"
PASSWORD_TOM_CLUB="${TEST_USER_PASSWORD_TOM_CLUB:-testpass123}"

echo -e "${YELLOW}Creating/updating test users...${NC}"
echo ""

##############################################################################
# User 1: tom (admin)
##############################################################################
echo -e "${BLUE}User 1: tom (admin)${NC}"
echo "  - Username: tom"
echo "  - Internal Email: tom@missingtable.local"
echo "  - Role: admin"
echo "  - Password: ${PASSWORD_TOM}"

# Try to set role (this will create profile if user exists without one)
echo -e "  ${YELLOW}Setting role to admin...${NC}"
if uv run python manage_users.py role --user tom --role admin --confirm 2>&1 | grep -q "not found"; then
    echo -e "  ${GREEN}User doesn't exist, creating...${NC}"
    uv run python manage_users.py create \
        --email tom@missingtable.local \
        --password "${PASSWORD_TOM}" \
        --role admin \
        --confirm
else
    echo -e "  ${GREEN}Role updated (or profile created)${NC}"
fi

echo -e "  ${GREEN}✓ tom (admin) ready${NC}"
echo ""

##############################################################################
# User 2: tom_ifa (team-manager)
##############################################################################
echo -e "${BLUE}User 2: tom_ifa (team-manager for IFA)${NC}"
echo "  - Username: tom_ifa"
echo "  - Internal Email: tom_ifa@missingtable.local"
echo "  - Role: team-manager"
echo "  - Password: ${PASSWORD_TOM_IFA}"
echo "  - Team: IFA (will be assigned if team exists)"

# Try to set role (this will create profile if user exists without one)
echo -e "  ${YELLOW}Setting role to team-manager...${NC}"
if uv run python manage_users.py role --user tom_ifa --role team-manager --confirm 2>&1 | grep -q "not found"; then
    echo -e "  ${GREEN}User doesn't exist, creating...${NC}"
    uv run python manage_users.py create \
        --email tom_ifa@missingtable.local \
        --password "${PASSWORD_TOM_IFA}" \
        --role team-manager \
        --confirm
else
    echo -e "  ${GREEN}Role updated (or profile created)${NC}"
fi

# Try to assign to IFA team (get first IFA team found)
echo -e "  ${YELLOW}Looking for IFA team...${NC}"
IFA_TEAM_ID=$(uv run python manage_users.py teams 2>/dev/null | grep -i "IFA" | head -1 | awk '{print $2}' || echo "")

if [ -n "$IFA_TEAM_ID" ]; then
    echo -e "  ${YELLOW}Assigning to IFA team (ID: ${IFA_TEAM_ID})...${NC}"
    uv run python manage_users.py team --user tom_ifa --team-id "${IFA_TEAM_ID}" --confirm || echo -e "  ${YELLOW}Could not assign team (user may not be in auth.users yet)${NC}"
else
    echo -e "  ${YELLOW}No IFA team found - user created but not assigned to team${NC}"
fi

echo -e "  ${GREEN}✓ tom_ifa (team_manager) ready${NC}"
echo ""

##############################################################################
# User 3: tom_ifa_fan (team-fan)
##############################################################################
echo -e "${BLUE}User 3: tom_ifa_fan (team-fan for IFA)${NC}"
echo "  - Username: tom_ifa_fan"
echo "  - Internal Email: tom_ifa_fan@missingtable.local"
echo "  - Role: team-fan"
echo "  - Password: ${PASSWORD_TOM_IFA_FAN}"
echo "  - Team: IFA (will be assigned if team exists)"

# Try to set role (this will create profile if user exists without one)
echo -e "  ${YELLOW}Setting role to team-fan...${NC}"
if uv run python manage_users.py role --user tom_ifa_fan --role team-fan --confirm 2>&1 | grep -q "not found"; then
    echo -e "  ${GREEN}User doesn't exist, creating...${NC}"
    uv run python manage_users.py create \
        --email tom_ifa_fan@missingtable.local \
        --password "${PASSWORD_TOM_IFA_FAN}" \
        --role team-fan \
        --confirm
else
    echo -e "  ${GREEN}Role updated (or profile created)${NC}"
fi

# Try to assign to IFA team (use same team ID as tom_ifa)
if [ -n "$IFA_TEAM_ID" ]; then
    echo -e "  ${YELLOW}Assigning to IFA team (ID: ${IFA_TEAM_ID})...${NC}"
    uv run python manage_users.py team --user tom_ifa_fan --team-id "${IFA_TEAM_ID}" --confirm || echo -e "  ${YELLOW}Could not assign team (user may not be in auth.users yet)${NC}"
else
    echo -e "  ${YELLOW}No IFA team found - user created but not assigned to team${NC}"
fi

echo -e "  ${GREEN}✓ tom_ifa_fan (user) ready${NC}"
echo ""

##############################################################################
# User 4: tom_club (club_manager for IFA Club)
##############################################################################
echo -e "${BLUE}User 4: tom_club (club_manager for IFA Club)${NC}"
echo "  - Username: tom_club"
echo "  - Internal Email: tom_club@missingtable.local"
echo "  - Role: club_manager"
echo "  - Password: ${PASSWORD_TOM_CLUB}"
echo "  - Club: IFA Club (ID: 1)"

# Try to set role (this will create profile if user exists without one)
echo -e "  ${YELLOW}Setting role to club_manager...${NC}"
if uv run python manage_users.py role --user tom_club --role club_manager --confirm 2>&1 | grep -q "not found"; then
    echo -e "  ${GREEN}User doesn't exist, creating...${NC}"
    uv run python manage_users.py create \
        --email tom_club@missingtable.local \
        --password "${PASSWORD_TOM_CLUB}" \
        --role club_manager \
        --club-id 1 \
        --confirm
else
    echo -e "  ${GREEN}Role updated (or profile created)${NC}"
fi

echo -e "  ${GREEN}✓ tom_club (club_manager) ready${NC}"
echo ""

##############################################################################
# Summary
##############################################################################
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Test Users Seeded Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Login Credentials:${NC}"
echo "  1. Username: tom / Password: ${PASSWORD_TOM} (admin)"
echo "  2. Username: tom_ifa / Password: ${PASSWORD_TOM_IFA} (team-manager)"
echo "  3. Username: tom_ifa_fan / Password: ${PASSWORD_TOM_IFA_FAN} (team-fan)"
echo "  4. Username: tom_club / Password: ${PASSWORD_TOM_CLUB} (club_manager - IFA Club)"
echo ""
echo -e "${YELLOW}Note:${NC} If team assignments failed, users exist but aren't"
echo "linked to teams yet. Sign in to the app first, then re-run this script."
echo ""
echo -e "${BLUE}Verify users:${NC}"
echo "  APP_ENV=${ENVIRONMENT} uv run python backend/manage_users.py list"
echo ""

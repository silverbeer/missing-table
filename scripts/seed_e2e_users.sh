#!/bin/bash
# Seed E2E test users for Playwright testing
# These users are specifically for E2E tests and use the e2e_ prefix

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Seeding E2E Test Users${NC}"
echo -e "${BLUE}========================================${NC}"

# Determine environment
ENV="${1:-local}"
echo -e "Environment: ${GREEN}${ENV}${NC}"
echo ""

# Set APP_ENV for Python scripts
export APP_ENV="$ENV"

# Change to backend directory
cd "$(dirname "$0")/../backend"

echo -e "${YELLOW}Creating/updating E2E test users...${NC}"
echo ""

# Function to create or update a user
create_e2e_user() {
    local username="$1"
    local password="$2"
    local role="$3"
    local display_name="$4"

    echo -e "${BLUE}User: ${username} (${role})${NC}"
    echo -e "  - Username: ${username}"
    echo -e "  - Internal Email: ${username}@missingtable.local"
    echo -e "  - Role: ${role}"
    echo -e "  - Display Name: ${display_name}"

    # Create or update user using manage_users.py
    # First try to set role (will create profile if user exists in auth)
    echo -e "  ${YELLOW}Setting role to ${role}...${NC}"

    if uv run python manage_users.py role --user "${username}" --role "${role}" --confirm 2>/dev/null; then
        echo -e "  ${GREEN}Role updated (or profile created)${NC}"
    else
        # User doesn't exist, create them
        echo -e "  ${GREEN}User doesn't exist, creating...${NC}"
        uv run python manage_users.py create \
            --email "${username}@missingtable.local" \
            --password "${password}" \
            --role "${role}" \
            --display-name "${display_name}" \
            --confirm
    fi

    echo -e "  ${GREEN}Done${NC}"
    echo ""
}

# Create E2E test users
# These match the fixtures in backend/tests/e2e/playwright/conftest.py
create_e2e_user "e2e_admin" "AdminPassword123!" "admin" "E2E Admin"
create_e2e_user "e2e_manager" "ManagerPassword123!" "team-manager" "E2E Manager"
create_e2e_user "e2e_player" "PlayerPassword123!" "team-player" "E2E Player"
create_e2e_user "e2e_fan" "FanPassword123!" "team-fan" "E2E Fan"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}E2E Test Users Seeded Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Login Credentials:${NC}"
echo "  1. Username: e2e_admin / Password: AdminPassword123! (admin)"
echo "  2. Username: e2e_manager / Password: ManagerPassword123! (team-manager)"
echo "  3. Username: e2e_player / Password: PlayerPassword123! (team-player)"
echo "  4. Username: e2e_fan / Password: FanPassword123! (team-fan)"
echo ""
echo -e "${BLUE}Verify users:${NC}"
echo "  APP_ENV=${ENV} uv run python backend/manage_users.py list"
echo ""
echo -e "${YELLOW}Note:${NC} These users use the e2e_ prefix to distinguish them from"
echo "development test users (tom, tom_ifa, etc.)"

#!/bin/bash
# Script to sync .env.dev file between Documents folder and missing-table repo
# This allows you to keep the file in sync between Mac Mini and MacBook Air via iCloud

set -e

REPO_ENV_FILE="backend/.env.dev"
SHARED_ENV_FILE="$HOME/Documents/missing-table-env-dev"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

show_help() {
    echo "Usage: $0 [push|pull|status|help]"
    echo ""
    echo "Commands:"
    echo "  push    - Copy .env.dev from repo to Documents folder (for syncing to other machine)"
    echo "  pull    - Copy .env.dev from Documents folder to repo (after syncing from other machine)"
    echo "  status  - Show current state of both files"
    echo "  help    - Show this help message"
    echo ""
    echo "Workflow:"
    echo "  1. On Mac Mini: ./scripts/sync-env-dev.sh push"
    echo "  2. Wait for iCloud to sync ~/Documents/missing-table-env-dev"
    echo "  3. On MacBook Air: ./scripts/sync-env-dev.sh pull"
    echo ""
}

show_status() {
    echo -e "${BLUE}=== Status ===${NC}"
    echo ""

    if [ -f "$REPO_ENV_FILE" ]; then
        echo -e "${GREEN}✓${NC} Repo file exists: $REPO_ENV_FILE"
        echo "  Modified: $(stat -f "%Sm" "$REPO_ENV_FILE")"
        echo "  Size: $(wc -c < "$REPO_ENV_FILE") bytes"
    else
        echo -e "${RED}✗${NC} Repo file NOT found: $REPO_ENV_FILE"
    fi

    echo ""

    if [ -f "$SHARED_ENV_FILE" ]; then
        echo -e "${GREEN}✓${NC} Shared file exists: $SHARED_ENV_FILE"
        echo "  Modified: $(stat -f "%Sm" "$SHARED_ENV_FILE")"
        echo "  Size: $(wc -c < "$SHARED_ENV_FILE") bytes"
    else
        echo -e "${YELLOW}!${NC} Shared file NOT found: $SHARED_ENV_FILE"
        echo "  (This is normal if you haven't pushed yet)"
    fi

    echo ""

    if [ -f "$REPO_ENV_FILE" ] && [ -f "$SHARED_ENV_FILE" ]; then
        if diff -q "$REPO_ENV_FILE" "$SHARED_ENV_FILE" > /dev/null; then
            echo -e "${GREEN}Files are identical${NC}"
        else
            echo -e "${YELLOW}Files differ${NC}"
            echo ""
            echo "Differences:"
            diff "$REPO_ENV_FILE" "$SHARED_ENV_FILE" | head -20 || true
        fi
    fi
}

push_to_shared() {
    if [ ! -f "$REPO_ENV_FILE" ]; then
        echo -e "${RED}Error: Repo file not found: $REPO_ENV_FILE${NC}"
        exit 1
    fi

    echo -e "${BLUE}Pushing .env.dev to shared location...${NC}"
    cp "$REPO_ENV_FILE" "$SHARED_ENV_FILE"

    echo -e "${GREEN}✓ Successfully copied${NC}"
    echo "  From: $REPO_ENV_FILE"
    echo "  To:   $SHARED_ENV_FILE"
    echo ""
    echo -e "${YELLOW}Note: Wait for iCloud to sync ~/Documents before accessing from other machine${NC}"
}

pull_from_shared() {
    if [ ! -f "$SHARED_ENV_FILE" ]; then
        echo -e "${RED}Error: Shared file not found: $SHARED_ENV_FILE${NC}"
        echo "Have you run 'push' on the other machine yet?"
        exit 1
    fi

    # Backup existing file if it exists
    if [ -f "$REPO_ENV_FILE" ]; then
        BACKUP_FILE="${REPO_ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        echo -e "${YELLOW}Backing up existing file to: $BACKUP_FILE${NC}"
        cp "$REPO_ENV_FILE" "$BACKUP_FILE"
    fi

    echo -e "${BLUE}Pulling .env.dev from shared location...${NC}"
    cp "$SHARED_ENV_FILE" "$REPO_ENV_FILE"

    echo -e "${GREEN}✓ Successfully copied${NC}"
    echo "  From: $SHARED_ENV_FILE"
    echo "  To:   $REPO_ENV_FILE"
}

# Main script
case "${1:-help}" in
    push)
        push_to_shared
        ;;
    pull)
        pull_from_shared
        ;;
    status)
        show_status
        ;;
    help|*)
        show_help
        ;;
esac

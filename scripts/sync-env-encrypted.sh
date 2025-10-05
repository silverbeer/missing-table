#!/bin/bash
# Encrypted sync of .env.dev using Git (secrets never stored in plain text)
# Uses OpenSSL for encryption with a password

set -e

REPO_ENV_FILE="backend/.env.dev"
ENCRYPTED_FILE=".env.dev.encrypted"
BRANCH_NAME="sync-env-encrypted"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

show_help() {
    echo "Usage: $0 [push|pull|help]"
    echo ""
    echo "Commands:"
    echo "  push    - Encrypt and push .env.dev to Git (sync-env-encrypted branch)"
    echo "  pull    - Pull and decrypt .env.dev from Git"
    echo "  help    - Show this help message"
    echo ""
    echo "Workflow:"
    echo "  1. On Mac Mini: ./scripts/sync-env-encrypted.sh push"
    echo "     (You'll be asked for an encryption password)"
    echo "  2. On MacBook Air: ./scripts/sync-env-encrypted.sh pull"
    echo "     (Enter the same password to decrypt)"
    echo ""
    echo "Security:"
    echo "  - .env.dev is encrypted with AES-256 before pushing to Git"
    echo "  - Only the encrypted file is committed (secrets are safe)"
    echo "  - You need the password to decrypt on the other machine"
    echo ""
}

push_encrypted() {
    if [ ! -f "$REPO_ENV_FILE" ]; then
        echo -e "${RED}Error: File not found: $REPO_ENV_FILE${NC}"
        exit 1
    fi

    echo -e "${BLUE}Encrypting .env.dev...${NC}"
    echo "Enter encryption password (you'll need this on the other machine):"

    # Encrypt the file
    openssl enc -aes-256-cbc -salt -pbkdf2 -in "$REPO_ENV_FILE" -out "$ENCRYPTED_FILE"

    if [ $? -ne 0 ]; then
        echo -e "${RED}Encryption failed${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Encrypted${NC}"

    # Save current branch
    CURRENT_BRANCH=$(git branch --show-current)

    # Switch to sync branch (create if doesn't exist)
    if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
        git checkout "$BRANCH_NAME"
    else
        git checkout -b "$BRANCH_NAME"
    fi

    # Add and commit encrypted file
    git add "$ENCRYPTED_FILE"
    git commit -m "sync: Update encrypted .env.dev $(date '+%Y-%m-%d %H:%M:%S')" || true

    echo -e "${BLUE}Pushing to GitHub...${NC}"
    git push -u origin "$BRANCH_NAME"

    # Return to original branch
    git checkout "$CURRENT_BRANCH"

    # Clean up encrypted file from working directory
    rm -f "$ENCRYPTED_FILE"

    echo -e "${GREEN}✓ Successfully pushed encrypted .env.dev${NC}"
    echo "Run './scripts/sync-env-encrypted.sh pull' on the other machine"
}

pull_encrypted() {
    # Save current branch
    CURRENT_BRANCH=$(git branch --show-current)

    echo -e "${BLUE}Fetching latest from GitHub...${NC}"
    git fetch origin

    # Switch to sync branch
    if ! git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
        git checkout -b "$BRANCH_NAME" "origin/$BRANCH_NAME"
    else
        git checkout "$BRANCH_NAME"
        git pull origin "$BRANCH_NAME"
    fi

    if [ ! -f "$ENCRYPTED_FILE" ]; then
        echo -e "${RED}Error: Encrypted file not found${NC}"
        echo "Has it been pushed from the other machine yet?"
        git checkout "$CURRENT_BRANCH"
        exit 1
    fi

    # Backup existing .env.dev
    if [ -f "$REPO_ENV_FILE" ]; then
        BACKUP_FILE="${REPO_ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        echo -e "${YELLOW}Backing up existing file to: $BACKUP_FILE${NC}"
        cp "$REPO_ENV_FILE" "$BACKUP_FILE"
    fi

    echo -e "${BLUE}Decrypting .env.dev...${NC}"
    echo "Enter decryption password:"

    # Decrypt the file
    openssl enc -aes-256-cbc -d -pbkdf2 -in "$ENCRYPTED_FILE" -out "$REPO_ENV_FILE"

    if [ $? -ne 0 ]; then
        echo -e "${RED}Decryption failed (wrong password?)${NC}"
        git checkout "$CURRENT_BRANCH"
        exit 1
    fi

    # Return to original branch
    git checkout "$CURRENT_BRANCH"

    echo -e "${GREEN}✓ Successfully pulled and decrypted .env.dev${NC}"
}

# Main
case "${1:-help}" in
    push)
        push_encrypted
        ;;
    pull)
        pull_encrypted
        ;;
    help|*)
        show_help
        ;;
esac

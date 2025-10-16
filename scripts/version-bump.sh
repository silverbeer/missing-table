#!/bin/bash

# Version Bump Script for Missing Table
# Increments semantic version in VERSION file
#
# Usage:
#   ./scripts/version-bump.sh major      # 1.0.0 -> 2.0.0
#   ./scripts/version-bump.sh minor      # 1.0.0 -> 1.1.0
#   ./scripts/version-bump.sh patch      # 1.0.0 -> 1.0.1
#   ./scripts/version-bump.sh            # Defaults to patch

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VERSION_FILE="VERSION"
BUMP_TYPE="${1:-patch}"  # Default to patch if not specified

print_error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
}

print_success() {
    echo -e "${GREEN}SUCCESS: $1${NC}"
}

print_info() {
    echo -e "${YELLOW}INFO: $1${NC}"
}

print_step() {
    echo -e "${BLUE}▶ $1${NC}"
}

# Validate bump type
if [[ ! "$BUMP_TYPE" =~ ^(major|minor|patch)$ ]]; then
    print_error "Invalid bump type: $BUMP_TYPE"
    echo "Usage: $0 [major|minor|patch]"
    echo ""
    echo "Examples:"
    echo "  $0 major    # 1.0.0 -> 2.0.0"
    echo "  $0 minor    # 1.0.0 -> 1.1.0"
    echo "  $0 patch    # 1.0.0 -> 1.0.1 (default)"
    exit 1
fi

# Check if VERSION file exists
if [ ! -f "$VERSION_FILE" ]; then
    print_error "VERSION file not found at: $VERSION_FILE"
    print_info "Creating VERSION file with default version: 1.0.0"
    echo "1.0.0" > "$VERSION_FILE"
fi

# Read current version
CURRENT_VERSION=$(cat "$VERSION_FILE" | tr -d '\n\r' | tr -d ' ')
print_info "Current version: $CURRENT_VERSION"

# Parse version components
if [[ ! "$CURRENT_VERSION" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    print_error "Invalid version format in VERSION file: $CURRENT_VERSION"
    print_info "Expected format: MAJOR.MINOR.PATCH (e.g., 1.0.0)"
    exit 1
fi

MAJOR="${BASH_REMATCH[1]}"
MINOR="${BASH_REMATCH[2]}"
PATCH="${BASH_REMATCH[3]}"

# Bump version based on type
case "$BUMP_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
esac

# Generate new version
NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"

print_step "Bumping version: ${CURRENT_VERSION} -> ${NEW_VERSION} (${BUMP_TYPE})"

# Write new version to file
echo "$NEW_VERSION" > "$VERSION_FILE"

print_success "Version updated to: $NEW_VERSION"

# Show git status
if git rev-parse --git-dir > /dev/null 2>&1; then
    print_info "Git repository detected"
    echo ""
    echo "Next steps:"
    echo "  1. Review the change: git diff $VERSION_FILE"
    echo "  2. Commit the change: git add $VERSION_FILE && git commit -m \"chore: bump version to $NEW_VERSION\""
    echo "  3. Create git tag: git tag v$NEW_VERSION"
    echo "  4. Push changes: git push && git push --tags"
else
    print_info "Not in a git repository"
fi

# Output the new version for CI/CD use
echo "$NEW_VERSION"

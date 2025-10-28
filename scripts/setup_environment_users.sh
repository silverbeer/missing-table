#!/bin/bash
# Setup users for a specific environment (local, dev, or prod)
# This script creates the standard set of users needed for development and testing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if environment is specified
if [ -z "$1" ]; then
    print_error "Usage: $0 <environment>"
    echo "  Environments: local, dev, prod"
    echo ""
    echo "Example:"
    echo "  $0 local   # Setup users for local development"
    echo "  $0 dev     # Setup users for cloud dev environment"
    echo "  $0 prod    # Setup users for production environment"
    exit 1
fi

ENVIRONMENT=$1

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(local|dev|prod)$ ]]; then
    print_error "Invalid environment: $ENVIRONMENT"
    echo "  Valid environments: local, dev, prod"
    exit 1
fi

print_header "Setting up users for $ENVIRONMENT environment"
echo ""

# Set APP_ENV for the database connection
export APP_ENV=$ENVIRONMENT

cd "$PROJECT_ROOT/backend" || exit 1

# Check if manage_users.py exists
if [ ! -f "manage_users.py" ]; then
    print_error "manage_users.py not found in backend/"
    exit 1
fi

# Define users based on environment
if [ "$ENVIRONMENT" = "prod" ]; then
    # Production: Only create essential admin users
    # Real users should sign up themselves
    print_warning "Production environment detected"
    print_info "Only creating essential admin users for production"
    echo ""

    USERS=(
        "admin@missingtable.com:admin:Admin User"
    )

    print_warning "IMPORTANT: Production users should sign up via the web interface"
    print_warning "This script only creates admin accounts for system management"
    echo ""

else
    # Development/Local: Create test users for all roles
    print_info "Creating test users for $ENVIRONMENT environment"
    echo ""

    USERS=(
        "admin@missingtable.local:admin:Admin User"
        "manager@missingtable.local:team-manager:Team Manager"
        "fan@missingtable.local:user:Team Fan"
        "player@missingtable.local:team-player:Team Player"
    )
fi

# Create each user
echo "Creating users..."
for user_spec in "${USERS[@]}"; do
    IFS=':' read -r email role display_name <<< "$user_spec"

    echo ""
    print_info "Creating user: $email (Role: $role)"

    # Check if user already exists
    existing_user=$(APP_ENV=$ENVIRONMENT uv run python manage_users.py info --email "$email" 2>/dev/null | grep -c "User ID:" || true)

    if [ "$existing_user" -gt 0 ]; then
        print_warning "User $email already exists"

        # Ask if we should update the role
        read -p "Update role to $role? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            APP_ENV=$ENVIRONMENT uv run python manage_users.py role \
                --user "$email" \
                --role "$role" \
                --confirm

            if [ $? -eq 0 ]; then
                print_success "Updated role for $email"
            else
                print_error "Failed to update role for $email"
            fi
        fi
    else
        # Create new user
        APP_ENV=$ENVIRONMENT uv run python manage_users.py create \
            --email "$email" \
            --password "password123" \
            --role "$role" \
            --display-name "$display_name" \
            --confirm 2>&1

        if [ $? -eq 0 ]; then
            print_success "Created user: $email"
        else
            print_error "Failed to create user: $email"
        fi
    fi
done

echo ""
print_header "User Setup Complete"
echo ""

# Show summary
print_info "Summary:"
echo ""
APP_ENV=$ENVIRONMENT uv run python manage_users.py list

echo ""
print_success "User setup completed for $ENVIRONMENT environment"
echo ""

if [ "$ENVIRONMENT" != "prod" ]; then
    print_info "Test user credentials:"
    echo "  Email: admin@missingtable.local"
    echo "  Password: password123"
    echo ""
    print_warning "These are TEST credentials - never use in production!"
fi

echo ""
print_info "To manage users, use: cd backend && APP_ENV=$ENVIRONMENT uv run python manage_users.py"

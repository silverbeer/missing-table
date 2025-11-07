#!/bin/bash
# Database backup and restore utility script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

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

# Check if Python environment is available
check_environment() {
    if ! command -v uv &> /dev/null; then
        print_error "uv not found. Please install uv first."
        exit 1
    fi

    if [ ! -f "$PROJECT_ROOT/backend/pyproject.toml" ]; then
        print_error "Backend project not found. Please run from project root."
        exit 1
    fi
}

# Get current environment
get_current_environment() {
    echo "${APP_ENV:-local}"
}

# Set environment for database operations
set_database_environment() {
    local target_env="$1"

    if [ -n "$target_env" ]; then
        export APP_ENV="$target_env"
        print_warning "Using environment: $target_env"
    else
        local current_env=$(get_current_environment)
        print_warning "Using current environment: $current_env"
    fi
}

# Create a backup
backup_database() {
    local target_env="$1"
    set_database_environment "$target_env"

    local current_env=$(get_current_environment)
    print_header "Creating Database Backup ($current_env environment)"

    cd "$PROJECT_ROOT/backend" || exit 1

    # Create Python JSON backup
    print_warning "Creating JSON backup (Python)..."
    uv run python ../scripts/backup_database.py

    if [ $? -ne 0 ]; then
        print_error "Python backup failed"
        exit 1
    fi

    # Create SQL backup using Supabase CLI
    print_warning "Creating SQL backup (Supabase CLI)..."
    cd "$PROJECT_ROOT" || exit 1

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    SQL_BACKUP_FILE="backups/database_backup_${current_env}_${TIMESTAMP}.sql"

    # Use appropriate Supabase CLI flags based on environment
    if [ "$current_env" = "local" ]; then
        npx supabase db dump --local --data-only --file "$SQL_BACKUP_FILE"
    else
        # For cloud environments, we need to use the cloud database
        print_warning "Cloud backup requires manual configuration. Using Python backup only."
        print_warning "SQL backup skipped for cloud environment."
        print_success "Python backup completed successfully"
        return 0
    fi

    if [ $? -eq 0 ]; then
        print_success "SQL backup completed: $SQL_BACKUP_FILE"
        print_success "Both backups completed successfully"
    else
        print_error "SQL backup failed (JSON backup still available)"
        exit 1
    fi
}

# Restore from backup
restore_database() {
    local backup_file="$1"
    local target_env="$2"
    set_database_environment "$target_env"

    local current_env=$(get_current_environment)

    if [ -n "$backup_file" ]; then
        print_header "Restoring Database from $backup_file ($current_env environment)"
        cd "$PROJECT_ROOT/backend" || exit 1
        uv run python ../scripts/restore_database.py "$backup_file"
    else
        print_header "Restoring Database from Latest Backup ($current_env environment)"
        cd "$PROJECT_ROOT/backend" || exit 1
        uv run python ../scripts/restore_database.py --latest
    fi

    if [ $? -eq 0 ]; then
        print_success "Restore completed successfully"

        # Seed test users after successful restore
        print_warning "Seeding test users..."
        "$PROJECT_ROOT/scripts/seed_test_users.sh" "$current_env"

        if [ $? -eq 0 ]; then
            print_success "Test users seeded successfully"
        else
            print_warning "Test user seeding had some issues (check output above)"
        fi
    else
        print_error "Restore failed"
        exit 1
    fi
}

# List available backups
list_backups() {
    print_header "Available Backups"
    cd "$PROJECT_ROOT/backend" || exit 1
    uv run python ../scripts/backup_database.py --list
}

# Reset database and restore from latest backup
reset_and_populate() {
    local target_env="$1"
    set_database_environment "$target_env"

    local current_env=$(get_current_environment)
    print_header "Resetting Database and Restoring from Latest Backup ($current_env environment)"

    # First create a backup
    print_warning "Creating backup before reset..."
    backup_database "$current_env"

    # Reset database
    print_warning "Resetting database..."
    cd "$PROJECT_ROOT" || exit 1

    if [ "$current_env" = "local" ]; then
        npx supabase db reset
    else
        print_warning "Cloud environment reset requires manual intervention."
        print_warning "Consider using database migrations instead."
        print_error "Reset operation not supported for cloud environments."
        return 1
    fi

    # Restore real data from latest backup instead of creating sample data
    print_warning "Restoring real data from latest backup..."
    restore_database "" "$current_env"

    print_success "Database reset and restoration completed"
}

# Clean up old backups
cleanup_backups() {
    local keep_count="${1:-10}"
    print_header "Cleaning Up Old Backups (keeping $keep_count)"
    cd "$PROJECT_ROOT/backend" || exit 1
    uv run python ../scripts/backup_database.py --cleanup "$keep_count"
}

# Show help
show_help() {
    echo "Database Tools - MLS Next Development Utility"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  backup [env]                    Create backup for specified environment (local|dev|prod)"
    echo "  restore [backup_file] [env]     Restore from backup to specified environment"
    echo "  list                            List available backups"
    echo "  reset [env]                     Reset database and repopulate with basic data"
    echo "  cleanup [keep_count]            Clean up old backups (default: keep 10)"
    echo "  help                            Show this help message"
    echo ""
    echo "Environment Options:"
    echo "  local     Local Supabase (default) - requires 'npx supabase start'"
    echo "  dev       Cloud development environment"
    echo "  prod      Cloud production environment"
    echo ""
    echo "Examples:"
    echo "  $0 backup                                    # Create backup for current environment"
    echo "  $0 backup dev                                # Create backup for dev environment"
    echo "  $0 restore                                   # Restore latest backup to current environment"
    echo "  $0 restore backup_file.json dev              # Restore specific backup to dev environment"
    echo "  $0 list                                      # List all backups"
    echo "  $0 reset local                               # Reset local database"
    echo "  $0 cleanup 5                                 # Keep only 5 most recent backups"
    echo ""
}

# Main script logic
check_environment

case "${1:-help}" in
    backup)
        backup_database "$2"
        ;;
    restore)
        # Handle both formats: restore [file] [env] and restore [env]
        if [ -f "$2" ] || [ "$2" = "--latest" ]; then
            restore_database "$2" "$3"
        else
            restore_database "" "$2"
        fi
        ;;
    list)
        list_backups
        ;;
    reset)
        reset_and_populate "$2"
        ;;
    cleanup)
        cleanup_backups "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: ${1:-[none]}"
        echo ""
        show_help
        exit 1
        ;;
esac
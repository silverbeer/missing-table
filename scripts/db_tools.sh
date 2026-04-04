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

# Check that a recent backup exists (less than 4 hours old)
# Returns 0 if a recent backup exists, 1 otherwise
check_recent_backup() {
    local backup_dir="${HOME}/backups/missing-table"
    local max_age_minutes=240  # 4 hours

    if [ ! -d "$backup_dir" ]; then
        print_error "Backup directory not found: $backup_dir"
        return 1
    fi

    # Find backup files modified within the last 4 hours (compressed backups)
    local recent_backups
    recent_backups=$(find "$backup_dir" -maxdepth 1 -name "database_backup_[0-9]*.json.gz" -mmin -${max_age_minutes} 2>/dev/null | sort -r | head -1)

    if [ -z "$recent_backups" ]; then
        # Find the most recent backup to show how old it is
        local latest_backup
        latest_backup=$(ls -t "$backup_dir"/database_backup_[0-9]*.json.gz 2>/dev/null | head -1)
        if [ -n "$latest_backup" ]; then
            local file_age_seconds
            file_age_seconds=$(( $(date +%s) - $(stat -f %m "$latest_backup") ))
            local hours=$(( file_age_seconds / 3600 ))
            local minutes=$(( (file_age_seconds % 3600) / 60 ))
            print_error "No recent backup found. Latest backup is ${hours}h ${minutes}m old:"
            echo "  $(basename "$latest_backup")"
        else
            print_error "No backups found at all in $backup_dir"
        fi
        echo ""
        echo "Create a backup first:"
        echo "  ./scripts/db_tools.sh backup"
        return 1
    fi

    print_success "Recent backup found: $(basename "$recent_backups")"
    return 0
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

    # Create Python JSON backup (compressed, stored to ~/backups/missing-table/)
    print_warning "Creating JSON backup (Python)..."
    uv run python ../scripts/backup_database.py --backup-dir "${HOME}/backups/missing-table"

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

    # Verify a recent backup exists before destructive reset
    if ! check_recent_backup; then
        print_error "Aborting reset: no backup less than 4 hours old."
        return 1
    fi

    # Reset database
    print_warning "Resetting database..."
    cd "$PROJECT_ROOT" || exit 1

    if [ "$current_env" = "local" ]; then
        cd supabase-local && npx supabase db reset
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

# Deploy migrations to an environment
deploy_migrations() {
    local target_env="${1:-prod}"

    if [ "$target_env" != "prod" ] && [ "$target_env" != "local" ]; then
        print_error "Invalid environment: $target_env (must be 'local' or 'prod')"
        return 1
    fi

    if [ "$target_env" = "local" ]; then
        print_header "Applying Migrations to Local Database"
        cd "$PROJECT_ROOT/supabase-local" || exit 1
        npx supabase migration up
        if [ $? -eq 0 ]; then
            print_success "Local migrations applied successfully"
        else
            print_error "Local migration failed"
            return 1
        fi
        return 0
    fi

    # Production deployment
    print_header "Deploying Migrations to Production"
    echo ""
    print_warning "This will apply unapplied migrations to the PRODUCTION database."
    echo ""

    # Show which migrations will be applied
    print_warning "Checking for pending migrations..."
    cd "$PROJECT_ROOT/supabase-local" || exit 1

    # Save current env and switch to prod
    local original_env=$(get_current_environment)
    "$PROJECT_ROOT/switch-env.sh" prod 2>/dev/null

    echo ""
    npx supabase migration list --linked 2>/dev/null
    echo ""

    # Confirm
    read -p "$(echo -e "${YELLOW}Proceed with production migration? (yes/no): ${NC}")" confirm
    if [ "$confirm" != "yes" ]; then
        print_warning "Migration cancelled."
        "$PROJECT_ROOT/switch-env.sh" "$original_env" 2>/dev/null
        return 0
    fi

    # Step 1: Backup
    print_header "Step 1/3: Creating Production Backup"
    cd "$PROJECT_ROOT" || exit 1
    backup_database "prod"
    if [ $? -ne 0 ]; then
        print_error "Backup failed. Aborting migration."
        "$PROJECT_ROOT/switch-env.sh" "$original_env" 2>/dev/null
        return 1
    fi

    # Step 2: Push migrations
    print_header "Step 2/3: Applying Migrations"
    cd "$PROJECT_ROOT/supabase-local" || exit 1
    npx supabase db push --linked
    if [ $? -ne 0 ]; then
        print_error "Migration failed! Check output above."
        print_warning "Your backup is available for rollback."
        "$PROJECT_ROOT/switch-env.sh" "$original_env" 2>/dev/null
        return 1
    fi

    # Step 3: Verify
    print_header "Step 3/3: Verifying Migrations"
    npx supabase migration list --linked 2>/dev/null
    echo ""

    # Switch back to original env
    cd "$PROJECT_ROOT" || exit 1
    "$PROJECT_ROOT/switch-env.sh" "$original_env" 2>/dev/null

    print_success "Production migrations deployed successfully!"
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
    echo "Database Tools - Missing Table Development Utility"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  backup [env]                    Create backup for specified environment (local|prod)"
    echo "  restore [backup_file] [env]     Restore from backup to specified environment"
    echo "  list                            List available backups"
    echo "  migrate [env]                   Deploy pending migrations (default: prod)"
    echo "  reset [env]                     Reset database and repopulate with basic data"
    echo "  cleanup [keep_count]            Clean up old backups (default: keep 10)"
    echo "  help                            Show this help message"
    echo ""
    echo "Environment Options:"
    echo "  local     Local Supabase (default) - requires 'npx supabase start'"
    echo "  prod      Cloud production environment"
    echo ""
    echo "Examples:"
    echo "  $0 backup                                    # Create backup for current environment"
    echo "  $0 backup prod                               # Create backup for prod environment"
    echo "  $0 restore                                   # Restore latest backup to current environment"
    echo "  $0 restore backup_file.json prod             # Restore specific backup to prod environment"
    echo "  $0 list                                      # List all backups"
    echo "  $0 reset local                               # Reset local database"
    echo "  $0 migrate                                   # Deploy pending migrations to prod"
    echo "  $0 migrate local                              # Apply migrations locally"
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
    migrate)
        deploy_migrations "$2"
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
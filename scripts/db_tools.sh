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

# Create a backup
backup_database() {
    print_header "Creating Database Backup"
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
    SQL_BACKUP_FILE="backups/database_backup_${TIMESTAMP}.sql"
    
    npx supabase db dump --local --data-only --file "$SQL_BACKUP_FILE"
    
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
    
    if [ -n "$backup_file" ]; then
        print_header "Restoring Database from $backup_file"
        cd "$PROJECT_ROOT/backend" || exit 1
        uv run python ../scripts/restore_database.py "$backup_file"
    else
        print_header "Restoring Database from Latest Backup"
        cd "$PROJECT_ROOT/backend" || exit 1
        uv run python ../scripts/restore_database.py --latest
    fi
    
    if [ $? -eq 0 ]; then
        print_success "Restore completed successfully"
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
    print_header "Resetting Database and Restoring from Latest Backup"
    
    # First create a backup
    print_warning "Creating backup before reset..."
    backup_database
    
    # Reset database
    print_warning "Resetting database..."
    cd "$PROJECT_ROOT" || exit 1
    npx supabase db reset
    
    # Restore real data from latest backup instead of creating sample data
    print_warning "Restoring real data from latest backup..."
    restore_database
    
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
    echo "  backup                    Create dual backup (JSON + SQL) for local database"
    echo "  backup-prod               Create production backup (remote database)"
    echo "  restore [backup_file]     Restore from backup (latest if no file specified)"
    echo "  list                      List available backups"
    echo "  reset                     Reset database and repopulate with basic data"
    echo "  cleanup [keep_count]      Clean up old backups (default: keep 10)"
    echo "  help                      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 backup                                    # Create local dual backup"
    echo "  $0 backup-prod                              # Create production backup"
    echo "  $0 restore                                   # Restore from latest backup"
    echo "  $0 restore database_backup_20231220_143022.json  # Restore specific backup"
    echo "  $0 list                                      # List all backups"
    echo "  $0 reset                                     # Reset and repopulate"
    echo "  $0 cleanup 5                                 # Keep only 5 most recent backups"
    echo ""
}

# Main script logic
check_environment

case "${1:-help}" in
    backup)
        backup_database
        ;;
    restore)
        restore_database "$2"
        ;;
    list)
        list_backups
        ;;
    reset)
        reset_and_populate
        ;;
    cleanup)
        cleanup_backups "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
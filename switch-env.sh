#!/bin/bash
# Environment Switcher Script for Missing Table Development

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Config file to persist environment choice
ENV_CONFIG_FILE="$SCRIPT_DIR/.current-env"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

show_help() {
    echo "Environment Switcher for Missing Table Development"
    echo ""
    echo "Usage: $0 [ENVIRONMENT]"
    echo ""
    echo "Environments:"
    echo "  local    Use local Supabase (requires 'npx supabase start')"
    echo "  prod     Use cloud Supabase production (missingtable.com)"
    echo "  status   Show current environment configuration"
    echo "  help     Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 local     # Switch to local development"
    echo "  $0 prod      # Switch to production (cloud)"
    echo "  $0 status    # Show current environment"
    echo ""
    echo "What this script does:"
    echo "  - Sets APP_ENV environment variable for current session"
    echo "  - Updates shell export in ~/.bashrc or ~/.zshrc"
    echo "  - Shows which environment files will be loaded"
    echo ""
}

get_current_env() {
    # Priority: 1) .current-env file (set by switch-env.sh), 2) APP_ENV env var, 3) default to local
    if [ -f "$ENV_CONFIG_FILE" ]; then
        cat "$ENV_CONFIG_FILE"
    elif [ -n "$APP_ENV" ]; then
        echo "$APP_ENV"
    else
        echo "local"
    fi
}

show_status() {
    print_header "Current Environment Status"

    current_env=$(get_current_env)
    echo "Current APP_ENV: $current_env"

    # Check which files exist
    echo ""
    echo "Available environment files:"
    for env in local prod; do
        backend_file="$SCRIPT_DIR/backend/.env.$env"
        frontend_file="$SCRIPT_DIR/frontend/.env.$env"

        if [ -f "$backend_file" ] && [ -f "$frontend_file" ]; then
            if [ "$env" = "$current_env" ]; then
                echo -e "  ${GREEN}✅ $env (ACTIVE)${NC}"
            else
                echo -e "  ✅ $env"
            fi
        else
            echo -e "  ${RED}❌ $env (missing files)${NC}"
        fi
    done

    # Show what would be loaded
    echo ""
    echo "Environment files that would be loaded:"
    echo "  Backend:  .env.$current_env"
    echo "  Frontend: .env.$current_env"

    # Check if Supabase is running for local env
    if [ "$current_env" = "local" ]; then
        echo ""
        if curl -s http://127.0.0.1:54331/health > /dev/null 2>&1; then
            print_success "Local Supabase is running on port 54331"
        else
            print_warning "Local Supabase is not running. Run 'npx supabase start' to start it."
        fi
    fi
}

switch_environment() {
    local target_env="$1"

    # Validate environment
    if [ "$target_env" != "local" ] && [ "$target_env" != "prod" ]; then
        print_error "Invalid environment: $target_env"
        echo "Valid environments: local, prod"
        exit 1
    fi

    # Check if environment files exist
    backend_file="$SCRIPT_DIR/backend/.env.$target_env"
    frontend_file="$SCRIPT_DIR/frontend/.env.$target_env"

    if [ ! -f "$backend_file" ]; then
        print_error "Backend environment file not found: $backend_file"
        exit 1
    fi

    if [ ! -f "$frontend_file" ]; then
        print_error "Frontend environment file not found: $frontend_file"
        exit 1
    fi

    print_header "Switching to $target_env environment"

    # Write to config file (persists across sessions without needing to source anything)
    echo "$target_env" > "$ENV_CONFIG_FILE"
    print_success "Saved environment to .current-env"

    # Update shell configuration
    update_shell_config "$target_env"

    # Set environment variable for current session by sourcing the updated config
    # Determine which shell config was updated
    user_shell=$(basename "$SHELL")
    if [ "$user_shell" = "zsh" ]; then
        shell_config="$HOME/.zshrc"
    elif [ "$user_shell" = "bash" ]; then
        shell_config="$HOME/.bashrc"
    fi

    # Source the config if it exists
    if [ -f "$shell_config" ]; then
        source "$shell_config"
    fi

    # Also export directly for good measure
    export APP_ENV="$target_env"

    print_success "Environment switched to: $target_env"

    # Show next steps
    echo ""
    echo "Next steps:"
    if [ "$target_env" = "local" ]; then
        echo "  1. Restart services: ./missing-table.sh restart"
        echo "  2. Start local Supabase (if needed): npx supabase start"
        echo "  3. Restore data (if needed): ./scripts/db_tools.sh restore"
    elif [ "$target_env" = "prod" ]; then
        echo "  1. Restart services: ./missing-table.sh restart"
        echo "  2. Verify cloud connection works"
        print_warning "Production environment - use with caution!"
    fi

    echo ""
    echo -e "${BLUE}Note:${NC} Services will use new environment after restart."
    echo -e "${BLUE}Note:${NC} New terminal sessions will use $target_env by default."
    echo -e "${BLUE}Note:${NC} Run 'source ~/.zshrc' to update current terminal session."
}

update_shell_config() {
    local target_env="$1"

    # Determine shell config file by checking user's actual shell
    user_shell=$(basename "$SHELL")

    if [ "$user_shell" = "zsh" ]; then
        shell_config="$HOME/.zshrc"
    elif [ "$user_shell" = "bash" ]; then
        shell_config="$HOME/.bashrc"
    else
        print_warning "Unknown shell ($user_shell). Please manually add 'export APP_ENV=$target_env' to your shell configuration."
        return
    fi

    # Remove any existing APP_ENV export
    if [ -f "$shell_config" ]; then
        # Create backup
        cp "$shell_config" "$shell_config.backup.$(date +%Y%m%d_%H%M%S)"

        # Remove existing APP_ENV lines
        grep -v "^export APP_ENV=" "$shell_config" > "$shell_config.tmp"
        mv "$shell_config.tmp" "$shell_config"
    fi

    # Add new APP_ENV export
    echo "export APP_ENV=$target_env" >> "$shell_config"

    print_success "Updated $shell_config with APP_ENV=$target_env"
}

# Main script logic
case "${1:-help}" in
    local|prod)
        switch_environment "$1"
        ;;
    status)
        show_status
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
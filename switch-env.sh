#!/bin/bash
# Environment Switcher Script for Missing Table Development

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Unified config file
MT_CONFIG_FILE="$SCRIPT_DIR/.mt-config"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- .mt-config helpers ---

# Read a key from .mt-config, return default if missing
mt_config_get() {
    local key="$1"
    local default="$2"
    if [ -f "$MT_CONFIG_FILE" ]; then
        local value
        value=$(grep "^${key}=" "$MT_CONFIG_FILE" 2>/dev/null | head -1 | cut -d'=' -f2-)
        if [ -n "$value" ]; then
            echo "$value"
            return
        fi
    fi
    echo "$default"
}

# Write/update a key in .mt-config
mt_config_set() {
    local key="$1"
    local value="$2"
    if [ -f "$MT_CONFIG_FILE" ]; then
        # Remove existing key line
        grep -v "^${key}=" "$MT_CONFIG_FILE" > "$MT_CONFIG_FILE.tmp"
        mv "$MT_CONFIG_FILE.tmp" "$MT_CONFIG_FILE"
    else
        # Create new config with header
        echo "# Missing Table local environment config" > "$MT_CONFIG_FILE"
    fi
    echo "${key}=${value}" >> "$MT_CONFIG_FILE"
}

# --- End helpers ---

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}$1${NC}"
}

print_error() {
    echo -e "${RED}$1${NC}"
}

show_help() {
    echo "Environment Switcher for Missing Table Development"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Supabase Commands:"
    echo "  local              Use local Supabase (requires 'npx supabase start')"
    echo "  prod               Use cloud Supabase production (missingtable.com)"
    echo "  supabase local     Explicit: use local Supabase"
    echo "  supabase prod      Explicit: use prod Supabase"
    echo ""
    echo "Redis Commands:"
    echo "  redis local        Use Redis in local k3s (port-forward to Rancher Desktop)"
    echo "  redis cloud        Use Redis in cloud cluster (port-forward to cloud k8s)"
    echo ""
    echo "Cloud Context Commands:"
    echo "  cloud-context <name>   Set the kubectl context for cloud operations"
    echo ""
    echo "Other Commands:"
    echo "  status             Show current Supabase, Redis, and cloud context configuration"
    echo "  help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 local                          # Switch Supabase to local (Redis unchanged)"
    echo "  $0 prod                           # Switch Supabase to prod (Redis unchanged)"
    echo "  $0 supabase prod                  # Explicit: Switch Supabase to prod"
    echo "  $0 redis local                    # Switch Redis to local k3s"
    echo "  $0 redis cloud                    # Switch Redis to cloud cluster"
    echo "  $0 cloud-context lke560651-ctx    # Set cloud kubectl context"
    echo "  $0 status                         # Show current configuration"
    echo ""
    echo "Typical Workflow:"
    echo "  $0 cloud-context lke560651-ctx    # Set once when switching providers"
    echo "  $0 supabase prod                  # Use production database"
    echo "  $0 redis local                    # Use local k3s Redis for caching"
    echo "  ./missing-table.sh start --watch"
    echo ""
}

get_current_env() {
    # Priority: 1) .mt-config (set by switch-env.sh), 2) APP_ENV env var, 3) default to local
    local config_val
    config_val=$(mt_config_get supabase_env "")
    if [ -n "$config_val" ]; then
        echo "$config_val"
    elif [ -n "$APP_ENV" ]; then
        echo "$APP_ENV"
    else
        echo "local"
    fi
}

get_current_redis() {
    mt_config_get redis_source local
}

show_status() {
    print_header "Current Environment Status"

    current_env=$(get_current_env)
    current_redis=$(get_current_redis)
    cloud_ctx=$(mt_config_get cloud_context "")
    local_ctx=$(mt_config_get local_context rancher-desktop)

    echo ""
    echo -e "${YELLOW}Supabase:${NC}"
    echo -e "  Source: ${GREEN}$current_env${NC}"

    # Check which files exist
    echo ""
    echo "  Available environment files:"
    for env in local prod; do
        backend_file="$SCRIPT_DIR/backend/.env.$env"
        frontend_file="$SCRIPT_DIR/frontend/.env.$env"

        if [ -f "$backend_file" ] && [ -f "$frontend_file" ]; then
            if [ "$env" = "$current_env" ]; then
                echo -e "    ${GREEN}$env (ACTIVE)${NC}"
            else
                echo -e "    $env"
            fi
        else
            echo -e "    ${RED}$env (missing files)${NC}"
        fi
    done

    # Show what would be loaded
    echo ""
    echo "  Environment files that would be loaded:"
    echo "    Backend:  .env.$current_env"
    echo "    Frontend: .env.$current_env"

    # Check if Supabase is running for local env
    if [ "$current_env" = "local" ]; then
        echo ""
        if curl -s http://127.0.0.1:54321/health > /dev/null 2>&1; then
            print_success "  Local Supabase is running on port 54321"
        else
            print_warning "  Local Supabase is not running. Run 'npx supabase start' to start it."
        fi
    fi

    echo ""
    echo -e "${YELLOW}Redis:${NC}"
    if [ "$current_redis" = "local" ]; then
        echo -e "  Source: ${GREEN}local${NC} (k3s via $local_ctx)"
        echo "  Context: $local_ctx"
    elif [ "$current_redis" = "cloud" ]; then
        if [ -n "$cloud_ctx" ]; then
            echo -e "  Source: ${GREEN}cloud${NC} (cloud cluster)"
            echo "  Context: $cloud_ctx"
        else
            echo -e "  Source: ${GREEN}cloud${NC} (cloud cluster)"
            echo -e "  Context: ${RED}not configured${NC}"
            echo -e "  ${BLUE}Tip:${NC} Run '$0 cloud-context <name>' to set the cloud kubectl context"
        fi
    else
        echo -e "  Source: ${YELLOW}$current_redis${NC} (unknown)"
    fi

    echo ""
    echo -e "${YELLOW}Cloud Context:${NC}"
    if [ -n "$cloud_ctx" ]; then
        echo -e "  kubectl context: ${GREEN}$cloud_ctx${NC}"
    else
        echo -e "  kubectl context: ${YELLOW}not configured${NC}"
        echo -e "  ${BLUE}Tip:${NC} Run '$0 cloud-context <name>' to set the cloud kubectl context"
    fi

    echo ""
    echo -e "${YELLOW}Local Context:${NC}"
    echo -e "  kubectl context: ${GREEN}$local_ctx${NC}"

    echo ""
    echo -e "${BLUE}Tip:${NC} Use './switch-env.sh supabase <local|prod>' to change Supabase"
    echo -e "${BLUE}Tip:${NC} Use './switch-env.sh redis <local|cloud>' to change Redis"
    echo -e "${BLUE}Tip:${NC} Use './switch-env.sh cloud-context <name>' to set cloud context"
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

    # Write to .mt-config
    mt_config_set supabase_env "$target_env"
    print_success "Saved environment to .mt-config"

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

switch_redis() {
    local target_redis="$1"

    # Validate redis source
    if [ "$target_redis" != "local" ] && [ "$target_redis" != "cloud" ]; then
        print_error "Invalid Redis source: $target_redis"
        echo "Valid sources: local, cloud"
        echo "  local = Redis in local k3s (Rancher Desktop)"
        echo "  cloud = Redis in cloud cluster"
        exit 1
    fi

    print_header "Switching Redis to $target_redis"

    # Write to .mt-config
    mt_config_set redis_source "$target_redis"
    print_success "Saved Redis source to .mt-config"

    # Show context information
    if [ "$target_redis" = "local" ]; then
        local local_ctx
        local_ctx=$(mt_config_get local_context rancher-desktop)
        echo ""
        echo "Redis will connect to: local k3s ($local_ctx)"
        echo "Kubectl context: $local_ctx"
    elif [ "$target_redis" = "cloud" ]; then
        local cloud_ctx
        cloud_ctx=$(mt_config_get cloud_context "")
        echo ""
        echo "Redis will connect to: cloud cluster"
        if [ -n "$cloud_ctx" ]; then
            echo "Kubectl context: $cloud_ctx"
        else
            print_warning "Cloud context not configured. Run '$0 cloud-context <name>' to set it."
        fi
    fi

    echo ""
    echo "Next steps:"
    echo "  1. Restart services: ./missing-table.sh restart"
    echo ""
    print_success "Redis source switched to: $target_redis"
}

switch_cloud_context() {
    local context_name="$1"

    if [ -z "$context_name" ]; then
        print_error "Missing context name. Usage: $0 cloud-context <context-name>"
        echo ""
        echo "Examples:"
        echo "  $0 cloud-context lke560651-ctx          # Linode LKE"
        echo "  $0 cloud-context do-nyc1-missingtable   # DigitalOcean DOKS"
        echo ""
        echo "List available contexts with: kubectl config get-contexts"
        exit 1
    fi

    print_header "Setting cloud kubectl context"

    mt_config_set cloud_context "$context_name"
    print_success "Cloud context set to: $context_name"

    echo ""
    echo "This context will be used for:"
    echo "  - Redis cloud port-forwarding"
    echo "  - Any cloud kubectl operations in missing-table.sh"
    echo ""
    echo -e "${BLUE}Tip:${NC} Verify with: kubectl --context=$context_name cluster-info"
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
        # Backward compatible: switch Supabase environment
        switch_environment "$1"
        ;;
    supabase)
        # Explicit supabase command
        if [ -z "$2" ]; then
            print_error "Missing environment. Usage: $0 supabase <local|prod>"
            exit 1
        fi
        switch_environment "$2"
        ;;
    redis)
        # Redis source command
        if [ -z "$2" ]; then
            print_error "Missing redis source. Usage: $0 redis <local|cloud>"
            exit 1
        fi
        switch_redis "$2"
        ;;
    cloud-context)
        switch_cloud_context "$2"
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

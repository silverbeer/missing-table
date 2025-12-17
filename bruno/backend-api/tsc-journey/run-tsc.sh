#!/bin/bash
# TSC Journey Test Runner for Bruno
# Loads secrets from .env.tsc and runs Bruno tests
#
# Usage:
#   ./run-tsc.sh                    # Run all phases including cleanup
#   ./run-tsc.sh --skip-cleanup     # Run journey only (for UI testing)
#   ./run-tsc.sh cleanup            # Run cleanup only
#   ./run-tsc.sh 00-admin-setup     # Run specific phase

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/backend/tests/tsc/.env.tsc"
BRUNO_COLLECTION="$SCRIPT_DIR/.."  # bruno/backend-api (collection root with bruno.json)
TSC_JOURNEY_DIR="tsc-journey"       # Relative path from collection root

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env.tsc exists
if [ ! -f "$ENV_FILE" ]; then
    echo_error ".env.tsc not found at: $ENV_FILE"
    echo_info "Create it from the example:"
    echo "  cp $PROJECT_ROOT/backend/tests/tsc/.env.tsc.example $ENV_FILE"
    echo "  # Then edit $ENV_FILE with your passwords"
    exit 1
fi

# Load environment variables from .env.tsc
echo_info "Loading secrets from .env.tsc..."
set -a  # automatically export all variables
source "$ENV_FILE"
set +a

# Build env-var arguments for Bruno CLI
# Bruno uses --env-var flag to pass secrets
ENV_VARS=""
ENV_VARS="$ENV_VARS --env-var existing_admin_pass=${existing_admin_pass:-tom123!}"
ENV_VARS="$ENV_VARS --env-var tsc_admin_pass=${tsc_admin_pass:-tsc_b_admin123!}"
ENV_VARS="$ENV_VARS --env-var club_manager_pass=${club_manager_pass:-tsc_b_club_mgr123!}"
ENV_VARS="$ENV_VARS --env-var team_manager_pass=${team_manager_pass:-tsc_b_team_mgr123!}"
ENV_VARS="$ENV_VARS --env-var player_pass=${player_pass:-tsc_b_player123!}"
ENV_VARS="$ENV_VARS --env-var club_fan_pass=${club_fan_pass:-tsc_b_club_fan123!}"
ENV_VARS="$ENV_VARS --env-var team_fan_pass=${team_fan_pass:-tsc_b_team_fan123!}"

# Parse arguments
SKIP_CLEANUP=false
RUN_PHASE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        cleanup|99-cleanup)
            echo_error "Standalone cleanup not supported (Bruno can't persist IDs between runs)"
            echo_info "Use the Python cleanup script instead:"
            echo "  cd backend && uv run python scripts/tsc_cleanup.py --prefix tsc_b_"
            exit 1
            ;;
        00-admin-setup|01-club-manager|02-team-manager|03-player|04-fan)
            RUN_PHASE="$1"
            shift
            ;;
        *)
            echo_error "Unknown option: $1"
            echo "Usage: $0 [--skip-cleanup] [phase]"
            echo "Phases: 00-admin-setup, 01-club-manager, 02-team-manager, 03-player, 04-fan, cleanup"
            exit 1
            ;;
    esac
done

# Check if bru CLI is available
if ! command -v bru &> /dev/null; then
    echo_error "Bruno CLI (bru) not found. Install it with:"
    echo "  npm install -g @usebruno/cli"
    exit 1
fi

# Function to run a phase
run_phase() {
    local phase=$1
    local phase_path="$TSC_JOURNEY_DIR/$phase"
    local full_path="$BRUNO_COLLECTION/$phase_path"

    if [ ! -d "$full_path" ]; then
        echo_warn "Phase directory not found: $full_path"
        return 1
    fi

    echo_info "Running phase: $phase"
    # Bruno CLI must run from collection root (where bruno.json is)
    cd "$BRUNO_COLLECTION"
    # shellcheck disable=SC2086
    bru run "$phase_path" --env tsc $ENV_VARS
}

# Function to run all phases in a single bru command (preserves env vars)
run_all_phases() {
    local journey_path="$TSC_JOURNEY_DIR"
    local full_path="$BRUNO_COLLECTION/$journey_path"

    echo_info "Running all phases in single execution (env vars persist between phases)"
    cd "$BRUNO_COLLECTION"
    # -r flag enables recursive folder execution
    # shellcheck disable=SC2086
    bru run "$journey_path" -r --env tsc $ENV_VARS
}

# Run tests
if [ -n "$RUN_PHASE" ]; then
    # Run specific phase
    run_phase "$RUN_PHASE"
else
    if [ "$SKIP_CLEANUP" = true ]; then
        # Temporarily move cleanup folder OUTSIDE tsc-journey so bru -r skips it
        # This preserves env vars across all phases in a single execution
        CLEANUP_DIR="$SCRIPT_DIR/99-cleanup"
        CLEANUP_HIDDEN="$BRUNO_COLLECTION/.tsc-cleanup-temp"  # Parent dir

        # Function to restore cleanup folder (called on exit)
        restore_cleanup() {
            if [ -d "$CLEANUP_HIDDEN" ]; then
                mv "$CLEANUP_HIDDEN" "$CLEANUP_DIR"
                echo_info "Restored cleanup folder"
            fi
        }

        # Ensure cleanup folder is restored even if script fails
        trap restore_cleanup EXIT

        if [ -d "$CLEANUP_DIR" ]; then
            echo_info "Moving cleanup folder temporarily..."
            mv "$CLEANUP_DIR" "$CLEANUP_HIDDEN"
        fi

        # Run all phases at once (single bru command preserves env vars)
        echo_info "Running phases 00-04 in single execution (env vars persist)"
        cd "$BRUNO_COLLECTION"
        # shellcheck disable=SC2086
        bru run "$TSC_JOURNEY_DIR" -r --env tsc $ENV_VARS

        echo_info "Skipping cleanup phase (--skip-cleanup)"
        echo_info "Run cleanup later with: $0 cleanup"
    else
        # Run all phases at once (single bru command preserves env vars)
        run_all_phases
    fi
fi

echo_info "Done!"

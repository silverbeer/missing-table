#!/bin/bash

# Missing Table Service Management Script
# Usage: ./missing-table.sh {start|stop|restart|status|logs}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Service configuration
BACKEND_PORT=8000
FRONTEND_PORT=8080
REDIS_PORT=6379
PID_DIR="$HOME/.missing-table"
BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
REDIS_PF_PID_FILE="$PID_DIR/redis-portforward.pid"
LOG_DIR="$PID_DIR/logs"

# k3s/k8s configuration for Redis
REDIS_NAMESPACE="missing-table"
REDIS_SERVICE="missing-table-redis"

# Kubectl context configuration
K3S_CONTEXT="rancher-desktop"              # Local k3s context (Rancher Desktop)
DOKS_CONTEXT="do-nyc1-missingtable-dev"    # DOKS context

# Create directories if they don't exist
mkdir -p "$PID_DIR" "$LOG_DIR"

# Config files for persistent environment (shared with switch-env.sh)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_CONFIG_FILE="$SCRIPT_DIR/.current-env"
REDIS_CONFIG_FILE="$SCRIPT_DIR/.current-redis"

# Get current environment from config file or env var
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

# Get current Redis source from config file
get_current_redis() {
    # Read from .current-redis file, default to "local" for backward compatibility
    if [ -f "$REDIS_CONFIG_FILE" ]; then
        cat "$REDIS_CONFIG_FILE"
    else
        echo "local"
    fi
}

# Function to print usage
usage() {
    echo -e "${BLUE}Missing Table Service Manager${NC}"
    echo ""
    echo -e "${YELLOW}Usage:${NC} $0 {start|stop|restart|status|logs|tail|klogs}"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo "  start [--watch]    - Start backend, frontend, and Redis port-forward"
    echo "  stop               - Stop all running services and Redis port-forward"
    echo "  restart [--watch]  - Stop and start all services"
    echo "                       --watch: Enable auto-reload on code changes"
    echo "  status             - Show status of all services (incl. Redis in k3s)"
    echo "  logs               - Show recent logs from services"
    echo "  tail               - Follow logs in real-time (Ctrl+C to stop)"
    echo ""
    echo -e "${YELLOW}Kubernetes Log Commands:${NC}"
    echo "  klogs [options]    - Tail backend logs from Kubernetes (pretty-printed)"
    echo "                       --since=1h   : Show logs from last hour (default: 10m)"
    echo "                       --tail=100   : Show last N lines first (default: 50)"
    echo "                       --all        : Show all pods (default: backend only)"
    echo ""
    echo -e "${YELLOW}Redis:${NC}"
    echo "  Redis source is configured via './switch-env.sh redis <local|cloud>'"
    echo "    local = Redis in local k3s (Rancher Desktop)"
    echo "    cloud = Redis in DOKS cluster"
    echo "  Port-forwarded to localhost:6379. If Redis not deployed, caching disabled."
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  $0 start --watch   # With auto-reload for development"
    echo "  $0 start           # Without auto-reload"
    echo "  $0 status"
    echo "  $0 tail"
    echo ""
}

# Function to check if a port is in use
port_in_use() {
    lsof -i :$1 > /dev/null 2>&1
}

# Function to get process info by port
get_process_by_port() {
    lsof -ti :$1 2>/dev/null
}

# Function to get all missing-table related processes
get_missing_table_processes() {
    # Find processes related to missing-table (various ways Claude might start them)
    local pids=""

    # Method 1: By port
    local backend_pid=$(get_process_by_port $BACKEND_PORT)
    local frontend_pid=$(get_process_by_port $FRONTEND_PORT)

    # Method 2: By process name/command line
    local python_pids=$(pgrep -f "python.*app\.py" 2>/dev/null)
    local node_pids=$(pgrep -f "node.*serve" 2>/dev/null)
    local uv_pids=$(pgrep -f "uv run python app\.py" 2>/dev/null)

    # Combine all PIDs and remove duplicates
    pids="$backend_pid $frontend_pid $python_pids $node_pids $uv_pids"
    echo $pids | tr ' ' '\n' | sort -u | grep -v "^$" | tr '\n' ' '
}

# Function to kill a process by PID
kill_process() {
    local pid=$1
    local name=$2

    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo -e "${YELLOW}Stopping $name (PID: $pid)...${NC}"
        kill "$pid" 2>/dev/null

        # Wait up to 10 seconds for graceful shutdown
        local count=0
        while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
            sleep 1
            count=$((count + 1))
        done

        # Force kill if still running
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${RED}Force killing $name (PID: $pid)...${NC}"
            kill -9 "$pid" 2>/dev/null
        fi

        return 0
    else
        return 1
    fi
}

# Function to check if Redis pod is running in k3s (optionally with specific context)
redis_pod_running() {
    local context="${1:-}"
    local context_flag=""
    if [ -n "$context" ]; then
        context_flag="--context=$context"
    fi
    kubectl $context_flag get pod -n "$REDIS_NAMESPACE" -l app.kubernetes.io/component=redis --field-selector=status.phase=Running -o name 2>/dev/null | grep -q .
}

# Function to check if Redis is accessible locally
redis_accessible() {
    nc -z localhost $REDIS_PORT 2>/dev/null
}

# Function to get Redis pod status (optionally with specific context)
get_redis_status() {
    local context="${1:-}"
    local context_flag=""
    if [ -n "$context" ]; then
        context_flag="--context=$context"
    fi
    local pod_status=$(kubectl $context_flag get pod -n "$REDIS_NAMESPACE" -l app.kubernetes.io/component=redis -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
    if [ -z "$pod_status" ]; then
        echo "NOT_DEPLOYED"
    else
        echo "$pod_status"
    fi
}

# Function to start Redis port-forward to local k3s
start_redis_portforward() {
    echo -e "${YELLOW}Starting Redis port-forward to local k3s...${NC}"

    # Check if Redis pod is running in local k3s
    if ! redis_pod_running "$K3S_CONTEXT"; then
        echo -e "${RED}Redis pod is not running in local k3s${NC}"
        echo -e "${BLUE}Tip:${NC} Deploy Redis with: helm upgrade missing-table ./helm/missing-table --set redis.enabled=true -n missing-table"
        return 1
    fi

    # Check if already accessible
    if redis_accessible; then
        echo -e "${YELLOW}Redis already accessible on port $REDIS_PORT${NC}"
        return 0
    fi

    # Start port-forward in background
    local redis_pf_log="$LOG_DIR/redis-portforward.log"
    nohup kubectl --context="$K3S_CONTEXT" port-forward -n "$REDIS_NAMESPACE" "svc/$REDIS_SERVICE" "$REDIS_PORT:6379" > "$redis_pf_log" 2>&1 &
    local pf_pid=$!
    echo $pf_pid > "$REDIS_PF_PID_FILE"

    # Wait for port-forward to establish
    local count=0
    while [ $count -lt 5 ]; do
        if redis_accessible; then
            echo -e "${GREEN}Redis port-forward started to local k3s (PID: $pf_pid)${NC}"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    echo -e "${RED}Redis port-forward failed to start${NC}"
    return 1
}

# Function to start Redis port-forward to DOKS cloud cluster
start_cloud_redis_portforward() {
    echo -e "${YELLOW}Starting Redis port-forward to DOKS...${NC}"

    # Check if Redis pod is running in DOKS
    if ! redis_pod_running "$DOKS_CONTEXT"; then
        echo -e "${RED}Redis pod is not running in DOKS${NC}"
        echo -e "${BLUE}Tip:${NC} Ensure Redis is deployed in DOKS cluster"
        return 1
    fi

    # Check if already accessible
    if redis_accessible; then
        echo -e "${YELLOW}Redis already accessible on port $REDIS_PORT${NC}"
        return 0
    fi

    # Start port-forward in background
    local redis_pf_log="$LOG_DIR/redis-portforward.log"
    nohup kubectl --context="$DOKS_CONTEXT" port-forward -n "$REDIS_NAMESPACE" "svc/$REDIS_SERVICE" "$REDIS_PORT:6379" > "$redis_pf_log" 2>&1 &
    local pf_pid=$!
    echo $pf_pid > "$REDIS_PF_PID_FILE"

    # Wait for port-forward to establish
    local count=0
    while [ $count -lt 5 ]; do
        if redis_accessible; then
            echo -e "${GREEN}Redis port-forward started to DOKS (PID: $pf_pid)${NC}"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    echo -e "${RED}Redis port-forward to DOKS failed to start${NC}"
    return 1
}

# Function to stop Redis port-forward
stop_redis_portforward() {
    # Check PID file
    if [ -f "$REDIS_PF_PID_FILE" ]; then
        local pf_pid=$(cat "$REDIS_PF_PID_FILE")
        if [ -n "$pf_pid" ] && kill -0 "$pf_pid" 2>/dev/null; then
            echo -e "${YELLOW}Stopping Redis port-forward (PID: $pf_pid)...${NC}"
            kill "$pf_pid" 2>/dev/null
            rm -f "$REDIS_PF_PID_FILE"
            return 0
        fi
    fi

    # Also kill any orphaned port-forwards
    local pf_pids=$(pgrep -f "kubectl.*port-forward.*$REDIS_SERVICE" 2>/dev/null)
    if [ -n "$pf_pids" ]; then
        echo -e "${YELLOW}Stopping orphaned Redis port-forward processes...${NC}"
        echo "$pf_pids" | xargs kill 2>/dev/null
    fi

    rm -f "$REDIS_PF_PID_FILE"
}

# Function to start backend
start_backend() {
    local dev_mode="${1:-false}"
    echo -e "${YELLOW}Starting backend server...${NC}"

    # Check if already running
    if port_in_use $BACKEND_PORT; then
        local existing_pid=$(get_process_by_port $BACKEND_PORT)
        echo -e "${YELLOW}Backend already running on port $BACKEND_PORT (PID: $existing_pid)${NC}"
        return 0
    fi

    # Check if we're in the right directory
    if [ ! -d "backend" ]; then
        echo -e "${RED}Error: backend directory not found!${NC}"
        echo "Please run this script from the project root directory."
        return 1
    fi

    # Show current environment
    current_env="$(get_current_env)"
    echo "Using environment: $current_env"

    # Set environment variables for backend
    export LOG_LEVEL=info
    export APP_ENV="$current_env"
    export CACHE_ENABLED=true
    echo "Redis caching: ENABLED"

    cd backend

    # Start backend in background with logging
    local backend_log="$LOG_DIR/backend.log"
    echo "Backend logs: $backend_log"

    if command -v uv &> /dev/null; then
        if [ "$dev_mode" = "true" ]; then
            echo -e "${GREEN}Starting backend with auto-reload (uvicorn --reload)${NC}"
            APP_ENV="$current_env" nohup uv run uvicorn app:app --host 0.0.0.0 --port $BACKEND_PORT --reload --no-access-log > "$backend_log" 2>&1 &
        else
            APP_ENV="$current_env" nohup uv run python app.py > "$backend_log" 2>&1 &
        fi
    else
        echo -e "${YELLOW}uv not found, using python directly${NC}"
        APP_ENV="$current_env" nohup python app.py > "$backend_log" 2>&1 &
    fi

    local backend_pid=$!
    echo $backend_pid > "$BACKEND_PID_FILE"
    cd ..

    # Wait for backend to start
    echo "Waiting for backend to start..."
    local count=0
    while [ $count -lt 10 ]; do
        if port_in_use $BACKEND_PORT; then
            echo -e "${GREEN}Backend started successfully (PID: $backend_pid)${NC}"
            if [ "$dev_mode" = "true" ]; then
                echo -e "${GREEN}  Auto-reload: ENABLED (code changes will reload automatically)${NC}"
            fi
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    echo -e "${RED}Backend failed to start within 10 seconds${NC}"
    return 1
}

# Function to start frontend
start_frontend() {
    local dev_mode="${1:-false}"
    echo -e "${YELLOW}Starting frontend server...${NC}"

    # Check if already running
    if port_in_use $FRONTEND_PORT; then
        local existing_pid=$(get_process_by_port $FRONTEND_PORT)
        echo -e "${YELLOW}Frontend already running on port $FRONTEND_PORT (PID: $existing_pid)${NC}"
        return 0
    fi

    # Check if we're in the right directory
    if [ ! -d "frontend" ]; then
        echo -e "${RED}Error: frontend directory not found!${NC}"
        echo "Please run this script from the project root directory."
        return 1
    fi

    # Get current environment
    current_env="$(get_current_env)"
    export APP_ENV="$current_env"

    cd frontend

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo "Installing frontend dependencies..."
        npm install
    fi

    # Start frontend in background with logging
    local frontend_log="$LOG_DIR/frontend.log"
    echo "Frontend logs: $frontend_log"

    # Note: npm run serve already has hot-reload by default (Vue CLI)
    APP_ENV="$current_env" nohup npm run serve > "$frontend_log" 2>&1 &
    local frontend_pid=$!
    echo $frontend_pid > "$FRONTEND_PID_FILE"
    cd ..

    # Wait for frontend to start
    echo "Waiting for frontend to start..."
    local count=0
    while [ $count -lt 15 ]; do
        if port_in_use $FRONTEND_PORT; then
            echo -e "${GREEN}Frontend started successfully (PID: $frontend_pid)${NC}"
            echo -e "${GREEN}  Hot-reload: ENABLED (Vue files auto-reload by default)${NC}"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    echo -e "${RED}Frontend failed to start within 15 seconds${NC}"
    return 1
}

# Function to start all services
start_services() {
    local dev_mode="${1:-false}"

    if [ "$dev_mode" = "true" ]; then
        echo -e "${GREEN}Starting Missing Table application in DEVELOPMENT mode...${NC}\n"
    else
        echo -e "${GREEN}Starting Missing Table application...${NC}\n"
    fi

    # Check if we're in the right directory
    if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
        echo -e "${RED}Error: backend or frontend directory not found!${NC}"
        echo "Please run this script from the project root directory."
        return 1
    fi

    # Start Redis port-forward based on configured source
    local redis_source=$(get_current_redis)
    echo -e "Redis source: ${GREEN}$redis_source${NC}"

    if [ "$redis_source" = "cloud" ]; then
        # Port-forward to DOKS Redis
        if redis_pod_running "$DOKS_CONTEXT"; then
            start_cloud_redis_portforward
        else
            echo -e "${YELLOW}Redis not deployed in DOKS - caching will be disabled${NC}"
            echo -e "${BLUE}Tip:${NC} Ensure Redis is deployed in DOKS cluster"
            echo ""
        fi
    else
        # Default: port-forward to local k3s Redis
        if redis_pod_running "$K3S_CONTEXT"; then
            start_redis_portforward
        else
            echo -e "${YELLOW}Redis not deployed in local k3s - caching will be disabled${NC}"
            echo -e "${BLUE}Tip:${NC} To enable caching, deploy Redis with:"
            echo -e "  helm upgrade missing-table ./helm/missing-table --set redis.enabled=true -n missing-table"
            echo ""
        fi
    fi

    start_backend "$dev_mode"
    if [ $? -eq 0 ]; then
        start_frontend "$dev_mode"
        if [ $? -eq 0 ]; then
            echo -e "\n${GREEN}All services started successfully!${NC}"
            echo -e "Backend: http://localhost:$BACKEND_PORT"
            echo -e "Frontend: http://localhost:$FRONTEND_PORT"
            if [ "$dev_mode" = "true" ]; then
                echo -e "\n${GREEN}Development mode: Code changes will auto-reload${NC}"
                echo -e "  Backend: Python changes trigger uvicorn reload"
                echo -e "  Frontend: Vue files trigger hot module replacement"
            fi
            echo -e "\nUse '$0 status' to check service status"
            echo -e "Use '$0 logs' to view logs"
            echo -e "Use '$0 tail' to follow logs in real-time"
            echo -e "Use '$0 stop' to stop all services"
        fi
    fi
}

# Function to stop all services
stop_services() {
    echo -e "${YELLOW}Stopping Missing Table services...${NC}"

    local stopped=false

    # Get all related processes
    local all_pids=$(get_missing_table_processes)

    if [ -n "$all_pids" ]; then
        for pid in $all_pids; do
            if [ -n "$pid" ]; then
                # Try to determine what this process is
                local process_info=$(ps -p "$pid" -o comm= 2>/dev/null)
                kill_process "$pid" "$process_info"
                stopped=true
            fi
        done
    fi

    # Stop Redis port-forward
    stop_redis_portforward

    # Clean up PID files
    rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"

    if [ "$stopped" = true ]; then
        echo -e "${GREEN}All services stopped.${NC}"
    else
        echo -e "${YELLOW}No running services found.${NC}"
    fi
}

# Function to show service status
show_status() {
    echo -e "${BLUE}Missing Table Service Status${NC}"
    echo "================================"

    # Show current environment/database
    local current_env="$(get_current_env)"
    echo -e "\n${YELLOW}Environment:${NC}"
    echo -e "  Current: ${GREEN}$current_env${NC}"

    # Determine database connection based on environment
    if [ "$current_env" = "local" ]; then
        # Check if Supabase is running locally
        if curl -s http://127.0.0.1:54331/health > /dev/null 2>&1; then
            local supabase_url="http://127.0.0.1:54331"
            local studio_url="http://127.0.0.1:54333"
            echo -e "  Database: ${GREEN}Local Supabase${NC} ($supabase_url)"
            echo -e "  Studio UI: ${GREEN}$studio_url${NC}"
        else
            echo -e "  Database: ${RED}Local Supabase (not running)${NC}"
            echo -e "  ${BLUE}Tip:${NC} Start with 'npx supabase start'"
        fi
    elif [ "$current_env" = "dev" ]; then
        echo -e "  Database: ${GREEN}Cloud Supabase (dev)${NC}"
        # Extract Supabase URL from .env.dev if it exists
        if [ -f "backend/.env.dev" ]; then
            local supabase_url=$(grep "^SUPABASE_URL=" backend/.env.dev 2>/dev/null | cut -d '=' -f2)
            if [ -n "$supabase_url" ]; then
                # Extract project ref from URL (e.g., ppgxasqgqbnauvxozmjw from https://ppgxasqgqbnauvxozmjw.supabase.co)
                local project_ref=$(echo "$supabase_url" | sed -n 's|https://\([^.]*\)\.supabase\.co|\1|p')
                if [ -n "$project_ref" ]; then
                    echo -e "  Studio UI: ${GREEN}https://supabase.com/dashboard/project/$project_ref${NC}"
                fi
            fi
        fi
    elif [ "$current_env" = "prod" ]; then
        echo -e "  Database: ${GREEN}Cloud Supabase (prod)${NC}"
        # Extract Supabase URL from .env.prod if it exists
        if [ -f "backend/.env.prod" ]; then
            local supabase_url=$(grep "^SUPABASE_URL=" backend/.env.prod 2>/dev/null | cut -d '=' -f2)
            if [ -n "$supabase_url" ]; then
                local project_ref=$(echo "$supabase_url" | sed -n 's|https://\([^.]*\)\.supabase\.co|\1|p')
                if [ -n "$project_ref" ]; then
                    echo -e "  Studio UI: ${GREEN}https://supabase.com/dashboard/project/$project_ref${NC}"
                fi
            fi
        fi
    fi

    # Show how to switch environments
    echo -e "  ${BLUE}Tip:${NC} Use './switch-env.sh <local|dev|prod>' to change environment"

    # Backend status
    echo -e "\n${YELLOW}Backend (Port $BACKEND_PORT):${NC}"
    if port_in_use $BACKEND_PORT; then
        local backend_pid=$(get_process_by_port $BACKEND_PORT)
        echo -e "  Status: ${GREEN}RUNNING${NC} (PID: $backend_pid)"
        echo "  URL: http://localhost:$BACKEND_PORT"
    else
        echo -e "  Status: ${RED}STOPPED${NC}"
    fi

    # Frontend status
    echo -e "\n${YELLOW}Frontend (Port $FRONTEND_PORT):${NC}"
    if port_in_use $FRONTEND_PORT; then
        local frontend_pid=$(get_process_by_port $FRONTEND_PORT)
        echo -e "  Status: ${GREEN}RUNNING${NC} (PID: $frontend_pid)"
        echo "  URL: http://localhost:$FRONTEND_PORT"
    else
        echo -e "  Status: ${RED}STOPPED${NC}"
    fi

    # Redis status
    local redis_source=$(get_current_redis)
    echo -e "\n${YELLOW}Redis (Port $REDIS_PORT):${NC}"
    echo -e "  Source: ${GREEN}$redis_source${NC}"

    if [ "$redis_source" = "cloud" ]; then
        # Show DOKS Redis status
        echo "  Cluster: DOKS ($DOKS_CONTEXT)"
        local redis_status=$(get_redis_status "$DOKS_CONTEXT")
    else
        # Show local k3s Redis status
        echo "  Cluster: local k3s ($K3S_CONTEXT)"
        local redis_status=$(get_redis_status "$K3S_CONTEXT")
    fi

    case "$redis_status" in
        "Running")
            echo -e "  Pod: ${GREEN}RUNNING${NC} (namespace: $REDIS_NAMESPACE)"
            if redis_accessible; then
                local pf_pid=""
                if [ -f "$REDIS_PF_PID_FILE" ]; then
                    pf_pid=$(cat "$REDIS_PF_PID_FILE")
                fi
                if [ -n "$pf_pid" ] && kill -0 "$pf_pid" 2>/dev/null; then
                    echo -e "  Port-Forward: ${GREEN}ACTIVE${NC} (PID: $pf_pid)"
                else
                    echo -e "  Port-Forward: ${GREEN}ACTIVE${NC}"
                fi
                echo "  URL: redis://localhost:$REDIS_PORT"
            else
                echo -e "  Port-Forward: ${RED}INACTIVE${NC}"
                echo -e "  ${BLUE}Tip:${NC} Run '$0 start' to enable port-forwarding"
            fi
            ;;
        "NOT_DEPLOYED")
            echo -e "  Pod: ${YELLOW}NOT DEPLOYED${NC}"
            if [ "$redis_source" = "cloud" ]; then
                echo -e "  ${BLUE}Tip:${NC} Ensure Redis is deployed in DOKS cluster"
            else
                echo -e "  ${BLUE}Tip:${NC} Deploy with: helm upgrade missing-table ./helm/missing-table --set redis.enabled=true -n missing-table"
            fi
            ;;
        *)
            echo -e "  Pod: ${YELLOW}$redis_status${NC} (namespace: $REDIS_NAMESPACE)"
            ;;
    esac
    echo -e "  ${BLUE}Tip:${NC} Use './switch-env.sh redis <local|cloud>' to change Redis source"

    # Show all related processes
    local all_pids=$(get_missing_table_processes)
    if [ -n "$all_pids" ]; then
        echo -e "\n${YELLOW}Related Processes:${NC}"
        for pid in $all_pids; do
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                local cmd=$(ps -p "$pid" -o args= 2>/dev/null | cut -c1-80)
                echo "  PID $pid: $cmd"
            fi
        done
    fi

    echo ""
}

# Function to show logs
show_logs() {
    echo -e "${BLUE}Missing Table Service Logs${NC}"
    echo "=========================="

    if [ -f "$LOG_DIR/backend.log" ]; then
        echo -e "\n${YELLOW}Backend Logs (last 20 lines):${NC}"
        tail -20 "$LOG_DIR/backend.log"
    else
        echo -e "\n${YELLOW}No backend logs found${NC}"
    fi

    if [ -f "$LOG_DIR/frontend.log" ]; then
        echo -e "\n${YELLOW}Frontend Logs (last 20 lines):${NC}"
        tail -20 "$LOG_DIR/frontend.log"
    else
        echo -e "\n${YELLOW}No frontend logs found${NC}"
    fi

    echo ""
}

# Function to colorize JSON log output
colorize_json_log() {
    local line="$1"
    local timestamp level message

    # Try to parse JSON log line
    if echo "$line" | jq -e . >/dev/null 2>&1; then
        timestamp=$(echo "$line" | jq -r '.timestamp // .time // .ts // empty' 2>/dev/null)
        level=$(echo "$line" | jq -r '.level // .levelname // .severity // empty' 2>/dev/null | tr '[:lower:]' '[:upper:]')
        message=$(echo "$line" | jq -r '.message // .msg // empty' 2>/dev/null)

        # Format timestamp (keep just time portion if it's a full timestamp)
        if [ -n "$timestamp" ]; then
            timestamp=$(echo "$timestamp" | sed 's/.*T\([0-9:]*\).*/\1/' | cut -c1-8)
        else
            timestamp=$(date '+%H:%M:%S')
        fi

        # Colorize based on level
        case "$level" in
            ERROR|CRITICAL|FATAL)
                echo -e "${RED}[$timestamp] $level${NC} $message"
                ;;
            WARNING|WARN)
                echo -e "${YELLOW}[$timestamp] $level${NC} $message"
                ;;
            INFO)
                echo -e "${GREEN}[$timestamp] $level${NC} $message"
                ;;
            DEBUG|TRACE)
                echo -e "${BLUE}[$timestamp] $level${NC} $message"
                ;;
            *)
                echo -e "[$timestamp] $line"
                ;;
        esac
    else
        # Not JSON, output as-is with timestamp
        echo -e "[$(date '+%H:%M:%S')] $line"
    fi
}

# Function to tail Kubernetes logs (DOKS/cloud)
tail_k8s_logs() {
    local since="${1:-10m}"
    local tail_lines="${2:-50}"
    local show_all="${3:-false}"
    local namespace="$REDIS_NAMESPACE"  # Same namespace as app

    echo -e "${BLUE}Missing Table Kubernetes Logs${NC}"
    echo "=============================="

    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}kubectl not found. Please install kubectl first.${NC}"
        return 1
    fi

    # Check if we can connect to the cluster
    if ! kubectl cluster-info &>/dev/null; then
        echo -e "${RED}Cannot connect to Kubernetes cluster.${NC}"
        echo -e "${BLUE}Tip:${NC} Make sure your kubeconfig is set up correctly"
        return 1
    fi

    # Determine pod selector
    local pod_selector="app.kubernetes.io/name=missing-table-backend"
    if [ "$show_all" = "true" ]; then
        pod_selector="app.kubernetes.io/instance=missing-table"
    fi

    # Get current context for display
    local context=$(kubectl config current-context 2>/dev/null)
    echo -e "${YELLOW}Cluster:${NC} $context"
    echo -e "${YELLOW}Namespace:${NC} $namespace"
    echo -e "${YELLOW}Since:${NC} $since"
    echo -e "${YELLOW}Initial lines:${NC} $tail_lines"
    echo ""

    # Check if stern is available (preferred)
    if command -v stern &> /dev/null; then
        echo -e "${GREEN}Using stern for log streaming...${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        echo ""

        if [ "$show_all" = "true" ]; then
            # Match all missing-table pods
            stern "missing-table" \
                --namespace "$namespace" \
                --since "$since" \
                --tail "$tail_lines" \
                --output short \
                --color always \
                --template '{{color .PodColor .PodName}} {{color .ContainerColor .ContainerName}} {{.Message}}{{"\n"}}'
        else
            # Match backend pods only
            stern "missing-table-backend" \
                --namespace "$namespace" \
                --since "$since" \
                --tail "$tail_lines" \
                --output short \
                --color always \
                --template '{{color .PodColor .PodName}} {{.Message}}{{"\n"}}'
        fi
    else
        # Fallback to kubectl with colorization
        echo -e "${YELLOW}stern not found, using kubectl (install stern for better experience)${NC}"
        echo -e "${BLUE}Tip:${NC} brew install stern"
        echo ""

        # Get backend pod name
        local pod_name=$(kubectl get pods -n "$namespace" -l "$pod_selector" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

        if [ -z "$pod_name" ]; then
            echo -e "${RED}No backend pods found in namespace $namespace${NC}"
            echo -e "${BLUE}Tip:${NC} Check if the application is deployed with:"
            echo "  kubectl get pods -n $namespace"
            return 1
        fi

        echo -e "${GREEN}Tailing logs from pod: $pod_name${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        echo ""
        echo -e "${BLUE}─────────────────────────────────────────────────────${NC}"

        # Check if jq is available for JSON parsing
        if command -v jq &> /dev/null; then
            kubectl logs -f "$pod_name" -n "$namespace" --since="$since" --tail="$tail_lines" 2>&1 | while IFS= read -r line; do
                colorize_json_log "$line"
            done
        else
            # No jq, just add timestamps
            kubectl logs -f "$pod_name" -n "$namespace" --since="$since" --tail="$tail_lines" 2>&1 | while IFS= read -r line; do
                echo "[$(date '+%H:%M:%S')] $line"
            done
        fi
    fi
}

# Additional colors for log formatting
CYAN='\033[0;36m'
GRAY='\033[0;90m'
BOLD='\033[1m'
DIM='\033[2m'

# Function to format a JSON log line with colors
format_json_log() {
    local line="$1"
    local source="$2"  # "backend" or "frontend"

    # Check if line looks like JSON (starts with {)
    if [[ "$line" == "{"* ]]; then
        # Try to parse with jq if available
        if command -v jq &> /dev/null; then
            local level=$(echo "$line" | jq -r '.level // "info"' 2>/dev/null)
            local event=$(echo "$line" | jq -r '.event // .message // ""' 2>/dev/null)
            local timestamp=$(echo "$line" | jq -r '.timestamp // ""' 2>/dev/null)
            local filename=$(echo "$line" | jq -r '.filename // ""' 2>/dev/null)
            local lineno=$(echo "$line" | jq -r '.lineno // ""' 2>/dev/null)
            local request_id=$(echo "$line" | jq -r '.request_id // ""' 2>/dev/null)

            # Extract additional context fields (exclude standard fields)
            local context=$(echo "$line" | jq -r 'del(.event, .message, .level, .timestamp, .service, .session_id, .request_id, .logger, .filename, .lineno) | to_entries | map("\(.key)=\(.value)") | join(" ")' 2>/dev/null)

            # Extract time portion from ISO timestamp
            if [[ "$timestamp" == *"T"* ]]; then
                timestamp=$(echo "$timestamp" | sed 's/.*T\([0-9:]*\).*/\1/' | cut -c1-8)
            else
                timestamp=$(date '+%H:%M:%S')
            fi

            # Build location string
            local location=""
            if [ -n "$filename" ] && [ "$filename" != "null" ]; then
                location="${filename}:${lineno}"
            fi

            # Build request ID string (shortened)
            local req_str=""
            if [ -n "$request_id" ] && [ "$request_id" != "null" ]; then
                req_str="${request_id#mt-req-}"  # Remove prefix for brevity
            fi


            # Build the output line
            local output=""
            local level_str=""
            local event_color=""

            case "$level" in
                error|ERROR)
                    level_str="${RED}${BOLD}ERROR${NC}"
                    event_color="${RED}"
                    ;;
                warning|warn|WARNING|WARN)
                    level_str="${YELLOW}${BOLD}WARN ${NC}"
                    event_color="${YELLOW}"
                    ;;
                info|INFO)
                    level_str="${CYAN}INFO ${NC}"
                    event_color=""
                    ;;
                debug|DEBUG)
                    level_str="${DIM}DEBUG${NC}"
                    event_color="${DIM}"
                    ;;
                *)
                    level_str="${BLUE}$level${NC}"
                    event_color=""
                    ;;
            esac

            # Format: [time] LEVEL event | context | location
            output="${GRAY}[$timestamp]${NC} ${level_str} ${event_color}${event}${NC}"

            # Add context if present
            if [ -n "$context" ] && [ "$context" != "" ]; then
                output="${output} ${DIM}| ${context}${NC}"
            fi

            # Add location for errors/warnings
            if [ -n "$location" ] && [[ "$level" =~ ^(error|ERROR|warning|warn|WARNING|WARN)$ ]]; then
                output="${output} ${DIM}@ ${location}${NC}"
            fi

            echo -e "$output"
        else
            # Fallback: simple grep-based parsing
            local timestamp=$(date '+%H:%M:%S')
            if echo "$line" | grep -q '"level":\s*"error"'; then
                echo -e "${GRAY}[$timestamp]${NC} ${RED}${BOLD}ERROR${NC} ${RED}$line${NC}"
            elif echo "$line" | grep -q '"level":\s*"warning\|warn"'; then
                echo -e "${GRAY}[$timestamp]${NC} ${YELLOW}${BOLD}WARN ${NC} $line"
            else
                echo -e "${GRAY}[$timestamp]${NC} ${CYAN}INFO ${NC} $line"
            fi
        fi
    else
        # Non-JSON line (e.g., startup messages, stack traces)
        local timestamp=$(date '+%H:%M:%S')
        if echo "$line" | grep -iq "error\|exception\|traceback\|failed"; then
            echo -e "${GRAY}[$timestamp]${NC} ${RED}$line${NC}"
        elif echo "$line" | grep -iq "warning\|warn"; then
            echo -e "${GRAY}[$timestamp]${NC} ${YELLOW}$line${NC}"
        elif [ -n "$line" ]; then
            echo -e "${GRAY}[$timestamp]${NC} $line"
        fi
    fi
}

# Function to tail logs in real-time
tail_logs() {
    echo -e "${BLUE}${BOLD}Missing Table Service Logs (Live)${NC}"
    echo "=================================="
    echo -e "${YELLOW}Following logs in real-time... Press Ctrl+C to stop${NC}"
    echo ""
    echo -e "Legend: ${RED}${BOLD}ERROR${NC} ${YELLOW}${BOLD}WARN${NC} ${CYAN}INFO${NC} ${DIM}DEBUG${NC}"
    echo ""

    # Check which log files exist
    local backend_log="$LOG_DIR/backend.log"
    local frontend_log="$LOG_DIR/frontend.log"
    local log_files=""

    if [ -f "$backend_log" ]; then
        log_files="$log_files $backend_log"
    fi

    if [ -f "$frontend_log" ]; then
        log_files="$log_files $frontend_log"
    fi

    if [ -z "$log_files" ]; then
        echo -e "${RED}No log files found. Start the services first with: $0 start${NC}"
        return 1
    fi

    # Check for jq
    if ! command -v jq &> /dev/null; then
        echo -e "${YELLOW}Tip: Install jq for better JSON log formatting: brew install jq${NC}"
        echo ""
    fi

    # Function to cleanup on exit
    cleanup_tail() {
        exit 0
    }
    trap cleanup_tail INT TERM EXIT

    # Tail logs with formatting
    if [ -f "$backend_log" ] && [ -f "$frontend_log" ]; then
        echo -e "${GREEN}Tailing both backend and frontend logs...${NC}"
        echo ""
        tail -f "$backend_log" "$frontend_log" | while read -r line; do
            # Skip file header lines from tail -f
            if echo "$line" | grep -q "==> .*/backend.log <=="; then
                echo -e "\n${BLUE}${BOLD}--- BACKEND ---${NC}"
            elif echo "$line" | grep -q "==> .*/frontend.log <=="; then
                echo -e "\n${GREEN}${BOLD}--- FRONTEND ---${NC}"
            elif [ -n "$line" ]; then
                format_json_log "$line" "backend"
            fi
        done
    elif [ -f "$backend_log" ]; then
        echo -e "${GREEN}Tailing backend logs only...${NC}"
        echo ""
        tail -f "$backend_log" | while read -r line; do
            format_json_log "$line" "backend"
        done
    elif [ -f "$frontend_log" ]; then
        echo -e "${GREEN}Tailing frontend logs only...${NC}"
        echo ""
        tail -f "$frontend_log" | while read -r line; do
            format_json_log "$line" "frontend"
        done
    fi
}

# Main script logic
case "$1" in
    start)
        # Check for --watch flag
        if [ "$2" = "--watch" ]; then
            start_services true
        else
            start_services false
        fi
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        sleep 2
        # Check for --watch flag
        if [ "$2" = "--watch" ]; then
            start_services true
        else
            start_services false
        fi
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    tail)
        tail_logs
        ;;
    klogs)
        # Parse klogs options
        shift  # Remove 'klogs' from args
        klogs_since="10m"
        klogs_tail="50"
        klogs_all="false"

        for arg in "$@"; do
            case "$arg" in
                --since=*)
                    klogs_since="${arg#*=}"
                    ;;
                --tail=*)
                    klogs_tail="${arg#*=}"
                    ;;
                --all)
                    klogs_all="true"
                    ;;
                --help|-h)
                    echo -e "${BLUE}klogs - Tail Kubernetes logs with pretty formatting${NC}"
                    echo ""
                    echo "Usage: $0 klogs [options]"
                    echo ""
                    echo "Options:"
                    echo "  --since=DURATION   Show logs since duration (default: 10m)"
                    echo "                     Examples: 5s, 2m, 1h, 24h"
                    echo "  --tail=N           Show last N lines initially (default: 50)"
                    echo "  --all              Show logs from all pods, not just backend"
                    echo "  --help, -h         Show this help message"
                    echo ""
                    echo "Examples:"
                    echo "  $0 klogs                    # Last 10 min, 50 lines"
                    echo "  $0 klogs --since=1h         # Last hour"
                    echo "  $0 klogs --tail=100         # Start with 100 lines"
                    echo "  $0 klogs --since=30m --all  # All pods, last 30 min"
                    exit 0
                    ;;
                *)
                    echo -e "${RED}Unknown option: $arg${NC}"
                    echo "Use '$0 klogs --help' for usage"
                    exit 1
                    ;;
            esac
        done

        tail_k8s_logs "$klogs_since" "$klogs_tail" "$klogs_all"
        ;;
    *)
        usage
        exit 1
        ;;
esac

exit 0
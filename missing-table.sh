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
PID_DIR="$HOME/.missing-table"
BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
LOG_DIR="$PID_DIR/logs"

# Create directories if they don't exist
mkdir -p "$PID_DIR" "$LOG_DIR"

# Function to print usage
usage() {
    echo -e "${BLUE}Missing Table Service Manager${NC}"
    echo ""
    echo -e "${YELLOW}Usage:${NC} $0 {start|stop|restart|status|logs|tail}"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo "  start    - Start both backend and frontend services"
    echo "  stop     - Stop all running services"
    echo "  restart  - Stop and start all services"
    echo "  status   - Show status of all services"
    echo "  logs     - Show recent logs from services"
    echo "  tail     - Follow logs in real-time (Ctrl+C to stop)"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  $0 start"
    echo "  $0 status"
    echo "  $0 restart"
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

# Function to start backend
start_backend() {
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
    current_env="${APP_ENV:-local}"
    echo "Using environment: $current_env"

    # Set INFO log level for cleaner output during development
    export LOG_LEVEL=info

    cd backend

    # Start backend in background with logging
    local backend_log="$LOG_DIR/backend.log"
    echo "Backend logs: $backend_log"

    if command -v uv &> /dev/null; then
        nohup uv run python app.py > "$backend_log" 2>&1 &
    else
        echo -e "${YELLOW}uv not found, using python directly${NC}"
        nohup python app.py > "$backend_log" 2>&1 &
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

    cd frontend

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo "Installing frontend dependencies..."
        npm install
    fi

    # Start frontend in background with logging
    local frontend_log="$LOG_DIR/frontend.log"
    echo "Frontend logs: $frontend_log"

    nohup npm run serve > "$frontend_log" 2>&1 &
    local frontend_pid=$!
    echo $frontend_pid > "$FRONTEND_PID_FILE"
    cd ..

    # Wait for frontend to start
    echo "Waiting for frontend to start..."
    local count=0
    while [ $count -lt 15 ]; do
        if port_in_use $FRONTEND_PORT; then
            echo -e "${GREEN}Frontend started successfully (PID: $frontend_pid)${NC}"
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
    echo -e "${GREEN}Starting Missing Table application...${NC}\n"

    # Check if we're in the right directory
    if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
        echo -e "${RED}Error: backend or frontend directory not found!${NC}"
        echo "Please run this script from the project root directory."
        return 1
    fi

    start_backend
    if [ $? -eq 0 ]; then
        start_frontend
        if [ $? -eq 0 ]; then
            echo -e "\n${GREEN}All services started successfully!${NC}"
            echo -e "Backend: http://localhost:$BACKEND_PORT"
            echo -e "Frontend: http://localhost:$FRONTEND_PORT"
            echo -e "\nUse '$0 status' to check service status"
            echo -e "Use '$0 logs' to view logs"
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

# Function to tail logs in real-time
tail_logs() {
    echo -e "${BLUE}Missing Table Service Logs (Live)${NC}"
    echo "=================================="
    echo -e "${YELLOW}Following logs in real-time... Press Ctrl+C to stop${NC}"
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

    # Use multitail if available, otherwise fall back to tail -f
    if command -v multitail &> /dev/null; then
        echo -e "${GREEN}Using multitail for better display${NC}"
        multitail $log_files
    else
        # Create a temporary file for tail output formatting
        local temp_file="/tmp/missing-table-tail-$$"

        # Function to cleanup temp file on exit
        cleanup_tail() {
            rm -f "$temp_file"
            exit 0
        }
        trap cleanup_tail INT TERM EXIT

        # Use tail -f with labels
        if [ -f "$backend_log" ] && [ -f "$frontend_log" ]; then
            echo -e "${GREEN}Tailing both backend and frontend logs...${NC}"
            tail -f "$backend_log" "$frontend_log" | while read -r line; do
                # Add timestamp and color coding
                timestamp=$(date '+%H:%M:%S')
                if echo "$line" | grep -q "==> .*/backend.log <=="; then
                    echo -e "${BLUE}[$timestamp] BACKEND:${NC}"
                elif echo "$line" | grep -q "==> .*/frontend.log <=="; then
                    echo -e "${GREEN}[$timestamp] FRONTEND:${NC}"
                elif [ -n "$line" ]; then
                    echo "[$timestamp] $line"
                fi
            done
        elif [ -f "$backend_log" ]; then
            echo -e "${GREEN}Tailing backend logs only...${NC}"
            tail -f "$backend_log" | while read -r line; do
                timestamp=$(date '+%H:%M:%S')
                echo -e "${BLUE}[$timestamp] BACKEND:${NC} $line"
            done
        elif [ -f "$frontend_log" ]; then
            echo -e "${GREEN}Tailing frontend logs only...${NC}"
            tail -f "$frontend_log" | while read -r line; do
                timestamp=$(date '+%H:%M:%S')
                echo -e "${GREEN}[$timestamp] FRONTEND:${NC} $line"
            done
        fi
    fi
}

# Main script logic
case "$1" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        sleep 2
        start_services
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
    *)
        usage
        exit 1
        ;;
esac

exit 0
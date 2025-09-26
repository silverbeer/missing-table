#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    
    # Kill all child processes
    if [ -n "$BACKEND_PID" ]; then
        echo "Stopping backend (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null
    fi
    
    if [ -n "$FRONTEND_PID" ]; then
        echo "Stopping frontend (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null
    fi
    
    # Wait for processes to end
    wait
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

# Set up trap for cleanup on script exit
trap cleanup EXIT INT TERM

echo -e "${GREEN}Starting Missing Table application...${NC}\n"

# Check if we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo -e "${RED}Error: backend or frontend directory not found!${NC}"
    echo "Please run this script from the project root directory."
    exit 1
fi

# Start backend
echo -e "${YELLOW}Starting backend server...${NC}"

# Show current environment
current_env="${APP_ENV:-local}"
echo "Using environment: $current_env"

cd backend

# Check if uv is available
if command -v uv &> /dev/null; then
    uv run python app.py &
else
    echo -e "${YELLOW}uv not found, using python directly${NC}"
    python app.py &
fi
BACKEND_PID=$!
cd ..

# Wait a bit for backend to start
echo "Waiting for backend to start..."
sleep 3

# Check if backend is running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}Backend failed to start!${NC}"
    exit 1
fi

# Start frontend
echo -e "\n${YELLOW}Starting frontend server...${NC}"
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

npm run serve &
FRONTEND_PID=$!
cd ..

echo -e "\n${GREEN}Both services are starting...${NC}"
echo -e "Backend: http://localhost:8000"
echo -e "Frontend: http://localhost:8080"
echo -e "\nPress Ctrl+C to stop all services\n"

# Wait for both processes
wait
#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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
    
    # Stop Supabase if we started it
    if [ "$SUPABASE_STARTED" = true ]; then
        echo "Stopping Supabase..."
        cd backend && npx supabase stop
        cd ..
    fi
    
    # Wait for processes to end
    wait
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

# Set up trap for cleanup on script exit
trap cleanup EXIT INT TERM

echo -e "${GREEN}Starting Missing Table application with Supabase...${NC}\n"

# Check if we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo -e "${RED}Error: backend or frontend directory not found!${NC}"
    echo "Please run this script from the project root directory."
    exit 1
fi

# Check Supabase status
echo -e "${BLUE}Checking Supabase status...${NC}"
cd backend

# Check if supabase is already running
if npx supabase status 2>/dev/null | grep -q "RUNNING"; then
    echo -e "${GREEN}Supabase is already running${NC}"
    SUPABASE_STARTED=false
else
    echo -e "${YELLOW}Starting Supabase...${NC}"
    npx supabase start
    
    # Check if supabase started successfully
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to start Supabase!${NC}"
        echo "Make sure you have Docker running and Supabase CLI installed."
        exit 1
    fi
    SUPABASE_STARTED=true
    
    # Wait for Supabase to be ready
    echo "Waiting for Supabase to be ready..."
    sleep 5
fi

# Show Supabase endpoints
echo -e "\n${BLUE}Supabase endpoints:${NC}"
npx supabase status | grep -E "API URL|DB URL|Studio URL"

cd ..

# Start backend
echo -e "\n${YELLOW}Starting backend server...${NC}"
cd backend

# Use .env.local for local development
if [ -f ".env.local" ]; then
    echo "Using .env.local configuration"
    export $(grep -v '^#' .env.local | xargs)
fi

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

echo -e "\n${GREEN}All services are running!${NC}"
echo -e "   ${BLUE}Supabase Studio:${NC} http://localhost:54323"
echo -e "   ${BLUE}Backend API:${NC}     http://localhost:8000"
echo -e "   ${BLUE}Frontend:${NC}        http://localhost:8080"
echo -e "\nPress Ctrl+C to stop all services\n"

# Wait for both processes
wait
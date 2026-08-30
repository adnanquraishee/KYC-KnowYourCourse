#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")" || exit 1

# Colors for terminal output
BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}${BOLD}"
echo "========================================================"
echo "          KYC — Know Your Courses Launcher             "
echo "========================================================"
echo -e "${NC}"

# Cleanup function to kill background processes on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping KYC servers...${NC}"
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null
    fi
    # Also ensure ports 5300 and 5350 are freed
    lsof -ti:5350 | xargs kill -9 2>/dev/null
    lsof -ti:5300 | xargs kill -9 2>/dev/null
    echo -e "${GREEN}Servers stopped successfully.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# Free target ports before launching in case of orphaned processes
lsof -ti:5350 | xargs kill -9 2>/dev/null
lsof -ti:5300 | xargs kill -9 2>/dev/null

# 1. Setup / Verify Python Virtual Environment
echo -e "${BLUE}[1/4] Checking Python environment...${NC}"
PYTHON_BIN=""

if [ -f "venv/bin/python" ]; then
    PYTHON_BIN="venv/bin/python"
elif [ -f "../venv/bin/python" ]; then
    PYTHON_BIN="../venv/bin/python"
else
    echo -e "${YELLOW}Virtual environment not found. Creating venv...${NC}"
    python3 -m venv venv
    PYTHON_BIN="venv/bin/python"
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    "$PYTHON_BIN" -m pip install --upgrade pip
    "$PYTHON_BIN" -m pip install -r requirements.txt
fi

# 2. Setup / Verify Frontend Node Modules
echo -e "${BLUE}[2/4] Checking Frontend dependencies...${NC}"
if [ ! -d "gui/node_modules" ]; then
    echo -e "${YELLOW}Installing GUI dependencies (npm install)...${NC}"
    npm --prefix gui install
fi

# 3. Start Backend on Port 5350
echo -e "${BLUE}[3/4] Starting KYC Backend on port 5350...${NC}"
PORT=5350 "$PYTHON_BIN" api.py &
BACKEND_PID=$!

# 4. Start Frontend on Port 5300
echo -e "${BLUE}[4/4] Starting KYC Frontend on port 5300...${NC}"
npm --prefix gui run dev &
FRONTEND_PID=$!

echo ""
echo -e "${GREEN}${BOLD}KYC is booting up!${NC}"
echo -e "  Backend API:  ${CYAN}http://localhost:5350${NC}"
echo -e "  Frontend GUI: ${CYAN}http://localhost:5300${NC}"
echo ""
echo -e "${YELLOW}Waiting for servers to be ready...${NC}"

# Wait for frontend to be responsive (up to 15 seconds)
MAX_RETRIES=15
COUNTER=0
while [ $COUNTER -lt $MAX_RETRIES ]; do
    sleep 1
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:5300 >/dev/null 2>&1; then
        break
    fi
    COUNTER=$((COUNTER + 1))
done

echo -e "${GREEN}${BOLD}Opening http://localhost:5300 in your browser...${NC}"
open "http://localhost:5300"

echo ""
echo -e "${BOLD}Servers are running. Press ${RED}Ctrl+C${NC} in this window to stop both servers.${BOLD}"
echo "========================================================"
echo -e "${NC}"

# Keep script running and wait for background processes
wait

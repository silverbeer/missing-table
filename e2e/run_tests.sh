#!/bin/bash
# =============================================================================
# Playwright E2E Test Runner
# =============================================================================
# 
# Usage:
#   ./run_tests.sh              # Run all tests
#   ./run_tests.sh smoke        # Run smoke tests only
#   ./run_tests.sh auth         # Run authentication tests
#   ./run_tests.sh visual       # Run visual regression tests
#   ./run_tests.sh debug        # Run in debug mode (headed, slow)
#   ./run_tests.sh parallel     # Run tests in parallel
#   ./run_tests.sh <test_file>  # Run specific test file
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Navigate to test directory
cd "$(dirname "$0")"

echo -e "${BLUE}🎭 Missing Table E2E Test Runner${NC}"
echo "================================================"

# Create test results directory
mkdir -p test-results

# Default options
PYTEST_OPTS=""

# Parse arguments
case "$1" in
    smoke)
        echo -e "${YELLOW}Running smoke tests...${NC}"
        PYTEST_OPTS="-m smoke"
        ;;
    critical)
        echo -e "${YELLOW}Running critical tests...${NC}"
        PYTEST_OPTS="-m critical"
        ;;
    auth)
        echo -e "${YELLOW}Running authentication tests...${NC}"
        PYTEST_OPTS="-m auth"
        ;;
    standings)
        echo -e "${YELLOW}Running standings tests...${NC}"
        PYTEST_OPTS="-m standings"
        ;;
    visual)
        echo -e "${YELLOW}Running visual regression tests...${NC}"
        PYTEST_OPTS="-m visual"
        ;;
    debug)
        echo -e "${YELLOW}Running in debug mode...${NC}"
        PYTEST_OPTS="--headed --slowmo 500 -x -v"
        ;;
    parallel)
        echo -e "${YELLOW}Running tests in parallel...${NC}"
        PYTEST_OPTS="-n auto"
        ;;
    report)
        echo -e "${YELLOW}Opening test report...${NC}"
        if [ -f "test-results/report.html" ]; then
            open test-results/report.html
        else
            echo -e "${RED}No report found. Run tests first.${NC}"
        fi
        exit 0
        ;;
    help|--help|-h)
        echo "Usage: ./run_tests.sh [command|test_file]"
        echo ""
        echo "Commands:"
        echo "  smoke      - Run smoke tests"
        echo "  critical   - Run critical tests"
        echo "  auth       - Run authentication tests"
        echo "  standings  - Run standings tests"
        echo "  visual     - Run visual regression tests"
        echo "  debug      - Run in debug mode (headed, slow)"
        echo "  parallel   - Run tests in parallel"
        echo "  report     - Open HTML report"
        echo ""
        echo "Examples:"
        echo "  ./run_tests.sh                    # Run all tests"
        echo "  ./run_tests.sh test_auth.py      # Run specific file"
        echo "  ./run_tests.sh smoke              # Run smoke tests"
        exit 0
        ;;
    "")
        echo -e "${YELLOW}Running all tests...${NC}"
        ;;
    *.py)
        echo -e "${YELLOW}Running $1...${NC}"
        PYTEST_OPTS="$1"
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo "Run './run_tests.sh help' for usage"
        exit 1
        ;;
esac

# Run tests from project root using backend's uv environment
echo ""
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT/backend"
uv run pytest "$SCRIPT_DIR" $PYTEST_OPTS

# Report results
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Tests passed!${NC}"
    echo -e "Report: test-results/report.html"
else
    echo ""
    echo -e "${RED}❌ Some tests failed${NC}"
    echo -e "Check report: test-results/report.html"
    exit 1
fi

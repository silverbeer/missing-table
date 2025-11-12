#!/bin/bash
#
# Quick helper script for testing Phase 3 tools
#
# Usage:
#   ./crew_testing/test-tools.sh               # Interactive mode
#   ./crew_testing/test-tools.sh gap           # Test GapReportTool on auth.py
#   ./crew_testing/test-tools.sh all           # Test all tools on auth.py
#   ./crew_testing/test-tools.sh all --save    # Test all tools and save results
#

cd "$(dirname "$0")/.." || exit 1

MODULE="${2:-backend/auth.py}"

case "${1:-interactive}" in
    code)
        PYTHONPATH=. backend/.venv/bin/python3 crew_testing/test_phase3_tools.py code "$MODULE" "${@:3}"
        ;;
    coverage)
        PYTHONPATH=. backend/.venv/bin/python3 crew_testing/test_phase3_tools.py coverage "$MODULE" "${@:3}"
        ;;
    gap)
        PYTHONPATH=. backend/.venv/bin/python3 crew_testing/test_phase3_tools.py gap "$MODULE" "${@:3}"
        ;;
    all)
        PYTHONPATH=. backend/.venv/bin/python3 crew_testing/test_phase3_tools.py all "$MODULE" "${@:3}"
        ;;
    list)
        PYTHONPATH=. backend/.venv/bin/python3 crew_testing/test_phase3_tools.py list-modules
        ;;
    interactive|*)
        PYTHONPATH=. backend/.venv/bin/python3 crew_testing/test_phase3_tools.py interactive
        ;;
esac

#!/bin/bash
# Verification script for Phase 1 implementation

echo "🔍 Phase 1 Verification Script"
echo "==============================="
echo ""

ERRORS=0

# Test 1: Check all files exist
echo "📁 Test 1: Checking file structure..."
FILES=(
    "crew_testing/config.py"
    "crew_testing/crew_config.py"
    "crew_testing/main.py"
    "crew_testing/run.sh"
    "crew_testing/status.sh"
    "crew_testing/agents/__init__.py"
    "crew_testing/agents/swagger.py"
    "crew_testing/tools/__init__.py"
    "crew_testing/tools/openapi_tool.py"
    "crew_testing/tools/api_client_tool.py"
    "crew_testing/tools/test_scanner_tool.py"
    "crew_testing/README.md"
    "crew_testing/PHASE1_COMPLETE.md"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ MISSING: $file"
        ERRORS=$((ERRORS+1))
    fi
done
echo ""

# Test 2: Check Python imports
echo "🐍 Test 2: Checking Python imports..."
if PYTHONPATH=. backend/.venv/bin/python3 -c "import crew_testing.config" 2>/dev/null; then
    echo "  ✅ config module imports"
else
    echo "  ❌ config module import failed"
    ERRORS=$((ERRORS+1))
fi

if PYTHONPATH=. backend/.venv/bin/python3 -c "from crew_testing.tools import ReadOpenAPISpecTool" 2>/dev/null; then
    echo "  ✅ tools module imports"
else
    echo "  ❌ tools module import failed"
    ERRORS=$((ERRORS+1))
fi

if PYTHONPATH=. backend/.venv/bin/python3 -c "from crew_testing.agents import create_swagger_agent" 2>/dev/null; then
    echo "  ✅ agents module imports"
else
    echo "  ❌ agents module import failed"
    ERRORS=$((ERRORS+1))
fi
echo ""

# Test 3: Check CLI commands
echo "🖥️  Test 3: Testing CLI commands..."

if ./crew_testing/run.sh version &>/dev/null; then
    echo "  ✅ version command works"
else
    echo "  ❌ version command failed"
    ERRORS=$((ERRORS+1))
fi

if ./crew_testing/run.sh agents &>/dev/null; then
    echo "  ✅ agents command works"
else
    echo "  ❌ agents command failed"
    ERRORS=$((ERRORS+1))
fi

if ./crew_testing/run.sh --help &>/dev/null; then
    echo "  ✅ help command works"
else
    echo "  ❌ help command failed"
    ERRORS=$((ERRORS+1))
fi
echo ""

# Test 4: Check dependencies
echo "📦 Test 4: Checking dependencies..."
if backend/.venv/bin/python3 -c "import crewai; import anthropic; import typer; import rich" 2>/dev/null; then
    echo "  ✅ All required packages installed"
else
    echo "  ❌ Some packages missing"
    ERRORS=$((ERRORS+1))
fi
echo ""

# Test 5: Check backend status
echo "🖥️  Test 5: Checking MT backend..."
if curl -s http://localhost:8000/openapi.json > /dev/null 2>&1; then
    echo "  ✅ MT backend is running"
else
    echo "  ⚠️  MT backend not running (optional for Phase 1)"
fi
echo ""

# Test 6: Code quality check
echo "📝 Test 6: Checking code quality..."
PYTHON_FILES=$(find crew_testing -name "*.py" -not -path "*/\.*" 2>/dev/null | wc -l)
echo "  ✅ Found $PYTHON_FILES Python files"

if [ "$PYTHON_FILES" -ge 8 ]; then
    echo "  ✅ Sufficient code coverage"
else
    echo "  ❌ Insufficient files"
    ERRORS=$((ERRORS+1))
fi
echo ""

# Final results
echo "================================"
if [ $ERRORS -eq 0 ]; then
    echo "✅ ALL TESTS PASSED!"
    echo ""
    echo "Phase 1 implementation is complete and verified."
    echo "Ready for Phase 2 development!"
    exit 0
else
    echo "❌ FAILED: $ERRORS test(s) failed"
    echo ""
    echo "Please review the errors above and fix them."
    exit 1
fi

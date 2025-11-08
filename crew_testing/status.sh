#!/bin/bash
# Quick status check for CrewAI Testing System

echo "🤖 MT Testing Crew - Status Check"
echo "================================="
echo ""

# Check phase 1 files
echo "📁 Phase 1 Files:"
[ -f "crew_testing/agents/swagger.py" ] && echo "  ✅ Swagger agent" || echo "  ❌ Swagger agent MISSING"
[ -f "crew_testing/tools/openapi_tool.py" ] && echo "  ✅ OpenAPI tool" || echo "  ❌ OpenAPI tool MISSING"
[ -f "crew_testing/tools/api_client_tool.py" ] && echo "  ✅ API client tool" || echo "  ❌ API client tool MISSING"
[ -f "crew_testing/tools/test_scanner_tool.py" ] && echo "  ✅ Test scanner tool" || echo "  ❌ Test scanner tool MISSING"
[ -f "crew_testing/main.py" ] && echo "  ✅ CLI main.py" || echo "  ❌ CLI main.py MISSING"
[ -f "crew_testing/README.md" ] && echo "  ✅ Documentation" || echo "  ❌ Documentation MISSING"
echo ""

# Check dependencies
echo "📦 Dependencies:"
if backend/.venv/bin/python3 -c "import crewai" 2>/dev/null; then
    echo "  ✅ CrewAI installed"
else
    echo "  ❌ CrewAI NOT installed"
fi

if backend/.venv/bin/python3 -c "import anthropic" 2>/dev/null; then
    echo "  ✅ Anthropic SDK installed"
else
    echo "  ❌ Anthropic SDK NOT installed"
fi

if backend/.venv/bin/python3 -c "import typer" 2>/dev/null; then
    echo "  ✅ Typer CLI installed"
else
    echo "  ❌ Typer CLI NOT installed"
fi
echo ""

# Check API key
echo "🔑 Configuration:"
if grep -q "ANTHROPIC_API_KEY=sk-ant" .env.local 2>/dev/null; then
    echo "  ✅ Anthropic API key configured"
elif grep -q "ANTHROPIC_API_KEY=your_anthropic_api_key_here" .env.local 2>/dev/null; then  # pragma: allowlist secret
    echo "  ⚠️  Anthropic API key placeholder only (not configured)"
else
    echo "  ❌ Anthropic API key NOT configured"
fi
echo ""

# Check backend status
echo "🖥️  Backend Status:"
if curl -s http://localhost:8000/openapi.json > /dev/null 2>&1; then
    echo "  ✅ MT backend running (http://localhost:8000)"
else
    echo "  ❌ MT backend NOT running"
    echo "     Run: ./missing-table.sh start"
fi
echo ""

# Phase completion
echo "📊 Progress:"
echo "  ✅ Phase 1: COMPLETE (1/8 agents)"
echo "  ⏳ Phase 2: Not started (4 agents)"
echo "  ⏳ Phase 3: Not started (3 agents)"
echo "  ⏳ Phase 4: Not started (CI/CD)"
echo ""

# Quick commands
echo "🚀 Quick Commands:"
echo "  ./crew_testing/run.sh version  # Show version"
echo "  ./crew_testing/run.sh agents   # List agents"
echo "  ./crew_testing/run.sh scan     # Scan API (needs API key)"
echo ""

echo "📖 Documentation: crew_testing/README.md"
echo "✅ Phase 1 Report: crew_testing/PHASE1_COMPLETE.md"
echo ""

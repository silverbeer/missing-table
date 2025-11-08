# 🤖 MT Testing Crew - CrewAI Autonomous Testing System

> **An 8-agent autonomous testing system powered by CrewAI and Claude 3 Haiku**

## 📖 Overview

The MT Testing Crew is an intelligent, autonomous testing system that uses 8 specialized AI agents to ensure quality for the Missing Table backend API. Each agent has a specific role, from scanning API documentation to debugging test failures.

**Current Status:** Phase 1 Complete - Swagger agent operational

## 🌟 Meet the Crew

### ✅ Phase 1: Foundation (Current)

#### 📚 Swagger - API Documentation Expert
**Tagline:** *"I know every endpoint by heart"*

**Capabilities:**
- Reads OpenAPI specification from `/openapi.json`
- Catalogs all 47+ MT backend endpoints
- Scans `api_client/` for missing methods
- Scans `tests/` for coverage gaps
- Calculates coverage statistics

**Status:** ✅ Implemented and working

### ⏳ Phase 2: Core Agents (Coming Soon)

- 🎯 **Architect** - Test Scenario Designer
- 🎨 **Mocker** - Test Data Craftsman
- 🔧 **Forge** - Test Infrastructure Engineer
- ⚡ **Flash** - Test Executor

### ⏳ Phase 3: Intelligence Layer (Coming Later)

- 🔬 **Inspector** - Quality Analyst
- 📊 **Herald** - Test Reporter
- 🐛 **Sherlock** - Test Debugger

## 🚀 Quick Start

### Prerequisites

1. **Python 3.13+** with `uv` package manager
2. **Anthropic API key** from https://console.anthropic.com/
3. **MT backend running** on `http://localhost:8000`

### Installation

Dependencies are already installed via `pyproject.toml`:

```bash
# Dependencies were added and installed during setup
cd /path/to/missing-table
uv sync
```

### Configuration

Add your Anthropic API key to `.env.local`:

```bash
# Get your API key from: https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-api03-...
CREW_VERBOSE=false  # Set to true for detailed agent logs
```

### Usage

```bash
# Scan the MT backend API (recommended)
uv run python crew_testing/main.py scan

# Scan with verbose output (see agent thinking)
uv run python crew_testing/main.py scan --verbose

# Scan different backend URL
uv run python crew_testing/main.py scan --url http://dev.example.com:8000

# Show version info
uv run python crew_testing/main.py version

# List all agents
uv run python crew_testing/main.py agents

# Get help
uv run python crew_testing/main.py --help
```

## 📊 Example Output

```
🤖 MT Testing Crew
📚 Swagger - API Documentation Expert

Scanning: http://localhost:8000

📚 Swagger: Scanning MT backend API...
📚 OpenAPI Specification: Missing Table API
📚 Version: 1.0.0

📚 Total endpoints found: 47

## auth
  GET    /api/auth/me                           - Get current user
  POST   /api/auth/login                        - Login user
  POST   /api/auth/logout                       - Logout user

## matches
  GET    /api/matches                           - List matches
  POST   /api/matches                           - Create match
  GET    /api/matches/{id}                      - Get match by ID

...

🔍 Gap Detection Report
==================================================

⚠️  5 endpoints missing in api_client:
   - GET /api/clubs/{id}/stats
   - GET /api/teams/{id}/roster
   ...

⚠️  12 endpoints without test coverage:
   - GET /api/matches/{id}/stats
   ...

📊 Summary:
   Total endpoints: 47
   Missing client methods: 5
   Missing tests: 12
   Coverage: 74.5%
```

## 🏗️ Project Structure

```
crew_testing/
├── agents/
│   ├── __init__.py
│   └── swagger.py          # 📚 Swagger agent (Phase 1)
│   └── architect.py        # 🎯 Coming in Phase 2
│   └── mocker.py           # 🎨 Coming in Phase 2
│   └── forge.py            # 🔧 Coming in Phase 2
│   └── flash.py            # ⚡ Coming in Phase 2
│   └── inspector.py        # 🔬 Coming in Phase 3
│   └── herald.py           # 📊 Coming in Phase 3
│   └── sherlock.py         # 🐛 Coming in Phase 3
├── tools/
│   ├── __init__.py
│   ├── openapi_tool.py     # Read OpenAPI specs
│   ├── api_client_tool.py  # Scan and generate client methods
│   ├── test_scanner_tool.py # Analyze test coverage
│   ├── pytest_tool.py      # Run pytest (Phase 2)
│   ├── code_gen_tool.py    # Generate code (Phase 2)
│   └── git_tool.py         # Git operations (Phase 4)
├── reports/
│   └── .gitkeep            # HTML reports go here (Phase 3)
├── config.py               # Configuration management
├── crew_config.py          # CrewAI crew definition
├── main.py                 # CLI entry point
└── README.md               # This file
```

## 💰 Cost Analysis

**Model:** Claude 3 Haiku (cost-effective choice)

**Cost Per Scan:**
- Input: ~100K tokens × $0.25/M = $0.025
- Output: ~20K tokens × $1.25/M = $0.025
- **Total: ~$0.05 per scan** ✨

**Development (Phase 1-4):**
- ~50 test runs = $2.50 total

**Production (Monthly):**
- ~100 scans = $5.00/month

**Compare to:**
- Claude 3.5 Sonnet: $0.30/run (6x more expensive)
- GPT-4: $0.40/run (8x more expensive)

## 🔧 Development

### Running Tests

```bash
# Test the Swagger agent
uv run python crew_testing/main.py scan

# Test with actual MT backend
./missing-table.sh start  # Start MT backend
uv run python crew_testing/main.py scan
```

### Adding New Agents

See `docs/CREWAI_TESTING_PLAN.md` for the full implementation plan.

Example agent structure:

```python
# crew_testing/agents/your_agent.py
from crewai import Agent
from langchain_anthropic import ChatAnthropic
from crew_testing.config import CrewConfig

def create_your_agent() -> Agent:
    llm = ChatAnthropic(
        model=CrewConfig.DEFAULT_MODEL,
        anthropic_api_key=CrewConfig.ANTHROPIC_API_KEY,
        temperature=0.1,
    )

    agent = Agent(
        role="Your Role",
        goal="Your goal",
        backstory="Your backstory",
        verbose=CrewConfig.VERBOSE,
        llm=llm,
        tools=[...],
    )

    return agent
```

## 📅 Roadmap

### ✅ Phase 1: Foundation (Complete)
- [x] Project setup and dependencies
- [x] Configuration management
- [x] OpenAPI scanning tool
- [x] API client scanner tool
- [x] Test scanner tool
- [x] Swagger agent implementation
- [x] CLI interface
- [x] Basic documentation

### ⏳ Phase 2: Core Agents (Next - Week 2)
- [ ] Architect agent - Test scenario design
- [ ] Mocker agent - Test data generation
- [ ] Forge agent - Infrastructure maintenance
- [ ] Flash agent - Test execution
- [ ] End-to-end workflow for `/api/matches`

### ⏳ Phase 3: Intelligence Layer (Week 3)
- [ ] Inspector agent - Pattern analysis
- [ ] Herald agent - Report generation
- [ ] Sherlock agent - Failure debugging
- [ ] HTML dashboard reports

### ⏳ Phase 4: Production (Week 4)
- [ ] GitHub Actions integration
- [ ] PR comment automation
- [ ] Demo video recording
- [ ] Interview preparation

## 🤝 Contributing

This is a personal project for interview demonstration. However, feedback and suggestions are welcome!

## 📚 Related Documentation

- **[CREWAI_TESTING_PLAN.md](../docs/CREWAI_TESTING_PLAN.md)** - Complete implementation plan
- **[CLAUDE.md](../CLAUDE.md)** - Project context and terminology
- **[docs/04-testing/README.md](../docs/04-testing/README.md)** - Overall testing strategy

## 📝 License

Part of the Missing Table project - see main repository for license.

---

**Last Updated:** 2025-01-07
**Status:** Phase 1 Complete - Swagger agent operational
**Next:** Phase 2 - Core agents implementation

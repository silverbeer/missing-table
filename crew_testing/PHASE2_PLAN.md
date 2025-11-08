# 🎯 Phase 2 Implementation Plan - Core Squad Activation

**Status:** 🚀 IN PROGRESS
**Goal:** End-to-end test generation for a single endpoint (`/api/matches`)
**Timeline:** 4-6 hours
**Date:** November 8, 2025

---

## 🎯 Phase 2 Objectives

### Primary Goal
Implement 4 agents that work together to **automatically generate complete test coverage** for `/api/matches` endpoint:

1. **🎯 ARCHITECT** - Designs test scenarios
2. **🎨 MOCKER** - Generates test data
3. **🔧 FORGE** - Generates api_client methods
4. **⚡ FLASH** - Executes tests and reports coverage

### Success Criteria
- ✅ All 4 agents operational and working together
- ✅ Complete test file generated for `/api/matches`
- ✅ Missing api_client methods auto-generated
- ✅ Tests execute successfully
- ✅ Coverage increases measurably
- ✅ CLI command: `./crew_testing/run.sh generate /api/matches`

---

## 🏗️ Architecture

### Sequential Workflow

```
┌──────────────────────────────────────────────────────────────┐
│                    PHASE 2 WORKFLOW                          │
└──────────────────────────────────────────────────────────────┘

📚 SWAGGER (existing)
   │
   ├─► Scans /openapi.json
   ├─► Identifies /api/matches endpoint details
   └─► Passes to ARCHITECT
        │
        │
🎯 ARCHITECT
   │
   ├─► Receives endpoint spec from Swagger
   ├─► Designs test scenarios:
   │   • Happy path (valid match)
   │   • Error cases (missing fields, invalid IDs)
   │   • Edge cases (date boundaries, same team)
   │   • Security (unauthorized access)
   └─► Passes scenarios to MOCKER
        │
        │
🎨 MOCKER
   │
   ├─► Receives test scenarios
   ├─► Queries DB schema for FK relationships
   ├─► Generates test data:
   │   • Valid matches with real team IDs
   │   • Invalid data for error tests
   │   • Edge case data
   └─► Passes data + scenarios to FORGE & FLASH
        │
        ├──────────────────┬──────────────────┐
        │                  │                  │
🔧 FORGE              ⚡ FLASH           RESULTS
   │                  │                  │
   ├─► Generates:    ├─► Executes:      ├─► Test file written
   │   • Test file   │   • pytest       │   to backend/tests/
   │   • api_client  │   • Coverage     │
   │      methods    │   • Report       ├─► api_client updated
   │                 │                  │
   └─► Writes code   └─► Returns:       └─► Coverage report
                         • Pass/fail        generated
                         • Coverage %
                         • Gaps found
```

---

## 🛠️ Implementation Steps

### Step 1: Create Tools for Phase 2

**New tools needed:**

1. **`query_schema_tool.py`** - Database schema inspector
   - Query Supabase for table relationships
   - Return FK constraints
   - Identify required vs optional fields

2. **`code_generator_tool.py`** - Code generation utility
   - Generate Python test functions
   - Generate api_client methods
   - Use templates for consistency

3. **`pytest_runner_tool.py`** - Test execution
   - Run pytest with coverage
   - Parse output (pass/fail counts)
   - Return coverage percentage

4. **`file_writer_tool.py`** - Safe file operations
   - Write test files to backend/tests/
   - Update api_client/client.py
   - Backup before overwrite

### Step 2: Implement ARCHITECT Agent

**File:** `crew_testing/agents/architect.py`

**Responsibilities:**
- Receive endpoint spec from Swagger
- Design comprehensive test scenarios
- Consider:
  - HTTP methods (GET, POST, PUT, DELETE, PATCH)
  - Required vs optional parameters
  - Authentication requirements
  - Validation rules
  - Response codes (200, 201, 400, 401, 404, 500)

**Tools:**
- `read_openapi_spec` (existing)
- `detect_gaps` (existing)

**Output Format:**
```python
{
    "endpoint": "/api/matches",
    "scenarios": [
        {
            "name": "test_create_match_success",
            "description": "Valid match creation with existing teams",
            "method": "POST",
            "expected_status": 201,
            "requires_auth": True,
            "test_data_requirements": ["home_team_id", "away_team_id", "match_date"]
        },
        {
            "name": "test_create_match_missing_field",
            "description": "Missing required field returns 400",
            "method": "POST",
            "expected_status": 400,
            "requires_auth": True,
            "test_data_requirements": ["incomplete_data"]
        },
        # ... more scenarios
    ]
}
```

### Step 3: Implement MOCKER Agent

**File:** `crew_testing/agents/mocker.py`

**Responsibilities:**
- Receive test scenarios from Architect
- Generate appropriate test data for each
- Respect database constraints
- Create fixtures for pytest

**Tools:**
- `query_schema_tool` (new)
- `generate_test_data` (embedded logic)

**Output Format:**
```python
{
    "fixtures": {
        "valid_match_data": {
            "home_team_id": 1,
            "away_team_id": 2,
            "match_date": "2025-06-15",
            "season_id": 1,
            "age_group_id": 3,
            "division_id": 2
        },
        "invalid_match_missing_team": {
            "home_team_id": None,
            "away_team_id": 2,
            "match_date": "2025-06-15"
        }
    },
    "test_data_map": {
        "test_create_match_success": "valid_match_data",
        "test_create_match_missing_field": "invalid_match_missing_team"
    }
}
```

### Step 4: Implement FORGE Agent

**File:** `crew_testing/agents/forge.py`

**Responsibilities:**
- Generate test file from scenarios + data
- Generate missing api_client methods
- Use proper pytest conventions
- Include docstrings and type hints

**Tools:**
- `code_generator_tool` (new)
- `file_writer_tool` (new)

**Output:**
- `backend/tests/test_matches_generated.py`
- Updated `backend/api_client/client.py` with missing methods

**Test File Template:**
```python
\"\"\"
Auto-generated tests for /api/matches endpoint
Generated by: MT Testing Crew - Forge Agent
Date: 2025-11-08
\"\"\"

import pytest
from api_client import APIClient

@pytest.fixture
def valid_match_data():
    return {
        "home_team_id": 1,
        "away_team_id": 2,
        "match_date": "2025-06-15",
        # ...
    }

def test_create_match_success(api_client: APIClient, valid_match_data):
    \"\"\"Test successful match creation with valid data\"\"\"
    response = api_client.create_match(valid_match_data)
    assert response.status_code == 201
    assert "id" in response.json()
```

### Step 5: Implement FLASH Agent

**File:** `crew_testing/agents/flash.py`

**Responsibilities:**
- Execute generated tests
- Run with coverage tracking
- Parse pytest output
- Report results

**Tools:**
- `pytest_runner_tool` (new)

**Output Format:**
```python
{
    "total_tests": 15,
    "passed": 12,
    "failed": 3,
    "skipped": 0,
    "coverage_before": 51.2,
    "coverage_after": 68.5,
    "coverage_delta": +17.3,
    "duration_seconds": 8.2,
    "failed_tests": [
        {
            "name": "test_create_match_unauthorized",
            "error": "AssertionError: Expected 401, got 403"
        }
    ]
}
```

### Step 6: Create Phase 2 Orchestration

**File:** `crew_testing/crew_config.py` (update)

**New function:** `run_test_generation(endpoint: str)`

```python
def run_test_generation(endpoint: str) -> str:
    """
    Run Phase 2: Generate tests for a specific endpoint

    Workflow:
    1. Swagger scans endpoint details
    2. Architect designs test scenarios
    3. Mocker generates test data
    4. Forge generates code
    5. Flash executes and reports
    """

    # Create crew with sequential task execution
    crew = Crew(
        agents=[swagger_agent, architect_agent, mocker_agent, forge_agent, flash_agent],
        tasks=[scan_task, design_task, mock_task, forge_task, execute_task],
        process=Process.sequential,
        verbose=CrewConfig.VERBOSE
    )

    # Execute workflow
    result = crew.kickoff(inputs={"endpoint": endpoint})
    return result
```

### Step 7: Update CLI

**File:** `crew_testing/main.py`

**New command:**
```python
@app.command()
def generate(
    endpoint: str = typer.Argument(..., help="Endpoint to generate tests for (e.g., /api/matches)"),
    backend_url: str = typer.Option("http://localhost:8000", "--url", "-u"),
    verbose: bool = typer.Option(False, "--verbose", "-v")
):
    """
    🔧 Generate complete test coverage for an endpoint (Phase 2)

    This command runs the full Phase 2 crew:
    - Architect designs test scenarios
    - Mocker generates test data
    - Forge generates code (tests + api_client)
    - Flash executes and reports results
    """
    console.print(f"[bold blue]Generating tests for: {endpoint}[/bold blue]")

    result = run_test_generation(endpoint)

    console.print(Panel(result, title="Generation Complete", border_style="green"))
```

---

## 📊 Testing Strategy

### Unit Testing Each Agent

**Test each agent independently:**

```bash
# Test Architect
./crew_testing/run.sh test-architect /api/matches

# Test Mocker
./crew_testing/run.sh test-mocker /api/matches

# Test Forge
./crew_testing/run.sh test-forge /api/matches

# Test Flash
./crew_testing/run.sh test-flash
```

### Integration Testing

**Test the full workflow:**

```bash
# Generate tests for /api/matches
./crew_testing/run.sh generate /api/matches

# Expected output:
# 🎯 Architect: Designing 15 test scenarios...
# 🎨 Mocker: Generating test data...
# 🔧 Forge: Writing test file...
# 🔧 Forge: Updating api_client...
# ⚡ Flash: Executing 15 tests...
# ✅ Results: 12 passed, 3 failed
# 📊 Coverage: 51.2% → 68.5% (+17.3%)
```

---

## 💰 Cost Estimates

### Phase 2 LLM Costs

| Agent | LLM | Cost/Run | Why |
|-------|-----|----------|-----|
| Architect | GPT-4o | $0.20 | Complex reasoning for test design |
| Mocker | Claude Haiku | $0.05 | Data generation is straightforward |
| Forge | GPT-4o | $0.20 | Code generation requires intelligence |
| Flash | Claude Haiku | $0.05 | Test execution is procedural |
| **Total** | | **$0.50** | Per endpoint |

**Development costs:**
- Testing: ~10 runs × $0.50 = $5.00
- Refinement: ~20 runs × $0.50 = $10.00
- **Total Phase 2 dev:** ~$15.00

**Production usage:**
- Per endpoint: $0.50
- 73 endpoints: $36.50 (one-time for full coverage)

---

## 🎯 Success Metrics

### Phase 2 Complete When:

- ✅ All 4 agents implemented and tested
- ✅ `./crew_testing/run.sh generate /api/matches` works end-to-end
- ✅ Generated test file is valid Python
- ✅ Generated api_client methods are functional
- ✅ Tests execute via pytest
- ✅ Coverage improvement is measurable
- ✅ Documentation updated
- ✅ PHASE2_COMPLETE.md written

### Demo-Ready Criteria:

- ✅ Can run live demo in < 2 minutes
- ✅ Output is visually impressive (rich formatting)
- ✅ Before/after coverage comparison is clear
- ✅ Generated code is readable and professional
- ✅ Error handling is graceful

---

## 📝 Documentation Requirements

### Files to Create/Update:

1. **PHASE2_COMPLETE.md** - Phase 2 completion report
2. **PHASE2_ARCHITECTURE.md** - Technical deep dive
3. **README.md** - Update with Phase 2 commands
4. **TESTING_GUIDE.md** - Add Phase 2 testing scenarios
5. **IMPLEMENTATION_SUMMARY.md** - Update with Phase 2 details

---

## 🚀 Next Steps After Phase 2

### Phase 3: Intelligence Layer
- 🔬 Inspector - Analyze test patterns
- 📊 Herald - Generate beautiful reports
- 🐛 Sherlock - Debug test failures

### Phase 4: Production Deployment
- GitHub Actions integration
- PR automation
- Demo video
- Interview presentation

---

## 🎯 Let's Build!

**Starting with:** ARCHITECT agent
**Then:** MOCKER → FORGE → FLASH
**Timeline:** 4-6 hours total
**LFG!** 🚀

---

*Last Updated: November 8, 2025*
*Status: Implementation Starting*
*Phase: 2 of 4*

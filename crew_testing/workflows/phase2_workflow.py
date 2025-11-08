"""
Phase 2 Workflow - End-to-End Test Generation

Orchestrates the 4-agent workflow:
1. ARCHITECT - Design test scenarios
2. MOCKER - Generate test data
3. FORGE - Generate test code
4. FLASH - Execute tests

Usage:
    from crew_testing.workflows.phase2_workflow import run_phase2_workflow
    result = run_phase2_workflow("/api/matches")
"""

from crewai import Crew, Task, Process
from rich.console import Console

from crew_testing.config import CrewConfig
from crew_testing.agents import (
    create_architect_agent,
    get_architect_task_description,
    create_mocker_agent,
    get_mocker_task_description,
    create_forge_agent,
    get_forge_task_description,
    create_flash_agent,
    get_flash_task_description,
)

console = Console()


def run_phase2_workflow(
    endpoint: str,
    backend_url: str = "http://localhost:8000",
    verbose: bool = False
) -> str:
    """
    Run the complete Phase 2 workflow for an endpoint

    This orchestrates all 4 agents in sequence:
    1. ARCHITECT designs test scenarios
    2. MOCKER generates test data fixtures
    3. FORGE generates pytest test file
    4. FLASH executes tests and reports results

    Args:
        endpoint: API endpoint to test (e.g., "/api/matches")
        backend_url: Base URL of MT backend
        verbose: Show detailed agent conversations

    Returns:
        Final test execution report from FLASH
    """
    # Update config
    CrewConfig.VERBOSE = verbose

    # Create agents
    architect = create_architect_agent()
    mocker = create_mocker_agent()
    forge = create_forge_agent()
    flash = create_flash_agent()

    # Create tasks with sequential dependencies
    # ARCHITECT: Design test scenarios
    task_architect = Task(
        description=f"""
Analyze the {{endpoint}} endpoint and design comprehensive test scenarios.

Your task:
1. Read the OpenAPI spec for {{endpoint}}
2. Understand the endpoint's purpose, parameters, and expected behavior
3. Design test scenarios covering:
   - Happy path (valid requests)
   - Error cases (missing/invalid data)
   - Edge cases (boundaries, empty values)
   - Security concerns (injection, auth)
   - Performance (large data, pagination)

Output a detailed test plan in JSON format with comprehensive scenarios.
Be thorough. Think of scenarios developers wouldn't consider.
""",
        expected_output="JSON test plan with comprehensive scenarios",
        agent=architect,
    )

    # MOCKER: Generate test data (depends on ARCHITECT)
    task_mocker = Task(
        description="""
Based on the test scenarios from ARCHITECT (provided in context), generate realistic test data.

Your task:
1. Review the test scenarios and their test_data_requirements
2. Query the database schema to understand table structures and foreign keys
3. Generate pytest fixtures for each unique data requirement
4. Ensure data is realistic and matches database constraints

Output a JSON mapping of fixture names to fixture definitions.
Be realistic. Use actual team names, dates that make sense, etc.
Query the schema to understand what fields are required and what foreign keys exist.
""",
        expected_output="JSON mapping of fixture names to fixture definitions",
        agent=mocker,
        context=[task_architect],  # Gets ARCHITECT output automatically
    )

    # FORGE: Generate test code (depends on ARCHITECT and MOCKER)
    task_forge = Task(
        description="""
Generate a COMPLETE pytest test file with BOTH fixtures AND test functions.

⚠️  CRITICAL: Do NOT stop after generating fixtures! You MUST generate test functions!

Step-by-step instructions:
1. Review scenarios from ARCHITECT (in context)
2. Create file header with imports:
   ```python
   \"\"\"Test suite for {{endpoint}} endpoint\"\"\"
   import pytest
   from fastapi.testclient import TestClient
   from backend.app import app

   client = TestClient(app)
   ```

3. Generate simple test functions (NOT fixtures unless absolutely needed):
   ```python
   def test_get_version_success():
       \"\"\"Test successful GET request\"\"\"
       response = client.get("/api/version")
       assert response.status_code == 200
       assert "version" in response.json()

   def test_invalid_method():
       \"\"\"Test POST to GET-only endpoint\"\"\"
       response = client.post("/api/version")
       assert response.status_code == 405
   ```

4. Write ONE test function per scenario from ARCHITECT
5. Keep tests simple: request → assert status → assert response data
6. Use write_file tool to save to `backend/tests/test_<name>.py`

REQUIREMENTS:
- Minimum 3 test functions
- Each test: docstring, client request, 2+ assertions
- Use client.get(), client.post(), client.put(), client.delete()
- NO complex setup - keep it simple!

Output JSON: {{"file_path": "backend/tests/test_version.py", "total_tests": 6}}
""",
        expected_output="Test file path with confirmation that test functions were generated",
        agent=forge,
        context=[task_architect, task_mocker],  # Gets both outputs automatically
    )

    # FLASH: Execute tests (depends on FORGE)
    task_flash = Task(
        description="""
Execute the generated pytest tests and report results.

Your task:
1. Run pytest on the generated test file (from FORGE in context)
2. Parse the test results
3. Report on passes, failures, errors
4. Track coverage metrics
5. Provide actionable feedback on failures

Output a comprehensive test report.
If all tests pass, celebrate! 🎉
If tests fail, provide ACTIONABLE feedback - not just "test failed" but WHY and HOW TO FIX.
""",
        expected_output="Comprehensive test execution report with coverage metrics",
        agent=flash,
        context=[task_forge],  # Gets FORGE output automatically
    )

    # Create crew with sequential process
    crew = Crew(
        agents=[architect, mocker, forge, flash],
        tasks=[task_architect, task_mocker, task_forge, task_flash],
        process=Process.sequential,  # Execute in order
        verbose=verbose,
    )

    # Execute workflow
    console.print(f"\n[bold blue]🚀 Starting Phase 2 workflow for {endpoint}[/bold blue]\n")
    console.print("[cyan]📚 ARCHITECT → 🎨 MOCKER → 🔧 FORGE → ⚡ FLASH[/cyan]\n")

    result = crew.kickoff(inputs={
        "endpoint": endpoint,
        "backend_url": backend_url,
    })

    return str(result)


# Export for CLI usage
__all__ = ["run_phase2_workflow"]

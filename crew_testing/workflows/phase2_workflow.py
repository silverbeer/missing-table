"""
Phase 2 Workflow - End-to-End Test Generation

Orchestrates the 5-agent workflow:
1. ARCHITECT - Design test scenarios
2. MOCKER - Generate test data
3. FORGE - Generate test code
4. FLASH - Execute tests
5. MECHANIC - Fix failing tests (if needed)
6. FLASH - Verify fixes (re-run tests)

Usage:
    from crew_testing.workflows.phase2_workflow import run_phase2_workflow
    result = run_phase2_workflow("/api/matches")
"""

import time
import json
import re
from crewai import Crew, Task, Process
from rich.console import Console

from crew_testing.config import CrewConfig
from crew_testing.logger import CrewLogger
from crew_testing.lib import TestStateManager
from crew_testing.agents import (
    create_architect_agent,
    get_architect_task_description,
    create_mocker_agent,
    get_mocker_task_description,
    create_forge_agent,
    get_forge_task_description,
    create_flash_agent,
    get_flash_task_description,
    create_mechanic_agent,
    get_mechanic_task_description,
)

console = Console()


def run_phase2_workflow(
    endpoint: str,
    backend_url: str = "http://localhost:8000",
    verbose: bool = False
) -> str:
    """
    Run the complete Phase 2 workflow for an endpoint

    This orchestrates all 5 agents in sequence:
    1. ARCHITECT designs test scenarios
    2. MOCKER generates test data fixtures
    3. FORGE generates pytest test file
    4. FLASH executes tests and reports results
    5. MECHANIC fixes failing tests (if any failures)
    6. FLASH verifies fixes (re-runs tests)

    Args:
        endpoint: API endpoint to test (e.g., "/api/matches")
        backend_url: Base URL of MT backend
        verbose: Show detailed agent conversations

    Returns:
        Final test execution report from FLASH (after fixes)
    """
    # Initialize logger
    logger = CrewLogger("phase2", "workflow")
    start_time = time.time()

    logger.section(f"🚀 Phase 2 Workflow - {endpoint}")
    logger.info(f"Backend URL: {backend_url}")
    logger.info(f"Verbose mode: {verbose}")

    # Update config
    CrewConfig.VERBOSE = verbose

    # Create agents
    logger.section("Step 1: Create Agents")
    architect = create_architect_agent()
    mocker = create_mocker_agent()
    forge = create_forge_agent()
    flash = create_flash_agent()
    mechanic = create_mechanic_agent()
    flash_verify = create_flash_agent()  # Second FLASH instance for verification
    logger.success("Created 6 agents: ARCHITECT, MOCKER, FORGE, FLASH, MECHANIC, FLASH (verify)")

    # Create tasks with sequential dependencies
    logger.section("Step 2: Create Tasks")
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

    # MECHANIC: Fix failing tests (depends on FLASH)
    task_mechanic = Task(
        description="""
Analyze test failures from FLASH and fix the test file.

Your task:
1. Review the test failure report from FLASH (provided in context)
2. Identify the root cause of each failure
3. Update the test file with fixes
4. Focus on fixable test issues (not API bugs)

Common fixes:
- Add authentication headers for 403 Forbidden errors
- Fix assertions for incorrect expected values
- Generate valid test data
- Add required fixtures

Output JSON with fixes applied and confirmation that file was updated.
Be surgical - only fix what's broken, preserve everything else.
""",
        expected_output="JSON report of fixes applied with file path",
        agent=mechanic,
        context=[task_flash],  # Gets FLASH output automatically
    )

    # FLASH VERIFY: Re-run tests after fixes (depends on MECHANIC)
    task_flash_verify = Task(
        description="""
Re-execute the pytest tests after MECHANIC's fixes and report final results.

Your task:
1. Run pytest on the test file from FORGE (path in FORGE's context: backend/tests/test_<endpoint>.py)
2. MECHANIC may have updated the file - use the SAME path FORGE created
3. Parse the test results
4. Report on passes, failures, errors
5. Track coverage metrics
6. Compare with initial FLASH results - did tests improve?

IMPORTANT: Use the EXACT file path from FORGE's output, like "backend/tests/test_version.py"
DO NOT use generic paths like "fixed_test_file.py" or "test_file.py"

Output a comprehensive test report.
If all tests pass now, celebrate! 🎉🎉
If tests still fail, report what's still broken.
""",
        expected_output="Final test execution report with coverage metrics after fixes",
        agent=flash_verify,
        context=[task_forge, task_mechanic],  # Gets BOTH FORGE and MECHANIC outputs
    )

    logger.success("Created 6 tasks with sequential dependencies")

    # Create crew with sequential process
    logger.section("Step 3: Execute Workflow")
    crew = Crew(
        agents=[architect, mocker, forge, flash, mechanic, flash_verify],
        tasks=[task_architect, task_mocker, task_forge, task_flash, task_mechanic, task_flash_verify],
        process=Process.sequential,  # Execute in order
        verbose=verbose,
    )
    logger.info("Crew assembled with 6 agents and 6 tasks")

    # Execute workflow
    console.print(f"\n[bold blue]🚀 Starting Phase 2 workflow for {endpoint}[/bold blue]\n")
    console.print("[cyan]📚 ARCHITECT → 🎨 MOCKER → 🔧 FORGE → ⚡ FLASH → 🔨 MECHANIC → ⚡ FLASH (verify)[/cyan]\n")

    logger.info("Starting crew kickoff...")
    result = crew.kickoff(inputs={
        "endpoint": endpoint,
        "backend_url": backend_url,
    })

    # Log completion
    duration = time.time() - start_time
    logger.section("✅ Workflow Complete")
    logger.success(f"Duration: {duration:.2f} seconds")
    logger.info(f"Log file: crew_testing/logs/workflows/phase2_*.log")

    # Register test in manifest
    try:
        from pathlib import Path
        import os
        state = TestStateManager()

        # Derive test file path from endpoint
        # /api/version -> backend/tests/test_version.py
        endpoint_name = endpoint.strip('/').split('/')[-1]  # "version" from "/api/version"
        test_file = f"backend/tests/test_{endpoint_name}.py"

        # Find project root (directory containing crew_testing/main.py - the CLI entry point)
        current_dir = Path.cwd()
        project_root = current_dir
        while project_root != project_root.parent:
            if (project_root / "crew_testing" / "main.py").exists():
                break
            project_root = project_root.parent

        # Check if the test file actually exists (using absolute path)
        test_file_path = project_root / test_file
        if test_file_path.exists():
            # Register the test (using relative path from project root)
            endpoint_hash = state.hash_endpoint_definition(endpoint)
            state.register_test(endpoint, test_file, endpoint_hash)
            logger.success(f"Registered test in manifest: {endpoint} -> {test_file}")

            # Extract test results from output
            result_str = str(result)
            passed_match = re.search(r'(\d+)\s*passed', result_str)
            failed_match = re.search(r'(\d+)\s*failed', result_str)

            if passed_match or failed_match:
                passed = int(passed_match.group(1)) if passed_match else 0
                failed = int(failed_match.group(1)) if failed_match else 0
                total = passed + failed

                state.update_test_results(endpoint, {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "duration_ms": int(duration * 1000)
                })
                logger.success(f"Updated test cache: {passed}/{total} passed")
        else:
            logger.warning(f"Test file not found: {test_file} - test not registered")

    except Exception as e:
        logger.warning(f"Failed to register test: {e}")
        # Continue anyway - registration failure shouldn't break the workflow

    logger.close()

    return str(result)


# Export for CLI usage
__all__ = ["run_phase2_workflow"]

"""
⚡ Flash - Test Executor

Tagline: "Speed force testing"

Role: Test execution and results reporting

Responsibilities:
- Execute pytest tests
- Parse test results
- Report failures and errors
- Track coverage metrics
- Provide actionable feedback

Uses PytestRunnerTool to execute tests and parse results.
"""

from crewai import Agent

from crew_testing.config import CrewConfig
from crew_testing.tools import PytestRunnerTool


def create_flash_agent() -> Agent:
    """
    Create the Flash agent for test execution

    Uses Claude 3 Haiku for cost-effective test execution

    Returns:
        Configured CrewAI Agent
    """
    # Get LLM for this agent from config
    llm = CrewConfig.get_llm_for_agent("flash")

    # Initialize tools
    tools = [
        PytestRunnerTool(),
    ]

    # Create agent
    agent = Agent(
        role="Test Executor",
        goal=(
            "Execute pytest tests efficiently and report results clearly. "
            "Identify failures, track coverage, and provide actionable feedback."
        ),
        backstory=(
            "You are a speed demon when it comes to running tests. You execute tests "
            "with lightning speed and precision, parsing results to find exactly what "
            "went wrong when tests fail. "
            "\n\n"
            "Your superpower is clarity. When tests fail, you don't just say 'test failed' - "
            "you explain:\n"
            "1. **Which test failed**: Exact test name and file\n"
            "2. **Why it failed**: The assertion that failed, expected vs actual\n"
            "3. **Where it failed**: Line number and traceback\n"
            "4. **What to fix**: Actionable suggestions\n"
            "\n\n"
            "You understand pytest output deeply:\n"
            "- `.` means passed\n"
            "- `F` means failed\n"
            "- `E` means error (test couldn't even run)\n"
            "- `s` means skipped\n"
            "- Coverage percentage tells you how much code was exercised\n"
            "\n\n"
            "You run tests with coverage tracking so developers know:\n"
            "- Which lines of code are tested\n"
            "- Which lines are NOT tested (coverage gaps)\n"
            "- Overall coverage percentage\n"
            "\n\n"
            "When all tests pass, you celebrate! 🎉\n"
            "When tests fail, you provide clear, actionable feedback so developers can fix them quickly.\n"
            "\n\n"
            "You're not just running tests - you're providing quality assurance with speed and clarity."
        ),
        verbose=CrewConfig.VERBOSE,
        llm=llm,
        tools=tools,
        max_iter=10,  # Increased for test execution and reporting
        allow_delegation=False,
    )

    return agent


def get_flash_task_description() -> str:
    """
    Get the task description for the Flash agent

    Returns:
        Task description string
    """
    return """
Execute the generated pytest tests and report results.

Your task:
1. Run pytest on the generated test file
2. Parse the test results
3. Report on passes, failures, errors
4. Track coverage metrics
5. Provide actionable feedback on failures

Input from FORGE:
{forge_output}

Output a comprehensive test report:
{{
    "test_file": "backend/tests/test_matches.py",
    "execution_summary": {{
        "total_tests": 15,
        "passed": 13,
        "failed": 2,
        "errors": 0,
        "skipped": 0,
        "duration_seconds": 2.34
    }},
    "coverage": {{
        "percentage": 87,
        "lines_covered": 234,
        "lines_total": 269,
        "missing_lines": [45, 67, 89, 112, 143]
    }},
    "failures": [
        {{
            "test_name": "test_create_match_same_teams",
            "error_message": "AssertionError: Expected 400, got 201",
            "traceback": "...",
            "suggested_fix": "The API is not validating that home_team != away_team. Add validation in the endpoint."
        }},
        {{
            "test_name": "test_sql_injection_in_match_creation",
            "error_message": "AssertionError: Expected 400, got 500",
            "traceback": "...",
            "suggested_fix": "SQL injection payload caused a server error. Add input sanitization."
        }}
    ]
}}

If all tests pass, celebrate! 🎉
If tests fail, provide ACTIONABLE feedback - not just "test failed" but WHY and HOW TO FIX.
"""


# Export for agent creation
__all__ = ["create_flash_agent", "get_flash_task_description"]

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
        goal="Execute pytest tests and report the raw results. Simple and fast.",
        backstory=(
            "You are FLASH - the fastest test runner in the crew. "
            "Your job is simple: run tests using the run_pytest tool and report what it says. "
            "\n\n"
            "You don't analyze. You don't format. You don't suggest fixes. "
            "You just RUN tests and pass the results to the next agent. "
            "\n\n"
            "Speed is your superpower. One tool call, one result, done. ⚡"
        ),
        verbose=CrewConfig.VERBOSE,
        llm=llm,
        tools=tools,
        max_iter=5,  # Simple task needs fewer iterations
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

FORGE created a test file. Your job is simple:
1. Use the run_pytest tool with the test file path
2. Return whatever the tool outputs

That's it! Don't analyze, don't format, don't suggest fixes.
Just run the tests and report the tool's output.

Input from FORGE:
{forge_output}

Example:
Action: run_pytest
Action Input: {{"test_path": "backend/tests/test_version.py", "coverage": true}}
"""


# Export for agent creation
__all__ = ["create_flash_agent", "get_flash_task_description"]

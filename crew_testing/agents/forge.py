"""
🔧 Forge - Test Infrastructure Engineer

Tagline: "Forging quality, one test at a time"

Role: Test code generator and infrastructure maintainer

Responsibilities:
- Generate pytest test files from scenarios and fixtures
- Generate api_client methods for untested endpoints
- Write syntactically correct Python code
- Follow pytest best practices
- Maintain test infrastructure

Uses CodeGeneratorTool and FileWriterTool to create test files.
"""

from crewai import Agent

from crew_testing.config import CrewConfig
from crew_testing.tools import CodeGeneratorTool, FileWriterTool


def create_forge_agent() -> Agent:
    """
    Create the Forge agent for test code generation

    Uses GPT-4o for complex code generation reasoning

    Returns:
        Configured CrewAI Agent
    """
    # Get LLM for this agent from config
    llm = CrewConfig.get_llm_for_agent("forge")

    # Initialize tools
    tools = [
        CodeGeneratorTool(),
        FileWriterTool(),
    ]

    # Create agent
    agent = Agent(
        role="Test Infrastructure Engineer",
        goal=(
            "Generate clean, maintainable pytest test code that follows best practices. "
            "Create test files that are easy to read, well-documented, and properly structured."
        ),
        backstory=(
            "You are a master Python developer specializing in pytest and test infrastructure. "
            "You've written thousands of test files and know every pytest best practice. "
            "\n\n"
            "Your code is characterized by:\n"
            "1. **Clarity**: Clear test names, good docstrings, readable assertions\n"
            "2. **DRY Principle**: Reusable fixtures, no code duplication\n"
            "3. **Best Practices**: Proper use of fixtures, markers, parametrize\n"
            "4. **Proper Structure**: Arrange-Act-Assert pattern\n"
            "5. **Good Documentation**: Docstrings explaining what each test verifies\n"
            "\n\n"
            "You understand the MT testing ecosystem:\n"
            "- Tests live in `backend/tests/`\n"
            "- API client lives in `backend/api_client/`\n"
            "- Fixtures should be reusable across multiple tests\n"
            "- Always import from the right modules\n"
            "\n\n"
            "You generate code that:\n"
            "- Uses proper type hints\n"
            "- Has comprehensive docstrings\n"
            "- Follows PEP 8 style guide\n"
            "- Validates syntax before writing\n"
            "- Creates backups before overwriting files\n"
            "\n\n"
            "You're not just generating code - you're building test infrastructure that "
            "developers will rely on for years."
        ),
        verbose=CrewConfig.VERBOSE,
        llm=llm,
        tools=tools,
        max_iter=25,  # Increased for complete test file generation
        allow_delegation=False,
    )

    return agent


def get_forge_task_description() -> str:
    """
    Get the task description for the Forge agent

    Returns:
        Task description string
    """
    return """
Generate pytest test files based on test scenarios and fixtures.

Your task:
1. Review test scenarios from ARCHITECT
2. Review fixtures from MOCKER
3. Use the write_file tool DIRECTLY to create the test file
4. DO NOT use generate_code tool - just write the file directly

Input from ARCHITECT:
{architect_output}

Input from MOCKER:
{mocker_output}

IMPORTANT - Tool Usage:
ALWAYS use write_file tool with ABSOLUTE path "backend/tests/test_<endpoint>.py"

For endpoint /api/version → file_path: "backend/tests/test_version.py"
For endpoint /api/matches → file_path: "backend/tests/test_matches.py"

NEVER use relative paths like "tests/test_version.py" - ALWAYS include "backend/" prefix!

Example tool call:
Action: write_file
Action Input: {{
    "file_path": "backend/tests/test_version.py",
    "content": "\"\"\"\\nTest suite for /api/version endpoint\\n\"\"\"\\nimport pytest\\nfrom fastapi.testclient import TestClient\\nfrom backend.app import app\\n\\nclient = TestClient(app)\\n\\n\\ndef test_get_version_success():\\n    \"\"\"Test successful GET request\"\"\"\\n    response = client.get(\"/api/version\")\\n    assert response.status_code == 200\\n    assert \\\"version\\\" in response.json()\\n",
    "backup": true,
    "validate": true
}}

Test file structure:
```python
\"\"\"Test suite for {endpoint} endpoint\"\"\"
import pytest
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_example():
    \"\"\"Test description\"\"\"
    response = client.get("/api/endpoint")
    assert response.status_code == 200
```

After writing, return:
File written successfully: backend/tests/test_version.py
Tests: 7 scenarios
Lines: 56
"""


# Export for agent creation
__all__ = ["create_forge_agent", "get_forge_task_description"]

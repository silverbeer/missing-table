"""
🔧 Mechanic - Test Fixer

Tagline: "I fix what breaks"

Role: Test debugging and repair specialist

Responsibilities:
- Analyze test failure reports from FLASH
- Identify root causes of test failures
- Fix test code to make tests pass
- Handle common issues:
  - Missing authentication
  - Incorrect assertions
  - Wrong expected values
  - Missing fixtures
  - Database state issues

Uses FileWriterTool to update test files based on failure analysis.
"""

from crewai import Agent

from crew_testing.config import CrewConfig
from crew_testing.tools import FileWriterTool


def create_mechanic_agent() -> Agent:
    """
    Create the Mechanic agent for fixing failing tests

    Uses Claude Sonnet for intelligent test debugging

    Returns:
        Configured CrewAI Agent
    """
    # Get LLM for this agent from config
    llm = CrewConfig.get_llm_for_agent("mechanic")

    # Initialize tools
    tools = [
        FileWriterTool(),
    ]

    # Create agent
    agent = Agent(
        role="Test Repair Specialist",
        goal=(
            "Analyze test failures and fix test code to make tests pass. "
            "Understand why tests fail and apply the right fixes."
        ),
        backstory=(
            "You are a master debugger with years of experience fixing flaky tests. "
            "When tests fail, you don't panic - you analyze, understand, and fix. "
            "\n\n"
            "Your diagnostic process:\n"
            "1. **Read the failure report**: What test failed? What was the error?\n"
            "2. **Understand the root cause**: Why did it fail?\n"
            "   - 403 Forbidden = Missing authentication\n"
            "   - 401 Unauthorized = Invalid/expired token\n"
            "   - 400 Bad Request = Invalid input data\n"
            "   - 422 Validation Error = Schema mismatch\n"
            "   - 500 Server Error = Backend bug (not test issue)\n"
            "   - AssertionError = Wrong expected value\n"
            "3. **Apply the fix**: Update the test file with the correct solution\n"
            "4. **Verify**: Ensure the fix is minimal and correct\n"
            "\n\n"
            "Common fixes you apply:\n"
            "- **Authentication**: Add auth headers to requests that need them\n"
            "- **Fixtures**: Create pytest fixtures for test data\n"
            "- **Assertions**: Fix expected values based on actual API behavior\n"
            "- **Test data**: Generate valid test data that matches constraints\n"
            "- **Setup/Teardown**: Add proper test setup when needed\n"
            "\n\n"
            "You understand the difference between:\n"
            "- **Test bugs** (fixable) - Wrong assertions, missing auth, bad test data\n"
            "- **API bugs** (not fixable by you) - Backend returns wrong status, crashes\n"
            "\n\n"
            "When you fix tests, you:\n"
            "- Make minimal changes (only fix what's broken)\n"
            "- Keep tests simple and readable\n"
            "- Add comments explaining non-obvious fixes\n"
            "- Preserve the original test intent\n"
            "\n\n"
            "You're not just fixing tests - you're making them robust and maintainable."
        ),
        verbose=CrewConfig.VERBOSE,
        llm=llm,
        tools=tools,
        max_iter=20,  # Allow iterations for fixing multiple issues
        allow_delegation=False,
    )

    return agent


def get_mechanic_task_description() -> str:
    """
    Get the task description for the Mechanic agent

    Returns:
        Task description string
    """
    return """
Analyze test failures from FLASH and fix the test file.

Your task:
1. Review the test failure report from FLASH (provided in context)
2. Identify the root cause of each failure
3. Update the test file with fixes
4. Focus on fixable test issues (not API bugs)

Input from FLASH:
{flash_output}

Common fixes:
- **403 Forbidden**: Add authentication headers
  ```python
  # Add auth fixture
  @pytest.fixture
  def auth_headers():
      # Login and get token
      response = client.post("/api/auth/login", json={
          "username": "test_user",
          "password": "test_pass"  # pragma: allowlist secret
      })
      token = response.json()["access_token"]
      return {"Authorization": f"Bearer {token}"}

  # Use in test
  def test_get_matches(auth_headers):
      response = client.get("/api/matches", headers=auth_headers)
      assert response.status_code == 200
  ```

- **Wrong assertion**: Update expected value
  ```python
  # Before: assert "error" in data
  # After: assert "detail" in data  # API uses 'detail' not 'error'
  ```

- **Invalid test data**: Generate valid data
  ```python
  # Before: {"page": -1}  # Invalid
  # After: {"page": 1}    # Valid
  ```

Output format (JSON):
{{
    "fixes_applied": [
        {{
            "test_name": "test_get_matches_default_parameters",
            "issue": "403 Forbidden - missing authentication",
            "fix": "Added auth_headers fixture and passed to all auth-required tests"
        }},
        {{
            "test_name": "test_unauthorized_access_attempt",
            "issue": "Response uses 'detail' not 'error' key",
            "fix": "Changed assertion from 'error' to 'detail'"
        }}
    ],
    "file_path": "backend/tests/test_matches.py",
    "total_fixes": 2,
    "ready_for_retest": true
}}

Use write_file tool to save the fixed test file.
Be surgical - only fix what's broken, preserve everything else.
"""


# Export for agent creation
__all__ = ["create_mechanic_agent", "get_mechanic_task_description"]

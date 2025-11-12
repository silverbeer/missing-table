"""
Phase 3: Unit Test Generation Workflow

This workflow uses 4 agents to generate unit tests for Python modules:
1. Inspector - Analyzes code and identifies coverage gaps
2. Architect - Designs unit test scenarios based on gaps
3. Forge - Generates pytest code with mocks
4. Flash - Executes tests and measures coverage improvement

Usage:
    python unit_test_workflow.py backend/auth.py
    python unit_test_workflow.py backend/dao/enhanced_data_access_fixed.py --coverage-target 80
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crewai import Crew, Task, Process
from crew_testing.agents.inspector import create_inspector_agent
from crew_testing.agents.architect import create_architect_agent
from crew_testing.agents.forge import create_forge_agent
from crew_testing.agents.flash import create_flash_agent
from crew_testing.config import CrewConfig


def create_unit_test_crew(module_path: str, coverage_target: int = 80) -> Crew:
    """
    Create a CrewAI crew for unit test generation

    Args:
        module_path: Path to Python module to test
        coverage_target: Target coverage percentage (default: 80%)

    Returns:
        Configured CrewAI Crew
    """

    # Create agents
    inspector = create_inspector_agent()
    architect = create_architect_agent()
    forge = create_forge_agent()
    flash = create_flash_agent()

    # Task 1: Inspector analyzes code and coverage
    inspector_task = Task(
        description=f"""
        Analyze the Python module and identify testing gaps.

        Module: {module_path}

        Steps:
        1. Use analyze_code tool to extract functions, methods, complexity
        2. Use analyze_coverage tool to find uncovered lines
        3. Use generate_gap_report tool to prioritize testing gaps

        IMPORTANT: Your final output should ONLY be the gap report from step 3.
        Do NOT include the full code analysis or coverage analysis in your output.

        The gap report should show:
        - Critical priority functions (complex, large, untested)
        - High priority functions
        - Medium/Low priority functions
        - Recommended test count to reach {coverage_target}% coverage
        - For top 5 CRITICAL functions: include exception handling patterns and return behavior

        Focus on functions that need the most testing attention.
        Keep the report concise - Architect only needs the prioritized gaps.
        """,
        expected_output="Concise prioritized gap report (not full code analysis)",
        agent=inspector,
    )

    # Task 2: Architect designs unit test scenarios
    architect_task = Task(
        description="""
        Design comprehensive unit test scenarios based on Inspector's gap report.

        Context: You will receive a gap report from Inspector showing which functions
        are untested or poorly tested. Your job is to design test scenarios for these
        functions.

        For each HIGH and CRITICAL priority function, design:

        1. **Happy Path Tests**: Normal operation with valid inputs
           - Test with typical parameter values
           - Verify expected return values
           - Check that dependencies are called correctly

        2. **Error Handling Tests**: How function handles problems
           - Invalid input types (None, wrong type, negative numbers)
           - Boundary conditions (empty lists, max values, edge cases)
           - External dependency failures (database errors, network timeouts)

        3. **Edge Cases**: Unusual but valid scenarios
           - Empty strings, zero values, special characters
           - Maximum/minimum allowed values
           - Concurrent access (if relevant)

        For each test scenario, specify:
        - Test name (descriptive, follows pytest naming)
        - Purpose (what behavior it verifies)
        - Required mocks (which dependencies to mock)
        - Mock behavior (what mocked methods should return)
        - Assertions (what to verify in the result)

        Output format (JSON):
        {
            "module": "backend/auth.py",
            "scenarios": [
                {
                    "function": "AuthManager.verify_token",
                    "priority": "CRITICAL",
                    "tests": [
                        {
                            "name": "test_verify_token_valid_jwt",
                            "purpose": "Verify that valid JWT token is decoded correctly",
                            "category": "happy_path",
                            "mocks": {
                                "jwt.decode": "returns {'sub': 'user123', 'role': 'admin'}",
                                "supabase.table().select().eq().execute()": "returns Mock with .data = [{'id': 'user123', 'username': 'testuser', 'role': 'admin'}]"
                            },
                            "assertions": [
                                "user_data['username'] == 'testuser'",
                                "user_data['role'] == 'admin'"
                            ]
                        },
                        {
                            "name": "test_verify_token_expired",
                            "purpose": "Verify that expired token returns None (not raises exception)",
                            "category": "error",
                            "mocks": {
                                "jwt.decode": "raises jwt.ExpiredSignatureError"
                            },
                            "assertions": [
                                "result is None"
                            ]
                        }
                    ]
                }
            ]
        }

        Design tests for at least 5 CRITICAL priority functions from the gap report.
        """,
        expected_output="JSON-formatted unit test scenarios with mocking strategies",
        agent=architect,
        context=[inspector_task],  # Receives gap report from Inspector
    )

    # Task 3: Forge generates pytest code
    forge_task = Task(
        description="""
        Generate pytest unit test code based on Architect's test scenarios.

        Context: You will receive test scenarios from Architect. Your job is to
        write clean, working pytest code that implements these scenarios.

        Requirements:

        1. **File Structure**:
           - Create test file in backend/tests/unit/
           - Follow naming: test_<module_name>.py
           - Example: backend/auth.py → backend/tests/unit/test_auth.py

        2. **Code Quality**:
           - Use pytest fixtures for common setup
           - Use @pytest.mark.unit decorator
           - Use @patch decorators for mocking external dependencies
           - Follow Arrange-Act-Assert pattern
           - Include docstrings for each test
           - Use type hints

        3. **CRITICAL: Supabase Mocking Strategy**:

           **Problem:** Supabase uses method chaining: `client.table().select().eq().execute()`

           **Solution:** Mock the entire chain with return_value chaining

           ```python
           # ❌ WRONG - This will crash with "object of type 'Mock' has no len()"
           mock_supabase = Mock()
           auth_manager = AuthManager(supabase_client=mock_supabase)

           # ✅ CORRECT - Mock the full chain
           mock_supabase = Mock()
           mock_response = Mock()
           mock_response.data = [{  # Must be a list of dicts
               'id': 'user123',
               'username': 'testuser',
               'role': 'admin',
               'team_id': None,
               'display_name': 'Test User'
           }]

           # Configure the chain: table().select().eq().execute()
           mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

           auth_manager = AuthManager(supabase_client=mock_supabase)
           result = auth_manager.verify_token('token')
           # Now result will have data!
           ```

           **Key Points:**
           - `execute()` must return an object with `.data` attribute
           - `.data` must be a list (even for single result)
           - Each dict in the list should have all required fields

        4. **Exception Handling Tests**:

           **IMPORTANT:** Pay attention to the gap report's "Exception Handling" field!

           If it says: "jwt.ExpiredSignatureError → returns None"

           Then test should check for None return, NOT expect exception to be raised:

           ```python
           # ❌ WRONG - Function catches exception and returns None
           with pytest.raises(jwt.ExpiredSignatureError):
               result = auth_manager.verify_token('expired')

           # ✅ CORRECT - Function returns None
           result = auth_manager.verify_token('expired')
           assert result is None
           ```

        5. **Test Structure Example**:
           ```python
           import pytest
           from unittest.mock import Mock, patch, MagicMock

           # Import module under test
           from backend.auth import AuthManager

           @pytest.mark.unit
           class TestAuthManager:
               '''Unit tests for AuthManager class'''

               @patch('backend.auth.jwt.decode')
               def test_verify_token_valid_jwt(self, mock_jwt_decode):
                   '''Verify that valid JWT token is decoded correctly'''
                   # Arrange
                   mock_jwt_decode.return_value = {
                       'sub': 'user123',
                       'email': 'test@example.com'
                   }

                   # Mock Supabase response (CRITICAL!)
                   mock_supabase = Mock()
                   mock_response = Mock()
                   mock_response.data = [{
                       'id': 'user123',
                       'username': 'testuser',
                       'role': 'admin',
                       'team_id': None,
                       'display_name': 'Test User'
                   }]
                   mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

                   auth_manager = AuthManager(supabase_client=mock_supabase)

                   # Act
                   user_data = auth_manager.verify_token('valid_token')

                   # Assert
                   assert user_data['username'] == 'testuser'
                   assert user_data['role'] == 'admin'
                   mock_jwt_decode.assert_called_once()
           ```

        6. **Important Notes**:
           - DO NOT mock the function being tested (only its dependencies)
           - Use fixtures for repeated setup (database connections, clients)
           - Group related tests in classes
           - Test isolation - each test should be independent
           - ALWAYS mock Supabase with proper .data attribute

        Write the complete test file and save it using write_file tool.
        Use the path: backend/tests/unit/test_<module_name>.py

        After writing the file, output a summary:
        - File path
        - Number of tests generated
        - Functions covered
        - Mocking strategy used
        """,
        expected_output="Complete pytest test file saved to disk",
        agent=forge,
        context=[architect_task],  # Receives test scenarios from Architect
    )

    # Task 4: Flash executes tests and measures coverage
    flash_task = Task(
        description=f"""
        Execute the generated unit tests and measure coverage improvement.

        Context: Forge has generated a new test file. Your job is to:
        1. Run the tests
        2. Measure coverage for the target module
        3. Report improvement

        Steps:

        1. **Identify Test File**: Find the test file Forge created
           - Look in backend/tests/unit/
           - File name from Forge's output

        2. **Run Tests with Coverage**:
           ```bash
           cd backend && pytest <test_file> \\
               --cov={module_path} \\
               --cov-report=term \\
               -v
           ```

        3. **Parse Results**:
           - Test count (passed/failed/skipped)
           - Coverage percentage (before vs after)
           - Execution time

        4. **Generate Report**:
           ```markdown
           ⚡ Flash: Unit Test Execution Report

           📊 Test Results:
             Total:    15
             ✅ Passed: 15
             ❌ Failed: 0
             ⏭️  Skipped: 0
             📈 Pass Rate: 100%

           📈 Coverage Analysis:
             Module: {module_path}

             Before:  19.8% (37/187 statements)
             After:   45.0% (84/187 statements)

             ✅ Improvement: +25.2% (+47 statements)

             Remaining Gaps: 103 statements (55%)

           ⏱️  Duration: 0.8s

           💡 Recommendations:
             - Coverage increased significantly!
             - Still need 35% more to reach {coverage_target}% target
             - Focus next on: verify_service_account_token(), require_role()
           ```

        5. **Identify Remaining Gaps**:
           - Which functions still have low coverage?
           - Which test scenarios might be missing?
           - Recommend next functions to target

        Run the tests now and provide a comprehensive report.
        """,
        expected_output="Test execution report with coverage improvement analysis",
        agent=flash,
        context=[forge_task],  # Knows which test file was created
    )

    # Create crew
    crew = Crew(
        agents=[inspector, architect, forge, flash],
        tasks=[inspector_task, architect_task, forge_task, flash_task],
        process=Process.sequential,
        verbose=CrewConfig.VERBOSE,
    )

    return crew


def main():
    """Main entry point for unit test generation workflow"""

    if len(sys.argv) < 2:
        print("Usage: python unit_test_workflow.py <module_path> [--coverage-target 80]")
        print()
        print("Examples:")
        print("  python unit_test_workflow.py backend/auth.py")
        print("  python unit_test_workflow.py backend/dao/enhanced_data_access_fixed.py --coverage-target 85")
        sys.exit(1)

    module_path = sys.argv[1]
    coverage_target = 80

    # Parse optional arguments
    if "--coverage-target" in sys.argv:
        idx = sys.argv.index("--coverage-target")
        if idx + 1 < len(sys.argv):
            coverage_target = int(sys.argv[idx + 1])

    # Verify module exists
    full_path = project_root / module_path
    if not full_path.exists():
        print(f"❌ Error: Module not found: {module_path}")
        sys.exit(1)

    print("=" * 80)
    print("🤖 Phase 3: Unit Test Generation Workflow")
    print("=" * 80)
    print(f"Module: {module_path}")
    print(f"Coverage Target: {coverage_target}%")
    print(f"Verbose: {CrewConfig.VERBOSE}")
    print("=" * 80)
    print()

    # Create and run crew
    crew = create_unit_test_crew(module_path, coverage_target)

    print("🚀 Starting CrewAI workflow...")
    print("   Inspector → Architect → Forge → Flash")
    print()

    result = crew.kickoff()

    print()
    print("=" * 80)
    print("✅ Workflow Complete!")
    print("=" * 80)
    print(result)


if __name__ == "__main__":
    main()

"""
🎯 Architect - Test Scenario Designer

Tagline: "Breaking things before users do"

Role: Comprehensive test scenario designer

Responsibilities:
- Design test scenarios covering all paths
- Generate happy path tests
- Generate error/validation tests
- Think of edge cases and boundary conditions
- Security test scenarios (injection, unauthorized access)
- Performance test scenarios (pagination, large payloads)
"""

from crewai import Agent

from crew_testing.config import CrewConfig
from crew_testing.tools import ReadOpenAPISpecTool


def create_architect_agent() -> Agent:
    """
    Create the Architect agent for test scenario design

    Uses GPT-4o for complex reasoning about test scenarios

    Returns:
        Configured CrewAI Agent
    """
    # Get LLM for this agent from config
    llm = CrewConfig.get_llm_for_agent("architect")

    # Initialize tools - Phase 2 only needs OpenAPI spec
    tools = [
        ReadOpenAPISpecTool(),
        # DetectGapsTool() removed - Phase 1 tool not needed for Phase 2 workflow
    ]

    # Create agent
    agent = Agent(
        role="Test Scenario Designer",
        goal=(
            "Design comprehensive test scenarios that cover all paths, edge cases, "
            "and potential failure modes for API endpoints. Think like an attacker "
            "and a user who makes mistakes."
        ),
        backstory=(
            "You are an expert test architect with 15 years of experience in breaking "
            "production systems. You've seen every type of bug: from simple validation "
            "errors to complex race conditions and security vulnerabilities. "
            "\n\n"
            "Your superpower is thinking of edge cases that developers miss. You design "
            "tests that catch bugs BEFORE they reach production. You understand that "
            "good tests don't just verify the happy path - they explore boundaries, "
            "test error handling, and probe for security issues."
            "\n\n"
            "For every endpoint, you design:"
            "\n"
            "1. **Happy Path Tests**: Valid data, expected behavior"
            "\n"
            "2. **Error Tests**: Missing fields, invalid types, constraint violations"
            "\n"
            "3. **Edge Cases**: Boundary values, empty strings, null values, special characters"
            "\n"
            "4. **Security Tests**: SQL injection, XSS, unauthorized access, CSRF"
            "\n"
            "5. **Performance Tests**: Large payloads, pagination limits, concurrent requests"
            "\n\n"
            "You think in terms of 'what could possibly go wrong?' and design tests to prove it."
        ),
        verbose=CrewConfig.VERBOSE,
        llm=llm,
        tools=tools,
        max_iter=15,  # Allow more iterations for complex reasoning
        allow_delegation=False,
    )

    return agent


def get_architect_task_description() -> str:
    """
    Get the task description for the Architect agent

    Returns:
        Task description string
    """
    return """
Analyze the {endpoint} endpoint and design comprehensive test scenarios.

Your task:
1. Read the OpenAPI spec for {endpoint}
2. Understand the endpoint's purpose, parameters, and expected behavior
3. Design test scenarios covering:
   - Happy path (valid requests)
   - Error cases (missing/invalid data)
   - Edge cases (boundaries, empty values)
   - Security concerns (injection, auth)
   - Performance (large data, pagination)

Output a detailed test plan in JSON format:
{{
    "endpoint": "{endpoint}",
    "method": "POST|GET|PUT|DELETE",
    "authentication_required": true|false,
    "scenarios": [
        {{
            "name": "test_create_match_success",
            "category": "happy_path",
            "description": "Valid match creation with existing teams",
            "method": "POST",
            "expected_status": 201,
            "requires_auth": true,
            "test_data_requirements": ["home_team_id", "away_team_id", "match_date", "season_id"],
            "assertions": ["response has id", "response has created_at", "teams are different"]
        }},
        {{
            "name": "test_create_match_missing_home_team",
            "category": "error",
            "description": "Missing required field returns 400",
            "method": "POST",
            "expected_status": 400,
            "requires_auth": true,
            "test_data_requirements": ["away_team_id", "match_date"],
            "assertions": ["error message mentions home_team_id"]
        }},
        {{
            "name": "test_create_match_same_teams",
            "category": "edge_case",
            "description": "Same home and away team returns 400",
            "method": "POST",
            "expected_status": 400,
            "requires_auth": true,
            "test_data_requirements": ["same_team_for_both"],
            "assertions": ["error message about different teams"]
        }},
        {{
            "name": "test_create_match_unauthorized",
            "category": "security",
            "description": "Unauthenticated request returns 401",
            "method": "POST",
            "expected_status": 401,
            "requires_auth": false,
            "test_data_requirements": ["valid_match_data"],
            "assertions": ["error indicates authentication required"]
        }}
    ],
    "total_scenarios": 15,
    "coverage_estimate": "95%"
}}

Be thorough. Think of scenarios developers wouldn't consider.
"""


# Export for agent creation
__all__ = ["create_architect_agent", "get_architect_task_description"]

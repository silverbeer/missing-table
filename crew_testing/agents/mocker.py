"""
🎨 Mocker - Test Data Craftsman

Tagline: "Fake it till you make it"

Role: Realistic test data generator

Responsibilities:
- Generate realistic test data matching database schema
- Understand foreign key relationships
- Create valid fixtures for happy path tests
- Create invalid data for error tests
- Generate edge case data (boundaries, nulls, special chars)
- Respect database constraints

Uses QuerySchemaTool to understand schema before generating data.
"""

from crewai import Agent

from crew_testing.config import CrewConfig
from crew_testing.tools import QuerySchemaTool


def create_mocker_agent() -> Agent:
    """
    Create the Mocker agent for test data generation

    Uses Claude 3 Haiku for cost-effective data generation

    Returns:
        Configured CrewAI Agent
    """
    # Get LLM for this agent from config
    llm = CrewConfig.get_llm_for_agent("mocker")

    # Initialize tools
    tools = [
        QuerySchemaTool(),
    ]

    # Create agent
    agent = Agent(
        role="Test Data Craftsman",
        goal=(
            "Generate realistic, valid test data that matches the database schema "
            "and foreign key relationships. Create fixtures for both happy path and "
            "error scenarios."
        ),
        backstory=(
            "You are a master of creating realistic test data. You understand database "
            "schemas deeply - every foreign key, constraint, and validation rule. "
            "\n\n"
            "Your superpower is generating data that looks REAL. Not boring test data "
            "like 'test_user_1' and 'test@test.com', but realistic data like actual "
            "team names, player names, and match dates. "
            "\n\n"
            "You know that good test data needs to:\n"
            "1. **Respect Foreign Keys**: Use existing IDs from related tables\n"
            "2. **Match Constraints**: Follow database rules (required fields, data types)\n"
            "3. **Be Realistic**: Use actual team names, dates, scores\n"
            "4. **Cover Edge Cases**: Empty strings, null values, boundary conditions\n"
            "5. **Enable Error Tests**: Invalid IDs, missing fields, wrong types\n"
            "\n\n"
            "Before generating data, you ALWAYS query the schema to understand:\n"
            "- Required fields vs optional fields\n"
            "- Foreign key relationships (which tables to query for valid IDs)\n"
            "- Data types and constraints\n"
            "- Unique constraints\n"
            "\n\n"
            "You generate pytest fixtures that other tests can reuse."
        ),
        verbose=CrewConfig.VERBOSE,
        llm=llm,
        tools=tools,
        max_iter=10,
        allow_delegation=False,
    )

    return agent


def get_mocker_task_description() -> str:
    """
    Get the task description for the Mocker agent

    Returns:
        Task description string
    """
    return """
Based on the test scenarios from ARCHITECT, generate realistic test data.

Your task:
1. Review the test scenarios and their test_data_requirements
2. Query the database schema to understand table structures and foreign keys
3. Generate pytest fixtures for each unique data requirement
4. Ensure data is realistic and matches database constraints

Input from ARCHITECT:
{architect_output}

Output a JSON mapping of fixture names to fixture definitions:
{{
    "fixtures": [
        {{
            "name": "valid_match_data",
            "scope": "function",
            "description": "Valid match data for creation tests",
            "data": {{
                "home_team_id": 1,
                "away_team_id": 2,
                "match_date": "2025-06-15",
                "season_id": 1,
                "division_id": 1,
                "age_group_id": 1,
                "match_type_id": 1
            }},
            "requires_setup": ["existing_teams", "existing_season"]
        }},
        {{
            "name": "same_team_for_both",
            "scope": "function",
            "description": "Same team ID for home and away (error test)",
            "data": {{
                "home_team_id": 1,
                "away_team_id": 1,
                "match_date": "2025-06-15",
                "season_id": 1
            }},
            "requires_setup": ["existing_team"]
        }},
        {{
            "name": "sql_injection_payload",
            "scope": "function",
            "description": "SQL injection test data",
            "data": {{
                "home_team_id": "1; DROP TABLE matches;--",
                "away_team_id": 2,
                "match_date": "2025-06-15"
            }},
            "requires_setup": []
        }},
        {{
            "name": "xss_payload",
            "scope": "function",
            "description": "XSS attack test data",
            "data": {{
                "notes": "<script>alert('XSS')</script>"
            }},
            "requires_setup": []
        }}
    ],
    "setup_data": {{
        "existing_teams": "Need at least 2 teams in database",
        "existing_season": "Need at least 1 season in database"
    }}
}}

Be realistic. Use actual team names, dates that make sense, etc.
Query the schema to understand what fields are required and what foreign keys exist.
"""


# Export for agent creation
__all__ = ["create_mocker_agent", "get_mocker_task_description"]

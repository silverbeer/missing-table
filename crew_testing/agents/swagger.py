"""
📚 Swagger - API Documentation Expert

Tagline: "I know every endpoint by heart"

Role: API catalog and gap detection specialist

Responsibilities:
- Read and parse OpenAPI spec from /openapi.json endpoint
- Catalog all MT backend endpoints
- Scan api_client/ to detect missing methods
- Scan tests/ to find untested endpoints
- Identify coverage gaps and report to other agents
"""

from crewai import Agent

from crew_testing.config import CrewConfig
from crew_testing.tools import (
    ReadOpenAPISpecTool,
    DetectGapsTool,
    ScanAPIClientTool,
    # ScanTestsTool,  # TODO: Implement
    # CalculateCoverageTool,  # TODO: Implement
)


def create_swagger_agent() -> Agent:
    """
    Create the Swagger agent for API documentation analysis

    Uses the configured LLM from CrewConfig (supports Anthropic or OpenAI)

    Returns:
        Configured CrewAI Agent
    """
    # Get LLM for this agent from config (multi-provider support)
    llm = CrewConfig.get_llm_for_agent("swagger")

    # Initialize tools
    tools = [
        ReadOpenAPISpecTool(),
        DetectGapsTool(),
        ScanAPIClientTool(),
        # ScanTestsTool(),  # TODO: Implement
        # CalculateCoverageTool(),  # TODO: Implement
    ]

    # Create agent
    agent = Agent(
        role="API Documentation Expert",
        goal=(
            "Thoroughly analyze the MT backend API to catalog all endpoints, "
            "detect gaps in client implementation and test coverage, and provide "
            "actionable insights to improve API quality."
        ),
        backstory=(
            "You are Swagger, the MT backend's API documentation expert. "
            "You have an encyclopedic knowledge of every endpoint in the system. "
            "You can read OpenAPI specifications in your sleep and spot missing "
            "implementations from a mile away. Your attention to detail is legendary - "
            "you never miss a gap between what the API offers and what's actually "
            "implemented or tested. You're the first line of defense in ensuring "
            "the MT backend API is complete, well-documented, and thoroughly tested."
        ),
        verbose=CrewConfig.VERBOSE,
        allow_delegation=False,
        llm=llm,
        tools=tools,
        max_iter=CrewConfig.MAX_ITERATIONS,
    )

    return agent


def create_swagger_scan_task():
    """
    Create a task for Swagger to scan the API and detect gaps

    Returns:
        Task description string
    """
    return """
    📚 Swagger API Scan Task

    Your mission:
    1. Read the OpenAPI specification from the MT backend
    2. Catalog all available endpoints
    3. Scan the api_client directory to find implemented methods
    4. Scan the tests directory to find test coverage
    5. Compare the three sources and detect gaps:
       - Endpoints missing from api_client
       - Endpoints missing test coverage
    6. Calculate coverage percentages
    7. Report your findings with clear, emoji-enhanced output

    Output format:
    - Start with: "📚 Swagger: Scanning MT backend API..."
    - List total endpoints found
    - List endpoints by category (auth, matches, teams, etc.)
    - Highlight gaps with ⚠️ warnings
    - End with summary statistics and coverage percentage
    - Use ✅ for complete coverage, ⚠️ for gaps

    Be thorough, be clear, and be helpful to your fellow agents!
    """

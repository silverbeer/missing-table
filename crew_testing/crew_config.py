"""
CrewAI Crew Configuration

Defines the MT Testing Crew with agents and their tasks
"""

from crewai import Crew, Task, Process

from crew_testing.agents import create_swagger_agent, create_swagger_scan_task
from crew_testing.config import CrewConfig


def create_mt_testing_crew(endpoint: str = None) -> Crew:
    """
    Create the MT Testing Crew

    Args:
        endpoint: Optional specific endpoint to test (e.g., "/api/matches")
                 If None, scans all endpoints

    Returns:
        Configured Crew ready to execute
    """
    # Create agents
    swagger_agent = create_swagger_agent()

    # Create tasks
    swagger_task = Task(
        description=create_swagger_scan_task(),
        agent=swagger_agent,
        expected_output=(
            "A comprehensive report including:\n"
            "1. Total number of endpoints found\n"
            "2. Endpoints grouped by category/tag\n"
            "3. List of endpoints missing from api_client\n"
            "4. List of endpoints missing test coverage\n"
            "5. Coverage percentage statistics\n"
            "6. Clear recommendations for next steps"
        ),
    )

    # Create crew with sequential process
    crew = Crew(
        agents=[swagger_agent],
        tasks=[swagger_task],
        process=Process.sequential,
        verbose=CrewConfig.VERBOSE,
    )

    return crew


def run_swagger_scan(backend_url: str = "http://localhost:8000") -> str:
    """
    Run a Swagger API scan

    Args:
        backend_url: URL of the MT backend

    Returns:
        Scan results as formatted string
    """
    # Update config with backend URL
    CrewConfig.BACKEND_URL = backend_url

    # Create and run crew
    crew = create_mt_testing_crew()
    result = crew.kickoff()

    return str(result)

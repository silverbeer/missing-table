#!/usr/bin/env python3
"""
MT Testing Crew - CLI Entry Point

Usage:
    python crew_testing/main.py --scan
    python crew_testing/main.py --endpoint /api/matches
    python crew_testing/main.py --verbose
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from crew_testing.config import CrewConfig
from crew_testing.crew_config import run_swagger_scan

app = typer.Typer(
    help="🤖 MT Testing Crew - Autonomous API Testing with CrewAI",
    add_completion=False,
)
console = Console()


@app.command()
def scan(
    backend_url: str = typer.Option(
        "http://localhost:8000",
        "--url",
        "-u",
        help="MT backend URL",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed agent conversations",
    ),
):
    """
    📚 Scan the MT backend API and detect gaps

    This command runs the Swagger agent to:
    - Read the OpenAPI specification
    - Catalog all endpoints
    - Detect missing api_client methods
    - Identify untested endpoints
    - Calculate coverage statistics
    """
    # Update configuration
    CrewConfig.VERBOSE = verbose

    # Display banner
    banner = Text()
    banner.append("🤖 MT Testing Crew\n", style="bold blue")
    banner.append("📚 Swagger - API Documentation Expert\n", style="bold green")
    banner.append(f"\nScanning: {backend_url}", style="cyan")

    console.print(Panel(banner, title="CrewAI Testing System", border_style="blue"))
    console.print()

    try:
        # Validate configuration
        CrewConfig.validate()

        # Run scan
        with console.status("[bold green]Scanning API..."):
            result = run_swagger_scan(backend_url)

        # Display results
        console.print(Panel(result, title="Scan Results", border_style="green"))

    except ValueError as e:
        console.print(f"[bold red]❌ Configuration Error:[/bold red] {e}")
        console.print("\n[yellow]💡 Tip:[/yellow] Set ANTHROPIC_API_KEY in your .env file")
        raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(code=1)


@app.command()
def endpoint(
    path: str = typer.Argument(..., help="Endpoint path (e.g., /api/matches)"),
    backend_url: str = typer.Option(
        "http://localhost:8000",
        "--url",
        "-u",
        help="MT backend URL",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed agent conversations",
    ),
):
    """
    🎯 Test a specific endpoint (Phase 2 feature)

    This will eventually:
    - Generate test scenarios (Architect)
    - Create test data (Mocker)
    - Generate client methods (Forge)
    - Execute tests (Flash)
    - Debug failures (Sherlock)
    - Generate report (Herald)
    """
    console.print(
        Panel(
            f"[yellow]⚠️  Endpoint testing is a Phase 2 feature[/yellow]\n\n"
            f"For now, use: [cyan]python crew_testing/main.py scan[/cyan]\n\n"
            f"Coming soon: Full test generation for {path}",
            title="Under Development",
            border_style="yellow",
        )
    )


@app.command()
def version():
    """Show version information"""
    console.print(
        Panel(
            "[bold blue]MT Testing Crew[/bold blue]\n"
            "Version: 0.1.0 (Phase 1)\n"
            "Agents: 1/8 (Swagger only)\n"
            "Status: Development\n\n"
            "Using:\n"
            f"  • CrewAI\n"
            f"  • Claude 3 Haiku\n"
            f"  • Cost: ~$0.05 per scan",
            title="Version Info",
            border_style="blue",
        )
    )


@app.command()
def llm_config():
    """Show LLM configuration for all agents"""
    try:
        # Use the built-in config printer
        CrewConfig.print_llm_config()

    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def agents():
    """List all agents in the crew"""
    agents_text = """
📚 Swagger - API Documentation Expert
   Status: ✅ Implemented (Phase 1)
   LLM: OpenAI GPT-4o-mini ($0.03/run)
   Role: Scans API, detects gaps, catalogs endpoints

🎯 Architect - Test Scenario Designer
   Status: ✅ Implemented (Phase 2)
   LLM: OpenAI GPT-4o ($0.20/run)
   Role: Designs comprehensive test scenarios

🎨 Mocker - Test Data Craftsman
   Status: ⏳ Coming in Phase 2
   LLM: Anthropic Claude 3 Haiku ($0.05/run)
   Role: Generates realistic test data

⚡ Flash - Test Executor
   Status: ⏳ Coming in Phase 2
   LLM: Anthropic Claude 3 Haiku ($0.05/run)
   Role: Executes tests with coverage

🔬 Inspector - Quality Analyst
   Status: ⏳ Coming in Phase 3
   LLM: Anthropic Claude 3 Haiku ($0.05/run)
   Role: Analyzes patterns and metrics

📊 Herald - Test Reporter
   Status: ⏳ Coming in Phase 3
   LLM: Anthropic Claude 3 Haiku ($0.05/run)
   Role: Generates beautiful reports

🔧 Forge - Test Infrastructure Engineer
   Status: ⏳ Coming in Phase 2
   LLM: OpenAI GPT-4o ($0.20/run)
   Role: Maintains test framework and api_client

🐛 Sherlock - Test Debugger
   Status: ⏳ Coming in Phase 3
   LLM: OpenAI GPT-4o ($0.20/run)
   Role: Investigates failures and proposes fixes
"""
    console.print(Panel(agents_text.strip(), title="MT Testing Crew Roster", border_style="blue"))


@app.command()
def generate(
    endpoint: str = typer.Argument(..., help="Endpoint to generate tests for (e.g., /api/matches)"),
    backend_url: str = typer.Option("http://localhost:8000", "--url", "-u", help="MT backend URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed agent conversations"),
):
    """
    🎯 Generate test scenarios for an endpoint (Phase 2 - Architect only)

    This command runs the ARCHITECT agent to design comprehensive test scenarios.
    Full test generation (Mocker, Forge, Flash) coming soon!
    """
    # Update configuration
    CrewConfig.VERBOSE = verbose

    # Display banner
    banner = Text()
    banner.append("🤖 MT Testing Crew - Phase 2\n", style="bold blue")
    banner.append("🎯 Architect - Test Scenario Designer\n", style="bold green")
    banner.append(f"\nEndpoint: {endpoint}\n", style="cyan")
    banner.append("Status: Designing test scenarios...", style="yellow")

    console.print(Panel(banner, title="Test Generation", border_style="blue"))
    console.print()

    try:
        # Validate configuration
        CrewConfig.validate()

        # Import architect agent
        from crew_testing.agents.architect import create_architect_agent, get_architect_task_description
        from crewai import Task, Crew, Process

        # Create architect agent
        architect = create_architect_agent()

        # Create task
        task_description = get_architect_task_description()
        task = Task(
            description=task_description,
            expected_output="Detailed JSON test plan with comprehensive scenarios",
            agent=architect,
        )

        # Create crew with just architect
        crew = Crew(
            agents=[architect],
            tasks=[task],
            process=Process.sequential,
            verbose=verbose
        )

        # Run with endpoint input
        with console.status("[bold green]Architect designing test scenarios..."):
            result = crew.kickoff(inputs={"endpoint": endpoint})

        # Display results
        console.print(Panel(str(result), title="Test Scenarios Designed", border_style="green"))

        console.print("\n[yellow]ℹ️  Note: Full test generation (Mocker, Forge, Flash) coming in Phase 2 completion[/yellow]")

    except ValueError as e:
        console.print(f"[bold red]❌ Configuration Error:[/bold red] {e}")
        console.print("\n[yellow]💡 Tip:[/yellow] Set OPENAI_API_KEY in your .env.local file")
        raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(code=1)


@app.command()
def test(
    endpoint: str = typer.Argument(..., help="Endpoint to test (e.g., /api/matches)"),
    backend_url: str = typer.Option("http://localhost:8000", "--url", "-u", help="MT backend URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed agent conversations"),
):
    """
    🚀 Full end-to-end test generation and execution (Phase 2 Complete)

    This command runs ALL Phase 2 agents in sequence:
    1. 📚 ARCHITECT - Design comprehensive test scenarios
    2. 🎨 MOCKER - Generate realistic test data
    3. 🔧 FORGE - Generate pytest test files
    4. ⚡ FLASH - Execute tests and report results

    Example:
        python crew_testing/main.py test /api/matches --verbose
    """
    # Update configuration
    CrewConfig.VERBOSE = verbose

    # Display banner
    banner = Text()
    banner.append("🤖 MT Testing Crew - Phase 2 COMPLETE\n", style="bold blue")
    banner.append("🚀 Full Test Generation Pipeline\n", style="bold green")
    banner.append(f"\nEndpoint: {endpoint}\n", style="cyan")
    banner.append("Workflow: 📚 ARCHITECT → 🎨 MOCKER → 🔧 FORGE → ⚡ FLASH", style="yellow")

    console.print(Panel(banner, title="Phase 2 Workflow", border_style="blue"))
    console.print()

    try:
        # Validate configuration
        CrewConfig.validate()

        # Import workflow
        from crew_testing.workflows import run_phase2_workflow

        # Run Phase 2 workflow
        result = run_phase2_workflow(
            endpoint=endpoint,
            backend_url=backend_url,
            verbose=verbose
        )

        # Display final results
        console.print(Panel(result, title="🎉 Test Generation Complete", border_style="green"))

    except ValueError as e:
        console.print(f"[bold red]❌ Configuration Error:[/bold red] {e}")
        console.print("\n[yellow]💡 Tip:[/yellow] Set OPENAI_API_KEY in your .env.local file")
        raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

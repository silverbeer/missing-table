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
    regenerate: bool = typer.Option(False, "--regenerate", "-r", help="Force regenerate tests even if they exist"),
):
    """
    🚀 Full end-to-end test generation and execution (Phase 2 Complete)

    Smart Test Management:
    - If tests exist and spec unchanged → Run existing tests (1-2s, $0)
    - If tests exist and spec changed → Regenerate tests (90s, $0.50)
    - If tests don't exist → Generate tests (first time)
    - Use --regenerate to force regeneration

    This command runs ALL Phase 2 agents when needed:
    1. 📚 ARCHITECT - Design comprehensive test scenarios
    2. 🎨 MOCKER - Generate realistic test data
    3. 🔧 FORGE - Generate pytest test files
    4. ⚡ FLASH - Execute tests and report results

    Example:
        python crew_testing/main.py test /api/matches           # Smart detection
        python crew_testing/main.py test /api/matches -r        # Force regenerate
        python crew_testing/main.py test /api/matches --verbose # Show agent conversations
    """
    # Update configuration
    CrewConfig.VERBOSE = verbose

    try:
        # Validate configuration
        CrewConfig.validate()

        # Import state manager
        from crew_testing.lib import TestStateManager
        from pathlib import Path
        import subprocess
        import time
        import json

        state = TestStateManager()

        # Check if test exists
        if state.test_exists(endpoint):
            test_file = state.get_test_file(endpoint)

            # Display existing test info
            banner = Text()
            banner.append("🤖 MT Testing Crew - Smart Test Detection\n", style="bold blue")
            banner.append(f"📁 Found existing test: {test_file}\n", style="bold green")

            if not regenerate:
                # Check if spec changed
                change_report = state.check_spec_changes(endpoint)

                if not change_report.changed:
                    # Spec unchanged - just run existing tests
                    banner.append(f"\n✅ OpenAPI spec unchanged\n", style="green")
                    banner.append("⚡ Running existing tests (fast path)", style="yellow")

                    console.print(Panel(banner, title="Test Execution", border_style="green"))
                    console.print()

                    # Run pytest directly (find project root first)
                    current_dir = Path.cwd()
                    project_root = current_dir
                    while project_root != project_root.parent:
                        if (project_root / "crew_testing" / "main.py").exists():
                            break
                        project_root = project_root.parent

                    console.print(f"[cyan]Running: pytest {test_file} -v[/cyan]\n")

                    start_time = time.time()
                    result = subprocess.run(
                        ["pytest", test_file, "-v", "--tb=short"],
                        capture_output=True,
                        text=True,
                        cwd=project_root
                    )
                    duration = time.time() - start_time

                    # Display results
                    console.print(result.stdout)
                    if result.stderr:
                        console.print(f"[yellow]{result.stderr}[/yellow]")

                    # Parse results for cache update (pytest format: "6 passed, 2 failed")
                    import re
                    output = result.stdout

                    passed_match = re.search(r'(\d+)\s+passed', output)
                    failed_match = re.search(r'(\d+)\s+failed', output)

                    passed = int(passed_match.group(1)) if passed_match else 0
                    failed = int(failed_match.group(1)) if failed_match else 0
                    total = passed + failed

                    # Update cache
                    state.update_test_results(endpoint, {
                        "total": total,
                        "passed": passed,
                        "failed": failed,
                        "duration_ms": int(duration * 1000)
                    })

                    # Display summary
                    summary = Text()
                    summary.append(f"✅ Duration: {duration:.2f}s\n", style="green")
                    summary.append(f"📊 Tests: {total} total, {passed} passed, {failed} failed\n", style="cyan")
                    summary.append(f"💰 Cost: $0.00 (no AI generation needed)", style="green")

                    console.print(Panel(summary, title="Test Results", border_style="green"))
                    return

                else:
                    # Spec changed - need to regenerate
                    banner.append(f"\n⚠️  OpenAPI spec changed: {change_report.reason}\n", style="yellow")
                    banner.append("🔄 Regenerating tests...", style="yellow")
                    console.print(Panel(banner, title="Test Regeneration", border_style="yellow"))
                    console.print()

            else:
                # User forced regeneration
                banner.append(f"\n🔄 Force regeneration requested\n", style="yellow")
                banner.append("Workflow: 📚 ARCHITECT → 🎨 MOCKER → 🔧 FORGE → ⚡ FLASH", style="yellow")
                console.print(Panel(banner, title="Test Regeneration", border_style="yellow"))
                console.print()

        else:
            # No test exists - generate for first time
            banner = Text()
            banner.append("🤖 MT Testing Crew - Phase 2 COMPLETE\n", style="bold blue")
            banner.append("🚀 First-time Test Generation\n", style="bold green")
            banner.append(f"\nEndpoint: {endpoint}\n", style="cyan")
            banner.append("Workflow: 📚 ARCHITECT → 🎨 MOCKER → 🔧 FORGE → ⚡ FLASH", style="yellow")

            console.print(Panel(banner, title="Test Generation", border_style="blue"))
            console.print()

        # Run full workflow (for new tests, spec changes, or forced regeneration)
        from crew_testing.workflows import run_phase2_workflow

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


@app.command()
def logs(
    tail: bool = typer.Option(False, "--tail", "-f", help="Tail logs in real-time"),
    agent: str = typer.Option(None, "--agent", "-a", help="Show logs for specific agent (architect, mocker, forge, flash)"),
    workflow: str = typer.Option("workflow", "--workflow", "-w", help="Workflow type to view"),
):
    """
    📜 View CrewAI testing logs

    View or tail logs from workflow executions and individual agents.

    Examples:
        python crew_testing/main.py logs                    # View latest workflow log
        python crew_testing/main.py logs --tail             # Tail latest workflow log
        python crew_testing/main.py logs --agent architect  # View ARCHITECT agent log
        python crew_testing/main.py logs --agent forge -f   # Tail FORGE agent log
    """
    from pathlib import Path
    import subprocess

    logs_dir = Path("crew_testing/logs")
    latest_dir = logs_dir / "latest"

    if not latest_dir.exists():
        console.print("[yellow]⚠️  No logs found. Run a workflow first.[/yellow]")
        console.print("\n[cyan]Try: ./crew_testing/run.sh test /api/matches[/cyan]")
        return

    # Determine which log to view
    if agent:
        log_file = latest_dir / f"{agent}.log"
        log_name = f"{agent.upper()} Agent"
    else:
        # Find latest workflow log
        workflow_logs = list((logs_dir / "workflows").glob("*.log"))
        if not workflow_logs:
            console.print("[yellow]⚠️  No workflow logs found[/yellow]")
            return

        log_file = max(workflow_logs, key=lambda p: p.stat().st_mtime)
        log_name = "Workflow"

    if not log_file.exists():
        console.print(f"[red]❌ Log file not found: {log_file}[/red]")
        return

    # Display header
    console.print(Panel(
        f"[bold cyan]{log_name} Log[/bold cyan]\n"
        f"[dim]{log_file}[/dim]",
        border_style="blue"
    ))
    console.print()

    # View or tail the log
    try:
        if tail:
            console.print("[cyan]Tailing log (Ctrl+C to stop)...[/cyan]\n")
            # Use Python to tail and render Rich markup
            import time
            with open(log_file, "r") as f:
                # Go to end of file
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if line:
                        # Render line with Rich markup
                        console.print(line.rstrip())
                    else:
                        time.sleep(0.1)
        else:
            # Read and render log file with Rich markup
            with open(log_file, "r") as f:
                for line in f:
                    console.print(line.rstrip())

    except KeyboardInterrupt:
        console.print("\n[cyan]Stopped tailing log[/cyan]")
    except Exception as e:
        console.print(f"[red]❌ Error viewing log: {e}[/red]")


if __name__ == "__main__":
    app()

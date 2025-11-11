#!/usr/bin/env python3
"""
Test Inspector Tools in Isolation

Tests the three new tools for Phase 3:
- CodeAnalyzerTool
- CoverageAnalyzerTool
- GapReportTool

This validates the tools work before integrating into a Crew workflow.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from crew_testing.tools import (
    CodeAnalyzerTool,
    CoverageAnalyzerTool,
    GapReportTool,
)

console = Console()


def test_code_analyzer():
    """Test CodeAnalyzerTool on a real module"""
    console.print("\n[bold blue]Test 1: Code Analyzer Tool[/bold blue]\n")

    tool = CodeAnalyzerTool()

    # Test on a simple module - auth.py
    module_path = "backend/auth.py"

    console.print(f"Analyzing: {module_path}")

    with console.status("[bold green]Analyzing code..."):
        result = tool._run(module_path)

    # Display as markdown
    md = Markdown(result)
    console.print(Panel(md, title="Code Analysis", border_style="green"))

    return result


def test_coverage_analyzer():
    """Test CoverageAnalyzerTool"""
    console.print("\n[bold blue]Test 2: Coverage Analyzer Tool[/bold blue]\n")

    tool = CoverageAnalyzerTool()

    # Test on same module
    module_path = "backend/auth.py"

    console.print(f"Analyzing coverage for: {module_path}")

    with console.status("[bold green]Analyzing coverage..."):
        result = tool._run(module_path)

    # Display as markdown
    md = Markdown(result)
    console.print(Panel(md, title="Coverage Analysis", border_style="yellow"))

    return result


def test_gap_report():
    """Test GapReportTool"""
    console.print("\n[bold blue]Test 3: Gap Report Tool[/bold blue]\n")

    tool = GapReportTool()

    # Test on same module
    module_path = "backend/auth.py"

    console.print(f"Generating gap report for: {module_path}")

    with console.status("[bold green]Generating gap report..."):
        result = tool._run(module_path)

    # Display as markdown
    md = Markdown(result)
    console.print(Panel(md, title="Gap Report", border_style="red"))

    return result


def main():
    """Run all tool tests"""
    console.print(Panel(
        "[bold cyan]Inspector Tools Test Suite[/bold cyan]\n"
        "Testing Phase 3 tools in isolation",
        border_style="cyan"
    ))

    try:
        # Test 1: Code Analyzer
        code_result = test_code_analyzer()

        # Test 2: Coverage Analyzer
        coverage_result = test_coverage_analyzer()

        # Test 3: Gap Report
        gap_result = test_gap_report()

        # Summary
        console.print("\n[bold green]✅ All tool tests completed![/bold green]")
        console.print("\n[bold cyan]Summary:[/bold cyan]")
        console.print("1. ✅ Code Analyzer - Extracted functions/methods")
        console.print("2. ✅ Coverage Analyzer - Read coverage data")
        console.print("3. ✅ Gap Report - Generated prioritized gaps")

    except Exception as e:
        console.print(f"\n[bold red]❌ Error:[/bold red] {e}")
        console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()

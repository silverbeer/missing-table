#!/usr/bin/env python3
"""
Module Inspector CLI - Analyze Python modules for testing gaps

Usage:
    ./crew_testing/inspect.py backend/auth.py
    ./crew_testing/inspect.py backend/dao/enhanced_data_access_fixed.py --verbose
    ./crew_testing/inspect.py backend/services/invite_service.py --output report.md
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from typing import Optional

from crew_testing.tools import (
    CodeAnalyzerTool,
    CoverageAnalyzerTool,
    GapReportTool,
)

app = typer.Typer(
    help="🔬 Module Inspector - Analyze Python modules for testing gaps",
    add_completion=False,
)
console = Console()


@app.command()
def main(
    module_path: str = typer.Argument(
        ...,
        help="Path to Python module to inspect (e.g., backend/auth.py)"
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Save gap report to markdown file"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed code and coverage analysis"
    ),
    code_only: bool = typer.Option(
        False,
        "--code-only",
        help="Only run code analysis (skip coverage)"
    ),
    coverage_only: bool = typer.Option(
        False,
        "--coverage-only",
        help="Only run coverage analysis (skip code)"
    ),
):
    """
    Analyze a Python module to identify testing gaps and prioritize test generation.

    Examples:

        # Quick gap report
        ./crew_testing/inspect.py backend/auth.py

        # Detailed analysis
        ./crew_testing/inspect.py backend/dao/enhanced_data_access_fixed.py -v

        # Save report to file
        ./crew_testing/inspect.py backend/services/invite_service.py -o gap_report.md

        # Just code analysis
        ./crew_testing/inspect.py backend/auth.py --code-only
    """
    # Display banner
    banner = f"""🔬 Module Inspector

Analyzing: `{module_path}`
"""
    console.print(Panel(banner, border_style="cyan"))

    try:
        # Validate module exists
        if not Path(module_path).exists():
            console.print(f"[bold red]❌ Error:[/bold red] Module not found: {module_path}")
            raise typer.Exit(code=1)

        results = {}

        # Run code analysis
        if not coverage_only:
            console.print("\n[bold blue]Step 1: Code Analysis[/bold blue]")
            with console.status("[bold green]Analyzing code structure..."):
                code_tool = CodeAnalyzerTool()
                code_result = code_tool._run(module_path)
                results['code'] = code_result

            if verbose:
                md = Markdown(code_result)
                console.print(Panel(md, title="Code Analysis", border_style="green"))
            else:
                console.print("✅ Code analysis complete")

        # Run coverage analysis
        if not code_only:
            console.print("\n[bold blue]Step 2: Coverage Analysis[/bold blue]")
            with console.status("[bold green]Analyzing coverage data..."):
                coverage_tool = CoverageAnalyzerTool()
                coverage_result = coverage_tool._run(module_path)
                results['coverage'] = coverage_result

            if verbose:
                md = Markdown(coverage_result)
                console.print(Panel(md, title="Coverage Analysis", border_style="yellow"))
            else:
                console.print("✅ Coverage analysis complete")

        # Generate gap report (unless single-analysis mode)
        if not code_only and not coverage_only:
            console.print("\n[bold blue]Step 3: Gap Report Generation[/bold blue]")
            with console.status("[bold green]Generating prioritized gap report..."):
                gap_tool = GapReportTool()
                gap_result = gap_tool._run(module_path)
                results['gaps'] = gap_result

            # Display gap report
            md = Markdown(gap_result)
            console.print(Panel(md, title="Gap Report", border_style="red"))

            # Save to file if requested
            if output:
                output_path = Path(output)
                output_path.write_text(gap_result)
                console.print(f"\n✅ Gap report saved to: [cyan]{output}[/cyan]")

        # Summary
        console.print("\n[bold green]✅ Analysis complete![/bold green]")

        if not code_only and not coverage_only:
            console.print("\n[bold cyan]Next Steps:[/bold cyan]")
            console.print("1. Review the gap report above")
            console.print("2. Start with CRITICAL priority gaps")
            console.print("3. Use CrewAI to generate unit tests:")
            console.print(f"   [dim]# Coming soon: ./crew_testing/generate_tests.py {module_path}[/dim]")

    except Exception as e:
        console.print(f"\n[bold red]❌ Error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(code=1)


@app.command()
def batch(
    modules: list[str] = typer.Argument(
        ...,
        help="Space-separated list of modules to inspect"
    ),
    output_dir: str = typer.Option(
        "gap_reports",
        "--output-dir",
        "-d",
        help="Directory to save gap reports"
    ),
):
    """
    Analyze multiple modules and generate gap reports for each.

    Examples:

        # Analyze multiple modules
        ./crew_testing/inspect.py batch backend/auth.py backend/dao/*.py

        # Save to custom directory
        ./crew_testing/inspect.py batch backend/**/*.py -d reports/
    """
    console.print(Panel(
        f"🔬 Batch Module Inspector\n\nAnalyzing {len(modules)} modules...",
        border_style="cyan"
    ))

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results_summary = []

    for i, module_path in enumerate(modules, 1):
        console.print(f"\n[bold blue]Module {i}/{len(modules)}: {module_path}[/bold blue]")

        try:
            if not Path(module_path).exists():
                console.print(f"[yellow]⚠️  Skipping (not found): {module_path}[/yellow]")
                results_summary.append((module_path, "NOT_FOUND", None))
                continue

            # Generate gap report
            with console.status(f"[bold green]Analyzing {module_path}..."):
                gap_tool = GapReportTool()
                gap_result = gap_tool._run(module_path)

            # Save to file
            module_name = Path(module_path).stem
            output_file = output_path / f"{module_name}_gaps.md"
            output_file.write_text(gap_result)

            console.print(f"✅ Gap report saved: [cyan]{output_file}[/cyan]")
            results_summary.append((module_path, "SUCCESS", output_file))

        except Exception as e:
            console.print(f"[red]❌ Error analyzing {module_path}: {e}[/red]")
            results_summary.append((module_path, "ERROR", str(e)))

    # Display summary
    console.print("\n[bold green]✅ Batch analysis complete![/bold green]\n")
    console.print("[bold cyan]Summary:[/bold cyan]")

    success_count = sum(1 for _, status, _ in results_summary if status == "SUCCESS")
    console.print(f"  ✅ Successful: {success_count}/{len(modules)}")
    console.print(f"  📁 Reports saved to: [cyan]{output_path}[/cyan]")


if __name__ == "__main__":
    app()

#!/usr/bin/env python3
"""
Phase 3 Tool Testing Suite

Interactive testing tool for CodeAnalyzerTool, CoverageAnalyzerTool, and GapReportTool.

Usage:
    # Interactive mode
    PYTHONPATH=. backend/.venv/bin/python3 crew_testing/test_phase3_tools.py

    # Test specific tool
    PYTHONPATH=. backend/.venv/bin/python3 crew_testing/test_phase3_tools.py code backend/auth.py
    PYTHONPATH=. backend/.venv/bin/python3 crew_testing/test_phase3_tools.py coverage backend/auth.py
    PYTHONPATH=. backend/.venv/bin/python3 crew_testing/test_phase3_tools.py gap backend/auth.py

    # Test all tools
    PYTHONPATH=. backend/.venv/bin/python3 crew_testing/test_phase3_tools.py all backend/auth.py

    # Save results to file
    PYTHONPATH=. backend/.venv/bin/python3 crew_testing/test_phase3_tools.py all backend/auth.py --save
"""

import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.markdown import Markdown
    from rich.prompt import Prompt, Confirm
    from rich import box
except ImportError:
    print("❌ Error: typer and rich are required")
    print("Install with: uv add typer rich")
    sys.exit(1)

from crew_testing.tools import CodeAnalyzerTool, CoverageAnalyzerTool, GapReportTool

app = typer.Typer(help="Phase 3 Tool Testing Suite")
console = Console()


def show_banner():
    """Show application banner"""
    banner = """
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║          Phase 3 Tool Testing Suite                     ║
    ║                                                          ║
    ║          Test CrewAI Inspector Tools                    ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")


def test_code_analyzer(module_path: str, save: bool = False) -> str:
    """Test CodeAnalyzerTool on a module"""
    console.print("\n[bold cyan]🔬 Testing CodeAnalyzerTool[/bold cyan]")
    console.print(f"Module: [yellow]{module_path}[/yellow]\n")

    try:
        tool = CodeAnalyzerTool()
        result = tool._run(module_path)

        # Show result
        console.print(Panel(
            Markdown(result),
            title="CodeAnalyzerTool Result",
            border_style="cyan"
        ))

        if save:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"crew_testing/reports/code_analysis_{timestamp}.md")
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_text(result)
            console.print(f"\n✅ Saved to: [green]{output_path}[/green]")

        return result

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise


def test_coverage_analyzer(module_path: str, save: bool = False) -> str:
    """Test CoverageAnalyzerTool on a module"""
    console.print("\n[bold cyan]📊 Testing CoverageAnalyzerTool[/bold cyan]")
    console.print(f"Module: [yellow]{module_path}[/yellow]\n")

    try:
        tool = CoverageAnalyzerTool()
        result = tool._run(module_path)

        # Show result
        console.print(Panel(
            Markdown(result),
            title="CoverageAnalyzerTool Result",
            border_style="cyan"
        ))

        if save:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"crew_testing/reports/coverage_analysis_{timestamp}.md")
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_text(result)
            console.print(f"\n✅ Saved to: [green]{output_path}[/green]")

        return result

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise


def test_gap_report(module_path: str, save: bool = False) -> str:
    """Test GapReportTool on a module"""
    console.print("\n[bold cyan]🎯 Testing GapReportTool[/bold cyan]")
    console.print(f"Module: [yellow]{module_path}[/yellow]\n")

    try:
        tool = GapReportTool()
        result = tool._run(module_path)

        # Show result
        console.print(Panel(
            Markdown(result),
            title="GapReportTool Result",
            border_style="cyan"
        ))

        if save:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"crew_testing/reports/gap_report_{timestamp}.md")
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_text(result)
            console.print(f"\n✅ Saved to: [green]{output_path}[/green]")

        return result

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise


def test_all_tools(module_path: str, save: bool = False):
    """Test all Phase 3 tools in sequence"""
    console.print("\n[bold cyan]🔄 Testing All Phase 3 Tools[/bold cyan]")
    console.print(f"Module: [yellow]{module_path}[/yellow]\n")

    results = {}

    # Test 1: Code Analyzer
    try:
        console.rule("[cyan]1. Code Analysis[/cyan]")
        results['code_analysis'] = test_code_analyzer(module_path, save=False)
        console.print("✅ CodeAnalyzerTool: [green]PASSED[/green]\n")
    except Exception as e:
        console.print(f"❌ CodeAnalyzerTool: [red]FAILED[/red] - {e}\n")
        results['code_analysis'] = None

    # Test 2: Coverage Analyzer
    try:
        console.rule("[cyan]2. Coverage Analysis[/cyan]")
        results['coverage_analysis'] = test_coverage_analyzer(module_path, save=False)
        console.print("✅ CoverageAnalyzerTool: [green]PASSED[/green]\n")
    except Exception as e:
        console.print(f"❌ CoverageAnalyzerTool: [red]FAILED[/red] - {e}\n")
        results['coverage_analysis'] = None

    # Test 3: Gap Report
    try:
        console.rule("[cyan]3. Gap Report[/cyan]")
        results['gap_report'] = test_gap_report(module_path, save=False)
        console.print("✅ GapReportTool: [green]PASSED[/green]\n")
    except Exception as e:
        console.print(f"❌ GapReportTool: [red]FAILED[/red] - {e}\n")
        results['gap_report'] = None

    # Summary
    console.rule("[cyan]Summary[/cyan]")
    passed = sum(1 for v in results.values() if v is not None)
    total = len(results)

    table = Table(title="Test Results", box=box.ROUNDED)
    table.add_column("Tool", style="cyan")
    table.add_column("Status", style="bold")

    table.add_row(
        "CodeAnalyzerTool",
        "[green]✅ PASSED[/green]" if results['code_analysis'] else "[red]❌ FAILED[/red]"
    )
    table.add_row(
        "CoverageAnalyzerTool",
        "[green]✅ PASSED[/green]" if results['coverage_analysis'] else "[red]❌ FAILED[/red]"
    )
    table.add_row(
        "GapReportTool",
        "[green]✅ PASSED[/green]" if results['gap_report'] else "[red]❌ FAILED[/red]"
    )

    console.print(table)
    console.print(f"\nResult: [cyan]{passed}/{total}[/cyan] tools passed\n")

    # Save combined report if requested
    if save:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"crew_testing/reports/full_analysis_{timestamp}.md")
        output_path.parent.mkdir(exist_ok=True)

        combined_report = f"""# Phase 3 Tool Testing Report

**Module:** `{module_path}`
**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Tests Passed:** {passed}/{total}

---

## 1. Code Analysis

{results['code_analysis'] or '❌ Test failed'}

---

## 2. Coverage Analysis

{results['coverage_analysis'] or '❌ Test failed'}

---

## 3. Gap Report

{results['gap_report'] or '❌ Test failed'}

---

## Summary

- CodeAnalyzerTool: {'✅ PASSED' if results['code_analysis'] else '❌ FAILED'}
- CoverageAnalyzerTool: {'✅ PASSED' if results['coverage_analysis'] else '❌ FAILED'}
- GapReportTool: {'✅ PASSED' if results['gap_report'] else '❌ FAILED'}
"""
        output_path.write_text(combined_report)
        console.print(f"✅ Full report saved to: [green]{output_path}[/green]\n")

    return results


@app.command()
def code(
    module_path: str = typer.Argument(..., help="Path to Python module to analyze"),
    save: bool = typer.Option(False, "--save", "-s", help="Save result to file")
):
    """Test CodeAnalyzerTool only"""
    show_banner()
    test_code_analyzer(module_path, save)


@app.command()
def coverage(
    module_path: str = typer.Argument(..., help="Path to Python module to analyze"),
    save: bool = typer.Option(False, "--save", "-s", help="Save result to file")
):
    """Test CoverageAnalyzerTool only"""
    show_banner()
    test_coverage_analyzer(module_path, save)


@app.command()
def gap(
    module_path: str = typer.Argument(..., help="Path to Python module to analyze"),
    save: bool = typer.Option(False, "--save", "-s", help="Save result to file")
):
    """Test GapReportTool only"""
    show_banner()
    test_gap_report(module_path, save)


@app.command()
def all(
    module_path: str = typer.Argument(..., help="Path to Python module to analyze"),
    save: bool = typer.Option(False, "--save", "-s", help="Save results to file")
):
    """Test all Phase 3 tools in sequence"""
    show_banner()
    test_all_tools(module_path, save)


@app.command()
def interactive():
    """Interactive mode with menu"""
    show_banner()

    # Default modules
    modules = [
        "backend/auth.py",
        "backend/app.py",
        "backend/dao/supabase_data_access.py",
    ]

    while True:
        console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
        console.print("[bold]Available Commands:[/bold]\n")

        table = Table(box=box.SIMPLE)
        table.add_column("Command", style="cyan", width=15)
        table.add_column("Description")

        table.add_row("1", "Test CodeAnalyzerTool")
        table.add_row("2", "Test CoverageAnalyzerTool")
        table.add_row("3", "Test GapReportTool")
        table.add_row("4", "Test All Tools")
        table.add_row("5", "Change module")
        table.add_row("6", "List available modules")
        table.add_row("q", "Quit")

        console.print(table)
        console.print()

        # Show current module
        current_module = modules[0]
        console.print(f"Current module: [yellow]{current_module}[/yellow]\n")

        choice = Prompt.ask(
            "[bold cyan]What would you like to do?[/bold cyan]",
            choices=["1", "2", "3", "4", "5", "6", "q"],
            default="4"
        )

        if choice == "q":
            console.print("\n[cyan]👋 Goodbye![/cyan]\n")
            break

        elif choice == "1":
            save = Confirm.ask("Save result to file?", default=False)
            test_code_analyzer(current_module, save)

        elif choice == "2":
            save = Confirm.ask("Save result to file?", default=False)
            test_coverage_analyzer(current_module, save)

        elif choice == "3":
            save = Confirm.ask("Save result to file?", default=False)
            test_gap_report(current_module, save)

        elif choice == "4":
            save = Confirm.ask("Save results to file?", default=False)
            test_all_tools(current_module, save)

        elif choice == "5":
            console.print("\n[bold]Available modules:[/bold]")
            for i, mod in enumerate(modules, 1):
                console.print(f"  {i}. {mod}")
            console.print("  +. Enter custom path")

            module_choice = Prompt.ask("\nSelect module", default="1")
            if module_choice == "+":
                custom_path = Prompt.ask("Enter module path")
                modules.insert(0, custom_path)
            else:
                try:
                    idx = int(module_choice) - 1
                    if 0 <= idx < len(modules):
                        modules.insert(0, modules.pop(idx))
                except ValueError:
                    console.print("[red]Invalid choice[/red]")

        elif choice == "6":
            console.print("\n[bold]Available modules:[/bold]")
            for i, mod in enumerate(modules, 1):
                marker = "→" if i == 1 else " "
                console.print(f"  {marker} {i}. {mod}")

        # Wait for user
        if choice in ["1", "2", "3", "4"]:
            Prompt.ask("\n[dim]Press Enter to continue[/dim]", default="")


@app.command()
def list_modules():
    """List commonly tested modules"""
    show_banner()

    console.print("\n[bold cyan]Commonly Tested Modules:[/bold cyan]\n")

    modules = [
        ("backend/auth.py", "Authentication and authorization"),
        ("backend/app.py", "Main FastAPI application"),
        ("backend/dao/supabase_data_access.py", "Database access layer"),
        ("backend/dao/enhanced_data_access_fixed.py", "Enhanced DAO"),
    ]

    table = Table(box=box.ROUNDED)
    table.add_column("Module", style="cyan")
    table.add_column("Description")

    for module, desc in modules:
        table.add_row(module, desc)

    console.print(table)
    console.print()


def main():
    """Main entry point"""
    # If no arguments, run interactive mode
    if len(sys.argv) == 1:
        sys.argv.append("interactive")

    app()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Comprehensive test runner for the backend with different test categories and options.
"""

import subprocess
import sys
import argparse
import os
from pathlib import Path
from datetime import datetime


def run_command(cmd, description=""):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    if description:
        print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    start_time = datetime.now()
    result = subprocess.run(cmd, capture_output=False, text=True)
    end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds()
    print(f"\nCompleted in {duration:.2f} seconds")
    print(f"Exit code: {result.returncode}")
    
    return result.returncode == 0


def check_environment():
    """Check if the testing environment is properly set up."""
    print("Checking test environment...")
    
    # Check if uv is available
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("ERROR: uv not found. Please install uv first.")
            return False
        print(f"✓ uv found: {result.stdout.strip()}")
    except FileNotFoundError:
        print("ERROR: uv not found. Please install uv first.")
        return False
    
    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print("ERROR: pyproject.toml not found. Run from backend directory.")
        return False
    print("✓ Found pyproject.toml")
    
    # Check if tests directory exists
    if not Path("tests").exists():
        print("ERROR: tests directory not found.")
        return False
    print("✓ Found tests directory")
    
    # Check environment variables
    supabase_url = os.getenv('SUPABASE_URL')
    if supabase_url:
        print(f"✓ SUPABASE_URL: {supabase_url}")
    else:
        print("⚠️  SUPABASE_URL not set (some tests may be skipped)")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Run backend tests with various options")
    parser.add_argument("--category", choices=["unit", "integration", "contract", "e2e", "smoke", "slow", "all"],
                       default="all", help="Test category to run")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage")
    parser.add_argument("--html-coverage", action="store_true", help="Generate HTML coverage report")
    parser.add_argument("--xml-coverage", action="store_true", help="Generate XML coverage report")
    parser.add_argument("--json-coverage", action="store_true", help="Generate JSON coverage report")
    parser.add_argument("--fail-under", type=int, help="Fail if coverage is below this percentage")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fail-fast", "-x", action="store_true", help="Stop on first failure")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    parser.add_argument("--file", help="Run specific test file")
    parser.add_argument("--function", help="Run specific test function")
    parser.add_argument("--dry-run", action="store_true", help="Show commands without running")

    args = parser.parse_args()

    # Check environment
    if not check_environment():
        sys.exit(1)

    # Build pytest command
    cmd = ["uv", "run", "pytest"]

    # Per-category coverage thresholds (if not specified by user)
    coverage_thresholds = {
        "unit": 80,
        "integration": 70,
        "contract": 90,
        "e2e": 50,
        "smoke": 100,
        "all": 75
    }

    # Add test category markers
    if args.category == "unit":
        cmd.extend(["-m", "unit"])
    elif args.category == "integration":
        cmd.extend(["-m", "integration"])
    elif args.category == "contract":
        cmd.extend(["-m", "contract"])
    elif args.category == "e2e":
        cmd.extend(["-m", "e2e"])
    elif args.category == "smoke":
        cmd.extend(["-m", "smoke"])
    elif args.category == "slow":
        cmd.extend(["-m", "slow"])
    elif args.category == "all":
        # Run all tests
        pass
    
    # Add coverage options
    if args.coverage or args.html_coverage or args.xml_coverage or args.json_coverage:
        cmd.extend(["--cov=."])

        if args.html_coverage:
            cmd.extend(["--cov-report=html"])
        if args.xml_coverage:
            cmd.extend(["--cov-report=xml"])
        if args.json_coverage:
            cmd.extend(["--cov-report=json"])
        if not args.html_coverage and not args.xml_coverage and not args.json_coverage:
            cmd.extend(["--cov-report=term-missing"])

        # Add coverage threshold
        fail_under = args.fail_under if args.fail_under else coverage_thresholds.get(args.category, 75)
        cmd.extend(["--cov-fail-under", str(fail_under)])
    
    # Add verbose output
    if args.verbose:
        cmd.append("-v")
    
    # Add fail fast
    if args.fail_fast:
        cmd.append("-x")
    
    # Add parallel execution
    if args.parallel:
        cmd.extend(["-n", "auto"])  # Requires pytest-xdist
    
    # Add specific file or function
    if args.file:
        if args.function:
            cmd.append(f"{args.file}::{args.function}")
        else:
            cmd.append(args.file)
    elif args.function:
        cmd.extend(["-k", args.function])
    
    # Show command if dry run
    if args.dry_run:
        print(f"Would run: {' '.join(cmd)}")
        return
    
    # Run the tests
    description = f"pytest tests ({args.category} category)"
    if args.coverage or args.html_coverage or args.xml_coverage or args.json_coverage:
        fail_under = args.fail_under if args.fail_under else coverage_thresholds.get(args.category, 75)
        description += f" with coverage (threshold: {fail_under}%)"

    success = run_command(cmd, description)

    # Generate additional reports
    if args.html_coverage:
        print(f"\n{'='*60}")
        if success:
            print("✅ HTML coverage report generated in htmlcov/")
        else:
            print("⚠️  HTML coverage report generated in htmlcov/ (tests failed or coverage threshold not met)")
        print("Open htmlcov/index.html in your browser to view the report")
        print(f"{'='*60}")

    if args.xml_coverage:
        print(f"\n{'='*60}")
        if success:
            print("✅ XML coverage report generated as coverage.xml")
        else:
            print("⚠️  XML coverage report generated as coverage.xml (tests failed or coverage threshold not met)")
        print(f"{'='*60}")

    if args.json_coverage:
        print(f"\n{'='*60}")
        if success:
            print("✅ JSON coverage report generated as coverage.json")
        else:
            print("⚠️  JSON coverage report generated as coverage.json (tests failed or coverage threshold not met)")
        print(f"{'='*60}")

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

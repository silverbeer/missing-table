#!/usr/bin/env python3
"""
Comprehensive test runner for the backend with different test categories and options.
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and return the result."""
    if description:
        pass

    start_time = datetime.now()
    result = subprocess.run(cmd, capture_output=False, text=True)
    end_time = datetime.now()

    (end_time - start_time).total_seconds()

    return result.returncode == 0


def check_environment():
    """Check if the testing environment is properly set up."""

    # Check if uv is available
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            return False
    except FileNotFoundError:
        return False

    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        return False

    # Check if tests directory exists
    if not Path("tests").exists():
        return False

    # Check environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    if supabase_url:
        pass
    else:
        pass

    return True


def main():
    parser = argparse.ArgumentParser(description="Run backend tests with various options")
    parser.add_argument(
        "--category",
        choices=["unit", "integration", "contract", "e2e", "smoke", "slow", "all"],
        default="all",
        help="Test category to run",
    )
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
        "all": 75,
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

        # Add coverage threshold (use is not None to allow 0)
        fail_under = args.fail_under if args.fail_under is not None else coverage_thresholds.get(args.category, 75)
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
        return

    # Run the tests
    description = f"pytest tests ({args.category} category)"
    if args.coverage or args.html_coverage or args.xml_coverage or args.json_coverage:
        fail_under = args.fail_under if args.fail_under is not None else coverage_thresholds.get(args.category, 75)
        description += f" with coverage (threshold: {fail_under}%)"

    success = run_command(cmd, description)

    # Generate additional reports
    if args.html_coverage:
        if success:
            pass
        else:
            pass

    if args.xml_coverage:
        if success:
            pass
        else:
            pass

    if args.json_coverage:
        if success:
            pass
        else:
            pass

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

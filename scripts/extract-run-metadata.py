#!/usr/bin/env python3
"""
Extract structured metadata from test reports for history tracking.

This script parses Allure and Vitest reports to extract:
- Summary statistics per suite
- Individual test results with status and duration
- Coverage percentages

Output is used for:
- Test run history tracking
- Regression detection (comparing runs)
- Flaky test detection

Usage:
    python scripts/extract-run-metadata.py \
        --run-id 12345 \
        --commit-sha abc1234 \
        --backend-allure-dir backend/allure-report \
        --backend-coverage-json backend/coverage.json \
        --frontend-results-json frontend/test-results.json \
        --frontend-coverage-json frontend/coverage/coverage-final.json \
        --journey-allure-dir backend/allure-report \
        --output /tmp/run-metadata.json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Pydantic Models
# =============================================================================


class TestResult(BaseModel):
    """Individual test result."""

    suite: str  # "backend", "frontend", "journey"
    name: str  # Short test name
    full_name: str  # Full test path
    status: Literal["passed", "failed", "broken", "skipped", "unknown"]
    duration_ms: int = 0


class SuiteStats(BaseModel):
    """Summary statistics for a test suite."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    broken: int = 0
    skipped: int = 0
    duration_ms: int = 0
    coverage_pct: Optional[float] = None


class RunMetadata(BaseModel):
    """Complete metadata for a test run."""

    run_id: str
    commit_sha: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    trigger: str = "workflow_dispatch"
    workflow: str = "unit"  # "unit" or "journey"
    version: str = ""  # Build version (e.g., "1.0.1.252")
    branch: str = ""  # Git branch name
    suites: dict[str, SuiteStats] = Field(default_factory=dict)
    tests: list[TestResult] = Field(default_factory=list)

    @property
    def overall_status(self) -> str:
        """Return overall status: passed, failed, or unknown."""
        if not self.suites:
            return "unknown"
        total_failed = sum(s.failed + s.broken for s in self.suites.values())
        if total_failed > 0:
            return "failed"
        total_tests = sum(s.total for s in self.suites.values())
        if total_tests == 0:
            return "unknown"
        return "passed"


# =============================================================================
# Allure Report Parsing
# =============================================================================


def parse_allure_summary(allure_dir: Path) -> tuple[SuiteStats, int]:
    """Parse Allure summary.json for aggregate stats."""
    summary_file = allure_dir / "widgets" / "summary.json"

    if not summary_file.exists():
        print(f"Warning: {summary_file} not found", file=sys.stderr)
        return SuiteStats(), 0

    with open(summary_file) as f:
        data = json.load(f)

    statistic = data.get("statistic", {})
    time_data = data.get("time", {})

    return SuiteStats(
        total=statistic.get("total", 0),
        passed=statistic.get("passed", 0),
        failed=statistic.get("failed", 0),
        broken=statistic.get("broken", 0),
        skipped=statistic.get("skipped", 0),
        duration_ms=time_data.get("duration", 0),
    ), time_data.get("duration", 0)


def parse_allure_tests(allure_dir: Path, suite_name: str) -> list[TestResult]:
    """Parse individual test results from Allure data directory."""
    tests = []
    data_dir = allure_dir / "data" / "test-cases"

    if not data_dir.exists():
        # Try alternative location
        data_dir = allure_dir / "data"

    # Allure stores test results in multiple JSON files
    # Look for test-cases/*.json or suites.json
    suites_file = allure_dir / "data" / "suites.json"

    if suites_file.exists():
        with open(suites_file) as f:
            data = json.load(f)

        # Parse the suites.json structure
        for child in data.get("children", []):
            tests.extend(_parse_allure_suite_children(child, suite_name))

    return tests


def _parse_allure_suite_children(node: dict, suite_name: str) -> list[TestResult]:
    """Recursively parse Allure suite structure."""
    tests = []

    if "children" in node:
        # This is a container (test class or module)
        for child in node["children"]:
            tests.extend(_parse_allure_suite_children(child, suite_name))
    else:
        # This is a test case
        status = node.get("status", "unknown")
        # Map Allure status to our status
        status_map = {
            "passed": "passed",
            "failed": "failed",
            "broken": "broken",
            "skipped": "skipped",
            "pending": "skipped",
        }
        normalized_status = status_map.get(status, "unknown")

        name = node.get("name", "unknown")
        parent_name = node.get("parentUid", "")

        tests.append(TestResult(
            suite=suite_name,
            name=name,
            full_name=node.get("uid", name),  # Use uid as full path
            status=normalized_status,
            duration_ms=node.get("time", {}).get("duration", 0),
        ))

    return tests


# =============================================================================
# Vitest Report Parsing
# =============================================================================


def parse_vitest_results(results_json: Path) -> tuple[SuiteStats, list[TestResult]]:
    """Parse Vitest JSON report for stats and individual tests."""
    if not results_json.exists():
        print(f"Warning: {results_json} not found", file=sys.stderr)
        return SuiteStats(), []

    with open(results_json) as f:
        data = json.load(f)

    # Calculate duration
    start_time = data.get("startTime", 0)
    test_results = data.get("testResults", [])
    end_time = max((t.get("endTime", 0) for t in test_results), default=start_time)
    duration_ms = int(end_time - start_time) if end_time > start_time else 0

    stats = SuiteStats(
        total=data.get("numTotalTests", 0),
        passed=data.get("numPassedTests", 0),
        failed=data.get("numFailedTests", 0),
        skipped=data.get("numPendingTests", 0) + data.get("numTodoTests", 0),
        duration_ms=duration_ms,
    )

    # Parse individual test results
    tests = []
    for file_result in test_results:
        file_name = file_result.get("name", "unknown")
        for assertion in file_result.get("assertionResults", []):
            status_map = {
                "passed": "passed",
                "failed": "failed",
                "pending": "skipped",
                "todo": "skipped",
            }
            status = status_map.get(assertion.get("status", ""), "unknown")

            tests.append(TestResult(
                suite="frontend",
                name=assertion.get("title", "unknown"),
                full_name=f"{file_name}::{assertion.get('fullName', assertion.get('title', ''))}",
                status=status,
                duration_ms=int(assertion.get("duration", 0)),
            ))

    return stats, tests


# =============================================================================
# Coverage Parsing
# =============================================================================


def parse_python_coverage(coverage_json: Path) -> Optional[float]:
    """Parse Python coverage.json for percent covered."""
    if not coverage_json.exists():
        return None

    with open(coverage_json) as f:
        data = json.load(f)

    totals = data.get("totals", {})
    return totals.get("percent_covered", 0.0)


def parse_istanbul_coverage(coverage_json: Path) -> Optional[float]:
    """Parse Istanbul/V8 coverage-final.json for percent covered."""
    if not coverage_json.exists():
        return None

    with open(coverage_json) as f:
        data = json.load(f)

    total_statements = 0
    covered_statements = 0

    for file_data in data.values():
        statements = file_data.get("s", {})
        total_statements += len(statements)
        covered_statements += sum(1 for count in statements.values() if count > 0)

    if total_statements == 0:
        return 0.0

    return (covered_statements / total_statements) * 100


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract run metadata from test reports")
    parser.add_argument("--run-id", required=True, help="GitHub Actions run ID")
    parser.add_argument("--commit-sha", required=True, help="Git commit SHA")
    parser.add_argument("--trigger", default="workflow_dispatch",
                        help="Workflow trigger type (push, workflow_dispatch, schedule)")
    parser.add_argument("--workflow", default="unit",
                        choices=["unit", "journey"],
                        help="Workflow type: unit (quality.yml) or journey (quality-journey.yml)")
    parser.add_argument("--version", default="",
                        help="Build version (e.g., 1.0.1.252)")
    parser.add_argument("--branch", default="",
                        help="Git branch name")
    parser.add_argument("--output", "-o", required=True, help="Output JSON file path")

    # Backend inputs
    parser.add_argument("--backend-allure-dir", help="Path to backend Allure report")
    parser.add_argument("--backend-coverage-json", help="Path to backend coverage.json")

    # Frontend inputs
    parser.add_argument("--frontend-results-json", help="Path to Vitest results JSON")
    parser.add_argument("--frontend-coverage-json", help="Path to frontend coverage JSON")

    # Journey inputs
    parser.add_argument("--journey-allure-dir", help="Path to journey Allure report")

    args = parser.parse_args()

    # Initialize metadata
    metadata = RunMetadata(
        run_id=args.run_id,
        commit_sha=args.commit_sha,
        trigger=args.trigger,
        workflow=args.workflow,
        version=args.version,
        branch=args.branch,
    )

    # Process backend tests
    if args.backend_allure_dir:
        allure_dir = Path(args.backend_allure_dir)
        if allure_dir.exists():
            stats, _ = parse_allure_summary(allure_dir)
            if args.backend_coverage_json:
                stats.coverage_pct = parse_python_coverage(Path(args.backend_coverage_json))
            metadata.suites["backend"] = stats

            tests = parse_allure_tests(allure_dir, "backend")
            metadata.tests.extend(tests)
            print(f"Backend: {stats.passed}/{stats.total} tests, "
                  f"{len(tests)} individual results extracted")

    # Process frontend tests
    if args.frontend_results_json:
        results_path = Path(args.frontend_results_json)
        if results_path.exists():
            stats, tests = parse_vitest_results(results_path)
            if args.frontend_coverage_json:
                stats.coverage_pct = parse_istanbul_coverage(Path(args.frontend_coverage_json))
            metadata.suites["frontend"] = stats
            metadata.tests.extend(tests)
            print(f"Frontend: {stats.passed}/{stats.total} tests, "
                  f"{len(tests)} individual results extracted")

    # Process journey tests
    if args.journey_allure_dir:
        allure_dir = Path(args.journey_allure_dir)
        if allure_dir.exists():
            stats, _ = parse_allure_summary(allure_dir)
            metadata.suites["journey"] = stats

            tests = parse_allure_tests(allure_dir, "journey")
            metadata.tests.extend(tests)
            print(f"Journey: {stats.passed}/{stats.total} tests, "
                  f"{len(tests)} individual results extracted")

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(metadata.model_dump(), f, indent=2)

    print(f"Metadata written to: {output_path}")
    print(f"Overall status: {metadata.overall_status}")
    print(f"Total tests tracked: {len(metadata.tests)}")


if __name__ == "__main__":
    main()

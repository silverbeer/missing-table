#!/usr/bin/env python3
"""
Compare test runs to detect regressions, improvements, and flaky tests.

This script compares the current run against history to identify:
- New failures (tests that were passing, now failing)
- Fixed tests (tests that were failing, now passing)
- Flaky tests (tests that flip status frequently)
- Significant duration changes

Usage:
    python scripts/compare-runs.py \
        --current /tmp/run-metadata.json \
        --history /tmp/history.json \
        --output /tmp/comparison.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Models
# =============================================================================


class TestChange(BaseModel):
    """A test that changed status between runs."""

    suite: str
    name: str
    full_name: str
    previous_status: str
    current_status: str
    duration_ms: int = 0


class FlakyTest(BaseModel):
    """A test identified as flaky."""

    suite: str
    name: str
    full_name: str
    flip_count: int  # Number of status changes in history
    recent_statuses: list[str]  # Status history (most recent first)


class DurationChange(BaseModel):
    """A test with significant duration change."""

    suite: str
    name: str
    previous_ms: int
    current_ms: int
    change_pct: float


class ComparisonResult(BaseModel):
    """Result of comparing runs."""

    current_run_id: str
    previous_run_id: Optional[str] = None
    status_change: Literal["regression", "improvement", "stable", "mixed", "first_run"]
    summary: dict = Field(default_factory=lambda: {
        "new_failures": 0,
        "fixed": 0,
        "still_failing": 0,
        "flaky": 0,
    })
    new_failures: list[TestChange] = Field(default_factory=list)
    fixed: list[TestChange] = Field(default_factory=list)
    still_failing: list[TestChange] = Field(default_factory=list)
    flaky_tests: list[FlakyTest] = Field(default_factory=list)
    duration_changes: dict = Field(default_factory=lambda: {
        "significant_slowdowns": [],
        "significant_speedups": [],
    })


# =============================================================================
# Functions
# =============================================================================


def load_json(path: Path) -> dict:
    """Load and parse a JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path) as f:
        return json.load(f)


def get_test_status_map(tests: list[dict]) -> dict[str, dict]:
    """Create a map of test full_name -> test data."""
    return {t["full_name"]: t for t in tests}


def get_previous_run_tests(history: dict) -> Optional[dict[str, dict]]:
    """Get test results from the most recent run in history."""
    runs = history.get("runs", [])
    if not runs:
        return None

    # The most recent run in history is at index 0
    # But we need the full metadata, not just summary
    # Since history only has summary, we can't get individual tests
    # We need to download the previous run's full metadata

    return None  # History doesn't have individual tests


def compare_with_previous(
    current_tests: list[dict],
    previous_tests: Optional[dict[str, dict]],
) -> tuple[list[TestChange], list[TestChange], list[TestChange]]:
    """Compare current tests with previous run.

    Returns: (new_failures, fixed, still_failing)
    """
    new_failures = []
    fixed = []
    still_failing = []

    if previous_tests is None:
        return new_failures, fixed, still_failing

    current_map = get_test_status_map(current_tests)

    # Check each current test against previous
    for test in current_tests:
        full_name = test["full_name"]
        current_status = test["status"]
        prev_test = previous_tests.get(full_name)

        if prev_test is None:
            # New test, skip comparison
            continue

        prev_status = prev_test["status"]

        # Determine if this is a failure (failed or broken)
        is_current_fail = current_status in ("failed", "broken")
        was_prev_fail = prev_status in ("failed", "broken")

        if is_current_fail and not was_prev_fail:
            # New failure
            new_failures.append(TestChange(
                suite=test["suite"],
                name=test["name"],
                full_name=full_name,
                previous_status=prev_status,
                current_status=current_status,
                duration_ms=test.get("duration_ms", 0),
            ))
        elif not is_current_fail and was_prev_fail:
            # Fixed
            fixed.append(TestChange(
                suite=test["suite"],
                name=test["name"],
                full_name=full_name,
                previous_status=prev_status,
                current_status=current_status,
                duration_ms=test.get("duration_ms", 0),
            ))
        elif is_current_fail and was_prev_fail:
            # Still failing
            still_failing.append(TestChange(
                suite=test["suite"],
                name=test["name"],
                full_name=full_name,
                previous_status=prev_status,
                current_status=current_status,
                duration_ms=test.get("duration_ms", 0),
            ))

    return new_failures, fixed, still_failing


def detect_flaky_tests(
    current_tests: list[dict],
    history_runs: list[dict],
    min_flips: int = 2,
) -> list[FlakyTest]:
    """Detect flaky tests by analyzing status changes across runs.

    A test is considered flaky if it has changed status >= min_flips times.
    """
    flaky = []

    # Build status history for each test
    # Note: history_runs only contains summaries, not individual test results
    # For now, we'll return empty - we need to store full test results in history
    # This will be enhanced when we store test results in S3

    # TODO: Implement when we have access to historical test results
    # For now, we can only detect flaky tests if we download previous run metadata

    return flaky


def detect_duration_changes(
    current_tests: list[dict],
    previous_tests: Optional[dict[str, dict]],
    threshold_pct: float = 50.0,
    min_duration_ms: int = 100,
) -> tuple[list[DurationChange], list[DurationChange]]:
    """Detect significant duration changes.

    Returns: (slowdowns, speedups)
    """
    slowdowns = []
    speedups = []

    if previous_tests is None:
        return slowdowns, speedups

    for test in current_tests:
        full_name = test["full_name"]
        current_ms = test.get("duration_ms", 0)
        prev_test = previous_tests.get(full_name)

        if prev_test is None:
            continue

        prev_ms = prev_test.get("duration_ms", 0)

        # Skip very fast tests (noise)
        if prev_ms < min_duration_ms and current_ms < min_duration_ms:
            continue

        # Calculate percentage change
        if prev_ms > 0:
            change_pct = ((current_ms - prev_ms) / prev_ms) * 100
        else:
            continue

        if abs(change_pct) >= threshold_pct:
            change = DurationChange(
                suite=test["suite"],
                name=test["name"],
                previous_ms=prev_ms,
                current_ms=current_ms,
                change_pct=round(change_pct, 1),
            )

            if change_pct > 0:
                slowdowns.append(change)
            else:
                speedups.append(change)

    # Sort by absolute change percentage
    slowdowns.sort(key=lambda x: x.change_pct, reverse=True)
    speedups.sort(key=lambda x: x.change_pct)

    return slowdowns[:10], speedups[:10]  # Top 10 each


def determine_status_change(
    new_failures: list,
    fixed: list,
    still_failing: list,
    has_previous: bool,
) -> Literal["regression", "improvement", "stable", "mixed", "first_run"]:
    """Determine overall status change."""
    if not has_previous:
        return "first_run"

    has_new_failures = len(new_failures) > 0
    has_fixed = len(fixed) > 0

    if has_new_failures and has_fixed:
        return "mixed"
    elif has_new_failures:
        return "regression"
    elif has_fixed:
        return "improvement"
    else:
        return "stable"


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare test runs for regression detection")
    parser.add_argument("--current", required=True,
                        help="Path to current run metadata JSON")
    parser.add_argument("--history", required=True,
                        help="Path to history.json")
    parser.add_argument("--previous-metadata",
                        help="Path to previous run's full metadata JSON (optional)")
    parser.add_argument("--output", "-o", required=True,
                        help="Output path for comparison.json")
    parser.add_argument("--duration-threshold", type=float, default=50.0,
                        help="Percent change threshold for duration changes (default: 50)")

    args = parser.parse_args()

    # Load current run
    try:
        current = load_json(Path(args.current))
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Load history
    try:
        history = load_json(Path(args.history))
    except FileNotFoundError:
        print("No history found, treating as first run")
        history = {"runs": []}

    # Load previous run's full metadata if provided
    previous_tests = None
    previous_run_id = None

    if args.previous_metadata:
        try:
            previous = load_json(Path(args.previous_metadata))
            previous_tests = get_test_status_map(previous.get("tests", []))
            previous_run_id = previous.get("run_id")
            print(f"Comparing against previous run: {previous_run_id}")
        except FileNotFoundError:
            print("Previous metadata not found, skipping detailed comparison")
    elif history.get("runs"):
        # Get previous run ID from history (for reference)
        previous_run_id = history["runs"][0].get("run_id")
        print(f"Previous run ID from history: {previous_run_id}")
        print("Note: Detailed comparison requires --previous-metadata")

    current_tests = current.get("tests", [])

    # Perform comparisons
    new_failures, fixed, still_failing = compare_with_previous(
        current_tests, previous_tests
    )

    flaky_tests = detect_flaky_tests(current_tests, history.get("runs", []))

    slowdowns, speedups = detect_duration_changes(
        current_tests,
        previous_tests,
        threshold_pct=args.duration_threshold,
    )

    # Determine overall status change
    status_change = determine_status_change(
        new_failures, fixed, still_failing,
        has_previous=previous_tests is not None,
    )

    # Build result
    result = ComparisonResult(
        current_run_id=current.get("run_id", "unknown"),
        previous_run_id=previous_run_id,
        status_change=status_change,
        summary={
            "new_failures": len(new_failures),
            "fixed": len(fixed),
            "still_failing": len(still_failing),
            "flaky": len(flaky_tests),
        },
        new_failures=new_failures,
        fixed=fixed,
        still_failing=still_failing,
        flaky_tests=flaky_tests,
        duration_changes={
            "significant_slowdowns": [s.model_dump() for s in slowdowns],
            "significant_speedups": [s.model_dump() for s in speedups],
        },
    )

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(result.model_dump(), f, indent=2)

    # Print summary
    print(f"\nComparison result: {status_change}")
    print(f"  New failures: {len(new_failures)}")
    print(f"  Fixed: {len(fixed)}")
    print(f"  Still failing: {len(still_failing)}")
    print(f"  Flaky tests: {len(flaky_tests)}")
    print(f"  Duration changes: {len(slowdowns)} slowdowns, {len(speedups)} speedups")
    print(f"\nOutput: {output_path}")


if __name__ == "__main__":
    main()

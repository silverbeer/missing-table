#!/usr/bin/env python3
"""
Update the test run history index with current run metadata.

Maintains a rolling index of the last N runs for:
- Dashboard history display
- Regression detection
- Flaky test analysis

Usage:
    python scripts/update-history-index.py \
        --current-run /tmp/run-metadata.json \
        --history /tmp/history.json \
        --output /tmp/history.json \
        --max-runs 10
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# Models
# =============================================================================


class SuiteSummary(BaseModel):
    """Summary stats for a suite in history."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    coverage_pct: Optional[float] = None


class RunSummary(BaseModel):
    """Summary of a single run for history index."""

    run_id: str
    commit_sha: str
    timestamp: str
    status: str  # "passed", "failed", "unknown"
    workflow: str = "unit"  # "unit" or "journey"
    summary: dict  # {total, passed, failed, skipped}
    suites: dict[str, SuiteSummary] = Field(default_factory=dict)
    report_url: str = ""


class HistoryIndex(BaseModel):
    """The history index containing recent runs."""

    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    runs: list[RunSummary] = Field(default_factory=list)


# =============================================================================
# Functions
# =============================================================================


def load_history(history_path: Path) -> HistoryIndex:
    """Load existing history or return empty index."""
    if not history_path.exists():
        print(f"No existing history at {history_path}, starting fresh")
        return HistoryIndex()

    try:
        with open(history_path) as f:
            data = json.load(f)
        return HistoryIndex.model_validate(data)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Warning: Could not parse history file: {e}", file=sys.stderr)
        return HistoryIndex()


def load_run_metadata(metadata_path: Path) -> dict:
    """Load run metadata JSON."""
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    with open(metadata_path) as f:
        return json.load(f)


def create_run_summary(metadata: dict) -> RunSummary:
    """Create a RunSummary from full run metadata."""
    suites_data = metadata.get("suites", {})

    # Calculate overall totals
    total = sum(s.get("total", 0) for s in suites_data.values())
    passed = sum(s.get("passed", 0) for s in suites_data.values())
    failed = sum(s.get("failed", 0) + s.get("broken", 0) for s in suites_data.values())
    skipped = sum(s.get("skipped", 0) for s in suites_data.values())

    # Determine status
    if total == 0:
        status = "unknown"
    elif failed > 0:
        status = "failed"
    else:
        status = "passed"

    # Build suite summaries
    suites = {}
    for suite_name, suite_data in suites_data.items():
        suites[suite_name] = SuiteSummary(
            total=suite_data.get("total", 0),
            passed=suite_data.get("passed", 0),
            failed=suite_data.get("failed", 0) + suite_data.get("broken", 0),
            skipped=suite_data.get("skipped", 0),
            coverage_pct=suite_data.get("coverage_pct"),
        )

    # Build report URL from timestamp and run_id
    run_id = metadata.get("run_id", "unknown")
    timestamp = metadata.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    report_url = f"/runs/missing-table/prod/{date_str}/{run_id}/"

    return RunSummary(
        run_id=run_id,
        commit_sha=metadata.get("commit_sha", "unknown"),
        timestamp=timestamp,
        status=status,
        workflow=metadata.get("workflow", "unit"),
        summary={
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        },
        suites=suites,
        report_url=report_url,
    )


def update_history(
    history: HistoryIndex,
    new_run: RunSummary,
    max_runs: int = 10
) -> HistoryIndex:
    """Add new run to history, maintaining max_runs limit."""
    # Check if this run already exists (by run_id)
    existing_ids = {r.run_id for r in history.runs}
    if new_run.run_id in existing_ids:
        print(f"Run {new_run.run_id} already in history, updating...")
        history.runs = [r for r in history.runs if r.run_id != new_run.run_id]

    # Add new run at the beginning (most recent first)
    history.runs.insert(0, new_run)

    # Trim to max_runs
    if len(history.runs) > max_runs:
        removed = len(history.runs) - max_runs
        history.runs = history.runs[:max_runs]
        print(f"Trimmed {removed} old run(s) from history")

    # Update timestamp
    history.updated_at = datetime.now(timezone.utc).isoformat()

    return history


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="Update test run history index")
    parser.add_argument("--current-run", required=True,
                        help="Path to current run metadata JSON")
    parser.add_argument("--history", required=True,
                        help="Path to existing history.json (or where to create it)")
    parser.add_argument("--output", "-o", required=True,
                        help="Output path for updated history.json")
    parser.add_argument("--max-runs", type=int, default=10,
                        help="Maximum number of runs to keep in history (default: 10)")

    args = parser.parse_args()

    # Load current run metadata
    try:
        metadata = load_run_metadata(Path(args.current_run))
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Load existing history
    history = load_history(Path(args.history))

    # Create summary for new run
    new_run = create_run_summary(metadata)
    print(f"Adding run {new_run.run_id} ({new_run.status}): "
          f"{new_run.summary['passed']}/{new_run.summary['total']} tests")

    # Update history
    history = update_history(history, new_run, args.max_runs)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(history.model_dump(), f, indent=2)

    print(f"History updated: {output_path}")
    print(f"Total runs in history: {len(history.runs)}")


if __name__ == "__main__":
    main()

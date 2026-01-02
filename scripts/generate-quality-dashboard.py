#!/usr/bin/env python3
"""
Generate Quality Dashboard HTML from test results.

This script reads backend (Allure) and frontend (Vitest JSON) test reports
and generates a unified quality dashboard showing all test suites.

Usage:
    python scripts/generate-quality-dashboard.py \
        --output /tmp/index.html \
        --commit-sha abc1234 \
        --run-id 12345 \
        --backend-allure-dir backend/allure-report \
        --backend-coverage-json backend/coverage.json \
        --frontend-results-json frontend/test-results.json \
        --frontend-coverage-json frontend/coverage/coverage-final.json \
        --journey-allure-dir backend/journey-allure-report
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, computed_field


# =============================================================================
# Pydantic Models
# =============================================================================


class TestStatistic(BaseModel):
    """Test result statistics."""

    passed: int = 0
    failed: int = 0
    broken: int = 0
    skipped: int = 0
    unknown: int = 0
    total: int = 0


class TestTime(BaseModel):
    """Test timing information from Allure."""

    start: int = 0
    stop: int = 0
    duration: int = 0  # milliseconds
    min_duration: int = Field(0, alias="minDuration")
    max_duration: int = Field(0, alias="maxDuration")
    sum_duration: int = Field(0, alias="sumDuration")


class AllureSummary(BaseModel):
    """Allure summary.json structure."""

    report_name: str = Field("Allure Report", alias="reportName")
    statistic: TestStatistic = Field(default_factory=TestStatistic)
    time: TestTime = Field(default_factory=TestTime)


class CoverageTotals(BaseModel):
    """Coverage totals from coverage.json (Python coverage.py format)."""

    covered_lines: int = 0
    num_statements: int = 0
    percent_covered: float = 0.0
    missing_lines: int = 0
    excluded_lines: int = 0


class CoverageReport(BaseModel):
    """Coverage.json structure (partial)."""

    totals: CoverageTotals = Field(default_factory=CoverageTotals)


class TestMetrics(BaseModel):
    """Aggregated metrics for a test suite."""

    name: str
    label: str
    tool: str = ""  # e.g., "pytest + Allure", "Vitest"
    statistic: TestStatistic = Field(default_factory=TestStatistic)
    duration_ms: int = 0
    coverage_percent: Optional[float] = None
    coverage_report_url: Optional[str] = None
    test_report_url: Optional[str] = None

    @computed_field
    @property
    def duration_sec(self) -> str:
        return f"{self.duration_ms / 1000:.1f}"

    @computed_field
    @property
    def pass_rate(self) -> float:
        if self.statistic.total == 0:
            return 0.0
        return self.statistic.passed / self.statistic.total * 100

    @computed_field
    @property
    def status(self) -> Literal["success", "failure", "unknown"]:
        if self.statistic.total == 0:
            return "unknown"
        if self.statistic.failed == 0 and self.statistic.broken == 0:
            return "success"
        return "failure"

    @computed_field
    @property
    def passed_pct(self) -> float:
        if self.statistic.total == 0:
            return 0.0
        return self.statistic.passed / self.statistic.total * 100

    @computed_field
    @property
    def failed_pct(self) -> float:
        if self.statistic.total == 0:
            return 0.0
        return self.statistic.failed / self.statistic.total * 100

    @computed_field
    @property
    def skipped_pct(self) -> float:
        if self.statistic.total == 0:
            return 0.0
        return self.statistic.skipped / self.statistic.total * 100


class DashboardConfig(BaseModel):
    """Configuration for dashboard generation."""

    commit_sha: str
    run_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    )
    repo_url: str = "https://github.com/silverbeer/missing-table"

    @computed_field
    @property
    def commit_short(self) -> str:
        return self.commit_sha[:7]


# =============================================================================
# Data Loading
# =============================================================================


def load_allure_summary(allure_dir: Path) -> AllureSummary:
    """Load and parse Allure's summary.json."""
    summary_file = allure_dir / "widgets" / "summary.json"

    if not summary_file.exists():
        print(f"Warning: {summary_file} not found", file=sys.stderr)
        return AllureSummary()

    with open(summary_file) as f:
        data = json.load(f)

    return AllureSummary.model_validate(data)


def load_python_coverage(coverage_json: Path) -> Optional[float]:
    """Load Python coverage.json and return percent covered."""
    if not coverage_json.exists():
        print(f"Warning: {coverage_json} not found", file=sys.stderr)
        return None

    with open(coverage_json) as f:
        data = json.load(f)

    report = CoverageReport.model_validate(data)
    return report.totals.percent_covered


def load_vitest_results(results_json: Path) -> tuple[TestStatistic, int]:
    """Load Vitest JSON results and return (statistics, duration_ms)."""
    if not results_json.exists():
        print(f"Warning: {results_json} not found", file=sys.stderr)
        return TestStatistic(), 0

    with open(results_json) as f:
        data = json.load(f)

    # Calculate duration from start/end times
    start_time = data.get("startTime", 0)
    test_results = data.get("testResults", [])
    end_time = max((t.get("endTime", 0) for t in test_results), default=start_time)
    duration_ms = int(end_time - start_time) if end_time > start_time else 0

    return TestStatistic(
        passed=data.get("numPassedTests", 0),
        failed=data.get("numFailedTests", 0),
        skipped=data.get("numPendingTests", 0) + data.get("numTodoTests", 0),
        total=data.get("numTotalTests", 0),
    ), duration_ms


def load_istanbul_coverage(coverage_json: Path) -> Optional[float]:
    """Load Istanbul/V8 coverage-final.json and return percent covered."""
    if not coverage_json.exists():
        print(f"Warning: {coverage_json} not found", file=sys.stderr)
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


def build_backend_metrics(
    allure_dir: Optional[Path] = None,
    coverage_json: Optional[Path] = None,
) -> TestMetrics:
    """Build TestMetrics for backend tests."""
    if allure_dir:
        allure = load_allure_summary(allure_dir)
        statistic = allure.statistic
        duration_ms = allure.time.duration
    else:
        statistic = TestStatistic()
        duration_ms = 0

    coverage_percent = None
    if coverage_json:
        coverage_percent = load_python_coverage(coverage_json)

    return TestMetrics(
        name="backend",
        label="Backend Unit",
        tool="pytest + Allure",
        statistic=statistic,
        duration_ms=duration_ms,
        coverage_percent=coverage_percent,
        coverage_report_url="latest/missing-table/prod/backend-unit/index.html",
        test_report_url="latest/missing-table/prod/allure/index.html",
    )


def build_frontend_metrics(
    results_json: Optional[Path] = None,
    coverage_json: Optional[Path] = None,
) -> TestMetrics:
    """Build TestMetrics for frontend tests."""
    if results_json:
        statistic, duration_ms = load_vitest_results(results_json)
    else:
        statistic = TestStatistic()
        duration_ms = 0

    coverage_percent = None
    if coverage_json:
        coverage_percent = load_istanbul_coverage(coverage_json)

    return TestMetrics(
        name="frontend",
        label="Frontend Unit",
        tool="Vitest",
        statistic=statistic,
        duration_ms=duration_ms,
        coverage_percent=coverage_percent,
        coverage_report_url="latest/missing-table/prod/frontend-unit/index.html",
        test_report_url="latest/missing-table/prod/frontend-vitest/index.html",
    )


def build_journey_metrics(
    allure_dir: Optional[Path] = None,
) -> TestMetrics:
    """Build TestMetrics for user journey tests."""
    if allure_dir:
        allure = load_allure_summary(allure_dir)
        statistic = allure.statistic
        duration_ms = allure.time.duration
    else:
        statistic = TestStatistic()
        duration_ms = 0

    return TestMetrics(
        name="journey",
        label="User Journey",
        tool="pytest + Allure",
        statistic=statistic,
        duration_ms=duration_ms,
        coverage_percent=None,  # Journey tests don't measure coverage
        coverage_report_url=None,
        test_report_url="latest/missing-table/prod/journey/index.html",
    )


# =============================================================================
# HTML Generation
# =============================================================================


def generate_status_style(status: str) -> tuple[str, str, str]:
    """Return (icon, color, background) for a status."""
    if status == "success":
        return "✅", "#22863a", "#dcffe4"
    elif status == "failure":
        return "❌", "#cb2431", "#ffeef0"
    return "❓", "#6b7280", "#f3f4f6"


def overall_status(metrics_list: list[TestMetrics]) -> str:
    """Determine overall status from multiple test suites."""
    if not metrics_list:
        return "unknown"
    if any(m.status == "failure" for m in metrics_list):
        return "failure"
    if all(m.status == "success" for m in metrics_list):
        return "success"
    return "unknown"


def generate_test_suite_card(m: TestMetrics) -> str:
    """Generate HTML card for a single test suite."""
    icon, color, bg = generate_status_style(m.status)
    coverage_str = f"{m.coverage_percent:.1f}%" if m.coverage_percent is not None else "N/A"
    tool_badge = f'<span class="tool-badge">{m.tool}</span>' if m.tool else ""

    return f'''
      <div class="suite-card">
        <div class="suite-header">
          <span class="suite-icon">{icon}</span>
          <h3>{m.label}</h3>
          {tool_badge}
        </div>
        <div class="suite-stats">
          <div class="stat">
            <span class="stat-value">{m.statistic.passed}<span class="stat-small">/{m.statistic.total}</span></span>
            <span class="stat-label">Tests</span>
          </div>
          <div class="stat">
            <span class="stat-value">{coverage_str}</span>
            <span class="stat-label">Coverage</span>
          </div>
          <div class="stat">
            <span class="stat-value">{m.duration_sec}<span class="stat-small">s</span></span>
            <span class="stat-label">Duration</span>
          </div>
        </div>
        <div class="test-bar">
          <div class="test-bar-passed" style="width: {m.passed_pct:.0f}%;"></div>
          <div class="test-bar-failed" style="width: {m.failed_pct:.0f}%;"></div>
          <div class="test-bar-skipped" style="width: {m.skipped_pct:.0f}%;"></div>
        </div>
      </div>'''


def generate_report_links(metrics_list: list[TestMetrics]) -> str:
    """Generate HTML for report links."""
    links = []

    for m in metrics_list:
        if m.test_report_url:
            # Determine icon and description based on tool
            if "Allure" in m.tool:
                icon = "🎯"
                desc = "Interactive test report with charts and history"
            else:
                icon = "🧪"
                desc = "Interactive test results viewer"

            links.append(f'''
        <a class="report-link" href="{m.test_report_url}">
          <span class="report-icon">{icon}</span>
          <div class="report-info">
            <h3>{m.label} Tests ({m.tool})</h3>
            <p>{desc}</p>
          </div>
        </a>''')

        if m.coverage_report_url:
            links.append(f'''
        <a class="report-link" href="{m.coverage_report_url}">
          <span class="report-icon">📈</span>
          <div class="report-info">
            <h3>{m.label} Coverage</h3>
            <p>Detailed code coverage analysis</p>
          </div>
        </a>''')

    return "\n".join(links)


def generate_dashboard_html(
    metrics_list: list[TestMetrics],
    config: DashboardConfig,
) -> str:
    """Generate the complete dashboard HTML."""
    status = overall_status(metrics_list)
    icon, color, bg = generate_status_style(status)

    total_passed = sum(m.statistic.passed for m in metrics_list)
    total_tests = sum(m.statistic.total for m in metrics_list)
    total_duration = sum(m.duration_ms for m in metrics_list)

    suite_cards = "\n".join(generate_test_suite_card(m) for m in metrics_list)
    report_links = generate_report_links(metrics_list)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📊</text></svg>">
  <title>Quality Dashboard - Missing Table</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      background-color: #f3f4f6;
      min-height: 100vh;
    }}
    .container {{ max-width: 1024px; margin: 0 auto; padding: 2rem 1rem; }}
    .header {{ text-align: center; margin-bottom: 2rem; }}
    .header h1 {{ font-size: 2.25rem; font-weight: 700; color: #2563eb; margin-bottom: 0.5rem; }}
    .header p {{ font-size: 1.125rem; color: #4b5563; }}

    /* Summary cards */
    .summary-cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}
    .summary-card {{
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      padding: 1rem;
      text-align: center;
    }}
    .summary-card-icon {{ font-size: 1.25rem; margin-bottom: 0.25rem; }}
    .summary-card-value {{ font-size: 1.5rem; font-weight: 700; color: #1f2937; }}
    .summary-card-value-small {{ font-size: 0.875rem; font-weight: 400; color: #6b7280; }}
    .summary-card-label {{ color: #4b5563; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .status-badge {{
      display: inline-block;
      padding: 0.25rem 0.5rem;
      border-radius: 0.25rem;
      font-weight: 600;
      font-size: 0.75rem;
    }}

    /* Test suite section */
    .suites-section {{
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }}
    .suites-section h2 {{ font-size: 1.125rem; font-weight: 600; color: #1f2937; margin-bottom: 1rem; }}
    .suites-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1rem;
    }}
    .suite-card {{
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 0.5rem;
      padding: 1rem;
    }}
    .suite-header {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.75rem;
    }}
    .suite-icon {{ font-size: 1.25rem; }}
    .suite-header h3 {{ font-size: 1rem; font-weight: 600; color: #1f2937; }}
    .tool-badge {{ font-size: 0.65rem; background: #e5e7eb; color: #4b5563; padding: 0.125rem 0.375rem; border-radius: 0.25rem; margin-left: auto; }}
    .suite-stats {{
      display: flex;
      justify-content: space-between;
      margin-bottom: 0.75rem;
    }}
    .stat {{ text-align: center; }}
    .stat-value {{ font-size: 1.125rem; font-weight: 600; color: #1f2937; }}
    .stat-small {{ font-size: 0.75rem; font-weight: 400; color: #6b7280; }}
    .stat-label {{ display: block; font-size: 0.65rem; color: #6b7280; text-transform: uppercase; }}
    .test-bar {{
      height: 0.375rem;
      background: #e5e7eb;
      border-radius: 0.25rem;
      overflow: hidden;
      display: flex;
    }}
    .test-bar-passed {{ background: #22c55e; }}
    .test-bar-failed {{ background: #ef4444; }}
    .test-bar-skipped {{ background: #f59e0b; }}

    /* Reports section */
    .reports-section {{
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }}
    .reports-section h2 {{ font-size: 1.125rem; font-weight: 600; color: #1f2937; margin-bottom: 1rem; }}
    .report-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1rem;
    }}
    .report-link {{
      display: flex;
      align-items: center;
      padding: 0.875rem;
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 0.5rem;
      text-decoration: none;
      color: #1f2937;
      transition: all 0.15s ease;
    }}
    .report-link:hover {{ background: #eff6ff; border-color: #2563eb; }}
    .report-icon {{ font-size: 1.25rem; margin-right: 0.75rem; }}
    .report-info h3 {{ font-size: 0.875rem; font-weight: 600; margin-bottom: 0.125rem; }}
    .report-info p {{ color: #6b7280; font-size: 0.75rem; }}

    /* Meta section */
    .meta-section {{
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      padding: 1rem 1.5rem;
      display: flex;
      flex-wrap: wrap;
      gap: 1rem 2rem;
    }}
    .meta-section p {{ font-size: 0.875rem; color: #4b5563; }}
    .meta-section a {{ color: #2563eb; text-decoration: none; }}
    .meta-section a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Quality Dashboard</h1>
      <p>Test results and coverage reports for Missing Table</p>
    </div>

    <div class="summary-cards">
      <div class="summary-card">
        <div class="summary-card-icon">{icon}</div>
        <div class="summary-card-value"><span class="status-badge" style="background: {bg}; color: {color};">{status}</span></div>
        <div class="summary-card-label">Overall Status</div>
      </div>
      <div class="summary-card">
        <div class="summary-card-icon">✅</div>
        <div class="summary-card-value">{total_passed}<span class="summary-card-value-small">/{total_tests}</span></div>
        <div class="summary-card-label">Total Tests</div>
      </div>
      <div class="summary-card">
        <div class="summary-card-icon">📦</div>
        <div class="summary-card-value">{len(metrics_list)}</div>
        <div class="summary-card-label">Test Suites</div>
      </div>
      <div class="summary-card">
        <div class="summary-card-icon">⚡</div>
        <div class="summary-card-value">{total_duration / 1000:.1f}<span class="summary-card-value-small">s</span></div>
        <div class="summary-card-label">Total Duration</div>
      </div>
    </div>

    <div class="suites-section">
      <h2>Test Suites</h2>
      <div class="suites-grid">
{suite_cards}
      </div>
    </div>

    <div class="reports-section">
      <h2>Detailed Reports</h2>
      <div class="report-grid">
{report_links}
      </div>
    </div>

    <div class="meta-section">
      <p><strong>Generated:</strong> {config.timestamp}</p>
      <p><strong>Commit:</strong> <a href="{config.repo_url}/commit/{config.commit_sha}">{config.commit_short}</a></p>
      <p><strong>Run:</strong> <a href="{config.repo_url}/actions/runs/{config.run_id}">#{config.run_id}</a></p>
    </div>
  </div>
</body>
</html>'''


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Quality Dashboard")
    parser.add_argument("--output", "-o", required=True, help="Output HTML file path")
    parser.add_argument("--commit-sha", required=True, help="Git commit SHA")
    parser.add_argument("--run-id", required=True, help="GitHub Actions run ID")

    # Backend test inputs
    parser.add_argument("--backend-allure-dir", help="Path to backend Allure report directory")
    parser.add_argument("--backend-coverage-json", help="Path to backend coverage.json")

    # Frontend test inputs
    parser.add_argument("--frontend-results-json", help="Path to frontend test-results.json")
    parser.add_argument("--frontend-coverage-json", help="Path to frontend coverage-final.json")

    # Journey test inputs
    parser.add_argument("--journey-allure-dir", help="Path to user journey Allure report directory")
    parser.add_argument("--include-journey", action="store_true",
                        help="Always show journey card (even without local allure data)")

    # Legacy single-suite arguments (for backwards compatibility)
    parser.add_argument("--allure-dir", help="(deprecated) Use --backend-allure-dir")
    parser.add_argument("--coverage-json", help="(deprecated) Use --backend-coverage-json")

    args = parser.parse_args()

    # Handle legacy arguments
    backend_allure = Path(args.backend_allure_dir) if args.backend_allure_dir else (
        Path(args.allure_dir) if args.allure_dir else None
    )
    backend_coverage = Path(args.backend_coverage_json) if args.backend_coverage_json else (
        Path(args.coverage_json) if args.coverage_json else None
    )

    # Build metrics for each test suite
    metrics_list = []

    if backend_allure or backend_coverage:
        backend = build_backend_metrics(
            allure_dir=backend_allure,
            coverage_json=backend_coverage,
        )
        metrics_list.append(backend)
        print(f"Backend: {backend.statistic.passed}/{backend.statistic.total} tests, "
              f"{backend.coverage_percent:.1f}% coverage" if backend.coverage_percent else
              f"Backend: {backend.statistic.passed}/{backend.statistic.total} tests")

    frontend_results = Path(args.frontend_results_json) if args.frontend_results_json else None
    frontend_coverage = Path(args.frontend_coverage_json) if args.frontend_coverage_json else None

    if frontend_results or frontend_coverage:
        frontend = build_frontend_metrics(
            results_json=frontend_results,
            coverage_json=frontend_coverage,
        )
        metrics_list.append(frontend)
        print(f"Frontend: {frontend.statistic.passed}/{frontend.statistic.total} tests, "
              f"{frontend.coverage_percent:.1f}% coverage" if frontend.coverage_percent else
              f"Frontend: {frontend.statistic.passed}/{frontend.statistic.total} tests")

    journey_allure = Path(args.journey_allure_dir) if args.journey_allure_dir else None

    if journey_allure or args.include_journey:
        journey = build_journey_metrics(allure_dir=journey_allure)
        metrics_list.append(journey)
        if journey.statistic.total > 0:
            print(f"Journey: {journey.statistic.passed}/{journey.statistic.total} tests, "
                  f"{journey.duration_sec}s duration")
        else:
            print("Journey: card added (run journey tests to see stats)")

    if not metrics_list:
        print("Error: No test results provided", file=sys.stderr)
        sys.exit(1)

    # Build config
    config = DashboardConfig(
        commit_sha=args.commit_sha,
        run_id=args.run_id,
    )

    # Generate HTML
    html = generate_dashboard_html(metrics_list, config)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)

    print(f"Dashboard generated: {output_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate Quality Dashboard HTML from test results.

This script reads Allure and coverage reports and generates a unified
quality dashboard. Designed to be extensible for multiple test types.

Usage:
    python scripts/generate-quality-dashboard.py \
        --output /tmp/index.html \
        --commit-sha abc1234 \
        --run-id 12345 \
        --test-type unit \
        --allure-dir backend/allure-report \
        --coverage-json backend/coverage.json
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
    """Test result statistics from Allure."""

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
    """Coverage totals from coverage.json."""

    covered_lines: int = 0
    num_statements: int = 0
    percent_covered: float = 0.0
    missing_lines: int = 0
    excluded_lines: int = 0


class CoverageReport(BaseModel):
    """Coverage.json structure (partial)."""

    totals: CoverageTotals = Field(default_factory=CoverageTotals)


class TestMetrics(BaseModel):
    """Aggregated metrics for a test type."""

    test_type: str
    statistic: TestStatistic = Field(default_factory=TestStatistic)
    duration_ms: int = 0
    coverage_percent: Optional[float] = None

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


def load_coverage_report(coverage_json: Path) -> Optional[CoverageReport]:
    """Load and parse coverage.json."""
    if not coverage_json.exists():
        print(f"Warning: {coverage_json} not found", file=sys.stderr)
        return None

    with open(coverage_json) as f:
        data = json.load(f)

    return CoverageReport.model_validate(data)


def build_test_metrics(
    test_type: str,
    allure_dir: Path,
    coverage_json: Optional[Path] = None,
) -> TestMetrics:
    """Build TestMetrics from Allure and coverage data."""
    allure = load_allure_summary(allure_dir)

    coverage_percent = None
    if coverage_json:
        coverage = load_coverage_report(coverage_json)
        if coverage:
            coverage_percent = coverage.totals.percent_covered

    return TestMetrics(
        test_type=test_type,
        statistic=allure.statistic,
        duration_ms=allure.time.duration,
        coverage_percent=coverage_percent,
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


def generate_dashboard_html(metrics: TestMetrics, config: DashboardConfig) -> str:
    """Generate the complete dashboard HTML."""
    icon, color, bg = generate_status_style(metrics.status)
    coverage_str = f"{metrics.coverage_percent:.1f}" if metrics.coverage_percent else "N/A"

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
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}
    .card {{
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06);
      padding: 1.25rem;
      text-align: center;
    }}
    .card-icon {{ font-size: 1.5rem; margin-bottom: 0.5rem; }}
    .card-value {{ font-size: 1.75rem; font-weight: 700; color: #1f2937; }}
    .card-value-small {{ font-size: 1rem; font-weight: 400; color: #6b7280; }}
    .card-label {{ color: #4b5563; font-size: 0.75rem; margin-top: 0.25rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .status-badge {{
      display: inline-block;
      padding: 0.375rem 0.75rem;
      border-radius: 0.375rem;
      font-weight: 600;
      font-size: 0.875rem;
    }}
    .progress-bar {{
      height: 0.375rem;
      background: #e5e7eb;
      border-radius: 0.25rem;
      overflow: hidden;
      margin-top: 0.5rem;
    }}
    .progress-bar-fill {{ height: 100%; border-radius: 0.25rem; }}
    .progress-bar-fill.green {{ background: #22c55e; }}
    .test-bar {{ display: flex; }}
    .test-bar-passed {{ background: #22c55e; }}
    .test-bar-failed {{ background: #ef4444; }}
    .test-bar-skipped {{ background: #f59e0b; }}
    .reports-section {{
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06);
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }}
    .reports-section h2 {{ font-size: 1.125rem; font-weight: 600; color: #1f2937; margin-bottom: 1rem; }}
    .report-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1rem;
    }}
    .report-link {{
      display: flex;
      align-items: center;
      padding: 1rem;
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 0.5rem;
      text-decoration: none;
      color: #1f2937;
      transition: all 0.15s ease;
    }}
    .report-link:hover {{ background: #eff6ff; border-color: #2563eb; }}
    .report-icon {{ font-size: 1.5rem; margin-right: 1rem; }}
    .report-info h3 {{ font-size: 1rem; font-weight: 600; margin-bottom: 0.25rem; }}
    .report-info p {{ color: #6b7280; font-size: 0.875rem; }}
    .meta-section {{
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06);
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

    <div class="cards">
      <div class="card">
        <div class="card-icon">{icon}</div>
        <div class="card-value"><span class="status-badge" style="background: {bg}; color: {color};">{metrics.status}</span></div>
        <div class="card-label">Build Status</div>
      </div>
      <div class="card">
        <div class="card-icon">✅</div>
        <div class="card-value">{metrics.statistic.passed}<span class="card-value-small"> / {metrics.statistic.total}</span></div>
        <div class="card-label">Tests Passed</div>
        <div class="progress-bar test-bar">
          <div class="test-bar-passed" style="width: {metrics.passed_pct:.0f}%;"></div>
          <div class="test-bar-failed" style="width: {metrics.failed_pct:.0f}%;"></div>
          <div class="test-bar-skipped" style="width: {metrics.skipped_pct:.0f}%;"></div>
        </div>
      </div>
      <div class="card">
        <div class="card-icon">📊</div>
        <div class="card-value">{coverage_str}<span class="card-value-small">%</span></div>
        <div class="card-label">Code Coverage</div>
        <div class="progress-bar"><div class="progress-bar-fill green" style="width: {metrics.coverage_percent or 0:.0f}%;"></div></div>
      </div>
      <div class="card">
        <div class="card-icon">⚡</div>
        <div class="card-value">{metrics.duration_sec}<span class="card-value-small">s</span></div>
        <div class="card-label">Test Duration</div>
      </div>
    </div>

    <div class="reports-section">
      <h2>Available Reports</h2>
      <div class="report-grid">
        <a class="report-link" href="latest/missing-table/prod/allure/index.html">
          <span class="report-icon">🎯</span>
          <div class="report-info">
            <h3>Allure Report</h3>
            <p>Interactive test report with charts and history</p>
          </div>
        </a>
        <a class="report-link" href="latest/missing-table/prod/backend-unit/index.html">
          <span class="report-icon">📈</span>
          <div class="report-info">
            <h3>Coverage Report</h3>
            <p>Detailed code coverage analysis</p>
          </div>
        </a>
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
    parser.add_argument("--test-type", default="unit", help="Test type (unit, integration, e2e)")
    parser.add_argument("--allure-dir", required=True, help="Path to Allure report directory")
    parser.add_argument("--coverage-json", help="Path to coverage.json")
    args = parser.parse_args()

    # Build metrics
    metrics = build_test_metrics(
        test_type=args.test_type,
        allure_dir=Path(args.allure_dir),
        coverage_json=Path(args.coverage_json) if args.coverage_json else None,
    )

    # Build config
    config = DashboardConfig(
        commit_sha=args.commit_sha,
        run_id=args.run_id,
    )

    # Generate HTML
    html = generate_dashboard_html(metrics, config)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)

    # Print summary
    print(f"Dashboard generated: {output_path}")
    print(f"  Test type: {metrics.test_type}")
    print(f"  Tests: {metrics.statistic.passed}/{metrics.statistic.total} passed ({metrics.pass_rate:.0f}%)")
    if metrics.coverage_percent:
        print(f"  Coverage: {metrics.coverage_percent:.1f}%")
    print(f"  Duration: {metrics.duration_sec}s")


if __name__ == "__main__":
    main()

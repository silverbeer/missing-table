#!/usr/bin/env python3
"""
Generate Quality Dashboard HTML from test results.

This script reads backend (Allure) and frontend (Vitest JSON) test reports
and generates a unified quality dashboard showing all test suites.

Features:
- Test suite summary cards with pass/fail/coverage stats
- Test run history (last 10 runs)
- Regression detection (new failures, fixed tests)
- Flaky test identification
- Duration change tracking

Usage:
    python scripts/generate-quality-dashboard.py \
        --output /tmp/index.html \
        --commit-sha abc1234 \
        --run-id 12345 \
        --backend-allure-dir backend/allure-report \
        --backend-coverage-json backend/coverage.json \
        --frontend-results-json frontend/test-results.json \
        --frontend-coverage-json frontend/coverage/coverage-final.json \
        --journey-allure-dir backend/journey-allure-report \
        --history-json /tmp/history.json \
        --comparison-json /tmp/comparison.json
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

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
    coverage_percent: float | None = None
    coverage_report_url: str | None = None
    test_report_url: str | None = None

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
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    )
    repo_url: str = "https://github.com/silverbeer/missing-table"

    @computed_field
    @property
    def commit_short(self) -> str:
        return self.commit_sha[:7]


# History and Comparison Models
class HistorySuiteSummary(BaseModel):
    """Suite summary from history."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    coverage_pct: float | None = None


class HistoryRun(BaseModel):
    """A run from history index."""

    run_id: str
    commit_sha: str
    timestamp: str
    status: str  # "passed", "failed", "unknown"
    workflow: str = "unit"  # "unit" or "journey"
    version: str = ""  # Build version (e.g., "1.0.1.252")
    branch: str = ""  # Git branch name
    summary: dict  # {total, passed, failed, skipped}
    suites: dict[str, HistorySuiteSummary] = Field(default_factory=dict)
    report_url: str = ""


class HistoryIndex(BaseModel):
    """History index containing recent runs."""

    updated_at: str = ""
    runs: list[HistoryRun] = Field(default_factory=list)


class TestChange(BaseModel):
    """A test that changed status."""

    suite: str
    name: str
    full_name: str = ""
    previous_status: str = ""
    current_status: str = ""
    duration_ms: int = 0


class FlakyTest(BaseModel):
    """A flaky test."""

    suite: str
    name: str
    full_name: str = ""
    flip_count: int = 0
    recent_statuses: list[str] = Field(default_factory=list)


class DurationChange(BaseModel):
    """A test with duration change."""

    suite: str = ""
    name: str
    previous_ms: int = 0
    current_ms: int = 0
    change_pct: float = 0.0


class ComparisonResult(BaseModel):
    """Comparison between runs."""

    current_run_id: str = ""
    previous_run_id: str | None = None
    status_change: str = "first_run"  # regression, improvement, stable, mixed, first_run
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


def load_python_coverage(coverage_json: Path) -> float | None:
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


def load_istanbul_coverage(coverage_json: Path) -> float | None:
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
    allure_dir: Path | None = None,
    coverage_json: Path | None = None,
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
    results_json: Path | None = None,
    coverage_json: Path | None = None,
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
    allure_dir: Path | None = None,
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


def build_contract_metrics(
    allure_dir: Path | None = None,
    api_inventory_json: Path | None = None,
) -> TestMetrics:
    """Build TestMetrics for API contract tests."""
    if allure_dir:
        allure = load_allure_summary(allure_dir)
        statistic = allure.statistic
        duration_ms = allure.time.duration
    else:
        statistic = TestStatistic()
        duration_ms = 0

    coverage_percent = None
    coverage_report_url = None

    if api_inventory_json and api_inventory_json.exists():
        try:
            with open(api_inventory_json) as f:
                inventory = json.load(f)
            summary = inventory.get("summary", {})
            total = summary.get("total_endpoints", 0)
            with_client = summary.get("with_client_method", 0)
            if total > 0:
                coverage_percent = (with_client / total) * 100
                coverage_report_url = "latest/missing-table/prod/api-coverage/index.html"
        except Exception as e:
            print(f"Warning: Could not parse API inventory: {e}", file=sys.stderr)

    return TestMetrics(
        name="contract",
        label="API Contract",
        tool="pytest + Allure",
        statistic=statistic,
        duration_ms=duration_ms,
        coverage_percent=coverage_percent,
        coverage_report_url=coverage_report_url,
        test_report_url="latest/missing-table/prod/contract/index.html",
    )


def load_history(history_json: Path) -> HistoryIndex | None:
    """Load history index from JSON file."""
    if not history_json.exists():
        print(f"Warning: {history_json} not found", file=sys.stderr)
        return None

    try:
        with open(history_json) as f:
            data = json.load(f)
        return HistoryIndex.model_validate(data)
    except Exception as e:
        print(f"Warning: Could not parse history: {e}", file=sys.stderr)
        return None


def load_comparison(comparison_json: Path) -> ComparisonResult | None:
    """Load comparison result from JSON file."""
    if not comparison_json.exists():
        print(f"Warning: {comparison_json} not found", file=sys.stderr)
        return None

    try:
        with open(comparison_json) as f:
            data = json.load(f)
        return ComparisonResult.model_validate(data)
    except Exception as e:
        print(f"Warning: Could not parse comparison: {e}", file=sys.stderr)
        return None


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


def format_timestamp(iso_timestamp: str) -> str:
    """Format ISO timestamp for display."""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %H:%M")
    except (ValueError, AttributeError):
        return "Unknown"


def generate_type_badge(workflow: str) -> str:
    """Return colored HTML badge for workflow type."""
    badges = {
        "unit": '<span class="type-badge type-unit">Unit</span>',
        "journey": '<span class="type-badge type-journey">Journey</span>',
        "contract": '<span class="type-badge type-contract">Contract</span>',
    }
    return badges.get(workflow, f'<span class="type-badge">{workflow}</span>')


def generate_history_section(
    history: HistoryIndex | None,
    comparison: ComparisonResult | None,
    config: DashboardConfig,
) -> str:
    """Generate unified HTML for Quality History section.

    Shows all workflow types (unit, journey, contract) in a single table
    with a Type column containing colored badges.
    """
    if not history or not history.runs:
        return ""

    section_id = "history"
    all_runs = history.runs

    if not all_runs:
        return ""

    # Generate comparison banner if we have comparison data
    banner_html = ""
    if comparison and comparison.status_change != "first_run":
        if comparison.status_change == "regression":
            banner_class = "regression"
            banner_icon = "⚠️"
            banner_text = f"{comparison.summary.get('new_failures', 0)} new test failure(s) since last run"
        elif comparison.status_change == "improvement":
            banner_class = "improvement"
            banner_icon = "✅"
            banner_text = f"{comparison.summary.get('fixed', 0)} test(s) fixed since last run"
        elif comparison.status_change == "mixed":
            banner_class = "mixed"
            banner_icon = "🔄"
            new_fails = comparison.summary.get('new_failures', 0)
            fixed = comparison.summary.get('fixed', 0)
            banner_text = f"{new_fails} new failure(s), {fixed} fixed since last run"
        else:
            banner_class = "stable"
            banner_icon = "✓"
            banner_text = "No changes since last run"

        banner_html = f'''
      <div class="comparison-banner {banner_class}">
        <span class="banner-icon">{banner_icon}</span>
        <span class="banner-text">{banner_text}</span>
        <button class="banner-toggle" onclick="toggleDiffDetails()">Show Details</button>
      </div>'''

    # Generate history table rows with checkboxes for comparison
    rows = []
    for i, run in enumerate(all_runs):
        is_current = (run.run_id == config.run_id)
        row_class = "current-run" if is_current else ""

        # Status icon
        if run.status == "passed":
            status_icon = "🟢"
        elif run.status == "failed":
            status_icon = "🔴"
        else:
            status_icon = "⚪"

        # Format suite columns
        backend = run.suites.get("backend")
        frontend = run.suites.get("frontend")
        journey = run.suites.get("journey")
        contract = run.suites.get("contract")

        def suite_cell(suite: HistorySuiteSummary | None) -> str:
            if not suite or suite.total == 0:
                return '<td class="suite-cell na">-</td>'
            css_class = "passed" if suite.failed == 0 else "failed"
            return f'<td class="suite-cell {css_class}">{suite.passed}/{suite.total}</td>'

        total = run.summary.get("total", 0)
        passed = run.summary.get("passed", 0)

        timestamp_display = format_timestamp(run.timestamp)
        timestamp_iso = run.timestamp
        commit_short = run.commit_sha[:7] if run.commit_sha else "unknown"

        # Extract date from timestamp for report URLs
        try:
            dt = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")

        # Build report links based on workflow
        report_base = f"/runs/missing-table/prod/{date_str}/{run.run_id}"
        if run.workflow == "journey":
            report_links = f'<a href="{report_base}/journey/" title="Journey Allure Report">🎯</a>'
        elif run.workflow == "contract":
            report_links = f'<a href="{report_base}/contract/" title="Contract Allure Report">🎯</a>'
        else:
            report_links = (
                f'<a href="{report_base}/allure/" title="Backend Allure Report">🎯</a> '
                f'<a href="{report_base}/backend-unit/" title="Backend Coverage">📊</a> '
                f'<a href="{report_base}/frontend-vitest/" title="Frontend Vitest Report">🧪</a> '
                f'<a href="{report_base}/frontend-unit/" title="Frontend Coverage">📈</a>'
            )

        # Type badge
        type_badge = generate_type_badge(run.workflow)

        # Build all 4 suite columns
        suite_cells = suite_cell(backend) + suite_cell(frontend) + suite_cell(journey) + suite_cell(contract)

        # Build info cell
        version_display = run.version if run.version else "-"
        branch_display = run.branch if run.branch else "-"
        build_cell = f'<span class="build-version">{version_display}</span><br><span class="build-branch">{branch_display}</span>' if run.version or run.branch else "-"

        rows.append(f'''
        <tr class="{row_class}" data-run-id="{run.run_id}" data-run-date="{date_str}" data-workflow="{run.workflow}">
          <td><input type="checkbox" class="run-checkbox {section_id}-checkbox" value="{run.run_id}" onchange="updateCompareButton('{section_id}')"></td>
          <td><a href="{config.repo_url}/actions/runs/{run.run_id}" target="_blank">#{run.run_id[-6:]}</a></td>
          <td>{timestamp_display}</td>
          <td class="build-cell">{build_cell}</td>
          <td><code><a href="{config.repo_url}/commit/{run.commit_sha}" target="_blank">{commit_short}</a></code></td>
          <td>{type_badge}</td>
          {suite_cells}
          <td>{passed}/{total}</td>
          <td class="report-links">{report_links}</td>
          <td>{status_icon}</td>
        </tr>''')

    rows_html = "\n".join(rows)

    return f'''
    <div class="history-section" id="{section_id}-section">
      <h2>Quality History (Last {len(all_runs)} Runs)</h2>
      <div class="compare-controls">
        <button id="{section_id}-compare-btn" class="compare-button" disabled onclick="compareSelectedRuns('{section_id}')">
          Select 2 runs to compare
        </button>
        <span id="{section_id}-compare-status" class="compare-status"></span>
      </div>
      {banner_html}
      <div class="history-table-wrapper">
        <table class="history-table">
          <thead>
            <tr>
              <th class="checkbox-col">Compare</th>
              <th>Run</th>
              <th>Date</th>
              <th>Build</th>
              <th>Commit</th>
              <th>Type</th>
              <th>Backend</th>
              <th>Frontend</th>
              <th>Journey</th>
              <th>Contract</th>
              <th>Total</th>
              <th>Reports</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
      </div>
    </div>
    <div id="{section_id}-compare-results" class="diff-section" style="display: none;">
      <div class="compare-header">
        <h3>Comparison Results</h3>
        <button class="close-compare" onclick="closeCompareResults('{section_id}')">✕ Close</button>
      </div>
      <div id="{section_id}-compare-content"></div>
    </div>'''


def generate_diff_section(comparison: ComparisonResult | None) -> str:
    """Generate HTML for diff/comparison details section."""
    if not comparison or comparison.status_change == "first_run":
        return ""

    sections = []

    # New failures
    if comparison.new_failures:
        items = "\n".join(f'''
          <li>
            <span class="test-name">{t.name}</span>
            <span class="suite-tag">{t.suite}</span>
            <span class="duration">{t.duration_ms / 1000:.1f}s</span>
          </li>''' for t in comparison.new_failures)

        sections.append(f'''
      <div class="diff-category new-failures">
        <h4>🔴 New Failures ({len(comparison.new_failures)})</h4>
        <ul>{items}</ul>
      </div>''')

    # Fixed tests
    if comparison.fixed:
        items = "\n".join(f'''
          <li>
            <span class="test-name">{t.name}</span>
            <span class="suite-tag">{t.suite}</span>
          </li>''' for t in comparison.fixed)

        sections.append(f'''
      <div class="diff-category fixed">
        <h4>🟢 Fixed ({len(comparison.fixed)})</h4>
        <ul>{items}</ul>
      </div>''')

    # Still failing
    if comparison.still_failing:
        items = "\n".join(f'''
          <li>
            <span class="test-name">{t.name}</span>
            <span class="suite-tag">{t.suite}</span>
          </li>''' for t in comparison.still_failing)

        sections.append(f'''
      <div class="diff-category still-failing">
        <h4>🟡 Still Failing ({len(comparison.still_failing)})</h4>
        <ul>{items}</ul>
      </div>''')

    # Flaky tests
    if comparison.flaky_tests:
        items = "\n".join(f'''
          <li>
            <span class="test-name">{t.name}</span>
            <span class="suite-tag">{t.suite}</span>
            <span class="flaky-indicator">⟳ {t.flip_count} flips</span>
          </li>''' for t in comparison.flaky_tests)

        sections.append(f'''
      <div class="diff-category flaky">
        <h4>⚠️ Flaky Tests ({len(comparison.flaky_tests)})</h4>
        <ul>{items}</ul>
      </div>''')

    # Duration changes
    slowdowns = comparison.duration_changes.get("significant_slowdowns", [])
    speedups = comparison.duration_changes.get("significant_speedups", [])

    if slowdowns or speedups:
        duration_items = []

        for s in slowdowns:
            name = s.get("name", "unknown")
            prev = s.get("previous_ms", 0) / 1000
            curr = s.get("current_ms", 0) / 1000
            pct = s.get("change_pct", 0)
            duration_items.append(f'''
            <tr class="slowdown">
              <td>{name}</td>
              <td>{prev:.1f}s → {curr:.1f}s</td>
              <td class="change-pct">+{pct:.0f}%</td>
            </tr>''')

        for s in speedups:
            name = s.get("name", "unknown")
            prev = s.get("previous_ms", 0) / 1000
            curr = s.get("current_ms", 0) / 1000
            pct = s.get("change_pct", 0)
            duration_items.append(f'''
            <tr class="speedup">
              <td>{name}</td>
              <td>{prev:.1f}s → {curr:.1f}s</td>
              <td class="change-pct">{pct:.0f}%</td>
            </tr>''')

        if duration_items:
            sections.append(f'''
      <div class="diff-category duration">
        <h4>⏱️ Significant Duration Changes</h4>
        <table class="duration-table">
          {"".join(duration_items)}
        </table>
      </div>''')

    if not sections:
        return ""

    return f'''
    <div class="diff-section" id="diff-details" style="display: none;">
      <h3>Changes from Previous Run</h3>
      {"".join(sections)}
    </div>'''


def generate_dashboard_html(
    metrics_list: list[TestMetrics],
    config: DashboardConfig,
    history: HistoryIndex | None = None,
    comparison: ComparisonResult | None = None,
) -> str:
    """Generate the complete dashboard HTML."""
    status = overall_status(metrics_list)
    icon, color, bg = generate_status_style(status)

    total_passed = sum(m.statistic.passed for m in metrics_list)
    total_tests = sum(m.statistic.total for m in metrics_list)
    total_duration = sum(m.duration_ms for m in metrics_list)

    suite_cards = "\n".join(generate_test_suite_card(m) for m in metrics_list)
    report_links = generate_report_links(metrics_list)

    # Generate unified history section showing all workflow types
    history_section = generate_history_section(history, comparison, config)

    diff_section = generate_diff_section(comparison)

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

    /* History section */
    .history-section {{
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }}
    .history-section h2 {{ font-size: 1.125rem; font-weight: 600; color: #1f2937; margin-bottom: 1rem; }}
    .history-table-wrapper {{ overflow-x: auto; }}
    .history-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
    .history-table th, .history-table td {{ padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #e5e7eb; }}
    .history-table th {{ background: #f9fafb; font-weight: 600; color: #4b5563; font-size: 0.75rem; text-transform: uppercase; }}
    .history-table tr:hover {{ background: #f9fafb; }}
    .history-table tr.current-run {{ background: #eff6ff; }}
    .history-table tr.current-run:hover {{ background: #dbeafe; }}
    .history-table a {{ color: #2563eb; text-decoration: none; }}
    .history-table a:hover {{ text-decoration: underline; }}
    .history-table code {{ background: #f3f4f6; padding: 0.125rem 0.25rem; border-radius: 0.25rem; font-size: 0.75rem; }}
    .suite-cell.passed {{ color: #22863a; }}
    .suite-cell.failed {{ color: #cb2431; }}
    .suite-cell.na {{ color: #9ca3af; }}

    /* Type badges */
    .type-badge {{
      display: inline-block;
      padding: 0.125rem 0.5rem;
      border-radius: 9999px;
      font-size: 0.6875rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.025em;
      white-space: nowrap;
    }}
    .type-unit {{ background: #dbeafe; color: #1d4ed8; }}
    .type-journey {{ background: #dcfce7; color: #15803d; }}
    .type-contract {{ background: #f3e8ff; color: #7e22ce; }}

    /* Comparison banner */
    .comparison-banner {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.75rem 1rem;
      border-radius: 0.375rem;
      margin-bottom: 1rem;
      font-size: 0.875rem;
    }}
    .comparison-banner.regression {{ background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }}
    .comparison-banner.improvement {{ background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }}
    .comparison-banner.mixed {{ background: #fffbeb; border: 1px solid #fde68a; color: #92400e; }}
    .comparison-banner.stable {{ background: #f9fafb; border: 1px solid #e5e7eb; color: #4b5563; }}
    .banner-icon {{ font-size: 1rem; }}
    .banner-text {{ flex: 1; }}
    .banner-toggle {{
      background: transparent;
      border: 1px solid currentColor;
      border-radius: 0.25rem;
      padding: 0.25rem 0.5rem;
      font-size: 0.75rem;
      cursor: pointer;
      color: inherit;
    }}
    .banner-toggle:hover {{ background: rgba(0,0,0,0.05); }}

    /* Diff section */
    .diff-section {{
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }}
    .diff-section h3 {{ font-size: 1rem; font-weight: 600; color: #1f2937; margin-bottom: 1rem; }}
    .diff-category {{ margin-bottom: 1rem; }}
    .diff-category:last-child {{ margin-bottom: 0; }}
    .diff-category h4 {{ font-size: 0.875rem; font-weight: 600; margin-bottom: 0.5rem; }}
    .diff-category ul {{ list-style: none; padding: 0; margin: 0; }}
    .diff-category li {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.375rem 0;
      border-bottom: 1px solid #f3f4f6;
      font-size: 0.8125rem;
    }}
    .diff-category li:last-child {{ border-bottom: none; }}
    .test-name {{ flex: 1; font-family: monospace; }}
    .suite-tag {{
      background: #e5e7eb;
      color: #4b5563;
      padding: 0.125rem 0.375rem;
      border-radius: 0.25rem;
      font-size: 0.6875rem;
      text-transform: uppercase;
    }}
    .duration {{ color: #6b7280; font-size: 0.75rem; }}
    .flaky-indicator {{ color: #d97706; font-size: 0.75rem; }}
    .new-failures h4 {{ color: #dc2626; }}
    .fixed h4 {{ color: #16a34a; }}
    .still-failing h4 {{ color: #ca8a04; }}
    .flaky h4 {{ color: #d97706; }}
    .duration-table {{ width: 100%; font-size: 0.8125rem; }}
    .duration-table td {{ padding: 0.375rem 0.5rem; }}
    .duration-table tr.slowdown {{ color: #dc2626; }}
    .duration-table tr.speedup {{ color: #16a34a; }}
    .change-pct {{ font-weight: 600; text-align: right; }}

    /* Compare controls */
    .compare-controls {{
      display: flex;
      align-items: center;
      gap: 1rem;
      margin-bottom: 1rem;
    }}
    .compare-button {{
      background: #2563eb;
      color: white;
      border: none;
      padding: 0.5rem 1rem;
      border-radius: 0.375rem;
      font-size: 0.875rem;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.15s;
    }}
    .compare-button:hover:not(:disabled) {{ background: #1d4ed8; }}
    .compare-button:disabled {{
      background: #9ca3af;
      cursor: not-allowed;
    }}
    .compare-status {{ color: #6b7280; font-size: 0.875rem; }}
    .checkbox-col {{ width: 60px; text-align: center; }}
    .report-links {{ white-space: nowrap; }}
    .report-links a {{
      display: inline-block;
      text-decoration: none;
      padding: 0.125rem;
      border-radius: 0.25rem;
      transition: background 0.15s;
    }}
    .report-links a:hover {{ background: #e5e7eb; }}
    .build-cell {{ font-size: 0.75rem; line-height: 1.3; white-space: nowrap; }}
    .build-version {{ font-weight: 600; color: #1f2937; }}
    .build-branch {{ color: #6b7280; }}
    .run-checkbox {{ width: 1rem; height: 1rem; cursor: pointer; }}
    .compare-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }}
    .close-compare {{
      background: transparent;
      border: 1px solid #e5e7eb;
      border-radius: 0.25rem;
      padding: 0.25rem 0.5rem;
      font-size: 0.75rem;
      cursor: pointer;
      color: #6b7280;
    }}
    .close-compare:hover {{ background: #f3f4f6; }}
    .compare-loading {{ text-align: center; padding: 2rem; color: #6b7280; }}
    .compare-error {{ color: #dc2626; padding: 1rem; background: #fef2f2; border-radius: 0.375rem; }}
    .compare-summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}
    .compare-stat {{
      background: #f9fafb;
      border-radius: 0.375rem;
      padding: 0.75rem;
      text-align: center;
    }}
    .compare-stat-value {{ font-size: 1.5rem; font-weight: 700; }}
    .compare-stat-value.new-fail {{ color: #dc2626; }}
    .compare-stat-value.fixed {{ color: #16a34a; }}
    .compare-stat-value.unchanged {{ color: #6b7280; }}
    .compare-stat-label {{ font-size: 0.75rem; color: #6b7280; text-transform: uppercase; }}
  </style>
  <script>
    function toggleDiffDetails() {{
      const diff = document.getElementById('diff-details');
      const btn = document.querySelector('.banner-toggle');
      if (diff.style.display === 'none') {{
        diff.style.display = 'block';
        btn.textContent = 'Hide Details';
      }} else {{
        diff.style.display = 'none';
        btn.textContent = 'Show Details';
      }}
    }}

    function updateCompareButton(sectionId) {{
      const checkboxes = document.querySelectorAll('.' + sectionId + '-checkbox:checked');
      const btn = document.getElementById(sectionId + '-compare-btn');
      const status = document.getElementById(sectionId + '-compare-status');

      if (!btn || !status) return;

      if (checkboxes.length === 0) {{
        btn.disabled = true;
        btn.textContent = 'Select 2 runs to compare';
        status.textContent = '';
      }} else if (checkboxes.length === 1) {{
        btn.disabled = true;
        btn.textContent = 'Select 1 more run';
        status.textContent = '1 run selected';
      }} else if (checkboxes.length === 2) {{
        btn.disabled = false;
        btn.textContent = 'Compare Selected Runs';
        status.textContent = '2 runs selected';
      }} else {{
        btn.disabled = true;
        btn.textContent = 'Select only 2 runs';
        status.textContent = checkboxes.length + ' runs selected (max 2)';
      }}
    }}

    async function fetchMetadata(runId, runDate) {{
      const url = `/runs/missing-table/prod/${{runDate}}/${{runId}}/metadata.json`;
      const response = await fetch(url);
      if (!response.ok) {{
        throw new Error(`Failed to fetch metadata for run ${{runId}}`);
      }}
      return response.json();
    }}

    function compareTests(olderMeta, newerMeta) {{
      const olderTests = {{}};
      const newerTests = {{}};

      // Build maps of test name -> status
      (olderMeta.tests || []).forEach(t => {{
        olderTests[t.full_name] = t;
      }});
      (newerMeta.tests || []).forEach(t => {{
        newerTests[t.full_name] = t;
      }});

      const newFailures = [];
      const fixed = [];
      const stillFailing = [];
      const newTests = [];

      // Check all tests in newer run
      Object.entries(newerTests).forEach(([name, test]) => {{
        const oldTest = olderTests[name];
        const isNewFail = test.status === 'failed' || test.status === 'broken';
        const wasOldFail = oldTest && (oldTest.status === 'failed' || oldTest.status === 'broken');

        if (!oldTest) {{
          newTests.push(test);
        }} else if (isNewFail && !wasOldFail) {{
          newFailures.push({{ ...test, previous_status: oldTest.status }});
        }} else if (!isNewFail && wasOldFail) {{
          fixed.push({{ ...test, previous_status: oldTest.status }});
        }} else if (isNewFail && wasOldFail) {{
          stillFailing.push(test);
        }}
      }});

      return {{ newFailures, fixed, stillFailing, newTests }};
    }}

    function renderCompareResults(olderMeta, newerMeta, comparison) {{
      const {{ newFailures, fixed, stillFailing, newTests }} = comparison;

      let html = `
        <div class="compare-summary">
          <div class="compare-stat">
            <div class="compare-stat-value new-fail">${{newFailures.length}}</div>
            <div class="compare-stat-label">New Failures</div>
          </div>
          <div class="compare-stat">
            <div class="compare-stat-value fixed">${{fixed.length}}</div>
            <div class="compare-stat-label">Fixed</div>
          </div>
          <div class="compare-stat">
            <div class="compare-stat-value unchanged">${{stillFailing.length}}</div>
            <div class="compare-stat-label">Still Failing</div>
          </div>
          <div class="compare-stat">
            <div class="compare-stat-value unchanged">${{newTests.length}}</div>
            <div class="compare-stat-label">New Tests</div>
          </div>
        </div>
        <p style="color: #6b7280; font-size: 0.875rem; margin-bottom: 1rem;">
          Comparing run #${{olderMeta.run_id.slice(-6)}} → #${{newerMeta.run_id.slice(-6)}}
        </p>
      `;

      if (newFailures.length > 0) {{
        html += `<div class="diff-category new-failures"><h4>🔴 New Failures (${{newFailures.length}})</h4><ul>`;
        newFailures.forEach(t => {{
          html += `<li><span class="test-name">${{t.name}}</span><span class="suite-tag">${{t.suite}}</span></li>`;
        }});
        html += `</ul></div>`;
      }}

      if (fixed.length > 0) {{
        html += `<div class="diff-category fixed"><h4>🟢 Fixed (${{fixed.length}})</h4><ul>`;
        fixed.forEach(t => {{
          html += `<li><span class="test-name">${{t.name}}</span><span class="suite-tag">${{t.suite}}</span></li>`;
        }});
        html += `</ul></div>`;
      }}

      if (stillFailing.length > 0) {{
        html += `<div class="diff-category still-failing"><h4>🟡 Still Failing (${{stillFailing.length}})</h4><ul>`;
        stillFailing.forEach(t => {{
          html += `<li><span class="test-name">${{t.name}}</span><span class="suite-tag">${{t.suite}}</span></li>`;
        }});
        html += `</ul></div>`;
      }}

      if (newFailures.length === 0 && fixed.length === 0 && stillFailing.length === 0) {{
        html += `<p style="text-align: center; color: #16a34a; padding: 2rem;">✓ No test status changes between these runs</p>`;
      }}

      return html;
    }}

    async function compareSelectedRuns(sectionId) {{
      const checkboxes = document.querySelectorAll('.' + sectionId + '-checkbox:checked');
      if (checkboxes.length !== 2) return;

      const resultsDiv = document.getElementById(sectionId + '-compare-results');
      const contentDiv = document.getElementById(sectionId + '-compare-content');

      if (!resultsDiv || !contentDiv) return;

      // Get run info from table rows
      const runs = Array.from(checkboxes).map(cb => {{
        const row = cb.closest('tr');
        return {{
          id: row.dataset.runId,
          date: row.dataset.runDate
        }};
      }});

      // Sort by run ID to determine older vs newer
      runs.sort((a, b) => a.id.localeCompare(b.id));
      const [older, newer] = runs;

      // Show loading state
      resultsDiv.style.display = 'block';
      contentDiv.innerHTML = '<div class="compare-loading">Loading run metadata...</div>';

      try {{
        const [olderMeta, newerMeta] = await Promise.all([
          fetchMetadata(older.id, older.date),
          fetchMetadata(newer.id, newer.date)
        ]);

        const comparison = compareTests(olderMeta, newerMeta);
        contentDiv.innerHTML = renderCompareResults(olderMeta, newerMeta, comparison);

        // Scroll to results
        resultsDiv.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
      }} catch (error) {{
        contentDiv.innerHTML = `<div class="compare-error">Error: ${{error.message}}</div>`;
      }}
    }}

    function closeCompareResults(sectionId) {{
      const resultsDiv = document.getElementById(sectionId + '-compare-results');
      if (resultsDiv) resultsDiv.style.display = 'none';
    }}
  </script>
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

{history_section}
{diff_section}

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

    # Contract test inputs
    parser.add_argument("--contract-allure-dir", help="Path to contract Allure report directory")
    parser.add_argument("--include-contract", action="store_true",
                        help="Always show contract card (even without local allure data)")
    parser.add_argument("--api-inventory-json", help="Path to api_inventory.json for endpoint coverage")

    # History and comparison inputs
    parser.add_argument("--history-json", help="Path to history.json for run history display")
    parser.add_argument("--comparison-json", help="Path to comparison.json for regression detection")

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

    contract_allure = Path(args.contract_allure_dir) if args.contract_allure_dir else None

    api_inventory = Path(args.api_inventory_json) if args.api_inventory_json else None

    if contract_allure or args.include_contract:
        contract = build_contract_metrics(allure_dir=contract_allure, api_inventory_json=api_inventory)
        metrics_list.append(contract)
        if contract.statistic.total > 0:
            print(f"Contract: {contract.statistic.passed}/{contract.statistic.total} tests, "
                  f"{contract.duration_sec}s duration")
        else:
            print("Contract: card added (run contract tests to see stats)")

    if not metrics_list:
        print("Error: No test results provided", file=sys.stderr)
        sys.exit(1)

    # Load history and comparison data if provided
    history = None
    comparison = None

    if args.history_json:
        history = load_history(Path(args.history_json))
        if history:
            print(f"History: {len(history.runs)} runs loaded")

    if args.comparison_json:
        comparison = load_comparison(Path(args.comparison_json))
        if comparison:
            print(f"Comparison: {comparison.status_change} "
                  f"({comparison.summary.get('new_failures', 0)} new failures, "
                  f"{comparison.summary.get('fixed', 0)} fixed)")

    # Build config
    config = DashboardConfig(
        commit_sha=args.commit_sha,
        run_id=args.run_id,
    )

    # Generate HTML
    html = generate_dashboard_html(metrics_list, config, history, comparison)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)

    print(f"Dashboard generated: {output_path}")


if __name__ == "__main__":
    main()

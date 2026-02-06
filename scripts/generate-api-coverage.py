#!/usr/bin/env python3
"""
Generate API Coverage HTML page from api_inventory.json.

Reads the API inventory and generates a standalone HTML page showing
every endpoint, its client method, contract tests, and coverage status.

Usage:
    python scripts/generate-api-coverage.py \
        --inventory backend/api_inventory.json \
        --output /tmp/api-coverage/index.html \
        --commit-sha abc1234 \
        --run-id 12345
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


def extract_api_area(path: str) -> str:
    """Extract API area from path prefix (e.g., /api/admin/players -> admin)."""
    parts = path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "api":
        return parts[1]
    return "other"


STATUS_COLORS: dict[str, tuple[str, str, str]] = {
    "fully_covered": ("#dcfce7", "#166534", "Fully Covered"),
    "client_only": ("#fef9c3", "#854d0e", "Client Only"),
    "missing_client": ("#fef2f2", "#991b1b", "Missing Client"),
}


def status_color(status: str) -> tuple[str, str, str]:
    """Return (bg_color, text_color, label) for a coverage status."""
    return STATUS_COLORS.get(status, ("#f3f4f6", "#6b7280", status))


def generate_html(inventory: dict, commit_sha: str, run_id: str) -> str:
    """Generate the complete API coverage HTML page."""
    summary = inventory.get("summary", {})
    endpoints = inventory.get("endpoints", [])
    excluded = inventory.get("excluded_endpoints", [])

    total = summary.get("total_endpoints", 0)
    with_client = summary.get("with_client_method", 0)
    with_tests = summary.get("with_tests", 0)
    excluded_count = summary.get("excluded", 0)

    coverage_pct = (with_client / total * 100) if total > 0 else 0

    # Count by status
    status_counts = summary.get("coverage_status", {})
    fully_covered = status_counts.get("fully_covered", 0)
    client_only = status_counts.get("client_only", 0)
    missing_client = status_counts.get("missing_client", 0)

    # Group endpoints by API area
    areas: dict[str, list[dict]] = defaultdict(list)
    for ep in endpoints:
        area = extract_api_area(ep["path"])
        areas[area] = areas.get(area, [])
        areas[area].append(ep)

    # Sort areas alphabetically, endpoints by path within each area
    sorted_areas = sorted(areas.keys())

    # Generate endpoint rows
    endpoint_rows = []
    for area in sorted_areas:
        area_endpoints = sorted(areas[area], key=lambda e: (e["path"], e["method"]))
        endpoint_rows.append(
            f'<tr class="area-header"><td colspan="5">{area.upper()}</td></tr>'
        )
        for ep in area_endpoints:
            bg, text_color, label = status_color(ep.get("coverage_status", "unknown"))
            method = ep["method"]
            path = ep["path"]
            client_method = ep.get("client_method", "-")
            tests = ep.get("tests", [])
            contract_tests = [t for t in tests if t.get("type") == "contract"]
            test_names = ", ".join(t["test_name"] for t in contract_tests) if contract_tests else "-"

            method_class = method.lower()

            test_count = len(contract_tests)
            test_suffix = "s" if test_count != 1 else ""
            endpoint_rows.append(f'''
        <tr>
          <td><span class="method-badge method-{method_class}">{method}</span></td>
          <td class="path-cell"><code>{path}</code></td>
          <td><code>{client_method}</code></td>
          <td class="tests-cell" title="{test_names}">{test_count} test{test_suffix}</td>
          <td><span class="status-pill" style="background:{bg};color:{text_color};">{label}</span></td>
        </tr>''')

    rows_html = "\n".join(endpoint_rows)

    # Generate excluded rows
    excluded_rows = []
    for ep in excluded:
        excluded_rows.append(f'''
        <tr>
          <td><span class="method-badge method-{ep["method"].lower()}">{ep["method"]}</span></td>
          <td><code>{ep["path"]}</code></td>
          <td>{ep.get("reason", "-")}</td>
        </tr>''')
    excluded_html = "\n".join(excluded_rows)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    commit_short = commit_sha[:7] if len(commit_sha) >= 7 else commit_sha

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🔍</text></svg>">
  <title>API Coverage - Missing Table</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      background-color: #f3f4f6;
      min-height: 100vh;
    }}
    .container {{ max-width: 1280px; margin: 0 auto; padding: 2rem 1rem; }}
    .header {{ text-align: center; margin-bottom: 2rem; }}
    .header h1 {{ font-size: 2rem; font-weight: 700; color: #2563eb; margin-bottom: 0.5rem; }}
    .header p {{ font-size: 1rem; color: #4b5563; }}

    /* Summary section */
    .summary {{
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }}
    .summary-stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 1rem;
      margin-bottom: 1.25rem;
    }}
    .summary-stat {{
      text-align: center;
      padding: 0.75rem;
      background: #f9fafb;
      border-radius: 0.375rem;
    }}
    .summary-stat-value {{ font-size: 1.5rem; font-weight: 700; color: #1f2937; }}
    .summary-stat-value-small {{ font-size: 0.875rem; font-weight: 400; color: #6b7280; }}
    .summary-stat-label {{ font-size: 0.7rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }}

    /* Progress bar */
    .progress-bar {{
      height: 0.5rem;
      background: #e5e7eb;
      border-radius: 0.25rem;
      overflow: hidden;
    }}
    .progress-fill {{
      height: 100%;
      border-radius: 0.25rem;
      transition: width 0.3s;
    }}
    .progress-fill.green {{ background: #22c55e; }}
    .progress-fill.yellow {{ background: #f59e0b; }}
    .progress-fill.red {{ background: #ef4444; }}

    /* Breakdown */
    .breakdown {{
      display: flex;
      gap: 1.5rem;
      margin-top: 1rem;
      flex-wrap: wrap;
    }}
    .breakdown-item {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.875rem;
      color: #4b5563;
    }}
    .breakdown-dot {{
      width: 0.75rem;
      height: 0.75rem;
      border-radius: 50%;
    }}

    /* Endpoints table */
    .endpoints-section {{
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }}
    .endpoints-section h2 {{ font-size: 1.125rem; font-weight: 600; color: #1f2937; margin-bottom: 1rem; }}
    .table-wrapper {{ overflow-x: auto; }}
    .endpoints-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
    .endpoints-table th, .endpoints-table td {{
      padding: 0.5rem 0.75rem;
      text-align: left;
      border-bottom: 1px solid #e5e7eb;
      white-space: nowrap;
    }}
    .endpoints-table td:nth-child(3) {{ white-space: normal; }}
    .endpoints-table th {{
      background: #f9fafb;
      font-weight: 600;
      color: #4b5563;
      font-size: 0.75rem;
      text-transform: uppercase;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    .endpoints-table tr:hover {{ background: #f9fafb; }}
    .endpoints-table code {{ background: #f3f4f6; padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-size: 0.8rem; }}
    .path-cell {{ white-space: nowrap; }}
    .tests-cell {{ text-align: center; }}

    /* Area header rows */
    .area-header td {{
      background: #eff6ff;
      font-weight: 600;
      color: #1e40af;
      font-size: 0.75rem;
      letter-spacing: 0.05em;
      padding: 0.375rem 0.75rem;
      border-bottom: 2px solid #bfdbfe;
    }}

    /* Method badges */
    .method-badge {{
      display: inline-block;
      padding: 0.125rem 0.5rem;
      border-radius: 0.25rem;
      font-size: 0.7rem;
      font-weight: 600;
      font-family: monospace;
      min-width: 3.5rem;
      text-align: center;
    }}
    .method-get {{ background: #dcfce7; color: #166534; }}
    .method-post {{ background: #dbeafe; color: #1e40af; }}
    .method-put {{ background: #fef9c3; color: #854d0e; }}
    .method-patch {{ background: #fef9c3; color: #854d0e; }}
    .method-delete {{ background: #fef2f2; color: #991b1b; }}

    /* Status pill */
    .status-pill {{
      display: inline-block;
      padding: 0.125rem 0.5rem;
      border-radius: 1rem;
      font-size: 0.75rem;
      font-weight: 500;
      white-space: nowrap;
    }}

    /* Excluded section */
    .excluded-section {{
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }}
    .excluded-section h2 {{ font-size: 1rem; font-weight: 600; color: #6b7280; margin-bottom: 1rem; }}
    .excluded-table {{ width: 100%; border-collapse: collapse; font-size: 0.8125rem; color: #6b7280; }}
    .excluded-table th, .excluded-table td {{
      padding: 0.375rem 0.75rem;
      text-align: left;
      border-bottom: 1px solid #e5e7eb;
    }}
    .excluded-table th {{
      background: #f9fafb;
      font-weight: 600;
      font-size: 0.7rem;
      text-transform: uppercase;
    }}

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
      <h1>API Coverage</h1>
      <p>Endpoint coverage analysis for Missing Table API</p>
    </div>

    <div class="summary">
      <div class="summary-stats">
        <div class="summary-stat">
          <div class="summary-stat-value">{with_client}<span class="summary-stat-value-small">/{total}</span></div>
          <div class="summary-stat-label">Endpoints Covered</div>
        </div>
        <div class="summary-stat">
          <div class="summary-stat-value">{coverage_pct:.1f}<span class="summary-stat-value-small">%</span></div>
          <div class="summary-stat-label">Coverage</div>
        </div>
        <div class="summary-stat">
          <div class="summary-stat-value">{with_tests}</div>
          <div class="summary-stat-label">With Tests</div>
        </div>
        <div class="summary-stat">
          <div class="summary-stat-value">{excluded_count}</div>
          <div class="summary-stat-label">Excluded</div>
        </div>
      </div>

      <div class="progress-bar">
        <div class="progress-fill {"green" if coverage_pct >= 90 else "yellow" if coverage_pct >= 70 else "red"}" style="width: {coverage_pct:.1f}%;"></div>
      </div>

      <div class="breakdown">
        <div class="breakdown-item">
          <div class="breakdown-dot" style="background: #22c55e;"></div>
          <span>Fully Covered: {fully_covered}</span>
        </div>
        <div class="breakdown-item">
          <div class="breakdown-dot" style="background: #f59e0b;"></div>
          <span>Client Only: {client_only}</span>
        </div>
        <div class="breakdown-item">
          <div class="breakdown-dot" style="background: #ef4444;"></div>
          <span>Missing Client: {missing_client}</span>
        </div>
      </div>
    </div>

    <div class="endpoints-section">
      <h2>Endpoints ({len(endpoints)})</h2>
      <div class="table-wrapper">
        <table class="endpoints-table">
          <thead>
            <tr>
              <th>Method</th>
              <th>Path</th>
              <th>Client Method</th>
              <th>Contract Tests</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
{rows_html}
          </tbody>
        </table>
      </div>
    </div>

    {"" if not excluded else f"""
    <div class="excluded-section">
      <h2>Excluded Endpoints ({excluded_count})</h2>
      <table class="excluded-table">
        <thead>
          <tr>
            <th>Method</th>
            <th>Path</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
{excluded_html}
        </tbody>
      </table>
    </div>
    """}

    <div class="meta-section">
      <p><strong>Generated:</strong> {timestamp}</p>
      <p><strong>Commit:</strong> <a href="https://github.com/silverbeer/missing-table/commit/{commit_sha}">{commit_short}</a></p>
      <p><strong>Run:</strong> <a href="https://github.com/silverbeer/missing-table/actions/runs/{run_id}">#{run_id}</a></p>
    </div>
  </div>
</body>
</html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate API Coverage HTML page")
    parser.add_argument("--inventory", required=True, help="Path to api_inventory.json")
    parser.add_argument("--output", "-o", required=True, help="Output HTML file path")
    parser.add_argument("--commit-sha", required=True, help="Git commit SHA")
    parser.add_argument("--run-id", required=True, help="GitHub Actions run ID")

    args = parser.parse_args()

    inventory_path = Path(args.inventory)
    if not inventory_path.exists():
        print(f"Error: {inventory_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(inventory_path) as f:
        inventory = json.load(f)

    html = generate_html(inventory, args.commit_sha, args.run_id)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)

    summary = inventory.get("summary", {})
    total = summary.get("total_endpoints", 0)
    with_client = summary.get("with_client_method", 0)
    print(f"API Coverage page generated: {output_path}")
    print(f"  {with_client}/{total} endpoints covered")


if __name__ == "__main__":
    main()

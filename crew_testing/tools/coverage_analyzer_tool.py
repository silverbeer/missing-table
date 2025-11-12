"""
Coverage Analyzer Tool - Measure test coverage for Python modules

This tool analyzes test coverage to identify which lines of code
are executed by tests and which are not.

Features:
- Read .coverage data files
- Analyze coverage for specific modules
- Report executed vs missing lines
- Calculate coverage percentage
- Identify uncovered code sections

Used by Inspector agent to prioritize testing gaps.
"""

import os
from pathlib import Path
from typing import Dict, List, Any
from crewai.tools import BaseTool

try:
    from coverage import Coverage
    from coverage.results import Analysis
    COVERAGE_AVAILABLE = True
except ImportError:
    COVERAGE_AVAILABLE = False


class CoverageAnalyzerTool(BaseTool):
    """Analyzes test coverage for Python modules"""

    name: str = "analyze_coverage"
    description: str = """
    Analyzes test coverage for a Python module to identify tested and untested code.

    Provides:
    - Overall coverage percentage
    - List of executed lines
    - List of missing (untested) lines
    - Branch coverage information
    - Uncovered code sections

    Input: module_path (str) - Path to Python module to analyze
    Output: Detailed coverage report in markdown

    Note: Requires pytest coverage data (.coverage file) to exist.
    Run 'pytest --cov=backend --cov-report=term' first to generate coverage data.
    """

    def _run(self, module_path: str) -> str:
        """
        Analyze test coverage for Python module

        Args:
            module_path: Path to Python module to analyze

        Returns:
            Markdown-formatted coverage report
        """
        if not COVERAGE_AVAILABLE:
            return "❌ Error: coverage library not installed. Run 'uv add coverage' to install."

        try:
            # Resolve paths
            project_root = Path(__file__).parent.parent.parent

            if not os.path.isabs(module_path):
                full_module_path = project_root / module_path
            else:
                full_module_path = Path(module_path)

            if not full_module_path.exists():
                return f"❌ Error: Module not found: {module_path}"

            # Look for .coverage file
            coverage_file = project_root / ".coverage"
            backend_coverage_file = project_root / "backend" / ".coverage"

            if backend_coverage_file.exists():
                coverage_data_file = backend_coverage_file
            elif coverage_file.exists():
                coverage_data_file = coverage_file
            else:
                return (
                    "❌ Error: No coverage data found (.coverage file missing).\n\n"
                    "Run tests with coverage first:\n"
                    "```bash\n"
                    "cd backend && uv run pytest --cov=backend --cov-report=term\n"
                    "```"
                )

            # Load coverage data
            cov = Coverage(data_file=str(coverage_data_file))
            cov.load()

            # Get analysis for the module
            try:
                analysis = cov.analysis2(str(full_module_path))
            except Exception as e:
                return (
                    f"❌ Error: Could not analyze coverage for {module_path}\n\n"
                    f"Details: {str(e)}\n\n"
                    "Make sure the module was included in the coverage run."
                )

            # Generate report
            return self._generate_coverage_report(module_path, full_module_path, analysis, cov)

        except Exception as e:
            return f"❌ Error analyzing coverage: {str(e)}\n{type(e).__name__}"

    def _generate_coverage_report(
        self,
        module_path: str,
        full_module_path: Path,
        analysis: tuple,
        cov: Coverage
    ) -> str:
        """Generate markdown coverage report"""

        # Unpack analysis results
        # analysis is a tuple: (filename, executed_lines, excluded_lines, missing_lines)
        filename, executed_lines, excluded_lines, missing_lines = analysis

        # Read source code for context
        try:
            with open(full_module_path, 'r', encoding='utf-8') as f:
                source_lines = f.readlines()
        except Exception:
            source_lines = []

        total_lines = len(source_lines)
        executable_lines = len(executed_lines) + len(missing_lines)
        coverage_pct = (len(executed_lines) / executable_lines * 100) if executable_lines > 0 else 0

        # Build report
        report = f"""
📊 Coverage Analysis Report

**File:** `{module_path}`
**Total Lines:** {total_lines}
**Executable Lines:** {executable_lines}
**Executed Lines:** {len(executed_lines)}
**Missing Lines:** {len(missing_lines)}
**Coverage:** {coverage_pct:.1f}%

---

"""

        # Coverage status
        if coverage_pct >= 80:
            report += "✅ **Status:** GOOD - Coverage is above 80%\n\n"
        elif coverage_pct >= 50:
            report += "⚠️ **Status:** MODERATE - Coverage is below 80%\n\n"
        else:
            report += "❌ **Status:** LOW - Coverage is below 50%\n\n"

        report += "---\n\n"

        # Missing lines breakdown
        if missing_lines:
            report += f"## 🔴 Untested Code ({len(missing_lines)} lines)\n\n"

            # Group consecutive lines into ranges
            missing_ranges = self._group_line_ranges(missing_lines)

            report += "**Missing Line Ranges:**\n"
            for start, end in missing_ranges:
                if start == end:
                    report += f"- Line {start}\n"
                else:
                    report += f"- Lines {start}-{end}\n"

            report += "\n"

            # Show code snippets for uncovered sections (first 5 ranges)
            report += "**Untested Code Snippets:**\n\n"
            for i, (start, end) in enumerate(missing_ranges[:5]):
                if source_lines:
                    snippet_start = max(0, start - 1)  # 0-indexed
                    snippet_end = min(len(source_lines), end)
                    snippet = ''.join(source_lines[snippet_start:snippet_end])

                    report += f"**Lines {start}-{end}:**\n```python\n{snippet}```\n\n"

                if i >= 4 and len(missing_ranges) > 5:
                    report += f"... and {len(missing_ranges) - 5} more untested sections\n\n"
                    break

            report += "---\n\n"

        # Executed lines summary
        if executed_lines:
            report += f"## ✅ Tested Code ({len(executed_lines)} lines)\n\n"

            executed_ranges = self._group_line_ranges(executed_lines)
            report += "**Covered Line Ranges:**\n"
            for start, end in executed_ranges[:10]:
                if start == end:
                    report += f"- Line {start}\n"
                else:
                    report += f"- Lines {start}-{end}\n"

            if len(executed_ranges) > 10:
                report += f"- ... and {len(executed_ranges) - 10} more covered sections\n"

            report += "\n---\n\n"

        # Priority recommendations
        report += "## 🎯 Testing Priorities\n\n"

        if coverage_pct < 50:
            report += "**HIGH PRIORITY:** Coverage is critically low. Focus on:\n"
            report += "1. Core functionality and critical paths\n"
            report += "2. Error handling and edge cases\n"
            report += "3. Public API methods and functions\n"
        elif coverage_pct < 80:
            report += "**MEDIUM PRIORITY:** Coverage needs improvement. Focus on:\n"
            report += "1. Untested error handling paths\n"
            report += "2. Edge cases and boundary conditions\n"
            report += "3. Complex logic and branching\n"
        else:
            report += "**LOW PRIORITY:** Good coverage. Consider:\n"
            report += "1. Remaining edge cases\n"
            report += "2. Error scenarios\n"
            report += "3. Integration testing\n"

        report += "\n---\n\n✅ Coverage analysis complete! Ready for gap prioritization.\n"

        return report

    def _group_line_ranges(self, lines: List[int]) -> List[tuple]:
        """Group consecutive line numbers into ranges"""
        if not lines:
            return []

        sorted_lines = sorted(lines)
        ranges = []
        start = sorted_lines[0]
        end = sorted_lines[0]

        for line in sorted_lines[1:]:
            if line == end + 1:
                end = line
            else:
                ranges.append((start, end))
                start = line
                end = line

        ranges.append((start, end))
        return ranges


# Export tool
__all__ = ["CoverageAnalyzerTool"]

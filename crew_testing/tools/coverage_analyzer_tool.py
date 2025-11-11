"""
Coverage Analyzer Tool - Read pytest coverage reports and identify gaps

This tool reads pytest coverage data to identify which lines of code
are covered by tests and which lines need test coverage.
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any
from crewai.tools import BaseTool


class CoverageAnalyzerTool(BaseTool):
    """Reads pytest coverage reports and identifies testing gaps"""

    name: str = "analyze_coverage"
    description: str = """
    Analyzes pytest coverage data for a specific module to identify:
    - Total statements (lines of code)
    - Covered statements (lines executed by tests)
    - Uncovered statements (lines not executed)
    - Coverage percentage
    - Specific uncovered line numbers
    - Missing test scenarios

    Input: module_path (str) - Path to Python module to analyze
    Output: Markdown report with coverage gaps
    """

    def _run(self, module_path: str) -> str:
        """
        Analyze coverage for a Python module

        Args:
            module_path: Path to Python module (e.g., "backend/dao/enhanced_data_access_fixed.py")

        Returns:
            Markdown-formatted coverage gap report
        """
        try:
            # Resolve paths
            project_root = Path(__file__).parent.parent.parent

            if not os.path.isabs(module_path):
                full_module_path = project_root / module_path
            else:
                full_module_path = Path(module_path)

            if not full_module_path.exists():
                return f"❌ Error: Module not found: {module_path}"

            # Check if .coverage file exists
            coverage_file = project_root / ".coverage"
            if not coverage_file.exists():
                return self._no_coverage_report(module_path)

            # Get coverage data using coverage.py
            try:
                # Import coverage module
                import coverage

                # Load coverage data
                cov = coverage.Coverage(data_file=str(coverage_file))
                cov.load()

                # Get analysis for this file
                file_path_str = str(full_module_path)
                try:
                    analysis = cov.analysis2(file_path_str)
                except Exception:
                    # Try relative path
                    try:
                        rel_path = str(full_module_path.relative_to(project_root))
                        analysis = cov.analysis2(rel_path)
                    except Exception:
                        return self._no_coverage_for_module(module_path)

                # Extract coverage data
                # analysis = (filename, executed_lines, excluded_lines, missing_lines)
                filename, executed, excluded, missing = analysis

                # Calculate statistics
                total_statements = len(executed) + len(missing)
                covered_statements = len(executed)
                coverage_pct = (covered_statements / total_statements * 100) if total_statements > 0 else 0

                return self._generate_coverage_report(
                    module_path=module_path,
                    total_statements=total_statements,
                    covered_statements=covered_statements,
                    coverage_pct=coverage_pct,
                    executed_lines=executed,
                    missing_lines=missing,
                    excluded_lines=excluded,
                )

            except ImportError:
                return "❌ Error: 'coverage' package not installed. Run: pip install coverage"

        except Exception as e:
            return f"❌ Error analyzing coverage: {str(e)}\n{type(e).__name__}"

    def _no_coverage_report(self, module_path: str) -> str:
        """Generate report when no coverage data exists"""
        return f"""
⚠️ No Coverage Data Available

**Module:** `{module_path}`

**Issue:** No `.coverage` file found in project root.

**Solution:** Run pytest with coverage first:

```bash
cd backend && pytest --cov={module_path} --cov-report=term
```

**Then re-run this analysis.**

---

**Current Coverage:** Unknown (no data)
**Testable:** ✅ (ready for unit test generation)
"""

    def _no_coverage_for_module(self, module_path: str) -> str:
        """Generate report when module not in coverage data"""
        return f"""
⚠️ Module Not in Coverage Report

**Module:** `{module_path}`

**Issue:** Module not found in existing coverage data.

**Possible Reasons:**
1. No tests have imported this module yet
2. Module path is incorrect
3. Module is in a directory not covered by tests

**Current Coverage:** 0% (not tested)
**Status:** ✅ High priority for unit test generation

**Recommendation:** Generate unit tests for this module to establish baseline coverage.
"""

    def _generate_coverage_report(
        self,
        module_path: str,
        total_statements: int,
        covered_statements: int,
        coverage_pct: float,
        executed_lines: List[int],
        missing_lines: List[int],
        excluded_lines: List[int],
    ) -> str:
        """Generate detailed coverage report"""

        # Determine priority based on coverage %
        if coverage_pct >= 80:
            priority = "🟢 LOW"
            status = "Well tested"
        elif coverage_pct >= 50:
            priority = "🟡 MEDIUM"
            status = "Needs improvement"
        elif coverage_pct >= 20:
            priority = "🟠 HIGH"
            status = "Poorly tested"
        else:
            priority = "🔴 CRITICAL"
            status = "Untested"

        report = f"""
📊 Coverage Analysis Report

**Module:** `{module_path}`
**Status:** {status}
**Priority:** {priority}

---

## Coverage Statistics

| Metric | Value |
|--------|-------|
| **Total Statements** | {total_statements} |
| **Covered** | {covered_statements} ({coverage_pct:.1f}%) |
| **Missing** | {len(missing_lines)} ({100 - coverage_pct:.1f}%) |
| **Excluded** | {len(excluded_lines)} |

"""

        # Coverage bar
        covered_bars = int(coverage_pct / 5)
        uncovered_bars = 20 - covered_bars
        bar = "█" * covered_bars + "░" * uncovered_bars
        report += f"**Coverage:** {bar} {coverage_pct:.1f}%\n\n"

        # Missing lines summary
        if missing_lines:
            report += "---\n\n## 🔴 Uncovered Lines\n\n"

            # Group consecutive lines into ranges
            ranges = self._group_line_ranges(missing_lines)

            report += f"**Total:** {len(missing_lines)} lines\n\n"
            report += "**Line Ranges:**\n"

            for start, end in ranges[:20]:  # Show first 20 ranges
                if start == end:
                    report += f"- Line {start}\n"
                else:
                    report += f"- Lines {start}-{end} ({end - start + 1} lines)\n"

            if len(ranges) > 20:
                report += f"\n... and {len(ranges) - 20} more ranges\n"

        # Recommendations
        report += "\n---\n\n## 💡 Recommendations\n\n"

        if coverage_pct == 0:
            report += """
**Zero Coverage - Start Fresh:**
1. Generate comprehensive unit tests from scratch
2. Target 80%+ coverage
3. Focus on all public functions/methods
4. Mock all external dependencies

**Estimated Tests Needed:** Based on module size
"""
        elif coverage_pct < 50:
            report += f"""
**Low Coverage - Significant Gaps:**
1. Generate unit tests for uncovered functions
2. Target coverage increase: {coverage_pct:.1f}% → 80% (+{80 - coverage_pct:.1f}%)
3. Prioritize high-complexity uncovered functions
4. Review existing tests for completeness

**Estimated Tests Needed:** ~{len(missing_lines) // 5} tests
"""
        elif coverage_pct < 80:
            report += f"""
**Moderate Coverage - Fill Remaining Gaps:**
1. Identify uncovered edge cases
2. Target coverage increase: {coverage_pct:.1f}% → 80% (+{80 - coverage_pct:.1f}%)
3. Add error handling tests
4. Test boundary conditions

**Estimated Tests Needed:** ~{len(missing_lines) // 8} tests
"""
        else:
            report += f"""
**High Coverage - Polish Remaining Gaps:**
1. Test remaining edge cases: {100 - coverage_pct:.1f}% uncovered
2. Add integration tests if needed
3. Review for flaky tests
4. Consider property-based testing

**Estimated Tests Needed:** ~{len(missing_lines) // 10} tests
"""

        # Next steps
        report += f"""
---

## 🎯 Next Steps

1. **Run Code Analysis:** Use `analyze_code` tool to identify functions
2. **Generate Gap Report:** Use `generate_gap_report` tool to prioritize
3. **Design Test Scenarios:** Architect agent designs unit tests
4. **Generate Tests:** Forge agent creates pytest code
5. **Measure Improvement:** Re-run coverage after test generation

---

✅ Coverage analysis complete! Ready for gap prioritization.
"""

        return report

    def _group_line_ranges(self, lines: List[int]) -> List[tuple]:
        """Group consecutive lines into ranges"""
        if not lines:
            return []

        sorted_lines = sorted(lines)
        ranges = []
        start = sorted_lines[0]
        end = sorted_lines[0]

        for line in sorted_lines[1:]:
            if line == end + 1:
                # Consecutive line
                end = line
            else:
                # Gap - save current range and start new one
                ranges.append((start, end))
                start = line
                end = line

        # Don't forget the last range
        ranges.append((start, end))

        return ranges


class CoverageRunnerTool(BaseTool):
    """Runs pytest with coverage for a module (convenience tool)"""

    name: str = "run_coverage"
    description: str = """
    Runs pytest with coverage measurement for a specific module.
    Useful when coverage data doesn't exist yet.

    Input: module_path (str) - Path to module to measure coverage
    Output: Coverage run results
    """

    def _run(self, module_path: str) -> str:
        """Run pytest with coverage"""
        try:
            project_root = Path(__file__).parent.parent.parent
            backend_dir = project_root / "backend"

            # Build pytest command
            cmd = [
                "pytest",
                "--cov=" + module_path,
                "--cov-report=term",
                "--cov-report=html",
                "-v",
            ]

            # Run pytest
            result = subprocess.run(
                cmd,
                cwd=str(backend_dir),
                capture_output=True,
                text=True,
                timeout=60,
            )

            output = f"**Exit Code:** {result.returncode}\n\n"

            if result.returncode == 0:
                output += "✅ Coverage measurement complete!\n\n"
            else:
                output += "⚠️ Some tests failed, but coverage was measured.\n\n"

            output += "**Coverage Output:**\n```\n"
            output += result.stdout
            output += "\n```\n"

            if result.stderr:
                output += "\n**Errors/Warnings:**\n```\n"
                output += result.stderr
                output += "\n```\n"

            return output

        except subprocess.TimeoutExpired:
            return "❌ Error: Coverage run timed out (60s)"
        except Exception as e:
            return f"❌ Error running coverage: {str(e)}"

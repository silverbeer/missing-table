"""
Pytest Runner Tool

Executes pytest tests and collects results:
- Run tests with coverage
- Parse pytest output
- Extract pass/fail counts
- Calculate coverage percentage
- Identify failed tests

Used by Flash agent to execute generated tests and report results.
"""

import subprocess
import re
from typing import Dict, Any
from crewai.tools import BaseTool
from pathlib import Path


class PytestRunnerTool(BaseTool):
    """Tool to execute pytest tests and collect results"""

    name: str = "run_pytest"
    description: str = (
        "Executes pytest tests with coverage tracking. "
        "Runs specified test files or entire test suite. "
        "Returns detailed results including pass/fail counts, coverage percentage, "
        "and information about failed tests."
    )

    def _run(self, test_path: str = "backend/tests", coverage: bool = True) -> str:
        """
        Run pytest tests

        Args:
            test_path: Path to test file or directory (default: backend/tests)
            coverage: Whether to run with coverage tracking (default: True)

        Returns:
            Formatted string with test results
        """
        try:
            # Build pytest command
            cmd = ["pytest", test_path, "-v"]

            if coverage:
                cmd.extend(["--cov=backend", "--cov-report=term-missing"])

            # Change to project root
            project_root = Path(__file__).parent.parent.parent

            # Run pytest
            result = subprocess.run(
                cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=60
            )

            # Parse output
            return self._parse_pytest_output(result.stdout, result.stderr, result.returncode)

        except subprocess.TimeoutExpired:
            return "❌ Error: Pytest execution timed out (>60 seconds)"
        except Exception as e:
            return f"❌ Error running pytest: {e}"

    def _parse_pytest_output(self, stdout: str, stderr: str, returncode: int) -> str:
        """Parse pytest output and extract key metrics"""
        output = []

        output.append("⚡ Flash: Test Execution Results\n")
        output.append("=" * 60)
        output.append("")

        # Extract test counts
        passed = failed = skipped = 0

        # Look for pytest summary line like: "5 passed, 2 failed, 1 skipped in 2.34s"
        summary_match = re.search(
            r'(\d+)\s+passed|(\d+)\s+failed|(\d+)\s+skipped',
            stdout,
            re.MULTILINE
        )

        if summary_match:
            # Extract individual counts
            passed_match = re.search(r'(\d+)\s+passed', stdout)
            failed_match = re.search(r'(\d+)\s+failed', stdout)
            skipped_match = re.search(r'(\d+)\s+skipped', stdout)

            if passed_match:
                passed = int(passed_match.group(1))
            if failed_match:
                failed = int(failed_match.group(1))
            if skipped_match:
                skipped = int(skipped_match.group(1))

        total = passed + failed + skipped

        # Test results
        output.append("📊 Test Results:")
        output.append(f"  Total:   {total}")
        output.append(f"  ✅ Passed:  {passed}")
        output.append(f"  ❌ Failed:  {failed}")
        output.append(f"  ⏭️  Skipped: {skipped}")

        if total > 0:
            pass_rate = (passed / total) * 100
            output.append(f"  📈 Pass Rate: {pass_rate:.1f}%")
        output.append("")

        # Extract coverage
        coverage_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', stdout)
        if coverage_match:
            coverage_pct = coverage_match.group(1)
            output.append(f"📊 Coverage: {coverage_pct}%")
            output.append("")

        # Extract failed tests
        if failed > 0:
            output.append("❌ Failed Tests:")
            failed_tests = re.findall(r'FAILED\s+(.+?)\s+-', stdout)
            for test in failed_tests[:10]:  # Limit to first 10
                output.append(f"  • {test}")
            if len(failed_tests) > 10:
                output.append(f"  ... and {len(failed_tests) - 10} more")
            output.append("")

        # Extract execution time
        time_match = re.search(r'in\s+([\d.]+)s', stdout)
        if time_match:
            duration = time_match.group(1)
            output.append(f"⏱️  Duration: {duration}s")
            output.append("")

        # Overall status
        output.append("=" * 60)
        if returncode == 0:
            output.append("✅ All tests passed!")
        elif failed > 0:
            output.append(f"⚠️  {failed} test(s) failed")
        else:
            output.append("⚠️  Tests completed with warnings")

        return "\n".join(output)


# Export for tool registration
__all__ = ["PytestRunnerTool"]

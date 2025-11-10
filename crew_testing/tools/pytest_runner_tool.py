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
            # pytest must run from backend directory (where pyproject.toml is)
            project_root = Path(__file__).parent.parent.parent
            backend_dir = project_root / "backend"

            # Adjust test path to be relative to backend directory
            # If path starts with "backend/", remove it
            if test_path.startswith("backend/"):
                test_path_relative = test_path[8:]  # Remove "backend/" prefix
            else:
                test_path_relative = test_path

            # Build pytest command using uv to ensure correct venv
            cmd = ["uv", "run", "pytest", test_path_relative, "-v"]

            if coverage:
                # Coverage path is now relative to backend
                cmd.extend(["--cov=.", "--cov-report=term-missing"])

            # Run pytest from backend directory
            result = subprocess.run(
                cmd,
                cwd=str(backend_dir),
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

        # Extract failed tests with detailed error information
        if failed > 0:
            output.append("❌ Failed Tests:")

            # Parse FAILURES section for detailed error info
            failures_section = re.search(r'=+\s*FAILURES\s*=+(.*?)(?:=+\s*|$)', stdout, re.DOTALL)
            if failures_section:
                failures_text = failures_section.group(1)

                # Split by test failure headers
                test_failures = re.split(r'_+\s+(\w+)\s+_+', failures_text)

                for i in range(1, len(test_failures), 2):
                    if i + 1 < len(test_failures):
                        test_name = test_failures[i]
                        failure_detail = test_failures[i + 1]

                        output.append(f"\n  Test: {test_name}")

                        # Extract assertion error
                        assert_match = re.search(r'(assert\s+.+?)(?:\n|$)', failure_detail, re.DOTALL)
                        if assert_match:
                            output.append(f"  Error: {assert_match.group(1).strip()}")

                        # Extract status code if 403/401
                        status_match = re.search(r'assert (\d+) == (\d+)', failure_detail)
                        if status_match:
                            actual = status_match.group(1)
                            expected = status_match.group(2)
                            output.append(f"  Expected status: {expected}, Got: {actual}")

                            if actual == "403":
                                output.append(f"  💡 Fix: Add authentication headers (403 Forbidden = missing auth)")
                            elif actual == "401":
                                output.append(f"  💡 Fix: Update or refresh authentication token (401 Unauthorized)")

                        # Limit output per test
                        if len(output) > 100:
                            output.append("\n  ... (truncated for brevity)")
                            break
            else:
                # Fallback to simple list
                failed_tests = re.findall(r'FAILED\s+(.+?)\s+-', stdout)
                for test in failed_tests[:10]:
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

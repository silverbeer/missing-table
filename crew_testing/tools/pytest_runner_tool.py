"""
Pytest Runner Tool

Executes pytest tests and collects results:
- Run tests with coverage (using run_tests.py like CI)
- Parse pytest output
- Extract pass/fail counts
- Calculate coverage percentage
- Identify failed tests
- Generate structured JSON reports

Used by Flash agent to execute generated tests and report results.
"""

import subprocess
import re
import json
from typing import Dict, Any
from crewai.tools import BaseTool
from pathlib import Path
from datetime import datetime


class PytestRunnerTool(BaseTool):
    """Tool to execute pytest tests and collect results"""

    name: str = "run_pytest"
    description: str = (
        "Executes pytest tests with coverage tracking using run_tests.py (same as CI). "
        "Supports test categories: unit, integration, contract, e2e, smoke, all. "
        "Generates structured JSON reports in crew_testing/reports/. "
        "Returns detailed results including pass/fail counts, coverage percentage, "
        "and information about failed tests."
    )

    def _run(
        self,
        test_path: str = None,
        category: str = None,
        coverage: bool = True
    ) -> str:
        """
        Run pytest tests using run_tests.py (same as CI)

        Args:
            test_path: Path to specific test file (optional)
            category: Test category (unit/integration/contract/e2e/smoke/all) (optional)
            coverage: Whether to run with coverage tracking (default: True)

        Returns:
            Formatted string with test results
        """
        try:
            # Setup paths
            project_root = Path(__file__).parent.parent.parent
            backend_dir = project_root / "backend"
            reports_dir = project_root / "crew_testing" / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)

            # Determine what to run
            if test_path:
                # Running specific test file - use pytest directly
                return self._run_specific_test(test_path, coverage, backend_dir, reports_dir)
            elif category:
                # Running test category - use run_tests.py like CI
                return self._run_category(category, coverage, backend_dir, reports_dir)
            else:
                # Default: run all tests using run_tests.py
                return self._run_category("all", coverage, backend_dir, reports_dir)

        except subprocess.TimeoutExpired:
            return "❌ Error: Pytest execution timed out (>120 seconds)"
        except Exception as e:
            return f"❌ Error running pytest: {e}"

    def _run_specific_test(
        self,
        test_path: str,
        coverage: bool,
        backend_dir: Path,
        reports_dir: Path
    ) -> str:
        """Run a specific test file using pytest directly"""
        # Adjust test path to be relative to backend directory
        if test_path.startswith("backend/"):
            test_path_relative = test_path[8:]
        else:
            test_path_relative = test_path

        # Build pytest command
        cmd = ["uv", "run", "pytest", test_path_relative, "-v"]

        if coverage:
            cmd.extend([
                "--cov=.",
                "--cov-report=term-missing",
                "--cov-report=json"
            ])

        # Run pytest
        result = subprocess.run(
            cmd,
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
            timeout=120
        )

        # Save structured report
        report_data = self._create_report_data(
            result.stdout,
            result.stderr,
            result.returncode,
            test_path=test_path_relative,
            category="specific"
        )
        self._save_report(report_data, reports_dir)

        # Parse and return output
        return self._parse_pytest_output(
            result.stdout,
            result.stderr,
            result.returncode,
            report_data
        )

    def _run_category(
        self,
        category: str,
        coverage: bool,
        backend_dir: Path,
        reports_dir: Path
    ) -> str:
        """Run test category using run_tests.py (same as CI)"""
        # Build run_tests.py command (same as CI)
        cmd = ["uv", "run", "python", "run_tests.py", "--category", category]

        if coverage:
            cmd.extend(["--xml-coverage", "--json-coverage"])

        # Run tests
        result = subprocess.run(
            cmd,
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
            timeout=120
        )

        # Save structured report
        report_data = self._create_report_data(
            result.stdout,
            result.stderr,
            result.returncode,
            category=category
        )
        self._save_report(report_data, reports_dir)

        # Parse and return output
        return self._parse_pytest_output(
            result.stdout,
            result.stderr,
            result.returncode,
            report_data
        )

    def _create_report_data(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
        test_path: str = None,
        category: str = None
    ) -> Dict[str, Any]:
        """Create structured report data"""
        # Extract test counts
        passed = failed = skipped = 0
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

        # Extract coverage
        coverage_pct = None
        coverage_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', stdout)
        if coverage_match:
            coverage_pct = int(coverage_match.group(1))

        # Extract execution time
        duration = None
        time_match = re.search(r'in\s+([\d.]+)s', stdout)
        if time_match:
            duration = float(time_match.group(1))

        # Extract failed tests
        failed_tests = []
        if failed > 0:
            failed_test_names = re.findall(r'FAILED\s+(.+?)\s+-', stdout)
            failed_tests = failed_test_names[:20]  # Limit to 20

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "test_path": test_path,
            "category": category,
            "results": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "pass_rate": (passed / total * 100) if total > 0 else 0
            },
            "coverage": {
                "percentage": coverage_pct
            } if coverage_pct else None,
            "duration_seconds": duration,
            "failed_tests": failed_tests,
            "exit_code": returncode,
            "success": returncode == 0
        }

    def _save_report(self, report_data: Dict[str, Any], reports_dir: Path) -> None:
        """Save structured report to JSON file"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        category = report_data.get("category", "unknown")
        report_file = reports_dir / f"test_run_{category}_{timestamp}.json"

        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)

        # Also save as latest for easy access
        latest_file = reports_dir / f"latest_{category}.json"
        with open(latest_file, 'w') as f:
            json.dump(report_data, f, indent=2)

    def _parse_pytest_output(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
        report_data: Dict[str, Any]
    ) -> str:
        """Parse pytest output and extract key metrics"""
        output = []

        output.append("⚡ Flash: Test Execution Results\n")
        output.append("=" * 60)
        output.append("")

        # Use report_data for consistent metrics
        results = report_data["results"]
        total = results["total"]
        passed = results["passed"]
        failed = results["failed"]
        skipped = results["skipped"]
        pass_rate = results["pass_rate"]

        # Show category/path
        if report_data.get("category"):
            output.append(f"📁 Category: {report_data['category']}")
        if report_data.get("test_path"):
            output.append(f"📄 Test Path: {report_data['test_path']}")
        if report_data.get("category") or report_data.get("test_path"):
            output.append("")

        # Test results
        output.append("📊 Test Results:")
        output.append(f"  Total:   {total}")
        output.append(f"  ✅ Passed:  {passed}")
        output.append(f"  ❌ Failed:  {failed}")
        output.append(f"  ⏭️  Skipped: {skipped}")
        output.append(f"  📈 Pass Rate: {pass_rate:.1f}%")
        output.append("")

        # Coverage
        if report_data.get("coverage"):
            coverage_pct = report_data["coverage"]["percentage"]
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

        # Execution time
        if report_data.get("duration_seconds"):
            duration = report_data["duration_seconds"]
            output.append(f"⏱️  Duration: {duration:.2f}s")
            output.append("")

        # Overall status
        output.append("=" * 60)
        if report_data["success"]:
            output.append("✅ All tests passed!")
        elif failed > 0:
            output.append(f"⚠️  {failed} test(s) failed")
        else:
            output.append("⚠️  Tests completed with warnings")

        output.append("")
        output.append(f"📄 Report saved: crew_testing/reports/latest_{report_data.get('category', 'unknown')}.json")

        return "\n".join(output)


# Export for tool registration
__all__ = ["PytestRunnerTool"]

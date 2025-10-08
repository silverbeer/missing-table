#!/usr/bin/env python3
"""
Test Pyramid Visualization Tool

Analyzes pytest results and displays test distribution across the test pyramid.
Shows total tests, pass/fail, and coverage at each pyramid level.

Usage:
    python test_pyramid.py                    # Run tests and show pyramid
    python test_pyramid.py --json            # Output JSON format
    python test_pyramid.py --no-run          # Use existing results
"""

import subprocess
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple
import re


class TestPyramid:
    """Test pyramid analyzer and visualizer."""

    PYRAMID_LEVELS = [
        ('e2e', 'E2E Tests', '🔺'),
        ('contract', 'Contract Tests', '🔶'),
        ('integration', 'Integration Tests', '🔷'),
        ('component', 'Component Tests', '🔸'),
        ('unit', 'Unit Tests', '🟦'),
    ]

    def __init__(self):
        self.results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'by_level': defaultdict(lambda: {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}),
            'by_stack': defaultdict(lambda: {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}),
            'by_module': defaultdict(lambda: {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}),
        }

    def run_tests(self) -> str:
        """Run pytest with markers and collect results."""
        print("🧪 Running tests and collecting markers...")

        # First, collect test items with markers
        collect_cmd = [
            'uv', 'run', 'pytest',
            '--collect-only',
            '-q',
            '--tb=no',
        ]

        collect_result = subprocess.run(collect_cmd, capture_output=True, text=True)
        self.parse_collection_output(collect_result.stdout)

        # Then run tests with JSON output
        cmd = [
            'uv', 'run', 'pytest',
            '--tb=short',
            '-v',
            '--json-report',
            '--json-report-file=/tmp/pytest_report.json',
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout

    def parse_collection_output(self, output: str):
        """Parse pytest collection output to extract test markers."""
        self.test_markers = {}
        current_test = None

        for line in output.split('\n'):
            # Look for test collection lines
            if '<Function' in line or '<Method' in line:
                # Extract test nodeid
                match = re.search(r'<Function (.+?)>', line)
                if not match:
                    match = re.search(r'<Method (.+?)>', line)
                if match:
                    current_test = match.group(1)
            # Look for marker lines
            elif current_test and '@pytest.mark' in line:
                marker = line.strip().split('.')[-1]
                if current_test not in self.test_markers:
                    self.test_markers[current_test] = []
                self.test_markers[current_test].append(marker)

    def parse_markers(self, test_item: dict) -> Tuple[str, str, str]:
        """Extract pyramid level, stack, and module from test path and name."""
        nodeid = test_item.get('nodeid', '')

        # Determine pyramid level from path patterns
        level = 'unit'  # Default
        if '/contract/' in nodeid or '_contract' in nodeid:
            level = 'contract'
        elif '_e2e' in nodeid or 'e2e' in nodeid.lower():
            level = 'e2e'
        elif '/integration/' in nodeid or 'test_dao' in nodeid or 'test_api' in nodeid:
            level = 'integration'
        elif 'component' in nodeid.lower():
            level = 'component'

        # Determine stack - always backend for now (no frontend tests)
        stack = 'backend'

        # Determine module from path/name
        module = 'other'
        if 'auth' in nodeid.lower():
            module = 'auth'
        elif 'dao' in nodeid.lower():
            module = 'dao'
        elif 'api' in nodeid.lower():
            module = 'api'
        elif 'invite' in nodeid.lower():
            module = 'invite'
        elif 'game' in nodeid.lower():
            module = 'games'
        elif 'standing' in nodeid.lower():
            module = 'standings'
        elif 'admin' in nodeid.lower():
            module = 'admin'

        return level, stack, module

    def analyze_json_report(self):
        """Analyze pytest JSON report."""
        report_file = Path('/tmp/pytest_report.json')
        if not report_file.exists():
            print("❌ No test report found. Run tests first.")
            return

        with open(report_file) as f:
            data = json.load(f)

        for test in data.get('tests', []):
            outcome = test.get('outcome', 'unknown')
            level, stack, module = self.parse_markers(test)

            # Update totals
            self.results['total'] += 1
            if outcome == 'passed':
                self.results['passed'] += 1
            elif outcome == 'failed':
                self.results['failed'] += 1
            elif outcome == 'skipped':
                self.results['skipped'] += 1

            # Update by level
            self.results['by_level'][level]['total'] += 1
            if outcome == 'passed':
                self.results['by_level'][level]['passed'] += 1
            elif outcome == 'failed':
                self.results['by_level'][level]['failed'] += 1
            elif outcome == 'skipped':
                self.results['by_level'][level]['skipped'] += 1

            # Update by stack
            self.results['by_stack'][stack]['total'] += 1
            if outcome == 'passed':
                self.results['by_stack'][stack]['passed'] += 1
            elif outcome == 'failed':
                self.results['by_stack'][stack]['failed'] += 1
            elif outcome == 'skipped':
                self.results['by_stack'][stack]['skipped'] += 1

            # Update by module
            self.results['by_module'][module]['total'] += 1
            if outcome == 'passed':
                self.results['by_module'][module]['passed'] += 1
            elif outcome == 'failed':
                self.results['by_module'][module]['failed'] += 1
            elif outcome == 'skipped':
                self.results['by_module'][module]['skipped'] += 1

    def draw_pyramid_bar(self, level: str, total: int, passed: int, failed: int, max_width: int = 50) -> str:
        """Draw a single pyramid bar with pass/fail visualization."""
        if total == 0:
            return "□" * 5

        # Calculate proportional widths
        width = min(int((total / max(1, max_width)) * 50), 50)
        if width == 0 and total > 0:
            width = 1

        # Calculate segments
        pass_width = int((passed / total) * width) if total > 0 else 0
        fail_width = int((failed / total) * width) if total > 0 else 0
        skip_width = width - pass_width - fail_width

        # Build bar
        bar = "✅" * pass_width + "❌" * fail_width + "⏭️" * skip_width
        return bar or "□"

    def visualize_pyramid(self):
        """Display the test pyramid visualization."""
        print("\n" + "="*80)
        print("🏔️  TEST PYRAMID VISUALIZATION")
        print("="*80 + "\n")

        # Find max total for scaling
        max_total = max([self.results['by_level'].get(lvl[0], {}).get('total', 0)
                        for lvl in self.PYRAMID_LEVELS], default=1)

        # Draw pyramid levels
        for marker, name, emoji in self.PYRAMID_LEVELS:
            stats = self.results['by_level'].get(marker, {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0})
            total = stats['total']
            passed = stats['passed']
            failed = stats['failed']
            skipped = stats['skipped']

            bar = self.draw_pyramid_bar(marker, total, passed, failed, max_total)

            # Calculate pass rate
            pass_rate = (passed / total * 100) if total > 0 else 0

            # Indent for pyramid shape (E2E at top is most indented)
            indent_level = [lvl[0] for lvl in self.PYRAMID_LEVELS].index(marker)
            indent = " " * (indent_level * 4)

            status = "✅" if failed == 0 and total > 0 else "❌" if failed > 0 else "⚪"

            print(f"{indent}{emoji} {name:20} {status}")
            print(f"{indent}   {bar}")
            print(f"{indent}   Total: {total:3} | ✅ {passed:3} | ❌ {failed:3} | ⏭️ {skipped:3} | {pass_rate:5.1f}% pass")
            print()

        # Summary
        print("="*80)
        print(f"📊 OVERALL: {self.results['total']} tests | "
              f"✅ {self.results['passed']} passed | "
              f"❌ {self.results['failed']} failed | "
              f"⏭️ {self.results['skipped']} skipped")
        pass_rate = (self.results['passed'] / self.results['total'] * 100) if self.results['total'] > 0 else 0
        print(f"   Pass Rate: {pass_rate:.1f}%")
        print("="*80 + "\n")

    def visualize_stack_distribution(self):
        """Show test distribution by stack."""
        print("📚 STACK DISTRIBUTION")
        print("-" * 80)

        for stack in ['backend', 'frontend']:
            stats = self.results['by_stack'].get(stack, {'total': 0, 'passed': 0, 'failed': 0})
            total = stats['total']
            passed = stats['passed']
            failed = stats['failed']

            bar = self.draw_pyramid_bar(stack, total, passed, failed, self.results['total'])
            pass_rate = (passed / total * 100) if total > 0 else 0

            icon = "🐍" if stack == 'backend' else "🎨"
            print(f"{icon} {stack.capitalize():12} | {bar}")
            print(f"   Total: {total:3} | ✅ {passed:3} | ❌ {failed:3} | {pass_rate:5.1f}% pass")
            print()

        print()

    def visualize_module_distribution(self):
        """Show test distribution by module."""
        print("🎯 MODULE DISTRIBUTION")
        print("-" * 80)

        # Sort modules by total tests (descending)
        sorted_modules = sorted(
            self.results['by_module'].items(),
            key=lambda x: x[1]['total'],
            reverse=True
        )

        for module, stats in sorted_modules:
            if stats['total'] == 0:
                continue

            total = stats['total']
            passed = stats['passed']
            failed = stats['failed']

            bar = self.draw_pyramid_bar(module, total, passed, failed, self.results['total'])
            pass_rate = (passed / total * 100) if total > 0 else 0

            print(f"  {module:12} | {bar}")
            print(f"   Total: {total:3} | ✅ {passed:3} | ❌ {failed:3} | {pass_rate:5.1f}% pass")
            print()

        print()

    def export_json(self):
        """Export results as JSON."""
        return json.dumps(self.results, indent=2)


def main():
    """Main entry point."""
    pyramid = TestPyramid()

    # Check arguments
    no_run = '--no-run' in sys.argv
    json_output = '--json' in sys.argv

    if not no_run:
        pyramid.run_tests()

    pyramid.analyze_json_report()

    if json_output:
        print(pyramid.export_json())
    else:
        pyramid.visualize_pyramid()
        pyramid.visualize_stack_distribution()
        pyramid.visualize_module_distribution()


if __name__ == '__main__':
    main()

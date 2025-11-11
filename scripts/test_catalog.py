#!/usr/bin/env python3
"""
Test Catalog Generator

Scans the test suite and generates a comprehensive catalog of all tests,
their markers, prerequisites, and metadata for CrewAI consumption.

Usage:
    python scripts/test_catalog.py                    # Generate catalog
    python scripts/test_catalog.py --output json      # JSON output
    python scripts/test_catalog.py --output table     # Table output
    python scripts/test_catalog.py --save catalog.json # Save to file
"""

import ast
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Set
from datetime import datetime
from collections import defaultdict


class TestCatalog:
    """Generates a catalog of all tests in the test suite."""

    def __init__(self, tests_dir: Path):
        self.tests_dir = tests_dir
        self.tests = []
        self.stats = defaultdict(int)

    def scan_test_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Scan a test file and extract test metadata."""
        tests = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                    test_info = self.extract_test_info(node, file_path)
                    tests.append(test_info)

        except Exception as e:
            print(f"Error scanning {file_path}: {e}")

        return tests

    def extract_test_info(self, node: ast.FunctionDef, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from a test function node."""
        # Get relative path from backend directory
        rel_path = file_path.relative_to(self.tests_dir.parent)

        # Extract markers from decorators
        markers = self.extract_markers(node)

        # Extract docstring
        docstring = ast.get_docstring(node) or ""

        # Determine test category from markers
        category = self.determine_category(markers)

        # Extract prerequisites
        prerequisites = self.extract_prerequisites(markers)

        # Determine owner (placeholder - could be extracted from comments or metadata)
        owner = "backend-team"

        # Extract fixture requirements
        fixtures = self.extract_fixtures(node)

        test_info = {
            "name": node.name,
            "full_name": f"{rel_path}::{node.name}",
            "file": str(rel_path),
            "line": node.lineno,
            "category": category,
            "markers": markers,
            "prerequisites": prerequisites,
            "fixtures": fixtures,
            "docstring": docstring.strip(),
            "owner": owner,
            "estimated_duration": self.estimate_duration(category),
            "coverage_threshold": self.get_coverage_threshold(category)
        }

        return test_info

    def extract_markers(self, node: ast.FunctionDef) -> List[str]:
        """Extract pytest markers from decorators."""
        markers = []

        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Attribute):
                # @pytest.mark.unit
                if isinstance(decorator.value, ast.Attribute):
                    if decorator.value.attr == 'mark':
                        markers.append(decorator.attr)
            elif isinstance(decorator, ast.Call):
                # @pytest.mark.parametrize(...)
                if isinstance(decorator.func, ast.Attribute):
                    if isinstance(decorator.func.value, ast.Attribute):
                        if decorator.func.value.attr == 'mark':
                            markers.append(decorator.func.attr)

        return markers

    def extract_fixtures(self, node: ast.FunctionDef) -> List[str]:
        """Extract fixture requirements from function arguments."""
        fixtures = []

        for arg in node.args.args:
            if arg.arg not in ['self', 'cls']:
                fixtures.append(arg.arg)

        return fixtures

    def extract_prerequisites(self, markers: List[str]) -> Dict[str, bool]:
        """Determine prerequisites based on markers."""
        prerequisites = {
            "database": False,
            "supabase": False,
            "redis": False,
            "authentication": False,
            "external_api": False,
            "rabbitmq": False
        }

        marker_set = set(markers)

        # Check for database-related markers
        if 'database' in marker_set or 'requires_supabase' in marker_set:
            prerequisites['database'] = True
            prerequisites['supabase'] = True

        if 'requires_redis' in marker_set:
            prerequisites['redis'] = True

        if 'auth' in marker_set:
            prerequisites['authentication'] = True

        if 'external' in marker_set:
            prerequisites['external_api'] = True

        return prerequisites

    def determine_category(self, markers: List[str]) -> str:
        """Determine primary test category from markers."""
        priority_order = ['smoke', 'unit', 'integration', 'contract', 'e2e']

        for category in priority_order:
            if category in markers:
                return category

        return 'uncategorized'

    def estimate_duration(self, category: str) -> str:
        """Estimate test duration based on category."""
        durations = {
            "unit": "<100ms",
            "integration": "<500ms",
            "contract": "<1s",
            "e2e": "<5s",
            "smoke": "<2s",
            "uncategorized": "unknown"
        }
        return durations.get(category, "unknown")

    def get_coverage_threshold(self, category: str) -> int:
        """Get coverage threshold for category."""
        thresholds = {
            "unit": 80,
            "integration": 70,
            "contract": 90,
            "e2e": 50,
            "smoke": 100,
            "uncategorized": 75
        }
        return thresholds.get(category, 75)

    def scan_all_tests(self) -> None:
        """Scan all test files in the tests directory."""
        test_files = list(self.tests_dir.rglob("test_*.py"))

        for test_file in test_files:
            tests = self.scan_test_file(test_file)
            self.tests.extend(tests)

            # Update stats
            for test in tests:
                self.stats[f"total_tests"] += 1
                self.stats[f"{test['category']}_tests"] += 1

    def generate_catalog(self) -> Dict[str, Any]:
        """Generate the complete test catalog."""
        catalog = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "tests_dir": str(self.tests_dir),
                "total_tests": len(self.tests),
                "version": "1.0.0"
            },
            "statistics": dict(self.stats),
            "tests": self.tests,
            "categories": self.get_category_breakdown(),
            "prerequisites": self.get_prerequisites_breakdown()
        }

        return catalog

    def get_category_breakdown(self) -> Dict[str, int]:
        """Get breakdown of tests by category."""
        breakdown = defaultdict(int)

        for test in self.tests:
            breakdown[test['category']] += 1

        return dict(breakdown)

    def get_prerequisites_breakdown(self) -> Dict[str, int]:
        """Get breakdown of tests by prerequisites."""
        breakdown = defaultdict(int)

        for test in self.tests:
            for prereq, required in test['prerequisites'].items():
                if required:
                    breakdown[prereq] += 1

        return dict(breakdown)

    def print_table(self) -> None:
        """Print test catalog as a table."""
        print("\n" + "="*100)
        print(" "*40 + "TEST CATALOG")
        print("="*100)

        print(f"\n📊 Statistics:")
        print(f"  Total tests: {len(self.tests)}")

        # Category breakdown
        category_breakdown = self.get_category_breakdown()
        print(f"\n📁 By Category:")
        for category, count in sorted(category_breakdown.items()):
            percentage = (count / len(self.tests)) * 100 if self.tests else 0
            print(f"  {category:15s}: {count:3d} ({percentage:5.1f}%)")

        # Prerequisites breakdown
        prereq_breakdown = self.get_prerequisites_breakdown()
        print(f"\n🔧 Prerequisites:")
        for prereq, count in sorted(prereq_breakdown.items()):
            print(f"  {prereq:20s}: {count:3d} tests")

        # Sample tests
        print(f"\n📝 Sample Tests (first 10):")
        print(f"  {'Name':<50s} {'Category':<15s} {'File':<50s}")
        print(f"  {'-'*115}")

        for test in self.tests[:10]:
            name = test['name'][:48]
            category = test['category']
            file = str(Path(test['file']).name)[:48]
            print(f"  {name:<50s} {category:<15s} {file:<50s}")

        if len(self.tests) > 10:
            print(f"  ... and {len(self.tests) - 10} more tests")

        print("\n" + "="*100)


def main():
    parser = argparse.ArgumentParser(description="Generate test catalog")
    parser.add_argument("--output", choices=["json", "table"], default="table",
                       help="Output format (json or table)")
    parser.add_argument("--save", help="Save catalog to file")
    parser.add_argument("--tests-dir", default="backend/tests",
                       help="Path to tests directory")

    args = parser.parse_args()

    # Determine tests directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    tests_dir = project_root / args.tests_dir

    if not tests_dir.exists():
        print(f"Error: Tests directory not found: {tests_dir}")
        return 1

    # Generate catalog
    print(f"📚 Scanning tests in: {tests_dir}")
    catalog_gen = TestCatalog(tests_dir)
    catalog_gen.scan_all_tests()

    # Output results
    if args.output == "json":
        catalog = catalog_gen.generate_catalog()
        json_output = json.dumps(catalog, indent=2)
        print(json_output)

        if args.save:
            with open(args.save, 'w') as f:
                f.write(json_output)
            print(f"\n✅ Catalog saved to: {args.save}")

    else:  # table
        catalog_gen.print_table()

        if args.save:
            catalog = catalog_gen.generate_catalog()
            with open(args.save, 'w') as f:
                json.dump(catalog, f, indent=2)
            print(f"\n✅ Catalog also saved to: {args.save}")

    return 0


if __name__ == "__main__":
    exit(main())

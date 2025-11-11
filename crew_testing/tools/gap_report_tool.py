"""
Gap Report Tool - Generate prioritized test coverage gap reports

This tool combines code analysis and coverage data to create actionable
reports showing what tests need to be written, in priority order.
"""

import ast
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
from crewai.tools import BaseTool

try:
    import coverage
    COVERAGE_AVAILABLE = True
except ImportError:
    COVERAGE_AVAILABLE = False


class GapReportTool(BaseTool):
    """Generates prioritized list of testing gaps by combining code and coverage analysis"""

    name: str = "generate_gap_report"
    description: str = """
    Creates an actionable gap report by analyzing:
    - Code structure (functions, methods, complexity)
    - Coverage data (which lines are tested)
    - Priority ranking (complexity × uncovered %)

    Outputs:
    - High-priority gaps (complex, uncovered functions)
    - Medium-priority gaps
    - Low-priority gaps
    - Recommended test count
    - Suggested test scenarios for top gaps

    Input: module_path (str) - Path to Python module
    Output: Prioritized gap report in markdown
    """

    def _run(self, module_path: str) -> str:
        """
        Generate prioritized gap report

        Args:
            module_path: Path to Python module to analyze

        Returns:
            Markdown-formatted gap report with priorities
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

            # Step 1: Analyze code structure
            with open(full_module_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            try:
                tree = ast.parse(source_code, filename=str(full_module_path))
            except SyntaxError as e:
                return f"❌ Syntax Error: {e}"

            analyzer = GapASTAnalyzer(source_code)
            analyzer.visit(tree)

            # Step 2: Get coverage data
            coverage_data = self._get_coverage_data(module_path, full_module_path, project_root)

            # Step 3: Combine and prioritize
            gaps = self._identify_gaps(analyzer, coverage_data)

            # Step 4: Generate report
            return self._generate_report(module_path, analyzer, coverage_data, gaps)

        except Exception as e:
            return f"❌ Error generating gap report: {str(e)}\n{type(e).__name__}"

    def _get_coverage_data(
        self,
        module_path: str,
        full_module_path: Path,
        project_root: Path
    ) -> Dict[str, Any]:
        """Get coverage data for module"""

        if not COVERAGE_AVAILABLE:
            return {
                'available': False,
                'error': 'coverage package not installed'
            }

        coverage_file = project_root / ".coverage"
        if not coverage_file.exists():
            return {
                'available': False,
                'error': 'no coverage data'
            }

        try:
            cov = coverage.Coverage(data_file=str(coverage_file))
            cov.load()

            # Try multiple path variations
            for path_variant in [str(full_module_path), str(full_module_path.relative_to(project_root)), module_path]:
                try:
                    filename, executed, excluded, missing = cov.analysis2(path_variant)
                    total = len(executed) + len(missing)
                    coverage_pct = (len(executed) / total * 100) if total > 0 else 0

                    return {
                        'available': True,
                        'executed_lines': set(executed),
                        'missing_lines': set(missing),
                        'coverage_pct': coverage_pct,
                    }
                except Exception:
                    continue

            return {
                'available': False,
                'error': 'module not in coverage data'
            }

        except Exception as e:
            return {
                'available': False,
                'error': str(e)
            }

    def _identify_gaps(self, analyzer: 'GapASTAnalyzer', coverage_data: Dict) -> List[Dict]:
        """Identify testing gaps and prioritize them"""

        gaps = []

        # Collect all functions/methods
        all_units = analyzer.functions.copy()
        for cls in analyzer.classes:
            for method in cls['methods']:
                method['class_name'] = cls['name']  # Add class context
                all_units.append(method)

        # Analyze each unit
        for unit in all_units:
            gap_info = self._analyze_unit_gap(unit, coverage_data)
            if gap_info:
                gaps.append(gap_info)

        # Sort by priority score (descending)
        gaps.sort(key=lambda x: x['priority_score'], reverse=True)

        return gaps

    def _analyze_unit_gap(self, unit: Dict, coverage_data: Dict) -> Dict:
        """Analyze a single function/method for testing gaps"""

        # Calculate coverage for this unit
        if coverage_data.get('available'):
            unit_lines = set(range(unit['lineno'], unit['end_lineno'] + 1))
            executed = unit_lines & coverage_data['executed_lines']
            missing = unit_lines & coverage_data['missing_lines']

            if len(unit_lines) > 0:
                unit_coverage = (len(executed) / len(unit_lines)) * 100
            else:
                unit_coverage = 0
        else:
            unit_coverage = 0  # Assume 0% if no coverage data

        # Calculate priority score
        # Priority = complexity × (100 - coverage%) × line_count_factor
        line_factor = min(unit['line_count'] / 10, 5)  # Cap at 5x
        priority_score = unit['complexity'] * (100 - unit_coverage) * line_factor

        # Determine priority level
        if priority_score >= 500:
            priority_level = "🔴 CRITICAL"
        elif priority_score >= 200:
            priority_level = "🟠 HIGH"
        elif priority_score >= 50:
            priority_level = "🟡 MEDIUM"
        else:
            priority_level = "🟢 LOW"

        # Generate test scenario suggestions
        scenarios = self._suggest_scenarios(unit, unit_coverage)

        class_prefix = f"{unit.get('class_name')}." if unit.get('class_name') else ""

        return {
            'name': f"{class_prefix}{unit['name']}",
            'full_name': unit['name'],
            'class_name': unit.get('class_name'),
            'lineno': unit['lineno'],
            'line_count': unit['line_count'],
            'complexity': unit['complexity'],
            'coverage': unit_coverage,
            'priority_score': priority_score,
            'priority_level': priority_level,
            'docstring': unit['docstring'],
            'arguments': unit['arguments'],
            'suggested_tests': scenarios,
        }

    def _suggest_scenarios(self, unit: Dict, current_coverage: float) -> int:
        """Suggest number of test scenarios based on complexity and coverage"""

        base_tests = 3  # Always at least happy path, edge case, error case

        # Add tests based on complexity
        if unit['complexity'] >= 10:
            base_tests += 5
        elif unit['complexity'] >= 5:
            base_tests += 3
        elif unit['complexity'] >= 3:
            base_tests += 1

        # Add tests based on argument count
        arg_count = len([a for a in unit['arguments'] if a['kind'] == 'positional'])
        if arg_count >= 4:
            base_tests += 2
        elif arg_count >= 2:
            base_tests += 1

        # Reduce if already has some coverage
        if current_coverage > 50:
            base_tests = max(2, base_tests // 2)
        elif current_coverage > 20:
            base_tests = max(3, int(base_tests * 0.7))

        return base_tests

    def _generate_report(
        self,
        module_path: str,
        analyzer: 'GapASTAnalyzer',
        coverage_data: Dict,
        gaps: List[Dict]
    ) -> str:
        """Generate markdown gap report"""

        total_units = len(gaps)
        total_tests_needed = sum(g['suggested_tests'] for g in gaps)

        # Split by priority
        critical = [g for g in gaps if "CRITICAL" in g['priority_level']]
        high = [g for g in gaps if "HIGH" in g['priority_level']]
        medium = [g for g in gaps if "MEDIUM" in g['priority_level']]
        low = [g for g in gaps if "LOW" in g['priority_level']]

        # Coverage status
        if coverage_data.get('available'):
            cov_status = f"{coverage_data['coverage_pct']:.1f}%"
        else:
            cov_status = "Unknown (no coverage data)"

        report = f"""
📊 Test Coverage Gap Report

**Module:** `{module_path}`
**Total Functions/Methods:** {total_units}
**Current Coverage:** {cov_status}
**Recommended Tests:** {total_tests_needed}

---

## 🎯 Gap Summary

| Priority | Count | Tests Needed |
|----------|-------|--------------|
| 🔴 **CRITICAL** | {len(critical)} | {sum(g['suggested_tests'] for g in critical)} |
| 🟠 **HIGH** | {len(high)} | {sum(g['suggested_tests'] for g in high)} |
| 🟡 **MEDIUM** | {len(medium)} | {sum(g['suggested_tests'] for g in medium)} |
| 🟢 **LOW** | {len(low)} | {sum(g['suggested_tests'] for g in low)} |

---

"""

        # Critical gaps
        if critical:
            report += f"## 🔴 CRITICAL Priority Gaps ({len(critical)})\n\n"
            report += "These functions are complex, large, and untested. Start here!\n\n"

            for gap in critical[:10]:  # Show top 10
                report += self._format_gap(gap)

            if len(critical) > 10:
                report += f"\n... and {len(critical) - 10} more critical gaps\n"

            report += "\n---\n\n"

        # High priority gaps
        if high:
            report += f"## 🟠 HIGH Priority Gaps ({len(high)})\n\n"

            for gap in high[:10]:
                report += self._format_gap(gap)

            if len(high) > 10:
                report += f"\n... and {len(high) - 10} more high priority gaps\n"

            report += "\n---\n\n"

        # Medium priority gaps (just list names)
        if medium:
            report += f"## 🟡 MEDIUM Priority Gaps ({len(medium)})\n\n"
            for gap in medium[:15]:
                report += f"- `{gap['name']}()` - {gap['suggested_tests']} tests suggested\n"

            if len(medium) > 15:
                report += f"- ... and {len(medium) - 15} more\n"

            report += "\n---\n\n"

        # Recommendations
        report += "## 💡 Recommended Action Plan\n\n"

        if critical:
            report += "### Phase 1: Critical Gaps (Immediate)\n"
            report += f"Generate **{sum(g['suggested_tests'] for g in critical[:5])} tests** for top 5 critical functions:\n"
            for i, gap in enumerate(critical[:5], 1):
                report += f"{i}. `{gap['name']}()` - {gap['suggested_tests']} tests\n"
            report += "\n"

        if high:
            report += "### Phase 2: High Priority (This Week)\n"
            report += f"Generate **{sum(g['suggested_tests'] for g in high[:10])} tests** for top 10 high priority functions\n\n"

        if medium or low:
            report += "### Phase 3: Remaining Gaps (Next Sprint)\n"
            remaining = sum(g['suggested_tests'] for g in medium + low)
            report += f"Generate **{remaining} tests** for medium/low priority functions\n\n"

        # Target coverage
        if coverage_data.get('available'):
            current_cov = coverage_data['coverage_pct']
            target_cov = 80
            improvement_needed = target_cov - current_cov

            report += f"""
---

## 📈 Coverage Target

**Current:** {current_cov:.1f}%
**Target:** {target_cov}%
**Improvement Needed:** +{improvement_needed:.1f}%

**Estimated Impact:**
- Phase 1 (Critical): +{len(critical) * 5:.1f}% coverage
- Phase 2 (High): +{len(high) * 3:.1f}% coverage
- Phase 3 (Med/Low): +{len(medium + low) * 1:.1f}% coverage

**Projected Final Coverage:** ~{min(95, current_cov + len(critical) * 5 + len(high) * 3 + len(medium + low) * 1):.1f}%
"""

        report += """
---

## 🚀 Next Steps

1. **Start with Critical Gaps:** Use Architect agent to design test scenarios
2. **Generate Tests:** Use Forge agent to create pytest code with mocks
3. **Execute & Measure:** Use Flash agent to run tests and measure coverage
4. **Iterate:** Repeat for High and Medium priority gaps

✅ Gap analysis complete! Ready for test generation.
"""

        return report

    def _format_gap(self, gap: Dict) -> str:
        """Format a single gap for the report"""

        args_str = ', '.join([a['name'] for a in gap['arguments']])

        output = f"### `{gap['name']}({args_str})`\n\n"
        output += f"- **Priority Score:** {gap['priority_score']:.0f}\n"
        output += f"- **Lines:** {gap['lineno']}-{gap['lineno'] + gap['line_count'] - 1} ({gap['line_count']} lines)\n"
        output += f"- **Complexity:** {gap['complexity']}\n"
        output += f"- **Coverage:** {gap['coverage']:.1f}%\n"
        output += f"- **Suggested Tests:** {gap['suggested_tests']}\n"

        if gap['docstring']:
            doc_preview = gap['docstring'][:100] + "..." if len(gap['docstring']) > 100 else gap['docstring']
            output += f"- **Purpose:** {doc_preview}\n"

        output += "\n"

        return output


class GapASTAnalyzer(ast.NodeVisitor):
    """Simplified AST analyzer for gap analysis (reuse from code_analyzer)"""

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.functions = []
        self.classes = []
        self.current_class = None

    def visit_ClassDef(self, node):
        class_info = {
            'name': node.name,
            'lineno': node.lineno,
            'end_lineno': node.end_lineno or node.lineno,
            'methods': [],
        }

        prev_class = self.current_class
        self.current_class = class_info
        self.classes.append(class_info)
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node):
        func_info = {
            'name': node.name,
            'lineno': node.lineno,
            'end_lineno': node.end_lineno or node.lineno,
            'line_count': (node.end_lineno or node.lineno) - node.lineno + 1,
            'docstring': ast.get_docstring(node),
            'arguments': self._extract_arguments(node.args),
            'complexity': self._estimate_complexity(node),
        }

        if self.current_class:
            self.current_class['methods'].append(func_info)
        else:
            self.functions.append(func_info)

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def _extract_arguments(self, args_node):
        arguments = []
        for arg in args_node.args:
            arguments.append({
                'name': arg.arg,
                'kind': 'positional',
            })
        if args_node.vararg:
            arguments.append({'name': f"*{args_node.vararg.arg}", 'kind': 'vararg'})
        if args_node.kwarg:
            arguments.append({'name': f"**{args_node.kwarg.arg}", 'kind': 'kwarg'})
        return arguments

    def _estimate_complexity(self, node):
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

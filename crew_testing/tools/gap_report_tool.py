"""
Gap Report Tool - Prioritize testing gaps by combining code analysis and coverage data

This tool combines AST-based code analysis with test coverage information
to identify and prioritize testing gaps.

Features:
- Combines code structure analysis with coverage data
- Prioritizes gaps by complexity, size, and coverage
- Identifies CRITICAL functions needing tests most urgently
- Shows implementation details for high-priority functions
- Generates concise, actionable gap reports

Used by Inspector agent to guide test generation.
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple
from crewai.tools import BaseTool


class GapReportTool(BaseTool):
    """Generates prioritized testing gap reports"""

    name: str = "generate_gap_report"
    description: str = """
    Generates a prioritized testing gap report by combining code analysis and coverage data.

    Identifies which functions need tests most urgently based on:
    - Cyclomatic complexity (higher = more critical)
    - Function size (longer = more critical)
    - Current test coverage (lower = more critical)
    - External dependencies (database, API = more critical)
    - Exception handling complexity

    Output is a markdown report showing CRITICAL gaps with implementation details.

    Input: module_path (str) - Path to Python module to analyze
    Output: Prioritized gap report in markdown

    Note: Requires .coverage file to exist. Run 'pytest --cov' first.
    """

    def _run(self, module_path: str) -> str:
        """
        Generate prioritized gap report for Python module

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

            # Read and parse source code
            with open(full_module_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            try:
                tree = ast.parse(source_code, filename=str(full_module_path))
            except SyntaxError as e:
                return f"❌ Syntax Error: {e}"

            # Analyze code structure
            analyzer = GapASTAnalyzer(source_code)
            analyzer.visit(tree)

            # Try to load coverage data
            coverage_data = self._load_coverage_data(full_module_path, project_root)

            # Generate prioritized gap report
            return self._generate_gap_report(module_path, analyzer, coverage_data, source_code)

        except Exception as e:
            return f"❌ Error generating gap report: {str(e)}\n{type(e).__name__}"

    def _load_coverage_data(self, module_path: Path, project_root: Path) -> Dict[str, Any]:
        """Load coverage data if available"""
        try:
            from coverage import Coverage

            # Look for .coverage file
            coverage_file = project_root / ".coverage"
            backend_coverage_file = project_root / "backend" / ".coverage"

            if backend_coverage_file.exists():
                coverage_data_file = backend_coverage_file
            elif coverage_file.exists():
                coverage_data_file = coverage_file
            else:
                return {'available': False}

            # Load coverage
            cov = Coverage(data_file=str(coverage_data_file))
            cov.load()

            # Get analysis
            try:
                analysis = cov.analysis2(str(module_path))
                # Unpack analysis results - use indexing for compatibility with different coverage versions
                filename = analysis[0]
                executed_lines = analysis[1]
                excluded_lines = analysis[2] if len(analysis) > 2 else []
                missing_lines = analysis[3] if len(analysis) > 3 else []
                executable_lines = len(executed_lines) + len(missing_lines)
                coverage_pct = (len(executed_lines) / executable_lines * 100) if executable_lines > 0 else 0

                return {
                    'available': True,
                    'executed_lines': set(executed_lines),
                    'missing_lines': set(missing_lines),
                    'coverage_pct': coverage_pct,
                }
            except Exception:
                return {'available': False}

        except ImportError:
            return {'available': False}

    def _generate_gap_report(
        self,
        module_path: str,
        analyzer: 'GapASTAnalyzer',
        coverage_data: Dict[str, Any],
        source_code: str
    ) -> str:
        """Generate prioritized gap report"""

        # Collect all testable units (functions + methods)
        all_units = []

        # Add top-level functions
        for func in analyzer.functions:
            all_units.append({
                'type': 'function',
                'name': func['name'],
                'full_name': func['name'],
                **func
            })

        # Add class methods
        for cls in analyzer.classes:
            for method in cls['methods']:
                all_units.append({
                    'type': 'method',
                    'name': method['name'],
                    'full_name': f"{cls['name']}.{method['name']}",
                    'class_name': cls['name'],
                    **method
                })

        # Calculate priority scores
        for unit in all_units:
            unit['priority_score'] = self._calculate_priority(unit, coverage_data)
            unit['coverage_status'] = self._get_coverage_status(unit, coverage_data)

        # Sort by priority (highest first)
        all_units.sort(key=lambda u: u['priority_score'], reverse=True)

        # Generate report
        total_units = len(all_units)
        critical_units = [u for u in all_units if u['priority_score'] >= 7]
        high_units = [u for u in all_units if 5 <= u['priority_score'] < 7]
        medium_units = [u for u in all_units if 3 <= u['priority_score'] < 5]

        report = f"""
🎯 Testing Gap Report

**File:** `{module_path}`
**Total Testable Units:** {total_units}
**Coverage:** {coverage_data.get('coverage_pct', 0):.1f}% ({"available" if coverage_data.get('available') else "no data"})

**Priority Breakdown:**
- 🔴 **CRITICAL** (score ≥7): {len(critical_units)} functions
- 🟠 **HIGH** (score 5-6): {len(high_units)} functions
- 🟡 **MEDIUM** (score 3-4): {len(medium_units)} functions
- 🟢 **LOW** (score <3): {len(all_units) - len(critical_units) - len(high_units) - len(medium_units)} functions

---

"""

        # Show CRITICAL gaps with full details
        if critical_units:
            report += "## 🔴 CRITICAL Testing Gaps\n\n"
            report += "**These functions MUST be tested first:**\n\n"

            for unit in critical_units:
                report += f"### `{unit['full_name']}()`\n\n"
                report += f"- **Priority Score:** {unit['priority_score']}/10\n"
                report += f"- **Complexity:** {unit['complexity']}\n"
                report += f"- **Lines:** {unit['lineno']}-{unit['end_lineno']} ({unit['line_count']} lines)\n"
                report += f"- **Coverage:** {unit['coverage_status']}\n"

                # Show implementation details for CRITICAL functions
                if unit.get('return_pattern'):
                    report += f"- **Return Pattern:** {unit['return_pattern']}\n"

                if unit.get('exception_handlers'):
                    report += f"- **Exception Handling:** {len(unit['exception_handlers'])} handlers\n"
                    for handler in unit['exception_handlers'][:2]:
                        report += f"  - `{handler['exception_type']}` → {handler['action']}\n"

                if unit.get('external_calls'):
                    report += f"- **External Dependencies:** {len(unit['external_calls'])} calls\n"
                    for call in unit['external_calls'][:3]:
                        report += f"  - {call['type']}: `{call['call']}`\n"

                report += "\n**Why Critical:**\n"
                reasons = self._get_priority_reasons(unit)
                for reason in reasons:
                    report += f"- {reason}\n"

                report += "\n"

            report += "---\n\n"

        # Show HIGH priority gaps (summary only)
        if high_units:
            report += "## 🟠 HIGH Priority Gaps\n\n"
            for unit in high_units[:5]:
                report += f"- `{unit['full_name']}()` - Complexity: {unit['complexity']}, Lines: {unit['line_count']}, {unit['coverage_status']}\n"

            if len(high_units) > 5:
                report += f"- ... and {len(high_units) - 5} more high-priority gaps\n"

            report += "\n---\n\n"

        # Show summary recommendations
        report += "## 📋 Recommendations\n\n"

        if len(critical_units) > 0:
            report += f"**URGENT:** Focus on {len(critical_units)} CRITICAL gaps first. "
            report += "These are complex, untested functions with external dependencies.\n\n"

        if len(high_units) > 0:
            report += f"**Next:** Address {len(high_units)} HIGH priority gaps. "
            report += "These are moderately complex functions needing test coverage.\n\n"

        if coverage_data.get('coverage_pct', 0) < 50:
            report += "**Coverage is critically low.** Prioritize core functionality and error handling.\n\n"
        elif coverage_data.get('coverage_pct', 0) < 80:
            report += "**Coverage needs improvement.** Focus on edge cases and error paths.\n\n"
        else:
            report += "**Coverage is good.** Consider remaining edge cases and integration tests.\n\n"

        report += "---\n\n✅ Gap analysis complete! Ready for test scenario design.\n"

        return report

    def _calculate_priority(self, unit: Dict[str, Any], coverage_data: Dict[str, Any]) -> int:
        """Calculate priority score (0-10) for a function"""
        score = 0

        # Complexity factor (0-3 points)
        complexity = unit.get('complexity', 1)
        if complexity >= 10:
            score += 3
        elif complexity >= 5:
            score += 2
        elif complexity >= 3:
            score += 1

        # Size factor (0-2 points)
        line_count = unit.get('line_count', 0)
        if line_count >= 50:
            score += 2
        elif line_count >= 20:
            score += 1

        # Coverage factor (0-3 points)
        if coverage_data.get('available'):
            unit_lines = set(range(unit['lineno'], unit['end_lineno'] + 1))
            missing_lines = coverage_data.get('missing_lines', set())
            uncovered_lines = unit_lines.intersection(missing_lines)
            coverage_ratio = 1 - (len(uncovered_lines) / len(unit_lines)) if len(unit_lines) > 0 else 0

            if coverage_ratio < 0.2:  # < 20% covered
                score += 3
            elif coverage_ratio < 0.5:  # < 50% covered
                score += 2
            elif coverage_ratio < 0.8:  # < 80% covered
                score += 1

        # External dependencies factor (0-2 points)
        external_calls = unit.get('external_calls', [])
        if len(external_calls) >= 3:
            score += 2
        elif len(external_calls) >= 1:
            score += 1

        return min(score, 10)  # Cap at 10

    def _get_coverage_status(self, unit: Dict[str, Any], coverage_data: Dict[str, Any]) -> str:
        """Get human-readable coverage status"""
        if not coverage_data.get('available'):
            return "⚠️ No coverage data"

        unit_lines = set(range(unit['lineno'], unit['end_lineno'] + 1))
        missing_lines = coverage_data.get('missing_lines', set())
        uncovered_lines = unit_lines.intersection(missing_lines)

        if len(uncovered_lines) == 0:
            return "✅ Fully covered"

        coverage_ratio = 1 - (len(uncovered_lines) / len(unit_lines)) if len(unit_lines) > 0 else 0
        coverage_pct = coverage_ratio * 100

        if coverage_pct < 20:
            return f"❌ Untested ({coverage_pct:.0f}% covered)"
        elif coverage_pct < 80:
            return f"⚠️ Partially tested ({coverage_pct:.0f}% covered)"
        else:
            return f"🟡 Mostly covered ({coverage_pct:.0f}% covered)"

    def _get_priority_reasons(self, unit: Dict[str, Any]) -> List[str]:
        """Get human-readable reasons for priority"""
        reasons = []

        if unit.get('complexity', 0) >= 5:
            reasons.append(f"High complexity ({unit['complexity']} branches)")

        if unit.get('line_count', 0) >= 20:
            reasons.append(f"Large function ({unit['line_count']} lines)")

        if unit.get('external_calls'):
            dep_types = {call['type'] for call in unit['external_calls']}
            reasons.append(f"External dependencies: {', '.join(dep_types)}")

        if unit.get('exception_handlers'):
            reasons.append(f"Complex error handling ({len(unit['exception_handlers'])} exception types)")

        if unit['coverage_status'].startswith('❌'):
            reasons.append("No test coverage")

        return reasons


class GapASTAnalyzer(ast.NodeVisitor):
    """AST visitor to extract code structure with implementation details"""

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.source_lines = source_code.split('\n')
        self.imports = []
        self.functions = []
        self.classes = []
        self.current_class = None

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(f"import {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            self.imports.append(f"from {module} import {alias.name}")
        self.generic_visit(node)

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
            'returns': self._extract_return_type(node),
            # Enhanced analysis for gap prioritization
            'exception_handlers': self._extract_exception_handlers(node),
            'return_pattern': self._analyze_return_pattern(node),
            'external_calls': self._extract_external_calls(node),
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
            arguments.append({'name': arg.arg, 'kind': 'positional'})
        if args_node.vararg:
            arguments.append({'name': f"*{args_node.vararg.arg}", 'kind': 'vararg'})
        if args_node.kwarg:
            arguments.append({'name': f"**{args_node.kwarg.arg}", 'kind': 'kwarg'})
        return arguments

    def _extract_return_type(self, node):
        if node.returns:
            return ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)
        return None

    def _estimate_complexity(self, node):
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def _extract_exception_handlers(self, node):
        """Extract try/except blocks and their exception types"""
        handlers = []
        for child in ast.walk(node):
            if isinstance(child, ast.Try):
                for handler in child.handlers:
                    exc_type = self._get_name(handler.type) if handler.type else "Exception"
                    handler_action = "unknown"
                    for stmt in handler.body:
                        if isinstance(stmt, ast.Return):
                            handler_action = f"returns {self._get_name(stmt.value)}"
                            break
                        elif isinstance(stmt, ast.Raise):
                            if stmt.exc:
                                handler_action = f"raises {self._get_name(stmt.exc)}"
                            else:
                                handler_action = "re-raises"
                            break
                    handlers.append({
                        'exception_type': exc_type,
                        'action': handler_action,
                        'lineno': handler.lineno if hasattr(handler, 'lineno') else None,
                    })
        return handlers

    def _analyze_return_pattern(self, node):
        """Analyze return statements to understand return behavior"""
        returns = []
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                return_value = self._get_name(child.value) if child.value else "None"
                returns.append(return_value)

        if not returns:
            return "No explicit returns (returns None)"

        unique_returns = set(returns)
        if len(unique_returns) == 1:
            return f"Always returns: {returns[0]}"
        elif 'None' in unique_returns:
            return f"Returns {', '.join(r for r in unique_returns if r != 'None')} or None"
        else:
            return f"Returns: {', '.join(unique_returns)}"

    def _extract_external_calls(self, node):
        """Extract calls to external dependencies (database, APIs, etc.)"""
        external_calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._get_name(child.func)
                if any(keyword in call_name.lower() for keyword in ['supabase', 'table', 'select', 'insert', 'update', 'delete', 'execute']):
                    external_calls.append({'type': 'database', 'call': call_name})
                elif any(keyword in call_name.lower() for keyword in ['request', 'get', 'post', 'put', 'delete', 'fetch']):
                    external_calls.append({'type': 'http', 'call': call_name})
                elif any(keyword in call_name.lower() for keyword in ['open', 'read', 'write', 'file']):
                    external_calls.append({'type': 'file_io', 'call': call_name})
        # Deduplicate
        seen = set()
        unique_calls = []
        for call in external_calls:
            call_key = (call['type'], call['call'])
            if call_key not in seen:
                seen.add(call_key)
                unique_calls.append(call)
        return unique_calls

    def _get_name(self, node):
        """Extract name from various AST node types"""
        if node is None:
            return "None"
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_name(node.value)
            return f"{value}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_name(node.func) + "()"
        elif isinstance(node, ast.Constant):
            return repr(node.value) if isinstance(node.value, str) else str(node.value)
        elif isinstance(node, (ast.Dict, ast.List, ast.Tuple, ast.Set)):
            return node.__class__.__name__.lower()
        else:
            return ast.unparse(node) if hasattr(ast, 'unparse') else "..."


# Export tool
__all__ = ["GapReportTool"]

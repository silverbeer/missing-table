"""
Code Analyzer Tool - Extract Python code structure using AST

This tool analyzes Python source files to extract:
- Functions and methods with signatures
- Cyclomatic complexity
- Exception handling patterns
- Return behavior
- External dependencies
- Implementation snippets

Used by Inspector agent to identify testing gaps.
"""

import ast
import os
from pathlib import Path
from typing import List, Dict, Any
from crewai.tools import BaseTool


class CodeAnalyzerTool(BaseTool):
    """Analyzes Python code structure using AST"""

    name: str = "analyze_code"
    description: str = """
    Analyzes a Python module to extract code structure information:
    - Functions, methods, classes
    - Cyclomatic complexity
    - Exception handling patterns (catches vs re-raises)
    - Return patterns (returns dict, returns None, etc.)
    - External dependencies (database, API calls)
    - Implementation snippets

    Input: module_path (str) - Path to Python module
    Output: Detailed code structure report in markdown
    """

    def _run(self, module_path: str) -> str:
        """
        Analyze Python module structure

        Args:
            module_path: Path to Python module to analyze

        Returns:
            Markdown-formatted code structure report
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
            analyzer = CodeASTAnalyzer(source_code)
            analyzer.visit(tree)

            # Generate report
            return self._generate_report(module_path, analyzer, source_code)

        except Exception as e:
            return f"❌ Error analyzing code: {str(e)}\\n{type(e).__name__}"

    def _generate_report(self, module_path: str, analyzer: 'CodeASTAnalyzer', source_code: str) -> str:
        """Generate markdown code analysis report"""

        total_functions = len(analyzer.functions)
        total_methods = sum(len(cls['methods']) for cls in analyzer.classes)
        total_testable = total_functions + total_methods

        # Count complexity
        all_units = analyzer.functions.copy()
        for cls in analyzer.classes:
            all_units.extend(cls['methods'])

        complexities = [u['complexity'] for u in all_units]
        avg_complexity = sum(complexities) / len(complexities) if complexities else 0
        max_complexity = max(complexities) if complexities else 0
        high_complexity = [u for u in all_units if u['complexity'] >= 5]

        report = f"""
🔬 Code Analysis Report

**File:** `{module_path}`
**Lines:** {len(source_code.split(chr(10)))}
**Classes:** {len(analyzer.classes)}
**Functions:** {total_functions}
**Methods:** {total_methods}
**Total Testable Units:** {total_testable}

---

## 📦 Imports ({len(analyzer.imports)})

"""
        # List imports (first 10)
        for i, imp in enumerate(analyzer.imports[:10]):
            report += f"- `{imp}`\\n"
        if len(analyzer.imports) > 10:
            report += f"- ... and {len(analyzer.imports) - 10} more\\n"

        report += "\\n---\\n\\n"

        # Classes
        if analyzer.classes:
            report += f"## 📚 Classes ({len(analyzer.classes)})\\n\\n"
            for cls in analyzer.classes:
                report += f"### `{cls['name']}`\\n\\n"
                report += f"- **Lines:** {cls['lineno']}-{cls['end_lineno']}\\n"
                report += f"- **Methods:** {len(cls['methods'])}\\n\\n"

                if cls['methods']:
                    report += "**Methods:**\\n"
                    for method in cls['methods']:
                        args = ', '.join([arg['name'] for arg in method['arguments']])
                        report += f"- `{method['name']}({args})` - {method['line_count']} lines, complexity: {method['complexity']}\\n"

                report += "\\n"

            report += "---\\n\\n"

        # Top-level functions
        if analyzer.functions:
            report += f"## 🔧 Top-Level Functions ({len(analyzer.functions)})\\n\\n"
            for func in analyzer.functions:
                args = ', '.join([arg['name'] for arg in func['arguments']])
                report += f"### `{func['name']}({args})`\\n\\n"
                report += f"- **Lines:** {func['lineno']}-{func['end_lineno']} ({func['line_count']} lines)\\n"
                report += f"- **Complexity:** {func['complexity']}\\n"

                if func.get('returns'):
                    report += f"- **Returns:** `{func['returns']}`\\n"

                if func.get('docstring'):
                    doc_preview = func['docstring'][:100] + "..." if len(func['docstring']) > 100 else func['docstring']
                    report += f"- **Docstring:** {doc_preview}\\n"

                # Show implementation details
                if func.get('return_pattern'):
                    report += f"- **Return Pattern:** {func['return_pattern']}\\n"

                if func.get('exception_handlers'):
                    report += f"- **Exception Handling:** {len(func['exception_handlers'])} handlers\\n"
                    for handler in func['exception_handlers'][:2]:
                        report += f"  - `{handler['exception_type']}` → {handler['action']}\\n"

                if func.get('external_calls'):
                    report += f"- **External Dependencies:** {len(func['external_calls'])} calls\\n"
                    for call in func['external_calls'][:3]:
                        report += f"  - {call['type']}: `{call['call']}`\\n"

                if func.get('implementation_snippet'):
                    report += f"\\n**Implementation Snippet:**\\n```python\\n{func['implementation_snippet']}\\n```\\n"

                report += "\\n"

            report += "---\\n\\n"

        # Complexity summary
        report += f"""## 📊 Complexity Summary

- **Average Complexity:** {avg_complexity:.1f}
- **Max Complexity:** {max_complexity}
- **High Complexity (≥5):** {len(high_complexity)} functions

"""
        if high_complexity:
            report += "**High Complexity Functions:**\\n"
            for unit in high_complexity[:5]:
                report += f"- `{unit['name']}()` - Complexity: {unit['complexity']}\\n"

        report += "\\n---\\n\\n✅ Analysis complete! Ready for test scenario design.\\n"

        return report


class CodeASTAnalyzer(ast.NodeVisitor):
    """AST visitor to extract code structure"""

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.source_lines = source_code.split('\\n')
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
            # Enhanced analysis
            'exception_handlers': self._extract_exception_handlers(node),
            'return_pattern': self._analyze_return_pattern(node),
            'external_calls': self._extract_external_calls(node),
            'implementation_snippet': self._get_implementation_snippet(node),
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
                    # Analyze what happens in the handler
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
                # Detect common external dependencies
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

    def _get_implementation_snippet(self, node):
        """Get a relevant snippet of the implementation (first 10 lines of body)"""
        try:
            body_start = node.lineno
            # Skip docstring if present
            if (node.body and isinstance(node.body[0], ast.Expr) and
                isinstance(node.body[0].value, (ast.Str, ast.Constant))):
                body_start = node.body[1].lineno if len(node.body) > 1 else node.lineno
            else:
                body_start = node.body[0].lineno if node.body else node.lineno

            snippet_end = min(body_start + 10, node.end_lineno or node.lineno)
            snippet_lines = self.source_lines[body_start-1:snippet_end]
            snippet = '\\n'.join(snippet_lines)

            if len(snippet) > 500:
                snippet = snippet[:500] + "..."
            return snippet
        except Exception:
            return "Unable to extract snippet"

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

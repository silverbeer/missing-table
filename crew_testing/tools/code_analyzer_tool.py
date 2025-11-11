"""
Code Analyzer Tool - Parse Python code to extract testable units

This tool uses Python's AST (Abstract Syntax Tree) module to analyze
Python source files and extract functions, methods, classes, and their
metadata for test generation.
"""

import ast
import os
from pathlib import Path
from typing import Any, Optional
from crewai.tools import BaseTool
from pydantic import Field


class CodeAnalyzerTool(BaseTool):
    """Analyzes Python code to extract testable units (functions, methods, classes)"""

    name: str = "analyze_code"
    description: str = """
    Parses a Python file and extracts all testable units including:
    - Functions (top-level and nested)
    - Methods (instance and class methods)
    - Classes
    - Function signatures
    - Docstrings
    - Complexity estimates
    - Dependencies (imports, function calls)

    Input: file_path (str) - Absolute or relative path to Python file
    Output: Markdown report with code analysis
    """

    def _run(self, file_path: str) -> str:
        """
        Analyze Python code and extract testable units

        Args:
            file_path: Path to Python file (relative to project root or absolute)

        Returns:
            Markdown-formatted analysis report
        """
        try:
            # Resolve file path
            if not os.path.isabs(file_path):
                # Assume relative to project root
                project_root = Path(__file__).parent.parent.parent
                file_path = str(project_root / file_path)

            if not os.path.exists(file_path):
                return f"❌ Error: File not found: {file_path}"

            # Read source code
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            # Parse AST
            try:
                tree = ast.parse(source_code, filename=file_path)
            except SyntaxError as e:
                return f"❌ Syntax Error in {file_path}:\n{e}"

            # Extract analysis
            analyzer = CodeASTAnalyzer(source_code)
            analyzer.visit(tree)

            # Generate markdown report
            return analyzer.generate_report(file_path)

        except Exception as e:
            return f"❌ Error analyzing code: {str(e)}\n{type(e).__name__}"


class CodeASTAnalyzer(ast.NodeVisitor):
    """AST visitor to extract code metadata"""

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.source_lines = source_code.split('\n')
        self.functions = []
        self.classes = []
        self.imports = []
        self.current_class = None

    def visit_Import(self, node):
        """Extract import statements"""
        for alias in node.names:
            self.imports.append({
                'type': 'import',
                'module': alias.name,
                'alias': alias.asname,
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Extract from...import statements"""
        for alias in node.names:
            self.imports.append({
                'type': 'from_import',
                'module': node.module or '',
                'name': alias.name,
                'alias': alias.asname,
            })
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Extract class definitions"""
        class_info = {
            'name': node.name,
            'lineno': node.lineno,
            'end_lineno': node.end_lineno or node.lineno,
            'docstring': ast.get_docstring(node),
            'bases': [self._get_name(base) for base in node.bases],
            'methods': [],
            'decorators': [self._get_name(d) for d in node.decorator_list],
        }

        # Store current class context
        prev_class = self.current_class
        self.current_class = class_info
        self.classes.append(class_info)

        # Visit methods
        self.generic_visit(node)

        # Restore class context
        self.current_class = prev_class

    def visit_FunctionDef(self, node):
        """Extract function/method definitions"""
        # Get function signature
        args = self._extract_arguments(node.args)

        func_info = {
            'name': node.name,
            'lineno': node.lineno,
            'end_lineno': node.end_lineno or node.lineno,
            'line_count': (node.end_lineno or node.lineno) - node.lineno + 1,
            'docstring': ast.get_docstring(node),
            'arguments': args,
            'decorators': [self._get_name(d) for d in node.decorator_list],
            'returns': self._get_name(node.returns) if node.returns else None,
            'is_async': isinstance(node, ast.AsyncFunctionDef),
            'is_method': self.current_class is not None,
            'class_name': self.current_class['name'] if self.current_class else None,
            'complexity': self._estimate_complexity(node),
            # NEW: Implementation details
            'exception_handlers': self._extract_exception_handlers(node),
            'return_pattern': self._analyze_return_pattern(node),
            'external_calls': self._extract_external_calls(node),
            'implementation_snippet': self._get_implementation_snippet(node),
        }

        if self.current_class:
            # Add to class methods
            self.current_class['methods'].append(func_info)
        else:
            # Top-level function
            self.functions.append(func_info)

        # Don't visit nested functions for now (could be added later)
        # self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        """Handle async functions"""
        self.visit_FunctionDef(node)

    def _extract_arguments(self, args_node):
        """Extract function arguments with type hints"""
        arguments = []

        # Regular args
        for arg in args_node.args:
            arguments.append({
                'name': arg.arg,
                'type': self._get_name(arg.annotation) if arg.annotation else None,
                'kind': 'positional',
            })

        # *args
        if args_node.vararg:
            arguments.append({
                'name': f"*{args_node.vararg.arg}",
                'type': self._get_name(args_node.vararg.annotation) if args_node.vararg.annotation else None,
                'kind': 'vararg',
            })

        # **kwargs
        if args_node.kwarg:
            arguments.append({
                'name': f"**{args_node.kwarg.arg}",
                'type': self._get_name(args_node.kwarg.annotation) if args_node.kwarg.annotation else None,
                'kind': 'kwarg',
            })

        return arguments

    def _estimate_complexity(self, node):
        """Estimate cyclomatic complexity"""
        complexity = 1  # Base complexity

        # Count decision points
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # and/or operators
                complexity += len(child.values) - 1

        return complexity

    def _get_name(self, node):
        """Extract name from AST node"""
        if node is None:
            return None
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_name(node.value)
            return f"{value}.{node.attr}" if value else node.attr
        elif isinstance(node, ast.Subscript):
            value = self._get_name(node.value)
            return f"{value}[...]"
        else:
            return ast.unparse(node)

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
                        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                            call_name = self._get_name(stmt.value.func)
                            if 'log' in call_name.lower():
                                handler_action = "logs and continues"

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

        # Categorize return pattern
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
                    external_calls.append({
                        'type': 'database',
                        'call': call_name,
                    })
                elif any(keyword in call_name.lower() for keyword in ['request', 'get', 'post', 'put', 'delete', 'fetch']):
                    external_calls.append({
                        'type': 'http',
                        'call': call_name,
                    })
                elif any(keyword in call_name.lower() for keyword in ['open', 'read', 'write', 'file']):
                    external_calls.append({
                        'type': 'file_io',
                        'call': call_name,
                    })

        # Deduplicate while preserving order
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
            # Get first 10 lines of function body (excluding docstring)
            body_start = node.lineno

            # Skip docstring if present
            if (node.body and
                isinstance(node.body[0], ast.Expr) and
                isinstance(node.body[0].value, (ast.Str, ast.Constant))):
                body_start = node.body[1].lineno if len(node.body) > 1 else node.lineno
            else:
                body_start = node.body[0].lineno if node.body else node.lineno

            # Get up to 10 lines from body start
            snippet_end = min(body_start + 10, node.end_lineno or node.lineno)

            # Extract lines from source
            snippet_lines = self.source_lines[body_start-1:snippet_end]
            snippet = '\n'.join(snippet_lines)

            # Truncate if too long
            if len(snippet) > 500:
                snippet = snippet[:500] + "..."

            return snippet
        except Exception:
            return "Unable to extract snippet"

    def generate_report(self, file_path: str) -> str:
        """Generate markdown analysis report"""
        file_name = os.path.basename(file_path)
        total_lines = len(self.source_lines)
        total_functions = len(self.functions)
        total_classes = len(self.classes)
        total_methods = sum(len(cls['methods']) for cls in self.classes)
        total_units = total_functions + total_methods

        report = f"""
🔬 Code Analysis Report

**File:** `{file_path}`
**Lines:** {total_lines}
**Classes:** {total_classes}
**Functions:** {total_functions}
**Methods:** {total_methods}
**Total Testable Units:** {total_units}

---

## 📦 Imports ({len(self.imports)})

"""

        # List imports
        if self.imports:
            for imp in self.imports[:10]:  # Show first 10
                if imp['type'] == 'import':
                    report += f"- `import {imp['module']}`\n"
                else:
                    report += f"- `from {imp['module']} import {imp['name']}`\n"
            if len(self.imports) > 10:
                report += f"- ... and {len(self.imports) - 10} more\n"
        else:
            report += "No imports found\n"

        report += "\n---\n\n"

        # List classes
        if self.classes:
            report += f"## 📚 Classes ({len(self.classes)})\n\n"
            for cls in self.classes:
                report += f"### `{cls['name']}`\n\n"
                report += f"- **Lines:** {cls['lineno']}-{cls['end_lineno']}\n"
                report += f"- **Methods:** {len(cls['methods'])}\n"
                if cls['bases']:
                    report += f"- **Inherits:** {', '.join(cls['bases'])}\n"
                if cls['docstring']:
                    report += f"- **Docstring:** {cls['docstring'][:80]}...\n"

                # List methods
                if cls['methods']:
                    report += f"\n**Methods:**\n\n"
                    for method in cls['methods']:
                        args = ', '.join([arg['name'] for arg in method['arguments']])
                        report += f"#### `{method['name']}({args})`\n\n"
                        report += f"- **Lines:** {method['lineno']}-{method['end_lineno']} ({method['line_count']} lines)\n"
                        report += f"- **Complexity:** {method['complexity']}\n"

                        # Implementation details
                        if method.get('return_pattern'):
                            report += f"- **Return Pattern:** {method['return_pattern']}\n"

                        if method.get('exception_handlers'):
                            report += f"- **Exception Handling:** {len(method['exception_handlers'])} handlers\n"
                            for handler in method['exception_handlers'][:2]:
                                report += f"  - `{handler['exception_type']}` → {handler['action']}\n"
                            if len(method['exception_handlers']) > 2:
                                report += f"  - ... and {len(method['exception_handlers']) - 2} more\n"

                        if method.get('external_calls'):
                            report += f"- **External Dependencies:** {len(method['external_calls'])} calls\n"
                            for call in method['external_calls'][:2]:
                                report += f"  - {call['type']}: `{call['call']}`\n"
                            if len(method['external_calls']) > 2:
                                report += f"  - ... and {len(method['external_calls']) - 2} more\n"

                        if method.get('implementation_snippet') and method['implementation_snippet'] != "Unable to extract snippet":
                            snippet = method['implementation_snippet']
                            # Truncate snippet for methods to save space
                            if len(snippet) > 300:
                                snippet = snippet[:300] + "..."
                            report += f"\n**Implementation Snippet:**\n```python\n{snippet}\n```\n"

                        report += "\n"

                report += "\n"

            report += "---\n\n"

        # List functions
        if self.functions:
            report += f"## 🔧 Top-Level Functions ({len(self.functions)})\n\n"
            for func in self.functions:
                args = ', '.join([arg['name'] for arg in func['arguments']])
                report += f"### `{func['name']}({args})`\n\n"
                report += f"- **Lines:** {func['lineno']}-{func['end_lineno']} ({func['line_count']} lines)\n"
                report += f"- **Complexity:** {func['complexity']}\n"
                if func['returns']:
                    report += f"- **Returns:** `{func['returns']}`\n"
                if func['decorators']:
                    report += f"- **Decorators:** {', '.join([f'`@{d}`' for d in func['decorators']])}\n"
                if func['docstring']:
                    report += f"- **Docstring:** {func['docstring'][:100]}...\n"

                # NEW: Implementation details
                if func.get('return_pattern'):
                    report += f"- **Return Pattern:** {func['return_pattern']}\n"

                if func.get('exception_handlers'):
                    report += f"- **Exception Handling:** {len(func['exception_handlers'])} handlers\n"
                    for handler in func['exception_handlers'][:3]:  # Show first 3
                        report += f"  - `{handler['exception_type']}` → {handler['action']}\n"
                    if len(func['exception_handlers']) > 3:
                        report += f"  - ... and {len(func['exception_handlers']) - 3} more\n"

                if func.get('external_calls'):
                    report += f"- **External Dependencies:** {len(func['external_calls'])} calls\n"
                    for call in func['external_calls'][:3]:  # Show first 3
                        report += f"  - {call['type']}: `{call['call']}`\n"
                    if len(func['external_calls']) > 3:
                        report += f"  - ... and {len(func['external_calls']) - 3} more\n"

                if func.get('implementation_snippet') and func['implementation_snippet'] != "Unable to extract snippet":
                    report += f"\n**Implementation Snippet:**\n```python\n{func['implementation_snippet']}\n```\n"

                report += "\n"

        # Summary
        report += "---\n\n"
        report += "## 📊 Complexity Summary\n\n"

        all_units = self.functions + [m for cls in self.classes for m in cls['methods']]
        if all_units:
            complexities = [u['complexity'] for u in all_units]
            avg_complexity = sum(complexities) / len(complexities)
            max_complexity = max(complexities)
            high_complexity = [u for u in all_units if u['complexity'] >= 5]

            report += f"- **Average Complexity:** {avg_complexity:.1f}\n"
            report += f"- **Max Complexity:** {max_complexity}\n"
            report += f"- **High Complexity (≥5):** {len(high_complexity)} functions\n\n"

            if high_complexity:
                report += "**High Complexity Functions:**\n"
                for func in sorted(high_complexity, key=lambda x: x['complexity'], reverse=True)[:5]:
                    class_name = f"{func['class_name']}." if func.get('class_name') else ""
                    report += f"- `{class_name}{func['name']}()` - Complexity: {func['complexity']}\n"

        report += "\n---\n\n"
        report += "✅ Analysis complete! Ready for test scenario design.\n"

        return report

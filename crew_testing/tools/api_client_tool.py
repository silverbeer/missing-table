"""
API Client Scanner Tool - Scans backend/api_client/ directory

This tool enables agents to:
- Scan the api_client directory for Python files
- Extract method definitions
- Identify available client methods
- Detect missing implementations
"""

import ast
import os
from pathlib import Path
from typing import List, Dict, Any

from crewai.tools import BaseTool


class ScanAPIClientTool(BaseTool):
    """Tool to scan api_client directory and extract method information"""

    name: str = "scan_api_client"
    description: str = (
        "Scans the backend/api_client/ directory to find all implemented client methods. "
        "Returns a list of method names, their signatures, and docstrings. "
        "Use this to understand what API client methods are currently available."
    )

    def _run(self, api_client_path: str = None) -> str:
        """
        Scan api_client directory for methods

        Args:
            api_client_path: Path to api_client directory (default: ../api_client)

        Returns:
            Formatted string with method information
        """
        if api_client_path is None:
            # Default to backend/api_client
            current_dir = Path(__file__).parent.parent.parent
            api_client_path = current_dir / "api_client"

        api_client_path = Path(api_client_path)

        if not api_client_path.exists():
            return f"❌ Error: api_client directory not found at {api_client_path}"

        try:
            methods = self._scan_directory(api_client_path)
            return self._format_methods(methods)

        except Exception as e:
            return f"❌ Error scanning api_client: {e}"

    def _scan_directory(self, directory: Path) -> List[Dict[str, Any]]:
        """Recursively scan directory for Python files and extract methods"""
        methods = []

        for python_file in directory.rglob("*.py"):
            if python_file.name.startswith("__"):
                continue

            file_methods = self._extract_methods_from_file(python_file)
            methods.extend(file_methods)

        return methods

    def _extract_methods_from_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract method definitions from a Python file using AST"""
        methods = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(file_path))

            for node in ast.walk(tree):
                # Look for class definitions
                if isinstance(node, ast.ClassDef):
                    class_name = node.name

                    # Look for methods in the class
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_info = {
                                "file": file_path.name,
                                "class": class_name,
                                "name": item.name,
                                "args": self._get_args(item),
                                "docstring": ast.get_docstring(item) or "No docstring",
                                "is_async": isinstance(item, ast.AsyncFunctionDef),
                            }
                            methods.append(method_info)

                # Also look for standalone functions
                elif isinstance(node, ast.FunctionDef) and not isinstance(node, ast.AsyncFunctionDef):
                    method_info = {
                        "file": file_path.name,
                        "class": None,
                        "name": node.name,
                        "args": self._get_args(node),
                        "docstring": ast.get_docstring(node) or "No docstring",
                        "is_async": False,
                    }
                    methods.append(method_info)

        except Exception as e:
            print(f"Warning: Could not parse {file_path}: {e}")

        return methods

    def _get_args(self, func_node: ast.FunctionDef) -> List[str]:
        """Extract argument names from function definition"""
        args = []
        for arg in func_node.args.args:
            if arg.arg != "self" and arg.arg != "cls":
                args.append(arg.arg)
        return args

    def _format_methods(self, methods: List[Dict[str, Any]]) -> str:
        """Format methods into human-readable output"""
        if not methods:
            return "⚠️  No methods found in api_client directory"

        output = []
        output.append(f"📂 API Client Methods Found: {len(methods)}")
        output.append("=" * 60)
        output.append("")

        # Group by file
        methods_by_file: Dict[str, List[Dict[str, Any]]] = {}
        for method in methods:
            file_name = method["file"]
            if file_name not in methods_by_file:
                methods_by_file[file_name] = []
            methods_by_file[file_name].append(method)

        for file_name, file_methods in methods_by_file.items():
            output.append(f"## {file_name}")
            output.append("")

            for method in file_methods:
                class_prefix = f"{method['class']}." if method['class'] else ""
                async_prefix = "async " if method['is_async'] else ""
                args_str = ", ".join(method['args'])

                output.append(f"  {async_prefix}{class_prefix}{method['name']}({args_str})")

                # Show first line of docstring
                docstring_lines = method['docstring'].split('\n')
                if docstring_lines:
                    first_line = docstring_lines[0].strip()
                    if first_line:
                        output.append(f"    → {first_line}")

                output.append("")

        return "\n".join(output)


class GenerateClientMethodTool(BaseTool):
    """Tool to generate missing API client methods"""

    name: str = "generate_client_method"
    description: str = (
        "Generates a new API client method based on OpenAPI specification. "
        "Creates properly typed method with docstring, error handling, and examples. "
        "Use this when a gap is detected between API spec and client implementation."
    )

    def _run(
        self,
        endpoint_path: str,
        http_method: str,
        operation_id: str,
        summary: str,
        parameters: List[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate client method code

        Args:
            endpoint_path: API endpoint path (e.g., "/api/matches/{id}")
            http_method: HTTP method (GET, POST, PUT, DELETE)
            operation_id: OpenAPI operation ID
            summary: Brief description of endpoint
            parameters: List of parameter definitions

        Returns:
            Generated Python method code
        """
        parameters = parameters or []

        # Generate method name from operation_id or path
        method_name = operation_id.replace("-", "_") if operation_id else self._path_to_method_name(endpoint_path, http_method)

        # Extract path parameters
        path_params = [p for p in parameters if p.get("in") == "path"]
        query_params = [p for p in parameters if p.get("in") == "query"]
        required_params = [p for p in parameters if p.get("required", False)]

        # Build method signature
        args = ["self"]
        for param in path_params:
            args.append(f"{param['name']}: str")
        for param in query_params:
            param_name = param['name']
            param_type = "str"  # Simplification - could infer from schema
            if param.get("required"):
                args.append(f"{param_name}: {param_type}")
            else:
                args.append(f"{param_name}: Optional[{param_type}] = None")

        args_str = ", ".join(args)

        # Build URL
        url = endpoint_path

        # Generate code
        code = f'''
    def {method_name}({args_str}) -> Dict[str, Any]:
        """
        {summary}

        Args:
{self._format_param_docs(parameters)}

        Returns:
            API response data

        Raises:
            HTTPError: If request fails

        Example:
            >>> client = APIClient()
{self._format_example(method_name, path_params, query_params)}
        """
        url = f"{{self.base_url}}{url}"

{self._format_query_params(query_params)}

        response = self.session.{http_method.lower()}(url{", params=params" if query_params else ""})
        response.raise_for_status()
        return response.json()
'''

        output = []
        output.append("🔧 Generated API Client Method:")
        output.append("=" * 60)
        output.append(code)
        output.append("")
        output.append("📝 Add this method to backend/api_client/client.py")

        return "\n".join(output)

    def _path_to_method_name(self, path: str, http_method: str) -> str:
        """Convert endpoint path to method name"""
        # /api/matches/{id}/stats -> get_match_stats
        parts = [p for p in path.split("/") if p and not p.startswith("{")]
        resource = parts[-1].replace("-", "_") if parts else "unknown"

        method_map = {
            "GET": "get",
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete",
        }

        prefix = method_map.get(http_method.upper(), http_method.lower())
        return f"{prefix}_{resource}"

    def _format_param_docs(self, parameters: List[Dict[str, Any]]) -> str:
        """Format parameter documentation"""
        if not parameters:
            return "            None"

        docs = []
        for param in parameters:
            name = param['name']
            desc = param.get('description', 'No description')
            required = " (required)" if param.get('required') else " (optional)"
            docs.append(f"            {name}: {desc}{required}")

        return "\n".join(docs)

    def _format_example(self, method_name: str, path_params: List[Dict], query_params: List[Dict]) -> str:
        """Format usage example"""
        args = []
        for param in path_params:
            args.append(f'"{param["name"]}_123"')
        for param in query_params[:2]:  # Show first 2 query params
            if param.get("required"):
                args.append(f'{param["name"]}="value"')

        args_str = ", ".join(args)
        return f'            >>> result = client.{method_name}({args_str})'

    def _format_query_params(self, query_params: List[Dict]) -> str:
        """Format query parameter handling code"""
        if not query_params:
            return ""

        lines = ["        params = {}"]
        for param in query_params:
            name = param['name']
            if param.get('required'):
                lines.append(f'        params["{name}"] = {name}')
            else:
                lines.append(f'        if {name} is not None:')
                lines.append(f'            params["{name}"] = {name}')

        return "\n".join(lines) + "\n"

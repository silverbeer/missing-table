"""
OpenAPI Tool - Reads and parses the MT backend OpenAPI specification

This tool enables the Swagger agent to:
- Fetch the OpenAPI spec from /openapi.json endpoint
- Parse endpoint definitions
- Extract request/response schemas
- Identify required parameters and validation rules
"""

import httpx
from typing import Any, Dict, List, Optional

from crewai.tools import BaseTool


class ReadOpenAPISpecTool(BaseTool):
    """Tool to read and parse OpenAPI specification from MT backend"""

    name: str = "read_openapi_spec"
    description: str = (
        "Reads the OpenAPI specification from the MT backend's /openapi.json endpoint. "
        "Returns a structured view of all available endpoints including methods, paths, "
        "parameters, request/response schemas, and descriptions. "
        "IMPORTANT: Pass only the base URL (e.g., 'http://localhost:8000'), NOT the full path. "
        "The tool will automatically append '/openapi.json' to fetch the spec."
    )

    def _run(self, base_url: str = "http://localhost:8000") -> str:
        """
        Fetch and parse OpenAPI specification

        Args:
            base_url: Base URL of the MT backend WITHOUT /openapi.json path
                     (e.g., 'http://localhost:8000' not 'http://localhost:8000/openapi.json')

        Returns:
            Formatted string with endpoint information
        """
        try:
            # Strip /openapi.json if accidentally included
            base_url = base_url.rstrip('/').replace('/openapi.json', '')
            openapi_url = f"{base_url}/openapi.json"
            response = httpx.get(openapi_url, timeout=10.0)
            response.raise_for_status()

            spec = response.json()
            return self._format_spec(spec)

        except httpx.HTTPError as e:
            return f"❌ Error fetching OpenAPI spec: {e}"
        except Exception as e:
            return f"❌ Unexpected error: {e}"

    def _format_spec(self, spec: Dict[str, Any]) -> str:
        """Format OpenAPI spec into human-readable text"""
        output = []
        output.append(f"📚 OpenAPI Specification: {spec.get('info', {}).get('title', 'Unknown')}")
        output.append(
            f"📚 Version: {spec.get('info', {}).get('version', 'Unknown')}"
        )
        output.append("")

        paths = spec.get("paths", {})
        output.append(f"📚 Total endpoints found: {self._count_endpoints(paths)}")
        output.append("")

        # Group endpoints by tag/category
        endpoints_by_tag = self._group_by_tag(paths)

        for tag, endpoints in endpoints_by_tag.items():
            output.append(f"## {tag}")
            for endpoint in endpoints:
                output.append(self._format_endpoint(endpoint))
            output.append("")

        return "\n".join(output)

    def _count_endpoints(self, paths: Dict[str, Any]) -> int:
        """Count total endpoints across all paths"""
        count = 0
        for path_item in paths.values():
            count += len([m for m in path_item.keys() if m in ["get", "post", "put", "delete", "patch"]])
        return count

    def _group_by_tag(self, paths: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Group endpoints by their OpenAPI tags"""
        endpoints_by_tag: Dict[str, List[Dict[str, Any]]] = {}

        for path, path_item in paths.items():
            for method in ["get", "post", "put", "delete", "patch"]:
                if method not in path_item:
                    continue

                operation = path_item[method]
                tags = operation.get("tags", ["untagged"])
                tag = tags[0] if tags else "untagged"

                if tag not in endpoints_by_tag:
                    endpoints_by_tag[tag] = []

                endpoints_by_tag[tag].append({
                    "path": path,
                    "method": method.upper(),
                    "operation": operation
                })

        return endpoints_by_tag

    def _format_endpoint(self, endpoint: Dict[str, Any]) -> str:
        """Format a single endpoint for display"""
        method = endpoint["method"]
        path = endpoint["path"]
        operation = endpoint["operation"]

        summary = operation.get("summary", "No description")
        operation_id = operation.get("operationId", "unknown")

        # Extract parameters
        params = operation.get("parameters", [])
        required_params = [p["name"] for p in params if p.get("required", False)]

        output = f"  {method:6} {path:40} - {summary}"
        if operation_id:
            output += f"\n         operation_id: {operation_id}"
        if required_params:
            output += f"\n         required: {', '.join(required_params)}"

        return output


class DetectGapsTool(BaseTool):
    """Tool to detect gaps between API spec, api_client, and tests"""

    name: str = "detect_gaps"
    description: str = (
        "Compares the OpenAPI specification against the api_client implementation "
        "and test coverage to detect gaps. Returns a list of endpoints that are "
        "missing client methods or test coverage."
    )

    def _run(
        self,
        openapi_endpoints: List[str],
        api_client_methods: List[str],
        test_coverage: List[str]
    ) -> str:
        """
        Detect gaps in coverage

        Args:
            openapi_endpoints: List of endpoint paths from OpenAPI spec
            api_client_methods: List of method names in api_client
            test_coverage: List of tested endpoint paths

        Returns:
            Formatted gap report
        """
        output = []
        output.append("🔍 Gap Detection Report")
        output.append("=" * 50)
        output.append("")

        # Find endpoints without client methods
        missing_client = []
        for endpoint in openapi_endpoints:
            # Convert endpoint path to expected method name
            # e.g., "GET /api/matches" -> "get_matches"
            # This is a simplified heuristic
            if not any(self._endpoint_matches_method(endpoint, method) for method in api_client_methods):
                missing_client.append(endpoint)

        # Find endpoints without tests
        missing_tests = []
        for endpoint in openapi_endpoints:
            if endpoint not in test_coverage:
                missing_tests.append(endpoint)

        # Report results
        if missing_client:
            output.append(f"⚠️  {len(missing_client)} endpoints missing in api_client:")
            for endpoint in missing_client[:10]:  # Show first 10
                output.append(f"   - {endpoint}")
            if len(missing_client) > 10:
                output.append(f"   ... and {len(missing_client) - 10} more")
        else:
            output.append("✅ All endpoints have api_client methods")

        output.append("")

        if missing_tests:
            output.append(f"⚠️  {len(missing_tests)} endpoints without test coverage:")
            for endpoint in missing_tests[:10]:  # Show first 10
                output.append(f"   - {endpoint}")
            if len(missing_tests) > 10:
                output.append(f"   ... and {len(missing_tests) - 10} more")
        else:
            output.append("✅ All endpoints have test coverage")

        output.append("")
        output.append(f"📊 Summary:")
        output.append(f"   Total endpoints: {len(openapi_endpoints)}")
        output.append(f"   Missing client methods: {len(missing_client)}")
        output.append(f"   Missing tests: {len(missing_tests)}")
        output.append(f"   Coverage: {((len(openapi_endpoints) - len(missing_tests)) / len(openapi_endpoints) * 100):.1f}%")

        return "\n".join(output)

    def _endpoint_matches_method(self, endpoint: str, method_name: str) -> bool:
        """
        Check if an endpoint matches a client method name

        This is a heuristic - you may need to adjust based on your naming conventions
        """
        # Simple heuristic: convert "GET /api/matches" to "get_matches"
        parts = endpoint.lower().split()
        if len(parts) < 2:
            return False

        http_method = parts[0]
        path = parts[1]

        # Extract resource name from path
        # /api/matches/{id} -> matches
        path_parts = [p for p in path.split("/") if p and not p.startswith("{")]
        if not path_parts:
            return False

        resource = path_parts[-1].replace("-", "_")

        # Generate expected method names
        expected_names = [
            f"{http_method}_{resource}",
            f"{http_method}_{resource}_by_id",
            resource,
            f"get_{resource}",
            f"create_{resource}",
            f"update_{resource}",
            f"delete_{resource}",
        ]

        return any(name in method_name.lower() for name in expected_names)

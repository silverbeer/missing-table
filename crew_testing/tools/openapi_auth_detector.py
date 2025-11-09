"""
OpenAPI Auth Detector Tool

Detects authentication requirements from OpenAPI specification.
Used by FORGE to determine if generated tests need authentication.
"""

import json
from typing import Any, Dict, Optional, Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class OpenAPIAuthDetectorInput(BaseModel):
    """Input for OpenAPIAuthDetector tool."""

    endpoint: str = Field(..., description="API endpoint path (e.g., '/api/matches')")
    backend_url: str = Field(
        default="http://localhost:8000", description="Base URL of MT backend"
    )


class OpenAPIAuthDetectorTool(BaseTool):
    """
    Tool to detect if an endpoint requires authentication from OpenAPI spec.

    Checks the OpenAPI specification to see if an endpoint has security requirements.
    Returns information about what type of authentication is needed.
    """

    name: str = "openapi_auth_detector"
    description: str = (
        "Detects if an API endpoint requires authentication by checking the OpenAPI spec. "
        "Returns auth type (HTTPBearer, etc.) and whether auth is required. "
        "Use this BEFORE generating tests to determine if you need to add auth headers."
    )
    args_schema: Type[BaseModel] = OpenAPIAuthDetectorInput

    def _run(self, endpoint: str, backend_url: str = "http://localhost:8000") -> str:
        """
        Check if an endpoint requires authentication

        Args:
            endpoint: API endpoint path (e.g., '/api/matches')
            backend_url: Base URL of MT backend

        Returns:
            JSON string with auth requirements
        """
        try:
            # Fetch OpenAPI spec
            openapi_url = f"{backend_url}/openapi.json"
            response = httpx.get(openapi_url, timeout=5.0)
            response.raise_for_status()
            spec = response.json()

            # Find the endpoint in the spec
            path_item = spec.get("paths", {}).get(endpoint)
            if not path_item:
                return json.dumps({
                    "requires_auth": False,
                    "auth_type": None,
                    "error": f"Endpoint {endpoint} not found in OpenAPI spec",
                })

            # Check all HTTP methods for this endpoint
            methods = ["get", "post", "put", "patch", "delete"]
            auth_required = False
            auth_types = set()

            for method in methods:
                operation = path_item.get(method)
                if operation and "security" in operation:
                    # Endpoint has security requirements
                    auth_required = True
                    for security_req in operation["security"]:
                        # security_req is like {"HTTPBearer": []}
                        auth_types.update(security_req.keys())

            if auth_required:
                return json.dumps({
                    "requires_auth": True,
                    "auth_type": list(auth_types)[0] if auth_types else "HTTPBearer",
                    "message": f"Endpoint {endpoint} requires authentication",
                    "fixture_needed": "auth_headers",
                    "example": {
                        "fixture": '@pytest.fixture\ndef auth_headers():\n    """Mock authentication headers for testing."""\n    return {"Authorization": "Bearer mock_token_for_testing"}',
                        "usage": 'response = client.get("/api/matches", headers=auth_headers)',
                    }
                })
            else:
                return json.dumps({
                    "requires_auth": False,
                    "auth_type": None,
                    "message": f"Endpoint {endpoint} does not require authentication",
                })

        except Exception as e:
            return json.dumps({
                "requires_auth": False,
                "auth_type": None,
                "error": f"Failed to check auth requirements: {str(e)}",
            })


# Export for tool registration
__all__ = ["OpenAPIAuthDetectorTool"]

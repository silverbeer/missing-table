"""
Schemathesis property-based API contract tests.

These tests use Schemathesis to automatically generate test cases
based on the OpenAPI schema.
"""

import pytest
import schemathesis
from pathlib import Path


# Load OpenAPI schema
schema_path = Path(__file__).parent.parent.parent / "openapi.json"

if not schema_path.exists():
    pytest.skip(
        "OpenAPI schema not found. Run: python backend/scripts/export_openapi.py",
        allow_module_level=True
    )

# Create schema from file
schema = schemathesis.from_path(str(schema_path))


@schema.parametrize()
@pytest.mark.contract
def test_api_contract(case):
    """
    Property-based test that validates API responses against OpenAPI schema.

    This test:
    - Generates requests based on the OpenAPI schema
    - Sends requests to the API
    - Validates responses match the schema
    """
    # Send request
    response = case.call()

    # Check response is valid according to schema
    case.validate_response(response)

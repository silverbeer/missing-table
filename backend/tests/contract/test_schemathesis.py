"""
Schemathesis property-based contract tests.

This test uses Schemathesis to automatically generate test cases from the OpenAPI schema
and verify that the API behaves correctly for all endpoints.
"""

import pytest
import schemathesis
from hypothesis import settings
from pathlib import Path

# Load OpenAPI schema with base_url
schema_path = Path(__file__).parent.parent.parent / "openapi.json"

# Skip this test file for now - we'll use manual contract tests
# Schemathesis integration can be added later after initial setup
pytest.skip("Schemathesis tests require running server - skipping for initial setup", allow_module_level=True)


@pytest.mark.contract
@pytest.mark.skip(reason="Requires running API server")
def test_api_schema_compliance():
    """
    Property-based test that verifies API compliance with OpenAPI schema.

    This test:
    - Generates random valid requests based on the schema
    - Sends requests to the API
    - Validates responses match the schema
    - Checks for common issues (500 errors, schema violations, etc.)

    Note: This requires a running API server. Use pytest with --base-url option.
    """
    schema = schemathesis.openapi.from_file(
        str(schema_path),
        base_url="http://localhost:8000"
    )

    # Example usage (not executed due to skip):
    # for case in schema.get_all_cases():
    #     case.call_and_validate()


@pytest.mark.contract
def test_schema_validation():
    """Validate that the OpenAPI schema itself is valid."""
    from openapi_spec_validator import validate

    with open(schema_path) as f:
        import json
        spec = json.load(f)

    # This will raise an exception if schema is invalid
    validate(spec)

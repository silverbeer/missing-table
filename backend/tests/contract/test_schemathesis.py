"""
Schemathesis property-based contract tests.

This test uses Schemathesis to automatically generate test cases from the OpenAPI schema
and verify that the API behaves correctly for all endpoints.
"""

import pytest
import schemathesis
from hypothesis import settings
from pathlib import Path

# Load OpenAPI schema
schema_path = Path(__file__).parent.parent.parent / "openapi.json"
schema = schemathesis.from_path(str(schema_path))


# Configure hypothesis settings for property-based testing
@settings(max_examples=50, deadline=5000)
@schema.parametrize()
@pytest.mark.contract
def test_api_schema_compliance(case):
    """
    Property-based test that verifies API compliance with OpenAPI schema.

    This test:
    - Generates random valid requests based on the schema
    - Sends requests to the API
    - Validates responses match the schema
    - Checks for common issues (500 errors, schema violations, etc.)
    """
    # Schemathesis will automatically:
    # - Generate valid request data based on schema
    # - Make the HTTP request
    # - Validate response against schema
    # - Check response status codes
    # - Detect schema violations
    case.call_and_validate()


@pytest.mark.contract
def test_schema_validation():
    """Validate that the OpenAPI schema itself is valid."""
    from openapi_spec_validator import validate

    with open(schema_path) as f:
        import json
        spec = json.load(f)

    # This will raise an exception if schema is invalid
    validate(spec)

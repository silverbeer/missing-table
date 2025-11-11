"""
Schemathesis property-based API contract tests.

These tests use Schemathesis to automatically generate test cases
based on the OpenAPI schema.

NOTE: This test is currently disabled due to schemathesis API changes.
TODO: Update to use correct schemathesis 4.x API (from_uri or openapi.from_path)
"""

import pytest
from pathlib import Path


# Temporarily skip this test file until schemathesis API is fixed
pytest.skip(
    "Schemathesis tests temporarily disabled - API needs update for schemathesis 4.x",
    allow_module_level=True
)


# Load OpenAPI schema
schema_path = Path(__file__).parent.parent.parent / "openapi.json"

if not schema_path.exists():
    pytest.skip(
        "OpenAPI schema not found. Run: python backend/scripts/export_openapi.py",
        allow_module_level=True
    )

# TODO: Fix schemathesis API usage
# Old API (3.x): schemathesis.from_path(str(schema_path))
# New API (4.x): Need to investigate correct method
# Possible: schemathesis.from_uri() or schemathesis.openapi.from_file()

# @schema.parametrize()
# @pytest.mark.contract
# def test_api_contract(case):
#     """
#     Property-based test that validates API responses against OpenAPI schema.
#
#     This test:
#     - Generates requests based on the OpenAPI schema
#     - Sends requests to the API
#     - Validates responses match the schema
#     """
#     # Send request
#     response = case.call()
#
#     # Check response is valid according to schema
#     case.validate_response(response)

#!/usr/bin/env python3
"""
Export OpenAPI schema from FastAPI application.

This script exports the OpenAPI schema to a JSON file for API contract testing.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path to import app
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from app import app
except ImportError as e:
    print(f"Error importing app: {e}")
    print("Make sure you're running this from the backend directory with dependencies installed")
    sys.exit(1)


def export_openapi_schema(output_file: str = "openapi.json"):
    """Export OpenAPI schema to JSON file."""
    try:
        # Get OpenAPI schema from FastAPI app
        openapi_schema = app.openapi()

        # Write to file
        output_path = Path(output_file)
        with open(output_path, 'w') as f:
            json.dump(openapi_schema, f, indent=2)

        print(f"✅ OpenAPI schema exported to {output_path}")
        print(f"   Title: {openapi_schema.get('info', {}).get('title')}")
        print(f"   Version: {openapi_schema.get('info', {}).get('version')}")
        print(f"   Endpoints: {len(openapi_schema.get('paths', {}))}")

        return True

    except Exception as e:
        print(f"❌ Error exporting OpenAPI schema: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export OpenAPI schema from FastAPI app")
    parser.add_argument(
        "--output",
        "-o",
        default="openapi.json",
        help="Output file path (default: openapi.json)"
    )

    args = parser.parse_args()

    success = export_openapi_schema(args.output)
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""Export OpenAPI schema to JSON file without logging interference."""

import json
import logging
import sys
from pathlib import Path

# Disable all logging before importing app
logging.disable(logging.CRITICAL)

# Suppress print statements from app initialization
import io
import contextlib

# Redirect stdout temporarily during import
with contextlib.redirect_stdout(io.StringIO()):
    from app import app

# Re-enable stdout
sys.stdout = sys.__stdout__

# Export OpenAPI schema
schema = app.openapi()
output_file = Path(__file__).parent.parent / "openapi.json"

with open(output_file, "w") as f:
    json.dump(schema, f, indent=2)

print(f"✅ Exported OpenAPI schema to {output_file}", file=sys.stderr)

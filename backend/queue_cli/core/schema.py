"""
Schema validation and translation for match messages.

Handles validation against the canonical schema and translation
between the external schema (match-scraper) and internal schema (celery tasks).
"""

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import ValidationError


class SchemaValidator:
    """Validates and translates match message schemas."""

    # Field name mappings from canonical schema to internal schema
    FIELD_MAPPINGS = {
        "date": "match_date",
        "score_home": "home_score",
        "score_away": "away_score",
        "status": "match_status",
        "match_id": "external_match_id",
    }

    def __init__(self, schema_path: str | None = None):
        """
        Initialize schema validator.

        Args:
            schema_path: Path to JSON schema file. If None, uses default schema.
        """
        if schema_path is None:
            # Default to canonical schema in docs
            schema_path = str(
                Path(__file__).parent.parent.parent.parent / "docs" / "08-integrations" / "match-message-schema.json"
            )

        with open(schema_path) as f:
            self.schema = json.load(f)

    def validate(self, data: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
        """
        Validate data against schema.

        Args:
            data: Data to validate

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []

        try:
            jsonschema.validate(instance=data, schema=self.schema)
        except ValidationError as e:
            errors.append(f"Schema validation failed: {e.message}")
            return False, errors, warnings

        # Check for fields that need translation
        for canonical_field, internal_field in self.FIELD_MAPPINGS.items():
            if canonical_field in data and internal_field in data:
                warnings.append(f"Both '{canonical_field}' and '{internal_field}' present. Using '{internal_field}'.")

        return True, errors, warnings

    def translate_to_internal(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Translate from canonical schema (match-scraper) to internal schema (celery tasks).

        Args:
            data: Data in canonical schema format

        Returns:
            Data in internal schema format
        """
        result = data.copy()

        for canonical_field, internal_field in self.FIELD_MAPPINGS.items():
            if canonical_field in result and internal_field not in result:
                result[internal_field] = result[canonical_field]

        return result

    def translate_to_canonical(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Translate from internal schema (celery tasks) to canonical schema (match-scraper).

        Args:
            data: Data in internal schema format

        Returns:
            Data in canonical schema format
        """
        result = data.copy()

        # Reverse mapping
        reverse_mappings = {v: k for k, v in self.FIELD_MAPPINGS.items()}

        for internal_field, canonical_field in reverse_mappings.items():
            if internal_field in result and canonical_field not in result:
                result[canonical_field] = result[internal_field]

        return result

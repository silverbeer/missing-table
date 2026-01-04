"""
YAML-Driven Model Validation Tests

This module dynamically generates pytest tests from YAML specification files,
enabling non-developers to add test cases without writing Python code.

For qualityplaybook.dev: Demonstrates innovative data-driven testing where
test specifications are externalized to human-readable YAML files. QA engineers
and product managers can contribute test cases without Python knowledge.

Features:
- External test specifications in human-readable YAML
- Automatic test generation using pytest parametrization
- Support for testing Pydantic validators
- Clear error messages with context
- Self-documenting test structure

Usage:
    pytest tests/unit/test_model_validation_yaml.py -v
    pytest tests/unit/test_model_validation_yaml.py -k "username" -v
    pytest tests/unit/test_model_validation_yaml.py -k "valid" -v
    pytest tests/unit/test_model_validation_yaml.py -k "invalid" -v
"""

import pytest
import allure
import yaml
from pathlib import Path
from typing import Any, Dict, List, Tuple
from pydantic import ValidationError

import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from models.auth import (
    UserSignup,
    UserLogin,
    ProfilePhotoSlot,
    PlayerCustomization,
    PlayerHistoryCreate,
    PlayerHistoryUpdate,
    AdminPlayerUpdate,
    AdminPlayerTeamAssignment,
)

# ============================================================================
# Model Registry - Maps model names from YAML to Python classes
# ============================================================================

MODEL_REGISTRY = {
    "UserSignup": UserSignup,
    "UserLogin": UserLogin,
    "ProfilePhotoSlot": ProfilePhotoSlot,
    "PlayerCustomization": PlayerCustomization,
    "PlayerHistoryCreate": PlayerHistoryCreate,
    "PlayerHistoryUpdate": PlayerHistoryUpdate,
    "AdminPlayerUpdate": AdminPlayerUpdate,
    "AdminPlayerTeamAssignment": AdminPlayerTeamAssignment,
}

# Path to validation specs
VALIDATION_SPECS_DIR = Path(__file__).parent.parent / "fixtures" / "data" / "validation_specs"


def load_yaml_spec(filename: str) -> Dict[str, Any]:
    """Load a YAML validation specification file."""
    filepath = VALIDATION_SPECS_DIR / filename
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)


def discover_spec_files() -> List[Path]:
    """Discover all YAML spec files in the validation_specs directory."""
    if not VALIDATION_SPECS_DIR.exists():
        return []
    return sorted([f for f in VALIDATION_SPECS_DIR.glob("*.yaml") if f.name != "schema.yaml"])


def generate_valid_test_cases() -> List[Tuple]:
    """
    Generate pytest test cases for valid inputs from all YAML spec files.

    Returns:
        List of tuples: (spec_file, model_name, field_name, case_data, case_id)
    """
    test_cases = []

    for spec_file in discover_spec_files():
        spec = load_yaml_spec(spec_file.name)
        model_name = spec.get("model")
        field_name = spec.get("field")

        # Generate valid cases
        for i, case in enumerate(spec.get("valid_cases", [])):
            desc = case.get("description", f"case_{i}").replace(" ", "_").replace("(", "").replace(")", "")[:30]
            case_id = f"{spec_file.stem}_{field_name}_valid_{desc}"
            test_cases.append((
                spec_file.name,
                model_name,
                field_name,
                case,
                case_id
            ))

    return test_cases


def generate_invalid_test_cases() -> List[Tuple]:
    """
    Generate pytest test cases for invalid inputs from all YAML spec files.

    Returns:
        List of tuples: (spec_file, model_name, field_name, case_data, case_id)
    """
    test_cases = []

    for spec_file in discover_spec_files():
        spec = load_yaml_spec(spec_file.name)
        model_name = spec.get("model")
        field_name = spec.get("field")

        # Generate invalid cases
        for i, case in enumerate(spec.get("invalid_cases", [])):
            desc = case.get("description", f"case_{i}").replace(" ", "_").replace("(", "").replace(")", "")[:30]
            case_id = f"{spec_file.stem}_{field_name}_invalid_{desc}"
            test_cases.append((
                spec_file.name,
                model_name,
                field_name,
                case,
                case_id
            ))

    return test_cases


# Collect test cases at module load time
VALID_TEST_CASES = generate_valid_test_cases()
INVALID_TEST_CASES = generate_invalid_test_cases()


def build_model_data(model_class, target_field: str, target_value: Any) -> Dict[str, Any]:
    """
    Build minimum required data for a Pydantic model.

    Provides default values for required fields so we can test
    specific field validation in isolation.
    """
    # Default values for required fields by model
    defaults = {
        "UserSignup": {
            "username": "testuser",
            "password": "TestPassword123!",
        },
        "UserLogin": {
            "username": "testuser",
            "password": "TestPassword123!",
        },
        "ProfilePhotoSlot": {
            "slot": 1,
        },
        "PlayerCustomization": {
            # All fields optional
        },
        "PlayerHistoryCreate": {
            "team_id": 1,
            "season_id": 1,
        },
        "PlayerHistoryUpdate": {
            # All fields optional
        },
        "AdminPlayerUpdate": {
            # All fields optional
        },
        "AdminPlayerTeamAssignment": {
            "team_id": 1,
            "season_id": 1,
        },
    }

    model_name = model_class.__name__
    data = defaults.get(model_name, {}).copy()
    data[target_field] = target_value

    return data


@pytest.mark.unit
@pytest.mark.data_driven
@allure.suite("Parameterized Tests")
@allure.sub_suite("YAML-Driven Validation")
@allure.feature("Data-Driven Testing")
class TestYAMLDrivenValidation:
    """
    YAML-driven Pydantic model validation tests.

    Test cases are loaded from YAML files in:
    tests/fixtures/data/validation_specs/

    To add new test cases:
    1. Edit the appropriate YAML file
    2. Add entries to valid_cases or invalid_cases
    3. Run pytest - new cases are automatically discovered

    For qualityplaybook.dev: This pattern enables QA/Dev collaboration
    by separating test data (YAML) from test logic (Python).
    """

    @pytest.mark.parametrize(
        "spec_file,model_name,field_name,case_data,case_id",
        VALID_TEST_CASES,
        ids=lambda x: x if isinstance(x, str) else None
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.story("Valid Input Acceptance")
    def test_valid_input(
        self,
        spec_file: str,
        model_name: str,
        field_name: str,
        case_data: Dict[str, Any],
        case_id: str
    ):
        """Test that valid inputs pass validation and transform correctly."""
        # Get the model class
        model_class = MODEL_REGISTRY.get(model_name)
        assert model_class is not None, f"Unknown model: {model_name}"

        input_value = case_data.get("input")
        expected_value = case_data.get("expected", input_value)
        description = case_data.get("description", "No description")

        # Build minimum required data for the model
        model_data = build_model_data(model_class, field_name, input_value)

        # Act - create model instance (should not raise)
        try:
            instance = model_class(**model_data)
            actual_value = getattr(instance, field_name)

            # Assert
            assert actual_value == expected_value, (
                f"\n{'='*60}\n"
                f"YAML SPEC: {spec_file}\n"
                f"{'='*60}\n"
                f"Field: {model_name}.{field_name}\n"
                f"Description: {description}\n"
                f"\nInput: {repr(input_value)}\n"
                f"Expected: {repr(expected_value)}\n"
                f"Actual: {repr(actual_value)}\n"
                f"{'='*60}"
            )
        except ValidationError as e:
            pytest.fail(
                f"\n{'='*60}\n"
                f"UNEXPECTED VALIDATION FAILURE\n"
                f"{'='*60}\n"
                f"YAML Spec: {spec_file}\n"
                f"Field: {model_name}.{field_name}\n"
                f"Description: {description}\n"
                f"\nInput: {repr(input_value)}\n"
                f"Expected: Valid input should pass\n"
                f"\nValidation Error:\n{e}\n"
                f"{'='*60}"
            )

    @pytest.mark.parametrize(
        "spec_file,model_name,field_name,case_data,case_id",
        INVALID_TEST_CASES,
        ids=lambda x: x if isinstance(x, str) else None
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.story("Invalid Input Rejection")
    def test_invalid_input(
        self,
        spec_file: str,
        model_name: str,
        field_name: str,
        case_data: Dict[str, Any],
        case_id: str
    ):
        """Test that invalid inputs fail validation with expected error."""
        # Get the model class
        model_class = MODEL_REGISTRY.get(model_name)
        assert model_class is not None, f"Unknown model: {model_name}"

        input_value = case_data.get("input")
        error_contains = case_data.get("error_contains", "")
        description = case_data.get("description", "No description")

        # Build minimum required data for the model
        model_data = build_model_data(model_class, field_name, input_value)

        # Act & Assert - should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            model_class(**model_data)

        # Verify error message contains expected substring
        error_message = str(exc_info.value).lower()
        assert error_contains.lower() in error_message, (
            f"\n{'='*60}\n"
            f"ERROR MESSAGE MISMATCH\n"
            f"{'='*60}\n"
            f"YAML Spec: {spec_file}\n"
            f"Field: {model_name}.{field_name}\n"
            f"Description: {description}\n"
            f"\nInput: {repr(input_value)}\n"
            f"Expected error to contain: '{error_contains}'\n"
            f"\nActual error:\n{exc_info.value}\n"
            f"{'='*60}"
        )


@pytest.mark.unit
@allure.suite("Parameterized Tests")
@allure.sub_suite("YAML-Driven Validation")
@allure.feature("Test Quality")
@allure.story("YAML Specification Discovery")
class TestYAMLSpecDiscovery:
    """Meta-tests to verify YAML spec discovery and structure."""

    @allure.severity(allure.severity_level.MINOR)
    def test_yaml_specs_directory_exists(self):
        """Verify the validation specs directory exists."""
        assert VALIDATION_SPECS_DIR.exists(), (
            f"Validation specs directory not found: {VALIDATION_SPECS_DIR}"
        )

    def test_yaml_specs_discovered(self):
        """Verify YAML spec files are discovered."""
        spec_files = discover_spec_files()
        assert len(spec_files) > 0, "No YAML spec files found"
        print(f"\nDiscovered {len(spec_files)} YAML spec files:")
        for f in spec_files:
            print(f"  - {f.name}")

    def test_yaml_spec_structure(self):
        """Verify all YAML specs have required structure."""
        for spec_file in discover_spec_files():
            spec = load_yaml_spec(spec_file.name)

            # Check required fields
            assert "model" in spec, f"{spec_file.name}: missing 'model'"
            assert "field" in spec, f"{spec_file.name}: missing 'field'"
            assert spec["model"] in MODEL_REGISTRY, (
                f"{spec_file.name}: unknown model '{spec['model']}'"
            )

            valid_cases = spec.get("valid_cases", [])
            invalid_cases = spec.get("invalid_cases", [])

            assert len(valid_cases) + len(invalid_cases) > 0, (
                f"{spec_file.name}: must have at least one test case"
            )

            # Validate case structure
            for i, case in enumerate(valid_cases):
                assert "input" in case or case.get("input") is None, (
                    f"{spec_file.name}: valid_cases[{i}] missing 'input'"
                )

            for i, case in enumerate(invalid_cases):
                assert "input" in case or case.get("input") is None, (
                    f"{spec_file.name}: invalid_cases[{i}] missing 'input'"
                )
                assert "error_contains" in case, (
                    f"{spec_file.name}: invalid_cases[{i}] missing 'error_contains'"
                )

    def test_all_models_in_registry_exist(self):
        """Verify all registered models can be imported."""
        for model_name, model_class in MODEL_REGISTRY.items():
            assert model_class is not None, f"Model {model_name} is None"
            assert hasattr(model_class, '__name__'), f"Model {model_name} is not a class"


@pytest.mark.unit
@allure.suite("Parameterized Tests")
@allure.sub_suite("YAML-Driven Validation")
@allure.feature("Test Quality")
@allure.story("Coverage Metrics")
class TestYAMLSpecCoverage:
    """Coverage metrics for YAML specifications."""

    @allure.severity(allure.severity_level.MINOR)
    def test_print_coverage_summary(self):
        """Print test case coverage summary."""
        total_valid = len(VALID_TEST_CASES)
        total_invalid = len(INVALID_TEST_CASES)

        print(f"\n{'='*60}")
        print("YAML-DRIVEN TEST COVERAGE SUMMARY")
        print(f"{'='*60}")
        print(f"Total valid test cases: {total_valid}")
        print(f"Total invalid test cases: {total_invalid}")
        print(f"Total test cases: {total_valid + total_invalid}")
        print(f"\nBy specification file:")

        for spec_file in discover_spec_files():
            spec = load_yaml_spec(spec_file.name)
            valid = len(spec.get("valid_cases", []))
            invalid = len(spec.get("invalid_cases", []))
            print(f"  {spec_file.name}: {valid} valid, {invalid} invalid")

        print(f"{'='*60}")

        # This test always passes - it's for documentation
        assert True


# ============================================================================
# Documentation Helper
# ============================================================================

def print_all_test_cases():
    """Print all test cases for documentation."""
    print("\n" + "=" * 80)
    print("YAML-DRIVEN VALIDATION TEST CASES")
    print("=" * 80)

    for spec_file in discover_spec_files():
        spec = load_yaml_spec(spec_file.name)
        model = spec.get("model")
        field = spec.get("field")

        print(f"\n{spec_file.name}")
        print(f"  Model: {model}")
        print(f"  Field: {field}")
        print(f"  Description: {spec.get('description', 'N/A')[:100]}")

        print("  Valid cases:")
        for case in spec.get("valid_cases", []):
            desc = case.get("description", "No description")
            print(f"    - {desc}: input={repr(case.get('input'))}")

        print("  Invalid cases:")
        for case in spec.get("invalid_cases", []):
            desc = case.get("description", "No description")
            print(f"    - {desc}: input={repr(case.get('input'))}")


if __name__ == "__main__":
    print_all_test_cases()

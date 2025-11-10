"""
State Manager for CrewAI Testing System

Manages test manifest (version controlled) and runtime cache (local).
Tracks OpenAPI spec changes to avoid unnecessary test regeneration.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

import yaml


@dataclass
class ChangeReport:
    """Report of OpenAPI spec changes"""
    changed: bool
    reason: str  # "spec_unchanged" | "endpoint_unchanged" | "endpoint_changed"
    changes: Optional[Dict[str, Any]] = None


class TestStateManager:
    """
    Manages test state across runs

    - Manifest (YAML): Version controlled, team-shared test registry
    - Cache (JSON): Local runtime data, not version controlled
    """

    MANIFEST_FILE = Path("crew_testing/test_manifest.yml")
    CACHE_FILE = Path("crew_testing/.test_cache.json")
    OPENAPI_SPEC = Path("backend/openapi.json")

    def __init__(self):
        """Initialize state manager"""
        self.manifest = self._load_manifest()
        self.cache = self._load_cache()

    # =========================================================================
    # Manifest Operations (Version Controlled)
    # =========================================================================

    def _load_manifest(self) -> Dict[str, Any]:
        """Load test manifest from YAML file"""
        if not self.MANIFEST_FILE.exists():
            return self._create_empty_manifest()

        try:
            with open(self.MANIFEST_FILE, 'r') as f:
                manifest = yaml.safe_load(f) or {}

            # Validate structure
            if "version" not in manifest:
                manifest["version"] = "1.0"
            if "api_spec" not in manifest:
                manifest["api_spec"] = {}
            if "endpoints" not in manifest:
                manifest["endpoints"] = {}

            return manifest
        except Exception as e:
            print(f"Warning: Error loading manifest: {e}")
            return self._create_empty_manifest()

    def _create_empty_manifest(self) -> Dict[str, Any]:
        """Create empty manifest structure"""
        return {
            "version": "1.0",
            "api_spec": {
                "source": str(self.OPENAPI_SPEC),
                "global_hash": "",
                "last_checked": None
            },
            "endpoints": {}
        }

    def _save_manifest(self):
        """Save manifest to YAML file"""
        try:
            # Ensure directory exists
            self.MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Write atomically (write to temp, then rename)
            temp_file = self.MANIFEST_FILE.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                yaml.safe_dump(self.manifest, f, default_flow_style=False, sort_keys=False)

            temp_file.replace(self.MANIFEST_FILE)
        except Exception as e:
            print(f"Error saving manifest: {e}")

    # =========================================================================
    # Cache Operations (Local Runtime Data)
    # =========================================================================

    def _load_cache(self) -> Dict[str, Any]:
        """Load runtime cache from JSON file"""
        if not self.CACHE_FILE.exists():
            return {}

        try:
            with open(self.CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Error loading cache: {e}")
            return {}

    def _save_cache(self):
        """Save cache to JSON file"""
        try:
            # Ensure directory exists
            self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Write atomically
            temp_file = self.CACHE_FILE.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.cache, f, indent=2)

            temp_file.replace(self.CACHE_FILE)
        except Exception as e:
            print(f"Error saving cache: {e}")

    # =========================================================================
    # Test Registration and Lookup
    # =========================================================================

    def test_exists(self, endpoint: str) -> bool:
        """Check if test exists in manifest"""
        return endpoint in self.manifest["endpoints"]

    def get_test_file(self, endpoint: str) -> Optional[str]:
        """Get test file path from manifest"""
        if not self.test_exists(endpoint):
            return None
        return self.manifest["endpoints"][endpoint].get("test_file")

    def register_test(self, endpoint: str, test_file: str, endpoint_hash: str):
        """
        Register new test in manifest

        Args:
            endpoint: API endpoint (e.g., "/api/version")
            test_file: Path to test file (e.g., "backend/tests/test_version.py")
            endpoint_hash: Hash of endpoint definition
        """
        self.manifest["endpoints"][endpoint] = {
            "test_file": test_file,
            "endpoint_hash": endpoint_hash,
            "generated_at": datetime.now().isoformat(),
            "generated_by": "crew_phase2_v1.0"
        }

        # Update global spec hash
        try:
            global_hash = self._hash_global_spec()
            self.manifest["api_spec"]["global_hash"] = global_hash
            self.manifest["api_spec"]["last_checked"] = datetime.now().isoformat()
        except Exception:
            pass  # Continue even if spec hashing fails

        self._save_manifest()

    def update_test_results(self, endpoint: str, results: Dict[str, Any]):
        """
        Update runtime cache with test results

        Args:
            endpoint: API endpoint
            results: Test results dict with keys: total, passed, failed, duration_ms
        """
        self.cache[endpoint] = {
            "last_run": datetime.now().isoformat(),
            "status": "passing" if results.get("failed", 0) == 0 else "failing",
            "test_count": results.get("total", 0),
            "pass_count": results.get("passed", 0),
            "fail_count": results.get("failed", 0),
            "duration_ms": results.get("duration_ms", 0)
        }
        self._save_cache()

    # =========================================================================
    # OpenAPI Spec Change Detection
    # =========================================================================

    def check_spec_changes(self, endpoint: str) -> ChangeReport:
        """
        Check if OpenAPI spec changed since test was generated

        Args:
            endpoint: API endpoint to check

        Returns:
            ChangeReport with changed status and details
        """
        if not self.test_exists(endpoint):
            return ChangeReport(
                changed=True,
                reason="test_not_found",
                changes={"message": "No test found for this endpoint"}
            )

        try:
            # Quick global check first
            current_global_hash = self._hash_global_spec()
            stored_global_hash = self.manifest["api_spec"].get("global_hash", "")

            if current_global_hash == stored_global_hash and stored_global_hash:
                # Spec hasn't changed at all
                return ChangeReport(
                    changed=False,
                    reason="spec_unchanged"
                )

            # Global hash changed - check if THIS endpoint changed
            current_endpoint_hash = self.hash_endpoint_definition(endpoint)
            stored_endpoint_hash = self.manifest["endpoints"][endpoint].get("endpoint_hash", "")

            if current_endpoint_hash == stored_endpoint_hash:
                # This endpoint unchanged (other endpoints changed)
                return ChangeReport(
                    changed=False,
                    reason="endpoint_unchanged"
                )

            # This endpoint changed
            return ChangeReport(
                changed=True,
                reason="endpoint_changed",
                changes={"message": "Endpoint definition changed since last generation"}
            )

        except Exception as e:
            # If we can't determine changes, assume changed (safe default)
            return ChangeReport(
                changed=True,
                reason="error_checking",
                changes={"error": str(e)}
            )

    def _hash_global_spec(self) -> str:
        """Hash entire OpenAPI spec"""
        if not self.OPENAPI_SPEC.exists():
            return ""

        try:
            with open(self.OPENAPI_SPEC, 'r') as f:
                spec_content = f.read()
            return hashlib.sha256(spec_content.encode()).hexdigest()[:16]
        except Exception:
            return ""

    def hash_endpoint_definition(self, endpoint: str) -> str:
        """
        Hash just the test-relevant parts of an endpoint definition

        Args:
            endpoint: API endpoint (e.g., "/api/version")

        Returns:
            Hash string (16 chars)
        """
        if not self.OPENAPI_SPEC.exists():
            return ""

        try:
            with open(self.OPENAPI_SPEC, 'r') as f:
                spec = json.load(f)

            # Get endpoint definition
            if endpoint not in spec.get('paths', {}):
                return ""

            endpoint_def = spec['paths'][endpoint]

            # Extract only test-relevant fields
            relevant = {
                'parameters': endpoint_def.get('get', {}).get('parameters', []),
                'requestBody': endpoint_def.get('get', {}).get('requestBody'),
                'responses': endpoint_def.get('get', {}).get('responses', {}),
                'security': endpoint_def.get('get', {}).get('security', [])
            }

            # Normalize and hash
            canonical = json.dumps(relevant, sort_keys=True)
            return hashlib.sha256(canonical.encode()).hexdigest()[:16]

        except Exception:
            return ""

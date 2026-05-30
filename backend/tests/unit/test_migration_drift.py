"""
Unit tests for the schema-drift guard's pure logic (SB-79).

Only the DB-free halves are tested here — reading versions from filenames and
diffing two version sets. The psycopg fetch and the live prod run are exercised
by the scheduled CI job, not the unit suite (which must stay env-independent).

The guard lives at repo-root scripts/check_migration_drift.py, so it's loaded
by file path. It must be registered in sys.modules before exec_module, or the
dataclass in it fails to resolve its own module annotations.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[3] / "scripts" / "check_migration_drift.py"
)
_spec = importlib.util.spec_from_file_location("check_migration_drift", _SCRIPT)
guard = importlib.util.module_from_spec(_spec)
sys.modules["check_migration_drift"] = guard
_spec.loader.exec_module(guard)


@pytest.mark.unit
class TestReadMigrationVersions:
    def test_extracts_version_prefix_and_includes_baseline(self, tmp_path):
        (tmp_path / "00000000000000_schema.sql").write_text("-- baseline")
        (tmp_path / "20260529000000_add_players_age_group_id.sql").write_text("-- x")
        (tmp_path / "20260201000000_foo.sql").write_text("-- y")
        versions = guard.read_migration_versions(tmp_path)
        assert versions == {"00000000000000", "20260201000000", "20260529000000"}

    def test_ignores_non_sql_and_non_numeric(self, tmp_path):
        (tmp_path / "20260201000000_foo.sql").write_text("-- y")
        (tmp_path / "README.md").write_text("# notes")
        (tmp_path / "notes_scratch.sql").write_text("-- not a version")
        versions = guard.read_migration_versions(tmp_path)
        assert versions == {"20260201000000"}


@pytest.mark.unit
class TestComputeDrift:
    def test_in_sync_when_equal(self):
        s = {"00000000000000", "20260201000000"}
        report = guard.compute_drift(s, set(s))
        assert report.in_sync
        assert report.missing_in_env == []
        assert report.orphan_in_env == []

    def test_missing_in_env_when_file_not_applied(self):
        files = {"00000000000000", "20260520000000", "20260527010000"}
        applied = {"00000000000000"}
        report = guard.compute_drift(files, applied)
        assert not report.in_sync
        # Sorted, and only the un-applied ones.
        assert report.missing_in_env == ["20260520000000", "20260527010000"]
        assert report.orphan_in_env == []

    def test_orphan_in_env_when_applied_has_no_file(self):
        files = {"00000000000000"}
        applied = {"00000000000000", "29990101000000"}
        report = guard.compute_drift(files, applied)
        assert not report.in_sync
        assert report.orphan_in_env == ["29990101000000"]
        assert report.missing_in_env == []

    def test_reports_both_directions(self):
        report = guard.compute_drift({"a", "b"}, {"b", "c"})
        assert report.missing_in_env == ["a"]
        assert report.orphan_in_env == ["c"]


@pytest.mark.unit
class TestRenderReport:
    def test_in_sync_message(self):
        out = guard.render_report("local", guard.compute_drift({"a"}, {"a"}))
        assert "in sync" in out

    def test_drift_message_lists_versions(self):
        out = guard.render_report(
            "prod", guard.compute_drift({"a", "20260520000000"}, {"a"})
        )
        assert "DRIFT DETECTED" in out
        assert "20260520000000" in out
        assert "Missing in env" in out

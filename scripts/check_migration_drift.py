#!/usr/bin/env python3
"""
Schema-drift guard (SB-79).

"Advanced linting" for migration state: assert that the set of applied
versions in an environment's `supabase_migrations.schema_migrations` equals the
set of timestamped migration files in `supabase/migrations/`.

Unit/code tests can't catch this — CI's test DB is built from the migration
files, so it always has the correct schema. Drift is an *environment-state*
problem (a migration merged but never deployed, or schema hand-applied in the
Supabase SQL editor without recording a row), so it needs an environment check.

Two halves, deliberately split so the diff logic stays pure and unit-testable
with no DB:
  - read_migration_versions() / compute_drift()  → pure, no IO
  - fetch_applied_versions()                     → the only DB touch

Usage:
    DATABASE_URL=postgresql://... python scripts/check_migration_drift.py --env prod
    python scripts/check_migration_drift.py --env local --db-url postgresql://...

Exits 0 when in sync, 1 on any drift (so CI fails the build).
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"


def read_migration_versions(migrations_dir: Path) -> set[str]:
    """
    Collect migration *versions* from the *.sql filenames in a directory.

    A version is the leading token before the first underscore, e.g.
    `20260529000000_add_players_age_group_id.sql` -> `20260529000000`. The
    consolidated baseline `00000000000000_schema.sql` is included.
    """
    versions: set[str] = set()
    for path in migrations_dir.glob("*.sql"):
        version = path.name.split("_", 1)[0]
        if version.isdigit():
            versions.add(version)
    return versions


@dataclass
class DriftReport:
    """Result of comparing repo migration files against an env's applied set."""

    missing_in_env: list[str] = field(default_factory=list)  # file exists, not applied
    orphan_in_env: list[str] = field(default_factory=list)  # applied, no file

    @property
    def in_sync(self) -> bool:
        return not self.missing_in_env and not self.orphan_in_env


def compute_drift(file_versions: set[str], applied_versions: set[str]) -> DriftReport:
    """Pure diff of repo migration files vs. an environment's applied versions."""
    return DriftReport(
        missing_in_env=sorted(file_versions - applied_versions),
        orphan_in_env=sorted(applied_versions - file_versions),
    )


def fetch_applied_versions(db_url: str) -> set[str]:
    """Read applied migration versions from supabase_migrations.schema_migrations."""
    import psycopg2  # imported lazily so the pure logic stays import-light

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version FROM supabase_migrations.schema_migrations")
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def render_report(env: str, report: DriftReport) -> str:
    """Human-readable summary for CI logs."""
    lines = [f"Migration drift check — env: {env}"]
    if report.in_sync:
        lines.append("✓ in sync — applied versions match the repo migration files")
        return "\n".join(lines)

    lines.append("✗ DRIFT DETECTED")
    if report.missing_in_env:
        lines.append("")
        lines.append("  Missing in env (file exists, NOT applied — likely un-deployed):")
        lines.extend(f"    - {v}" for v in report.missing_in_env)
    if report.orphan_in_env:
        lines.append("")
        lines.append("  Orphan in env (applied/recorded, NO file — history rewritten):")
        lines.extend(f"    - {v}" for v in report.orphan_in_env)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Schema-drift guard (SB-79)")
    parser.add_argument(
        "--env",
        default=os.getenv("APP_ENV", "local"),
        help="Environment label for the report (local/prod). Default: $APP_ENV or local.",
    )
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL"),
        help="Postgres connection string. Default: $DATABASE_URL.",
    )
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=DEFAULT_MIGRATIONS_DIR,
        help=f"Migrations directory. Default: {DEFAULT_MIGRATIONS_DIR}",
    )
    args = parser.parse_args(argv)

    if not args.db_url:
        print("error: no database URL (set DATABASE_URL or pass --db-url)", file=sys.stderr)
        return 2
    if not args.migrations_dir.is_dir():
        print(f"error: migrations dir not found: {args.migrations_dir}", file=sys.stderr)
        return 2

    file_versions = read_migration_versions(args.migrations_dir)
    applied_versions = fetch_applied_versions(args.db_url)
    report = compute_drift(file_versions, applied_versions)

    print(render_report(args.env, report))
    return 0 if report.in_sync else 1


if __name__ == "__main__":
    sys.exit(main())

"""Every table has a backup decision, and every backed-up table a restore decision (SB-1071).

Twice, tables went unbacked-up for months. In March 2026 it was tournaments,
tournament_age_groups, audit_events, audit_teams and login_events. By September
it was eleven more — division_age_groups, the QoP ranking history, users'
follows and notification preferences, push subscriptions, the support inbox and
the admin audit log. Both times backup_database.py printed a warning at run
time, and both times nobody acted on it: a warning in a log is not a gate.

This is the gate. It needs no database — it reads the migrations — so a PR that
creates a table without deciding whether to back it up fails CI.

It also checks the other half: restore_database.py keeps its own table list,
and five backed-up tables had never been restored.
"""

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_MIGRATIONS = _ROOT / "supabase" / "migrations"

# [schema.]name, each part optionally double-quoted.
_NAME = r'(?:"?(\w+)"?\.)?"?(\w+)"?'
_CREATE = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?" + _NAME, re.I)
_DROP = re.compile(r"drop\s+table\s+(?:if\s+exists\s+)?" + _NAME, re.I)
_RENAME = re.compile(r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?" + _NAME + r'\s+rename\s+to\s+"?(\w+)"?', re.I)
_CREATE_BLOCK = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?" + _NAME + r"\s*\((.*?)\)\s*;", re.I | re.S)
_ID_COLUMN = re.compile(r'(?:^|,)\s*"?id"?\s+\w', re.I | re.M)
# `<column> <type> ... REFERENCES [schema.]table` inside a CREATE TABLE body.
_INLINE_REFERENCES = re.compile(
    r'(?:^|,)\s*"?(\w+)"?\s+[^,]*?\breferences\s+' + _NAME, re.I | re.M | re.S
)
# ALTER TABLE [schema.]t ADD CONSTRAINT ... FOREIGN KEY (col) REFERENCES [schema.]other
_ALTER_FK = re.compile(
    r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?"
    + _NAME
    + r"\s+add\s+constraint\s+\S+\s+foreign\s+key\s*\(\s*\"?(\w+)\"?\s*\)"
    r"\s*references\s+" + _NAME,
    re.I | re.S,
)
# The whole body of an ALTER TABLE, so every ADD COLUMN in it can be scanned.
# This is the spelling SB-1104 arrived by: `leagues.match_type_id` was added
# long after RESTORATION_ORDER was written, and a parser that only read CREATE
# TABLE bodies would miss exactly the dependencies most likely to be stale.
_ALTER_BLOCK = re.compile(
    r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?" + _NAME + r"(.*?);", re.I | re.S
)
_ADD_COLUMN_REF = re.compile(
    r'add\s+column\s+(?:if\s+not\s+exists\s+)?"?(\w+)"?[^,]*?\breferences\s+' + _NAME,
    re.I | re.S,
)


def _sql(path: Path) -> str:
    text = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
    return re.sub(r"--[^\n]*", "", text)


def _migration_files() -> list[Path]:
    # Top level only: .archive/ holds superseded history, not the schema.
    return sorted(_MIGRATIONS.glob("*.sql"))


def migration_tables() -> set[str]:
    """public tables that exist after applying every migration in order."""
    tables: set[str] = set()
    for path in _migration_files():
        sql = _sql(path)
        for statement in re.finditer(r"\b(?:create|drop|alter)\s+table\b", sql, re.I):
            chunk = sql[statement.start() : statement.start() + 300]
            for kind, pattern in (("create", _CREATE), ("drop", _DROP), ("rename", _RENAME)):
                match = pattern.match(chunk)
                if not match:
                    continue
                if (match.group(1) or "public").lower() != "public":
                    break
                name = match.group(2).lower()
                if kind == "create":
                    tables.add(name)
                elif kind == "drop":
                    tables.discard(name)
                else:
                    tables.discard(name)
                    tables.add(match.group(3).lower())
                break
    return tables


def tables_without_id() -> set[str]:
    """public tables whose CREATE TABLE declares no `id` column."""
    missing: set[str] = set()
    for path in _migration_files():
        for block in _CREATE_BLOCK.finditer(_sql(path)):
            if (block.group(1) or "public").lower() != "public":
                continue
            name = block.group(2).lower()
            if _ID_COLUMN.search(block.group(3)):
                missing.discard(name)
            else:
                missing.add(name)
    return missing & migration_tables()


def foreign_keys() -> set[tuple[str, str, str]]:
    """(table, referenced_table, column) for every public FK the migrations declare.

    Covers both spellings the schema uses: a `REFERENCES` clause inside a
    CREATE TABLE, and a later `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY`.
    Reading the migrations rather than a live database keeps this a unit test,
    so it gates a PR rather than a deploy.
    """
    keys: set[tuple[str, str, str]] = set()
    known = migration_tables()

    for path in _migration_files():
        sql = _sql(path)

        # Column-level: `league_id integer REFERENCES public.leagues(id)`.
        for block in _CREATE_BLOCK.finditer(sql):
            if (block.group(1) or "public").lower() != "public":
                continue
            table = block.group(2).lower()
            for ref in _INLINE_REFERENCES.finditer(block.group(3)):
                column = (ref.group(1) or "").lower()
                if (ref.group(2) or "public").lower() != "public":
                    continue
                keys.add((table, ref.group(3).lower(), column))

        # Statement-level: ALTER TABLE ... FOREIGN KEY (col) REFERENCES other(id).
        for alter in _ALTER_FK.finditer(sql):
            if (alter.group(1) or "public").lower() != "public":
                continue
            if (alter.group(4) or "public").lower() != "public":
                continue
            keys.add((alter.group(2).lower(), alter.group(5).lower(), alter.group(3).lower()))

        # ALTER TABLE ... ADD COLUMN <col> <type> REFERENCES [schema.]other.
        for block in _ALTER_BLOCK.finditer(sql):
            if (block.group(1) or "public").lower() != "public":
                continue
            table = block.group(2).lower()
            for ref in _ADD_COLUMN_REF.finditer(block.group(3)):
                if (ref.group(2) or "public").lower() != "public":
                    continue
                keys.add((table, ref.group(3).lower(), ref.group(1).lower()))

    # A constraint naming a table no migration creates is a parser artefact, not
    # a dependency; dropping those keeps a mis-parse from failing the wrong test.
    return {(t, r, c) for t, r, c in keys if t in known and r in known}


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, _ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def backup():
    yield _load("backup_database")
    sys.modules.pop("backup_database", None)


@pytest.fixture
def restore(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:55321")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")  # pragma: allowlist secret
    yield _load("restore_database")
    sys.modules.pop("restore_database", None)


@pytest.mark.unit
class TestTheMigrationParser:
    """The gate is only as good as the parser, so pin what it must see."""

    def test_finds_tables_from_the_baseline_and_later_migrations(self):
        tables = migration_tables()

        assert {"matches", "teams", "user_profiles"} <= tables  # baseline schema
        assert {"division_age_groups", "user_team_follows"} <= tables  # later migrations

    def test_a_dropped_table_is_gone(self):
        # 20260404201640_drop_radius_tables.sql
        assert not {t for t in migration_tables() if t.startswith("rad")}

    def test_finds_the_tables_that_have_no_id_column(self):
        assert {"tournament_age_groups", "user_team_follows"} <= tables_without_id()
        assert "matches" not in tables_without_id()

    def test_finds_foreign_keys_in_both_spellings(self):
        pairs = {(table, references) for table, references, _ in foreign_keys()}

        # The one SB-1104 was about, plus a couple of well-known edges.
        assert ("leagues", "match_types") in pairs
        assert ("divisions", "leagues") in pairs
        assert ("matches", "teams") in pairs

    def test_a_table_with_no_foreign_keys_has_none(self):
        assert not [t for t, _, _ in foreign_keys() if t == "age_groups"]


@pytest.mark.unit
class TestEveryTableHasABackupDecision:
    def test_every_table_is_backed_up_or_excluded(self, backup):
        undecided = migration_tables() - set(backup.TABLES_TO_BACKUP) - backup.EXCLUDED_TABLES

        assert not undecided, (
            f"Tables with no backup decision: {sorted(undecided)}. Add each to TABLES_TO_BACKUP "
            "in scripts/backup_database.py (and to RESTORATION_ORDER or RESTORE_SKIPPED in "
            "scripts/restore_database.py), or to EXCLUDED_TABLES with the reason."
        )

    def test_the_lists_name_only_tables_that_exist(self, backup):
        stale = (set(backup.TABLES_TO_BACKUP) | backup.EXCLUDED_TABLES) - migration_tables()

        assert not stale, f"Backup lists name tables no migration creates: {sorted(stale)}"

    def test_no_table_is_both_backed_up_and_excluded(self, backup):
        assert not set(backup.TABLES_TO_BACKUP) & backup.EXCLUDED_TABLES

    def test_no_table_is_backed_up_twice(self, backup):
        assert len(backup.TABLES_TO_BACKUP) == len(set(backup.TABLES_TO_BACKUP))


@pytest.mark.unit
class TestEveryBackedUpTableHasARestoreDecision:
    def test_every_backed_up_table_is_restored_or_deliberately_skipped(self, backup, restore):
        backed_up = set(backup.TABLES_TO_BACKUP) | {backup.AUTH_USERS_KEY}
        undecided = backed_up - set(restore.RESTORATION_ORDER) - set(restore.RESTORE_SKIPPED)

        assert not undecided, (
            f"Backed up but never restored: {sorted(undecided)}. Add each to RESTORATION_ORDER "
            "(after the tables it references) or to RESTORE_SKIPPED with the reason."
        )

    def test_restore_names_only_backed_up_tables(self, backup, restore):
        backed_up = set(backup.TABLES_TO_BACKUP) | {backup.AUTH_USERS_KEY}

        assert set(restore.RESTORATION_ORDER) <= backed_up
        assert set(restore.RESTORE_SKIPPED) <= backed_up

    def test_nothing_is_both_restored_and_skipped(self, restore):
        assert not set(restore.RESTORATION_ORDER) & set(restore.RESTORE_SKIPPED)

    def test_restored_tables_without_an_id_are_cleared_by_column(self, restore):
        # clear_table() pages through `id`; without one it fails and the restore
        # then collides with the rows it could not clear.
        needs_column = tables_without_id() & set(restore.RESTORATION_ORDER)

        assert needs_column == set(restore.CLEAR_BY_COLUMN)

    def test_the_order_respects_foreign_keys(self, restore):
        """Every table comes after the tables it references (SB-1104).

        The order's whole job is this, and nothing checked it. `leagues` sat
        before `match_types` although `leagues.match_type_id` references it,
        which was harmless only while every league left that column null. The
        first league to set one broke inserts *and* — because clearing runs in
        reverse — broke clearing too, so the seeded rows survived and the
        backup's collided with them. A third of the season went missing from a
        restore that reported nothing worse than "completed with errors".
        """
        position = {table: i for i, table in enumerate(restore.RESTORATION_ORDER)}

        out_of_order = [
            (table, references)
            for table, references, _ in foreign_keys()
            # Self-references are ordered within a table, not between tables.
            if table != references
            and table in position
            and references in position
            and position[references] > position[table]
        ]

        assert not out_of_order, (
            "RESTORATION_ORDER puts these tables before ones they reference: "
            + ", ".join(f"{t} -> {r}" for t, r in sorted(set(out_of_order)))
            + ". Move each referenced table above the table that references it."
        )

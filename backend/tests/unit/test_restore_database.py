"""Restore fidelity (SB-917).

A restore that half-failed reported success. Three faults compounded: PostgREST
rejects a whole batch of 100 when one row is bad, the exception was caught at
table level so every later batch was abandoned, and the process exited 0 anyway
— so `setup-local-db.sh` printed "Data restore complete" and carried on over a
truncated database.

The script lives at repo-root scripts/restore_database.py and builds a Supabase
client at import, so it is loaded by file path with the credentials stubbed and
the client replaced.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "restore_database.py"


@pytest.fixture
def restore(monkeypatch):
    """Load the script with a dummy Supabase client bound at import."""
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:55321")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")  # pragma: allowlist secret
    spec = importlib.util.spec_from_file_location("restore_database", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    sys.modules["restore_database"] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("restore_database", None)


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    """Mimics PostgREST: a batch insert fails entirely if any row is bad."""

    def __init__(self, client, name):
        self.client = client
        self.name = name
        self._payload = None

    def insert(self, payload):
        self._payload = payload
        return self

    def select(self, *_args, **_kwargs):
        self._payload = None
        return self

    def execute(self):
        if self._payload is None:
            return FakeResult([])
        rows = self._payload if isinstance(self._payload, list) else [self._payload]
        bad = [r for r in rows if r.get("id") in self.client.bad_ids]
        if bad:
            raise RuntimeError(f"invalid input for id={bad[0]['id']}")
        self.client.inserted.setdefault(self.name, []).extend(rows)
        return FakeResult(rows)


class FakeClient:
    def __init__(self, bad_ids=()):
        self.bad_ids = set(bad_ids)
        self.inserted = {}

    def table(self, name):
        return FakeTable(self, name)


def rows(count, start=1):
    return [{"id": start + i, "name": f"row-{start + i}"} for i in range(count)]


@pytest.mark.unit
class TestBatchFailureIsContained:
    def test_one_bad_row_costs_one_row(self, restore):
        restore.supabase = FakeClient(bad_ids={7})

        result = restore.restore_table("clubs", rows(10))

        assert result.inserted == 9
        assert [rid for rid, _ in result.failures] == [7]

    def test_later_batches_still_run(self, restore):
        # The old code exited the batch loop on the first failure, so a bad row
        # early in a large table silently truncated everything after it.
        restore.supabase = FakeClient(bad_ids={3})

        # 250 rows = three batches, with the bad row in the first.
        result = restore.restore_table("players", rows(250))

        assert result.inserted == 249
        assert len(restore.supabase.inserted["players"]) == 249

    def test_the_failure_names_the_record_and_the_reason(self, restore):
        restore.supabase = FakeClient(bad_ids={2})

        result = restore.restore_table("teams", rows(3))

        record_id, error = result.failures[0]
        assert record_id == 2
        assert "invalid input" in error

    def test_a_clean_table_reports_ok(self, restore):
        restore.supabase = FakeClient()

        result = restore.restore_table("teams", rows(120))

        assert result.ok
        assert result.inserted == 120
        assert result.failures == []

    def test_an_empty_table_is_not_a_failure(self, restore):
        restore.supabase = FakeClient()

        result = restore.restore_table("teams", [])

        assert result.ok
        assert result.inserted == 0


@pytest.mark.unit
class TestCountsAreReal:
    def test_inserted_counts_rows_that_landed_not_rows_in_the_file(self, restore):
        restore.supabase = FakeClient(bad_ids={1, 2, 3})

        result = restore.restore_table("clubs", rows(10))

        assert result.attempted == 10
        assert result.inserted == 7


@pytest.mark.unit
class TestNotNullGuard:
    def test_matches_guard_covers_the_columns_prod_leaves_nullable(self, restore):
        # age_group_id and match_type_id are NOT NULL locally and nullable in
        # prod (SB-916), so a prod row missing one reaches the database.
        good = {
            "id": 1,
            "home_team_id": 1,
            "away_team_id": 2,
            "season_id": 3,
            "age_group_id": 4,
            "match_type_id": 5,
        }
        missing_age = {**good, "id": 2, "age_group_id": None}
        missing_type = {**good, "id": 3, "match_type_id": None}

        kept = restore.validate_records("matches", [good, missing_age, missing_type])

        assert [r["id"] for r in kept] == [1]

    def test_an_untracked_table_is_passed_through(self, restore):
        data = [{"id": 1}, {"id": 2}]
        assert restore.validate_records("some_other_table", data) == data


@pytest.mark.unit
class TestExitCode:
    """What setup-local-db.sh actually checks."""

    def _backup(self, tmp_path, records):
        import json

        payload = {
            "backup_info": {"created_at": "2026-08-29T00:00:00Z"},
            "tables": {"clubs": records},
        }
        path = tmp_path / "database_backup_20260829_000000.json"
        path.write_text(json.dumps(payload))
        return path

    def _quiet(self, restore, monkeypatch):
        monkeypatch.setattr(restore, "clear_table", lambda *_a, **_k: True)
        monkeypatch.setattr(restore, "reset_sequences", lambda *_a, **_k: None)
        monkeypatch.setattr(restore, "get_local_user_profile_ids", lambda: set())

    def test_a_rejected_record_exits_non_zero(self, restore, tmp_path, monkeypatch):
        self._quiet(restore, monkeypatch)
        restore.supabase = FakeClient(bad_ids={2})
        backup = self._backup(tmp_path, rows(3))

        assert restore.main([str(backup)]) == 1

    def test_a_clean_restore_exits_zero(self, restore, tmp_path, monkeypatch):
        self._quiet(restore, monkeypatch)
        restore.supabase = FakeClient()
        backup = self._backup(tmp_path, rows(3))

        assert restore.main([str(backup)]) == 0

    def test_a_missing_backup_file_exits_non_zero(self, restore, tmp_path, monkeypatch):
        self._quiet(restore, monkeypatch)
        restore.supabase = FakeClient()

        assert restore.main([str(tmp_path / "nope.json")]) == 1

    def test_no_arguments_exits_non_zero(self, restore):
        assert restore.main([]) == 1


@pytest.mark.unit
class TestUserReferenceSanitization:
    """The map had drifted from the schema (SB-1071)."""

    PRESENT = "11111111-1111-1111-1111-111111111111"
    ABSENT = "99999999-9999-9999-9999-999999999999"

    def test_player_stats_are_never_dropped_for_their_integer_player_id(self, restore):
        # player_match_stats.player_id references players(id), an integer. The
        # old map treated it as a user uuid, so no row ever passed and a
        # restore silently dropped every goal and assist.
        stats = [{"id": 1, "player_id": 42, "goals": 2}, {"id": 2, "player_id": 7, "goals": 0}]

        kept = restore.sanitize_user_profile_refs("player_match_stats", stats, {self.PRESENT})

        assert kept == stats

    def test_invitation_users_that_are_absent_are_cleared(self, restore):
        rows = [{"id": 1, "invited_by_user_id": self.ABSENT, "used_by_user_id": self.PRESENT}]

        [kept] = restore.sanitize_user_profile_refs("invitations", rows, {self.PRESENT})

        assert kept["invited_by_user_id"] is None
        assert kept["used_by_user_id"] == self.PRESENT

    def test_match_authors_that_are_absent_are_cleared_not_dropped(self, restore):
        rows = [{"id": 1, "created_by": self.ABSENT, "updated_by": self.ABSENT}]

        [kept] = restore.sanitize_user_profile_refs("matches", rows, set())

        assert kept["created_by"] is None and kept["updated_by"] is None

    @pytest.mark.parametrize("table", ["user_team_follows", "user_bracket_follows", "user_notification_preferences"])
    def test_a_users_own_rows_are_dropped_when_the_user_is_absent(self, restore, table):
        rows = [{"user_id": self.PRESENT}, {"user_id": self.ABSENT}]

        kept = restore.sanitize_user_profile_refs(table, rows, {self.PRESENT})

        assert kept == [{"user_id": self.PRESENT}]

    def test_email_sent_by_an_absent_user_is_kept_with_the_sender_cleared(self, restore):
        rows = [{"id": "m1", "sent_by_user_id": self.ABSENT, "body_text": "hello"}]

        [kept] = restore.sanitize_user_profile_refs("email_messages", rows, set())

        assert kept["sent_by_user_id"] is None


class FakeDelete:
    def __init__(self, calls, table):
        self.calls = calls
        self.table = table

    def delete(self):
        return self

    def filter(self, column, operator, criteria):
        self.calls.append((self.table, f"{column}={operator}.{criteria}"))
        return self

    def select(self, *_args):
        raise AssertionError(f"{self.table} has no id column to page through")

    def execute(self):
        return FakeResult([{"user_id": "u"}])


@pytest.mark.unit
class TestClearingTablesWithoutAnId:
    @pytest.mark.parametrize("table", ["tournament_age_groups", "user_team_follows"])
    def test_cleared_by_filtering_on_a_key_column(self, restore, table):
        calls: list[tuple[str, str]] = []
        restore.supabase = type("Client", (), {"table": lambda _self, name: FakeDelete(calls, name)})()

        restore.clear_table(table)

        assert calls == [(table, f"{restore.CLEAR_BY_COLUMN[table]}=not.is.null")]

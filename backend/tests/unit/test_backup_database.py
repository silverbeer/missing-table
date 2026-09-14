"""Backup failure is loud (SB-1068).

The script caught every error per table, dropped the table, wrote the file and
exited 0. With local Supabase down it produced a 206-byte, zero-table backup,
printed "Backup completed successfully!", and that file became the newest one —
which is what `restore --latest` picks, and restore clears every table before
it loads. A backup is now complete or it is not written, and the exit code says
which.

The script lives at repo-root scripts/backup_database.py and builds a Supabase
client at import, so it is loaded by file path with the credentials stubbed and
the client replaced, as in test_restore_database.py.
"""

import gzip
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from postgrest.exceptions import APIError

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "backup_database.py"


@pytest.fixture
def backup(monkeypatch):
    """Load the script with a dummy client, no real waiting and no schema probe.

    configure() is stubbed to record the environment asked for; tests put a
    FakeDatabase on `supabase` themselves.
    """
    spec = importlib.util.spec_from_file_location("backup_database", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["backup_database"] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "sleep", lambda _seconds: None)
    monkeypatch.setattr(module, "check_for_new_tables", lambda _tables: [])

    configured: list[str] = []

    def fake_configure(env):
        configured.append(env)
        module.app_env = env

    module.configured = configured
    module.real_configure = module.configure
    monkeypatch.setattr(module, "configure", fake_configure)
    yield module
    sys.modules.pop("backup_database", None)


def rows(count, start=1):
    return [{"id": start + i, "name": f"row-{start + i}"} for i in range(count)]


def connection_refused():
    return httpx.ConnectError("[Errno 61] Connection refused")


def api_error(code, message="boom"):
    return APIError({"message": message, "code": code, "hint": None, "details": None})


class FakeResult:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class FakeQuery:
    """Just enough of PostgREST's query builder: select, range, execute."""

    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.with_count = False
        self.start = 0
        self.end = 0

    def select(self, *_columns, count=None):
        self.with_count = count is not None
        return self

    def range(self, start, end):
        self.start, self.end = start, end
        return self

    def execute(self):
        self.db.calls.append(self.name)
        self.db.raise_planned_failure(self.name)
        table = self.db.tables.get(self.name, [])
        page = table[self.start : self.end + 1][: self.db.max_rows]
        count = self.db.counts.get(self.name, len(table)) if self.with_count else None
        return FakeResult(page, count)


class FakeDatabase:
    """Tables by name, plus planned failures.

    `failures` maps a table name (or "*" for every table) to an exception that
    is raised on every call, or to a list of exceptions raised one per call
    before calls start succeeding.
    """

    def __init__(self, tables, failures=None, counts=None, max_rows=None):
        self.tables = tables
        self.failures = failures or {}
        self.counts = counts or {}
        self.max_rows = max_rows
        self.calls = []
        self.auth = SimpleNamespace(admin=SimpleNamespace(list_users=self._list_users))

    def table(self, name):
        return FakeQuery(self, name)

    def raise_planned_failure(self, name):
        planned = self.failures.get(name, self.failures.get("*"))
        if isinstance(planned, list):
            if planned:
                raise planned.pop(0)
        elif planned is not None:
            raise planned

    def _list_users(self, page=1, per_page=1000):
        self.calls.append("auth_users")
        self.raise_planned_failure("auth_users")
        users = self.tables.get("auth_users", [])
        start = (page - 1) * per_page
        return users[start : start + per_page]


def scraped_only_world(backup):
    """The default environment: seeded reference data and scraped matches, no user data.

    Rosters, lineups and match events are empty because for most teams nobody has
    entered any — that is a complete backup, not a failed one.
    """
    tables: dict[str, list] = {name: [] for name in backup.TABLES_TO_BACKUP}
    for name in backup.REQUIRED_NON_EMPTY:
        tables[name] = [{"id": 1, "name": f"{name}-1"}]
    tables["teams"] = rows(2)
    tables["matches"] = rows(3)
    tables["auth_users"] = []
    return tables


def payload(tables):
    return {"backup_info": {}, "tables": tables}


def files_in(directory):
    return sorted(p.name for p in directory.iterdir())


@pytest.mark.unit
class TestValidateBackup:
    def test_a_scraped_only_backup_is_complete(self, backup):
        tables = scraped_only_world(backup)

        assert backup.validate_backup(payload(tables), backup.TABLES_TO_BACKUP) == []

    def test_the_206_byte_backup_is_rejected_table_by_table(self, backup):
        # What the old script wrote with the database down.
        problems = backup.validate_backup(payload({}), backup.TABLES_TO_BACKUP)

        assert len(problems) == len(backup.TABLES_TO_BACKUP) + 1  # + auth_users
        assert "matches: missing" in problems

    def test_a_missing_table_is_named(self, backup):
        tables = scraped_only_world(backup)
        del tables["matches"]

        assert backup.validate_backup(payload(tables), backup.TABLES_TO_BACKUP) == ["matches: missing"]

    def test_missing_auth_users_is_named(self, backup):
        tables = scraped_only_world(backup)
        del tables["auth_users"]

        assert backup.validate_backup(payload(tables), backup.TABLES_TO_BACKUP) == ["auth_users: missing"]

    def test_an_empty_seeded_table_means_no_real_database(self, backup):
        tables = scraped_only_world(backup)
        tables["seasons"] = []

        problems = backup.validate_backup(payload(tables), backup.TABLES_TO_BACKUP)

        assert len(problems) == 1
        assert problems[0].startswith("seasons: empty")

    def test_a_table_that_is_not_rows_is_rejected(self, backup):
        tables = scraped_only_world(backup)
        tables["teams"] = {"error": "not rows"}

        problems = backup.validate_backup(payload(tables), backup.TABLES_TO_BACKUP)

        assert problems == ["teams: expected a list of rows, got dict"]

    def test_no_tables_section(self, backup):
        assert backup.validate_backup({"backup_info": {}}, backup.TABLES_TO_BACKUP) == [
            "backup has no 'tables' section"
        ]


@pytest.mark.unit
class TestTransientErrors:
    @pytest.mark.parametrize(
        "error",
        [
            httpx.ConnectError("refused"),
            httpx.ReadTimeout("slow"),
            APIError({"message": "JSON could not be generated", "code": 504, "hint": None, "details": None}),
            APIError({"message": "bad gateway", "code": "502", "hint": None, "details": None}),
        ],
        ids=["connect", "timeout", "gateway-504", "502"],
    )
    def test_retried(self, backup, error):
        assert backup.is_transient(error)

    @pytest.mark.parametrize(
        "error",
        [
            APIError({"message": "relation does not exist", "code": "PGRST205", "hint": None, "details": None}),
            APIError({"message": "permission denied", "code": "42501", "hint": None, "details": None}),
            ValueError("bad"),
        ],
        ids=["missing-table", "permission", "value-error"],
    )
    def test_not_retried(self, backup, error):
        assert not backup.is_transient(error)


@pytest.mark.unit
class TestBackupTable:
    def test_reads_every_page(self, backup):
        backup.supabase = FakeDatabase({"matches": rows(2500)})

        result = backup.backup_table("matches")

        assert len(result) == 2500
        assert backup.supabase.calls.count("matches") == 3

    def test_a_transient_failure_is_retried(self, backup):
        backup.supabase = FakeDatabase(
            {"matches": rows(3)},
            failures={"matches": [connection_refused(), api_error("504")]},
        )

        result = backup.backup_table("matches")

        assert len(result) == 3
        assert backup.supabase.calls.count("matches") == 3

    def test_retries_give_up_and_raise(self, backup):
        backup.supabase = FakeDatabase({"matches": rows(3)}, failures={"matches": connection_refused()})

        with pytest.raises(httpx.ConnectError):
            backup.backup_table("matches")

        assert backup.supabase.calls.count("matches") == backup.MAX_ATTEMPTS

    def test_a_permanent_failure_is_not_retried(self, backup):
        backup.supabase = FakeDatabase({}, failures={"matches": api_error("PGRST205", "relation does not exist")})

        with pytest.raises(APIError):
            backup.backup_table("matches")

        assert backup.supabase.calls.count("matches") == 1

    def test_a_short_read_is_an_error_not_a_smaller_table(self, backup):
        # A max-rows cap below the page size makes page one look like the end.
        backup.supabase = FakeDatabase({"matches": rows(1200)}, max_rows=500)

        with pytest.raises(backup.BackupError, match="read 500 of 1200 rows"):
            backup.backup_table("matches")


@pytest.mark.unit
class TestWriteBackup:
    def test_written_backup_reads_back_and_leaves_no_temp_file(self, backup, tmp_path):
        data = payload(scraped_only_world(backup))
        target = tmp_path / "database_backup_20260914_120000.json.gz"

        backup.write_backup(data, target)

        assert files_in(tmp_path) == [target.name]
        with gzip.open(target, "rt", encoding="utf-8") as f:
            assert len(json.load(f)["tables"]["matches"]) == 3

    def test_a_failed_write_leaves_nothing_behind(self, backup, tmp_path, monkeypatch):
        def disk_full(*_args, **_kwargs):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(backup.json, "dump", disk_full)
        target = tmp_path / "database_backup_20260914_120000.json.gz"

        with pytest.raises(backup.BackupError, match="No space left on device"):
            backup.write_backup(payload(scraped_only_world(backup)), target)

        assert files_in(tmp_path) == []


@pytest.mark.unit
class TestExitCode:
    """What db_tools.sh migrate prod and run_backup.sh actually check."""

    def _run(self, backup, tmp_path, db, app_env="prod"):
        backup.supabase = db
        # A URL that belongs to the environment, so the mismatch guard stays out of the way.
        backup.url = "http://127.0.0.1:55321" if app_env == "local" else "https://project.supabase.co"
        return backup.main(["--env", app_env, "--backup-dir", str(tmp_path)])

    def test_a_complete_backup_exits_zero_and_writes_one_file(self, backup, tmp_path):
        db = FakeDatabase(scraped_only_world(backup))

        assert self._run(backup, tmp_path, db) == 0

        [written] = list(tmp_path.iterdir())
        with gzip.open(written, "rt", encoding="utf-8") as f:
            info = json.load(f)["backup_info"]
        assert info["app_env"] == "prod"
        assert info["row_counts"]["matches"] == 3
        assert info["row_counts"]["players"] == 0

    def test_database_down_exits_non_zero_and_writes_nothing(self, backup, tmp_path, capsys):
        db = FakeDatabase(scraped_only_world(backup), failures={"*": connection_refused()})

        assert self._run(backup, tmp_path, db, app_env="local") == 1

        assert files_in(tmp_path) == []
        out = capsys.readouterr().out
        assert "Backup of local failed" in out
        assert "npx supabase start" in out
        assert "Backup completed successfully" not in out

    def test_database_down_fails_at_the_connection_check_not_per_table(self, backup, tmp_path):
        db = FakeDatabase(scraped_only_world(backup), failures={"*": connection_refused()})

        self._run(backup, tmp_path, db, app_env="local")

        assert set(db.calls) == {"seasons"}

    def test_one_failed_table_fails_the_backup_and_is_named(self, backup, tmp_path, capsys):
        db = FakeDatabase(scraped_only_world(backup), failures={"players": api_error("42501", "permission denied")})

        assert self._run(backup, tmp_path, db) == 1

        assert files_in(tmp_path) == []
        out = capsys.readouterr().out
        assert "players: PostgREST 42501: permission denied" in out

    def test_every_failed_table_is_reported_not_just_the_first(self, backup, tmp_path, capsys):
        db = FakeDatabase(
            scraped_only_world(backup),
            failures={"players": api_error("42501"), "match_events": api_error("42501")},
        )

        assert self._run(backup, tmp_path, db) == 1

        out = capsys.readouterr().out
        assert "2 table(s) could not be backed up" in out

    def test_stops_once_the_database_stops_responding(self, backup, tmp_path, capsys):
        db = FakeDatabase(scraped_only_world(backup), failures={"clubs": connection_refused()})

        assert self._run(backup, tmp_path, db) == 1

        tables = backup.TABLES_TO_BACKUP
        after_clubs = tables[tables.index("clubs") + 1 :]
        assert not set(after_clubs) & set(db.calls)
        assert "not attempted" in capsys.readouterr().out

    def test_failed_auth_users_fails_the_backup(self, backup, tmp_path):
        db = FakeDatabase(scraped_only_world(backup), failures={"auth_users": api_error("403", "not allowed")})

        assert self._run(backup, tmp_path, db) == 1
        assert files_in(tmp_path) == []

    def test_empty_seeded_table_fails_the_backup(self, backup, tmp_path, capsys):
        tables = scraped_only_world(backup)
        tables["seasons"] = []

        assert self._run(backup, tmp_path, FakeDatabase(tables)) == 1

        assert files_in(tmp_path) == []
        assert "seasons: empty" in capsys.readouterr().out

    def test_missing_credentials_exit_non_zero(self, backup, tmp_path):
        assert self._run(backup, tmp_path, None) == 1
        assert files_in(tmp_path) == []

    def test_cancelling_exits_130_and_writes_nothing(self, backup, tmp_path):
        db = FakeDatabase(scraped_only_world(backup), failures={"matches": KeyboardInterrupt()})

        assert self._run(backup, tmp_path, db) == 130
        assert files_in(tmp_path) == []

    def test_list_needs_no_credentials(self, backup, tmp_path):
        backup.supabase = None

        assert backup.main(["--list", "--backup-dir", str(tmp_path)]) == 0


@pytest.mark.unit
class TestProductionIsTheDefault:
    """SB-1069: a bare backup twice backed up a stopped local database, because
    it read APP_ENV and the shell exported APP_ENV=local."""

    def test_no_env_backs_up_prod(self, backup, tmp_path):
        backup.supabase = FakeDatabase(scraped_only_world(backup))
        backup.url = "https://project.supabase.co"

        assert backup.main(["--backup-dir", str(tmp_path)]) == 0
        assert backup.configured == ["prod"]

    def test_app_env_local_is_ignored(self, backup, tmp_path, monkeypatch):
        monkeypatch.setenv("APP_ENV", "local")
        backup.supabase = FakeDatabase(scraped_only_world(backup))
        backup.url = "https://project.supabase.co"

        backup.main(["--backup-dir", str(tmp_path)])

        assert backup.configured == ["prod"]

    def test_local_only_when_asked(self, backup, tmp_path):
        backup.supabase = FakeDatabase(scraped_only_world(backup))
        backup.url = "http://127.0.0.1:55321"

        assert backup.main(["--env", "local", "--backup-dir", str(tmp_path)]) == 0
        assert backup.configured == ["local"]

    def test_an_unknown_environment_is_refused(self, backup, tmp_path):
        with pytest.raises(SystemExit) as exit_info:
            backup.main(["--env", "dev", "--backup-dir", str(tmp_path)])

        assert exit_info.value.code == 2


@pytest.mark.unit
class TestEnvironmentMismatch:
    @pytest.mark.parametrize(
        ("env", "url"),
        [
            ("prod", "https://project.supabase.co"),
            ("local", "http://127.0.0.1:55321"),
            ("local", "http://localhost:55321"),
        ],
    )
    def test_matching(self, backup, env, url):
        assert backup.environment_mismatch(env, url) is None

    def test_prod_pointing_at_localhost(self, backup):
        assert "local address" in backup.environment_mismatch("prod", "http://127.0.0.1:55321")

    def test_local_pointing_at_the_cloud(self, backup):
        assert "not a local address" in backup.environment_mismatch("local", "https://project.supabase.co")

    def test_a_mismatch_fails_the_backup_before_reading_anything(self, backup, tmp_path, capsys):
        db = FakeDatabase(scraped_only_world(backup))
        backup.supabase = db
        backup.url = "http://127.0.0.1:55321"

        assert backup.main(["--env", "prod", "--backup-dir", str(tmp_path)]) == 1

        assert db.calls == []
        assert files_in(tmp_path) == []
        assert "local address" in capsys.readouterr().out


@pytest.mark.unit
class TestConfigure:
    def test_loads_the_named_environment_file(self, backup, tmp_path, monkeypatch):
        for name in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "DATABASE_URL"):
            monkeypatch.setenv(name, "stale-from-the-shell")
        (tmp_path / ".env.prod").write_text(
            "SUPABASE_URL=https://project.supabase.co\n"
            "SUPABASE_SERVICE_KEY=test-service-key\n"  # pragma: allowlist secret
        )
        monkeypatch.setattr(backup, "backend_path", tmp_path)

        backup.real_configure("prod")

        assert backup.app_env == "prod"
        assert backup.url == "https://project.supabase.co"
        assert backup.supabase is not None

    def test_a_missing_environment_file_is_an_error_not_a_fallback(self, backup, tmp_path, monkeypatch):
        # The old loader fell back to backend/.env — a backup labelled prod
        # holding whatever that file pointed at.
        (tmp_path / ".env").write_text("SUPABASE_URL=http://127.0.0.1:55321\n")
        monkeypatch.setattr(backup, "backend_path", tmp_path)

        with pytest.raises(backup.BackupError, match=r"\.env\.prod not found"):
            backup.real_configure("prod")

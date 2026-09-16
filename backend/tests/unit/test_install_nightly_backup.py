"""Retiring the old cron entry never hangs, and never fails the install (SB-1077).

Installing the launchd jobs (SB-1070) ended with `crontab -l | grep -v ... |
crontab -`. Run from a process with no terminal, macOS waits on a permission
prompt nobody can see: it hung for ten minutes, and `set -e` then reported
"INSTALL FAILED" even though both jobs were already loaded and working.

The script is sourced here — its body is behind a `BASH_SOURCE` guard — so the
cron step can be exercised against a stub crontab, in a temporary HOME, without
touching the real one.
"""

import shutil
import subprocess
import time
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "install_nightly_backup.sh"
_BASH = shutil.which("bash") or "/bin/bash"

CRON_LINE = "0 3 * * * /Users/someone/gitrepos/missing-table/scripts/run_backup.sh"
OTHER_LINE = "*/5 * * * * /usr/local/bin/something-else"

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash"),
]


def _stub_crontab(tmp_path, mode, contents):
    """A crontab that reads and writes `state`, or hangs on write.

    The hanging one ignores SIGTERM and detaches its file descriptors, which is
    what a real `crontab -` stuck on a macOS permission prompt looks like from
    outside: a plain kill will not shift it, and nothing it leaves behind holds
    this test's captured pipes open.
    """
    state = tmp_path / "crontab.state"
    state.write_text(contents)
    stub = tmp_path / "crontab"
    hang = "trap '' TERM\nexec 1> /dev/null 2>&1 0< /dev/null\nsleep 60"
    write = hang if mode == "hangs" else f'cat > "{state}"'
    stub.write_text(f'#!/bin/bash\nif [ "$1" = "-l" ]; then cat "{state}"; exit 0; fi\n{write}\nexit 0\n')
    stub.chmod(0o755)
    return stub, state


def _run(snippet, tmp_path, stub=None, force=True, timeout="2"):
    env = {
        "HOME": str(tmp_path / "home"),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "MT_CRONTAB_TIMEOUT": timeout,
    }
    if stub is not None:
        env["MT_CRONTAB_CMD"] = str(stub)
    if force:
        env["MT_CRONTAB_FORCE"] = "1"
    (tmp_path / "home").mkdir(exist_ok=True)
    # Fixed command, built from repo-local constants — no caller input.
    return subprocess.run(  # noqa: S603
        [_BASH, "-c", f'source "{_SCRIPT}"; {snippet}'],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )


class TestRetireCronEntry:
    def test_nothing_to_remove_is_success(self, tmp_path):
        stub, state = _stub_crontab(tmp_path, "works", OTHER_LINE + "\n")

        result = _run("retire_cron_entry", tmp_path, stub)

        assert result.returncode == 0
        assert state.read_text() == OTHER_LINE + "\n"  # untouched

    def test_removes_the_entry_and_keeps_the_rest(self, tmp_path):
        stub, state = _stub_crontab(tmp_path, "works", f"{OTHER_LINE}\n{CRON_LINE}\n")

        result = _run("retire_cron_entry", tmp_path, stub)

        assert result.returncode == 0
        assert "run_backup.sh" not in state.read_text()
        assert OTHER_LINE in state.read_text()
        assert "Removed the old run_backup.sh crontab entry" in result.stdout

    def test_the_old_crontab_is_saved_first(self, tmp_path):
        stub, _ = _stub_crontab(tmp_path, "works", f"{OTHER_LINE}\n{CRON_LINE}\n")

        _run("retire_cron_entry", tmp_path, stub)

        [saved] = (tmp_path / "home" / ".local" / "share").glob("crontab.before-sb-1070.*")
        assert CRON_LINE in saved.read_text()

    def test_a_hanging_write_gives_up_instead_of_waiting_forever(self, tmp_path):
        # The SB-1077 failure: `crontab -` blocked on an invisible prompt.
        stub, state = _stub_crontab(tmp_path, "hangs", f"{CRON_LINE}\n")

        started = time.monotonic()
        result = _run("retire_cron_entry", tmp_path, stub)
        elapsed = time.monotonic() - started

        assert result.returncode == 3
        assert elapsed < 30
        assert CRON_LINE in state.read_text()  # nothing was written

    def test_without_a_terminal_it_does_not_even_try(self, tmp_path):
        # How an agent or a CI job runs it: no tty, so no prompt to hang on.
        stub, state = _stub_crontab(tmp_path, "hangs", f"{CRON_LINE}\n")

        result = _run("retire_cron_entry", tmp_path, stub, force=False)

        assert result.returncode == 2
        assert CRON_LINE in state.read_text()


class TestSummary:
    def test_a_skipped_cron_step_prints_the_command_to_run(self, tmp_path):
        result = _run("print_summary 2", tmp_path)

        assert "Both jobs are loaded" in result.stdout
        assert "not run from a terminal" in result.stdout
        assert "crontab -l | grep -v 'scripts/run_backup.sh' | crontab -" in result.stdout

    def test_a_hung_cron_step_names_the_permission_prompt(self, tmp_path):
        result = _run("print_summary 3", tmp_path)

        assert "permission prompt" in result.stdout
        assert "crontab -l | grep -v" in result.stdout

    def test_a_clean_install_says_nothing_about_cron(self, tmp_path):
        result = _run("print_summary 0", tmp_path)

        assert "Both jobs are loaded" in result.stdout
        assert "crontab" not in result.stdout

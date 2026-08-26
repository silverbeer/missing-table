"""`mt --env`: targeting prod is one command, not a mode (SB-841).

Before this the only way to run a command against production was to edit
`.mt-config`, which changes the target of every subsequent command in every
shell until somebody changes it back. The procedure was: back the file up, flip
it, do the work, restore it — which works exactly as long as nothing fails in
the middle and nobody forgets. A forgotten flip means the next "local" command
quietly hits production.

Two things follow from making the target easy to change, and both are tested
here: the precedence has to be predictable, and the stored session has to be
per environment. A prod token sent to localhost, or a prod match id treated as
a local one, would be a worse failure than the one being fixed.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import mt_cli

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Point every file mt_cli reads at a temp dir, and clear the override.

    BACKEND_DIR is redirected too, so `.env.local` and `.env.prod` are the ones
    written here. Reading the developer's real env files would make these tests
    pass or fail on whether someone happens to have a `.env.prod` — which is
    exactly how the first version of this file went green locally and red in CI.
    """
    config = tmp_path / ".mt-config"
    state = tmp_path / ".mt-cli-state.json"
    monkeypatch.setattr(mt_cli, "MT_CONFIG_FILE", config)
    monkeypatch.setattr(mt_cli, "STATE_FILE", state)
    monkeypatch.setattr(mt_cli, "BACKEND_DIR", tmp_path)
    monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", None)
    monkeypatch.delenv("APP_ENV", raising=False)
    (tmp_path / ".env.local").write_text("BACKEND_URL=http://localhost:8000\n")
    (tmp_path / ".env.prod").write_text("BACKEND_URL=https://api.missingtable.com\n")
    return config, state


def write_config(config, env: str) -> None:
    config.write_text(f"supabase_env={env}\n")


@pytest.mark.unit
class TestPrecedence:
    def test_nothing_set_is_local(self):
        assert mt_cli.resolve_env() == ("local", "default")

    def test_the_config_file_is_the_persistent_mode(self, isolated):
        config, _ = isolated
        write_config(config, "prod")
        assert mt_cli.resolve_env()[0] == "prod"

    def test_app_env_beats_the_config_file(self, isolated, monkeypatch):
        """The surprising half of the old order.

        `APP_ENV=prod mt ...` looks like it should work and silently did
        nothing, because .mt-config won.
        """
        config, _ = isolated
        write_config(config, "local")
        monkeypatch.setenv("APP_ENV", "prod")
        assert mt_cli.resolve_env() == ("prod", "APP_ENV")

    def test_the_flag_beats_everything(self, isolated, monkeypatch):
        config, _ = isolated
        write_config(config, "local")
        monkeypatch.setenv("APP_ENV", "local")
        monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", "prod")
        assert mt_cli.resolve_env() == ("prod", "--env")

    def test_the_source_is_reported_so_a_surprise_can_be_explained(self, isolated):
        config, _ = isolated
        write_config(config, "prod")
        assert mt_cli.resolve_env()[1] == ".mt-config"


@pytest.mark.unit
class TestTheFlag:
    def test_it_changes_the_target(self, isolated):
        result = runner.invoke(mt_cli.app, ["--env", "prod", "config"])
        assert result.exit_code == 0
        assert "prod" in result.output

    def test_it_writes_nothing_to_disk(self, isolated):
        """The whole point: one command, not a mode left behind."""
        config, _ = isolated
        write_config(config, "local")
        runner.invoke(mt_cli.app, ["--env", "prod", "config"])
        assert config.read_text() == "supabase_env=local\n"

    def test_an_unknown_environment_is_refused(self, isolated):
        result = runner.invoke(mt_cli.app, ["--env", "staging", "config"])
        assert result.exit_code == 1
        assert "local" in result.output and "prod" in result.output

    def test_without_it_the_config_file_still_decides(self, isolated):
        config, _ = isolated
        write_config(config, "local")
        result = runner.invoke(mt_cli.app, ["config"])
        assert "local" in result.output


@pytest.mark.unit
class TestSessionsArePerEnvironment:
    def test_a_token_is_stored_under_its_environment(self, isolated, monkeypatch):
        _, state_file = isolated
        monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", "prod")
        mt_cli.save_state(mt_cli.CLIState(access_token="prod-token", username="tom"))

        stored = json.loads(state_file.read_text())
        assert stored["environments"]["prod"]["access_token"] == "prod-token"

    def test_a_prod_token_is_never_offered_to_local(self, isolated, monkeypatch):
        """The failure --env would otherwise have made easy."""
        monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", "prod")
        mt_cli.save_state(mt_cli.CLIState(access_token="prod-token"))

        monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", "local")
        assert mt_cli.load_state().access_token is None

    def test_saving_one_environment_leaves_the_other_alone(self, isolated, monkeypatch):
        monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", "prod")
        mt_cli.save_state(mt_cli.CLIState(access_token="prod-token"))

        monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", "local")
        mt_cli.save_state(mt_cli.CLIState(access_token="local-token"))

        monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", "prod")
        assert mt_cli.load_state().access_token == "prod-token"

    def test_an_active_match_does_not_leak_across_environments(self, isolated, monkeypatch):
        """Match 1053 in prod is some unrelated fixture locally."""
        monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", "prod")
        mt_cli.save_state(mt_cli.CLIState(access_token="t", match_id=1053))

        monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", "local")
        assert mt_cli.load_state().match_id is None

    def test_logout_only_clears_the_targeted_environment(self, isolated, monkeypatch):
        monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", "prod")
        mt_cli.save_state(mt_cli.CLIState(access_token="prod-token", username="tom"))
        monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", "local")
        mt_cli.save_state(mt_cli.CLIState(access_token="local-token", username="tom"))

        runner.invoke(mt_cli.app, ["--env", "local", "logout"])

        monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", "prod")
        assert mt_cli.load_state().access_token == "prod-token"
        monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", "local")
        assert mt_cli.load_state().access_token is None


@pytest.mark.unit
class TestMigratingAnOlderStateFile:
    def test_a_flat_file_is_read_as_the_current_environment(self, isolated):
        config, state_file = isolated
        write_config(config, "local")
        state_file.write_text(json.dumps({"access_token": "old", "username": "tom"}))

        assert mt_cli.load_state().access_token == "old"

    def test_and_is_rewritten_in_the_new_shape(self, isolated):
        config, state_file = isolated
        write_config(config, "local")
        state_file.write_text(json.dumps({"access_token": "old", "username": "tom"}))

        mt_cli.save_state(mt_cli.load_state())

        stored = json.loads(state_file.read_text())
        assert stored["environments"]["local"]["access_token"] == "old"

    def test_an_empty_file_is_not_a_crash(self, isolated):
        _, state_file = isolated
        state_file.write_text("{}")
        assert mt_cli.load_state().access_token is None


@pytest.mark.unit
class TestAnnouncingTheTarget:
    def test_prod_says_so(self, isolated, capsys):
        mt_cli._ENV_OVERRIDE = "prod"
        try:
            mt_cli.announce_target()
        finally:
            mt_cli._ENV_OVERRIDE = None
        assert "prod" in capsys.readouterr().out

    def test_local_stays_quiet(self, isolated, capsys):
        # A banner on every local command is noise, and noise is what gets
        # tuned out — including the one that matters.
        mt_cli.announce_target()
        assert capsys.readouterr().out == ""

    def test_it_names_where_the_target_came_from(self, isolated, capsys):
        config, _ = isolated
        write_config(config, "prod")
        mt_cli.announce_target()
        # The file's name, not its absolute path: `mt config` prints the path,
        # and a wrapped temp path in a one-line banner reads as noise.
        assert ".mt-config" in capsys.readouterr().out

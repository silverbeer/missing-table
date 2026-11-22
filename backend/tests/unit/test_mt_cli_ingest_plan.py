"""`mt ingest plan` and `mt ingest apply` (SB-1763) against a stub client: no network, no database."""

import json
from unittest.mock import MagicMock

import httpx
import pytest
from rich.console import Console
from typer.testing import CliRunner

import mt_cli

pytestmark = pytest.mark.unit
runner = CliRunner()

REPORT = {
    "entries": 4,
    "sides": {
        "Academy": {
            "entries": 3,
            "resolved": 1,
            "ambiguous": 0,
            "missing": {"total": 2, "alias_fixable": 1, "needs_create": 1, "unknown": 0},
            "unknown_league": 0,
            "unknown_age_group": 0,
            "resolver": {"wrong_side": 2, "missing": 0},
        },
        "no hint": {
            "entries": 1,
            "resolved": 0,
            "ambiguous": 1,
            "missing": {"total": 0, "alias_fixable": 0, "needs_create": 0, "unknown": 0},
            "unknown_league": 0,
            "unknown_age_group": 0,
            "resolver": {"wrong_side": 0, "missing": 0},
        },
    },
    "matches": {"total": 2, "would_land": 0, "would_land_after_plan": 1},
    "conferences": {
        "placed": [{"league": "Academy", "conference": "New England", "teams": 1, "registrations": 2}],
        "unplaced": 0,
        "unknown": [{"league": "Academy", "conference": "Atlantis", "reason": "MT has no conference by that name"}],
    },
    "ambiguous": [{"name": "Both", "age_group": "U15", "league": None, "reason": "ambiguous: team ids 7, 9"}],
    "unknown": [],
    "actions": {"alias": {"proposed": 1, "needs_review": 0}, "create_team": {"proposed": 0, "needs_review": 1}},
}
ALIAS = {
    "id": "a001",
    "type": "alias",
    "status": "proposed",
    "reason": "…",
    "external_name": "River FC",
    "league": "Academy",
    "team_id": 12,
    "fixes": [{"name": "River FC", "age_group": "U15", "league": "Academy", "status": "wrong_side"}],
}
CREATE = {**ALIAS, "id": "a002", "type": "create_team", "status": "needs_review", "external_name": "Lake United"}
DATABASE = "0123456789ab"
PLANNED = {
    "plan_id": "plan-20261122T160301-ab12cd34",
    "database": DATABASE,
    "report": REPORT,
    "actions": [ALIAS, CREATE],
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mt_cli, "console", Console(width=200))
    monkeypatch.setattr(mt_cli, "get_current_env", lambda: "local")
    stub = MagicMock()
    stub.plan_ingest.return_value = PLANNED
    state = MagicMock(username="tom")
    monkeypatch.setattr(mt_cli, "get_client", lambda: (stub, state))
    return stub


def _write(path, data):
    path.write_text(json.dumps(data))
    return path


def _plan_file(tmp_path, actions, **header):
    plan = {"plan_id": "plan-1", "environment": "local", "database": DATABASE, "actions": actions, **header}
    return _write(tmp_path / "plan.json", {key: value for key, value in plan.items() if value is not None})


class TestPlan:
    MESSAGES = [
        {
            "home_team": "River FC",
            "away_team": "Lake United",
            "age_group": "U15",
            "league": "Academy",
            "competition": "AD Group Play",
            "match_date": "2026-12-02",
            "external_match_id": "m11-75-1",
            "season": "2026-27",
        },
        {"name": "Both", "age_group": "U15", "city": "ignored"},
    ]

    def test_it_writes_the_plan_file_with_its_provenance(self, client, tmp_path):
        teams = _write(tmp_path / "fest.json", self.MESSAGES)
        brackets = _write(tmp_path / "brackets.json", [])
        output = tmp_path / "plan.json"

        out = runner.invoke(
            mt_cli.app, ["ingest", "plan", "--teams", str(teams), "--brackets", str(brackets), "-o", str(output)]
        )

        assert out.exit_code == 0, out.output
        plan = json.loads(output.read_text())
        assert plan["plan_id"] == PLANNED["plan_id"]
        assert plan["generated_by"] == "tom"
        assert plan["environment"] == "local"
        assert plan["database"] == DATABASE
        assert plan["inputs"] == {"teams": "fest.json", "brackets": "brackets.json"}
        assert plan["generated_at"].startswith("20")
        assert plan["report"] == REPORT
        assert plan["actions"] == [ALIAS, CREATE]
        assert list(plan)[:6] == ["plan_id", "generated_at", "generated_by", "environment", "database", "inputs"]

    def test_it_sends_only_the_fields_a_plan_reads(self, client, tmp_path):
        teams = _write(tmp_path / "fest.json", self.MESSAGES)

        runner.invoke(mt_cli.app, ["ingest", "plan", "--teams", str(teams), "-o", str(tmp_path / "plan.json")])

        client.plan_ingest.assert_called_once_with(
            [
                {
                    "home_team": "River FC",
                    "away_team": "Lake United",
                    "age_group": "U15",
                    "league": "Academy",
                    "competition": "AD Group Play",
                },
                {"name": "Both", "age_group": "U15"},
            ],
            None,
        )
        client.apply_ingest_plan.assert_not_called()

    def test_it_prints_the_report_and_says_nothing_changed(self, client, tmp_path):
        teams = _write(tmp_path / "fest.json", self.MESSAGES)
        output = tmp_path / "plan.json"

        out = runner.invoke(mt_cli.app, ["ingest", "plan", "--teams", str(teams), "-o", str(output)]).output

        assert "Academy" in out and "no hint" in out
        assert "0 of 2 now" in out
        assert "Academy / New England: 1 team(s), 2 age group registration(s)" in out
        assert "Bracket not used: Academy / Atlantis" in out
        assert "Ambiguous: Both (U15, no hint)" in out
        assert "alias: 1 proposed, 0 needs review" in out
        assert "create_team: 0 proposed, 1 needs review" in out
        assert "Nothing has been changed" in out
        # The path is long enough to wrap; compare without the line breaks.
        assert f"mt ingest apply {output} --dry-run" in " ".join(out.split())

    def test_input_without_matches_says_so_rather_than_printing_zero(self, client, tmp_path):
        client.plan_ingest.return_value = {**PLANNED, "report": {**REPORT, "matches": None}}
        teams = _write(tmp_path / "names.json", self.MESSAGES[1:])

        out = runner.invoke(mt_cli.app, ["ingest", "plan", "--teams", str(teams), "-o", str(tmp_path / "p.json")])

        assert "carries no matches" in out.output
        assert "would land:" not in out.output

    def test_a_teams_file_that_is_not_json_stops_before_any_call(self, client, tmp_path):
        teams = tmp_path / "fest.json"
        teams.write_text("not json")
        output = tmp_path / "plan.json"

        out = runner.invoke(mt_cli.app, ["ingest", "plan", "--teams", str(teams), "-o", str(output)])

        assert out.exit_code == 1
        assert "is not JSON" in out.output
        client.plan_ingest.assert_not_called()
        assert not output.exists()

    def test_a_missing_teams_file_stops_before_any_call(self, client, tmp_path):
        out = runner.invoke(
            mt_cli.app, ["ingest", "plan", "--teams", str(tmp_path / "absent.json"), "-o", str(tmp_path / "p.json")]
        )

        assert out.exit_code == 1
        assert "Cannot read teams file" in out.output
        client.plan_ingest.assert_not_called()


def _response(*outcomes, closed=()):
    results = [
        {"id": f"a{n:03d}", "type": "alias", "external_name": f"Team {n}", "outcome": outcome, "detail": detail}
        for n, (outcome, detail) in enumerate(outcomes, start=1)
    ]
    return {"plan_id": "plan-1", "dry_run": False, "results": results, "failures_closed": list(closed)}


def _approved(count):
    return [{**ALIAS, "id": f"a{n:03d}", "status": "approved"} for n in range(1, count + 1)]


class TestApply:
    def test_it_says_how_many_were_skipped_as_not_approved(self, client, tmp_path):
        actions = [{**ALIAS, "status": "approved"}, CREATE, {**CREATE, "id": "a003", "status": "proposed"}]
        client.apply_ingest_plan.return_value = _response(
            ("applied", None), ("skipped", "not approved"), ("skipped", "not approved")
        )

        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, actions))])

        assert out.exit_code == 0, out.output
        assert "2 of 3 action(s) skipped: not approved." in out.output
        assert "1 applied · 0 already applied · 0 refused · 0 failed" in out.output
        client.apply_ingest_plan.assert_called_once_with("plan-1", actions, DATABASE, False)

    def test_a_fresh_plan_applies_nothing_and_says_why(self, client, tmp_path):
        client.apply_ingest_plan.return_value = _response(("skipped", "not approved"), ("skipped", "not approved"))

        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, [ALIAS, CREATE]))])

        assert out.exit_code == 0
        assert "0 applied" in out.output
        assert "2 of 2 action(s) skipped: not approved." in out.output
        assert '"status": "approved"' in out.output

    def test_each_outcome_is_printed_with_its_reason_and_a_refusal_fails_the_command(self, client, tmp_path):
        client.apply_ingest_plan.return_value = _response(
            ("applied", None),
            ("already_applied", None),
            ("refused", "the name 'River FC' is already taken by team 11"),
            closed=[{"id": 5, "raw_name": "River FC"}],
        )

        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, _approved(3)))])

        assert out.exit_code == 1
        assert "applied a001 alias Team 1" in out.output
        assert "already applied a002 alias Team 2" in out.output
        assert "refused a003 alias Team 3 — the name 'River FC' is already taken by team 11" in out.output
        assert "1 applied · 1 already applied · 1 refused · 0 failed" in out.output
        assert "1 ingest failure(s) closed" in out.output
        assert "plan plan-1" in out.output

    def test_a_dry_run_is_passed_on_and_named(self, client, tmp_path):
        response = _response(("would_apply", None))
        response["results"][0]["steps"] = ["alias 'River FC' (Academy) → team 12"]
        client.apply_ingest_plan.return_value = response
        actions = _approved(1)

        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, actions)), "--dry-run"])

        assert out.exit_code == 0, out.output
        client.apply_ingest_plan.assert_called_once_with("plan-1", actions, DATABASE, True)
        assert "would apply a001 alias Team 1 — alias 'River FC' (Academy) → team 12" in out.output
        assert "1 would apply" in out.output
        assert "Dry run: nothing was written." in out.output

    def test_a_dry_run_is_one_request_so_shared_rows_are_judged_together(self, client, tmp_path):
        client.apply_ingest_plan.side_effect = lambda plan_id, batch, database, dry_run: _response(
            *[("would_apply", None)] * len(batch)
        )

        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, _approved(35))), "--dry-run"])

        assert [len(call.args[1]) for call in client.apply_ingest_plan.call_args_list] == [35]
        assert "35 would apply" in out.output
        assert not (tmp_path / "plan.applied.json").exists()


class TestApplyInBatches:
    @staticmethod
    def _applied(plan_id, batch, database, dry_run):
        return _response(*[("applied", None)] * len(batch))

    def test_a_long_plan_goes_ten_at_a_time(self, client, tmp_path):
        client.apply_ingest_plan.side_effect = self._applied

        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, _approved(25)))])

        assert out.exit_code == 0, out.output
        assert [len(call.args[1]) for call in client.apply_ingest_plan.call_args_list] == [10, 10, 5]
        assert "25 applied" in out.output

    def test_each_batch_is_printed_as_it_returns(self, client, tmp_path, monkeypatch):
        seen_before_each_call = []
        printed = []
        console = mt_cli.console
        monkeypatch.setattr(console, "print", lambda *args, **kwargs: printed.append(" ".join(map(str, args))))

        def apply(plan_id, batch, database, dry_run):
            seen_before_each_call.append(sum("applied" in line and " alias " in line for line in printed))
            return self._applied(plan_id, batch, database, dry_run)

        client.apply_ingest_plan.side_effect = apply

        runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, _approved(25)))])

        # By the time the second and third requests are made, the earlier outcomes are on screen.
        assert seen_before_each_call == [0, 10, 20]
        assert any("Batch 1 of 3 (actions 1-10)" in line for line in printed)
        assert any("Batch 3 of 3 (actions 21-25)" in line for line in printed)

    @pytest.mark.parametrize(
        "error",
        [httpx.ReadTimeout("timed out"), httpx.ConnectError("connection refused"), mt_cli.APIError("HTTP 502")],
    )
    def test_an_interrupted_batch_is_explained_not_a_traceback(self, client, tmp_path, error):
        calls = []

        def apply(plan_id, batch, database, dry_run):
            calls.append(batch)
            if len(calls) == 2:
                raise error
            return self._applied(plan_id, batch, database, dry_run)

        client.apply_ingest_plan.side_effect = apply

        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, _approved(25)))])
        text = " ".join(out.output.split())

        assert out.exit_code == 1
        assert out.exception is None or isinstance(out.exception, SystemExit)
        assert "Batch 2 of 3 (actions 11-20) did not complete" in text
        assert "1 of 3 batch(es) completed before it." in text
        assert "This batch may have been partly applied" in text
        assert "Run the same command again: apply is idempotent" in text
        assert len(calls) == 2  # the third batch is not attempted

    def test_an_interrupted_dry_run_does_not_claim_anything_was_applied(self, client, tmp_path):
        client.apply_ingest_plan.side_effect = httpx.ReadTimeout("timed out")

        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, _approved(3))), "--dry-run"])

        assert out.exit_code == 1
        assert "did not complete" in out.output
        assert "partly applied" not in out.output


class TestTheAppliedLog:
    IDS = {"club_id": 2, "team_id": 1001, "team_created": True, "alias_id": 77, "mapping_ids": [501]}

    def _apply(self, plan_id, batch, database, dry_run):
        response = _response(*[("applied", None)] * len(batch))
        for row, action in zip(response["results"], batch, strict=True):
            row["id"] = action["id"]
            row["ids"] = {**self.IDS, "team_id": 1000 + int(action["id"][1:])}
            row["steps"] = ["create team", "alias"]
        return response

    def test_what_each_action_wrote_is_recorded_beside_the_plan(self, client, tmp_path):
        client.apply_ingest_plan.side_effect = self._apply
        plan = _plan_file(tmp_path, _approved(12))

        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(plan)])

        log = json.loads((tmp_path / "plan.applied.json").read_text())
        assert (log["plan_id"], log["environment"], log["database"]) == ("plan-1", "local", DATABASE)
        assert [batch["batch"] for batch in log["batches"]] == [1, 2]
        assert [len(batch["actions"]) for batch in log["batches"]] == [10, 2]
        first = log["batches"][0]["actions"][0]
        assert first == {
            "id": "a001",
            "type": "alias",
            "external_name": "Team 1",
            "outcome": "applied",
            "ids": {**self.IDS, "team_id": 1001},
            "steps": ["create team", "alias"],
        }
        assert log["batches"][0]["applied_at"].startswith("20")
        assert "plan.applied.json" in " ".join(out.output.split())

    def test_it_is_saved_after_every_batch_so_an_interruption_keeps_what_was_done(self, client, tmp_path):
        calls = []

        def apply(plan_id, batch, database, dry_run):
            calls.append(batch)
            if len(calls) == 2:
                raise httpx.ReadTimeout("timed out")
            return self._apply(plan_id, batch, database, dry_run)

        client.apply_ingest_plan.side_effect = apply

        runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, _approved(25)))])

        log = json.loads((tmp_path / "plan.applied.json").read_text())
        assert [len(batch["actions"]) for batch in log["batches"]] == [10]

    def test_a_second_run_appends_and_keeps_the_first(self, client, tmp_path):
        client.apply_ingest_plan.side_effect = self._apply
        plan = _plan_file(tmp_path, _approved(2))
        runner.invoke(mt_cli.app, ["ingest", "apply", str(plan)])

        runner.invoke(mt_cli.app, ["ingest", "apply", str(plan)])

        log = json.loads((tmp_path / "plan.applied.json").read_text())
        assert len(log["batches"]) == 2

    def test_closed_failures_are_recorded(self, client, tmp_path):
        closed = [{"id": 5, "raw_name": "River FC", "league": "Academy", "team_id": 12}]
        response = self._apply("plan-1", _approved(1), DATABASE, False)
        response["failures_closed"] = closed
        client.apply_ingest_plan.return_value = response

        runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, _approved(1)))])

        log = json.loads((tmp_path / "plan.applied.json").read_text())
        assert log["batches"][0]["failures_closed"] == closed

    def test_nothing_written_leaves_no_log(self, client, tmp_path):
        client.apply_ingest_plan.return_value = _response(("already_applied", None), ("refused", "taken"))

        runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, _approved(2)))])

        assert not (tmp_path / "plan.applied.json").exists()

    def test_another_plans_log_is_not_appended_to(self, client, tmp_path):
        _write(tmp_path / "plan.applied.json", {"plan_id": "plan-other", "batches": []})

        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, _approved(1)))])

        assert out.exit_code == 1
        assert "is not the applied log of plan plan-1" in " ".join(out.output.split())
        client.apply_ingest_plan.assert_not_called()


class TestWhichDatabaseAPlanIsFor:
    def test_a_plan_made_against_another_environment_is_refused(self, client, tmp_path):
        plan = _plan_file(tmp_path, _approved(1), environment="prod")

        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(plan)])

        assert out.exit_code == 1
        assert "generated against prod" in out.output
        assert "targets local" in out.output
        client.apply_ingest_plan.assert_not_called()

    @pytest.mark.parametrize("missing", ["environment", "database"])
    @pytest.mark.parametrize("flags", [[], ["--dry-run"]])
    def test_a_plan_that_does_not_say_is_refused_not_trusted(self, client, tmp_path, missing, flags):
        plan = _plan_file(tmp_path, _approved(1), **{missing: None})

        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(plan), *flags])

        assert out.exit_code == 1
        assert f'has no "{missing}" in its header' in " ".join(out.output.split())
        client.apply_ingest_plan.assert_not_called()

    def test_the_fingerprint_goes_to_the_server_which_decides(self, client, tmp_path):
        client.apply_ingest_plan.side_effect = mt_cli.APIError(
            "The plan was made against another database (0123456789ab); this one is ffffffffffff."
        )

        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(_plan_file(tmp_path, _approved(1)))])

        assert out.exit_code == 1
        assert client.apply_ingest_plan.call_args.args[2] == DATABASE
        assert "made against another database" in " ".join(out.output.split())

    def test_a_file_that_is_not_a_plan_is_refused(self, client, tmp_path):
        out = runner.invoke(mt_cli.app, ["ingest", "apply", str(_write(tmp_path / "fest.json", [ALIAS]))])

        assert out.exit_code == 1
        assert "is not a plan file" in out.output
        client.apply_ingest_plan.assert_not_called()


class TestTheTimeoutIsLongerForTheseCallsOnly:
    def _client(self):
        from api_client import MissingTableClient

        api = MissingTableClient(base_url="http://api.test", access_token="token")
        api._client = MagicMock()
        api._client.request.return_value = MagicMock(status_code=200, is_success=True, json=lambda: {})
        return api

    def test_plan_and_apply_ask_for_more_time(self):
        api = self._client()

        api.plan_ingest([{"name": "River FC", "age_group": "U15"}])
        api.apply_ingest_plan("plan-1", [], DATABASE, True)

        timeouts = [call.kwargs.get("timeout") for call in api._client.request.call_args_list]
        assert timeouts == [180.0, 180.0]
        assert api._client.request.call_args.kwargs["json"] == {
            "plan_id": "plan-1",
            "database": DATABASE,
            "actions": [],
            "dry_run": True,
        }

    def test_every_other_call_keeps_the_clients_default(self):
        api = self._client()

        api.get_ingest_failures()

        assert "timeout" not in api._client.request.call_args.kwargs
        assert api.timeout == 30.0

"""`mt motw suggest` (SB-1551) against a stub client: no network, no database."""

from unittest.mock import MagicMock

import pytest
from rich.console import Console
from typer.testing import CliRunner

import mt_cli

pytestmark = pytest.mark.unit
runner = CliRunner()

TEAM = {"name": "FC Westchester", "position": 1, "table_size": 13}
RESULT = {
    "week_start": "2026-11-09",
    "week_end": "2026-11-15",
    "current_pick": None,
    "coverage": {"eligible": 48, "fixtures_in_week": 48, "teams_low_sample": 23, "rules_season": "2026-27"},
    "reason": None,
    "candidates": [
        {
            "match_id": 4096,
            "match_date": "2026-11-14",
            "age_group": {"name": "U15"},
            "division": {"name": "Turnpike"},
            "competition": "Flex",
            "home": {"name": "Beachside of Connecticut", "position": 2, "table_size": 13},
            "away": TEAM,
            "score": {"quality": 0.57, "closeness": 0.81, "stakes": 1.0, "form": 0.91, "penalty": 1.0, "total": 0.767},
            "flags": ["qualifying_line"],
            "facts": [{"id": "4096:gap", "text": "1 point separates them."}],
        }
    ],
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mt_cli, "console", Console(width=140))
    stub = MagicMock()
    monkeypatch.setattr(mt_cli, "get_client", lambda: (stub, None))
    return stub


def test_suggest_lists_ranked_candidates(client):
    client.get_motw_candidates.return_value = RESULT
    out = runner.invoke(mt_cli.app, ["motw", "suggest", "--week", "2026-11-14", "--facts"])
    assert out.exit_code == 0, out.output
    client.get_motw_candidates.assert_called_once_with("2026-11-14", limit=5)
    assert "match #4096" in out.output
    assert "FC Westchester (1/13)" in out.output
    assert "48 eligible of 48" in out.output
    assert "4096:gap" in out.output


def test_empty_week_prints_the_reason(client):
    client.get_motw_candidates.return_value = {**RESULT, "candidates": [], "reason": "No pool fixtures are dated."}
    out = runner.invoke(mt_cli.app, ["motw", "suggest"])
    assert out.exit_code == 0
    assert "No pool fixtures" in out.output


def test_existing_pick_is_called_out(client):
    client.get_motw_candidates.return_value = {**RESULT, "current_pick": {"match_id": 4093}}
    out = runner.invoke(mt_cli.app, ["motw", "suggest"])
    assert "Already picked: match #4093" in out.output


def test_api_error_exits_1(client):
    client.get_motw_candidates.side_effect = mt_cli.APIError("Admin access required")
    out = runner.invoke(mt_cli.app, ["motw", "suggest"])
    assert out.exit_code == 1

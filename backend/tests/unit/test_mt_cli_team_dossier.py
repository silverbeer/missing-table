"""`mt team dossier` (SB-1780) against a stub client: no network, no database."""

from unittest.mock import MagicMock

import pytest
from rich.console import Console
from typer.testing import CliRunner

import mt_cli

pytestmark = pytest.mark.unit
runner = CliRunner()

NOTE = (
    "Positions, percentiles and key wins are measured inside each team's own conference table. "
    "Conferences only meet at tournaments, so they are never compared."
)


def conference(kind, league, division, **stats):
    base = {
        "kind": kind,
        "competition": "Flex" if kind == "flex" else "League",
        "division": {"id": 1, "name": division, "league": league},
        "league": league,
        "position": None,
        "table_size": 8,
        "played": 0,
        "wins": None,
        "draws": None,
        "losses": None,
        "gf": None,
        "ga": None,
        "gd": None,
        "ppg": None,
        "gf_per_game": None,
        "ga_per_game": None,
        "clean_sheets": None,
        "strength_percentile": None,
        "low_sample": True,
        "no_results": True,
        "fact_ids": [],
    }
    return {**base, **stats}


RESULT = {
    "team": {"id": 7, "name": "FC Westchester", "club_name": "FC Westchester", "pro_academy": False},
    "age_group": {"id": 3, "name": "U15"},
    "season": {"id": 184, "name": "2026-2027"},
    "context": None,
    "conferences": [
        conference(
            "league",
            "Homegrown",
            "Northeast",
            position=2,
            played=8,
            wins=6,
            draws=1,
            losses=1,
            gf=20,
            ga=6,
            gd=14,
            ppg=2.38,
            clean_sheets=4,
            strength_percentile=88,
            low_sample=False,
            no_results=False,
        ),
        conference("flex", "Flex", "Empire"),
    ],
    "totals": {"played": 8},
    "key_wins": [
        {
            "match_id": 11,
            "date": "2026-10-03",
            "opponent": {"id": 9, "name": "NYCFC"},
            "opponent_conference": None,
            "opponent_position": None,
            "opponent_table_size": None,
            "score": "2-1",
            "kind": "pro_academy_upset",
            "fact_id": "t7:a3:win:11",
        }
    ],
    "form": [
        {"match_id": 11, "date": "2026-10-03", "opponent": {"id": 9, "name": "NYCFC"}, "score": "2-1", "result": "W"}
    ],
    "streak_fact_id": "t7:a3:form:streak",
    "flags": [],
    "facts": [{"id": "t7:a3:form:streak", "text": "FC Westchester have won 4 League/Flex matches in a row."}],
    "coverage": {"note": NOTE},
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mt_cli, "console", Console(width=160))
    stub = MagicMock()
    stub.get_teams.return_value = [{"id": 7, "name": "FC Westchester"}]
    stub.get_age_groups.return_value = [{"id": 3, "name": "U15"}, {"id": 4, "name": "U16"}]
    monkeypatch.setattr(mt_cli, "get_client", lambda: (stub, None))
    return stub


def test_note_first_then_conferences_absent_as_dash(client):
    client.get_team_dossier.return_value = RESULT
    out = runner.invoke(mt_cli.app, ["team", "dossier", "FC Westchester", "--age", "U15"])
    assert out.exit_code == 0, out.output
    client.get_team_dossier.assert_called_once_with(7, age_group_id=3, for_match_id=None)
    assert out.output.index("never compared") < out.output.index("Northeast")
    assert "2/8" in out.output
    empire = next(row for row in out.output.splitlines() if "Empire" in row)
    assert "—" in empire and " 0-0" not in empire  # absent renders as absent, not 0
    assert "pro_academy_upset" in out.output
    assert "won 4 League/Flex matches in a row" in out.output


def test_for_match_shows_playing_up(client):
    ctx = {
        "match_id": 601,
        "bracket_age_group": {"id": 4, "name": "U16"},
        "season_age_group": {"id": 3, "name": "U15"},
        "playing_up": True,
        "playing_up_inferred": True,
    }
    client.get_team_dossier.return_value = {**RESULT, "context": ctx, "flags": ["playing_up", "playing_up_inferred"]}
    out = runner.invoke(mt_cli.app, ["team", "dossier", "7", "--match", "601"])
    assert out.exit_code == 0, out.output
    client.get_team_dossier.assert_called_once_with(7, age_group_id=None, for_match_id=601)
    assert "Playing up in match 601" in out.output
    assert "inferred" in out.output


def test_no_registration_says_so(client):
    client.get_team_dossier.return_value = {**RESULT, "conferences": [], "flags": ["no_conference", "no_results"]}
    out = runner.invoke(mt_cli.app, ["team", "dossier", "7", "-a", "U15"])
    assert out.exit_code == 0
    assert "No U15 registration" in out.output


def test_needs_an_age_or_a_match(client):
    out = runner.invoke(mt_cli.app, ["team", "dossier", "7"])
    assert out.exit_code == 1
    client.get_team_dossier.assert_not_called()


def test_json(client):
    client.get_team_dossier.return_value = RESULT
    out = runner.invoke(mt_cli.app, ["team", "dossier", "7", "-a", "U15", "--json"])
    assert out.exit_code == 0, out.output
    assert '"streak_fact_id": "t7:a3:form:streak"' in out.output


def test_api_error_exits_1(client):
    client.get_team_dossier.side_effect = mt_cli.APIError("No match with id 9999.")
    out = runner.invoke(mt_cli.app, ["team", "dossier", "7", "--match", "9999"])
    assert out.exit_code == 1
    assert "No match with id 9999" in out.output

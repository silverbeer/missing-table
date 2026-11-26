"""`mt leaders` (SB-1781) against a stub client: no network, no database."""

from unittest.mock import MagicMock

import pytest
from rich.console import Console
from typer.testing import CliRunner

import mt_cli

pytestmark = pytest.mark.unit
runner = CliRunner()


def row(rank, team_id, name, conference, gp, value, **extra):
    return {
        "rank": rank,
        "team": {"id": team_id, "name": name, "club_name": None},
        "conference": conference,
        "no_conference": conference is None,
        "gp": gp,
        "w": gp,
        "d": 0,
        "l": 0,
        "value": value,
        **extra,
    }


NOTE = (
    "12 teams from 2 conferences, plus 1 with no Homegrown conference. Conferences only meet at tournaments, "
    "so this compares stats across conferences: a stat board, not a ranking. Teams with fewer than 6 games are listed, not ranked. "
    "Level scores count as draws; Flex shootout points are not counted."
)
RESULT = {
    "league": "Homegrown",
    "age_group": {"id": 3, "name": "U15"},
    "season": {"id": 184, "name": "2026-2027"},
    "coverage": {"teams": 12, "matches": 30, "min_gp": 6, "note": NOTE},
    "reason": None,
    "boards": [
        {
            "key": "pts",
            "title": "Points (W=3, D=1; shootouts count as draws)",
            "variant": "total",
            "better": "higher",
            "rows": [row(1, 1, "FC Westchester", "Northeast", 8, 24), row(2, 7, "Flex Only FC", None, 6, 18)],
            "unranked_count": 1,
        },
        {
            "key": "ppg",
            "title": "Points per game",
            "variant": "per_game",
            "better": "higher",
            "rows": [],
            "unranked_count": 1,
        },
        {
            "key": "pro_wins",
            "title": "Wins over pro academies",
            "variant": "total",
            "better": "higher",
            "rows": [row(1, 1, "FC Westchester", "Northeast", 8, 1, pro_games=2)],
            "unranked_count": 1,
        },
    ],
    "unranked": [row(None, 3, "Newcomers SC", "Southeast", 4, None)],
    "unranked_count": 9,
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mt_cli, "console", Console(width=160))
    stub = MagicMock()
    monkeypatch.setattr(mt_cli, "get_client", lambda: (stub, None))
    return stub


def test_coverage_comes_first_then_boards(client):
    client.get_leaderboards.return_value = RESULT
    out = runner.invoke(mt_cli.app, ["leaders", "U15", "-l", "Homegrown"])
    assert out.exit_code == 0, out.output
    client.get_leaderboards.assert_called_once_with("U15", league="Homegrown", season=None, limit=20)
    assert out.output.index("not a ranking") < out.output.index("FC Westchester")
    assert "30 matches" in out.output
    assert "no conference" in out.output
    assert "Points per game: nobody ranked yet · 1 unranked" in out.output
    # The unranked list is printed once, not per board, with its count.
    assert out.output.count("Newcomers SC") == 1
    assert "Unranked: under 6 games (1 of 9, most games first)" in out.output
    assert "1 of 2" in out.output  # pro wins carry their denominator


def test_one_board(client):
    client.get_leaderboards.return_value = RESULT
    out = runner.invoke(mt_cli.app, ["leaders", "U15", "--board", "pro_wins"])
    assert out.exit_code == 0, out.output
    assert "Wins over pro academies · pro_wins" in out.output
    assert "Points (W=3" not in out.output


def test_unknown_board_exits_1_without_calling(client):
    out = runner.invoke(mt_cli.app, ["leaders", "U15", "--board", "elo"])
    assert out.exit_code == 1
    client.get_leaderboards.assert_not_called()


def test_empty_age_group_prints_the_reason(client):
    client.get_leaderboards.return_value = {**RESULT, "reason": "No League or Flex results at U15 yet."}
    out = runner.invoke(mt_cli.app, ["leaders", "U15"])
    assert out.exit_code == 0
    assert "No League or Flex results" in out.output


def test_json(client):
    client.get_leaderboards.return_value = RESULT
    out = runner.invoke(mt_cli.app, ["leaders", "U15", "--json", "-n", "5", "--season", "2025-2026"])
    assert out.exit_code == 0, out.output
    client.get_leaderboards.assert_called_once_with("U15", league="Homegrown", season="2025-2026", limit=5)
    assert '"key": "pts"' in out.output


def test_api_error_exits_1(client):
    client.get_leaderboards.side_effect = mt_cli.APIError("age_group must be one of U13, U15")
    out = runner.invoke(mt_cli.app, ["leaders", "U99"])
    assert out.exit_code == 1
    assert "age_group must be one of" in out.output

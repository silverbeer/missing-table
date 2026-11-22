"""The round keys must agree everywhere they are hand-listed (SB-1752).

Three copies of VALID_ROUNDS exist: the DAO (authoritative), the ``mt`` CLI,
and the load-tournament-matches skill script. The skill script is parsed with
``ast`` rather than imported because importing it mutates sys.path and builds
a typer app.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.backend]

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_SCRIPT = REPO_ROOT / ".claude/skills/load-tournament-matches/scripts/mt.py"
NEW_ROUNDS = {"showcase", "consolation", "placement_final"}


def _literal_valid_rounds(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "VALID_ROUNDS" for t in node.targets
        ):
            return set(ast.literal_eval(node.value))
    raise AssertionError(f"no top-level VALID_ROUNDS literal in {path}")


def test_skill_script_rounds_match_the_dao():
    from dao.tournament_dao import VALID_ROUNDS

    assert SKILL_SCRIPT.exists()
    assert _literal_valid_rounds(SKILL_SCRIPT) == VALID_ROUNDS


def test_cli_rounds_match_the_dao():
    from dao.tournament_dao import VALID_ROUNDS
    from mt_cli import VALID_ROUNDS as CLI_ROUNDS

    assert set(CLI_ROUNDS) == VALID_ROUNDS


def test_dao_accepts_the_new_fest_rounds():
    from dao.tournament_dao import VALID_ROUNDS

    assert NEW_ROUNDS <= VALID_ROUNDS

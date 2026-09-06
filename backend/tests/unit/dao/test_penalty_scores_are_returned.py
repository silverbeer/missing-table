"""The shootout must survive the flatten (SB-1026).

An MLS NEXT Flex fixture cannot end level: a regulation draw is decided on
penalties. The columns have existed since the tournament work and the ingest
fills them, but every read path flattens a row into a curated dict, and none of
them copied the pair — so the match page rendered a draw the competition does
not allow, and the ingest's own change detection compared the message against a
dict with no such key and re-wrote the same values on every run.
"""

import ast
import inspect
import textwrap

import pytest

from dao import match_dao

# Flattening functions: they build a dict literal carrying home_score.
READ_PATHS = [
    "get_match_by_external_id",
    "get_match_by_teams_and_date",
    "get_all_matches",
    "get_matches_by_team",
    "get_match_by_id",
    "get_live_matches",
    "get_live_match_state",
]


def _flattened_keys(func_name: str) -> list[set[str]]:
    """Key sets of every dict literal in a function that carries home_score."""
    source = inspect.getsource(getattr(match_dao.MatchDAO, func_name))
    tree = ast.parse(textwrap.dedent(source))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = {k.value for k in node.keys if isinstance(k, ast.Constant)}
        if "home_score" in keys:
            found.append(keys)
    return found


@pytest.mark.parametrize("func_name", READ_PATHS)
def test_a_read_path_returns_the_shootout(func_name):
    """The dict handed back to a caller carries the pair.

    Asserted on the response shape rather than on every dict in the function:
    some of these also build a query filter or an update payload from the same
    score fields, and penalties do not belong in those — the table's CHECK
    constraints reject them on anything but a level score.
    """
    dicts = _flattened_keys(func_name)
    assert dicts, f"{func_name} no longer flattens a match — update this test"

    carrying = [
        keys
        for keys in dicts
        if {"home_penalty_score", "away_penalty_score"} <= keys
    ]
    assert carrying, (
        f"{func_name} returns a match with a score and no shootout; "
        f"key sets seen: {[sorted(k)[:6] for k in dicts]}"
    )

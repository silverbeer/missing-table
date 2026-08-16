"""Every get_match_by_id call site must pass include_test (SB-647).

`MatchDAO.get_match_by_id` defaults `include_test=False` and filters out
`is_test` rows. A handler that omits the kwarg therefore 404s on the TSC test
world before any permission check runs — reads of a test match succeed while
writes to it fail, which is what blocked the Android dry run on its first
action.

That defect was 23 handlers each missing one keyword argument, so the useful
guard is structural rather than behavioural: parse app.py and assert the call
sites are correct. This catches a *new* handler added without the kwarg, which
an endpoint-by-endpoint integration test never would.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.backend]

APP_PY = Path(__file__).resolve().parents[2] / "app.py"


def _call_sites() -> list[ast.Call]:
    tree = ast.parse(APP_PY.read_text())
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get_match_by_id"
    ]


def test_app_py_actually_calls_get_match_by_id():
    """Guard the guard: a rename must not silently empty this test."""
    assert len(_call_sites()) > 10, (
        "found almost no get_match_by_id call sites — was it renamed? "
        "Update this test rather than deleting it."
    )


def test_every_call_site_passes_include_test():
    offenders = [
        site.lineno
        for site in _call_sites()
        if not any(kw.arg == "include_test" for kw in site.keywords)
    ]
    assert not offenders, (
        "app.py:"
        + ", app.py:".join(str(line) for line in offenders)
        + " call get_match_by_id without include_test. It defaults to False and "
        "filters out is_test rows, so these will 404 on the test world. Pass "
        "include_test=viewer_sees_test_content(current_user)."
    )


def test_call_sites_derive_visibility_from_the_viewer():
    """A blanket include_test=True would disable the partition, not honour it."""
    bad = []
    for site in _call_sites():
        for kw in site.keywords:
            if kw.arg != "include_test":
                continue
            # Expected: include_test=viewer_sees_test_content(current_user)
            ok = (
                isinstance(kw.value, ast.Call)
                and isinstance(kw.value.func, ast.Name)
                and kw.value.func.id == "viewer_sees_test_content"
            )
            if not ok:
                bad.append(site.lineno)
    assert not bad, (
        "app.py:"
        + ", app.py:".join(str(line) for line in bad)
        + " pass include_test as something other than "
        "viewer_sees_test_content(current_user). A constant True would let real "
        "users reach test matches; a constant False reintroduces SB-647."
    )


# ---------------------------------------------------------------------------
# SB-649 — the same defect one layer down, in the DAO's own read-backs
# ---------------------------------------------------------------------------

MATCH_DAO_PY = Path(__file__).resolve().parents[2] / "dao" / "match_dao.py"

# Methods that mutate and then read the row back to return it. The read-back
# must pass include_test=True: the caller was already authorised to write, so
# re-applying the partition returns None and the handler reports a 500 for an
# update that actually succeeded.
MUTATING_METHODS = {"update_match_clock", "reopen_match", "update_match_score"}


def _dao_readbacks() -> list[tuple[str, ast.Call]]:
    """(enclosing method, call) for every self.get_live_match_state(...) in the DAO."""
    tree = ast.parse(MATCH_DAO_PY.read_text())
    found = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get_live_match_state"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
            ):
                found.append((fn.name, node))
    return found


def test_the_known_mutating_methods_still_exist():
    """Guard the guard: a rename must not silently empty this test."""
    names = {name for name, _ in _dao_readbacks()}
    missing = MUTATING_METHODS - names
    assert not missing, (
        f"{sorted(missing)} no longer read state back via get_live_match_state — "
        "were they renamed or refactored? Update MUTATING_METHODS."
    )


def test_post_write_readbacks_pass_include_test():
    offenders = [
        f"{name} (match_dao.py:{call.lineno})"
        for name, call in _dao_readbacks()
        if name in MUTATING_METHODS
        and not any(kw.arg == "include_test" for kw in call.keywords)
    ]
    assert not offenders, (
        "these post-write read-backs omit include_test: "
        + ", ".join(offenders)
        + ". get_live_match_state defaults it to False and filters is_test rows, "
        "so the write succeeds and the caller still sees a failure (SB-649). "
        "Pass include_test=True — the caller was already authorised to write."
    )

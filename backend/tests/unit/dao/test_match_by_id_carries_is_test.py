"""get_match_by_id must return is_test (SB-1534).

The notification dispatcher loads a match with include_test=True and then
narrows a test match's audience to admins and test users, and keeps it out of
club channels, on this flag. The read path flattens the row into a curated
dict, so a missing key would make every rehearsal look like a real match and
push it to real followers and public club rooms.
"""

import ast
import inspect
import textwrap

import pytest

from dao import match_dao

pytestmark = [pytest.mark.unit, pytest.mark.backend]


def _flattened_keys() -> list[set[str]]:
    source = inspect.getsource(match_dao.MatchDAO.get_match_by_id)
    tree = ast.parse(textwrap.dedent(source))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = {k.value for k in node.keys if isinstance(k, ast.Constant)}
        if "home_score" in keys:
            found.append(keys)
    return found


def test_get_match_by_id_flatten_carries_is_test():
    flattened = _flattened_keys()
    assert flattened, "get_match_by_id no longer builds a flattened dict; update this test"
    assert all("is_test" in keys for keys in flattened)

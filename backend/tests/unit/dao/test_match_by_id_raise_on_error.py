"""MatchDAO.get_match_by_id(raise_on_error=...) (SB-1780).

The default keeps the endpoints' behaviour (a failed read is None); the team
dossier passes True so a failed read is "unavailable", not "no such match".
"""

from unittest.mock import MagicMock

import pytest

from dao.match_dao import MatchDAO

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]


def _dao(execute):
    dao = MatchDAO.__new__(MatchDAO)
    dao.connection_holder = MagicMock()
    query = MagicMock()
    for method in ("select", "eq"):
        getattr(query, method).return_value = query
    query.execute.side_effect = execute
    client = MagicMock()
    client.table.return_value = query
    dao.client = client
    return dao


def test_a_failed_read_is_none_by_default():
    assert _dao(RuntimeError("PostgREST down")).get_match_by_id(1) is None


def test_a_failed_read_raises_when_asked():
    with pytest.raises(RuntimeError):
        _dao(RuntimeError("PostgREST down")).get_match_by_id(1, raise_on_error=True)


def test_an_unknown_match_is_none_either_way():
    assert _dao([MagicMock(data=[])]).get_match_by_id(1, raise_on_error=True) is None

"""Dry-running a load before it writes (SB-823).

The failure this prevents is not a crash. On the tournament path an unknown
name silently CREATES a lightweight team — that is how a duplicate IFA
appeared and had to be merged back by a script no longer in the repo. Being
able to ask "which of these do you already know?" turns a load from something
you react to into something you inspect.
"""

from unittest.mock import MagicMock

import pytest

from dao.team_dao import TeamDAO

IFA = {"id": 19, "name": "IFA"}
LONG = "Intercontinental Football Academy of New England"


def _dao(direct=None, resolved=None, similar=None):
    dao = object.__new__(TeamDAO)
    dao.connection_holder = MagicMock()
    client = MagicMock()
    table = MagicMock()
    for m in ("select", "ilike", "eq", "limit"):
        getattr(table, m).return_value = table
    table.execute.return_value = MagicMock(data=similar or [])
    client.table.return_value = table
    dao.client = client
    dao._table = table
    dao.get_team_by_name = MagicMock(return_value=direct)
    dao.resolve_team_by_name = MagicMock(return_value=resolved)
    return dao


@pytest.mark.unit
class TestReconcileNames:
    def test_a_direct_name_match_is_known(self):
        dao = _dao(direct=IFA)
        [r] = dao.reconcile_names(["IFA"])
        assert r["status"] == "known"
        assert r["team_id"] == 19

    def test_an_alias_hit_is_reported_as_alias_not_known(self):
        # Both mean "will resolve", but an alias hit says the feed and the
        # database disagree on spelling — worth seeing even when nothing is
        # broken, because it is the thing that goes stale silently.
        dao = _dao(direct=None, resolved=IFA)
        [r] = dao.reconcile_names([LONG])
        assert r["status"] == "alias"
        assert r["team_name"] == "IFA"

    def test_an_unknown_name_is_unknown(self):
        dao = _dao(direct=None, resolved=None, similar=[])
        [r] = dao.reconcile_names(["Brand New Club"])
        assert r["status"] == "unknown"

    def test_an_unknown_name_carries_near_matches(self):
        # A name one word away from an existing team is the signal a human
        # needs to spot a rename.
        dao = _dao(direct=None, resolved=None, similar=[{"id": 34, "name": "New York Red Bulls"}])
        [r] = dao.reconcile_names(["Red Bull New York"])
        assert r["status"] == "unknown"
        assert r["similar"][0]["name"] == "New York Red Bulls"

    def test_it_never_creates_anything(self):
        # The entire point. A reconcile that writes is just a load.
        dao = _dao(direct=None, resolved=None, similar=[])
        dao.reconcile_names(["Brand New Club"])
        dao._table.insert.assert_not_called()

    def test_league_scopes_alias_resolution(self):
        # The same string can point at different teams in different leagues.
        dao = _dao(direct=None, resolved=IFA)
        dao.reconcile_names([LONG], league_id=1)
        assert dao.resolve_team_by_name.call_args.kwargs["league_id"] == 1

    def test_a_blank_name_is_unknown_rather_than_an_error(self):
        # Feeds send junk. One bad row must not sink a 500-name dry run.
        dao = _dao(direct=IFA)
        results = dao.reconcile_names(["", "   "])
        assert [r["status"] for r in results] == ["unknown", "unknown"]

    def test_whitespace_is_normalised_before_lookup(self):
        dao = _dao(direct=IFA)
        [r] = dao.reconcile_names(["  IFA   "])
        assert r["status"] == "known"
        assert dao.get_team_by_name.call_args.args[0] == "IFA"

    def test_the_original_string_is_echoed_back(self):
        # The caller needs to map results onto what it sent, and the fix for an
        # unknown is to alias the string verbatim.
        dao = _dao(direct=IFA)
        [r] = dao.reconcile_names(["  IFA  "])
        assert r["name"] == "  IFA  "

    def test_mixed_statuses_in_one_call(self):
        dao = _dao(direct=None, resolved=None, similar=[])
        dao.get_team_by_name = MagicMock(side_effect=lambda n: IFA if n == "IFA" else None)
        results = dao.reconcile_names(["IFA", "Brand New Club"])
        assert [r["status"] for r in results] == ["known", "unknown"]


@pytest.mark.unit
class TestSimilarTeams:
    def test_generic_words_do_not_drive_near_matches(self):
        # Every other club is a "Soccer Club"; matching on that returns noise.
        dao = _dao(similar=[{"id": 1, "name": "Anything"}])
        dao._similar_teams("Soccer Club Academy United", limit=5)
        dao._table.ilike.assert_not_called()

    def test_a_lookup_failure_does_not_sink_the_reconcile(self):
        # Near-matches are a convenience on top of the answer that matters.
        dao = _dao(direct=None, resolved=None)
        dao._table.execute.side_effect = RuntimeError("db down")
        [r] = dao.reconcile_names(["Brand New Club"])
        assert r["status"] == "unknown"
        assert r["similar"] == []

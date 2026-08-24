"""Alias resolution for team names (SB-822).

Team identity is the teams.name string. A feed that spells a team differently
does not match — and on the tournament path it does not fail either, it CREATES
a second team. That is how 'Intercontinental Football Academy of New England'
became a duplicate IFA, cleaned up by a fix_duplicate_ifa_teams.py that is no
longer in the repo.

The alias check inside get_or_create_opponent_team is the load-bearing one:
everywhere else a miss is a failed lookup, but there a miss is a new row.
"""

from unittest.mock import MagicMock

import pytest

LONG_NAME = "Intercontinental Football Academy of New England"
IFA = {"id": 19, "name": "IFA", "city": "Boston, MA", "club_id": 1}


def _team_dao(direct=None, alias_team_id=None, by_id=None):
    from dao.team_dao import TeamDAO

    dao = object.__new__(TeamDAO)
    dao.connection_holder = MagicMock()
    client = MagicMock()

    def table(name):
        t = MagicMock()
        t.select.return_value = t
        t.ilike.return_value = t
        t.eq.return_value = t
        t.order.return_value = t
        t.limit.return_value = t
        if name == "teams":
            t.execute.return_value = MagicMock(data=[direct] if direct else [])
        elif name == "team_aliases":
            t.execute.return_value = MagicMock(data=[{"team_id": alias_team_id}] if alias_team_id else [])
        else:
            t.execute.return_value = MagicMock(data=[])
        return t

    client.table.side_effect = table
    dao.client = client
    # get_team_by_id is @dao_cache-decorated; stub it rather than fight the cache.
    dao.get_team_by_id = MagicMock(return_value=by_id)
    return dao


@pytest.mark.unit
class TestResolveTeamByName:
    def test_direct_name_match_wins_without_touching_aliases(self):
        dao = _team_dao(direct=IFA)
        assert dao.resolve_team_by_name("IFA")["id"] == 19
        dao.get_team_by_id.assert_not_called()

    def test_alias_resolves_to_the_canonical_team(self):
        # The case that produced a duplicate before this existed.
        dao = _team_dao(direct=None, alias_team_id=19, by_id=IFA)
        resolved = dao.resolve_team_by_name(LONG_NAME)
        assert resolved["name"] == "IFA"

    def test_unknown_name_resolves_to_none(self):
        # None is the correct answer for a genuinely new team. Callers decide
        # what to do about it; the point is that they get to decide.
        dao = _team_dao(direct=None, alias_team_id=None)
        assert dao.resolve_team_by_name("Some Brand New Club") is None

    def test_whitespace_is_normalised_before_lookup(self):
        dao = _team_dao(direct=IFA)
        assert dao.resolve_team_by_name("  IFA   ") is not None

    @pytest.mark.parametrize("empty", ["", "   ", None])
    def test_empty_input_is_none_rather_than_a_lookup(self, empty):
        dao = _team_dao(direct=IFA)
        assert dao.resolve_team_by_name(empty) is None


def _tournament_dao(exact=None, alias_team_id=None):
    from dao.tournament_dao import TournamentDAO

    dao = object.__new__(TournamentDAO)
    dao.connection_holder = MagicMock()
    client = MagicMock()
    created = {"calls": []}

    def table(name):
        t = MagicMock()
        t.select.return_value = t
        t.ilike.return_value = t
        t.eq.return_value = t
        t.limit.return_value = t

        def _insert(row):
            created["calls"].append(row)
            inserted = MagicMock()
            inserted.execute.return_value = MagicMock(data=[{"id": 999, **row}])
            return inserted

        t.insert.side_effect = _insert
        if name == "teams":
            t.execute.return_value = MagicMock(data=[exact] if exact else [])
        elif name == "team_aliases":
            t.execute.return_value = MagicMock(data=[{"team_id": alias_team_id}] if alias_team_id else [])
        else:
            t.execute.return_value = MagicMock(data=[])
        return t

    client.table.side_effect = table
    dao.client = client
    return dao, created


@pytest.mark.unit
class TestGetOrCreateOpponentTeamUsesAliases:
    def test_alias_hit_returns_the_existing_team_and_creates_nothing(self):
        # The whole point. Before this, the long name missed and a second IFA
        # was inserted.
        dao, created = _tournament_dao(exact=None, alias_team_id=19)

        team_id = dao.get_or_create_opponent_team(LONG_NAME, age_group_id=2)

        assert team_id == 19
        assert [c for c in created["calls"] if "name" in c] == [], "an aliased name must not create a team"

    def test_a_genuinely_unknown_name_still_creates(self):
        # The escape hatch has to survive: tournaments do meet teams MT has
        # never seen, and refusing them would be worse than a lightweight row.
        dao, created = _tournament_dao(exact=None, alias_team_id=None)

        dao.get_or_create_opponent_team("Genuinely New Club", age_group_id=2)

        # Two inserts: the team, then its team_mappings row. Assert on the team
        # rather than the count, so adding another side effect later does not
        # fail this test spuriously.
        team_inserts = [c for c in created["calls"] if "name" in c]
        assert len(team_inserts) == 1
        assert team_inserts[0]["name"] == "Genuinely New Club"

    def test_direct_match_short_circuits_before_aliases(self):
        dao, created = _tournament_dao(exact={"id": 19, "name": "IFA"})

        assert dao.get_or_create_opponent_team("IFA", age_group_id=2) == 19
        assert [c for c in created["calls"] if "name" in c] == []

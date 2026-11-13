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


def _team_dao(direct=None, alias_rows=None, by_id=None):
    from dao.team_dao import TeamDAO

    dao = object.__new__(TeamDAO)
    dao.connection_holder = MagicMock()
    client = MagicMock()
    _tables: dict = {}

    def table(name):
        if name in _tables:
            return _tables[name]
        t = MagicMock()
        _tables[name] = t
        t.select.return_value = t
        t.ilike.return_value = t
        t.eq.return_value = t
        t.order.return_value = t
        t.limit.return_value = t
        if name == "teams":
            t.execute.return_value = MagicMock(data=[direct] if direct else [])
        elif name == "team_aliases":
            t.execute.return_value = MagicMock(data=alias_rows or [])
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
        dao = _team_dao(
            direct=None, alias_rows=[{"team_id": 19, "league_id": None, "source": "mlssoccer.com"}], by_id=IFA
        )
        resolved = dao.resolve_team_by_name(LONG_NAME)
        assert resolved["name"] == "IFA"

    def test_unknown_name_resolves_to_none(self):
        # None is the correct answer for a genuinely new team. Callers decide
        # what to do about it; the point is that they get to decide.
        dao = _team_dao(direct=None, alias_rows=[])
        assert dao.resolve_team_by_name("Some Brand New Club") is None

    def test_whitespace_is_normalised_before_lookup(self):
        dao = _team_dao(direct=IFA)
        assert dao.resolve_team_by_name("  IFA   ") is not None

    @pytest.mark.parametrize("empty", ["", "   ", None])
    def test_empty_input_is_none_rather_than_a_lookup(self, empty):
        dao = _team_dao(direct=IFA)
        assert dao.resolve_team_by_name(empty) is None

    def test_an_ambiguous_alias_refuses_to_guess(self):
        # The table is scoped (external_name, league_id, source), so the same
        # string can legitimately point at different teams in different
        # leagues. This resolver is league-agnostic, and silently picking the
        # wrong team is worse than reporting the name unresolved.
        dao = _team_dao(
            direct=None,
            alias_rows=[
                {"team_id": 19, "league_id": 1, "source": "mlssoccer.com"},
                {"team_id": 77, "league_id": 2, "source": "mlssoccer.com"},
            ],
            by_id=IFA,
        )
        assert dao.resolve_team_by_name("Shared Name") is None

    def test_the_same_team_via_several_sources_still_resolves(self):
        # Two feeds spelling one team the same way is not ambiguity.
        dao = _team_dao(
            direct=None,
            alias_rows=[
                {"team_id": 19, "league_id": 1, "source": "mlssoccer.com"},
                {"team_id": 19, "league_id": 1, "source": "kitman"},
            ],
            by_id=IFA,
        )
        assert dao.resolve_team_by_name(LONG_NAME)["id"] == 19


@pytest.mark.unit
class TestResolveTeamByNameScopedToLeague:
    """SB-830: match ingest knows its league, so ambiguity is resolvable.

    The 2026-2027 Kitman feeds publish three competitions whose bracket names
    overlap. A caller that knows which one it is reading should not be handed
    None just because some other league uses the same string.
    """

    OTHER = {"id": 77, "name": "Some Other Team", "city": None, "club_id": 9}

    def test_league_scope_resolves_an_otherwise_ambiguous_alias(self):
        dao = _team_dao(
            direct=None,
            alias_rows=[
                {"team_id": 19, "league_id": 1, "source": "kitman"},
                {"team_id": 77, "league_id": 2, "source": "kitman"},
            ],
            by_id=IFA,
        )
        assert dao.resolve_team_by_name("Shared Name") is None  # unscoped: refuses
        assert dao.resolve_team_by_name("Shared Name", league_id=1)["id"] == 19

    def test_a_league_agnostic_alias_still_matches_when_scoped(self):
        # league_id NULL means "this spelling applies everywhere". Scoping must
        # narrow ambiguity, never drop a hit that was always going to be right.
        dao = _team_dao(
            direct=None,
            alias_rows=[{"team_id": 19, "league_id": None, "source": "kitman"}],
            by_id=IFA,
        )
        assert dao.resolve_team_by_name(LONG_NAME, league_id=1)["id"] == 19

    def test_scoping_to_a_league_with_no_alias_row_falls_back_rather_than_blanks(self):
        # Only league 2 has this alias. Asking as league 1 leaves nothing
        # scoped, so the unscoped rows are judged as before — one team_id, so
        # it resolves. The alternative (return None) would break every feed
        # whose league name we failed to map.
        dao = _team_dao(
            direct=None,
            alias_rows=[{"team_id": 19, "league_id": 2, "source": "kitman"}],
            by_id=IFA,
        )
        assert dao.resolve_team_by_name(LONG_NAME, league_id=1)["id"] == 19

    def test_unknown_name_is_still_none_when_scoped(self):
        dao = _team_dao(direct=None, alias_rows=[])
        assert dao.resolve_team_by_name("Some Brand New Club", league_id=1) is None


@pytest.mark.unit
class TestLeagueScopedAliasBeatsExactName:
    """SB-1652: a club's Homegrown team holds the bare club name.

    The Academy feed sends 'FC Greater Boston Bolts' for the club's Academy
    team, which MT keeps as 'FC Greater Boston Bolts Academy'. With the exact
    name checked first, 22 Academy fixtures landed on Homegrown team rows and
    no alias could redirect them.
    """

    ACADEMY = 2
    HG_BOLTS = {"id": 17, "name": "FC Greater Boston Bolts", "city": "Waltham, MA", "club_id": 15}
    AC_BOLTS = {"id": 178, "name": "FC Greater Boston Bolts Academy", "city": None, "club_id": 15}

    def test_an_alias_scoped_to_the_league_wins_over_the_exact_name(self):
        dao = _team_dao(
            direct=self.HG_BOLTS,
            alias_rows=[{"team_id": 178, "league_id": self.ACADEMY, "source": "mlssoccer.com"}],
            by_id=self.AC_BOLTS,
        )
        assert dao.resolve_team_by_name("FC Greater Boston Bolts", league_id=self.ACADEMY)["id"] == 178

    def test_another_league_still_gets_the_exact_name(self):
        # Homegrown ingest of the same string must stay on the Homegrown row.
        dao = _team_dao(
            direct=self.HG_BOLTS,
            alias_rows=[{"team_id": 178, "league_id": self.ACADEMY, "source": "mlssoccer.com"}],
            by_id=self.AC_BOLTS,
        )
        assert dao.resolve_team_by_name("FC Greater Boston Bolts", league_id=1)["id"] == 17
        dao.get_team_by_id.assert_not_called()

    def test_a_league_agnostic_alias_does_not_override_the_exact_name(self):
        # Only a deliberate, league-scoped alias jumps the queue; the existing
        # NULL-league aliases keep their old precedence.
        dao = _team_dao(
            direct=self.HG_BOLTS,
            alias_rows=[{"team_id": 178, "league_id": None, "source": "mlssoccer.com"}],
            by_id=self.AC_BOLTS,
        )
        assert dao.resolve_team_by_name("FC Greater Boston Bolts", league_id=self.ACADEMY)["id"] == 17

    def test_without_a_league_the_exact_name_wins_as_before(self):
        dao = _team_dao(
            direct=self.HG_BOLTS,
            alias_rows=[{"team_id": 178, "league_id": self.ACADEMY, "source": "mlssoccer.com"}],
            by_id=self.AC_BOLTS,
        )
        assert dao.resolve_team_by_name("FC Greater Boston Bolts")["id"] == 17

    def test_two_teams_scoped_to_the_same_league_refuse_to_guess(self):
        dao = _team_dao(
            direct=self.HG_BOLTS,
            alias_rows=[
                {"team_id": 178, "league_id": self.ACADEMY, "source": "mlssoccer.com"},
                {"team_id": 999, "league_id": self.ACADEMY, "source": "kitman"},
            ],
            by_id=self.AC_BOLTS,
        )
        assert dao.resolve_team_by_name("FC Greater Boston Bolts", league_id=self.ACADEMY) is None


def _tournament_dao(exact=None, alias_team_id=None):
    from dao.tournament_dao import TournamentDAO

    dao = object.__new__(TournamentDAO)
    dao.connection_holder = MagicMock()
    client = MagicMock()
    created: dict[str, list] = {"calls": []}
    _tables: dict = {}

    def table(name):
        if name in _tables:
            return _tables[name]
        t = MagicMock()
        _tables[name] = t
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
class TestAliasQueryUsesTheRealColumn:
    """The alias column is `external_name`, not `alias`.

    The table pre-existed in production under a different shape than the one
    first written here, and the mocks happily returned rows for a filter on a
    column that does not exist — so the column name has to be asserted
    explicitly or a rename slips through into prod (it did once).
    """

    def test_resolver_filters_on_external_name(self):
        dao = _team_dao(direct=None, alias_rows=[], by_id=None)
        dao.resolve_team_by_name("Anything")

        alias_table = dao.client.table("team_aliases")
        filters = [c.args[0] for c in alias_table.ilike.call_args_list if c.args]
        assert "external_name" in filters
        assert "alias" not in filters

    def test_opponent_lookup_filters_on_external_name(self):
        dao, _ = _tournament_dao(exact=None, alias_team_id=None)
        dao.get_or_create_opponent_team("Anything", age_group_id=2)

        alias_table = dao.client.table("team_aliases")
        filters = [c.args[0] for c in alias_table.ilike.call_args_list if c.args]
        assert "external_name" in filters
        assert "alias" not in filters


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


@pytest.mark.unit
class TestAliasConflict:
    """SB-1652: the create-alias guard must not block the alias the fix needs.

    It asked 'does this string resolve anywhere?', so an Academy-scoped
    'Bayside FC' was refused because the Homegrown team owns that name.
    """

    ACADEMY, HOMEGROWN = 2, 1
    HG_BAYSIDE = {"id": 11, "name": "Bayside FC", "city": None, "club_id": 11}
    AC_BAYSIDE = {"id": 175, "name": "Bayside FC Academy", "city": None, "club_id": 11}

    def _dao(self, direct=None, alias_rows=None, leagues=None, by_id=None):
        dao = _team_dao(direct=direct, alias_rows=alias_rows, by_id=by_id or direct)
        dao._team_league_id = MagicMock(side_effect=lambda tid: (leagues or {}).get(tid))
        return dao

    def test_a_scoped_alias_does_not_collide_with_another_leagues_exact_name(self):
        dao = self._dao(direct=self.HG_BAYSIDE, leagues={11: self.HOMEGROWN})
        assert dao.alias_conflict("Bayside FC", 175, league_id=self.ACADEMY) is None

    def test_a_scoped_alias_collides_with_an_exact_name_in_its_own_league(self):
        dao = self._dao(direct=self.HG_BAYSIDE, leagues={11: self.ACADEMY})
        assert dao.alias_conflict("Bayside FC", 175, league_id=self.ACADEMY)["id"] == 11

    def test_a_scoped_alias_collides_with_another_alias_in_its_league(self):
        dao = self._dao(
            direct=None,
            alias_rows=[{"team_id": 11, "league_id": self.ACADEMY, "source": "kitman"}],
            by_id=self.HG_BAYSIDE,
        )
        assert dao.alias_conflict("Bayside FC", 175, league_id=self.ACADEMY)["id"] == 11

    def test_a_league_agnostic_alias_elsewhere_does_not_block_a_scoped_one(self):
        # 'Intercontinental Football Academy of New England' -> IFA (Homegrown)
        # is NULL-league; an Academy-scoped alias to IFA Academy must be allowed.
        dao = self._dao(
            direct=None,
            alias_rows=[{"team_id": 19, "league_id": None, "source": "mlssoccer.com"}],
            leagues={19: self.HOMEGROWN},
        )
        assert dao.alias_conflict(LONG_NAME, 123, league_id=self.ACADEMY) is None

    def test_without_a_league_any_other_team_is_a_conflict_as_before(self):
        dao = self._dao(direct=self.HG_BAYSIDE)
        assert dao.alias_conflict("Bayside FC", 175)["id"] == 11

    def test_pointing_at_the_team_that_already_owns_it_is_not_a_conflict(self):
        dao = self._dao(direct=self.HG_BAYSIDE, leagues={11: self.ACADEMY})
        assert dao.alias_conflict("Bayside FC", 11, league_id=self.ACADEMY) is None

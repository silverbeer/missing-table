"""Divisions the agent would otherwise never discover (SB-839).

The scraper's targets come from matches MT already has, so a division holding
none of them is invisible:

    no matches -> not advertised -> never scraped -> no matches

That closed loop is why the 2026-2027 season had exactly one target on
2026-08-26 — `Unknown | Unknown`, a friendly with no division — even with all
the season's reference data in place.
"""

from unittest.mock import MagicMock

import pytest

from dao.match_dao import MatchDAO

HOMEGROWN = {"id": 1, "name": "Homegrown", "is_active": True, "is_test": False}
FLEX = {"id": 290, "name": "Flex", "is_active": True, "is_test": False}
RETIRED = {"id": 34, "name": "Kick Futsal", "is_active": False, "is_test": False}
TEST_LEAGUE = {"id": 90, "name": "TSC League 1", "is_active": True, "is_test": True}


def _dao(divisions, seeded_division_ids, season_id=184):
    dao = object.__new__(MatchDAO)
    dao.connection_holder = MagicMock()
    client = MagicMock()

    def table(name):
        t = MagicMock()
        for m in ("select", "eq", "neq", "limit", "range"):
            getattr(t, m).return_value = t
        if name == "seasons":
            t.execute.return_value = MagicMock(data=[{"id": season_id}] if season_id else [])
        elif name == "divisions":
            t.execute.return_value = MagicMock(data=divisions)
        else:  # matches
            t.execute.return_value = MagicMock(data=[{"division_id": d} for d in seeded_division_ids])
        return t

    client.table.side_effect = table
    dao.client = client
    return dao


def _div(id, name, league):
    return {"id": id, "name": name, "leagues": league}


@pytest.mark.unit
class TestBootstrapDivisions:
    def test_a_division_with_no_matches_is_offered(self):
        dao = _dao([_div(276, "Turnpike", FLEX)], seeded_division_ids=[])
        out = dao.get_bootstrap_divisions("2026-2027")
        assert out == [{"division_id": 276, "division": "Turnpike", "league": "Flex"}]

    def test_a_division_that_already_has_matches_is_not(self):
        # It shows up in `targets` with real counts; offering it here too would
        # tell the agent to bootstrap something it is already syncing.
        dao = _dao([_div(1, "Northeast", HOMEGROWN)], seeded_division_ids=[1])
        assert dao.get_bootstrap_divisions("2026-2027") == []

    def test_seeding_is_scoped_to_the_season(self):
        # A division full of last season's matches is still unseeded for this
        # one — which is exactly the state every division was in for 2026-2027.
        dao = _dao([_div(1, "Northeast", HOMEGROWN)], seeded_division_ids=[])
        assert len(dao.get_bootstrap_divisions("2026-2027")) == 1

    def test_a_retired_league_is_never_offered(self):
        # Inactive means retired, not unseeded. Handing Kick Futsal to the
        # scraper as work to do would be a standing false positive.
        dao = _dao([_div(36, "Bracket A", RETIRED)], seeded_division_ids=[])
        assert dao.get_bootstrap_divisions("2026-2027") == []

    def test_a_test_league_is_hidden_from_real_viewers(self):
        dao = _dao([_div(87, "TSC Top Division", TEST_LEAGUE)], seeded_division_ids=[])
        assert dao.get_bootstrap_divisions("2026-2027", include_test=False) == []

    def test_a_test_league_is_visible_to_test_viewers(self):
        dao = _dao([_div(87, "TSC Top Division", TEST_LEAGUE)], seeded_division_ids=[])
        out = dao.get_bootstrap_divisions("2026-2027", include_test=True)
        assert [x["division"] for x in out] == ["TSC Top Division"]

    def test_results_are_ordered_by_league_then_division(self):
        dao = _dao(
            [_div(276, "Turnpike", FLEX), _div(264, "Empire", FLEX), _div(1, "Northeast", HOMEGROWN)],
            seeded_division_ids=[],
        )
        out = dao.get_bootstrap_divisions("2026-2027")
        assert [(x["league"], x["division"]) for x in out] == [
            ("Flex", "Empire"),
            ("Flex", "Turnpike"),
            ("Homegrown", "Northeast"),
        ]

    def test_an_unknown_season_is_empty_not_everything(self):
        # Returning every division for a typo'd season name would send the
        # agent to scrape the whole world.
        dao = _dao([_div(276, "Turnpike", FLEX)], seeded_division_ids=[], season_id=None)
        assert dao.get_bootstrap_divisions("1999-2000") == []

    def test_a_database_error_is_empty_rather_than_fatal(self):
        # This runs inside the agent's status endpoint. Losing bootstrap hints
        # degrades discovery; raising would take down the whole scrape plan.
        dao = _dao([_div(276, "Turnpike", FLEX)], seeded_division_ids=[])
        dao.client.table = MagicMock(side_effect=[MagicMock(), RuntimeError("db down")])
        assert dao.get_bootstrap_divisions("2026-2027") == []

    def test_no_age_groups_are_invented(self):
        # MT cannot know which age groups a brand-new division serves, and
        # guessing sends the scraper after combinations that do not exist:
        # U13/U14 have no Flex, U13-U15 have no Pathway.
        dao = _dao([_div(276, "Turnpike", FLEX)], seeded_division_ids=[])
        assert "age_group" not in dao.get_bootstrap_divisions("2026-2027")[0]

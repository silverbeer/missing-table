"""Which leagues are worth offering in a filter (SB-851).

`/api/leagues` returns every league, so the League filter offered **Kick
Futsal** on every season and age group — inactive, and holding 24 matches that
are all U14 2025-2026. Picking it anywhere else produced an empty table, and
its four IFA futsal teams showed up in the My Club team picker for 2026-2027.

The rule is: **active, or the selected season has matches in it.** Neither half
works alone, and both failure modes are covered below.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app import leagues_worth_offering
from dao.match_dao import MatchDAO

# Mirrors prod: only Kick Futsal is inactive, and Flex has no teams by
# teams.league_id because its participants are Homegrown teams.
HOMEGROWN = {"id": 1, "name": "Homegrown", "is_active": True}
ACADEMY = {"id": 2, "name": "Academy", "is_active": True}
KICK_FUTSAL = {"id": 34, "name": "Kick Futsal", "is_active": False}
TSC = {"id": 90, "name": "TSC League 1", "is_active": True}
FLEX = {"id": 290, "name": "Flex", "is_active": True}

ALL_LEAGUES = [HOMEGROWN, ACADEMY, KICK_FUTSAL, TSC, FLEX]


# The real rule, imported rather than reproduced: a copied rule passes while
# the code it mirrors is broken.
offer = leagues_worth_offering


def names(rows: list[dict]) -> set[str]:
    return {r["name"] for r in rows}


@pytest.mark.unit
class TestTheRule:
    def test_an_inactive_league_with_no_matches_is_hidden(self):
        # 2026-2027: Homegrown and Flex have matches; Kick Futsal does not.
        offered = offer(ALL_LEAGUES, {1: 190, 290: 68})
        assert "Kick Futsal" not in names(offered)

    def test_an_inactive_league_is_shown_in_a_season_it_played(self):
        # 2025-2026: 24 Kick Futsal matches. Hiding it would make real history
        # unreachable through the filter.
        offered = offer(ALL_LEAGUES, {1: 1265, 2: 176, 34: 24, 90: 1})
        assert "Kick Futsal" in names(offered)

    def test_an_active_league_with_no_matches_yet_is_still_shown(self):
        """The pre-season case, and why presence alone is not the rule.

        Only U15 is loaded for 2026-2027. Presence alone would drop Academy —
        and with it three legitimate IFA teams — from the team picker.
        """
        offered = offer(ALL_LEAGUES, {1: 190})
        assert "Academy" in names(offered)

    def test_flex_survives_despite_having_no_teams_of_its_own(self):
        """Flex has 0 teams by teams.league_id — its players are Homegrown teams.

        Any rule keyed on that column would hide the newest competition in the
        product.
        """
        offered = offer(ALL_LEAGUES, {290: 68})
        assert "Flex" in names(offered)

    def test_the_count_comes_back_with_each_row(self):
        offered = offer(ALL_LEAGUES, {1: 190, 290: 68})
        by_name = {r["name"]: r["matches_this_season"] for r in offered}
        assert by_name["Homegrown"] == 190
        assert by_name["Flex"] == 68
        assert by_name["Academy"] == 0

    def test_a_season_with_nothing_loaded_still_offers_active_leagues(self):
        offered = offer(ALL_LEAGUES, {})
        assert names(offered) == {"Homegrown", "Academy", "TSC League 1", "Flex"}

    def test_only_the_inactive_league_can_ever_be_dropped(self):
        for counts in ({}, {1: 5}, {34: 5}):
            offered = offer(ALL_LEAGUES, counts)
            assert names(ALL_LEAGUES) - names(offered) <= {"Kick Futsal"}


# ── MatchDAO.get_leagues_present ─────────────────────────────────────


@pytest.fixture(autouse=True)
def no_cached_counts():
    """Clear this method's cache keys around each test.

    Redis is reachable from the test environment, and get_leagues_present is
    @dao_cache'd — so without this a run picks up whatever a previous run
    computed for the same (season, include_test) key and the method under test
    never executes. This is how the JSON-string-keys bug was found; it should
    not be how the next one is hidden.
    """
    from dao.base_dao import clear_cache

    clear_cache("mt:dao:matches:leagues_present:*")
    yield
    clear_cache("mt:dao:matches:leagues_present:*")


def _dao(match_rows, division_rows):
    dao = object.__new__(MatchDAO)
    client = MagicMock()

    matches_chain = MagicMock()
    matches_chain.select.return_value = matches_chain
    matches_chain.eq.return_value = matches_chain
    matches_chain.execute.return_value = MagicMock(data=match_rows)

    divisions_chain = MagicMock()
    divisions_chain.select.return_value = divisions_chain
    divisions_chain.execute.return_value = MagicMock(data=division_rows)

    client.table.side_effect = lambda name: divisions_chain if name == "divisions" else matches_chain
    dao.client = client
    dao._matches = matches_chain
    return dao


DIVISIONS = [
    {"id": 1, "league_id": 1},  # Northeast, Homegrown
    {"id": 7, "league_id": 2},  # New England, Academy
    {"id": 60, "league_id": 34},  # Bracket A, Kick Futsal
    {"id": 309, "league_id": 290},  # Turnpike, Flex
]


@pytest.mark.unit
class TestLeaguesPresent:
    def test_it_counts_matches_per_league_through_divisions(self):
        dao = _dao([{"division_id": 1}, {"division_id": 1}, {"division_id": 309}], DIVISIONS)
        assert dao.get_leagues_present(season_id=184) == [
            {"league_id": 1, "matches": 2},
            {"league_id": 290, "matches": 1},
        ]

    def test_it_returns_a_list_so_the_cache_cannot_stringify_the_keys(self):
        """JSON has no integer keys.

        A dict[int, int] survives the first call and comes back from Redis with
        string keys on every one after, so `counts[league_id]` misses and every
        league reads as zero matches — which for this filter means a dormant
        league never returns to the season it played.
        """
        dao = _dao([{"division_id": 1}], DIVISIONS)
        rows = dao.get_leagues_present(season_id=184)
        assert isinstance(rows, list)
        assert all(isinstance(r["league_id"], int) for r in rows)

    def test_a_match_with_no_division_is_not_counted(self):
        # Friendlies and tournament fixtures carry none.
        dao = _dao([{"division_id": None}, {"division_id": 1}], DIVISIONS)
        assert dao.get_leagues_present(season_id=184) == [{"league_id": 1, "matches": 1}]

    def test_an_unknown_division_is_not_counted(self):
        dao = _dao([{"division_id": 9999}], DIVISIONS)
        assert dao.get_leagues_present(season_id=184) == []

    def test_no_matches_is_an_empty_list_not_an_error(self):
        dao = _dao([], DIVISIONS)
        assert dao.get_leagues_present(season_id=184) == []

    def test_the_test_partition_is_excluded_for_ordinary_viewers(self):
        dao = _dao([{"division_id": 1}], DIVISIONS)
        dao.get_leagues_present(season_id=184, include_test=False)
        assert ("is_test", False) in {c.args for c in dao._matches.eq.call_args_list}

    def test_admins_are_not_filtered(self):
        dao = _dao([{"division_id": 1}], DIVISIONS)
        dao.get_leagues_present(season_id=184, include_test=True)
        assert ("is_test", False) not in {c.args for c in dao._matches.eq.call_args_list}

    def test_a_database_error_degrades_to_empty(self):
        """Empty means "offer the active leagues" — never an error page over a filter."""
        dao = _dao([{"division_id": 1}], DIVISIONS)
        dao._matches.execute.side_effect = RuntimeError("boom")
        assert dao.get_leagues_present(season_id=184) == []

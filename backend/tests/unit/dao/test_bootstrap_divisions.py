"""Divisions the agent would otherwise never discover (SB-839).

The scraper's targets come from matches MT already has, so a division holding
none of them is invisible:

    no matches -> not advertised -> never scraped -> no matches

That closed loop is why the 2026-2027 season had exactly one target on
2026-08-26 — `Unknown | Unknown`, a friendly with no division — even with all
the season's reference data in place.

Since SB-1080 the rules — retired and test leagues, season scoping, cancelled
matches, ordering — are applied in the database by agent_bootstrap_divisions and
tested against Postgres in supabase/tests/agent_bootstrap_divisions_test.sql.
These tests cover what stays in the DAO: resolving the season, asking the right
question, the shape handed to the agent, and failing soft.
"""

from unittest.mock import MagicMock

import pytest

from dao.match_dao import MatchDAO

TURNPIKE = {"division_id": 276, "division": "Turnpike", "league": "Flex"}
EMPIRE = {"division_id": 264, "division": "Empire", "league": "Flex"}


def _dao(rows=(), season_id=184, rpc_error=None):
    dao = object.__new__(MatchDAO)
    dao.connection_holder = MagicMock()
    client = MagicMock()

    seasons = MagicMock()
    for method in ("select", "eq", "limit"):
        getattr(seasons, method).return_value = seasons
    seasons.execute.return_value = MagicMock(data=[{"id": season_id}] if season_id else [])
    client.table.return_value = seasons

    call = MagicMock()
    if rpc_error:
        call.execute.side_effect = rpc_error
    else:
        call.execute.return_value = MagicMock(data=list(rows))
    client.rpc.return_value = call

    dao.client = client
    return dao


@pytest.mark.unit
class TestBootstrapDivisions:
    def test_asks_the_database_about_this_season(self):
        dao = _dao([TURNPIKE])

        dao.get_bootstrap_divisions("2026-2027")

        dao.client.rpc.assert_called_once_with(
            "agent_bootstrap_divisions", {"p_season_id": 184, "p_include_test": False}
        )

    def test_test_viewers_ask_for_test_leagues(self):
        dao = _dao([TURNPIKE])

        dao.get_bootstrap_divisions("2026-2027", include_test=True)

        assert dao.client.rpc.call_args.args[1]["p_include_test"] is True

    def test_rows_reach_the_agent_in_the_order_the_database_returned(self):
        # Ordering is the function's job; re-sorting here could only disagree.
        dao = _dao([EMPIRE, TURNPIKE])

        assert dao.get_bootstrap_divisions("2026-2027") == [EMPIRE, TURNPIKE]

    def test_no_age_groups_are_invented(self):
        # MT cannot know which age groups a brand-new division serves, and
        # guessing sends the scraper after combinations that do not exist:
        # U13/U14 have no Flex, U13-U15 have no Pathway.
        dao = _dao([TURNPIKE])

        [row] = dao.get_bootstrap_divisions("2026-2027")

        assert set(row) == {"division_id", "division", "league"}

    def test_a_season_with_every_division_seeded_is_empty(self):
        assert _dao([]).get_bootstrap_divisions("2026-2027") == []

    def test_an_unknown_season_is_empty_not_everything(self):
        # For a season id with no matches the function offers every active
        # division; a typo'd season name must not send the agent to scrape the
        # whole world, so the DAO stops before asking.
        dao = _dao([TURNPIKE], season_id=None)

        assert dao.get_bootstrap_divisions("1999-2000") == []
        dao.client.rpc.assert_not_called()

    def test_a_database_error_is_empty_rather_than_fatal(self):
        # This runs inside the agent's status endpoint. Losing bootstrap hints
        # degrades discovery; raising would take down the whole scrape plan.
        dao = _dao(rpc_error=RuntimeError("db down"))

        assert dao.get_bootstrap_divisions("2026-2027") == []

    def test_a_missing_function_is_empty_rather_than_fatal(self):
        # The code deploying before the migration looks like this.
        dao = _dao(rpc_error=RuntimeError("Could not find the function public.agent_bootstrap_divisions"))

        assert dao.get_bootstrap_divisions("2026-2027") == []

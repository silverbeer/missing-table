"""
Unit tests for QoP Rankings DAO and API endpoints.

Tests:
- upsert_snapshot: valid snapshot returns inserted count
- get_latest_with_delta: no data returns has_data=False
- rank delta: prior rank 5, current rank 3 → rank_change = 2 (moved up)
- new entry with no prior week → rank_change = None
"""

from unittest.mock import MagicMock, Mock, patch

import pytest


# ─── DAO helpers ───────────────────────────────────────────────────────────────

def _make_client(table_responses: dict):
    """
    Build a mock Supabase client where table(name) returns a pre-configured
    mock chain. table_responses maps table name → list of row dicts returned
    by .execute().data for that table.

    For tables that need chained filtering (eq, order, ilike, limit), the mock
    always returns the preconfigured .execute() result regardless of filter
    arguments.
    """
    client = MagicMock()

    def table_side_effect(name):
        rows = table_responses.get(name, [])
        mock_response = Mock()
        mock_response.data = rows

        chain = MagicMock()
        # Any attribute access on the chain (select, eq, order, ilike, limit,
        # upsert, desc) returns the chain itself so calls can be chained freely.
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.ilike.return_value = chain
        chain.limit.return_value = chain
        chain.upsert.return_value = chain
        chain.execute.return_value = mock_response
        return chain

    client.table.side_effect = table_side_effect
    return client


# ─── upsert_snapshot ───────────────────────────────────────────────────────────

@pytest.mark.unit
class TestUpsertSnapshot:

    def test_upsert_returns_inserted_count(self):
        """POST with valid snapshot data returns the count of rows upserted."""
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        divisions = [{"id": 1, "name": "Northeast"}]
        age_groups = [{"id": 2, "name": "U14"}]
        teams = []  # no team match — team_id should be None
        upserted_rows = [
            {"id": 10, "rank": 1},
            {"id": 11, "rank": 2},
        ]

        client = _make_client({
            "divisions": divisions,
            "age_groups": age_groups,
            "teams": teams,
            "qop_rankings": upserted_rows,
        })

        snapshot = {
            "week_of": "2026-04-14",
            "division": "Northeast",
            "age_group": "U14",
            "scraped_at": "2026-04-16T00:00:00Z",
            "rankings": [
                {"rank": 1, "team_name": "Team A", "matches_played": 10, "att_score": 80.0, "def_score": 75.0, "qop_score": 78.0},
                {"rank": 2, "team_name": "Team B", "matches_played": 10, "att_score": 78.0, "def_score": 70.0, "qop_score": 74.0},
            ],
        }

        count = QoPRankingsDAO.upsert_snapshot(client, snapshot)
        assert count == 2

    def test_upsert_raises_on_unknown_division(self):
        """upsert_snapshot raises ValueError when division is not found."""
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        client = _make_client({
            "divisions": [{"id": 1, "name": "Northeast"}],
            "age_groups": [{"id": 2, "name": "U14"}],
        })

        snapshot = {
            "week_of": "2026-04-14",
            "division": "Unknown Division",
            "age_group": "U14",
            "rankings": [],
        }

        with pytest.raises(ValueError, match="Division not found"):
            QoPRankingsDAO.upsert_snapshot(client, snapshot)

    def test_upsert_empty_rankings_returns_zero(self):
        """upsert_snapshot with empty rankings list returns 0 without hitting qop_rankings table."""
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        client = _make_client({
            "divisions": [{"id": 1, "name": "Northeast"}],
            "age_groups": [{"id": 2, "name": "U14"}],
            "qop_rankings": [],
        })

        snapshot = {
            "week_of": "2026-04-14",
            "division": "Northeast",
            "age_group": "U14",
            "rankings": [],
        }

        count = QoPRankingsDAO.upsert_snapshot(client, snapshot)
        assert count == 0


# ─── get_latest_with_delta ─────────────────────────────────────────────────────

@pytest.mark.unit
class TestGetLatestWithDelta:

    def _make_ordered_client(self, week_rows, current_rows, prior_rows=None):
        """
        Build a client where qop_rankings returns different data depending on
        whether the query is for the distinct-weeks fetch, current week, or
        prior week.  We detect context via call count on the table mock.
        """
        client = MagicMock()
        call_count = {"n": 0}

        def table_side_effect(name):
            if name != "qop_rankings":
                mock_resp = Mock()
                mock_resp.data = []
                chain = MagicMock()
                chain.select.return_value = chain
                chain.eq.return_value = chain
                chain.order.return_value = chain
                chain.execute.return_value = mock_resp
                return chain

            call_count["n"] += 1
            call_num = call_count["n"]

            if call_num == 1:
                rows = week_rows
            elif call_num == 2:
                rows = current_rows
            else:
                rows = prior_rows or []

            mock_resp = Mock()
            mock_resp.data = rows

            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.order.return_value = chain
            chain.limit.return_value = chain
            chain.execute.return_value = mock_resp
            return chain

        client.table.side_effect = table_side_effect
        return client

    def test_no_data_returns_has_data_false(self):
        """GET with no rows for a division/age_group returns has_data=False and empty list."""
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        client = self._make_ordered_client(week_rows=[], current_rows=[])

        result = QoPRankingsDAO.get_latest_with_delta(client, division_id=1, age_group_id=2)

        assert result["has_data"] is False
        assert result["week_of"] is None
        assert result["prior_week_of"] is None
        assert result["rankings"] == []

    def test_rank_delta_computed_correctly(self):
        """
        Prior rank 5, current rank 3 → rank_change = 2 (moved up).
        Positive rank_change means the team improved its position.
        """
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        week_rows = [
            {"week_of": "2026-04-14"},
            {"week_of": "2026-04-14"},
            {"week_of": "2026-04-07"},
            {"week_of": "2026-04-07"},
        ]
        current_rows = [
            {
                "rank": 3,
                "team_name": "Team Alpha",
                "team_id": 42,
                "matches_played": 16,
                "att_score": 89.6,
                "def_score": 83.1,
                "qop_score": 87.6,
            }
        ]
        prior_rows = [
            {"rank": 5, "team_name": "Team Alpha"},
        ]

        client = self._make_ordered_client(week_rows, current_rows, prior_rows)

        result = QoPRankingsDAO.get_latest_with_delta(client, division_id=1, age_group_id=2)

        assert result["has_data"] is True
        assert result["week_of"] == "2026-04-14"
        assert result["prior_week_of"] == "2026-04-07"
        assert len(result["rankings"]) == 1

        entry = result["rankings"][0]
        assert entry["rank"] == 3
        assert entry["rank_change"] == 2  # 5 - 3 = 2 (moved up)

    def test_new_entry_no_prior_rank_change_is_none(self):
        """New entry with no prior week data → rank_change = None."""
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        # Only one week available → no prior week
        week_rows = [
            {"week_of": "2026-04-14"},
        ]
        current_rows = [
            {
                "rank": 1,
                "team_name": "Brand New Team",
                "team_id": None,
                "matches_played": 5,
                "att_score": 70.0,
                "def_score": 65.0,
                "qop_score": 68.0,
            }
        ]

        client = self._make_ordered_client(week_rows, current_rows, prior_rows=[])

        result = QoPRankingsDAO.get_latest_with_delta(client, division_id=1, age_group_id=2)

        assert result["has_data"] is True
        assert result["prior_week_of"] is None
        assert result["rankings"][0]["rank_change"] is None

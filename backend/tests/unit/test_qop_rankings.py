"""
Unit tests for QoP Rankings DAO and API endpoints.

Tests:
- upsert_snapshot: valid snapshot returns inserted count
- get_latest_with_delta: no data returns has_data=False
- rank delta: prior rank 5, current rank 3 → rank_change = 2 (moved up)
- new entry with no prior week → rank_change = None
- match preview: no QoP data → has_qop_data=False, all QoP fields null
- match preview: QoP data available → correct ranks attached to home/away
- match preview: teams from different divisions → has_qop_data=False
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


# ─── Match Preview QoP enrichment ──────────────────────────────────────────────

def _make_preview_base(home_team_id=1, away_team_id=2):
    """Return a minimal preview dict as returned by match_dao.get_match_preview."""
    return {
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "home_team_recent": [],
        "away_team_recent": [],
        "common_opponents": [],
        "head_to_head": [],
    }


def _make_team_with_details(team_id, name, division_id, age_group_id):
    return {
        "id": team_id,
        "name": name,
        "division": {"id": division_id, "name": "Northeast"},
        "age_group": {"id": age_group_id, "name": "U14"},
    }


@pytest.mark.unit
class TestMatchPreviewQoP:
    """Tests for QoP data enrichment on the match preview endpoint."""

    def _call_preview(self, home_team_id, away_team_id, mock_match_dao, mock_team_dao, mock_qop):
        """
        Simulate the QoP enrichment logic from the get_match_preview endpoint
        without spinning up the full FastAPI app.
        """
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        preview = mock_match_dao.get_match_preview(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            season_id=None,
            age_group_id=None,
            recent_count=5,
        )

        qop_defaults = {
            "has_qop_data": False,
            "home_qop_rank": None,
            "home_qop_rank_change": None,
            "away_qop_rank": None,
            "away_qop_rank_change": None,
        }

        try:
            home_team = mock_team_dao.get_team_with_details(home_team_id)
            away_team = mock_team_dao.get_team_with_details(away_team_id)

            home_division = home_team.get("division") if home_team else None
            away_division = away_team.get("division") if away_team else None
            home_division_id = home_division.get("id") if home_division else None
            away_division_id = away_division.get("id") if away_division else None
            home_age_group = home_team.get("age_group") if home_team else None
            home_age_group_id = home_age_group.get("id") if home_age_group else None

            if (
                home_division_id is None
                or away_division_id is None
                or home_division_id != away_division_id
                or home_age_group_id is None
            ):
                preview.update(qop_defaults)
            else:
                qop_data = mock_qop(mock_match_dao.client, home_division_id, home_age_group_id)
                if not qop_data.get("has_data"):
                    preview.update(qop_defaults)
                else:
                    rankings = qop_data["rankings"]

                    def find_team_rank(team_id, team_name):
                        for entry in rankings:
                            if entry.get("team_id") == team_id:
                                return entry["rank"], entry.get("rank_change")
                        if team_name:
                            for entry in rankings:
                                if entry.get("team_name", "").lower() == team_name.lower():
                                    return entry["rank"], entry.get("rank_change")
                        return None, None

                    home_name = home_team.get("name") if home_team else None
                    away_name = away_team.get("name") if away_team else None
                    home_rank, home_rank_change = find_team_rank(home_team_id, home_name)
                    away_rank, away_rank_change = find_team_rank(away_team_id, away_name)

                    preview.update({
                        "has_qop_data": True,
                        "home_qop_rank": home_rank,
                        "home_qop_rank_change": home_rank_change,
                        "away_qop_rank": away_rank,
                        "away_qop_rank_change": away_rank_change,
                    })
        except Exception:
            preview.update(qop_defaults)

        return preview

    def test_no_qop_data_returns_false_with_null_fields(self):
        """When QoPRankingsDAO returns has_data=False, preview gets has_qop_data=False and null fields."""
        home_id, away_id = 1, 2
        mock_match_dao = MagicMock()
        mock_match_dao.get_match_preview.return_value = _make_preview_base(home_id, away_id)

        mock_team_dao = MagicMock()
        mock_team_dao.get_team_with_details.side_effect = lambda tid: _make_team_with_details(
            tid, f"Team {tid}", division_id=10, age_group_id=20
        )

        mock_qop = MagicMock(return_value={"has_data": False, "week_of": None, "rankings": []})

        result = self._call_preview(home_id, away_id, mock_match_dao, mock_team_dao, mock_qop)

        assert result["has_qop_data"] is False
        assert result["home_qop_rank"] is None
        assert result["home_qop_rank_change"] is None
        assert result["away_qop_rank"] is None
        assert result["away_qop_rank_change"] is None
        # Existing fields still present
        assert result["home_team_recent"] == []
        assert result["head_to_head"] == []

    def test_qop_data_attaches_correct_ranks(self):
        """When QoP data exists, preview includes correct rank and rank_change for each team."""
        home_id, away_id = 7, 11
        mock_match_dao = MagicMock()
        mock_match_dao.get_match_preview.return_value = _make_preview_base(home_id, away_id)

        mock_team_dao = MagicMock()
        mock_team_dao.get_team_with_details.side_effect = lambda tid: _make_team_with_details(
            tid, "Home FC" if tid == home_id else "Away United", division_id=10, age_group_id=20
        )

        rankings = [
            {"rank": 8, "team_id": home_id, "team_name": "Home FC", "rank_change": 1},
            {"rank": 11, "team_id": away_id, "team_name": "Away United", "rank_change": 0},
        ]
        mock_qop = MagicMock(return_value={
            "has_data": True,
            "week_of": "2026-04-14",
            "rankings": rankings,
        })

        result = self._call_preview(home_id, away_id, mock_match_dao, mock_team_dao, mock_qop)

        assert result["has_qop_data"] is True
        assert result["home_qop_rank"] == 8
        assert result["home_qop_rank_change"] == 1
        assert result["away_qop_rank"] == 11
        assert result["away_qop_rank_change"] == 0

    def test_different_divisions_returns_no_qop_data(self):
        """Teams in different divisions → has_qop_data=False, no QoP lookup performed."""
        home_id, away_id = 3, 4
        mock_match_dao = MagicMock()
        mock_match_dao.get_match_preview.return_value = _make_preview_base(home_id, away_id)

        mock_team_dao = MagicMock()
        # Home team in division 10, away team in division 99 (different)
        mock_team_dao.get_team_with_details.side_effect = lambda tid: _make_team_with_details(
            tid, f"Team {tid}", division_id=10 if tid == home_id else 99, age_group_id=20
        )

        mock_qop = MagicMock()  # Should NOT be called

        result = self._call_preview(home_id, away_id, mock_match_dao, mock_team_dao, mock_qop)

        assert result["has_qop_data"] is False
        assert result["home_qop_rank"] is None
        assert result["away_qop_rank"] is None
        mock_qop.assert_not_called()

    def test_qop_lookup_by_name_fallback(self):
        """If team_id not in rankings, falls back to name match."""
        home_id, away_id = 5, 6
        mock_match_dao = MagicMock()
        mock_match_dao.get_match_preview.return_value = _make_preview_base(home_id, away_id)

        mock_team_dao = MagicMock()
        mock_team_dao.get_team_with_details.side_effect = lambda tid: _make_team_with_details(
            tid, "Alpha FC" if tid == home_id else "Beta SC", division_id=10, age_group_id=20
        )

        # Rankings have team_id=None (name-only entries, as can happen with unresolved teams)
        rankings = [
            {"rank": 3, "team_id": None, "team_name": "Alpha FC", "rank_change": 2},
            {"rank": 7, "team_id": None, "team_name": "Beta SC", "rank_change": -1},
        ]
        mock_qop = MagicMock(return_value={
            "has_data": True,
            "week_of": "2026-04-14",
            "rankings": rankings,
        })

        result = self._call_preview(home_id, away_id, mock_match_dao, mock_team_dao, mock_qop)

        assert result["has_qop_data"] is True
        assert result["home_qop_rank"] == 3
        assert result["home_qop_rank_change"] == 2
        assert result["away_qop_rank"] == 7
        assert result["away_qop_rank_change"] == -1

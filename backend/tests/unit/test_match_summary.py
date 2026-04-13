"""Unit tests for the agent match-summary endpoint."""

from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
class TestGetMatchSummary:
    """Tests for MatchDAO.get_match_summary()."""

    def _make_dao(self):
        from dao.match_dao import MatchDAO

        # Use object.__new__ to create the instance without calling __init__,
        # avoiding patch.object on the inherited BaseDAO.__init__ which can
        # interact with class state under parallel test execution (pytest-xdist).
        dao = object.__new__(MatchDAO)
        dao.connection_holder = MagicMock()
        dao.client = MagicMock()
        return dao

    def test_returns_empty_for_unknown_season(self):
        dao = self._make_dao()
        # Mock season lookup returning no results
        mock_table = MagicMock()
        dao.client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        result = dao.get_match_summary("9999-00")
        assert result == []

    def test_groups_matches_correctly(self):
        dao = self._make_dao()

        matches_data = [
            {
                "match_date": "2026-03-01",
                "match_status": "completed",
                "home_score": 2,
                "away_score": 1,
                "age_group": {"name": "U14"},
                "division": {"name": "Northeast", "league_id": 1, "leagues": {"name": "Homegrown"}},
            },
            {
                "match_date": "2026-03-15",
                "match_status": "scheduled",
                "home_score": None,
                "away_score": None,
                "age_group": {"name": "U14"},
                "division": {"name": "Northeast", "league_id": 1, "leagues": {"name": "Homegrown"}},
            },
        ]

        def table_side_effect(name):
            mock = MagicMock()
            if name == "seasons":
                mock.select.return_value = mock
                mock.eq.return_value = mock
                mock.limit.return_value = mock
                mock.execute.return_value = MagicMock(data=[{"id": 1}])
            elif name == "matches":
                mock.select.return_value = mock
                mock.eq.return_value = mock
                mock.neq.return_value = mock
                mock.range.return_value = mock
                mock.execute.return_value = MagicMock(data=matches_data)
            return mock

        dao.client.table = table_side_effect

        result = dao.get_match_summary("2025-26")
        assert len(result) == 1
        group = result[0]
        assert group["age_group"] == "U14"
        assert group["league"] == "Homegrown"
        assert group["division"] == "Northeast"
        assert group["total"] == 2
        assert group["by_status"]["completed"] == 1
        assert group["by_status"]["scheduled"] == 1
        assert group["last_played_date"] == "2026-03-01"

    def test_needs_score_counts_past_unscored(self):
        dao = self._make_dao()

        matches_data = [
            {
                "match_date": "2026-03-01",
                "match_status": "scheduled",
                "home_score": None,
                "away_score": None,
                "age_group": {"name": "U14"},
                "division": {"name": "Northeast", "league_id": 1, "leagues": {"name": "Homegrown"}},
            },
            {
                "match_date": "2026-03-01",
                "match_status": "tbd",
                "home_score": None,
                "away_score": None,
                "age_group": {"name": "U14"},
                "division": {"name": "Northeast", "league_id": 1, "leagues": {"name": "Homegrown"}},
            },
            {
                "match_date": "2099-12-31",
                "match_status": "scheduled",
                "home_score": None,
                "away_score": None,
                "age_group": {"name": "U14"},
                "division": {"name": "Northeast", "league_id": 1, "leagues": {"name": "Homegrown"}},
            },
        ]

        def table_side_effect(name):
            mock = MagicMock()
            if name == "seasons":
                mock.select.return_value = mock
                mock.eq.return_value = mock
                mock.limit.return_value = mock
                mock.execute.return_value = MagicMock(data=[{"id": 1}])
            elif name == "matches":
                mock.select.return_value = mock
                mock.eq.return_value = mock
                mock.neq.return_value = mock
                mock.range.return_value = mock
                mock.execute.return_value = MagicMock(data=matches_data)
            return mock

        dao.client.table = table_side_effect

        result = dao.get_match_summary("2025-26")
        assert result[0]["needs_score"] == 2  # Only past matches count

    def test_paginates_beyond_1000_rows(self):
        """Regression test: query must paginate past Supabase's 1000-row default limit."""
        dao = self._make_dao()

        # Simulate two pages: first returns 1000 rows (all U14), second returns 2 rows (U16)
        page1 = [
            {
                "match_date": "2026-03-01",
                "match_status": "completed",
                "home_score": 1,
                "away_score": 0,
                "scheduled_kickoff": None,
                "age_group": {"name": "U14"},
                "division": {"name": "Northeast", "league_id": 1, "leagues": {"name": "Homegrown"}},
            }
        ] * 1000
        page2 = [
            {
                "match_date": "2026-04-11",
                "match_status": "scheduled",
                "home_score": None,
                "away_score": None,
                "scheduled_kickoff": None,
                "age_group": {"name": "U16"},
                "division": {"name": "Northeast", "league_id": 1, "leagues": {"name": "Homegrown"}},
            },
            {
                "match_date": "2026-04-12",
                "match_status": "scheduled",
                "home_score": None,
                "away_score": None,
                "scheduled_kickoff": None,
                "age_group": {"name": "U16"},
                "division": {"name": "Northeast", "league_id": 1, "leagues": {"name": "Homegrown"}},
            },
        ]

        call_count = 0

        def table_side_effect(name):
            nonlocal call_count
            mock = MagicMock()
            if name == "seasons":
                mock.select.return_value = mock
                mock.eq.return_value = mock
                mock.limit.return_value = mock
                mock.execute.return_value = MagicMock(data=[{"id": 1}])
            elif name == "matches":
                mock.select.return_value = mock
                mock.eq.return_value = mock
                mock.neq.return_value = mock
                mock.range.return_value = mock

                def execute_side_effect():
                    nonlocal call_count
                    call_count += 1
                    return MagicMock(data=page1 if call_count == 1 else page2)

                mock.execute.side_effect = execute_side_effect
            return mock

        dao.client.table = table_side_effect

        result = dao.get_match_summary("2025-2026")

        assert call_count == 2, "Expected exactly two paginated fetches"
        groups = {r["age_group"]: r for r in result}
        assert "U14" in groups
        assert "U16" in groups, "U16 matches from page 2 must appear in the summary"
        assert groups["U16"]["total"] == 2
        assert groups["U16"]["needs_score"] == 2  # Both are past unscored matches


@pytest.mark.unit
class TestMatchSummaryEndpoint:
    """Tests for GET /api/agent/match-summary endpoint."""

    def test_returns_summary(self):
        from unittest.mock import patch as mock_patch

        with (
            mock_patch("app.match_dao") as mock_dao,
            mock_patch("app.require_match_management_permission", return_value=lambda: {"role": "service_account"}),
        ):
            mock_dao.get_match_summary.return_value = [
                {
                    "age_group": "U14",
                    "league": "Homegrown",
                    "division": "Northeast",
                    "total": 92,
                    "by_status": {"played": 45, "scheduled": 40},
                    "needs_score": 5,
                    "date_range": {"earliest": "2026-03-01", "latest": "2026-06-28"},
                    "last_played_date": "2026-03-07",
                }
            ]

            from fastapi.testclient import TestClient

            from app import app

            # Override the auth dependency
            from auth import require_match_management_permission

            app.dependency_overrides[require_match_management_permission] = lambda: {
                "role": "service_account",
                "service_name": "test",
                "permissions": ["manage_matches"],
            }

            try:
                client = TestClient(app)
                response = client.get("/api/agent/match-summary?season=2025-26")
                assert response.status_code == 200
                data = response.json()
                assert data["season"] == "2025-26"
                assert len(data["targets"]) == 1
                assert data["targets"][0]["total"] == 92
            finally:
                app.dependency_overrides.clear()

    def test_missing_season_param(self):
        from fastapi.testclient import TestClient

        from app import app
        from auth import require_match_management_permission

        app.dependency_overrides[require_match_management_permission] = lambda: {
            "role": "service_account",
        }

        try:
            client = TestClient(app)
            response = client.get("/api/agent/match-summary")
            assert response.status_code == 422  # Missing required query param
        finally:
            app.dependency_overrides.clear()

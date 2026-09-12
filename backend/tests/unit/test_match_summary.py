"""Unit tests for the agent match-summary endpoint."""

from datetime import UTC, date, datetime, timedelta
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

    def _rpc_dao(self, rows, season_id=1):
        """A DAO whose season lookup resolves and whose RPC returns `rows`."""
        dao = self._make_dao()

        season = MagicMock()
        season.select.return_value = season
        season.eq.return_value = season
        season.limit.return_value = season
        season.execute.return_value = MagicMock(data=[{"id": season_id}])
        dao.client.table.return_value = season

        rpc = MagicMock()
        rpc.execute.return_value = MagicMock(data=rows)
        dao.client.rpc.return_value = rpc
        return dao

    @staticmethod
    def _row(**kwargs):
        row = {
            "age_group": "U14",
            "league": "Homegrown",
            "division": "Northeast",
            "total": 2,
            "by_status": {"completed": 1, "scheduled": 1},
            "needs_score": 0,
            "needs_kickoff": 0,
            "earliest": "2026-03-01",
            "latest": "2026-03-15",
            "last_played_date": "2026-03-01",
        }
        row.update(kwargs)
        return row

    def test_reshapes_rows_into_the_agent_contract(self):
        """The planner in match-scraper reads these exact keys, so the shape is
        part of the contract, not an implementation detail."""
        dao = self._rpc_dao([self._row()])

        result = dao.get_match_summary("2025-26")

        assert len(result) == 1
        group = result[0]
        assert group["age_group"] == "U14"
        assert group["league"] == "Homegrown"
        assert group["division"] == "Northeast"
        assert group["total"] == 2
        assert group["by_status"] == {"completed": 1, "scheduled": 1}
        assert group["needs_score"] == 0
        assert group["needs_kickoff"] == 0
        assert group["date_range"] == {
            "earliest": "2026-03-01",
            "latest": "2026-03-15",
        }
        assert group["last_played_date"] == "2026-03-01"

    def test_asks_the_database_once(self):
        """Replaces test_paginates_beyond_1000_rows. That test existed because
        the old implementation read the season in 1000-row pages and would
        silently truncate if the loop were wrong. There is no loop now — the
        counts come back already aggregated, so truncation is not expressible
        (SB-1057)."""
        dao = self._rpc_dao([self._row() for _ in range(119)])

        result = dao.get_match_summary("2025-26")

        assert len(result) == 119
        assert dao.client.rpc.call_count == 1

    def test_passes_the_score_window_through(self):
        dao = self._rpc_dao([self._row(needs_score=4)])

        result = dao.get_match_summary(
            "2025-26", score_from="2026-09-12", score_to="2026-09-13"
        )

        assert result[0]["needs_score"] == 4
        _, params = dao.client.rpc.call_args[0]
        assert params["p_score_from"] == "2026-09-12"
        assert params["p_score_to"] == "2026-09-13"

    def test_passes_the_score_grace_from_python(self):
        """SCORE_GRACE stays defined in this module. The SQL default is a safety
        net, not a second source of truth (SB-1058)."""
        from dao.match_dao import SCORE_GRACE

        dao = self._rpc_dao([self._row()])
        dao.get_match_summary("2025-26")

        _, params = dao.client.rpc.call_args[0]
        assert params["p_score_grace"] == f"{SCORE_GRACE.total_seconds()} seconds"
        assert timedelta(hours=3) == SCORE_GRACE

    def test_passes_now_and_today_rather_than_letting_sql_decide(self):
        """The caller owns the clock, so the same call is reproducible."""
        dao = self._rpc_dao([self._row()])
        dao.get_match_summary("2025-26")

        _, params = dao.client.rpc.call_args[0]
        assert params["p_today"] == date.today().isoformat()
        parsed = datetime.fromisoformat(params["p_now"])
        assert parsed.tzinfo is not None
        assert abs((datetime.now(UTC) - parsed).total_seconds()) < 30

    def test_excludes_test_fixtures_by_default(self):
        """SB-591: the agent's "what is missing" counts must not be skewed by
        hand-created fixtures, which are never scraped."""
        dao = self._rpc_dao([self._row()])
        dao.get_match_summary("2025-26")

        _, params = dao.client.rpc.call_args[0]
        assert params["p_include_test"] is False

    def test_includes_test_fixtures_when_asked(self):
        dao = self._rpc_dao([self._row()])
        dao.get_match_summary("2025-26", include_test=True)

        _, params = dao.client.rpc.call_args[0]
        assert params["p_include_test"] is True

    def test_a_null_by_status_becomes_an_empty_dict(self):
        """jsonb_object_agg over no rows is NULL, and the planner expects a dict."""
        dao = self._rpc_dao([self._row(by_status=None)])

        assert dao.get_match_summary("2025-26")[0]["by_status"] == {}

    def test_no_rows_is_an_empty_summary(self):
        dao = self._rpc_dao([])

        assert dao.get_match_summary("2025-26") == []


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



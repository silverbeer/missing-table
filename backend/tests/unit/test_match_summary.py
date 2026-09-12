"""Unit tests for the agent match-summary endpoint."""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from dao.base_dao import MATCHES_READ_RELATION


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
            elif name == MATCHES_READ_RELATION:
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
            elif name == MATCHES_READ_RELATION:
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
            elif name == MATCHES_READ_RELATION:
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


@pytest.mark.unit
class TestScoreIsDue:
    """A missing score becomes news SCORE_GRACE after kick-off, not at midnight
    UTC (SB-1058). The old rule made a full Saturday programme report
    needs_score 0 for the whole of Saturday."""

    TODAY = "2026-09-12"
    NOW = datetime(2026, 9, 12, 18, 0, tzinfo=UTC)  # 14:00 ET

    def _due(self, kickoff, md=None, now=None):
        from dao.match_dao import _score_is_due

        return _score_is_due(
            {"scheduled_kickoff": kickoff},
            now or self.NOW,
            md or self.TODAY,
            self.TODAY,
        )

    def test_a_match_played_this_morning_is_due(self):
        """13:00 UTC is 09:00 ET — five hours gone, nobody should wait for
        midnight to ask for the score."""
        assert self._due("2026-09-12T13:00:00+00:00") is True

    def test_a_match_that_just_kicked_off_is_not_due(self):
        assert self._due("2026-09-12T17:45:00+00:00") is False

    def test_the_grace_boundary_is_inclusive(self):
        from dao.match_dao import SCORE_GRACE

        assert self._due((self.NOW - SCORE_GRACE).isoformat()) is True
        assert self._due((self.NOW - SCORE_GRACE + timedelta(seconds=1)).isoformat()) is False

    def test_a_match_tonight_is_not_due(self):
        assert self._due("2026-09-12T23:00:00+00:00") is False

    def test_a_zulu_timestamp_is_understood(self):
        assert self._due("2026-09-12T13:00:00Z") is True

    def test_a_naive_timestamp_is_read_as_utc(self):
        assert self._due("2026-09-12T13:00:00") is True
        assert self._due("2026-09-12T17:45:00") is False

    def test_no_kickoff_falls_back_to_the_date_rule(self):
        """Without a time there is no telling a finished match from one that has
        not started, so the calendar day is all there is to go on."""
        assert self._due(None, md="2026-09-11") is True
        assert self._due(None, md=self.TODAY) is False
        assert self._due("", md="2026-09-11") is True

    def test_an_unparseable_timestamp_falls_back_to_the_date_rule(self):
        assert self._due("not a timestamp", md="2026-09-11") is True
        assert self._due("not a timestamp", md=self.TODAY) is False


@pytest.mark.unit
class TestNeedsScoreUsesKickoff(TestGetMatchSummary):
    """The summary itself, not just the predicate."""

    def _summary(self, matches_data):
        dao = self._make_dao()

        def table_side_effect(name):
            mock = MagicMock()
            if name == "seasons":
                mock.select.return_value = mock
                mock.eq.return_value = mock
                mock.limit.return_value = mock
                mock.execute.return_value = MagicMock(data=[{"id": 1}])
            elif name == MATCHES_READ_RELATION:
                mock.select.return_value = mock
                mock.eq.return_value = mock
                mock.neq.return_value = mock
                mock.range.return_value = mock
                mock.execute.return_value = MagicMock(data=matches_data)
            return mock

        dao.client.table = table_side_effect
        return dao.get_match_summary("2026-2027")

    @staticmethod
    def _match(kickoff, md):
        return {
            "match_date": md,
            "match_status": "scheduled",
            "home_score": None,
            "away_score": None,
            "scheduled_kickoff": kickoff,
            "age_group": {"name": "U14"},
            "division": {"name": "Northeast", "league_id": 1, "leagues": {"name": "Homegrown"}},
        }

    def test_todays_finished_matches_are_counted(self):
        """Reproduces the reported case: matches played today, hours ago, that
        the old rule reported as needs_score 0."""
        today = date.today()
        long_done = datetime.now(UTC) - timedelta(hours=6)
        still_to_come = datetime.now(UTC) + timedelta(hours=2)

        result = self._summary(
            [
                self._match(long_done.isoformat(), today.isoformat()),
                self._match(long_done.isoformat(), today.isoformat()),
                self._match(still_to_come.isoformat(), today.isoformat()),
            ]
        )

        assert result[0]["total"] == 3
        assert result[0]["needs_score"] == 2

    def test_the_score_window_still_bounds_the_count(self):
        """score_from/score_to narrows the set; kick-off does not widen past it."""
        today = date.today()
        long_done = datetime.now(UTC) - timedelta(hours=6)

        result = self._summary([self._match(long_done.isoformat(), today.isoformat())])
        assert result[0]["needs_score"] == 1

        dao_result = self._summary_windowed(
            [self._match(long_done.isoformat(), today.isoformat())],
            score_to=(today - timedelta(days=1)).isoformat(),
        )
        assert dao_result[0]["needs_score"] == 0

    def _summary_windowed(self, matches_data, **kwargs):
        dao = self._make_dao()

        def table_side_effect(name):
            mock = MagicMock()
            if name == "seasons":
                mock.select.return_value = mock
                mock.eq.return_value = mock
                mock.limit.return_value = mock
                mock.execute.return_value = MagicMock(data=[{"id": 1}])
            elif name == MATCHES_READ_RELATION:
                mock.select.return_value = mock
                mock.eq.return_value = mock
                mock.neq.return_value = mock
                mock.range.return_value = mock
                mock.execute.return_value = MagicMock(data=matches_data)
            return mock

        dao.client.table = table_side_effect
        return dao.get_match_summary("2026-2027", **kwargs)

    def test_a_scored_match_is_never_counted(self):
        today = date.today()
        long_done = (datetime.now(UTC) - timedelta(hours=6)).isoformat()
        scored = self._match(long_done, today.isoformat())
        scored["home_score"] = 2
        scored["away_score"] = 1
        scored["match_status"] = "completed"

        result = self._summary([scored])
        assert result[0]["needs_score"] == 0

"""Unit tests for the reconcile's season read, GET /api/agent/season-matches (SB-1787)."""

from unittest.mock import MagicMock, patch

import pytest


def _row(match_id, **overrides):
    """A matches_with_test row as the DAO's select returns it."""
    row = {
        "id": match_id,
        "match_id": f"kitman-{match_id}",
        "match_date": "2026-09-05",
        "match_status": "completed",
        "home_team_id": 19,
        "away_team_id": 20,
        "home_score": 2,
        "away_score": 1,
        "home_penalty_score": None,
        "away_penalty_score": None,
        "division_id": 1,
        "source": "match-scraper-agent",
        "updated_by": None,
        "score_locked": False,
        "home_team": {"name": "IFA"},
        "away_team": {"name": "The Island FC West"},
        "match_type": {"name": "League"},
        "division": {"league_id": 1},
    }
    row.update(overrides)
    return row


def _dao(*pages):
    """A MatchDAO whose successive reads return `pages`, then nothing."""
    from dao.match_dao import MatchDAO

    dao = object.__new__(MatchDAO)
    dao.connection_holder = MagicMock()
    dao.client = MagicMock()
    query = MagicMock()
    for method in ("select", "eq", "in_", "gte", "lte", "order", "range"):
        getattr(query, method).return_value = query
    query.execute.side_effect = [MagicMock(data=list(p)) for p in pages] + [MagicMock(data=[])] * 5
    dao.client.table.return_value = query
    return dao, query


@pytest.mark.unit
class TestGetAgentSeasonMatches:
    def test_rows_carry_what_the_reconcile_compares(self):
        dao, _ = _dao([_row(1, source="manual", score_locked=True)])

        [match] = dao.get_agent_season_matches(season_id=5)

        assert match == {
            "id": 1,
            "match_id": "kitman-1",
            "match_date": "2026-09-05",
            "match_status": "completed",
            "home_team_id": 19,
            "home_team_name": "IFA",
            "away_team_id": 20,
            "away_team_name": "The Island FC West",
            "home_score": 2,
            "away_score": 1,
            "home_penalty_score": None,
            "away_penalty_score": None,
            "division_id": 1,
            "league_id": 1,
            "match_type": "League",
            "source": "manual",
            "entered_by_person": True,
            "score_locked": True,
        }

    def test_updated_by_is_neither_read_nor_returned(self):
        dao, query = _dao([_row(1, updated_by="a-user-uuid")])
        [match] = dao.get_agent_season_matches(season_id=5)
        assert "updated_by" not in query.select.call_args.args[0]
        assert "updated_by" not in match
        # A scraped row someone edited is still the feed's by this signal.
        assert match["entered_by_person"] is False

    @pytest.mark.parametrize(
        ("source", "expected"),
        [("match-scraper", False), ("match-scraper-agent", False), (None, False), ("manual", True)],
    )
    def test_entered_by_person_is_source_outside_the_feed(self, source, expected):
        dao, _ = _dao([_row(1, source=source)])
        [match] = dao.get_agent_season_matches(season_id=5)
        assert match["entered_by_person"] is expected

    def test_an_unscored_division_less_match_reads_as_absent_not_zero(self):
        dao, _ = _dao([_row(1, home_score=None, away_score=None, division_id=None, division=None, score_locked=None)])
        [match] = dao.get_agent_season_matches(season_id=5)
        assert (match["home_score"], match["away_score"]) == (None, None)
        assert match["league_id"] is None
        assert match["score_locked"] is False

    def test_page_n_starts_at_n_times_page_size(self):
        dao, query = _dao([_row(i) for i in range(3)])

        dao.get_agent_season_matches(season_id=5, page=2, page_size=50)

        assert query.range.call_args_list[0].args == (100, 149)

    def test_a_short_server_response_is_topped_up_to_a_full_page(self):
        # A server whose max_rows is below the page size returns short chunks;
        # the page keeps reading until full, so later pages' offsets stay right.
        dao, query = _dao([_row(1), _row(2)], [_row(3), _row(4)], [_row(5)])

        matches = dao.get_agent_season_matches(season_id=5, page=0, page_size=4)

        assert [m["id"] for m in matches] == [1, 2, 3, 4]
        assert [c.args for c in query.range.call_args_list] == [(0, 3), (2, 3)]

    def test_past_the_end_is_an_empty_page(self):
        dao, _ = _dao()
        assert dao.get_agent_season_matches(season_id=5, page=40) == []

    def test_the_page_size_is_capped_at_one_response(self):
        from dao.match_dao import AGENT_SEASON_PAGE_MAX

        dao, query = _dao()
        dao.get_agent_season_matches(season_id=5, page=1, page_size=10_000)
        assert query.range.call_args.args == (AGENT_SEASON_PAGE_MAX, 2 * AGENT_SEASON_PAGE_MAX - 1)

    def test_filters_reach_the_query(self):
        dao, query = _dao()

        dao.get_agent_season_matches(season_id=5, start_date="2026-09-01", end_date="2026-11-30", league_ids=[1, 2])

        query.eq.assert_any_call("season_id", 5)
        query.eq.assert_any_call("is_test", False)
        query.gte.assert_called_with("match_date", "2026-09-01")
        query.lte.assert_called_with("match_date", "2026-11-30")
        query.in_.assert_called_with("division.league_id", [1, 2])
        # Filtering on the embed needs it inner-joined.
        assert "divisions!inner" in query.select.call_args.args[0]

    def test_without_leagues_division_less_matches_are_kept(self):
        dao, query = _dao()
        dao.get_agent_season_matches(season_id=5)
        query.in_.assert_not_called()
        assert "divisions!inner" not in query.select.call_args.args[0]

    def test_a_database_error_raises(self):
        dao, query = _dao()
        query.execute.side_effect = RuntimeError("connection reset")
        with pytest.raises(RuntimeError):
            dao.get_agent_season_matches(season_id=5)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app import app
    from auth import require_admin_or_service_account

    app.dependency_overrides[require_admin_or_service_account] = lambda: {
        "role": "service_account",
        "service_name": "match-scraper",
        "permissions": ["manage_matches"],
    }
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
class TestAgentSeasonMatchesEndpoint:
    def test_returns_a_page(self, client):
        with patch("app.match_dao") as dao:
            dao.get_agent_season_matches.return_value = [{"id": 1}, {"id": 2}]
            response = client.get("/api/agent/season-matches?season_id=5&page=3&page_size=2&league_ids=1,2")

        assert response.status_code == 200
        assert response.json() == {
            "season_id": 5,
            "page": 3,
            "page_size": 2,
            "count": 2,
            "matches": [{"id": 1}, {"id": 2}],
        }
        kwargs = dao.get_agent_season_matches.call_args.kwargs
        assert kwargs["league_ids"] == [1, 2]
        assert (kwargs["page"], kwargs["page_size"]) == (3, 2)
        assert kwargs["include_test"] is False

    def test_dates_reach_the_dao_as_iso_strings(self, client):
        with patch("app.match_dao") as dao:
            dao.get_agent_season_matches.return_value = []
            client.get("/api/agent/season-matches?season_id=5&start_date=2026-09-01&end_date=2026-11-30")
        kwargs = dao.get_agent_season_matches.call_args.kwargs
        assert (kwargs["start_date"], kwargs["end_date"]) == ("2026-09-01", "2026-11-30")

    @pytest.mark.parametrize("query", ["start_date=yesterday", "end_date=2026-13-01", "start_date=2026-09"])
    def test_a_malformed_date_is_422(self, client, query):
        with patch("app.match_dao") as dao:
            response = client.get(f"/api/agent/season-matches?season_id=5&{query}")
        assert response.status_code == 422
        dao.get_agent_season_matches.assert_not_called()

    def test_an_empty_page_is_200(self, client):
        with patch("app.match_dao") as dao:
            dao.get_agent_season_matches.return_value = []
            response = client.get("/api/agent/season-matches?season_id=5&page=9")
        assert response.status_code == 200
        assert response.json()["matches"] == []

    def test_a_database_error_is_a_500_not_an_empty_page(self, client):
        with patch("app.match_dao") as dao:
            dao.get_agent_season_matches.side_effect = RuntimeError("relation does not exist")
            response = client.get("/api/agent/season-matches?season_id=5")
        assert response.status_code == 500
        # Generic to the caller; the cause is in the log.
        assert "relation" not in response.text

    def test_season_id_is_required(self, client):
        assert client.get("/api/agent/season-matches").status_code == 422

    def test_league_ids_must_be_integers(self, client):
        with patch("app.match_dao") as dao:
            response = client.get("/api/agent/season-matches?season_id=5&league_ids=1,Homegrown")
        assert response.status_code == 422
        dao.get_agent_season_matches.assert_not_called()

    @pytest.mark.parametrize("query", ["page=-1", "page_size=0", "page_size=1001"])
    def test_out_of_range_paging_is_rejected(self, client, query):
        assert client.get(f"/api/agent/season-matches?season_id=5&{query}").status_code == 422

    @pytest.mark.parametrize("role", ["team_manager", "club_manager"])
    def test_managers_are_refused(self, role):
        # A whole season across leagues is an admin or service-account read.
        from fastapi.testclient import TestClient

        from app import app
        from auth import get_current_user_required

        app.dependency_overrides[get_current_user_required] = lambda: {"role": role, "user_id": "u"}
        try:
            with patch("app.match_dao") as dao:
                response = TestClient(app).get("/api/agent/season-matches?season_id=5")
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 403
        dao.get_agent_season_matches.assert_not_called()

    def test_a_service_account_without_manage_matches_is_refused(self):
        from fastapi.testclient import TestClient

        from app import app
        from auth import get_current_user_required

        app.dependency_overrides[get_current_user_required] = lambda: {"role": "service_account", "permissions": []}
        try:
            assert TestClient(app).get("/api/agent/season-matches?season_id=5").status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_requires_match_management_permission(self):
        from fastapi.testclient import TestClient

        from app import app

        app.dependency_overrides.clear()
        assert TestClient(app).get("/api/agent/season-matches?season_id=5").status_code in (401, 403)


@pytest.mark.unit
class TestConflictRowsAreNotDroppedMatches:
    """A score_locked or scraped_overrode_manual row cost no match (SB-1787)."""

    ROWS = [
        {"id": 1, "kind": "team", "raw_name": "Brand New Club", "match_count": 4},
        {"id": 2, "kind": "score_locked", "raw_name": "match 4060", "match_count": 3},
        {"id": 3, "kind": "scraped_overrode_manual", "raw_name": "match 4061", "match_count": 1},
    ]

    def test_the_admin_endpoint_counts_only_dropped_matches(self):
        from fastapi.testclient import TestClient

        from app import app
        from auth import require_admin_or_service_account

        app.dependency_overrides[require_admin_or_service_account] = lambda: {"role": "admin"}
        try:
            with patch("app.ingest_failures_dao") as dao:
                dao.open_failures.return_value = [dict(r) for r in self.ROWS]
                payload = TestClient(app).get("/api/admin/ingest-failures").json()
        finally:
            app.dependency_overrides.clear()

        assert payload["count"] == 3
        assert payload["matches_dropped"] == 4

    def _admin_get(self, url):
        from fastapi.testclient import TestClient

        from app import app
        from auth import require_admin_or_service_account

        app.dependency_overrides[require_admin_or_service_account] = lambda: {"role": "service_account"}
        try:
            with patch("app.ingest_failures_dao") as dao:
                dao.open_failures.return_value = []
                assert TestClient(app).get(url).status_code == 200
        finally:
            app.dependency_overrides.clear()
        return dao.open_failures.call_args.kwargs

    def test_the_endpoint_leaves_conflicts_out_by_default(self):
        # match-scraper reads this list with no kind and reports its
        # match_count as "rejected by MT".
        kwargs = self._admin_get("/api/admin/ingest-failures?since=2026-11-01T00:00:00Z")
        assert kwargs["kinds"] is None and kwargs["include_conflicts"] is False

    def test_the_endpoint_lists_kinds_on_request(self):
        kwargs = self._admin_get("/api/admin/ingest-failures?kind=score_locked,scraped_overrode_manual")
        assert kwargs["kinds"] == ["score_locked", "scraped_overrode_manual"]

    def test_the_endpoint_includes_everything_on_request(self):
        assert self._admin_get("/api/admin/ingest-failures?include_conflicts=true")["include_conflicts"] is True

    def test_the_admin_tool_counts_only_dropped_matches(self):
        from mt_tools.ingest import list_ingest_failures

        source = MagicMock()
        source.open_failures.return_value = [dict(r) for r in self.ROWS]

        result = list_ingest_failures(source)

        assert result.count == 3
        assert result.matches_dropped == 4
        assert source.open_failures.call_args.kwargs == {"since": None, "limit": 50}

    def test_the_admin_tool_lists_conflicts_on_request(self):
        from mt_tools.ingest import list_ingest_failures

        source = MagicMock()
        source.open_failures.return_value = []

        list_ingest_failures(source, conflicts=True)

        assert source.open_failures.call_args.kwargs["kinds"] == ["score_locked", "scraped_overrode_manual"]


def _failures_dao(rows=None, error=None):
    from dao.ingest_failures_dao import IngestFailuresDAO

    dao = object.__new__(IngestFailuresDAO)
    dao.connection_holder = MagicMock()
    dao.client = MagicMock()
    query = MagicMock()
    for method in ("select", "eq", "ilike", "is_", "gte", "in_", "order", "limit"):
        getattr(query, method).return_value = query
    query.not_ = MagicMock()
    query.not_.in_.return_value = query
    if error:
        query.execute.side_effect = error
    else:
        query.execute.return_value = MagicMock(data=rows or [])
    dao.client.table.return_value = query
    return dao, query


@pytest.mark.unit
class TestIngestFailuresDAOConflicts:
    SAMPLE = "IFA vs X, 2026-09-05 U15: held score 2-1 → 3-1"

    def test_a_closed_row_with_the_same_sample_stays_closed(self):
        dao, query = _failures_dao([{"sample": self.SAMPLE, "resolved_at": "2026-11-20T00:00:00Z"}])
        assert dao.resolved_with_sample("score_locked", "match 4060", self.SAMPLE, league="Homegrown") is True
        query.eq.assert_any_call("league", "Homegrown")
        query.eq.assert_any_call("source", "match-scraper")

    def test_a_different_sample_reopens_it(self):
        dao, _ = _failures_dao([{"sample": self.SAMPLE, "resolved_at": "2026-11-20T00:00:00Z"}])
        assert dao.resolved_with_sample("score_locked", "match 4060", self.SAMPLE.replace("3-1", "4-1")) is False

    def test_an_open_row_is_recorded_as_usual(self):
        dao, _ = _failures_dao([{"sample": self.SAMPLE, "resolved_at": None}])
        assert dao.resolved_with_sample("score_locked", "match 4060", self.SAMPLE) is False

    def test_a_null_league_matches_rows_with_none(self):
        dao, query = _failures_dao([])
        assert dao.resolved_with_sample("score_locked", "match 4060", self.SAMPLE, league=None) is False
        query.is_.assert_called_with("league", "null")

    def test_a_failed_read_records_rather_than_loses(self):
        dao, _ = _failures_dao(error=RuntimeError("down"))
        assert dao.resolved_with_sample("score_locked", "match 4060", self.SAMPLE) is False

    def test_open_failures_leaves_conflicts_out_by_default(self):
        dao, query = _failures_dao([])
        dao.open_failures()
        query.not_.in_.assert_called_once_with("kind", ["score_locked", "scraped_overrode_manual"])
        query.in_.assert_not_called()

    def test_open_failures_by_kind(self):
        dao, query = _failures_dao([])
        dao.open_failures(kinds=["score_locked"])
        query.in_.assert_called_once_with("kind", ["score_locked"])
        query.not_.in_.assert_not_called()

    def test_open_failures_with_conflicts_filters_nothing(self):
        dao, query = _failures_dao([])
        dao.open_failures(include_conflicts=True)
        query.in_.assert_not_called()
        query.not_.in_.assert_not_called()

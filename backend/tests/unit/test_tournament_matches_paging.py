"""Unit tests for the paged tournament matches and filter facets (SB-1749).

DAO: ``get_tournament_matches`` builds one counted, ranged, ordered query and
reports the database's count as ``total``; ``get_tournament_filters`` degrades
to "unavailable" — None, not zeros — when the SQL function cannot be called.

API: the status codes and the rule that a filter which cannot match returns
nothing rather than everything.

The default fixture is scraped matches with no user data: no scores, no
rosters, nothing a manager entered.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

pytestmark = [pytest.mark.unit, pytest.mark.backend]


def _scraped_match(match_id, group="HD · A", round_key="group_stage"):
    return {
        "id": match_id,
        "match_date": "2026-12-04",
        "scheduled_kickoff": None,
        "match_status": "scheduled",
        "home_score": None,
        "away_score": None,
        "home_penalty_score": None,
        "away_penalty_score": None,
        "tournament_group": group,
        "tournament_round": round_key,
        "tournament_round_order": None,
        "age_group": {"id": 5, "name": "U13"},
        "home_team": {"id": 1, "name": "Home", "club": {"id": 10, "name": "Home Club", "logo_url": None}},
        "away_team": {"id": 2, "name": "Away", "club": None},
    }


class _Query:
    """Records one PostgREST query chain."""

    def __init__(self, result):
        self.select_args = None
        self.select_kwargs = None
        self.filters = []
        self.orders = []
        self.range_args = None
        self._result = result

    def select(self, *args, **kwargs):
        self.select_args, self.select_kwargs = args, kwargs
        return self

    def eq(self, col, val):
        self.filters.append((col, val))
        return self

    def order(self, col, desc=False):
        self.orders.append((col, desc))
        return self

    def range(self, start, end):
        self.range_args = (start, end)
        return self

    def execute(self):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _response(data=None, count=None):
    r = MagicMock()
    r.data = data if data is not None else []
    r.count = count
    return r


@pytest.fixture
def dao():
    from dao.tournament_dao import TournamentDAO

    d = TournamentDAO.__new__(TournamentDAO)
    d.connection_holder = MagicMock()
    d.client = MagicMock()
    return d


def _wire(dao, results):
    queries = [_Query(r) for r in results]
    dao.client.table.side_effect = queries
    return queries


class TestGetTournamentMatches:
    def test_total_is_the_database_count_not_the_page_length(self, dao):
        _wire(dao, [_response([_scraped_match(1), _scraped_match(2)], count=2400)])

        page = dao.get_tournament_matches(6, limit=2, offset=0)

        assert page["total"] == 2400
        assert len(page["matches"]) == 2
        assert (page["limit"], page["offset"]) == (2, 0)

    def test_query_is_counted_ranged_and_stably_ordered(self, dao):
        from dao.base_dao import MATCHES_READ_RELATION
        from dao.tournament_dao import TOURNAMENT_MATCH_SELECT

        queries = _wire(dao, [_response([_scraped_match(1)], count=900)])

        dao.get_tournament_matches(6, limit=200, offset=400)

        dao.client.table.assert_called_once_with(MATCHES_READ_RELATION)
        q = queries[0]
        assert q.select_args == (TOURNAMENT_MATCH_SELECT,)
        assert q.select_kwargs == {"count": "exact"}
        assert q.range_args == (400, 599)
        # id last: without a unique tiebreaker two pages can share a row.
        assert q.orders == [("match_date", False), ("scheduled_kickoff", False), ("id", False)]

    def test_only_the_filters_given_are_applied(self, dao):
        queries = _wire(dao, [_response([_scraped_match(1)], count=1)])
        dao.get_tournament_matches(6)
        assert queries[0].filters == [("tournament_id", 6), ("is_test", False)]

    def test_age_group_group_and_round_filters(self, dao):
        queries = _wire(dao, [_response([_scraped_match(1)], count=1)])
        dao.get_tournament_matches(6, age_group_id=5, group="HD · A", round="group_stage")
        assert ("age_group_id", 5) in queries[0].filters
        assert ("tournament_group", "HD · A") in queries[0].filters
        assert ("tournament_round", "group_stage") in queries[0].filters

    def test_include_test_drops_the_partition_filter(self, dao):
        queries = _wire(dao, [_response([_scraped_match(1)], count=1)])
        dao.get_tournament_matches(6, include_test=True)
        assert all(col != "is_test" for col, _ in queries[0].filters)

    def test_rows_have_the_detail_endpoints_shape(self, dao):
        _wire(dao, [_response([_scraped_match(1)], count=1)])
        match = dao.get_tournament_matches(6)["matches"][0]
        # Clubs are lifted off the team, exactly as get_tournament_by_id does.
        assert match["home_team"] == {"id": 1, "name": "Home"}
        assert match["home_team_club"] == {"id": 10, "name": "Home Club", "logo_url": None}
        assert match["away_team_club"] is None
        # A scraped fixture: unplayed scores stay None, never 0.
        assert match["home_score"] is None
        assert match["away_score"] is None

    def test_no_matches_is_an_empty_page(self, dao):
        _wire(dao, [_response([], count=0)])
        assert dao.get_tournament_matches(6, limit=50, offset=0) == {
            "matches": [],
            "total": 0,
            "limit": 50,
            "offset": 0,
        }

    def test_offset_past_the_end_is_an_empty_page_with_the_real_total(self, dao):
        past_end = APIError({"code": "PGRST103", "message": "Requested range not satisfiable"})
        queries = _wire(dao, [past_end, _response(count=412)])

        page = dao.get_tournament_matches(6, age_group_id=5, limit=200, offset=600)

        assert page == {"matches": [], "total": 412, "limit": 200, "offset": 600}
        # The recount carries the same filters as the page it replaces.
        assert queries[1].select_kwargs == {"count": "exact", "head": True}
        assert queries[1].filters == queries[0].filters

    def test_any_other_database_error_is_raised(self, dao):
        _wire(dao, [APIError({"code": "57014", "message": "statement timeout"})])
        with pytest.raises(APIError):
            dao.get_tournament_matches(6)


class TestMatchesPageCaching:
    """Only the pages the site asks for are cached, and briefly."""

    @pytest.fixture
    def cache(self):
        with patch("dao.base_dao.cache_get", return_value=None) as get, patch("dao.base_dao.cache_set") as put:
            yield get, put

    def test_a_canonical_page_is_cached_with_the_short_ttl(self, dao, cache):
        from dao.tournament_dao import TOURNAMENT_PAGE_CACHE_TTL
        from dao.tournament_filters import DEFAULT_LIMIT

        _, put = cache
        _wire(dao, [_response([_scraped_match(1)], count=900)])

        page = dao.get_tournament_matches(6, age_group_id=5, limit=DEFAULT_LIMIT, offset=2 * DEFAULT_LIMIT)

        assert TOURNAMENT_PAGE_CACHE_TTL == 60
        put.assert_called_once()
        key, value, ttl = put.call_args.args
        assert value == page
        assert ttl == TOURNAMENT_PAGE_CACHE_TTL

    def test_a_cached_canonical_page_skips_the_database(self, dao, cache):
        get, put = cache
        cached = {"matches": [_scraped_match(1)], "total": 900, "limit": 200, "offset": 0}
        get.return_value = cached

        assert dao.get_tournament_matches(6, age_group_id=5) == cached
        dao.client.table.assert_not_called()
        put.assert_not_called()

    @pytest.mark.parametrize(
        ("limit", "offset"),
        [(50, 0), (500, 0), (200, 1), (200, 199), (199, 199), (1, 200)],
    )
    def test_a_non_canonical_page_is_served_uncached(self, dao, cache, limit, offset):
        get, put = cache
        queries = _wire(dao, [_response([_scraped_match(1)], count=900)])

        page = dao.get_tournament_matches(6, age_group_id=5, limit=limit, offset=offset)

        assert len(page["matches"]) == 1
        assert queries[0].range_args == (offset, offset + limit - 1)
        get.assert_not_called()
        put.assert_not_called()

    def test_an_empty_canonical_page_is_not_cached(self, dao, cache):
        _, put = cache
        _wire(dao, [_response([], count=0)])
        dao.get_tournament_matches(6, group="No Such Group")
        put.assert_not_called()

    def test_the_key_carries_every_filter_and_the_test_partition(self, dao, cache):
        _, put = cache
        base = {"age_group_id": 5, "group": "HD · A", "round": "group_stage", "include_test": False}
        variants = [
            base,
            {**base, "age_group_id": 7},
            {**base, "group": "AD · A"},
            {**base, "round": "showcase"},
            {**base, "include_test": True},
        ]
        _wire(dao, [_response([_scraped_match(1)], count=1) for _ in range(len(variants) + 2)])

        for kwargs in variants:
            dao.get_tournament_matches(6, **kwargs)
        dao.get_tournament_matches(8, **base)
        dao.get_tournament_matches(6, offset=200, **base)

        keys = [call.args[0] for call in put.call_args_list]
        assert len(set(keys)) == len(variants) + 2


class TestGetTournamentFilters:
    def _rpc(self, dao, result):
        call = MagicMock()
        if isinstance(result, Exception):
            call.execute.side_effect = result
        else:
            call.execute.return_value = _response(result)
        dao.client.rpc.return_value = call

    def test_calls_the_function_with_every_parameter(self, dao):
        self._rpc(dao, [])
        dao.get_tournament_filters(6, age_group_id=5, include_test=True, on_date="2026-12-04")
        dao.client.rpc.assert_called_once_with(
            "tournament_filter_facets",
            {"p_tournament_id": 6, "p_age_group_id": 5, "p_include_test": True, "p_on_date": "2026-12-04"},
        )

    def test_groups_plus_counts(self, dao):
        self._rpc(
            dao,
            [
                {"facet": "age_group", "age_group_id": 5, "age_group_name": "U13", "matches": 1437},
                {"facet": "group", "tournament_group": "HD · A", "matches": 6},
                {"facet": "group", "tournament_group": "AD · A", "matches": 6},
            ],
        )
        out = dao.get_tournament_filters(6, age_group_id=5)
        assert out["facets_available"] is True
        assert out["age_groups"][0]["matches"] == 1437
        assert [g["key"] for g in out["groups"]] == ["AD · A", "HD · A"]

    def test_showcase_only_age_group_has_no_groups(self, dao):
        self._rpc(dao, [{"facet": "age_group", "age_group_id": 7, "age_group_name": "U15", "matches": 380}])
        assert dao.get_tournament_filters(6, age_group_id=7)["groups"] == []

    def test_missing_function_degrades_to_unavailable_not_zero(self, dao):
        self._rpc(dao, APIError({"code": "PGRST202", "message": "Could not find the function"}))
        with patch.object(type(dao), "get_tournament_age_groups", return_value=[{"id": 5, "name": "U13"}]):
            out = dao.get_tournament_filters(6, age_group_id=5)
        assert out == {
            "facets_available": False,
            "age_groups": [{"id": 5, "name": "U13", "matches": None, "matches_on_date": None}],
            "groups": None,
        }

    @pytest.mark.parametrize(
        "error",
        [
            APIError({"code": "57014", "message": "canceling statement due to statement timeout"}),
            APIError({"code": "42501", "message": "permission denied for function tournament_filter_facets"}),
            APIError({"code": "PGRST203", "message": "Could not choose the best candidate function"}),
            RuntimeError("connection reset"),
        ],
    )
    def test_any_other_error_is_raised_not_reported_as_unavailable(self, dao, error):
        self._rpc(dao, error)
        with (
            patch.object(type(dao), "get_tournament_age_groups", return_value=[{"id": 5, "name": "U13"}]),
            pytest.raises(type(error)),
        ):
            dao.get_tournament_filters(6, age_group_id=5)


class TestGetTournamentAgeGroups:
    def test_unknown_tournament_is_none(self, dao):
        chain = MagicMock()
        chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = _response([])
        dao.client.table.return_value = chain
        assert dao.get_tournament_age_groups(999) is None

    def test_known_tournament_with_no_age_groups_is_an_empty_list(self, dao):
        chain = MagicMock()
        chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = _response([{"id": 6}])
        dao.client.table.return_value = chain
        with patch.object(
            type(dao), "_attach_age_groups", side_effect=lambda ts: [{**t, "age_groups": []} for t in ts]
        ):
            assert dao.get_tournament_age_groups(6) == []


# ── API ──────────────────────────────────────────────────────────────────────

PAGE = {"matches": [_scraped_match(1)], "total": 1437, "limit": 200, "offset": 0}
FILTERS = {
    "facets_available": True,
    "age_groups": [{"id": 5, "name": "U13", "matches": 1437, "matches_on_date": None}],
    "groups": [{"key": "HD · A", "division": "HD", "label": "A", "matches": 6}],
}
UNAVAILABLE = {
    "facets_available": False,
    "age_groups": [{"id": 5, "name": "U13", "matches": None, "matches_on_date": None}],
    "groups": None,
}


@pytest.fixture
def client():
    import app as app_module
    from auth import get_current_user_optional

    dao = MagicMock()
    dao.get_tournament_age_groups.return_value = [{"id": 5, "name": "U13"}]
    dao.get_tournament_matches.return_value = PAGE
    dao.get_tournament_filters.return_value = FILTERS
    app_module.app.dependency_overrides[get_current_user_optional] = lambda: None
    with patch.object(app_module, "tournament_dao", dao):
        yield TestClient(app_module.app), dao
    app_module.app.dependency_overrides.clear()


def _sign_in(user):
    import app as app_module
    from auth import get_current_user_optional

    app_module.app.dependency_overrides[get_current_user_optional] = lambda: user


# Who sees the test partition: admins and flagged test users, nobody else.
VIEWERS = [
    ({"id": "u1", "role": "admin"}, True),
    ({"id": "u2", "role": "user", "is_test": True}, True),
    ({"id": "u3", "role": "team_manager"}, False),
    ({"id": "u4", "role": "user", "is_test": False}, False),
]


class TestMatchesEndpoint:
    def test_defaults(self, client):
        http, dao = client
        r = http.get("/api/tournaments/6/matches")
        assert r.status_code == 200
        assert r.json() == PAGE
        assert dao.get_tournament_matches.call_args.kwargs == {
            "age_group_id": None,
            "group": None,
            "round": None,
            "limit": 200,
            "offset": 0,
            "include_test": False,
        }

    def test_filters_are_passed_to_the_dao(self, client):
        http, dao = client
        params = {"age_group_id": "5", "group": "HD · A", "round": "group_stage", "limit": 50, "offset": 100}
        http.get("/api/tournaments/6/matches", params=params)
        kwargs = dao.get_tournament_matches.call_args.kwargs
        assert (kwargs["age_group_id"], kwargs["group"], kwargs["round"]) == (5, "HD · A", "group_stage")
        assert (kwargs["limit"], kwargs["offset"]) == (50, 100)

    def test_limit_is_capped_at_500(self, client):
        http, dao = client
        http.get("/api/tournaments/6/matches", params={"limit": 5000})
        assert dao.get_tournament_matches.call_args.kwargs["limit"] == 500

    def test_negative_offset_is_zero(self, client):
        http, dao = client
        http.get("/api/tournaments/6/matches", params={"offset": -10})
        assert dao.get_tournament_matches.call_args.kwargs["offset"] == 0

    def test_unknown_tournament_is_404(self, client):
        http, dao = client
        dao.get_tournament_age_groups.return_value = None
        assert http.get("/api/tournaments/999/matches").status_code == 404
        dao.get_tournament_matches.assert_not_called()

    def test_known_tournament_with_no_matches_is_200_and_empty(self, client):
        http, dao = client
        dao.get_tournament_age_groups.return_value = []
        dao.get_tournament_matches.return_value = {"matches": [], "total": 0, "limit": 200, "offset": 0}
        r = http.get("/api/tournaments/6/matches")
        assert r.status_code == 200
        assert r.json()["matches"] == []

    @pytest.mark.parametrize("params", [{"age_group_id": "abc"}, {"round": "not_a_round"}, {"age_group_id": "-3"}])
    def test_a_filter_that_cannot_match_returns_nothing_not_everything(self, client, params):
        http, dao = client
        r = http.get("/api/tournaments/6/matches", params=params)
        assert r.status_code == 200
        assert r.json() == {"matches": [], "total": 0, "limit": 200, "offset": 0}
        dao.get_tournament_matches.assert_not_called()

    def test_anonymous_viewers_never_see_test_matches(self, client):
        http, dao = client
        http.get("/api/tournaments/6/matches")
        assert dao.get_tournament_matches.call_args.kwargs["include_test"] is False

    @pytest.mark.parametrize(("user", "sees_test"), VIEWERS)
    def test_signed_in_viewers_see_test_matches_only_when_entitled(self, client, user, sees_test):
        http, dao = client
        _sign_in(user)
        http.get("/api/tournaments/6/matches")
        assert dao.get_tournament_matches.call_args.kwargs["include_test"] is sees_test

    def test_a_database_error_is_500(self, client):
        http, dao = client
        dao.get_tournament_matches.side_effect = RuntimeError("boom")
        assert http.get("/api/tournaments/6/matches").status_code == 500


class TestFiltersEndpoint:
    def test_returns_the_facets(self, client):
        http, dao = client
        r = http.get("/api/tournaments/6/filters", params={"age_group_id": "5", "on_date": "2026-12-04"})
        assert r.status_code == 200
        assert r.json() == FILTERS
        assert dao.get_tournament_filters.call_args.kwargs == {
            "age_group_id": 5,
            "include_test": False,
            "on_date": "2026-12-04",
        }

    def test_unavailable_facets_are_200_with_nulls(self, client):
        http, dao = client
        dao.get_tournament_filters.return_value = UNAVAILABLE
        r = http.get("/api/tournaments/6/filters", params={"age_group_id": "5"})
        assert r.status_code == 200
        body = r.json()
        assert body["groups"] is None
        assert body["age_groups"][0]["matches"] is None

    def test_anonymous_viewers_never_get_test_matches_counted(self, client):
        http, dao = client
        http.get("/api/tournaments/6/filters")
        assert dao.get_tournament_filters.call_args.kwargs["include_test"] is False

    @pytest.mark.parametrize(("user", "sees_test"), VIEWERS)
    def test_signed_in_viewers_get_test_matches_counted_only_when_entitled(self, client, user, sees_test):
        http, dao = client
        _sign_in(user)
        http.get("/api/tournaments/6/filters")
        assert dao.get_tournament_filters.call_args.kwargs["include_test"] is sees_test

    @pytest.mark.parametrize(
        "error",
        [
            APIError({"code": "57014", "message": "canceling statement due to statement timeout"}),
            RuntimeError("secret-host.internal refused the connection"),
        ],
    )
    def test_a_database_error_is_500_with_a_generic_message(self, client, error):
        http, dao = client
        dao.get_tournament_filters.side_effect = error
        r = http.get("/api/tournaments/6/filters", params={"age_group_id": "5"})
        assert r.status_code == 500
        # Not a degraded 200, and nothing of the error reaches the client.
        assert r.json() == {"detail": "Could not load tournament filters"}

    def test_unknown_tournament_is_404(self, client):
        http, dao = client
        dao.get_tournament_age_groups.return_value = None
        assert http.get("/api/tournaments/999/filters").status_code == 404

    def test_an_age_group_that_is_not_an_id_has_no_groups(self, client):
        http, dao = client
        r = http.get("/api/tournaments/6/filters", params={"age_group_id": "abc"})
        assert r.status_code == 200
        assert r.json()["groups"] == []
        assert r.json()["age_groups"] == FILTERS["age_groups"]

    def test_a_bad_age_group_does_not_turn_unknown_into_none(self, client):
        # Unavailable stays null: "abc has no groups" must not overwrite "unknown".
        http, dao = client
        dao.get_tournament_filters.return_value = UNAVAILABLE
        r = http.get("/api/tournaments/6/filters", params={"age_group_id": "abc"})
        assert r.json()["groups"] is None

    def test_a_bad_date_is_ignored(self, client):
        http, dao = client
        http.get("/api/tournaments/6/filters", params={"on_date": "Dec 4"})
        assert dao.get_tournament_filters.call_args.kwargs["on_date"] is None


class TestDetailEndpointUnchanged:
    def test_detail_still_returns_the_dao_payload_as_is(self, client):
        http, dao = client
        detail = {"id": 6, "name": "Fest", "age_groups": [], "matches": [_scraped_match(1)]}
        dao.get_tournament_by_id.return_value = detail
        r = http.get("/api/tournaments/6")
        assert r.status_code == 200
        assert r.json() == detail
        dao.get_tournament_by_id.assert_called_once_with(6, include_test=False)
        dao.get_tournament_matches.assert_not_called()

    def test_detail_unknown_tournament_is_still_404(self, client):
        http, dao = client
        dao.get_tournament_by_id.return_value = None
        assert http.get("/api/tournaments/999").status_code == 404

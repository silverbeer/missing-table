"""Prod test-partition visibility for matches (SB-591, Phase 2).

Phase 1 (SB-85) hid test leagues and tournaments from real viewers but not the
matches inside them. This exercises the Phase 2 filter on the match endpoints
and the match-derived views:

  GET /api/matches            — the raw list
  GET /api/matches/{id}       — direct fetch (must 404, not leak)
  GET /api/matches/live       — the LIVE tab an Android dry run drives
  GET /api/table              — standings; a test result must not move points
  GET /api/seasons/match-counts — admin counts

The seeded world covers the derivation rule's independent paths, because
matches.division_id and matches.tournament_id are both nullable:

  test-by-league  — real clubs, but the division's league is is_test
  test-by-club    — real league/division, but one club is is_test
  test-by-neither — no division at all, test club (a friendly)
  real            — control; must stay visible to everyone

Viewers are injected by overriding the auth dependencies, so no real tokens are
needed. The rows are real, so the view's derivation and the DAO filter are both
exercised for real.

Requires local Supabase. Skips cleanly if unreachable.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import app
from auth import get_current_user_optional, get_current_user_required
from dao.base_dao import clear_cache

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]


def _admin_client():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:55321")
    if not ("127.0.0.1" in url or "localhost" in url):
        pytest.skip(f"Refusing to run destructive test against non-local Supabase: {url}")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY not set — cannot run test-partition test")
    return create_client(url, key)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


def _first_id(admin, table: str) -> int:
    rows = admin.table(table).select("id").order("id").limit(1).execute().data
    if not rows:
        pytest.skip(f"No reference rows in {table}; seed the local DB first")
    return rows[0]["id"]


@pytest.fixture
def world():
    """Seed real + test leagues/clubs/teams and four matches covering each path."""
    admin = _admin_client()
    try:
        admin.table("leagues").select("id").limit(1).execute()
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("Local Supabase not reachable")

    season_id = _first_id(admin, "seasons")
    age_group_id = _first_id(admin, "age_groups")
    match_type_id = _first_id(admin, "match_types")

    created: dict[str, list[int]] = {
        "matches": [], "teams": [], "clubs": [], "divisions": [], "leagues": []
    }

    def _mk(table: str, payload: dict) -> dict:
        row = admin.table(table).insert(payload).execute().data[0]
        created[table].append(row["id"])
        return row

    real_league = _mk("leagues", {"name": _unique("ZZ Real Lg"), "is_active": True, "is_test": False})
    test_league = _mk("leagues", {"name": _unique("ZZ Test Lg"), "is_active": True, "is_test": True})
    real_div = _mk("divisions", {"name": _unique("ZZ Real Div"), "league_id": real_league["id"]})
    test_div = _mk("divisions", {"name": _unique("ZZ Test Div"), "league_id": test_league["id"]})

    real_club_a = _mk("clubs", {"name": _unique("ZZ Real Club A"), "is_test": False})
    real_club_b = _mk("clubs", {"name": _unique("ZZ Real Club B"), "is_test": False})
    test_club = _mk("clubs", {"name": _unique("ZZ Test Club"), "is_test": True})

    def _team(name: str, club: dict, league: dict, div: dict) -> dict:
        return _mk("teams", {
            "name": _unique(name), "club_id": club["id"],
            "league_id": league["id"], "division_id": div["id"],
        })

    real_a = _team("ZZ Real A", real_club_a, real_league, real_div)
    real_b = _team("ZZ Real B", real_club_b, real_league, real_div)
    test_team = _team("ZZ Test Team", test_club, real_league, real_div)

    base = datetime.now(UTC).date()

    def _match(home: dict, away: dict, division_id: int | None, offset: int, status="completed",
               hs=3, as_=1) -> dict:
        return _mk("matches", {
            "match_date": (base + timedelta(days=offset)).isoformat(),
            "home_team_id": home["id"], "away_team_id": away["id"],
            "season_id": season_id, "age_group_id": age_group_id,
            "match_type_id": match_type_id, "division_id": division_id,
            "match_status": status, "home_score": hs, "away_score": as_,
        })

    real_match = _match(real_a, real_b, real_div["id"], 1)
    test_by_league = _match(real_a, real_b, test_div["id"], 2)
    test_by_club = _match(test_team, real_b, real_div["id"], 3)
    test_by_neither = _match(test_team, real_b, None, 4)
    real_live = _match(real_a, real_b, real_div["id"], 5, status="live", hs=0, as_=0)
    test_live = _match(test_team, real_b, real_div["id"], 6, status="live", hs=0, as_=0)

    # Raw inserts bypass the DAOs' invalidates_cache, so bust everything that
    # could hold a stale match list, table or count.
    for pattern in ("mt:dao:matches:*", "mt:dao:teams:*", "mt:dao:stats:*",
                    "mt:dao:leagues:*", "mt:dao:tournaments:*", "mt:dao:seasons:*"):
        clear_cache(pattern)

    yield {
        "real": real_match,
        "test_by_league": test_by_league,
        "test_by_club": test_by_club,
        "test_by_neither": test_by_neither,
        "real_live": real_live,
        "test_live": test_live,
        "season_id": season_id,
        "age_group_id": age_group_id,
        "real_division_id": real_div["id"],
        "real_team_id": real_a["id"],
        "test_team_id": test_team["id"],
    }

    # Children first — matches reference teams, teams reference clubs/divisions.
    for table in ("matches", "teams", "clubs", "divisions", "leagues"):
        for row_id in created[table]:
            try:
                admin.table(table).delete().eq("id", row_id).execute()
            except Exception:  # pragma: no cover
                pass
    for pattern in ("mt:dao:matches:*", "mt:dao:teams:*", "mt:dao:stats:*",
                    "mt:dao:leagues:*", "mt:dao:tournaments:*", "mt:dao:seasons:*"):
        clear_cache(pattern)


_REAL_FAN = {"user_id": "real", "role": "team-fan", "is_test": False}
_TEST_USER = {"user_id": "tester", "role": "team-fan", "is_test": True}
_ADMIN = {"user_id": "admin", "role": "admin", "is_test": False}

HIDDEN_FROM_REAL = ("test_by_league", "test_by_club", "test_by_neither")


def _as(viewer):
    """Run the TestClient with both auth dependencies resolved to `viewer`."""
    app.dependency_overrides[get_current_user_optional] = lambda: viewer
    app.dependency_overrides[get_current_user_required] = lambda: viewer
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _ids(rows):
    return {r["id"] for r in rows}


class TestMatchListPartition:
    def test_real_viewer_sees_no_test_matches(self, world):
        with _as(_REAL_FAN) as client:
            resp = client.get("/api/matches", params={"season_id": world["season_id"]})
        assert resp.status_code == 200
        ids = _ids(resp.json())
        assert world["real"]["id"] in ids
        for key in HIDDEN_FROM_REAL:
            assert world[key]["id"] not in ids, f"{key} leaked to a real viewer"

    @pytest.mark.parametrize("viewer,label", [(_TEST_USER, "test user"), (_ADMIN, "admin")])
    def test_test_user_and_admin_see_every_match(self, world, viewer, label):
        with _as(viewer) as client:
            resp = client.get("/api/matches", params={"season_id": world["season_id"]})
        ids = _ids(resp.json())
        assert world["real"]["id"] in ids
        for key in HIDDEN_FROM_REAL:
            assert world[key]["id"] in ids, f"{key} hidden from {label}"


class TestSingleMatchPartition:
    @pytest.mark.parametrize("key", HIDDEN_FROM_REAL)
    def test_direct_fetch_of_a_test_match_404s_for_a_real_viewer(self, world, key):
        """Guessing the id must not bypass the list filter."""
        with _as(_REAL_FAN) as client:
            resp = client.get(f"/api/matches/{world[key]['id']}")
        assert resp.status_code == 404, f"{key} was fetchable by id: {resp.text[:200]}"

    def test_real_match_is_still_fetchable(self, world):
        with _as(_REAL_FAN) as client:
            resp = client.get(f"/api/matches/{world['real']['id']}")
        assert resp.status_code == 200

    @pytest.mark.parametrize("key", HIDDEN_FROM_REAL)
    def test_admin_can_fetch_a_test_match(self, world, key):
        with _as(_ADMIN) as client:
            resp = client.get(f"/api/matches/{world[key]['id']}")
        assert resp.status_code == 200


class TestLiveTabPartition:
    # /api/matches/live returns a flattened shape keyed by match_id, not id.
    @staticmethod
    def _live_ids(payload):
        return {r["match_id"] for r in payload}

    def test_a_test_dry_run_does_not_appear_on_the_public_live_tab(self, world):
        with _as(_REAL_FAN) as client:
            ids = self._live_ids(client.get("/api/matches/live").json())
        assert world["real_live"]["id"] in ids
        assert world["test_live"]["id"] not in ids

    def test_test_user_sees_their_own_dry_run(self, world):
        with _as(_TEST_USER) as client:
            ids = self._live_ids(client.get("/api/matches/live").json())
        assert world["test_live"]["id"] in ids


class TestStandingsPartition:
    """The whole point of the partition: a rehearsal must not change the table."""

    @staticmethod
    def _standings(payload):
        return payload["standings"] if isinstance(payload, dict) else payload

    def _table_for(self, viewer, world):
        params = {
            "season_id": world["season_id"],
            "age_group_id": world["age_group_id"],
            "division_id": world["real_division_id"],
        }
        with _as(viewer) as client:
            return self._standings(client.get("/api/table", params=params).json())

    def test_test_team_absent_from_a_real_viewers_standings(self, world):
        """test_by_club sits in the *real* division — only the flag keeps it out."""
        rows = self._table_for(_REAL_FAN, world)
        team_ids = {r["team_id"] for r in rows}
        assert world["real_team_id"] in team_ids
        assert world["test_team_id"] not in team_ids

    def test_admin_standings_include_the_test_team(self, world):
        rows = self._table_for(_ADMIN, world)
        assert world["test_team_id"] in {r["team_id"] for r in rows}

    def test_a_real_teams_record_is_identical_either_way(self, world):
        """A test result must not add a played match or points to a real team."""
        real_row = next(
            r for r in self._table_for(_REAL_FAN, world) if r["team_id"] == world["real_team_id"]
        )
        admin_row = next(
            r for r in self._table_for(_ADMIN, world) if r["team_id"] == world["real_team_id"]
        )
        for field in ("played", "points", "wins", "draws", "losses", "goals_for", "goals_against"):
            assert real_row[field] == admin_row[field], (
                f"{field} differs for a real team between viewers "
                f"({real_row[field]} vs {admin_row[field]}) — a test match moved the real table"
            )


class TestSeasonMatchCounts:
    def test_admin_counts_include_test_matches(self, world):
        """Admins are the audience that needs to confirm the test world exists."""
        with _as(_ADMIN) as client:
            resp = client.get("/api/seasons/match-counts")
        assert resp.status_code == 200
        by_season = {r["season_id"]: r["match_count"] for r in resp.json()}
        assert by_season.get(world["season_id"], 0) >= 6

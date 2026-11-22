"""Paged tournament matches and filter facets against a real database (SB-1749).

One PostgREST response is capped at 1,000 rows, so a tournament the size of
MLS NEXT Fest cannot be read in one request. This seeds one tournament with
more than 1,000 real matches shaped like the Fest — an age group with HD and
AD groups plus placement finals and consolation, and a showcase-only age
group — and reads it back through the DAO.

The facet counts come from the ``tournament_filter_facets`` SQL function
(migration 20261123120000). Tests that need it skip when it is not installed;
``test_filters_degrade_when_the_function_is_missing`` runs only then.

Requires local Supabase. Skips cleanly if unreachable or not local.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]

# Group-stage filler that takes the first age group past the 1,000-row cap.
FILLER = 1000
HD_A = 6
AD_A = 5
PLACEMENT = 3
CONSOLATION = 2
HD_SHOWCASE = 10
AD_SHOWCASE = 4
TEST_FIXTURES = 7  # played by a club flagged is_test

GROUPS_AGE_TOTAL = FILLER + HD_A + AD_A + PLACEMENT + CONSOLATION
SHOWCASE_AGE_TOTAL = HD_SHOWCASE + AD_SHOWCASE
REAL_TOTAL = GROUPS_AGE_TOTAL + SHOWCASE_AGE_TOTAL

SEED_DAY = date(2020, 1, 1)
DAYS = 30


def _admin_client():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:55321")
    if not ("127.0.0.1" in url or "localhost" in url):
        pytest.skip(f"Refusing to run destructive test against non-local Supabase: {url}")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY not set - cannot run tournament paging test")
    return create_client(url, key)


def _first_ids(admin, table: str, n: int = 1) -> list[int]:
    rows = admin.table(table).select("id").order("id").limit(n).execute().data
    if len(rows) < n:
        pytest.skip(f"Need {n} reference rows in {table}; seed the local DB first")
    return [r["id"] for r in rows]


def _dao(admin):
    from dao.tournament_dao import TournamentDAO

    dao = TournamentDAO.__new__(TournamentDAO)
    dao.connection_holder = MagicMock()
    dao.client = admin
    return dao


@pytest.fixture(scope="module")
def fest():
    """A Fest-shaped tournament of scraped matches: no scores, no rosters."""
    admin = _admin_client()
    try:
        admin.table("tournaments").select("id").limit(1).execute()
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("Local Supabase not reachable")

    season_id = _first_ids(admin, "seasons")[0]
    match_type_id = _first_ids(admin, "match_types")[0]
    groups_age, showcase_age = _first_ids(admin, "age_groups", 2)
    tag = uuid.uuid4().hex[:8]

    club_ids: list[int] = []
    team_ids: list[int] = []
    tournament_id = None
    try:
        for label, is_test in (("A", False), ("B", False), ("T", True)):
            club = (
                admin.table("clubs")
                .insert({"name": f"ZZ Paging Club {label} {tag}", "is_test": is_test})
                .execute()
                .data[0]
            )
            club_ids.append(club["id"])
            team = (
                admin.table("teams")
                .insert({"name": f"ZZ Paging Team {label} {tag}", "club_id": club["id"]})
                .execute()
                .data[0]
            )
            team_ids.append(team["id"])
        home, away, test_team = team_ids

        tournament_id = (
            admin.table("tournaments")
            .insert(
                {
                    "name": f"ZZ Paging Fest {tag}",
                    "start_date": SEED_DAY.isoformat(),
                    "season_id": season_id,
                    "is_active": True,
                    "is_test": False,
                }
            )
            .execute()
            .data[0]["id"]
        )

        rows: list[dict] = []

        def add(count, age_group_id, group, round_key, home_team=home):
            for _ in range(count):
                i = len(rows)
                rows.append(
                    {
                        # Many matches share a day and none has a kickoff, so
                        # only the id tiebreaker keeps the pages apart.
                        "match_date": (SEED_DAY + timedelta(days=i % DAYS)).isoformat(),
                        "home_team_id": home_team,
                        "away_team_id": away,
                        "season_id": season_id,
                        "age_group_id": age_group_id,
                        "match_type_id": match_type_id,
                        "tournament_id": tournament_id,
                        "tournament_group": group,
                        "tournament_round": round_key,
                        "match_status": "scheduled",
                    }
                )

        add(FILLER, groups_age, "HD · B", "group_stage")
        add(HD_A, groups_age, "HD · A", "group_stage")
        add(AD_A, groups_age, "AD · A", "group_stage")
        add(PLACEMENT, groups_age, "HD · Group Play", "placement_final")
        add(CONSOLATION, groups_age, "HD · Group Play", "consolation")
        add(HD_SHOWCASE, showcase_age, "HD · Showcase", "showcase")
        add(AD_SHOWCASE, showcase_age, "AD · Showcase", "showcase")
        add(TEST_FIXTURES, groups_age, "HD · A", "group_stage", home_team=test_team)
        for start in range(0, len(rows), 500):
            admin.table("matches").insert(rows[start : start + 500]).execute()

        yield {
            "admin": admin,
            "dao": _dao(admin),
            "tournament_id": tournament_id,
            "groups_age": groups_age,
            "showcase_age": showcase_age,
        }
    finally:
        # Each step runs even if an earlier one failed, so one bad delete does
        # not strand the rest of the "ZZ Paging" rows; failures are raised after.
        steps = []
        if tournament_id is not None:
            steps.append(("matches", "tournament_id", tournament_id))
            steps.append(("tournaments", "id", tournament_id))
        steps.extend(("teams", "id", tid) for tid in team_ids)
        steps.extend(("clubs", "id", cid) for cid in club_ids)
        failures = []
        for table, column, value in steps:
            try:
                admin.table(table).delete().eq(column, value).execute()
            except Exception as exc:
                failures.append(f"{table}.{column}={value}: {exc!r}")
        if failures:
            raise RuntimeError("fest cleanup left rows behind: " + "; ".join(failures))


def _facets_installed(admin) -> bool:
    from postgrest.exceptions import APIError

    try:
        admin.rpc("tournament_filter_facets", {"p_tournament_id": -1}).execute()
        return True
    except APIError:
        return False


@pytest.fixture
def facets(fest):
    if not _facets_installed(fest["admin"]):
        pytest.skip(
            "tournament_filter_facets is not installed - apply migration "
            "20261123120000_tournament_filter_facets.sql (./scripts/db_tools.sh migrate local)"
        )
    return fest


def _all_pages(dao, tournament_id, limit, **filters):
    pages, offset = [], 0
    while True:
        page = dao.get_tournament_matches(tournament_id, limit=limit, offset=offset, **filters)
        pages.append(page)
        offset += limit
        if offset >= page["total"]:
            return pages


# ── paging ───────────────────────────────────────────────────────────────────


def test_total_is_exact_above_the_row_cap(fest):
    page = fest["dao"].get_tournament_matches(fest["tournament_id"], limit=200, offset=0)

    assert REAL_TOTAL > 1000
    assert page["total"] == REAL_TOTAL
    assert len(page["matches"]) == 200


def test_pages_neither_overlap_nor_skip(fest):
    pages = _all_pages(fest["dao"], fest["tournament_id"], limit=200)

    ids = [m["id"] for page in pages for m in page["matches"]]
    assert len(ids) == REAL_TOTAL
    assert len(set(ids)) == REAL_TOTAL
    assert all(page["total"] == REAL_TOTAL for page in pages)
    # Day first, then id: the order the pages were cut in.
    keys = [(m["match_date"], m["id"]) for page in pages for m in page["matches"]]
    assert keys == sorted(keys)


def test_the_limit_cap_of_500_still_reads_every_row(fest):
    pages = _all_pages(fest["dao"], fest["tournament_id"], limit=500, age_group_id=fest["groups_age"])

    ids = {m["id"] for page in pages for m in page["matches"]}
    assert len(ids) == GROUPS_AGE_TOTAL
    assert GROUPS_AGE_TOTAL > 1000


def test_offset_past_the_end_is_empty_with_the_real_total(fest):
    page = fest["dao"].get_tournament_matches(fest["tournament_id"], limit=200, offset=REAL_TOTAL + 50)

    assert page["matches"] == []
    assert page["total"] == REAL_TOTAL


def test_offset_exactly_at_the_end_is_empty_with_the_real_total(fest):
    page = fest["dao"].get_tournament_matches(fest["tournament_id"], limit=200, offset=REAL_TOTAL)

    assert page["matches"] == []
    assert page["total"] == REAL_TOTAL


# ── filters on the match list ────────────────────────────────────────────────


def test_age_group_filter(fest):
    dao, tid = fest["dao"], fest["tournament_id"]

    showcase = dao.get_tournament_matches(tid, age_group_id=fest["showcase_age"], limit=200)
    assert showcase["total"] == SHOWCASE_AGE_TOTAL
    assert {m["tournament_round"] for m in showcase["matches"]} == {"showcase"}
    assert dao.get_tournament_matches(tid, age_group_id=fest["groups_age"], limit=1)["total"] == GROUPS_AGE_TOTAL


def test_hd_a_and_ad_a_filter_separately(fest):
    dao, tid = fest["dao"], fest["tournament_id"]

    hd = dao.get_tournament_matches(tid, age_group_id=fest["groups_age"], group="HD · A", limit=200)
    ad = dao.get_tournament_matches(tid, age_group_id=fest["groups_age"], group="AD · A", limit=200)

    assert hd["total"] == HD_A
    assert ad["total"] == AD_A
    assert {m["tournament_group"] for m in hd["matches"]} == {"HD · A"}
    assert {m["tournament_group"] for m in ad["matches"]} == {"AD · A"}
    assert not {m["id"] for m in hd["matches"]} & {m["id"] for m in ad["matches"]}


def test_round_filter(fest):
    dao, tid = fest["dao"], fest["tournament_id"]

    assert dao.get_tournament_matches(tid, round="placement_final", limit=200)["total"] == PLACEMENT
    assert dao.get_tournament_matches(tid, round="consolation", limit=200)["total"] == CONSOLATION
    assert dao.get_tournament_matches(tid, round="showcase", limit=200)["total"] == SHOWCASE_AGE_TOTAL


def test_a_group_nobody_plays_in_is_an_empty_page(fest):
    page = fest["dao"].get_tournament_matches(fest["tournament_id"], group="HD · ZZ", limit=200)

    assert page == {"matches": [], "total": 0, "limit": 200, "offset": 0}


def test_test_fixtures_are_hidden_unless_included(fest):
    dao, tid = fest["dao"], fest["tournament_id"]

    assert dao.get_tournament_matches(tid, limit=1, include_test=True)["total"] == REAL_TOTAL + TEST_FIXTURES
    hd_all = dao.get_tournament_matches(tid, group="HD · A", limit=200, include_test=True)
    assert hd_all["total"] == HD_A + TEST_FIXTURES


def test_a_scraped_match_renders_without_user_data(fest):
    match = fest["dao"].get_tournament_matches(fest["tournament_id"], limit=1)["matches"][0]

    # Unplayed and unscored: absent stays None, it is not 0.
    assert match["home_score"] is None
    assert match["away_score"] is None
    assert match["home_team"]["name"].startswith("ZZ Paging Team")
    assert match["home_team_club"]["name"].startswith("ZZ Paging Club")
    assert "club" not in match["home_team"]


# ── the old detail endpoint ──────────────────────────────────────────────────


def test_detail_endpoint_is_unchanged(fest):
    dao, tid = fest["dao"], fest["tournament_id"]

    detail = dao.get_tournament_by_id(tid)
    paged = dao.get_tournament_matches(tid, age_group_id=fest["showcase_age"], limit=200)

    assert detail["id"] == tid
    assert set(detail) >= {"id", "name", "start_date", "age_groups", "matches"}
    # Still one unpaged query: it returns what one response can hold and no more.
    assert 0 < len(detail["matches"]) <= REAL_TOTAL
    # A row is the same from either endpoint.
    by_id = {m["id"]: m for m in detail["matches"]}
    shared = [m for m in paged["matches"] if m["id"] in by_id]
    for match in shared:
        assert match == by_id[match["id"]]
    assert set(detail["matches"][0]) == set(paged["matches"][0])
    # Test fixtures stay out of it, as before.
    assert all(m["home_team"]["name"].startswith("ZZ Paging Team A") for m in detail["matches"])


# ── facets ───────────────────────────────────────────────────────────────────


def test_age_group_counts_are_exact_above_the_row_cap(facets):
    out = facets["dao"].get_tournament_filters(facets["tournament_id"])

    assert out["facets_available"] is True
    counts = {ag["id"]: ag["matches"] for ag in out["age_groups"]}
    assert counts == {facets["groups_age"]: GROUPS_AGE_TOTAL, facets["showcase_age"]: SHOWCASE_AGE_TOTAL}
    assert all(ag["name"] for ag in out["age_groups"])
    assert all(ag["matches_on_date"] is None for ag in out["age_groups"])


def test_groups_are_namespaced_by_division(facets):
    out = facets["dao"].get_tournament_filters(facets["tournament_id"], age_group_id=facets["groups_age"])

    groups = {g["key"]: g for g in out["groups"]}
    # Stage labels on other rounds ("HD · Group Play") are not groups.
    assert set(groups) == {"HD · A", "AD · A", "HD · B"}
    assert groups["HD · A"] == {"key": "HD · A", "division": "HD", "label": "A", "matches": HD_A}
    assert groups["AD · A"] == {"key": "AD · A", "division": "AD", "label": "A", "matches": AD_A}
    assert groups["HD · B"]["matches"] == FILLER


def test_a_showcase_only_age_group_has_no_groups(facets):
    out = facets["dao"].get_tournament_filters(facets["tournament_id"], age_group_id=facets["showcase_age"])

    assert out["groups"] == []
    assert out["facets_available"] is True


def test_facets_respect_the_test_partition(facets):
    dao, tid, age = facets["dao"], facets["tournament_id"], facets["groups_age"]

    hidden = dao.get_tournament_filters(tid, age_group_id=age)
    shown = dao.get_tournament_filters(tid, age_group_id=age, include_test=True)

    def hd_a(out):
        return next(g["matches"] for g in out["groups"] if g["key"] == "HD · A")

    assert hd_a(hidden) == HD_A
    assert hd_a(shown) == HD_A + TEST_FIXTURES


def test_matches_on_a_day_are_counted_per_age_group(facets):
    dao, tid = facets["dao"], facets["tournament_id"]
    day = SEED_DAY.isoformat()

    out = dao.get_tournament_filters(tid, on_date=day)

    for age_group in out["age_groups"]:
        expected = dao.get_tournament_matches(tid, age_group_id=age_group["id"], limit=500)
        on_day = sum(1 for m in expected["matches"] if m["match_date"] == day)
        if expected["total"] <= 500:
            assert age_group["matches_on_date"] == on_day
        else:
            assert age_group["matches_on_date"] >= on_day


def test_a_tournament_with_no_matches_has_empty_facets(facets):
    out = facets["dao"].get_tournament_filters(-1)

    assert out == {"facets_available": True, "age_groups": [], "groups": []}


def test_filters_degrade_when_the_function_is_missing(fest):
    if _facets_installed(fest["admin"]):
        pytest.skip("tournament_filter_facets is installed - the degraded path is covered by the unit tests")

    out = fest["dao"].get_tournament_filters(fest["tournament_id"], age_group_id=fest["groups_age"])

    # Unknown, not zero: no counts and no claim about groups.
    assert out["facets_available"] is False
    assert out["groups"] is None
    assert all(ag["matches"] is None for ag in out["age_groups"])
    # The match list does not depend on it.
    assert fest["dao"].get_tournament_matches(fest["tournament_id"], limit=1)["total"] == REAL_TOTAL

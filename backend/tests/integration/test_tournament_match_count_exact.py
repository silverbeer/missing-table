"""A tournament's match_count is exact above PostgREST's 1,000-row cap (SB-1752).

Counting the rows of one select under-reported any tournament with more than
1,000 matches. This seeds 1,005 real rows and asks the DAO for the count.

Requires local Supabase. Skips cleanly if unreachable or not local.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]

ROWS = 1005  # past the 1,000-row response cap


def _admin_client():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:55321")
    if not ("127.0.0.1" in url or "localhost" in url):
        pytest.skip(f"Refusing to run destructive test against non-local Supabase: {url}")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY not set - cannot run tournament count test")
    return create_client(url, key)


def _first_id(admin, table: str) -> int:
    rows = admin.table(table).select("id").order("id").limit(1).execute().data
    if not rows:
        pytest.skip(f"No reference rows in {table}; seed the local DB first")
    return rows[0]["id"]


@pytest.fixture
def big_tournament():
    admin = _admin_client()
    try:
        admin.table("tournaments").select("id").limit(1).execute()
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("Local Supabase not reachable")

    season_id = _first_id(admin, "seasons")
    age_group_id = _first_id(admin, "age_groups")
    match_type_id = _first_id(admin, "match_types")
    tag = uuid.uuid4().hex[:8]

    club_ids: list[int] = []
    team_ids: list[int] = []
    tournament_id = None
    try:
        for label in ("A", "B"):
            club = (
                admin.table("clubs")
                .insert({"name": f"ZZ Count Club {label} {tag}", "is_test": False})
                .execute()
                .data[0]
            )
            club_ids.append(club["id"])
            team = (
                admin.table("teams")
                .insert({"name": f"ZZ Count Team {label} {tag}", "club_id": club["id"]})
                .execute()
                .data[0]
            )
            team_ids.append(team["id"])

        tournament_id = (
            admin.table("tournaments")
            .insert(
                {
                    "name": f"ZZ Count Cup {tag}",
                    "start_date": "2026-01-01",
                    "season_id": season_id,
                    "is_active": True,
                    "is_test": False,
                }
            )
            .execute()
            .data[0]["id"]
        )
        base = date(2020, 1, 1)
        rows = [
            {
                "match_date": (base + timedelta(days=i)).isoformat(),
                "home_team_id": team_ids[0],
                "away_team_id": team_ids[1],
                "season_id": season_id,
                "age_group_id": age_group_id,
                "match_type_id": match_type_id,
                "tournament_id": tournament_id,
                "match_status": "scheduled",
            }
            for i in range(ROWS)
        ]
        admin.table("matches").insert(rows).execute()
        yield admin, tournament_id
    finally:
        # Each step runs even if an earlier one failed, so one bad delete does
        # not strand the rest of the "ZZ Count" rows; failures are raised after.
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
            raise RuntimeError("big_tournament cleanup left rows behind: " + "; ".join(failures))


def test_match_count_is_exact_above_the_row_cap(big_tournament):
    from dao.tournament_dao import TournamentDAO

    admin, tournament_id = big_tournament
    dao = TournamentDAO.__new__(TournamentDAO)
    dao.connection_holder = MagicMock()
    dao.client = admin

    out = dao._attach_match_counts([{"id": tournament_id}])

    assert out[0]["match_count"] == ROWS

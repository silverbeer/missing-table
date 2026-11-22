"""Match of the Day slots against the real table (SB-1750).

The unique (tournament_id, match_date, age_group_id) is what lets two age
groups hold a pick on the same day; the unit tests mock the table and cannot
see it. Needs local Supabase with the SB-1750 migration applied, and skips
cleanly otherwise.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from dao.base_dao import clear_cache
from dao.match_dao import SupabaseConnection
from dao.motd_dao import TABLE, MotdDAO

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]


def _local(url: str | None) -> bool:
    return bool(url) and ("127.0.0.1" in url or "localhost" in url)


@pytest.fixture
def world():
    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:55321")
    if not _local(url):
        pytest.skip(f"Refusing to run against non-local Supabase: {url}")
    conn = SupabaseConnection()
    # SupabaseConnection loads the environment itself; check what it resolved to.
    if not _local(conn.url):
        pytest.skip(f"Refusing to run against non-local Supabase: {conn.url}")
    client = conn.get_client()
    try:
        client.table(TABLE).select("age_group_id").limit(1).execute()
    except Exception:
        pytest.skip(f"{TABLE}.age_group_id missing: apply the SB-1750 migration")

    def _ids(table: str, count: int) -> list[int]:
        rows = client.table(table).select("id").order("id").limit(count).execute().data
        if len(rows) < count:
            pytest.skip(f"Need {count} rows in {table}; seed the local DB first")
        return [r["id"] for r in rows]

    season_id = _ids("seasons", 1)[0]
    match_type_id = _ids("match_types", 1)[0]
    age_a, age_b = _ids("age_groups", 2)

    created: dict[str, list[int]] = {"matches": [], "teams": [], "clubs": [], "tournaments": []}

    def _mk(table: str, payload: dict) -> dict:
        row = client.table(table).insert(payload).execute().data[0]
        created[table].append(row["id"])
        return row

    tag = uuid.uuid4().hex[:8]
    day = (datetime.now(UTC).date() + timedelta(days=30)).isoformat()
    try:
        tournament = _mk("tournaments", {"name": f"ZZ Motd Cup {tag}", "start_date": day})
        club_a = _mk("clubs", {"name": f"ZZ Motd Club A {tag}"})
        club_b = _mk("clubs", {"name": f"ZZ Motd Club B {tag}"})
        home = _mk("teams", {"name": f"ZZ Motd Home {tag}", "club_id": club_a["id"]})
        away = _mk("teams", {"name": f"ZZ Motd Away {tag}", "club_id": club_b["id"]})

        def _match(age_group_id: int) -> int:
            return _mk(
                "matches",
                {
                    "match_date": day,
                    "home_team_id": home["id"],
                    "away_team_id": away["id"],
                    "season_id": season_id,
                    "age_group_id": age_group_id,
                    "match_type_id": match_type_id,
                    "tournament_id": tournament["id"],
                    "match_status": "scheduled",
                },
            )["id"]

        matches = {"a": _match(age_a), "a_other": _match(age_a), "b": _match(age_b)}
        # Raw inserts bypass the DAOs' invalidates_cache.
        clear_cache("mt:dao:matches:*")

        yield {
            "dao": MotdDAO(conn),
            "tournament": tournament["id"],
            "day": day,
            "age_a": age_a,
            "age_b": age_b,
            **matches,
        }
    finally:
        # Children first; the picks cascade away with their tournament.
        for table in ("matches", "teams", "clubs", "tournaments"):
            for row_id in created[table]:
                try:
                    client.table(table).delete().eq("id", row_id).execute()
                except Exception:  # pragma: no cover
                    pass
        clear_cache("mt:dao:matches:*")


def test_two_age_groups_hold_a_pick_on_the_same_day(world):
    dao, fest, day = world["dao"], world["tournament"], world["day"]
    dao.set_for_match(fest, world["a"], blurb="first age group")
    dao.set_for_match(fest, world["b"], blurb="second age group")

    picks = dao.list_for_day(fest, day, include_test=True)
    assert {p["age_group_id"]: p["match"]["id"] for p in picks} == {
        world["age_a"]: world["a"],
        world["age_b"]: world["b"],
    }
    assert dao.get_for_day(fest, day, age_group_id=world["age_b"], include_test=True)["blurb"] == "second age group"


def test_repicking_one_age_group_replaces_only_that_slot(world):
    dao, fest, day = world["dao"], world["tournament"], world["day"]
    dao.set_for_match(fest, world["a"])
    dao.set_for_match(fest, world["b"])
    dao.set_for_match(fest, world["a_other"])

    picks = dao.list_for_day(fest, day, include_test=True)
    assert {p["age_group_id"]: p["match"]["id"] for p in picks} == {
        world["age_a"]: world["a_other"],
        world["age_b"]: world["b"],
    }


def test_clearing_one_age_group_leaves_the_other(world):
    dao, fest, day = world["dao"], world["tournament"], world["day"]
    dao.set_for_match(fest, world["a"])
    dao.set_for_match(fest, world["b"])

    assert dao.clear_day(fest, day, age_group_id=world["age_a"]) == 1
    assert dao.get_for_day(fest, day, age_group_id=world["age_a"], include_test=True) is None
    assert dao.get_for_day(fest, day, age_group_id=world["age_b"], include_test=True)["match"]["id"] == world["b"]

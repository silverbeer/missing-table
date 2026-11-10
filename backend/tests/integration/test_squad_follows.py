"""Squad follows against the real local database (SB-1608).

A follow row with age_group_id NULL follows every age group of the team; a row
with a value follows that squad only. These tests prove the unique constraint,
set_club_squads' replace semantics and the fan-out filter on real rows.

Requires local Supabase. Skips if it is not reachable or not local.
"""

from __future__ import annotations

import os
import uuid

import pytest

from dao.match_dao import SupabaseConnection
from dao.team_follow_dao import TeamFollowDAO

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]

_TEST_PASSWORD = "test-password-123"  # pragma: allowlist secret


def _admin_client():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:55321")
    if not ("127.0.0.1" in url or "localhost" in url):
        pytest.skip(f"Refusing to run destructive test against non-local Supabase: {url}")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY not set")
    return create_client(url, key)


@pytest.fixture
def world():
    admin = _admin_client()
    try:
        ages = admin.table("age_groups").select("id").order("id").limit(2).execute().data
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("Local Supabase not reachable")
    if len(ages) < 2:
        pytest.skip("Need two age groups")
    young, old = ages[0]["id"], ages[1]["id"]

    email = f"sb1608-{uuid.uuid4().hex[:8]}@missingtable.local"
    user_id = admin.auth.admin.create_user({"email": email, "password": _TEST_PASSWORD, "email_confirm": True}).user.id
    admin.table("user_profiles").upsert({"id": user_id, "email": email, "role": "club-fan"}).execute()
    club = admin.table("clubs").insert({"name": f"SquadClub-{uuid.uuid4().hex[:8]}"}).execute().data[0]
    other_club = admin.table("clubs").insert({"name": f"OtherClub-{uuid.uuid4().hex[:8]}"}).execute().data[0]
    team = (
        admin.table("teams").insert({"name": f"Squads-{uuid.uuid4().hex[:8]}", "club_id": club["id"]}).execute().data[0]
    )
    other = (
        admin.table("teams")
        .insert({"name": f"Other-{uuid.uuid4().hex[:8]}", "club_id": other_club["id"]})
        .execute()
        .data[0]
    )

    # The other club's team plays only the older age group.
    admin.table("team_mappings").insert({"team_id": other["id"], "age_group_id": old}).execute()

    yield {
        "admin": admin,
        "dao": TeamFollowDAO(SupabaseConnection()),
        "user_id": user_id,
        "team": team["id"],
        "other": other["id"],
        "young": young,
        "old": old,
    }

    def _safe(fn):
        try:
            fn()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass

    _safe(lambda: admin.table("user_team_follows").delete().eq("user_id", user_id).execute())
    _safe(lambda: admin.table("team_mappings").delete().eq("team_id", other["id"]).execute())
    _safe(lambda: admin.table("teams").delete().in_("id", [team["id"], other["id"]]).execute())
    _safe(lambda: admin.table("clubs").delete().in_("id", [club["id"], other_club["id"]]).execute())
    _safe(lambda: admin.table("user_profiles").delete().eq("id", user_id).execute())
    _safe(lambda: admin.auth.admin.delete_user(user_id))


def _rows(w) -> set[tuple[int, int | None]]:
    data = w["admin"].table("user_team_follows").select("team_id, age_group_id").eq("user_id", w["user_id"]).execute()
    return {(r["team_id"], r["age_group_id"]) for r in data.data}


class TestSquadFollows:
    def test_whole_team_follow_is_idempotent(self, world):
        dao = world["dao"]
        assert dao.follow(world["user_id"], world["team"])
        assert dao.follow(world["user_id"], world["team"])
        assert _rows(world) == {(world["team"], None)}

    def test_set_club_squads_replaces_a_whole_team_follow(self, world):
        dao, uid, team, young = world["dao"], world["user_id"], world["team"], world["young"]
        dao.follow(uid, team)
        assert dao.set_club_squads(uid, {team}, {(team, young)})
        assert _rows(world) == {(team, young)}

    def test_set_club_squads_leaves_other_clubs_alone(self, world):
        dao, uid, team, other = world["dao"], world["user_id"], world["team"], world["other"]
        young, old = world["young"], world["old"]
        dao.follow(uid, other)
        assert dao.set_club_squads(uid, {team}, {(team, young), (team, old)})
        assert dao.set_club_squads(uid, {team}, {(team, old)})
        assert _rows(world) == {(other, None), (team, old)}
        assert dao.set_club_squads(uid, {team}, set())
        assert _rows(world) == {(other, None)}

    def test_list_for_user_names_the_age_group(self, world):
        dao, uid, team, young = world["dao"], world["user_id"], world["team"], world["young"]
        dao.set_club_squads(uid, {team}, {(team, young)})
        (row,) = dao.list_for_user(uid)
        assert row["age_group_id"] == young
        assert row["age_group"]["id"] == young

    def test_fanout_honors_the_squad(self, world):
        dao, uid, team, young, old = world["dao"], world["user_id"], world["team"], world["young"], world["old"]
        dao.set_club_squads(uid, {team}, {(team, young)})
        assert dao.list_user_ids_for_team_ids([team], young) == [uid]
        assert dao.list_user_ids_for_team_ids([team], old) == []
        assert dao.list_user_ids_for_team_ids([team], None) == []

    def test_whole_team_follow_hears_every_age(self, world):
        dao, uid, team = world["dao"], world["user_id"], world["team"]
        dao.follow(uid, team)
        assert dao.list_user_ids_for_team_ids([team], world["old"]) == [uid]
        assert dao.list_user_ids_for_team_ids([team], None) == [uid]

    def test_unfollow_one_squad_keeps_the_others(self, world):
        dao, uid, team, young, old = world["dao"], world["user_id"], world["team"], world["young"], world["old"]
        dao.set_club_squads(uid, {team}, {(team, young), (team, old)})
        assert dao.unfollow(uid, team, young)
        assert _rows(world) == {(team, old)}
        assert dao.unfollow(uid, team)
        assert _rows(world) == set()


class TestFollowAnySquad:
    """SB-1618: the Follow button follows the squad being viewed, any club."""

    def test_team_plays_age_group_reads_registrations(self, world):
        dao = world["dao"]
        assert dao.team_plays_age_group(world["other"], world["old"]) is True
        assert dao.team_plays_age_group(world["other"], world["young"]) is False

    def test_follow_squad_of_another_club_is_idempotent(self, world):
        dao, uid, other, old = world["dao"], world["user_id"], world["other"], world["old"]
        assert dao.follow_squad(uid, other, old)
        assert dao.follow_squad(uid, other, old)
        assert _rows(world) == {(other, old)}
        assert dao.list_user_ids_for_team_ids([other], old) == [uid]
        assert dao.list_user_ids_for_team_ids([other], world["young"]) == []

    def test_a_whole_team_follow_already_covers_the_squad(self, world):
        dao, uid, other, old = world["dao"], world["user_id"], world["other"], world["old"]
        dao.follow(uid, other)
        assert dao.follow_squad(uid, other, old)
        assert _rows(world) == {(other, None)}

    def test_club_squad_picker_leaves_other_club_squads_alone(self, world):
        dao, uid, team, other = world["dao"], world["user_id"], world["team"], world["other"]
        dao.follow_squad(uid, other, world["old"])
        dao.set_club_squads(uid, {team}, {(team, world["young"])})
        assert _rows(world) == {(other, world["old"]), (team, world["young"])}

"""API tests for scoped notification channels (SB-1602), against local Supabase.

The default fixture is a team with no channels: that is the normal state.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app import app
from auth import get_current_user_required
from dao.club_dao import ClubDAO
from dao.club_notifications_dao import ClubNotificationsDAO
from dao.match_dao import SupabaseConnection

pytestmark = [pytest.mark.integration, pytest.mark.api]

DISCORD = "https://discord.com/api/webhooks/123/abc"
BASE = "/api/notification-channels"


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def user(role: str, club_id: int | None = None, team_id: int | None = None) -> dict:
    return {"user_id": None, "role": role, "club_id": club_id, "team_id": team_id, "username": role}


ADMIN = user("admin")


@contextmanager
def as_user(current: dict):
    app.dependency_overrides[get_current_user_required] = lambda: current
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user_required, None)


@pytest.fixture
def conn():
    return SupabaseConnection()


@pytest.fixture
def world(conn):
    """A club with one team and no channels."""
    client = conn.get_client()
    club = ClubDAO(conn).create_club(name=_unique("ChanClub"), city="Boston")
    other = ClubDAO(conn).create_club(name=_unique("ChanOther"), city="NYC")
    team = client.table("teams").insert({"name": _unique("ChanTeam"), "city": "Boston", "club_id": club["id"]}).execute().data[0]
    ages = {r["name"]: r["id"] for r in client.table("age_groups").select("id,name").execute().data}
    yield {"club": club["id"], "other": other["id"], "team": team["id"], "ages": ages}
    client.table("notification_channels").delete().eq("team_id", team["id"]).execute()
    client.table("teams").delete().eq("id", team["id"]).execute()
    for club_id in (club["id"], other["id"]):
        ClubDAO(conn).delete_club(club_id)


def team_body(world, age="U15", audience="fans", destination=DISCORD, **extra):
    return {
        "scope_type": "team",
        "team_id": world["team"],
        "age_group_id": world["ages"][age],
        "audience": audience,
        "platform": "discord",
        "destination": destination,
        **extra,
    }


def club_body(world, **extra):
    return {"scope_type": "club", "club_id": world["club"], "platform": "discord", "destination": DISCORD, **extra}


class TestList:
    def test_no_channels_is_200_and_empty(self, world):
        with as_user(ADMIN) as c:
            r = c.get(BASE, params={"scope_type": "team", "team_id": world["team"], "age_group_id": world["ages"]["U15"]})
        assert r.status_code == 200
        assert r.json() == []

    def test_destination_is_never_returned(self, world):
        with as_user(ADMIN) as c:
            c.post(BASE, json=team_body(world))
            r = c.get(BASE, params={"scope_type": "team", "team_id": world["team"], "age_group_id": world["ages"]["U15"]})
        row = r.json()[0]
        assert "destination" not in row
        assert row["hint"] == "/abc"


class TestScopeRules:
    def test_team_channel_needs_an_age_group(self, world):
        body = team_body(world)
        del body["age_group_id"]
        with as_user(ADMIN) as c:
            assert c.post(BASE, json=body).status_code == 422

    def test_squads_are_separate(self, world):
        with as_user(ADMIN) as c:
            assert c.post(BASE, json=team_body(world, age="U15")).status_code == 201
            r = c.get(BASE, params={"scope_type": "team", "team_id": world["team"], "age_group_id": world["ages"]["U16"]})
        assert r.json() == []

    def test_several_channels_per_scope_and_platform(self, world):
        with as_user(ADMIN) as c:
            assert c.post(BASE, json=team_body(world)).status_code == 201
            second = team_body(world, destination="https://discord.com/api/webhooks/456/def")
            assert c.post(BASE, json=second).status_code == 201

    def test_exact_duplicate_is_409_without_the_destination(self, world):
        with as_user(ADMIN) as c:
            c.post(BASE, json=team_body(world))
            r = c.post(BASE, json=team_body(world))
        assert r.status_code == 409
        assert "webhooks" not in r.text


class TestPermissions:
    @pytest.mark.parametrize("role", ["team-fan", "team-player", "club-fan"])
    def test_members_cannot_create(self, world, role):
        with as_user(user(role, club_id=world["club"], team_id=world["team"])) as c:
            assert c.post(BASE, json=team_body(world)).status_code == 403

    def test_team_manager_of_the_team(self, world):
        with as_user(user("team-manager", team_id=world["team"])) as c:
            assert c.post(BASE, json=team_body(world)).status_code == 201

    def test_team_manager_of_another_team(self, world):
        with as_user(user("team-manager", team_id=world["team"] + 999999)) as c:
            assert c.post(BASE, json=team_body(world)).status_code == 403

    def test_team_manager_cannot_create_a_club_channel(self, world):
        with as_user(user("team-manager", team_id=world["team"])) as c:
            assert c.post(BASE, json=club_body(world)).status_code == 403

    def test_club_manager_of_the_club_can_manage_its_team(self, world):
        with as_user(user("club_manager", club_id=world["club"])) as c:
            assert c.post(BASE, json=team_body(world)).status_code == 201

    def test_club_manager_of_another_club(self, world):
        with as_user(user("club_manager", club_id=world["other"])) as c:
            assert c.post(BASE, json=team_body(world)).status_code == 403
            assert c.post(BASE, json=club_body(world)).status_code == 403

    def test_global_is_admin_only(self, world):
        body = {"scope_type": "global", "platform": "discord", "destination": DISCORD}
        with as_user(user("club_manager", club_id=world["club"])) as c:
            assert c.post(BASE, json=body).status_code == 403

    def test_cannot_edit_another_clubs_channel(self, world):
        with as_user(ADMIN) as c:
            channel_id = c.post(BASE, json=team_body(world)).json()["id"]
        with as_user(user("club_manager", club_id=world["other"])) as c:
            assert c.patch(f"{BASE}/{channel_id}", json={"enabled": False}).status_code == 403
            assert c.delete(f"{BASE}/{channel_id}").status_code == 403


class TestPlayerChannels:
    def test_discord_u14_allowed(self, world):
        with as_user(ADMIN) as c:
            assert c.post(BASE, json=team_body(world, age="U14", audience="players")).status_code == 201

    def test_u13_refused(self, world):
        with as_user(ADMIN) as c:
            assert c.post(BASE, json=team_body(world, age="U13", audience="players")).status_code == 422

    def test_telegram_refused(self, world):
        body = team_body(world, audience="players", platform="telegram", destination="-100123")
        with as_user(ADMIN) as c:
            assert c.post(BASE, json=body).status_code == 422

    def test_club_players_on_discord(self, world):
        with as_user(user("club_manager", club_id=world["club"])) as c:
            assert c.post(BASE, json=club_body(world, audience="players")).status_code == 201

    def test_global_players_refused(self, world):
        body = {"scope_type": "global", "audience": "players", "platform": "discord", "destination": DISCORD}
        with as_user(ADMIN) as c:
            assert c.post(BASE, json=body).status_code == 422


class TestUpdate:
    def test_event_types_null_and_empty_stay_distinct(self, world):
        with as_user(ADMIN) as c:
            channel_id = c.post(BASE, json=team_body(world)).json()["id"]
            assert c.patch(f"{BASE}/{channel_id}", json={"event_types": []}).json()["event_types"] == []
            assert c.patch(f"{BASE}/{channel_id}", json={"event_types": None}).json()["event_types"] is None

    def test_unset_fields_are_left_alone(self, world):
        with as_user(ADMIN) as c:
            channel_id = c.post(BASE, json=team_body(world, event_types=["goal"])).json()["id"]
            assert c.patch(f"{BASE}/{channel_id}", json={"enabled": False}).json()["event_types"] == ["goal"]

    def test_unknown_event_rejected(self, world):
        with as_user(ADMIN) as c:
            assert c.post(BASE, json=team_body(world, event_types=["corner"])).status_code == 422

    def test_bad_destination_rejected(self, world):
        with as_user(ADMIN) as c:
            channel_id = c.post(BASE, json=team_body(world)).json()["id"]
            assert c.patch(f"{BASE}/{channel_id}", json={"destination": "https://evil.test/x"}).status_code == 422

    def test_missing_channel_is_404(self):
        with as_user(ADMIN) as c:
            assert c.delete(f"{BASE}/99999999").status_code == 404


class TestOriginalClubEndpoints:
    def test_they_read_and_write_the_same_rows(self, world, conn):
        with as_user(ADMIN) as c:
            assert c.put(f"/api/clubs/{world['club']}/notifications/discord", json={"destination": DISCORD}).status_code == 200
            scoped = c.get(BASE, params={"scope_type": "club", "club_id": world["club"]}).json()
        assert len(scoped) == 1
        assert scoped[0]["audience"] == "fans"

    def test_club_player_channels_stay_out_of_them(self, world, conn):
        with as_user(ADMIN) as c:
            c.post(BASE, json=club_body(world, audience="players"))
        assert ClubNotificationsDAO(conn).list_by_club(world["club"]) == []


class TestListForMatch:
    def _channel(self, conn, **fields):
        return (
            conn.get_client()
            .table("notification_channels")
            .insert({"platform": "discord", "destination": f"d-{uuid.uuid4().hex}", **fields})
            .execute()
            .data[0]["id"]
        )

    def test_finds_club_squad_and_global_but_not_another_squad(self, world, conn):
        u15, u16 = world["ages"]["U15"], world["ages"]["U16"]
        club = self._channel(conn, scope_type="club", club_id=world["club"])
        squad = self._channel(conn, scope_type="team", team_id=world["team"], age_group_id=u15)
        other_squad = self._channel(conn, scope_type="team", team_id=world["team"], age_group_id=u16)
        everyone = self._channel(conn, scope_type="global")
        try:
            rows = ClubNotificationsDAO(conn).list_for_match([world["club"]], [world["team"]], u15)
            ids = [row["id"] for row in rows]
            assert club in ids
            assert squad in ids
            assert everyone in ids
            assert other_squad not in ids
        finally:
            conn.get_client().table("notification_channels").delete().eq("id", everyone).execute()

    def test_team_with_no_channels_finds_nothing(self, world, conn):
        rows = ClubNotificationsDAO(conn).list_for_match([], [world["team"]], world["ages"]["U15"])
        assert [row for row in rows if row["scope_type"] == "team"] == []

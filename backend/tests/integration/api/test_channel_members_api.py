"""Channel access API (SB-1607), against local Supabase.

Uses an existing local fan profile, because grants reference real profiles.
Covers the three states: a team with no channels, channels with no invite link,
and channels people can join.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app import app
from auth import get_current_user_required
from dao.match_dao import SupabaseConnection

pytestmark = [pytest.mark.integration, pytest.mark.api]

DISCORD = "https://discord.com/api/webhooks/123/abc"
INVITE = "https://discord.gg/abc123XY"


@contextmanager
def as_user(current: dict):
    app.dependency_overrides[get_current_user_required] = lambda: current
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user_required, None)


@pytest.fixture
def world():
    """A new team in a local fan's club, with no channels."""
    client = SupabaseConnection().get_client()
    fans = (
        client.table("user_profiles")
        .select("id, role, club_id")
        .in_("role", ["team-fan", "club-fan", "team_fan", "club_fan"])
        .not_.is_("club_id", "null")
        .limit(1)
        .execute()
        .data
    )
    if not fans:
        pytest.skip("No local fan profile with a club")
    fan = fans[0]
    team = (
        client.table("teams")
        .insert({"name": f"ChanAccess-{uuid.uuid4().hex[:8]}", "city": "Boston", "club_id": fan["club_id"]})
        .execute()
        .data[0]
    )
    ages = {r["name"]: r["id"] for r in client.table("age_groups").select("id,name").execute().data}
    created: list[int] = []

    def channel(scope="team", audience="fans", invite_url=INVITE):
        row = {"platform": "discord", "destination": f"{DISCORD}{uuid.uuid4().hex}", "audience": audience}
        if scope == "team":
            row |= {"scope_type": "team", "team_id": team["id"], "age_group_id": ages["U15"]}
        else:
            row |= {"scope_type": "club", "club_id": fan["club_id"]}
        if invite_url:
            row["invite_url"] = invite_url
        cid = client.table("notification_channels").insert(row).execute().data[0]["id"]
        created.append(cid)
        return cid

    yield {
        "team": team["id"],
        "channel": channel,
        "fan": {"user_id": fan["id"], "role": fan["role"], "club_id": fan["club_id"], "team_id": None},
        "manager": {"user_id": None, "role": "team-manager", "club_id": None, "team_id": team["id"]},
    }
    for cid in created:
        client.table("notification_channels").delete().eq("id", cid).execute()
    client.table("teams").delete().eq("id", team["id"]).execute()


@pytest.fixture
def isolated(world):
    """Like `world`, but in a club of its own, so parallel tests cannot add channels to it.

    Only for tests that never need the fan's stored profile (no manager decisions).
    """
    from dao.club_dao import ClubDAO

    conn = SupabaseConnection()
    client = conn.get_client()
    club = ClubDAO(conn).create_club(name=f"ChanIso-{uuid.uuid4().hex[:8]}", city="Boston")
    team = (
        client.table("teams")
        .insert({"name": f"ChanIso-{uuid.uuid4().hex[:8]}", "city": "Boston", "club_id": club["id"]})
        .execute()
        .data[0]
    )
    u15 = client.table("age_groups").select("id").eq("name", "U15").execute().data[0]["id"]
    created: list[int] = []

    def channel(scope="team", audience="fans", invite_url=INVITE):
        row = {"platform": "discord", "destination": f"{DISCORD}{uuid.uuid4().hex}", "audience": audience}
        if scope == "team":
            row |= {"scope_type": "team", "team_id": team["id"], "age_group_id": u15}
        else:
            row |= {"scope_type": "club", "club_id": club["id"]}
        if invite_url:
            row["invite_url"] = invite_url
        cid = client.table("notification_channels").insert(row).execute().data[0]["id"]
        created.append(cid)
        return cid

    yield {"team": team["id"], "channel": channel, "fan": {**world["fan"], "club_id": club["id"]}}
    for cid in created:
        client.table("notification_channels").delete().eq("id", cid).execute()
    client.table("teams").delete().eq("id", team["id"]).execute()
    ClubDAO(conn).delete_club(club["id"])


def available(w, who="fan"):
    with as_user(w[who]) as c:
        r = c.get(f"/api/teams/{w['team']}/channels/available")
    assert r.status_code == 200
    return {ch["id"]: ch for ch in r.json()}


class TestStates:
    def test_team_with_no_channels_is_empty(self, isolated):
        assert available(isolated) == {}

    def test_unknown_team_is_empty(self, isolated):
        with as_user(isolated["fan"]) as c:
            r = c.get("/api/teams/999999999/channels/available")
        assert (r.status_code, r.json()) == (200, [])

    def test_channels_without_an_invite_link_are_not_listed(self, isolated):
        isolated["channel"](invite_url=None)
        assert available(isolated) == {}

    def test_populated(self, isolated):
        club = isolated["channel"]("club")
        squad = isolated["channel"]()
        players = isolated["channel"](audience="players")
        seen = available(isolated)
        assert seen[club]["state"] == "can_join"
        assert seen[squad]["state"] == "can_request"
        assert players not in seen
        assert all(ch["invite_url"] is None for ch in seen.values())
        assert all("destination" not in ch for ch in seen.values())


class TestFanCannotReachPlayerChannel:
    def test_join_and_request_are_404(self, world):
        players = world["channel"](audience="players")
        with as_user(world["fan"]) as c:
            assert c.post(f"/api/channels/{players}/join").status_code == 404
            assert c.post(f"/api/channels/{players}/request").status_code == 404

    def test_manager_cannot_invite_a_fan(self, world):
        players = world["channel"](audience="players")
        with as_user(world["manager"]) as c:
            r = c.put(f"/api/channels/{players}/members/{world['fan']['user_id']}", json={"status": "active"})
        assert r.status_code == 422


class TestJoin:
    def test_join_club_channel_reveals_link(self, world):
        club = world["channel"]("club")
        with as_user(world["fan"]) as c:
            r = c.post(f"/api/channels/{club}/join")
        assert r.status_code == 200
        assert r.json()["invite_url"] == INVITE
        assert available(world)[club]["state"] == "member"

    def test_squad_channel_cannot_be_joined_directly(self, world):
        squad = world["channel"]()
        with as_user(world["fan"]) as c:
            assert c.post(f"/api/channels/{squad}/join").status_code == 409


class TestRequestFlow:
    def test_request_review_approve(self, world):
        squad = world["channel"]()
        fan_id = world["fan"]["user_id"]
        with as_user(world["fan"]) as c:
            assert c.post(f"/api/channels/{squad}/request").json()["state"] == "requested"
        with as_user(world["manager"]) as c:
            pending = c.get("/api/channels/requests", params={"team_id": world["team"]}).json()
            assert [(p["channel_id"], p["user_id"]) for p in pending] == [(squad, fan_id)]
            r = c.put(f"/api/channels/{squad}/members/{fan_id}", json={"status": "active"})
            assert (r.status_code, r.json()["source"]) == (200, "request")
        assert available(world)[squad]["invite_url"] == INVITE

    def test_denied_cannot_request_again(self, world):
        squad = world["channel"]()
        fan_id = world["fan"]["user_id"]
        with as_user(world["fan"]) as c:
            c.post(f"/api/channels/{squad}/request")
        with as_user(world["manager"]) as c:
            assert c.put(f"/api/channels/{squad}/members/{fan_id}", json={"status": "denied"}).status_code == 200
        with as_user(world["fan"]) as c:
            assert c.post(f"/api/channels/{squad}/request").status_code == 409
        assert available(world)[squad]["state"] == "denied"

    def test_withdraw(self, world):
        squad = world["channel"]()
        with as_user(world["fan"]) as c:
            c.post(f"/api/channels/{squad}/request")
            assert c.delete(f"/api/channels/{squad}/request").status_code == 204
        assert available(world)[squad]["state"] == "can_request"

    def test_manager_invite_and_revoke(self, world):
        squad = world["channel"]()
        fan_id = world["fan"]["user_id"]
        with as_user(world["manager"]) as c:
            r = c.put(f"/api/channels/{squad}/members/{fan_id}", json={"status": "active"})
            assert r.json()["source"] == "invite"
            assert c.put(f"/api/channels/{squad}/members/{fan_id}", json={"status": "revoked"}).status_code == 200
        assert available(world)[squad]["invite_url"] is None

    def test_a_fan_cannot_review(self, world):
        world["channel"]()
        with as_user(world["fan"]) as c:
            assert c.get("/api/channels/requests", params={"team_id": world["team"]}).status_code == 403


def test_channel_api_rejects_a_public_invite_link(world):
    world["channel"]()
    admin = {"user_id": None, "role": "admin", "club_id": None, "team_id": None}
    body = {
        "scope_type": "team",
        "team_id": world["team"],
        "age_group_id": SupabaseConnection().get_client().table("age_groups").select("id").eq("name", "U16").execute().data[0]["id"],
        "platform": "telegram",
        "destination": "-1001234567890",
        "invite_url": "https://t.me/publicchannel",
    }
    with as_user(admin) as c:
        assert c.post("/api/notification-channels", json=body).status_code == 422


class TestMyChannels:
    """The profile card's endpoint (SB-1609)."""

    def test_no_team_or_club(self, world):
        nobody = {**world["fan"], "club_id": None, "team_id": None}
        with as_user(nobody) as c:
            body = c.get("/api/me/channels").json()
        assert body == {"channels": [], "has_team": False, "managed": None, "can_manage": False}

    def test_club_only_fan_sees_club_channel(self, world):
        club = world["channel"]("club")
        with as_user(world["fan"]) as c:
            body = c.get("/api/me/channels").json()
        assert body["has_team"] is True
        assert [ch["id"] for ch in body["channels"] if ch["id"] == club] == [club]

    def test_unclaimed_team(self, world):
        from dao.club_dao import ClubDAO

        conn = SupabaseConnection()
        club = ClubDAO(conn).create_club(name=f"Unclaimed-{uuid.uuid4().hex[:8]}", city="Boston")
        client = conn.get_client()
        team = client.table("teams").insert({"name": f"U-{uuid.uuid4().hex[:8]}", "city": "Boston", "club_id": club["id"]}).execute().data[0]
        try:
            with as_user(world["fan"]) as c:
                body = c.get("/api/me/channels", params={"team_id": team["id"]}).json()
            assert body == {"channels": [], "has_team": True, "managed": False, "can_manage": False}
        finally:
            client.table("teams").delete().eq("id", team["id"]).execute()
            ClubDAO(conn).delete_club(club["id"])

    def test_team_manager_can_manage_their_team(self, world):
        with as_user(world["manager"]) as c:
            body = c.get("/api/me/channels", params={"team_id": world["team"]}).json()
        assert body["can_manage"] is True

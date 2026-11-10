"""API tests for scoped notification channels (SB-1602), against local Supabase.

The default fixture is a team with no channels: that is the normal state.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from api import notification_channels as channels_api
from app import app
from auth import get_current_user_required
from dao.club_dao import ClubDAO
from dao.club_notifications_dao import ClubNotificationsDAO
from dao.match_dao import SupabaseConnection
from dao.notification_deliveries_dao import NotificationDeliveriesDAO
from notifications.adapters.base import DeliveryError, DeliveryResult, NotificationConfigError
from notifications.adapters.discord import DiscordAdapter
from notifications.preferences import CHANNEL_EVENT_TYPES

pytestmark = [pytest.mark.integration, pytest.mark.api]

DISCORD = "https://discord.com/api/webhooks/123/abc"
SLACK_HOOK = "https://hooks.slack.com/services/T000/B000/XXXX"
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
    team = (
        client.table("teams")
        .insert({"name": _unique("ChanTeam"), "city": "Boston", "club_id": club["id"]})
        .execute()
        .data[0]
    )
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
            r = c.get(
                BASE, params={"scope_type": "team", "team_id": world["team"], "age_group_id": world["ages"]["U15"]}
            )
        assert r.status_code == 200
        assert r.json() == []

    def test_destination_is_never_returned(self, world):
        with as_user(ADMIN) as c:
            c.post(BASE, json=team_body(world))
            r = c.get(
                BASE, params={"scope_type": "team", "team_id": world["team"], "age_group_id": world["ages"]["U15"]}
            )
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
            r = c.get(
                BASE, params={"scope_type": "team", "team_id": world["team"], "age_group_id": world["ages"]["U16"]}
            )
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

    def test_lineup_only_on_a_squad_player_channel(self, world):
        """SB-1610: a player-only event cannot be set where it would never be sent."""
        lineup = {"event_types": ["goal", "lineup"]}
        with as_user(ADMIN) as c:
            assert c.post(BASE, json=team_body(world, **lineup)).status_code == 422  # squad fans
            assert c.post(BASE, json=club_body(world, audience="players", **lineup)).status_code == 422
            ok = c.post(BASE, json=team_body(world, audience="players", **lineup))
            assert ok.status_code == 201, ok.text
            assert ok.json()["event_types"] == ["goal", "lineup"]

    def test_lineup_cannot_be_added_to_a_fan_channel_later(self, world):
        with as_user(ADMIN) as c:
            channel_id = c.post(BASE, json=team_body(world)).json()["id"]
            r = c.patch(f"{BASE}/{channel_id}", json={"event_types": ["lineup"]})
        assert r.status_code == 422
        assert "player channel" in r.json()["detail"]

    def test_match_threads_need_a_platform_with_threads(self, world):
        """SB-1606: Discord forum channels; club players rooms stay flat."""
        with as_user(ADMIN) as c:
            ok = c.post(BASE, json=team_body(world, post_as_threads=True))
            assert ok.status_code == 201, ok.text
            assert ok.json()["post_as_threads"] is True
            slack = team_body(world, age="U17", post_as_threads=True, platform="slack", destination=SLACK_HOOK)
            assert c.post(BASE, json=slack).status_code == 422
            assert c.post(BASE, json=club_body(world, audience="players", post_as_threads=True)).status_code == 422
            flat = c.post(BASE, json=club_body(world)).json()["id"]
            assert c.patch(f"{BASE}/{flat}", json={"post_as_threads": True}).json()["post_as_threads"] is True
            assert c.patch(f"{BASE}/{flat}", json={"post_as_threads": None}).status_code == 422

    def test_bad_destination_rejected(self, world):
        with as_user(ADMIN) as c:
            channel_id = c.post(BASE, json=team_body(world)).json()["id"]
            assert c.patch(f"{BASE}/{channel_id}", json={"destination": "https://evil.test/x"}).status_code == 422

    def test_missing_channel_is_404(self):
        with as_user(ADMIN) as c:
            assert c.delete(f"{BASE}/99999999").status_code == 404


class TestLabel:
    def test_label_is_trimmed_and_returned(self, world):
        with as_user(ADMIN) as c:
            r = c.post(BASE, json=club_body(world, label="  #ifa-live  "))
        assert r.status_code == 201
        assert r.json()["label"] == "#ifa-live"

    def test_blank_label_is_stored_as_none(self, world):
        with as_user(ADMIN) as c:
            channel = c.post(BASE, json=club_body(world, label="#a")).json()
            r = c.patch(f"{BASE}/{channel['id']}", json={"label": "   "})
        assert r.status_code == 200
        assert r.json()["label"] is None

    def test_no_label_is_none_not_empty(self, world):
        with as_user(ADMIN) as c:
            r = c.post(BASE, json=club_body(world))
        assert r.json()["label"] is None

    def test_too_long_label_rejected(self, world):
        with as_user(ADMIN) as c:
            r = c.post(BASE, json=club_body(world, label="x" * 81))
        assert r.status_code == 422


class TestLastDelivery:
    def _channel(self, world) -> int:
        with as_user(ADMIN) as c:
            return c.post(BASE, json=club_body(world)).json()["id"]

    def _list(self, world) -> list[dict]:
        with as_user(ADMIN) as c:
            return c.get(BASE, params={"scope_type": "club", "club_id": world["club"]}).json()

    def test_new_channel_has_posted_nothing(self, world):
        self._channel(world)
        [row] = self._list(world)
        assert row["last_delivery"] is None
        assert row["last_delivery_known"] is True

    def test_latest_delivery_wins(self, world, conn):
        channel_id = self._channel(world)
        ledger = NotificationDeliveriesDAO(conn)
        ledger.mark_sent(ledger.claim(channel_id, "match:1:kickoff"), "m1")
        ledger.mark_failed(ledger.claim(channel_id, "match:1:goal:2"), "discord send failed: HTTP 404")
        [row] = self._list(world)
        assert row["last_delivery"]["status"] == "failed"
        assert row["last_delivery"]["error"] == "discord send failed: HTTP 404"
        assert row["last_delivery"]["at"]

    def test_sent_carries_no_error(self, world, conn):
        channel_id = self._channel(world)
        ledger = NotificationDeliveriesDAO(conn)
        ledger.mark_sent(ledger.claim(channel_id, "match:1:kickoff"), None)
        [row] = self._list(world)
        assert row["last_delivery"] == {"status": "sent", "at": row["last_delivery"]["at"], "error": None}

    def test_unreadable_ledger_is_unknown_not_empty(self, world, monkeypatch):
        self._channel(world)
        monkeypatch.setattr(NotificationDeliveriesDAO, "latest_for", lambda self, ids: None)
        [row] = self._list(world)
        assert row["last_delivery"] is None
        assert row["last_delivery_known"] is False


class TestSendTest:
    @pytest.fixture(autouse=True)
    def _open_gates(self, monkeypatch):
        monkeypatch.setattr(channels_api, "is_notifications_enabled", lambda: True)
        monkeypatch.setattr(channels_api, "check_rate_limit", lambda key, max_per_minute: True)

    def _channel(self, world) -> int:
        with as_user(ADMIN) as c:
            return c.post(BASE, json=club_body(world)).json()["id"]

    def test_success(self, world, monkeypatch):
        sent = []
        monkeypatch.setattr(DiscordAdapter, "send", lambda self, dest, text: sent.append(dest))
        channel_id = self._channel(world)
        with as_user(ADMIN) as c:
            r = c.post(f"{BASE}/{channel_id}/test")
        assert r.json() == {"success": True, "error": None}
        assert sent == [DISCORD]

    def test_a_forum_channel_proves_follow_ups_find_the_thread(self, world, monkeypatch):
        """SB-1606: create a test post, then reply into it with the id that came back."""
        calls = []

        def threaded(self, dest, text, thread_ref, thread_name):
            calls.append((thread_ref, thread_name))
            return DeliveryResult(message_ref="m", thread_ref="777")

        monkeypatch.setattr(DiscordAdapter, "send_in_thread", threaded)
        with as_user(ADMIN) as c:
            channel_id = c.post(BASE, json=club_body(world, post_as_threads=True)).json()["id"]
            r = c.post(f"{BASE}/{channel_id}/test")
        assert r.json() == {"success": True, "error": None}
        assert calls == [(None, "Missing Table test"), ("777", None)]

    def test_a_forum_post_without_a_thread_id_is_reported(self, world, monkeypatch):
        monkeypatch.setattr(
            DiscordAdapter, "send_in_thread", lambda self, d, t, ref, name: DeliveryResult(message_ref="m")
        )
        with as_user(ADMIN) as c:
            channel_id = c.post(BASE, json=club_body(world, post_as_threads=True)).json()["id"]
            body = c.post(f"{BASE}/{channel_id}/test").json()
        assert body["success"] is False and "thread id" in body["error"]

    def test_delivery_error_is_shown(self, world, monkeypatch):
        def boom(self, dest, text):
            raise DeliveryError("discord send failed: HTTP 404")

        monkeypatch.setattr(DiscordAdapter, "send", boom)
        channel_id = self._channel(world)
        with as_user(ADMIN) as c:
            body = c.post(f"{BASE}/{channel_id}/test").json()
        assert body == {"success": False, "error": "discord send failed: HTTP 404"}

    def test_config_error_names_no_setting(self, world, monkeypatch):
        def boom(self, dest, text):
            raise NotificationConfigError("SOME_TOKEN is not set")

        monkeypatch.setattr(DiscordAdapter, "send", boom)
        channel_id = self._channel(world)
        with as_user(ADMIN) as c:
            body = c.post(f"{BASE}/{channel_id}/test").json()
        assert body["success"] is False
        assert "TOKEN" not in body["error"]

    def test_unexpected_error_leaks_nothing(self, world, monkeypatch):
        def boom(self, dest, text):
            raise RuntimeError(f"failed posting to {dest}")

        monkeypatch.setattr(DiscordAdapter, "send", boom)
        channel_id = self._channel(world)
        with as_user(ADMIN) as c:
            body = c.post(f"{BASE}/{channel_id}/test").json()
        assert DISCORD not in body["error"]

    def test_another_clubs_manager_is_refused(self, world):
        channel_id = self._channel(world)
        with as_user(user("club_manager", club_id=world["other"])) as c:
            assert c.post(f"{BASE}/{channel_id}/test").status_code == 403

    def test_missing_channel_is_404(self):
        with as_user(ADMIN) as c:
            assert c.post(f"{BASE}/999999999/test").status_code == 404

    def test_kill_switch_is_503(self, world, monkeypatch):
        channel_id = self._channel(world)
        monkeypatch.setattr(channels_api, "is_notifications_enabled", lambda: False)
        with as_user(ADMIN) as c:
            r = c.post(f"{BASE}/{channel_id}/test")
        assert r.status_code == 503
        assert "NOTIFICATIONS_ENABLED" not in r.text

    def test_rate_limited_is_429(self, world, monkeypatch):
        channel_id = self._channel(world)
        monkeypatch.setattr(channels_api, "check_rate_limit", lambda key, max_per_minute: False)
        with as_user(ADMIN) as c:
            assert c.post(f"{BASE}/{channel_id}/test").status_code == 429


class TestEventTypes:
    def test_lists_every_event_with_a_name(self):
        with as_user(user("team_manager")) as c:
            r = c.get(f"{BASE}/event-types")
        assert r.status_code == 200
        assert [e["id"] for e in r.json()] == list(CHANNEL_EVENT_TYPES)
        assert all(e["label"] for e in r.json())
        # Lineup is for a squad's player channel only (SB-1610).
        assert {e["id"] for e in r.json() if e["player_only"]} == {"lineup"}


class TestOriginalClubEndpoints:
    def test_they_read_and_write_the_same_rows(self, world, conn):
        with as_user(ADMIN) as c:
            assert (
                c.put(f"/api/clubs/{world['club']}/notifications/discord", json={"destination": DISCORD}).status_code
                == 200
            )
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

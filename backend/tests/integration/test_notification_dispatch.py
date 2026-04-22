"""Integration tests for the Phase 5 notification dispatcher.

Uses the real local Supabase to seed clubs + teams + matches + channels, but
mocks the outbound send function so no real Telegram/Discord calls are made.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import app
from auth import get_current_user_required
from dao.club_dao import ClubDAO
from dao.club_notifications_dao import ClubNotificationsDAO
from dao.match_dao import MatchDAO, SupabaseConnection
from dao.team_dao import TeamDAO
from notifications.dispatcher import Notifier, set_notifier
from notifications.tasks import notify_event_task

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]


# ---------------------------------------------------------------------------
# DB fixture scaffolding
# ---------------------------------------------------------------------------


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def conn():
    return SupabaseConnection()


@pytest.fixture
def club_dao(conn):
    return ClubDAO(conn)


@pytest.fixture
def team_dao(conn):
    return TeamDAO(conn)


@pytest.fixture
def match_dao(conn):
    return MatchDAO(conn)


@pytest.fixture
def notif_dao(conn):
    return ClubNotificationsDAO(conn)


@pytest.fixture
def two_clubs_with_teams_and_match(conn, club_dao):
    """Create 2 clubs + one team each + one match between them. Clean up after."""
    client = conn.get_client()

    home_club = club_dao.create_club(name=_unique("DispatchHome"), city="Boston")
    away_club = club_dao.create_club(name=_unique("DispatchAway"), city="Providence")

    def _fetch_ref(table: str) -> int:
        return client.table(table).select("id").limit(1).execute().data[0]["id"]

    age_group_id = _fetch_ref("age_groups")
    season_id = _fetch_ref("seasons")
    match_type_id = _fetch_ref("match_types")
    division_id = _fetch_ref("divisions")

    home_team = (
        client.table("teams")
        .insert(
            {
                "name": _unique("HomeTeam"),
                "city": "Boston",
                "club_id": home_club["id"],
            }
        )
        .execute()
        .data[0]
    )
    away_team = (
        client.table("teams")
        .insert(
            {
                "name": _unique("AwayTeam"),
                "city": "Providence",
                "club_id": away_club["id"],
            }
        )
        .execute()
        .data[0]
    )

    match = (
        client.table("matches")
        .insert(
            {
                "home_team_id": home_team["id"],
                "away_team_id": away_team["id"],
                "age_group_id": age_group_id,
                "season_id": season_id,
                "match_type_id": match_type_id,
                "division_id": division_id,
                "match_date": datetime.now(UTC).date().isoformat(),
                "scheduled_kickoff": (
                    datetime.now(UTC) + timedelta(hours=1)
                ).isoformat(),
                "home_score": 0,
                "away_score": 0,
                "match_status": "scheduled",
            }
        )
        .execute()
        .data[0]
    )

    try:
        yield {
            "home_club": home_club,
            "away_club": away_club,
            "home_team": home_team,
            "away_team": away_team,
            "match": match,
        }
    finally:
        # Delete in reverse dependency order.
        try:
            client.table("matches").delete().eq("id", match["id"]).execute()
        except Exception:
            pass
        for team in (home_team, away_team):
            try:
                client.table("teams").delete().eq("id", team["id"]).execute()
            except Exception:
                pass
        for club in (home_club, away_club):
            try:
                club_dao.delete_club(club["id"])
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Dispatcher — direct (no HTTP)
# ---------------------------------------------------------------------------


class TestNotifierDirectInvocation:
    def test_kickoff_dispatches_to_home_and_away_channels(
        self, conn, two_clubs_with_teams_and_match, notif_dao
    ):
        ctx = two_clubs_with_teams_and_match
        notif_dao.upsert(ctx["home_club"]["id"], "telegram", "-100home")
        notif_dao.upsert(ctx["away_club"]["id"], "discord", "https://discord.com/api/webhooks/1/away")

        send_fn = Mock()
        notifier = Notifier(connection=conn, send_fn=send_fn)

        notifier.notify("kickoff", ctx["match"]["id"])

        assert send_fn.call_count == 2
        platforms = sorted(call.args[0] for call in send_fn.call_args_list)
        destinations = sorted(call.args[1] for call in send_fn.call_args_list)
        assert platforms == ["discord", "telegram"]
        assert "-100home" in destinations
        # Message is the same for both
        messages = {call.args[2] for call in send_fn.call_args_list}
        assert len(messages) == 1
        assert "KICKOFF" in next(iter(messages))

    def test_skips_cleanly_when_no_channels_configured(
        self, conn, two_clubs_with_teams_and_match
    ):
        send_fn = Mock()
        notifier = Notifier(connection=conn, send_fn=send_fn)

        notifier.notify("kickoff", two_clubs_with_teams_and_match["match"]["id"])

        send_fn.assert_not_called()

    def test_kill_switch_short_circuits(
        self, conn, two_clubs_with_teams_and_match, notif_dao, monkeypatch
    ):
        ctx = two_clubs_with_teams_and_match
        notif_dao.upsert(ctx["home_club"]["id"], "telegram", "-100home")
        send_fn = Mock()
        notifier = Notifier(connection=conn, send_fn=send_fn)

        monkeypatch.setenv("NOTIFICATIONS_ENABLED", "false")
        notifier.notify("kickoff", ctx["match"]["id"])

        send_fn.assert_not_called()

    def test_goal_event_payload_reaches_formatter(
        self, conn, two_clubs_with_teams_and_match, notif_dao
    ):
        ctx = two_clubs_with_teams_and_match
        notif_dao.upsert(ctx["home_club"]["id"], "telegram", "-100home")

        send_fn = Mock()
        notifier = Notifier(connection=conn, send_fn=send_fn)

        notifier.notify(
            "goal",
            ctx["match"]["id"],
            extra={
                "team_id": ctx["home_team"]["id"],
                "player_name": "Scorer Smith",
                "match_minute": 34,
                "extra_time": 0,
            },
        )

        assert send_fn.call_count == 1
        msg = send_fn.call_args.args[2]
        assert "GOAL" in msg
        assert "Scorer Smith" in msg
        assert "34'" in msg

    def test_one_failing_send_does_not_block_others(
        self, conn, two_clubs_with_teams_and_match, notif_dao
    ):
        ctx = two_clubs_with_teams_and_match
        notif_dao.upsert(ctx["home_club"]["id"], "telegram", "-100home")
        notif_dao.upsert(ctx["away_club"]["id"], "discord", "https://discord.com/api/webhooks/1/away")

        def _send(platform, destination, content):
            if platform == "telegram":
                raise RuntimeError("telegram down")

        send_fn = Mock(side_effect=_send)
        notifier = Notifier(connection=conn, send_fn=send_fn)

        # Should not raise even though telegram failed
        notifier.notify("kickoff", ctx["match"]["id"])
        assert send_fn.call_count == 2

    def test_does_not_leak_destination_on_failure(
        self, conn, two_clubs_with_teams_and_match, notif_dao, caplog
    ):
        ctx = two_clubs_with_teams_and_match
        sensitive = "-100secretchatid9999"
        notif_dao.upsert(ctx["home_club"]["id"], "telegram", sensitive)

        def _boom(*args, **kwargs):
            raise RuntimeError("send failed")

        notifier = Notifier(connection=conn, send_fn=_boom)
        notifier.notify("kickoff", ctx["match"]["id"])

        assert sensitive not in caplog.text


# ---------------------------------------------------------------------------
# Integration through FastAPI BackgroundTasks
# ---------------------------------------------------------------------------


class TestLiveEndpointTriggersNotify:
    """Verify the BackgroundTasks hook fires for the live endpoints."""

    @pytest.fixture
    def admin_client(self):
        mock_admin = {
            "user_id": "00000000-0000-4000-8000-000000000001",
            "username": "dispatch_admin",
            "email": "dispatch@example.com",
            "role": "admin",
            "team_id": None,
            "club_id": None,
            "display_name": "Dispatch Admin",
        }
        app.dependency_overrides[get_current_user_required] = lambda: mock_admin
        try:
            with TestClient(app) as c:
                yield c
        finally:
            app.dependency_overrides.pop(get_current_user_required, None)

    def test_clock_kickoff_fires_notification(
        self, conn, admin_client, two_clubs_with_teams_and_match, notif_dao
    ):
        ctx = two_clubs_with_teams_and_match
        notif_dao.upsert(ctx["home_club"]["id"], "telegram", "-100kickoff")

        send_fn = Mock()
        set_notifier(Notifier(connection=conn, send_fn=send_fn))

        try:
            resp = admin_client.post(
                f"/api/matches/{ctx['match']['id']}/live/clock",
                json={"action": "start_first_half", "half_duration": 45},
            )
            assert resp.status_code == 200
            # BackgroundTasks runs synchronously after the response in TestClient
            assert send_fn.call_count == 1
            msg = send_fn.call_args.args[2]
            assert "KICKOFF" in msg
        finally:
            set_notifier(None)

    def test_second_half_does_not_fire_notification(
        self, conn, admin_client, two_clubs_with_teams_and_match, notif_dao
    ):
        ctx = two_clubs_with_teams_and_match
        notif_dao.upsert(ctx["home_club"]["id"], "telegram", "-100skip")

        send_fn = Mock()
        set_notifier(Notifier(connection=conn, send_fn=send_fn))
        try:
            # Start the match first so second half is valid
            admin_client.post(
                f"/api/matches/{ctx['match']['id']}/live/clock",
                json={"action": "start_first_half", "half_duration": 45},
            )
            send_fn.reset_mock()
            # start_second_half is intentionally skipped
            resp = admin_client.post(
                f"/api/matches/{ctx['match']['id']}/live/clock",
                json={"action": "start_second_half"},
            )
            assert resp.status_code == 200
            send_fn.assert_not_called()
        finally:
            set_notifier(None)


# ---------------------------------------------------------------------------
# notify_event_task wrapper
# ---------------------------------------------------------------------------


class TestNotifyEventTask:
    def test_swallows_exceptions(self, monkeypatch):
        def _explode(*_a, **_kw):
            raise RuntimeError("should not propagate")

        mock_notifier = Mock()
        mock_notifier.notify.side_effect = _explode
        set_notifier(mock_notifier)
        try:
            # Must not raise
            notify_event_task("goal", 1, None)
        finally:
            set_notifier(None)

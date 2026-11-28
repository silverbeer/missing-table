"""Operator feed: one sb-notify event per new final score (SB-1849).

Covers the event a final score becomes, that the feed is dormant without
SB_NOTIFY_CONFIG and never raises, that user-typed team names pass through as
plain text, the chart's routing config, and that each of the three final-score
paths emits exactly once while the follower fan-out runs as before.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sb_notify import NotifyResult, NotifyStatus, load_config

from notifications import ops_events
from notifications.ops_events import CONFIG_ENV, build_match_final_event, emit_match_final, emit_match_final_by_id
from notifications.tasks import notify_event_task

CHART_CONFIG = Path(__file__).resolve().parents[3] / "helm/missing-table/files/sb-notify/config.toml"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/123456/abcDEF_-xyz"  # pragma: allowlist secret

# The flattened row match_dao.get_match_by_id returns.
MATCH = {
    "id": 7,
    "home_team_id": 1,
    "away_team_id": 2,
    "home_team_name": "IFA",
    "away_team_name": "NEFC",
    "home_score": 2,
    "away_score": 1,
    "home_penalty_score": None,
    "away_penalty_score": None,
    "match_status": "completed",
    "match_date": "2026-11-09",
    "age_group_name": "U15",
    "match_type_name": "League",
    "division_name": "Northeast",
    "tournament_name": None,
    "source": "match-scraper",
    "is_test": False,
}


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setenv(CONFIG_ENV, str(tmp_path / "config.toml"))
    monkeypatch.setenv("SB_NOTIFY_STATE", str(tmp_path / "state.db"))
    monkeypatch.setenv("APP_BASE_URL", "https://mt.example/")


@pytest.fixture
def dormant(monkeypatch):
    monkeypatch.delenv(CONFIG_ENV, raising=False)
    monkeypatch.setattr(ops_events, "_dormant_logged", False)


@pytest.fixture
def sent(configured):
    with patch.object(ops_events, "notify", return_value=NotifyResult(status=NotifyStatus.DELIVERED)) as notify:
        yield notify


# --- the event -------------------------------------------------------------------


@pytest.mark.unit
class TestBuildMatchFinalEvent:
    def test_a_final_score_becomes_an_mt_match_final_event(self, configured):
        assert build_match_final_event(MATCH) == {
            "source": "mt-backend",
            "kind": "mt.match_final",
            "level": "info",
            "title": "IFA 2\u20131 NEFC",
            "body": "League · U15 · Northeast · 2026-11-09",
            "links": [("Match", "https://mt.example/?matchId=7")],
            "tags": {"age_group": "U15", "match_type": "League", "match_source": "match-scraper"},
            "dedupe_key": "mt.match_final:7:2-1",
        }

    def test_a_tournament_names_the_tournament_and_a_timestamp_reads_as_its_day(self, configured):
        event = build_match_final_event(
            {**MATCH, "tournament_name": "Jefferson Cup", "match_date": "2026-11-09T19:00:00+00:00"}
        )
        assert event["body"] == "Jefferson Cup · U15 · Northeast · 2026-11-09"

    def test_penalties_are_shown_when_both_are_stored(self, configured):
        event = build_match_final_event(
            {**MATCH, "home_score": 1, "away_score": 1, "home_penalty_score": 4, "away_penalty_score": 3}
        )
        assert event["title"] == "IFA 1\u20131 NEFC"
        assert event["body"].endswith("\nPenalties 4\u20133")

    def test_a_goalless_draw_is_a_score(self, configured):
        event = build_match_final_event({**MATCH, "home_score": 0, "away_score": 0})
        assert event["title"] == "IFA 0\u20130 NEFC"
        assert event["dedupe_key"] == "mt.match_final:7:0-0"

    def test_missing_names_and_unknown_joins_degrade_per_field(self, configured):
        sparse = {
            "id": 7,
            "home_score": 3,
            "away_score": 0,
            "home_team_name": "Unknown",  # what match_dao writes for a missing join
            "age_group_name": "Unknown",
            "match_type_name": None,
        }
        event = build_match_final_event(sparse)
        assert event["title"] == "Home team 3\u20130 Away team"
        assert event["body"] is None
        assert event["tags"] == {}

    @pytest.mark.parametrize("over", [{"home_score": None}, {"away_score": None}, {"id": None}])
    def test_no_score_no_event(self, over):
        assert build_match_final_event({**MATCH, **over}) is None

    def test_user_typed_names_go_through_as_plain_text(self, configured):
        """The sink escapes for its platform; markup added here would break that."""
        event = build_match_final_event(
            {**MATCH, "home_team_name": "@everyone FC", "away_team_name": "<!channel> *U15*"}
        )
        assert event["title"] == "@everyone FC 2\u20131 <!channel> *U15*"
        assert event["dedupe_key"] == "mt.match_final:7:2-1"


# --- emit --------------------------------------------------------------------------


@pytest.mark.unit
class TestEmitMatchFinal:
    def test_sends_the_event(self, sent):
        emit_match_final(MATCH)
        sent.assert_called_once_with(**build_match_final_event(MATCH))

    def test_dormant_without_config_and_logs_once(self, dormant):
        with patch.object(ops_events, "notify") as notify, patch.object(ops_events, "logger") as log:
            emit_match_final(MATCH)
            emit_match_final(MATCH)
            emit_match_final_by_id(7, MagicMock())
        notify.assert_not_called()
        assert [c.args[0] for c in log.info.call_args_list] == ["ops_events.dormant"]
        log.warning.assert_not_called()

    def test_dormant_skips_the_match_read(self, dormant):
        load = MagicMock()
        emit_match_final_by_id(7, load)
        load.assert_not_called()

    def test_a_test_match_is_not_a_result(self, sent):
        emit_match_final({**MATCH, "is_test": True})
        sent.assert_not_called()

    def test_never_raises_when_notify_raises(self, configured):
        with patch.object(ops_events, "notify", side_effect=RuntimeError("boom")):
            emit_match_final(MATCH)

    def test_never_raises_when_notify_fails(self, configured):
        failed = NotifyResult(status=NotifyStatus.FAILED, error="Slack destination must be an incoming webhook URL")
        with patch.object(ops_events, "notify", return_value=failed), patch.object(ops_events, "logger") as log:
            emit_match_final(MATCH)
        assert log.info.call_args.kwargs["status"] == "failed"

    def test_never_raises_when_the_match_read_fails(self, sent):
        emit_match_final_by_id(7, MagicMock(side_effect=RuntimeError("db down")))
        sent.assert_not_called()

    def test_an_unknown_match_sends_nothing(self, sent):
        emit_match_final_by_id(7, MagicMock(return_value=None))
        sent.assert_not_called()


@pytest.mark.unit
class TestThroughSbNotify:
    """The real library against the chart's config, with Discord's HTTP stubbed out."""

    FEST = {**MATCH, "tournament_id": 9, "tournament_name": "2026 MLS NEXT Fest"}

    @pytest.fixture
    def discord(self, monkeypatch, tmp_path):
        monkeypatch.setenv(CONFIG_ENV, str(CHART_CONFIG))
        monkeypatch.setenv("SB_NOTIFY_STATE", str(tmp_path / "state.db"))
        monkeypatch.setenv("SB_NOTIFY_DISCORD_FEST_WEBHOOK", DISCORD_WEBHOOK)
        posts = []

        def post(self, url, json=None, **kwargs):
            posts.append(json)
            return httpx.Response(204, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx.Client, "post", post)
        return posts

    def _at(self, hour):
        """A New York wall-clock hour on a November day (UTC-5)."""
        stamp = datetime(2026, 11, 9, (hour + 5) % 24, tzinfo=UTC).timestamp()
        return patch("sb_notify.router.time.time", return_value=stamp)

    def test_chart_config_routes_fest_scores_to_discord_in_real_time(self):
        config = load_config(CHART_CONFIG)
        assert [(route.sinks, route.quiet_hours) for route in config.routes] == [(("discord-mls-next-fest",), False)]
        assert config.sinks["discord-mls-next-fest"].destination_env == "SB_NOTIFY_DISCORD_FEST_WEBHOOK"
        quiet = config.quiet_hours
        assert (quiet.start.isoformat(), quiet.end.isoformat(), quiet.timezone) == (
            "22:00:00",
            "07:00:00",
            "America/New_York",
        )
        assert {str(level) for level in quiet.levels} == {"info", "warn", "error", "critical"}

    def test_a_fest_score_posts_once_and_the_dedupe_key_drops_a_repeat(self, discord):
        hostile = {**self.FEST, "home_team_name": "@everyone FC"}
        with self._at(15), patch.object(ops_events, "logger") as log:
            emit_match_final(hostile)
            emit_match_final(hostile)
        assert [c.kwargs["status"] for c in log.info.call_args_list] == ["delivered", "suppressed"]
        assert len(discord) == 1
        payload = discord[0]
        assert "2\u20131 NEFC" in payload["content"]
        assert "@everyone" not in payload["content"]
        assert payload["allowed_mentions"] == {"parse": []}
        # The destination is never logged.
        assert DISCORD_WEBHOOK not in json.dumps([c.kwargs for c in log.info.call_args_list], default=str)

    def test_a_late_fest_score_posts_at_once_despite_quiet_hours(self, discord):
        with self._at(23), patch.object(ops_events, "logger") as log:
            emit_match_final(self.FEST)
        assert [c.kwargs["status"] for c in log.info.call_args_list] == ["delivered"]
        assert len(discord) == 1

    def test_a_score_outside_the_fest_goes_nowhere(self, discord):
        with self._at(15), patch.object(ops_events, "logger") as log:
            emit_match_final({**MATCH, "tournament_id": 4})
        assert [c.kwargs["status"] for c in log.info.call_args_list] == ["unrouted"]
        assert discord == []


# --- the hook ----------------------------------------------------------------------


@pytest.fixture
def fanout():
    """The dispatcher, stubbed: it records the fan-out and serves the match row."""
    notifier = MagicMock()
    notifier.match_dao.get_match_by_id.return_value = MATCH
    with patch("notifications.tasks.get_notifier", return_value=notifier):
        yield notifier


@pytest.mark.unit
class TestNotifyEventTaskHook:
    def test_fulltime_fans_out_then_emits_once(self, fanout, sent):
        notify_event_task("fulltime", 7, None, "match:7:fulltime:2-1")
        fanout.notify.assert_called_once_with(
            event_type="fulltime", match_id=7, extra=None, event_key="match:7:fulltime:2-1"
        )
        fanout.match_dao.get_match_by_id.assert_called_once_with(7, include_test=True)
        sent.assert_called_once()

    @pytest.mark.parametrize("event_type", ["kickoff", "halftime", "goal", "yellow_card", "lineup"])
    def test_other_events_do_not_emit(self, fanout, sent, event_type):
        notify_event_task(event_type, 7)
        fanout.notify.assert_called_once()
        sent.assert_not_called()

    def test_a_failed_fan_out_still_emits(self, fanout, sent):
        fanout.notify.side_effect = RuntimeError("supabase down")
        notify_event_task("fulltime", 7)
        sent.assert_called_once()

    def test_a_failed_emit_leaves_the_fan_out_alone(self, fanout, configured):
        with patch.object(ops_events, "notify", side_effect=RuntimeError("boom")):
            notify_event_task("fulltime", 7)
        fanout.notify.assert_called_once()


# --- each final-score path, end to end through the background task -------------------


@pytest.mark.unit
class TestEachFinalScorePathEmitsOnce:
    def test_match_write_with_a_new_final_score(self, fanout, sent):
        from app import _maybe_notify_final_score

        tasks = BackgroundTasks()
        before = {"id": 7, "home_score": None, "away_score": None, "match_status": "scheduled"}
        _maybe_notify_final_score(tasks, before, {**MATCH})
        for task in tasks.tasks:
            task.func(*task.args, **task.kwargs)
        sent.assert_called_once()

    def test_match_write_that_leaves_the_score_alone(self, fanout, sent):
        from app import _maybe_notify_final_score

        tasks = BackgroundTasks()
        _maybe_notify_final_score(tasks, {**MATCH}, {**MATCH, "tournament_round": "final"})
        assert tasks.tasks == []
        sent.assert_not_called()

    def _final_score_alert(self, claimed):
        import app as app_module
        from app import app
        from auth import get_current_user_required

        app.dependency_overrides[get_current_user_required] = lambda: {"role": "admin", "username": "tom"}
        try:
            with (
                patch.object(app_module.match_dao, "get_match_by_id", return_value=MATCH),
                patch("api.club_notifications.claim_once", return_value=claimed),
                patch.object(app_module, "datetime") as dt,
            ):
                dt.now.return_value = datetime(2026, 11, 10, 12, tzinfo=UTC)
                return TestClient(app).post("/api/matches/7/final-score-alert")
        finally:
            app.dependency_overrides.clear()

    def test_scraper_final_score_alert(self, fanout, sent):
        assert self._final_score_alert(claimed=True).json()["queued"] is True
        fanout.notify.assert_called_once()
        sent.assert_called_once()

    def test_scraper_repeat_call_is_already_claimed(self, fanout, sent):
        assert self._final_score_alert(claimed=False).json()["reason"] == "already_sent"
        fanout.notify.assert_not_called()
        sent.assert_not_called()

    def _clock(self, action, match):
        from app import app
        from auth import require_match_management_permission

        app.dependency_overrides[require_match_management_permission] = lambda: {
            "user_id": "u",
            "id": "u",
            "username": "tester",
            "role": "admin",
        }
        try:
            with (
                patch("app.match_dao") as match_dao,
                patch("app.match_event_dao"),
                patch("app.player_stats_dao"),
                patch("app.lineup_dao"),
                patch("app.auth_manager") as auth,
            ):
                match_dao.get_match_by_id.return_value = match
                match_dao.update_match_clock.return_value = {"match_id": 7}
                match_dao.get_live_match_state.return_value = {"match_id": 7}
                auth.can_edit_match.return_value = True
                return TestClient(app).post("/api/matches/7/live/clock", json={"action": action})
        finally:
            app.dependency_overrides.clear()

    def test_live_scoring_full_time(self, fanout, sent):
        live = {**MATCH, "match_status": "live", "kickoff_time": "2026-11-09T13:00:00+00:00", "match_end_time": None}
        assert self._clock("end_match", live).status_code == 200
        sent.assert_called_once()

    def test_live_scoring_halftime_does_not_emit(self, fanout, sent):
        live = {**MATCH, "match_status": "live", "kickoff_time": "2026-11-09T13:00:00+00:00", "halftime_start": None}
        assert self._clock("start_halftime", live).status_code == 200
        fanout.notify.assert_called_once()
        sent.assert_not_called()

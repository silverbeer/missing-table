"""Telegram alerting for unresolved ingest names (SB-829).

The failure this guards against is not "no alert" — it is an alert stream
nobody reads. A season load that dies on seven spellings must send seven
messages, not the four hundred dropped matches' worth, and a brand-new season
with dozens of unknown names must not turn Telegram into a log tail.
"""

from unittest.mock import MagicMock, patch

import pytest

from notifications.ingest_alerts import CHAT_ID_ENV, alert_unresolved_name

NEW = {"id": 3, "match_count": 1, "should_alert": True}
REPEAT = {"id": 3, "match_count": 88, "should_alert": False}

ARGS = {
    "kind": "team",
    "raw_name": "Intercontinental Football Academy of New England",
    "league": "Homegrown",
    "sample": "IFA vs Island FC, 2026-09-05 U15",
}


@pytest.fixture
def dao():
    d = MagicMock()
    d.notified_since.return_value = 0
    return d


@pytest.fixture
def chat(monkeypatch):
    monkeypatch.setenv(CHAT_ID_ENV, "-100123")
    monkeypatch.delenv("MT_INGEST_ALERT_MAX_PER_HOUR", raising=False)


@pytest.mark.unit
class TestOneMessagePerName:
    def test_a_newly_seen_name_alerts(self, dao, chat):
        with patch("notifications.ingest_alerts.send_to") as send:
            assert alert_unresolved_name(dao, record=NEW, **ARGS) is True
        assert send.call_count == 1
        dao.mark_notified.assert_called_once_with([3])

    def test_the_same_name_again_does_not(self, dao, chat):
        # 412 dropped matches across 7 names is 7 messages, not 412.
        with patch("notifications.ingest_alerts.send_to") as send:
            assert alert_unresolved_name(dao, record=REPEAT, **ARGS) is False
        send.assert_not_called()

    def test_a_failed_record_write_does_not_alert(self, dao, chat):
        # record() returns None when the write itself failed. Alerting on a
        # failure we did not manage to persist means alerting on it again on
        # the next match, and the next.
        with patch("notifications.ingest_alerts.send_to") as send:
            assert alert_unresolved_name(dao, record=None, **ARGS) is False
        send.assert_not_called()


@pytest.mark.unit
class TestMessageContent:
    def _message(self, dao, **overrides):
        with patch("notifications.ingest_alerts.send_to") as send:
            alert_unresolved_name(dao, record=NEW, **{**ARGS, **overrides})
        return send.call_args.args[2]

    def test_names_the_string_verbatim(self, dao, chat):
        # Verbatim because the fix is to alias exactly this string; a tidied
        # copy would not be the one that needs aliasing.
        assert ARGS["raw_name"] in self._message(dao)

    def test_carries_the_fix_command(self, dao, chat):
        assert 'mt team alias add <team> "Intercontinental' in self._message(dao)

    def test_carries_league_and_a_sample_match(self, dao, chat):
        message = self._message(dao)
        assert "league: Homegrown" in message
        assert "IFA vs Island FC" in message

    def test_a_division_failure_does_not_suggest_the_team_command(self, dao, chat):
        message = self._message(dao, kind="division", raw_name="Turnpike", league="Flex")
        assert "Unknown division: Turnpike" in message
        assert "team alias add" not in message


@pytest.mark.unit
class TestVolumeCap:
    def test_under_the_cap_alerts_normally(self, dao, chat, monkeypatch):
        monkeypatch.setenv("MT_INGEST_ALERT_MAX_PER_HOUR", "3")
        dao.notified_since.return_value = 2
        with patch("notifications.ingest_alerts.send_to") as send:
            assert alert_unresolved_name(dao, record=NEW, **ARGS) is True
        assert ARGS["raw_name"] in send.call_args.args[2]

    def test_at_the_cap_says_so_once(self, dao, chat, monkeypatch):
        monkeypatch.setenv("MT_INGEST_ALERT_MAX_PER_HOUR", "3")
        dao.notified_since.return_value = 3
        with patch("notifications.ingest_alerts.send_to") as send:
            assert alert_unresolved_name(dao, record=NEW, **ARGS) is True
        message = send.call_args.args[2]
        assert "more than 3 unresolved names" in message
        assert "/api/admin/ingest-failures" in message

    def test_past_the_cap_is_silent_but_still_recorded(self, dao, chat, monkeypatch):
        # Silent, not lost: the row exists and the API still reports it.
        monkeypatch.setenv("MT_INGEST_ALERT_MAX_PER_HOUR", "3")
        dao.notified_since.return_value = 4
        with patch("notifications.ingest_alerts.send_to") as send:
            assert alert_unresolved_name(dao, record=NEW, **ARGS) is False
        send.assert_not_called()

    def test_a_junk_cap_setting_falls_back_to_the_default(self, dao, chat, monkeypatch):
        monkeypatch.setenv("MT_INGEST_ALERT_MAX_PER_HOUR", "not-a-number")
        dao.notified_since.return_value = 5
        with patch("notifications.ingest_alerts.send_to") as send:
            assert alert_unresolved_name(dao, record=NEW, **ARGS) is True
        assert ARGS["raw_name"] in send.call_args.args[2]


@pytest.mark.unit
class TestAlertingNeverBreaksIngest:
    def test_no_chat_id_configured_is_not_an_error(self, dao, monkeypatch):
        # The normal state locally and in CI. The row is recorded either way.
        monkeypatch.delenv(CHAT_ID_ENV, raising=False)
        with patch("notifications.ingest_alerts.send_to") as send:
            assert alert_unresolved_name(dao, record=NEW, **ARGS) is False
        send.assert_not_called()

    def test_a_telegram_failure_is_swallowed(self, dao, chat):
        # This runs on the failure path of a task that is already going to
        # fail. A diagnostic that can take down ingest is worse than none.
        with patch("notifications.ingest_alerts.send_to", side_effect=RuntimeError("bot token revoked")):
            assert alert_unresolved_name(dao, record=NEW, **ARGS) is False

    def test_a_dao_failure_is_swallowed(self, dao, chat):
        dao.notified_since.side_effect = RuntimeError("db down")
        with patch("notifications.ingest_alerts.send_to") as send:
            assert alert_unresolved_name(dao, record=NEW, **ARGS) is False
        send.assert_not_called()

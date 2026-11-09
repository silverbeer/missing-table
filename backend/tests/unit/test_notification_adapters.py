"""The contract every notification platform adapter must meet (SB-1600).

Parametrized over the registry, so a newly registered platform is held to all
of this without touching this file.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import httpx
import pytest

from notifications import registry
from notifications.adapters.base import (
    ChannelAdapter,
    DeliveryError,
    DeliveryResult,
    InvalidDestinationError,
    NotificationConfigError,
    UnsupportedPlatformError,
)
from notifications.adapters.discord import DiscordAdapter
from notifications.adapters.slack import SlackAdapter, escape
from notifications.adapters.telegram import TelegramAdapter
from notifications.senders import send_to

pytestmark = pytest.mark.unit

ADAPTERS = registry.all_adapters()
IDS = [adapter.id for adapter in ADAPTERS]


class TestAdapterContract:
    @pytest.mark.parametrize("adapter", ADAPTERS, ids=IDS)
    def test_declares_everything_the_setup_ui_renders(self, adapter: ChannelAdapter):
        for field in ("id", "label", "icon", "placeholder", "hint", "destination_error"):
            assert getattr(adapter, field), f"{adapter.id} has no {field}"

    @pytest.mark.parametrize("adapter", ADAPTERS, ids=IDS)
    def test_pattern_is_anchored_and_compiles(self, adapter: ChannelAdapter):
        re.compile(adapter.destination_pattern)
        assert adapter.destination_pattern.startswith("^")
        assert adapter.destination_pattern.endswith("$")

    @pytest.mark.parametrize("adapter", ADAPTERS, ids=IDS)
    @pytest.mark.parametrize("junk", ["", "not a destination", "https://example.com/x"])
    def test_rejects_junk(self, adapter: ChannelAdapter, junk: str):
        with pytest.raises(InvalidDestinationError):
            adapter.validate_destination(junk)

    @pytest.mark.parametrize("adapter", ADAPTERS, ids=IDS)
    def test_error_does_not_echo_the_destination(self, adapter: ChannelAdapter):
        value = "do-not-echo"
        with pytest.raises(InvalidDestinationError) as exc:
            adapter.validate_destination(value)
        assert value not in str(exc.value)


class TestDestinationValidation:
    @pytest.mark.parametrize("value", ["-1001234567890", "12345", "@my_channel"])
    def test_telegram_accepts(self, value: str):
        TelegramAdapter().validate_destination(value)

    @pytest.mark.parametrize(
        "value",
        [
            "https://discord.com/api/webhooks/123/abc-DEF_1",
            "https://discordapp.com/api/webhooks/123/abc",
        ],
    )
    def test_discord_accepts(self, value: str):
        DiscordAdapter().validate_destination(value)

    @pytest.mark.parametrize(
        "value",
        [
            "http://discord.com/api/webhooks/123/abc",
            "https://discord.com.evil.test/api/webhooks/123/abc",
            "https://discord.com/api/webhooks/123/abc\n",
        ],
    )
    def test_discord_rejects_lookalikes(self, value: str):
        with pytest.raises(InvalidDestinationError):
            DiscordAdapter().validate_destination(value)


class TestTelegramSend:
    def test_escapes_and_returns_the_message_id(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
        client = MagicMock()
        client.send.return_value = {"ok": True, "result": {"message_id": 77}}
        with patch("notifications.adapters.telegram.TelegramClient", return_value=client):
            result = TelegramAdapter().send("-100", "IFA 2-1 NEFC.")
        assert client.send.call_args.args[0] == r"IFA 2\-1 NEFC\."
        assert result == DeliveryResult(message_ref="77")

    def test_missing_token_raises_config_error(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        with pytest.raises(NotificationConfigError):
            TelegramAdapter().send("-100", "text")


class TestDiscordSend:
    def test_sends_unescaped_and_has_no_ref_on_204(self):
        client = MagicMock()
        client.send.return_value = None
        with patch("notifications.adapters.discord.DiscordWebhookClient", return_value=client):
            result = DiscordAdapter().send("https://hook", "IFA 2-1 NEFC.")
        client.send.assert_called_once_with("IFA 2-1 NEFC.")
        assert result == DeliveryResult(message_ref=None)


# Assembled so secret scanners don't read a test fixture as a real webhook.
SLACK_URL = "https://hooks.slack.com/" + "/".join(["services", "TEAM1", "BOT2", "abc3"])


class TestSlack:
    def test_accepts_a_webhook_url(self):
        SlackAdapter().validate_destination(SLACK_URL)

    @pytest.mark.parametrize(
        "value",
        [
            SLACK_URL.replace("https", "http", 1),
            SLACK_URL.replace("hooks.slack.com", "hooks.slack.com.evil.test"),
            SLACK_URL.replace("hooks.slack.com", "hooksXslack.com"),
            SLACK_URL + "/extra",
            SLACK_URL + "\n",
        ],
    )
    def test_rejects_lookalikes(self, value: str):
        with pytest.raises(InvalidDestinationError):
            SlackAdapter().validate_destination(value)

    def test_escapes_ampersand_first(self):
        assert escape("A&B <!channel>") == "A&amp;B &lt;!channel&gt;"

    def test_posts_escaped_text_with_a_timeout(self):
        request = httpx.Request("POST", SLACK_URL)
        with patch(
            "notifications.adapters.slack.httpx.post",
            return_value=httpx.Response(200, text="ok", request=request),
        ) as post:
            result = SlackAdapter().send(SLACK_URL, "<!channel> scored")
        assert post.call_args.args[0] == SLACK_URL
        assert post.call_args.kwargs["json"] == {
            "text": "&lt;!channel&gt; scored",
            "mrkdwn": False,
        }
        assert post.call_args.kwargs["timeout"] > 0
        assert result == DeliveryResult(message_ref=None)

    def test_does_not_claim_threads(self):
        assert SlackAdapter().capabilities == frozenset()

    def test_failure_does_not_leak_the_webhook(self):
        request = httpx.Request("POST", SLACK_URL)
        with (
            patch(
                "notifications.adapters.slack.httpx.post",
                return_value=httpx.Response(404, request=request),
            ),
            pytest.raises(DeliveryError) as exc,
        ):
            SlackAdapter().send(SLACK_URL, "text")
        assert "abc3" not in str(exc.value)
        assert "HTTP 404" in str(exc.value)

    def test_is_registered(self):
        assert isinstance(registry.get_adapter("slack"), SlackAdapter)


class TestSecretsStayOutOfErrors:
    """httpx error text includes the URL, which is where the secret lives."""

    URL = "https://provider.test/SECRET-IN-URL/send"

    def _status_error(self) -> httpx.HTTPStatusError:
        request = httpx.Request("POST", self.URL)
        response = httpx.Response(400, request=request)
        return httpx.HTTPStatusError(f"400 for url {self.URL}", request=request, response=response)

    @pytest.mark.parametrize(
        ("adapter", "client_path"),
        [
            (TelegramAdapter(), "notifications.adapters.telegram.TelegramClient"),
            (DiscordAdapter(), "notifications.adapters.discord.DiscordWebhookClient"),
        ],
        ids=["telegram", "discord"],
    )
    def test_http_failure_is_sanitized(self, adapter, client_path, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
        client = MagicMock()
        client.send.side_effect = self._status_error()
        with patch(client_path, return_value=client), pytest.raises(DeliveryError) as exc:
            adapter.send("dest", "text")
        assert "SECRET-IN-URL" not in str(exc.value)
        assert "HTTP 400" in str(exc.value)
        assert exc.value.__suppress_context__ is True


class TestRegistry:
    def test_unknown_platform_raises(self):
        with pytest.raises(UnsupportedPlatformError):
            registry.get_adapter("sms")

    def test_duplicate_id_is_refused(self):
        with pytest.raises(ValueError, match="already registered"):
            registry.register(TelegramAdapter())

    def test_send_to_delegates_to_the_adapter(self):
        adapter = MagicMock()
        adapter.send.return_value = DeliveryResult(message_ref="1")
        with patch("notifications.senders.get_adapter", return_value=adapter) as get:
            assert send_to("telegram", "dest", "text") == DeliveryResult(message_ref="1")
        get.assert_called_once_with("telegram")
        adapter.send.assert_called_once_with("dest", "text")

    def test_send_to_unknown_platform_is_a_value_error(self):
        with pytest.raises(ValueError, match="Unsupported platform"):
            send_to("sms", "dest", "text")

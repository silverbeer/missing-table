"""Slack, through a per-channel incoming webhook."""

from __future__ import annotations

from typing import ClassVar

import httpx

from notifications.adapters.base import ChannelAdapter, DeliveryResult

# Slack parses <...> as links and mentions, so a player named "<!channel>" would
# ping the room. Ampersand first, or it would re-escape the other two.
_ESCAPES = (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"))
_TIMEOUT_SECONDS = 5.0


def escape(text: str) -> str:
    for char, entity in _ESCAPES:
        text = text.replace(char, entity)
    return text


class SlackAdapter(ChannelAdapter):
    id: ClassVar[str] = "slack"
    label: ClassVar[str] = "Slack"
    icon: ClassVar[str] = "#️⃣"
    placeholder: ClassVar[str] = "https://hooks.slack.com/services/…"
    hint: ClassVar[str] = (
        "Add an Incoming Webhook to your Slack channel and paste the full webhook URL."
    )
    # Exact host and shape: the backend POSTs here, so this is the SSRF guard.
    destination_pattern: ClassVar[str] = (
        r"^https://hooks\.slack\.com/services/[A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9]+$"
    )
    destination_error: ClassVar[str] = "Slack destination must be an incoming webhook URL"
    # No Capability.THREADS: a webhook does not return the `ts` a thread needs.

    def _deliver(self, destination: str, content: str) -> DeliveryResult:
        response = httpx.post(
            destination,
            json={"text": escape(content), "mrkdwn": False},
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return DeliveryResult(message_ref=None)

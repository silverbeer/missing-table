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
    invite_pattern: ClassVar[str] = (
        r"^https://join\.slack\.com/t/[A-Za-z0-9-]{1,80}/shared_invite/[A-Za-z0-9_-]{4,200}$"
    )
    invite_error: ClassVar[str] = "Must be a Slack invite link (https://join.slack.com/t/.../shared_invite/...)"
    placeholder: ClassVar[str] = "https://hooks.slack.com/services/…"
    hint: ClassVar[str] = "Add an Incoming Webhook to your Slack channel and paste the full webhook URL."
    setup_steps: ClassVar[tuple[str, ...]] = (
        "Go to api.slack.com/apps → Create New App → Pick features, name it Missing Table and pick your "
        "workspace, or open the app you already made.",
        "Under Features → Incoming Webhooks, turn Activate Incoming Webhooks on.",
        "Click Add New Webhook to Workspace, pick the channel and click Authorize. If the channel is set to "
        "Private in Slack, join it first or it is not listed. Each webhook posts to one channel.",
        "Copy the Webhook URL (it starts https://hooks.slack.com/services/) and paste it here. "
        "Treat it like a password.",
        "Then click Send test to confirm a message arrives.",
    )
    # Exact host and shape: the backend POSTs here, so this is the SSRF guard.
    destination_pattern: ClassVar[str] = r"^https://hooks\.slack\.com/services/[A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9]+$"
    destination_error: ClassVar[str] = "Slack destination must be an incoming webhook URL"
    # Slack's terms require users to be over 16.
    min_player_age: ClassVar[int | None] = 17
    player_setup_steps: ClassVar[tuple[str, ...]] = (
        "Player channels are read-only with reactions: players react, only managers post.",
        "Channel details → Settings → Posting permissions: let only admins or chosen people post "
        "(needs a paid Slack plan). Leave Add Reactions on for everyone else.",
        "Check from a player account that it can react but not post; Slack's "
        "options vary by plan, so confirm before inviting players.",
    )
    # No Capability.THREADS: a webhook does not return the `ts` a thread needs.

    def _deliver(self, destination: str, content: str) -> DeliveryResult:
        response = httpx.post(
            destination,
            json={"text": escape(content), "mrkdwn": False},
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return DeliveryResult(message_ref=None)

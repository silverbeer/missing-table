"""Discord, through a per-channel webhook."""

from __future__ import annotations

from typing import ClassVar

import httpx
from discord_notify import DiscordWebhookClient

from notifications.adapters.base import Capability, ChannelAdapter, DeliveryResult

TIMEOUT_SECONDS = 10.0


class DiscordAdapter(ChannelAdapter):
    id: ClassVar[str] = "discord"
    label: ClassVar[str] = "Discord"
    icon: ClassVar[str] = "💬"
    invite_pattern: ClassVar[str] = r"^https://(discord\.gg|discord\.com/invite)/[A-Za-z0-9_-]{2,64}$"
    invite_error: ClassVar[str] = "Must be a Discord invite link (https://discord.gg/...)"
    placeholder: ClassVar[str] = "https://discord.com/api/webhooks/…/…"
    hint: ClassVar[str] = (
        "Create a webhook on your Discord channel (Channel Settings → Integrations → Webhooks) and paste the full URL."
    )
    setup_steps: ClassVar[tuple[str, ...]] = (
        "You need the Manage Webhooks permission on the Discord server.",
        "Open the channel's settings (gear icon) → Integrations → Webhooks → New Webhook.",
        "Name it Missing Table, make sure the right channel is selected, and save.",
        "Click Copy Webhook URL and paste it here. Treat it like a password: anyone with it can post.",
        "Then click Send test to confirm a message arrives.",
        "A text channel gets every update as its own message. For one post per match, point the "
        "webhook at a Forum channel instead and tick One post per match below.",
    )
    player_setup_steps: ClassVar[tuple[str, ...]] = (
        "Player channels are read-only with reactions: players react, only managers post.",
        "Channel settings → Permissions → @everyone: deny Send Messages, Send Messages in Threads, "
        "Create Public Threads and Create Private Threads.",
        "Keep View Channel, Read Message History and Add Reactions allowed. Reacting needs Read Message History.",
        "Check that no other role gives Send Messages back, then post a test as a player account.",
    )
    age_note: ClassVar[str | None] = "Discord requires members to be at least 13, and older in some countries."
    destination_pattern: ClassVar[str] = r"^https://discord(app)?\.com/api/webhooks/\d+/[\w-]+$"
    destination_error: ClassVar[str] = "Discord destination must be a webhook URL"
    # Discord's minimum age is 13; U14 is the youngest squad that clears it.
    min_player_age: ClassVar[int | None] = 14

    # Match threads (SB-1606): a webhook in a forum channel.
    capabilities: ClassVar[frozenset[Capability]] = frozenset({Capability.THREADS})

    def _deliver_in_thread(
        self, destination: str, content: str, thread_ref: str | None, thread_name: str | None
    ) -> DeliveryResult:
        """POST to the webhook with wait=true so Discord returns the message.

        `thread_name` makes a new forum post (forum and media channels only);
        `thread_id` posts into an existing one. A message posted in a thread
        carries the thread as its channel_id, which is how the new post's id
        comes back for follow-ups. Send test on a forum channel checks this
        live: it creates a post, then replies into it with that id.
        """
        params: dict[str, str] = {"wait": "true"}
        body: dict[str, str] = {"content": content}
        if thread_ref:
            params["thread_id"] = thread_ref
        elif thread_name:
            body["thread_name"] = thread_name[:100]
        response = httpx.post(destination, params=params, json=body, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json() if response.content else {}
        message_id = data.get("id")
        thread = data.get("channel_id") or thread_ref
        return DeliveryResult(
            message_ref=None if message_id is None else str(message_id),
            thread_ref=None if thread is None else str(thread),
        )

    def _deliver(self, destination: str, content: str) -> DeliveryResult:
        # Discord-flavored markdown is permissive, so the text goes as-is.
        response = DiscordWebhookClient(webhook_url=destination).send(content)
        # A webhook answers 204 with no body unless asked to wait.
        message_id = (response or {}).get("id")
        return DeliveryResult(message_ref=None if message_id is None else str(message_id))

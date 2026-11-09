"""Discord, through a per-channel webhook."""

from __future__ import annotations

from typing import ClassVar

from discord_notify import DiscordWebhookClient

from notifications.adapters.base import ChannelAdapter, DeliveryResult


class DiscordAdapter(ChannelAdapter):
    id: ClassVar[str] = "discord"
    label: ClassVar[str] = "Discord"
    icon: ClassVar[str] = "💬"
    invite_pattern: ClassVar[str] = r"^https://(discord\.gg|discord\.com/invite)/[A-Za-z0-9_-]{2,64}$"
    invite_error: ClassVar[str] = "Must be a Discord invite link (https://discord.gg/...)"
    placeholder: ClassVar[str] = "https://discord.com/api/webhooks/…/…"
    hint: ClassVar[str] = (
        "Create a webhook on your Discord channel (Channel Settings → Integrations → Webhooks) "
        "and paste the full URL."
    )
    destination_pattern: ClassVar[str] = r"^https://discord(app)?\.com/api/webhooks/\d+/[\w-]+$"
    destination_error: ClassVar[str] = "Discord destination must be a webhook URL"
    # Discord's minimum age is 13; U14 is the youngest squad that clears it.
    min_player_age: ClassVar[int | None] = 14

    def _deliver(self, destination: str, content: str) -> DeliveryResult:
        # Discord-flavored markdown is permissive, so the text goes as-is.
        response = DiscordWebhookClient(webhook_url=destination).send(content)
        # A webhook answers 204 with no body unless asked to wait.
        message_id = (response or {}).get("id")
        return DeliveryResult(message_ref=None if message_id is None else str(message_id))

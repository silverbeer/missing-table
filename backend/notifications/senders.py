"""Thin adapters around telegram-notify and discord-notify.

The notification subsystem's only outbound IO path. Errors are raised to
the caller; the caller (dispatcher / API test-send endpoint) decides what
to log or surface to the user.

Destination values are never logged by these helpers.
"""

from __future__ import annotations

import os

from discord_notify import DiscordWebhookClient
from telegram_notify import TelegramClient, escape


class NotificationConfigError(RuntimeError):
    """Raised when the subsystem is missing required config (e.g. bot token)."""


def send_to(platform: str, destination: str, content: str) -> None:
    """Deliver `content` to a single (platform, destination).

    For Telegram, `content` is escaped for MarkdownV2 here. For Discord,
    the content is sent as-is (Discord-flavored markdown is permissive).
    """
    if platform == "telegram":
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise NotificationConfigError(
                "TELEGRAM_BOT_TOKEN is not set — cannot send Telegram notifications."
            )
        client = TelegramClient(bot_token=bot_token, chat_id=destination)
        client.send(escape(content))
        return

    if platform == "discord":
        client = DiscordWebhookClient(webhook_url=destination)
        client.send(content)
        return

    raise ValueError(f"Unsupported platform: {platform}")

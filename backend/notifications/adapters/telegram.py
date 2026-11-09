"""Telegram, through the shared MT bot."""

from __future__ import annotations

import os
from typing import ClassVar

from telegram_notify import TelegramClient, escape

from notifications.adapters.base import ChannelAdapter, DeliveryResult, NotificationConfigError


class TelegramAdapter(ChannelAdapter):
    id: ClassVar[str] = "telegram"
    label: ClassVar[str] = "Telegram"
    icon: ClassVar[str] = "✈️"
    invite_pattern: ClassVar[str] = r"^https://t\.me/(\+|joinchat/)[A-Za-z0-9_-]{8,64}$"
    invite_error: ClassVar[str] = "Must be a private Telegram invite link (https://t.me/+...)"
    placeholder: ClassVar[str] = "e.g. -1001234567890 or @channelname"
    hint: ClassVar[str] = (
        "Paste the chat_id for a group the Missing Table bot has been added to, or an @channel username."
    )
    destination_pattern: ClassVar[str] = r"^(@\w+|-?\d+)$"
    destination_error: ClassVar[str] = (
        "Telegram destination must be a numeric chat_id (e.g. -1001234567890) or @channel"
    )

    def check_config(self) -> None:
        if not os.getenv("TELEGRAM_BOT_TOKEN"):
            raise NotificationConfigError(
                "TELEGRAM_BOT_TOKEN is not set — cannot send Telegram notifications."
            )

    def _deliver(self, destination: str, content: str) -> DeliveryResult:
        self.check_config()
        client = TelegramClient(bot_token=os.environ["TELEGRAM_BOT_TOKEN"], chat_id=destination)
        response = client.send(escape(content))
        message_id = (response.get("result") or {}).get("message_id")
        return DeliveryResult(message_ref=None if message_id is None else str(message_id))

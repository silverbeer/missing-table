"""The set of chat platforms MT can post to.

This is the only list of platforms in the codebase. API validation, the setup
UI (through GET /api/notifications/platforms) and delivery all read it. To add
a platform, write an adapter in `notifications/adapters/` and register it below;
`tests/unit/test_notification_adapters.py` holds every adapter to the contract
automatically.
"""

from __future__ import annotations

from notifications.adapters.base import ChannelAdapter, UnsupportedPlatformError
from notifications.adapters.discord import DiscordAdapter
from notifications.adapters.telegram import TelegramAdapter

_adapters: dict[str, ChannelAdapter] = {}


def register(adapter: ChannelAdapter) -> None:
    """Add a platform. A duplicate id is a programming error, so it raises."""
    if adapter.id in _adapters:
        raise ValueError(f"Platform already registered: {adapter.id}")
    _adapters[adapter.id] = adapter


def get_adapter(platform: str) -> ChannelAdapter:
    """Return the adapter for `platform`, or raise UnsupportedPlatformError."""
    try:
        return _adapters[platform]
    except KeyError:
        raise UnsupportedPlatformError(f"Unsupported platform: {platform}") from None


def all_adapters() -> list[ChannelAdapter]:
    """Every platform, in registration order (the order the UI shows)."""
    return list(_adapters.values())


def platform_ids() -> list[str]:
    return list(_adapters)


register(TelegramAdapter())
register(DiscordAdapter())

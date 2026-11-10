"""Single entry point for sending text to a (platform, destination).

The notification subsystem's only outbound IO path. Platform behavior lives in
the adapters; this delegates so callers that hold a platform id need no more.
Errors are raised to the caller (dispatcher, alerts, API test-send), which
decides what to log or surface; adapters make them safe to log.

Destination values are never logged by these helpers.
"""

from __future__ import annotations

from notifications.adapters.base import DeliveryResult, NotificationConfigError
from notifications.registry import get_adapter

__all__ = ["NotificationConfigError", "send_to"]


def send_to(platform: str, destination: str, content: str) -> DeliveryResult:
    """Deliver `content` to a single (platform, destination)."""
    return get_adapter(platform).send(destination, content)

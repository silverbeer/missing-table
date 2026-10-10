"""Admin ping when a new invite request arrives (SB-1313).

A request sitting unseen in the admin panel is a prospective user waiting on
nobody. This sends one short message to the operator's Telegram chat and/or
Discord channel per *new* `invite_requests` row; honeypot hits and duplicate
pending submissions never get here.

Destinations are the operator's, not a club's, so they come from env rather
than `club_notifications`:

- `MT_ADMIN_TELEGRAM_CHAT_ID` — same chat the ingest alerts use. Sent with the
  existing `TELEGRAM_BOT_TOKEN`.
- `MT_ADMIN_DISCORD_WEBHOOK_URL` — a webhook into an admin-only channel.

Either, both or neither may be set. Neither is a quiet no-op.
"""

from __future__ import annotations

import os

import structlog

from notifications.senders import send_to

logger = structlog.get_logger()

TELEGRAM_CHAT_ID_ENV = "MT_ADMIN_TELEGRAM_CHAT_ID"
DISCORD_WEBHOOK_ENV = "MT_ADMIN_DISCORD_WEBHOOK_URL"


def _admin_destinations() -> list[tuple[str, str]]:
    destinations = []
    chat_id = os.getenv(TELEGRAM_CHAT_ID_ENV)
    if chat_id:
        destinations.append(("telegram", chat_id))
    webhook = os.getenv(DISCORD_WEBHOOK_ENV)
    if webhook:
        destinations.append(("discord", webhook))
    return destinations


def _defang(value: str) -> str:
    # Name and team are typed by the public. A zero-width space after "@"
    # keeps "@everyone" in a name from pinging a whole Discord server.
    return value.replace("@", "@​")


def format_invite_request_alert(name: str, team: str | None, wants_ios_beta: bool) -> str:
    base_url = os.getenv("APP_BASE_URL", "https://missingtable.com").rstrip("/")
    lines = [
        "📬 New MT invite request",
        f"Name: {_defang(name)}",
        f"Team: {_defang(team) if team else '—'}",
    ]
    if wants_ios_beta:
        lines.append("iPhone beta: yes")
    # The admin panel has no URL deep link; Requests is its first section.
    lines.append(f"Review: {base_url}/ (Admin → Requests)")
    return "\n".join(lines)


def notify_new_invite_request(name: str, team: str | None, wants_ios_beta: bool = False) -> int:
    """Ping each configured admin destination. Returns how many sends succeeded.

    Never raises: this runs after the requester already has their response,
    and a broken ping must not turn into a failed request or a noisy task.
    """
    destinations = _admin_destinations()
    if not destinations:
        logger.info(
            "Invite request not pinged — neither %s nor %s is set",
            TELEGRAM_CHAT_ID_ENV,
            DISCORD_WEBHOOK_ENV,
        )
        return 0

    try:
        content = format_invite_request_alert(name, team, wants_ios_beta)
    except Exception:
        logger.exception("Could not format invite request alert")
        return 0

    sent = 0
    for platform, destination in destinations:
        try:
            send_to(platform, destination, content)
            sent += 1
        except Exception:
            # Destination values are never logged.
            logger.exception("Could not ping admins about invite request", platform=platform)
    return sent

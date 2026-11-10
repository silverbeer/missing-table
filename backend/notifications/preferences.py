"""User notification preference defaults (SB-57).

The `user_notification_preferences` table stores per-user opt-in flags for each
push notification event type. Missing rows fall back to these defaults — so
existing users keep the current behavior with zero migration backfill.

Defaults intentionally mirror the pre-SB-57 behavior:
  - kickoff/goal/halftime/fulltime → ON (the events that fire today).
  - yellow_card/red_card           → OFF (previously hard-coded skip in
                                          dispatcher.py).

Keeping defaults in code (not in the DB CHECK / DEFAULT clause) means we can
adjust them later without a migration.
"""

from __future__ import annotations

EVENT_TYPES: tuple[str, ...] = (
    "kickoff",
    "goal",
    "halftime",
    "fulltime",
    "yellow_card",
    "red_card",
)

# Events only a squad's player channel receives (SB-1610). Never a fan channel,
# a club channel, or anyone's personal push: they are content for the players.
# Kickoff reminders join this list once the delivery worker (SB-1604) can send
# at a set time; see docs/08-integrations/live-match-notifications.md.
PLAYER_EVENT_TYPES: tuple[str, ...] = ("lineup",)

# Every event a chat channel can be limited to, in display order.
CHANNEL_EVENT_TYPES: tuple[str, ...] = EVENT_TYPES + PLAYER_EVENT_TYPES


def is_player_only(event_type: str) -> bool:
    return event_type in PLAYER_EVENT_TYPES


# What setup screens call each event. Keys match CHANNEL_EVENT_TYPES exactly.
EVENT_LABELS: dict[str, str] = {
    "kickoff": "Kickoff",
    "goal": "Goals",
    "halftime": "Halftime",
    "fulltime": "Full time",
    "yellow_card": "Yellow cards",
    "red_card": "Red cards",
    "lineup": "Lineup posted",
}

DEFAULT_PREFERENCES: dict[str, bool] = {
    "kickoff": True,
    "goal": True,
    "halftime": True,
    "fulltime": True,
    "yellow_card": False,
    "red_card": False,
}


def merge_with_defaults(stored: dict[str, bool] | None) -> dict[str, bool]:
    """Return a complete prefs dict, with `stored` overriding defaults."""
    return {**DEFAULT_PREFERENCES, **(stored or {})}


def validate_event_type(event_type: str) -> bool:
    return event_type in EVENT_TYPES

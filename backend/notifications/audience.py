"""Who a channel may reach (SB-1602). Pure functions, no I/O.

Player channels are for squads old enough to use the platform. An age group that
can't be read as "U<number>" never qualifies: this fails closed.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from notifications.adapters.base import ChannelAdapter

MIN_PLAYER_AGE = 14

_AGE_GROUP = re.compile(r"^U(\d+)$")


def age_number(age_group_name: str | None) -> int | None:
    """14 for "U14"; None for anything else, including a test age group."""
    match = _AGE_GROUP.match(age_group_name or "")
    return int(match.group(1)) if match else None


def players_allowed_at(age_group_name: str | None) -> bool:
    """Whether a match at this age group may reach a player channel."""
    age = age_number(age_group_name)
    return age is not None and age >= MIN_PLAYER_AGE


def player_channel_problem(adapter: ChannelAdapter, age_group_name: str | None) -> str | None:
    """Why this platform can't host this player channel, or None if it can.

    `age_group_name` is the squad's, or None for a club channel, which spans
    every age group from MIN_PLAYER_AGE up and so must suit the youngest.
    """
    if adapter.min_player_age is None:
        return f"{adapter.label} can't be used for player channels"
    if age_group_name is None:
        youngest = MIN_PLAYER_AGE
    else:
        youngest = age_number(age_group_name)
        if not players_allowed_at(age_group_name) or youngest is None:
            return f"Player channels are only available from U{MIN_PLAYER_AGE}"
    if youngest < adapter.min_player_age:
        return f"{adapter.label} player channels are only available from U{adapter.min_player_age}"
    return None

"""Stable identities for match events (SB-1603).

The delivery ledger allows one post per (channel, event_key), so a key must be
the same every time the same event is announced and different for different
events. Pure, so those rules are testable without a database.
"""

from __future__ import annotations


def recorded_event_key(match_id: int, event_id: int) -> str:
    """A goal or card, identified by its `match_events` row."""
    return f"match:{match_id}:event:{event_id}"


def clock_event_key(match_id: int, event_type: str) -> str:
    """Kickoff or halftime, which happen once per match."""
    return f"match:{match_id}:{event_type}"


def fulltime_event_key(match_id: int, home_score: int | None, away_score: int | None) -> str:
    """Full time, keyed by score.

    Live scoring and a later match write announcing the same result share a
    key, so it posts once. A corrected score is a new key, so it posts again.
    A live match with no goals can still hold NULL scores, which is 0-0 here.
    """
    return f"match:{match_id}:fulltime:{home_score or 0}-{away_score or 0}"

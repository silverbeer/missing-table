"""Detect when a match write represents a *new final score* worth notifying.

Used by the admin/skill match-write endpoints (tournament create/update, and
the regular league update/patch path) to decide whether to fan a "fulltime"
notification out to followers. (SB-77)

This is a pure function with no I/O so it can be unit-tested directly.

A write qualifies as a notify-worthy scoring event when, AFTER the write, the
match has both a home and away score, AND either:

  - the (home, away) score pair actually changed vs. before the write
    (covers scheduled→scored, and an admin correcting a wrong score), or
  - the match newly transitioned into a completed status carrying a score
    (covers the rare case where the score was already present but the match
    only just got marked completed).

It deliberately does NOT fire when:

  - the write only touched metadata (round / group / order / kickoff / team
    identity) and left the score untouched — the common upsert-loop case, and
  - an identical score is re-submitted (idempotent re-runs of the skill), and
  - the match has no score yet, or is still in a non-completed state.
"""

from __future__ import annotations


def _status(match: dict) -> str | None:
    """Read the status under either key the row may expose.

    Raw `matches` rows use `match_status`; some joined read shapes alias it to
    `status`. Accept both so detection is robust to which path produced the dict.
    """
    return match.get("match_status") or match.get("status")


def _scores(match: dict) -> tuple[int | None, int | None]:
    return match.get("home_score"), match.get("away_score")


def is_new_final_score(old: dict | None, new: dict | None) -> bool:
    """Return True if `new` represents a fresh final score relative to `old`.

    `old` is the match row before the write (None for a create); `new` is the
    row after the write. Both are plain dicts straight off the matches table.
    """
    if not new:
        return False

    new_home, new_away = _scores(new)
    if new_home is None or new_away is None:
        return False  # no complete score yet — nothing to announce

    new_status = _status(new)
    # If a status is present it must be 'completed'; a partial/in-progress
    # write is not a final score. (None status is tolerated — tournament rows
    # may omit it; the score-pair check below still gates the notification.)
    if new_status is not None and new_status != "completed":
        return False

    old = old or {}
    old_home, old_away = _scores(old)
    old_status = _status(old)

    if (old_home, old_away) != (new_home, new_away):
        return True  # score newly set or corrected

    # Same score, but only just marked completed → fire once. Otherwise it's an
    # unchanged score on an already-completed match — no-op.
    return old_status != "completed" and new_status == "completed"

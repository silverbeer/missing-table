"""Re-time events after a clock correction (SB-1449).

Pure: no database. When a manager undoes halftime or the second half, every
event logged since the undone moment carries a minute read off the wrong
clock. Match #10106 went to the second half 14' in, so a goal at ~41' was
stamped 71'. This works out what each of those events should have read on
the corrected clock.

Each event is placed by its `created_at`, on the same clock the Android app
shows (whole minutes elapsed, the second half counting on from
`half_duration`, stoppage beyond each half as `extra_time`). An event synced
late from an offline phone carries its sync time, not its tap time, so it
can land a few minutes late — still far closer than the wrong clock's minute.
"""

from collections.abc import Iterable
from datetime import datetime


def _parse(ts: str | datetime | None) -> datetime | None:
    if ts is None or isinstance(ts, datetime):
        return ts
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def minute_at(
    at: datetime,
    kickoff_time: str | datetime,
    halftime_start: str | datetime | None,
    second_half_start: str | datetime | None,
    half_duration: int,
) -> tuple[int, int]:
    """The (match_minute, extra_time) the clock read at `at`.

    Mirrors the Android LiveClock: at half time the clock reads
    `half_duration`; a minute past either half's length is stoppage.
    """
    kickoff = _parse(kickoff_time)
    halftime = _parse(halftime_start)
    second_half = _parse(second_half_start)

    if second_half is not None and at >= second_half:
        minute = int((at - second_half).total_seconds() // 60) + half_duration
        cap = 2 * half_duration
    elif halftime is not None and at >= halftime:
        return half_duration, 0
    else:
        minute = int((at - kickoff).total_seconds() // 60)
        cap = half_duration

    minute = max(minute, 0)
    if minute > cap:
        return cap, minute - cap
    return minute, 0


def retime_events(
    events: Iterable[dict],
    since: str | datetime,
    kickoff_time: str | datetime,
    halftime_start: str | datetime | None,
    second_half_start: str | datetime | None,
    half_duration: int,
) -> list[tuple[int, int, int]]:
    """Corrected minutes for events logged since a clock correction's cut-off.

    Args:
        events: match events (deleted ones already filtered out); only those
            with a `match_minute` are timed — status changes and chat aren't.
        since: the clock timestamp the correction cleared; events before it
            were stamped on a clock that was right at the time.
        kickoff_time, halftime_start, second_half_start, half_duration: the
            clock as it stands after the correction.

    Returns:
        (event_id, match_minute, extra_time) for each event whose minute
        changes, oldest first.
    """
    cutoff = _parse(since)
    changes: list[tuple[datetime, int, int, int]] = []
    for event in events:
        if event.get("match_minute") is None or not event.get("created_at"):
            continue
        created = _parse(event["created_at"])
        if created < cutoff:
            continue
        minute, extra = minute_at(created, kickoff_time, halftime_start, second_half_start, half_duration)
        if (event["match_minute"], event.get("extra_time") or 0) != (minute, extra):
            changes.append((created, event["id"], minute, extra))
    changes.sort()
    return [(event_id, minute, extra) for _, event_id, minute, extra in changes]

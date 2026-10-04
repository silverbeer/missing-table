"""Minutes played, derived from a live-scored match's timeline (SB-1227).

Pure: no database, no clock. The caller supplies who started (recorded at
kickoff, SB-671) and the match's events; this works out who was on the pitch
for how long.

Minutes are counted on the nominal match clock — `2 * half_duration` — not
wall time. Stoppage is ignored: a sub at 45+3 came on at 45, and a starter who
plays the whole match played 90, however long the referee added.
"""

from collections.abc import Iterable


def compute_minutes_played(
    starter_ids: Iterable[int],
    events: Iterable[dict],
    half_duration: int,
) -> dict[int, int]:
    """Return minutes played for every player who appeared.

    Args:
        starter_ids: players on the pitch at kickoff
        events: match events; only `substitution` (player_id on, player_out_id
            off) and `red_card` (player_id off) are read, each needing a
            `match_minute`. Deleted events must already be filtered out.
        half_duration: minutes per half

    Returns:
        {player_id: minutes} for each starter and each player brought on —
        including a player brought on at the final whistle, who appeared for 0.
    """
    full_time = 2 * half_duration
    on_since: dict[int, int] = dict.fromkeys(starter_ids, 0)
    minutes: dict[int, int] = dict.fromkeys(on_since, 0)

    def clamp(minute: int) -> int:
        return max(0, min(minute, full_time))

    def take_off(player_id: int | None, minute: int) -> None:
        if player_id in on_since:
            minutes[player_id] += minute - on_since.pop(player_id)

    timed = [e for e in events if e.get("match_minute") is not None]
    # Ties within a minute keep their recorded order.
    timed.sort(key=lambda e: (e["match_minute"], e.get("created_at") or ""))

    for event in timed:
        minute = clamp(event["match_minute"])
        if event.get("event_type") == "substitution":
            take_off(event.get("player_out_id"), minute)
            player_in = event.get("player_id")
            if player_in is not None and player_in not in on_since:
                on_since[player_in] = minute
                minutes.setdefault(player_in, 0)
        elif event.get("event_type") == "red_card":
            take_off(event.get("player_id"), minute)

    for player_id in list(on_since):
        take_off(player_id, full_time)

    return minutes

"""Plain-text formatters for live-match notifications.

Pure functions — no I/O. The same text is sent to both Telegram and Discord.
Telegram senders apply MarkdownV2 escaping at send time; Discord accepts
plain text as-is.

All timestamps are rendered in the home club's timezone.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo  # noqa: TC003 — used at runtime for tz conversion

# Event type → emoji prefix
_EMOJI = {
    "kickoff": "⏱",
    "goal": "⚽",
    "yellow_card": "🟨",
    "red_card": "🟥",
    "halftime": "⏸",
    "fulltime": "🏁",
}


def _matchup_line(match: dict) -> str:
    return f"{match.get('home_team_name', 'Home')} vs {match.get('away_team_name', 'Away')}"


def _score_line(match: dict) -> str:
    home = match.get("home_score") or 0
    away = match.get("away_score") or 0
    return f"{match.get('home_team_name', 'Home')} {home} - {away} {match.get('away_team_name', 'Away')}"


def _minute_str(event: dict) -> str:
    """Return a match-minute label like "34'" or "90+3'"."""
    minute = event.get("match_minute")
    extra = event.get("extra_time") or 0
    if minute is None:
        return ""
    if extra:
        return f"{minute}+{extra}'"
    return f"{minute}'"


def _tag(match: dict) -> str:
    """Compact league/age-group tag line, e.g. 'MLS Next U14 · Northeast'."""
    parts: list[str] = []
    age_group = match.get("age_group_name")
    division = match.get("division_name")
    if age_group:
        parts.append(str(age_group))
    if division and division != "Unknown":
        parts.append(str(division))
    return " · ".join(parts)


def _kickoff_time_str(match: dict, tz: ZoneInfo) -> str:
    raw = match.get("scheduled_kickoff") or match.get("kickoff_time")
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return ""
    local = dt.astimezone(tz)
    return local.strftime("%-I:%M %p %Z").strip()


def format_kickoff(match: dict, tz: ZoneInfo) -> str:
    """Match has kicked off."""
    lines = [f"{_EMOJI['kickoff']} KICKOFF — {_matchup_line(match)}"]
    tag = _tag(match)
    if tag:
        lines.append(tag)
    time_str = _kickoff_time_str(match, tz)
    if time_str:
        lines.append(time_str)
    return "\n".join(lines)


def format_goal(event: dict, match: dict, tz: ZoneInfo) -> str:
    """A goal was scored. `event` carries team_id, player_name, minute, extra."""
    scoring_team_id = event.get("team_id")
    if scoring_team_id == match.get("home_team_id"):
        scoring_team = match.get("home_team_name", "Home")
    elif scoring_team_id == match.get("away_team_id"):
        scoring_team = match.get("away_team_name", "Away")
    else:
        scoring_team = "Unknown"

    player = event.get("player_name") or "Unknown player"
    minute = _minute_str(event)
    minute_suffix = f" {minute}" if minute else ""

    lines = [f"{_EMOJI['goal']} GOAL — {_matchup_line(match)}"]
    lines.append(f"{player} ({scoring_team}){minute_suffix}")
    lines.append(_score_line(match))
    return "\n".join(lines)


def format_card(event: dict, match: dict, tz: ZoneInfo) -> str:
    """A yellow or red card was shown."""
    card_type = event.get("card_type", "yellow_card")
    emoji = _EMOJI.get(card_type, "🟨")
    label = "Red card" if card_type == "red_card" else "Yellow card"

    carded_team_id = event.get("team_id")
    if carded_team_id == match.get("home_team_id"):
        team = match.get("home_team_name", "Home")
    elif carded_team_id == match.get("away_team_id"):
        team = match.get("away_team_name", "Away")
    else:
        team = "Unknown"

    player = event.get("player_name") or "Unknown player"
    minute = _minute_str(event)
    minute_suffix = f" {minute}" if minute else ""

    lines = [f"{emoji} {label} — {_matchup_line(match)}"]
    lines.append(f"{player} ({team}){minute_suffix}")
    return "\n".join(lines)


def format_halftime(match: dict, tz: ZoneInfo) -> str:
    """Halftime has begun."""
    lines = [f"{_EMOJI['halftime']} HALFTIME — {_matchup_line(match)}"]
    lines.append(_score_line(match))
    return "\n".join(lines)


def format_fulltime(match: dict, tz: ZoneInfo) -> str:
    """Final whistle."""
    lines = [f"{_EMOJI['fulltime']} FULL TIME — {_matchup_line(match)}"]
    lines.append(_score_line(match))
    tag = _tag(match)
    if tag:
        lines.append(tag)
    return "\n".join(lines)


EVENT_FORMATTERS = {
    "kickoff": format_kickoff,
    "halftime": format_halftime,
    "fulltime": format_fulltime,
}


def format_event(event_type: str, match: dict, extra: dict | None, tz: ZoneInfo) -> str | None:
    """Entry point: dispatch to the right formatter. Returns None if unsupported."""
    if event_type == "goal":
        return format_goal(extra or {}, match, tz)
    if event_type in {"yellow_card", "red_card"}:
        merged = {**(extra or {}), "card_type": event_type}
        return format_card(merged, match, tz)
    formatter = EVENT_FORMATTERS.get(event_type)
    if formatter is None:
        return None
    return formatter(match, tz)

"""Drift guard for Supabase session timeouts (SB-120).

Users were force-logged-out roughly daily (distinct from the hourly SB-115
bug). Root cause was a short session timeout: the `[auth.sessions]` block must
express the SB-78 "30-day idle session" intent — a long `inactivity_timeout`
and **no** `timebox` (a timebox force-logs-out on a fixed schedule regardless
of activity, which is exactly the daily-logout failure mode).

This pins the *local* config. Production session timeouts live in the Supabase
Cloud dashboard (Auth → Sessions) and must be kept in sync — see
docs/03-architecture/authentication.md.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

# backend/tests/unit/<this file> -> repo root is three parents up from backend/
_CONFIG_PATH = Path(__file__).resolve().parents[3] / "supabase" / "config.toml"

# 30 days, in the hour-based duration units the Supabase CLI accepts.
_THIRTY_DAYS_HOURS = 720


def _parse_hours(duration: str) -> int:
    """Parse a Supabase duration string like '720h' into whole hours."""
    assert duration.endswith("h"), f"expected an hour-based duration, got {duration!r}"
    return int(duration[:-1])


def _sessions() -> dict:
    with _CONFIG_PATH.open("rb") as fh:
        config = tomllib.load(fh)
    return config.get("auth", {}).get("sessions", {})


class TestSessionConfig:
    def test_config_file_exists(self):
        assert _CONFIG_PATH.is_file(), f"missing {_CONFIG_PATH}"

    def test_sessions_block_present(self):
        assert _sessions(), "[auth.sessions] block must be set (uncommented), not left to defaults"

    def test_inactivity_timeout_is_at_least_30_days(self):
        sessions = _sessions()
        assert "inactivity_timeout" in sessions, "inactivity_timeout must be pinned (SB-78 30-day idle)"
        assert _parse_hours(sessions["inactivity_timeout"]) >= _THIRTY_DAYS_HOURS

    def test_no_short_timebox(self):
        # A timebox force-logs-out every session on a fixed schedule regardless
        # of activity — the SB-120 daily-logout failure mode. It must be unset,
        # or no shorter than the 30-day idle window.
        sessions = _sessions()
        if "timebox" in sessions:
            assert _parse_hours(sessions["timebox"]) >= _THIRTY_DAYS_HOURS, (
                "timebox would force-logout active users (SB-120); leave it unset"
            )

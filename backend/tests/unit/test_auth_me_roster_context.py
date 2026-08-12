"""Unit tests for the roster context on /api/auth/me (SB-599).

The endpoint used to flatten each current-team entry down to
`{team_id, team, season}`, so the frontend had no way to know which age group /
league / division the signed-in viewer actually plays in and fell back to the
app-wide U14 default. These cover the widened payload and the role gate.

No database — `player_dao` is patched.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.backend]


# Gabe's actual prod row (SB-599): IFA, U15, Homegrown, Northeast, 2026-2027.
CURRENT_ROW = {
    "team_id": 19,
    "season_id": 184,
    "team": {"id": 19, "name": "IFA", "club": {"id": 1, "name": "IFA"}},
    "season": {"id": 184, "name": "2026-2027"},
    "age_group": {"id": 3, "name": "U15"},
    "league": {"id": 1, "name": "Homegrown"},
    "division": {"id": 1, "name": "Northeast"},
}

PLAYER_PROFILE = {
    "role": "team-player",
    "team_id": 19,
    "club_id": 1,
    "username": "gabe35",
    "display_name": "Gabe",
}


def _call_me(profile: dict, teams: list[dict]) -> dict:
    """Invoke the endpoint with player_dao patched, returning the profile payload."""
    import app as app_module

    with (
        patch.object(app_module.player_dao, "get_user_profile_with_relationships", return_value=profile),
        patch.object(app_module.player_dao, "get_all_current_player_teams", return_value=teams),
    ):
        result = asyncio.run(
            app_module.get_current_user_info(current_user={"user_id": "u-1", "email": "gabe@example.com"})
        )
    return result["user"]["profile"]


class TestCurrentTeamsRosterContext:
    def test_exposes_age_group_league_and_division(self):
        entry = _call_me(PLAYER_PROFILE, [CURRENT_ROW])["current_teams"][0]

        assert entry["age_group"] == {"id": 3, "name": "U15"}
        assert entry["league"] == {"id": 1, "name": "Homegrown"}
        assert entry["division"] == {"id": 1, "name": "Northeast"}

    def test_still_carries_team_and_season(self):
        entry = _call_me(PLAYER_PROFILE, [CURRENT_ROW])["current_teams"][0]

        assert entry["team_id"] == 19
        assert entry["team"]["name"] == "IFA"
        assert entry["season"]["id"] == 184

    def test_missing_roster_context_is_null_not_an_error(self):
        # Older history rows predate age_group/league/division being populated.
        bare = {"team_id": 19, "team": {"id": 19, "name": "IFA"}, "season": {"id": 184}}

        entry = _call_me(PLAYER_PROFILE, [bare])["current_teams"][0]

        assert entry["age_group"] is None
        assert entry["league"] is None
        assert entry["division"] is None

    def test_team_managers_get_roster_context_too(self):
        # Personalized defaults are not player-only: any non-admin with a roster
        # row should get them.
        manager = {**PLAYER_PROFILE, "role": "team-manager"}

        entry = _call_me(manager, [CURRENT_ROW])["current_teams"][0]

        assert entry["age_group"]["id"] == 3

    def test_admins_get_no_current_teams(self):
        # Admins browse every age group, so there is nothing to personalize and
        # no reason to pay for the extra query.
        admin = {**PLAYER_PROFILE, "role": "admin"}

        assert _call_me(admin, [CURRENT_ROW])["current_teams"] == []

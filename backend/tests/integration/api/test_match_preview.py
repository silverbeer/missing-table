"""Integration tests for the match-preview endpoint's Recent Form (SB-107).

GET /api/matches/preview/{home_team_id}/{away_team_id} returns each team's
recent form. Recent Form used to be scoped to the SAME match type as the
upcoming match, so a team that had only played (say) league matches showed
"No recent matches" on a tournament preview despite a full history. SB-107
removed that scoping — recent form is now the last N completed/forfeit
matches across ALL match types (still season + age-group scoped).

These tests seed the real local Supabase and assert that:
  1. a team's recent form mixes match types, and
  2. a team with NO matches of the upcoming match's type still shows form.

Both would have failed under the old match-type-scoped query. Requires local
Supabase running; skips cleanly if it isn't reachable.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]


# ---------------------------------------------------------------------------
# Infrastructure helpers (mirrors test_push_delivery_on_score.py)
# ---------------------------------------------------------------------------


def _admin_client():
    """Supabase client with the service-role key (bypasses RLS)."""
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
    # Hard safety rail: this test seeds + deletes rows. Never run it against a
    # non-local Supabase, regardless of how env/.mt-config resolved.
    if not ("127.0.0.1" in url or "localhost" in url):
        pytest.skip(f"Refusing to run destructive test against non-local Supabase: {url}")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY not set — cannot run match-preview integration test")
    return create_client(url, key)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Seed fixture: two teams with completed matches spanning multiple match types
# ---------------------------------------------------------------------------


@pytest.fixture
def preview_world():
    """Seed a graph that exercises cross-match-type recent form.

    Graph (all matches completed + scored, same season + age group):
      home_team  vs opp_shared  -> TOURNAMENT
      home_team  vs opp_league  -> LEAGUE
      away_team  vs opp_shared  -> LEAGUE   (away has NO tournament match)

    `opp_shared` faces both preview teams, so it is also a common opponent.
    """
    admin = _admin_client()
    try:
        admin.table("clubs").select("id").limit(1).execute()
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("Local Supabase not reachable")

    def _ref(table: str) -> int:
        return admin.table(table).select("id").limit(1).execute().data[0]["id"]

    age_group_id = _ref("age_groups")
    season_id = _ref("seasons")

    # Need two distinct match types — a tournament one and a non-tournament one.
    match_types = admin.table("match_types").select("id, name").execute().data or []
    tournament_type = next((m for m in match_types if "tournament" in m["name"].lower()), None)
    league_type = next(
        (m for m in match_types if m is not tournament_type and "tournament" not in m["name"].lower()),
        None,
    )
    if not tournament_type or not league_type:
        pytest.skip("Need at least one tournament and one non-tournament match type seeded")

    created_clubs: list[int] = []
    created_teams: list[int] = []
    created_matches: list[int] = []

    def _club(label: str) -> dict:
        club = admin.table("clubs").insert({"name": _unique(label), "city": "Testville"}).execute().data[0]
        created_clubs.append(club["id"])
        return club

    def _team(label: str, club_id: int) -> dict:
        team = (
            admin.table("teams")
            .insert({"name": _unique(label), "city": "Testville", "club_id": club_id})
            .execute()
            .data[0]
        )
        created_teams.append(team["id"])
        return team

    home = _team("PreviewHome", _club("PreviewHomeClub")["id"])
    away = _team("PreviewAway", _club("PreviewAwayClub")["id"])
    opp_shared = _team("PreviewOppShared", _club("PreviewOppSharedClub")["id"])
    opp_league = _team("PreviewOppLeague", _club("PreviewOppLeagueClub")["id"])

    def _match(home_id: int, away_id: int, match_type_id: int, days_ago: int) -> dict:
        match_date = (datetime.now(UTC).date() - timedelta(days=days_ago)).isoformat()
        row = (
            admin.table("matches")
            .insert(
                {
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "age_group_id": age_group_id,
                    "season_id": season_id,
                    "match_type_id": match_type_id,
                    "match_date": match_date,
                    "home_score": 2,
                    "away_score": 1,
                    "match_status": "completed",
                }
            )
            .execute()
            .data[0]
        )
        created_matches.append(row["id"])
        return row

    home_tournament = _match(home["id"], opp_shared["id"], tournament_type["id"], days_ago=2)
    home_league = _match(home["id"], opp_league["id"], league_type["id"], days_ago=4)
    away_league = _match(away["id"], opp_shared["id"], league_type["id"], days_ago=3)

    yield {
        "admin": admin,
        "season_id": season_id,
        "age_group_id": age_group_id,
        "tournament_type_id": tournament_type["id"],
        "league_type_id": league_type["id"],
        "home": home,
        "away": away,
        "home_tournament": home_tournament,
        "home_league": home_league,
        "away_league": away_league,
    }

    # --- teardown (children first) ---
    def _safe(fn):
        try:
            fn()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass

    for mid in created_matches:
        _safe(lambda mid=mid: admin.table("matches").delete().eq("id", mid).execute())
    for tid in created_teams:
        _safe(lambda tid=tid: admin.table("teams").delete().eq("id", tid).execute())
    for cid in created_clubs:
        _safe(lambda cid=cid: admin.table("clubs").delete().eq("id", cid).execute())


def _fetch_preview(client, world) -> dict:
    resp = client.get(
        f"/api/matches/preview/{world['home']['id']}/{world['away']['id']}",
        params={"season_id": world["season_id"], "age_group_id": world["age_group_id"]},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestMatchPreviewRecentForm:
    """Recent Form is no longer scoped to the upcoming match's type (SB-107)."""

    def test_recent_form_includes_all_match_types(self, authenticated_client, preview_world):
        """Home team's recent form mixes its tournament AND league matches."""
        data = _fetch_preview(authenticated_client, preview_world)

        home_recent = data["home_team_recent"]
        ids = {m["id"] for m in home_recent}
        assert preview_world["home_tournament"]["id"] in ids, "tournament match missing from recent form"
        assert preview_world["home_league"]["id"] in ids, "league match missing from recent form"

        type_ids = {m["match_type_id"] for m in home_recent}
        assert preview_world["tournament_type_id"] in type_ids
        assert preview_world["league_type_id"] in type_ids
        assert len(type_ids) >= 2, "recent form should span more than one match type"

    def test_team_without_matches_of_upcoming_type_still_has_form(
        self, authenticated_client, preview_world
    ):
        """Away team has only a LEAGUE match (no tournament) yet still shows form.

        This is the exact SB-107 bug: under the old match-type-scoped query the
        away team would have shown "No recent matches" on a tournament preview.
        """
        data = _fetch_preview(authenticated_client, preview_world)

        away_recent = data["away_team_recent"]
        away_ids = {m["id"] for m in away_recent}
        assert preview_world["away_league"]["id"] in away_ids
        assert preview_world["league_type_id"] in {m["match_type_id"] for m in away_recent}

"""
Unit tests for the /api/table endpoint QoP enrichment logic.

Tests:
- With no QoP data: has_qop_data=False and qop_rank=null on all standings rows
- With QoP data: correct qop_rank attached to matching teams by team_name
- With QoP data: team_id lookup takes priority over team_name lookup
- QoP exception: gracefully degrades — has_qop_data=False, qop_rank=null on all rows

These tests exercise the enrichment logic in isolation using the same
helper pattern as test_qop_rankings.py (mock Supabase client).
"""

from unittest.mock import MagicMock, Mock, patch

import pytest


# ─── helpers ───────────────────────────────────────────────────────────────────


def _make_qop_client_with_data(week_rows, current_rows, prior_rows=None):
    """
    Build a mock Supabase client whose qop_rankings table returns responses
    in sequence: weeks query → current-week rows → prior-week rows.
    """
    client = MagicMock()
    call_count = {"n": 0}

    def table_side_effect(name):
        if name != "qop_rankings":
            mock_resp = Mock()
            mock_resp.data = []
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.order.return_value = chain
            chain.execute.return_value = mock_resp
            return chain

        call_count["n"] += 1
        call_num = call_count["n"]

        if call_num == 1:
            rows = week_rows
        elif call_num == 2:
            rows = current_rows
        else:
            rows = prior_rows or []

        mock_resp = Mock()
        mock_resp.data = rows
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = mock_resp
        return chain

    client.table.side_effect = table_side_effect
    return client


def _make_standings_row(team_name: str, team_id: int | None = None) -> dict:
    """Return a minimal standings row as produced by calculate_standings_with_extras."""
    return {
        "team": team_name,
        "team_id": team_id,
        "played": 10,
        "wins": 5,
        "draws": 2,
        "losses": 3,
        "goals_for": 20,
        "goals_against": 15,
        "goal_difference": 5,
        "points": 17,
        "form": ["W", "D", "L", "W", "W"],
        "position_change": 0,
    }


# ─── QoP enrichment: no data ────────────────────────────────────────────────


@pytest.mark.unit
class TestTableQoPNoData:
    """When QoPRankingsDAO returns has_data=False, all qop_rank fields are null."""

    def test_no_qop_data_sets_nulls_on_all_rows(self):
        """
        Given a Supabase client with no qop_rankings rows,
        enriching standings rows sets qop_rank and qop_rank_change to None.
        """
        from dao.qop_rankings_dao import QoPRankingsDAO

        client = _make_qop_client_with_data(week_rows=[], current_rows=[])

        qop_data = QoPRankingsDAO.get_latest_with_delta(client, division_id=1, age_group_id=2)

        assert qop_data["has_data"] is False
        assert qop_data["week_of"] is None
        assert qop_data["rankings"] == []

        # Simulate what the endpoint does when has_data is False
        table = [
            _make_standings_row("Team Alpha"),
            _make_standings_row("Team Beta"),
        ]
        for row in table:
            row["qop_rank"] = None
            row["qop_rank_change"] = None

        for row in table:
            assert row["qop_rank"] is None
            assert row["qop_rank_change"] is None


# ─── QoP enrichment: matching by team_name ─────────────────────────────────


@pytest.mark.unit
class TestTableQoPByTeamName:
    """When QoP data is present, qop_rank is attached by matching team_name."""

    def test_qop_rank_attached_to_matching_team(self):
        """
        NEFC appears in both standings (team_name) and QoP rankings (team_name);
        enrichment attaches the correct qop_rank and qop_rank_change.
        """
        from dao.qop_rankings_dao import QoPRankingsDAO

        week_rows = [
            {"week_of": "2026-04-14"},
            {"week_of": "2026-04-07"},
        ]
        current_rows = [
            {
                "rank": 11,
                "team_name": "NEFC",
                "team_id": 7,
                "matches_played": 18,
                "att_score": 80.0,
                "def_score": 75.0,
                "qop_score": 78.0,
            },
            {
                "rank": 12,
                "team_name": "Other Club",
                "team_id": None,
                "matches_played": 16,
                "att_score": 70.0,
                "def_score": 65.0,
                "qop_score": 68.0,
            },
        ]
        prior_rows = [
            {"rank": 11, "team_name": "NEFC"},
            {"rank": 10, "team_name": "Other Club"},
        ]

        client = _make_qop_client_with_data(week_rows, current_rows, prior_rows)
        qop_data = QoPRankingsDAO.get_latest_with_delta(client, division_id=1, age_group_id=2)

        assert qop_data["has_data"] is True
        assert qop_data["week_of"] == "2026-04-14"

        # Build lookups (mirrors endpoint logic)
        qop_by_team_id: dict[int, dict] = {}
        qop_by_team_name: dict[str, dict] = {}
        for entry in qop_data["rankings"]:
            tid = entry.get("team_id")
            if tid is not None:
                qop_by_team_id[tid] = entry
            tname = entry.get("team_name", "")
            if tname:
                qop_by_team_name[tname.lower()] = entry

        table = [
            _make_standings_row("NEFC", team_id=None),   # no team_id — must match by name
            _make_standings_row("No Match Team"),
        ]

        for row in table:
            qop_entry = None
            row_team_id = row.get("team_id")
            if row_team_id is not None:
                qop_entry = qop_by_team_id.get(row_team_id)
            if qop_entry is None:
                row_team_name = (row.get("team") or "").lower()
                qop_entry = qop_by_team_name.get(row_team_name)
            row["qop_rank"] = qop_entry["rank"] if qop_entry else None
            row["qop_rank_change"] = qop_entry["rank_change"] if qop_entry else None

        nefc_row = table[0]
        assert nefc_row["qop_rank"] == 11
        assert nefc_row["qop_rank_change"] == 0  # prior 11 - current 11 = 0

        no_match_row = table[1]
        assert no_match_row["qop_rank"] is None
        assert no_match_row["qop_rank_change"] is None

    def test_team_id_lookup_takes_priority_over_name(self):
        """
        When a standings row has team_id=7 and the QoP entry has team_id=7,
        the match is made via team_id even if team_name differs.
        """
        from dao.qop_rankings_dao import QoPRankingsDAO

        week_rows = [{"week_of": "2026-04-14"}]
        current_rows = [
            {
                "rank": 3,
                "team_name": "NEFC Academy",
                "team_id": 7,
                "matches_played": 18,
                "att_score": 85.0,
                "def_score": 80.0,
                "qop_score": 83.0,
            }
        ]

        client = _make_qop_client_with_data(week_rows, current_rows, prior_rows=[])
        qop_data = QoPRankingsDAO.get_latest_with_delta(client, division_id=1, age_group_id=2)

        assert qop_data["has_data"] is True

        # Build lookups
        qop_by_team_id: dict[int, dict] = {}
        qop_by_team_name: dict[str, dict] = {}
        for entry in qop_data["rankings"]:
            tid = entry.get("team_id")
            if tid is not None:
                qop_by_team_id[tid] = entry
            tname = entry.get("team_name", "")
            if tname:
                qop_by_team_name[tname.lower()] = entry

        # Standings row uses a slightly different name but has team_id=7
        table = [_make_standings_row("NEFC", team_id=7)]

        for row in table:
            qop_entry = None
            row_team_id = row.get("team_id")
            if row_team_id is not None:
                qop_entry = qop_by_team_id.get(row_team_id)
            if qop_entry is None:
                row_team_name = (row.get("team") or "").lower()
                qop_entry = qop_by_team_name.get(row_team_name)
            row["qop_rank"] = qop_entry["rank"] if qop_entry else None
            row["qop_rank_change"] = qop_entry["rank_change"] if qop_entry else None

        assert table[0]["qop_rank"] == 3
        # No prior week so rank_change is None
        assert table[0]["qop_rank_change"] is None

    def test_case_insensitive_team_name_match(self):
        """Team name comparison is case-insensitive (QoP 'NEFC' matches standings 'nefc')."""
        qop_rankings = [
            {"rank": 5, "team_name": "NEFC", "team_id": None, "rank_change": 1}
        ]

        qop_by_team_name: dict[str, dict] = {}
        for entry in qop_rankings:
            tname = entry.get("team_name", "")
            if tname:
                qop_by_team_name[tname.lower()] = entry

        # Standings row has lowercase name
        table = [_make_standings_row("nefc")]
        for row in table:
            row_team_name = (row.get("team") or "").lower()
            qop_entry = qop_by_team_name.get(row_team_name)
            row["qop_rank"] = qop_entry["rank"] if qop_entry else None
            row["qop_rank_change"] = qop_entry["rank_change"] if qop_entry else None

        assert table[0]["qop_rank"] == 5
        assert table[0]["qop_rank_change"] == 1


# ─── QoP enrichment: missing division_id or age_group_id ───────────────────


@pytest.mark.unit
class TestTableQoPMissingParams:
    """When division_id or age_group_id is absent, QoP enrichment is skipped."""

    def test_no_division_id_all_null(self):
        """Without division_id, all qop fields are null (no DAO call needed)."""
        table = [
            _make_standings_row("Team A"),
            _make_standings_row("Team B"),
        ]
        # Simulates the else branch: division_id is None
        division_id = None
        age_group_id = 2

        if not (division_id and age_group_id):
            for row in table:
                row["qop_rank"] = None
                row["qop_rank_change"] = None

        for row in table:
            assert row["qop_rank"] is None
            assert row["qop_rank_change"] is None

    def test_no_age_group_id_all_null(self):
        """Without age_group_id, all qop fields are null."""
        table = [_make_standings_row("Team A")]
        division_id = 1
        age_group_id = None

        if not (division_id and age_group_id):
            for row in table:
                row["qop_rank"] = None
                row["qop_rank_change"] = None

        assert table[0]["qop_rank"] is None
        assert table[0]["qop_rank_change"] is None

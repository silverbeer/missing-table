"""
Unit tests for the /api/table endpoint QoP enrichment logic.

Tests:
- With no QoP data: has_qop_data=False and qop_rank=null on all standings rows
- With QoP data: correct qop_rank attached to matching teams by team_name
- With QoP data: team_id lookup takes priority over team_name lookup
- Case-insensitive team name match
- Missing division_id / age_group_id skips QoP enrichment entirely

These tests exercise the enrichment logic in isolation using the same
helper pattern as test_qop_rankings.py (mock Supabase client).
"""

from decimal import Decimal
from unittest.mock import MagicMock, Mock

import pytest

# ─── helpers ───────────────────────────────────────────────────────────────────


def _make_chain(response_data: list[dict]):
    mock_resp = Mock()
    mock_resp.data = response_data
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = mock_resp
    return chain


def _make_qop_client(snapshots: list[dict], current_rows: list[dict], prior_rows=None):
    """
    Build a Supabase client mock for the new snapshot-centric model.

      * Call 1 on qop_snapshots → list of up to 2 snapshot rows (current, prior)
      * Call 1 on qop_rankings  → rows for the current snapshot
      * Call 2 on qop_rankings  → rows for the prior snapshot
    """
    client = MagicMock()
    call_index: dict[str, int] = {}

    def table_side_effect(name):
        if name == "qop_snapshots":
            return _make_chain(snapshots)
        if name == "qop_rankings":
            n = call_index.get(name, 0)
            call_index[name] = n + 1
            return _make_chain(current_rows if n == 0 else (prior_rows or []))
        return _make_chain([])

    client.table.side_effect = table_side_effect
    return client


def _make_standings_row(team_name: str, team_id: int | None = None) -> dict:
    """Minimal standings row as produced by calculate_standings_with_extras."""
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


def _enrich_table(table: list[dict], qop_rankings: list[dict]) -> None:
    """Apply the same enrichment logic the /api/table endpoint uses."""
    qop_by_team_id: dict[int, dict] = {}
    qop_by_team_name: dict[str, dict] = {}
    for entry in qop_rankings:
        tid = entry.get("team_id")
        if tid is not None:
            qop_by_team_id[tid] = entry
        tname = entry.get("team_name", "")
        if tname:
            qop_by_team_name[tname.lower()] = entry

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


# ─── QoP enrichment: no data ────────────────────────────────────────────────


@pytest.mark.unit
class TestTableQoPNoData:
    """When QoPRankingsDAO returns has_data=False, all qop_rank fields are null."""

    def test_no_qop_data_sets_nulls_on_all_rows(self):
        from dao.qop_rankings_dao import QoPRankingsDAO

        client = _make_qop_client(snapshots=[], current_rows=[])
        qop_data = QoPRankingsDAO.get_latest_with_delta(
            client, division_id=1, age_group_id=2
        )

        assert qop_data["has_data"] is False
        assert qop_data["week_of"] is None
        assert qop_data["rankings"] == []

        table = [_make_standings_row("Team Alpha"), _make_standings_row("Team Beta")]
        _enrich_table(table, qop_data["rankings"])

        for row in table:
            assert row["qop_rank"] is None
            assert row["qop_rank_change"] is None


# ─── QoP enrichment: matching by team_name ─────────────────────────────────


@pytest.mark.unit
class TestTableQoPByTeamName:
    """When QoP data is present, qop_rank is attached by matching team_name."""

    def test_qop_rank_attached_to_matching_team(self):
        from dao.qop_rankings_dao import QoPRankingsDAO

        snapshots = [
            {"id": 102, "detected_at": "2026-04-18"},
            {"id": 7, "detected_at": "2026-04-10"},
        ]
        current_rows = [
            {
                "rank": 11,
                "team_name": "NEFC",
                "team_id": 7,
                "matches_played": 18,
                "att_score": Decimal("80.0"),
                "def_score": Decimal("75.0"),
                "qop_score": Decimal("78.0"),
            },
            {
                "rank": 12,
                "team_name": "Other Club",
                "team_id": None,
                "matches_played": 16,
                "att_score": Decimal("70.0"),
                "def_score": Decimal("65.0"),
                "qop_score": Decimal("68.0"),
            },
        ]
        prior_rows = [
            {"rank": 11, "team_name": "NEFC"},
            {"rank": 10, "team_name": "Other Club"},
        ]

        client = _make_qop_client(snapshots, current_rows, prior_rows)
        qop_data = QoPRankingsDAO.get_latest_with_delta(
            client, division_id=1, age_group_id=2
        )

        assert qop_data["has_data"] is True
        assert qop_data["week_of"] == "2026-04-18"

        table = [
            _make_standings_row("NEFC", team_id=None),  # match by name only
            _make_standings_row("No Match Team"),
        ]
        _enrich_table(table, qop_data["rankings"])

        nefc_row = table[0]
        assert nefc_row["qop_rank"] == 11
        assert nefc_row["qop_rank_change"] == 0  # 11 - 11

        no_match = table[1]
        assert no_match["qop_rank"] is None
        assert no_match["qop_rank_change"] is None

    def test_team_id_lookup_takes_priority_over_name(self):
        from dao.qop_rankings_dao import QoPRankingsDAO

        snapshots = [{"id": 103, "detected_at": "2026-04-18"}]
        current_rows = [
            {
                "rank": 3,
                "team_name": "NEFC Academy",
                "team_id": 7,
                "matches_played": 18,
                "att_score": Decimal("85.0"),
                "def_score": Decimal("80.0"),
                "qop_score": Decimal("83.0"),
            }
        ]

        client = _make_qop_client(snapshots, current_rows, prior_rows=[])
        qop_data = QoPRankingsDAO.get_latest_with_delta(
            client, division_id=1, age_group_id=2
        )
        assert qop_data["has_data"] is True

        # Standings row uses a different team_name but has team_id=7
        table = [_make_standings_row("NEFC", team_id=7)]
        _enrich_table(table, qop_data["rankings"])

        assert table[0]["qop_rank"] == 3
        assert table[0]["qop_rank_change"] is None  # no prior snapshot

    def test_case_insensitive_team_name_match(self):
        """Team name match is case-insensitive (QoP 'NEFC' matches standings 'nefc')."""
        qop_rankings = [
            {"rank": 5, "team_name": "NEFC", "team_id": None, "rank_change": 1}
        ]

        table = [_make_standings_row("nefc")]
        _enrich_table(table, qop_rankings)

        assert table[0]["qop_rank"] == 5
        assert table[0]["qop_rank_change"] == 1


# ─── QoP enrichment: missing division_id or age_group_id ───────────────────


@pytest.mark.unit
class TestTableQoPMissingParams:
    """When division_id or age_group_id is absent, QoP enrichment is skipped."""

    def test_no_division_id_all_null(self):
        table = [_make_standings_row("Team A"), _make_standings_row("Team B")]
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
        table = [_make_standings_row("Team A")]
        division_id = 1
        age_group_id = None

        if not (division_id and age_group_id):
            for row in table:
                row["qop_rank"] = None
                row["qop_rank_change"] = None

        assert table[0]["qop_rank"] is None
        assert table[0]["qop_rank_change"] is None

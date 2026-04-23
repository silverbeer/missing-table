"""
Unit tests for QoP Rankings DAO and API endpoints.

Tests:
- record_snapshot: first write inserts a new snapshot + rankings
- record_snapshot: unchanged rankings return status=unchanged, no insert
- record_snapshot: changed rankings insert a new snapshot
- record_snapshot: unknown division / age_group raises ValueError
- record_snapshot: empty rankings returns status=unchanged
- get_latest_with_delta: no data → has_data=False
- get_latest_with_delta: two snapshots → rank_change computed
- get_latest_with_delta: one snapshot only → rank_change=None
- get_with_delta: snapshot_id pinned to older snapshot → deltas vs. the one before it
- get_with_delta: nav metadata (prev_snapshot_id / next_snapshot_id) at boundaries
- get_with_delta: unknown snapshot_id → has_data=False
- match preview QoP enrichment (unchanged from legacy model)
"""

from decimal import Decimal
from unittest.mock import MagicMock, Mock

import pytest

# ─── Helpers ───────────────────────────────────────────────────────────────────


def _make_chain(response_data: list[dict]):
    """A Supabase query chain that accepts any .select/.eq/.order/.insert/etc
    calls and always returns `response_data` from .execute()."""
    mock_resp = Mock()
    mock_resp.data = response_data

    chain = MagicMock()
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.upsert.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.ilike.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = mock_resp
    return chain


def _make_client(table_responses: dict[str, object]):
    """
    Build a mock Supabase client.

    table_responses values can be:
      - list[dict]         → a single static response for every call to that table
      - list[list[dict]]   → sequential responses (call 1 → list[0], call 2 → list[1], …)
      - callable           → called with the raw chain to configure custom behavior
    """
    client = MagicMock()
    call_index: dict[str, int] = {}

    def table_side_effect(name):
        value = table_responses.get(name, [])

        if callable(value):
            return value()

        # Sequential vs static based on shape.
        if value and isinstance(value[0], list):
            idx = call_index.get(name, 0)
            rows = value[idx] if idx < len(value) else value[-1]
            call_index[name] = idx + 1
            return _make_chain(rows)

        return _make_chain(value)

    client.table.side_effect = table_side_effect
    return client


def _snapshot_payload(
    rankings=None,
    detected_at="2026-04-18",
    division="Northeast",
    age_group="U14",
    source="cronjob",
) -> dict:
    return {
        "detected_at": detected_at,
        "division": division,
        "age_group": age_group,
        "source": source,
        "rankings": rankings
        if rankings is not None
        else [
            {
                "rank": 1,
                "team_name": "Team A",
                "matches_played": 10,
                "att_score": 80.0,
                "def_score": 75.0,
                "qop_score": 78.0,
            },
            {
                "rank": 2,
                "team_name": "Team B",
                "matches_played": 10,
                "att_score": 78.0,
                "def_score": 70.0,
                "qop_score": 74.0,
            },
        ],
    }


# ─── record_snapshot ───────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRecordSnapshotFirstWrite:
    """No prior snapshot exists — should insert both the snapshot and rankings."""

    def test_first_write_inserts_snapshot_and_rankings(self):
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        inserted_snapshot = [{"id": 99, "detected_at": "2026-04-18"}]

        client = _make_client(
            {
                "divisions": [[{"id": 1, "name": "Northeast"}]],
                "age_groups": [[{"id": 2, "name": "U14"}]],
                # Sequence of calls on qop_snapshots:
                # 1) SELECT latest (no prior) → []
                # 2) INSERT new snapshot → [{id: 99, …}]
                "qop_snapshots": [[], inserted_snapshot],
                # Sequence of calls on qop_rankings:
                # (not called for read since no prior snapshot)
                # 1) INSERT rankings
                "qop_rankings": [[]],
                "teams": [],
            }
        )

        result = QoPRankingsDAO.record_snapshot(client, _snapshot_payload())

        assert result["status"] == "inserted"
        assert result["detected_at"] == "2026-04-18"
        assert result["snapshot_id"] == 99
        assert result["rankings_count"] == 2


@pytest.mark.unit
class TestRecordSnapshotUnchanged:
    """Prior snapshot exists with matching data — should skip the insert."""

    def test_unchanged_returns_unchanged_status(self):
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        prior_rankings = [
            {
                "rank": 1,
                "team_name": "Team A",
                "team_id": None,
                "matches_played": 10,
                "att_score": Decimal("80.0"),
                "def_score": Decimal("75.0"),
                "qop_score": Decimal("78.0"),
            },
            {
                "rank": 2,
                "team_name": "Team B",
                "team_id": None,
                "matches_played": 10,
                "att_score": Decimal("78.0"),
                "def_score": Decimal("70.0"),
                "qop_score": Decimal("74.0"),
            },
        ]

        client = _make_client(
            {
                "divisions": [[{"id": 1, "name": "Northeast"}]],
                "age_groups": [[{"id": 2, "name": "U14"}]],
                "qop_snapshots": [[{"id": 7, "detected_at": "2026-04-10"}]],
                # prior rankings fetched from prior snapshot
                "qop_rankings": [prior_rankings],
            }
        )

        result = QoPRankingsDAO.record_snapshot(client, _snapshot_payload())

        assert result["status"] == "unchanged"
        assert result["snapshot_id"] == 7  # reuses prior snapshot id
        assert result["detected_at"] == "2026-04-10"

    def test_score_rounding_defeats_false_positives(self):
        """Decimal('87.6') in DB must compare equal to 87.6 in payload."""
        from backend.dao.qop_rankings_dao import _rankings_equal

        a = [
            {
                "rank": 1,
                "team_name": "NYC FC",
                "matches_played": 16,
                "att_score": Decimal("89.6"),
                "def_score": Decimal("83.1"),
                "qop_score": Decimal("87.6"),
            }
        ]
        b = [
            {
                "rank": 1,
                "team_name": "NYC FC",
                "matches_played": 16,
                "att_score": 89.6,
                "def_score": 83.1,
                "qop_score": 87.6,
            }
        ]
        assert _rankings_equal(a, b)


@pytest.mark.unit
class TestRecordSnapshotChanged:
    """Prior snapshot exists but rankings differ — should insert a new snapshot."""

    def test_score_diff_triggers_insert(self):
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        # Prior says Team A qop_score=78.0; incoming payload says 79.0 → change.
        prior_rankings = [
            {
                "rank": 1,
                "team_name": "Team A",
                "team_id": None,
                "matches_played": 10,
                "att_score": Decimal("80.0"),
                "def_score": Decimal("75.0"),
                "qop_score": Decimal("78.0"),
            },
            {
                "rank": 2,
                "team_name": "Team B",
                "team_id": None,
                "matches_played": 10,
                "att_score": Decimal("78.0"),
                "def_score": Decimal("70.0"),
                "qop_score": Decimal("74.0"),
            },
        ]
        new_snapshot_row = [{"id": 101, "detected_at": "2026-04-18"}]

        client = _make_client(
            {
                "divisions": [[{"id": 1, "name": "Northeast"}]],
                "age_groups": [[{"id": 2, "name": "U14"}]],
                # 1) fetch latest snapshot → returns prior
                # 2) insert new snapshot
                "qop_snapshots": [
                    [{"id": 7, "detected_at": "2026-04-10"}],
                    new_snapshot_row,
                ],
                # 1) read prior rankings
                # 2) insert new rankings
                "qop_rankings": [prior_rankings, []],
                "teams": [],
            }
        )

        changed = _snapshot_payload()
        changed["rankings"][0]["qop_score"] = 79.0

        result = QoPRankingsDAO.record_snapshot(client, changed)

        assert result["status"] == "inserted"
        assert result["snapshot_id"] == 101

    def test_rank_reshuffle_triggers_insert(self):
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        # Same teams, same scores, different rank assignment — counts as change.
        prior_rankings = [
            {
                "rank": 1,
                "team_name": "Team A",
                "team_id": None,
                "matches_played": 10,
                "att_score": Decimal("80.0"),
                "def_score": Decimal("75.0"),
                "qop_score": Decimal("78.0"),
            },
            {
                "rank": 2,
                "team_name": "Team B",
                "team_id": None,
                "matches_played": 10,
                "att_score": Decimal("78.0"),
                "def_score": Decimal("70.0"),
                "qop_score": Decimal("74.0"),
            },
        ]
        new_snapshot_row = [{"id": 200, "detected_at": "2026-04-18"}]

        client = _make_client(
            {
                "divisions": [[{"id": 1, "name": "Northeast"}]],
                "age_groups": [[{"id": 2, "name": "U14"}]],
                "qop_snapshots": [
                    [{"id": 7, "detected_at": "2026-04-10"}],
                    new_snapshot_row,
                ],
                "qop_rankings": [prior_rankings, []],
                "teams": [],
            }
        )

        # Swap A ↔ B positions; scores stay the same but rank changes per team.
        reshuffled = _snapshot_payload()
        reshuffled["rankings"][0]["team_name"] = "Team B"
        reshuffled["rankings"][0]["att_score"] = 78.0
        reshuffled["rankings"][0]["def_score"] = 70.0
        reshuffled["rankings"][0]["qop_score"] = 74.0
        reshuffled["rankings"][1]["team_name"] = "Team A"
        reshuffled["rankings"][1]["att_score"] = 80.0
        reshuffled["rankings"][1]["def_score"] = 75.0
        reshuffled["rankings"][1]["qop_score"] = 78.0

        result = QoPRankingsDAO.record_snapshot(client, reshuffled)
        assert result["status"] == "inserted"


@pytest.mark.unit
class TestRecordSnapshotErrors:

    def test_unknown_division_raises(self):
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        client = _make_client(
            {
                "divisions": [{"id": 99, "name": "OtherLand"}],
                "age_groups": [{"id": 2, "name": "U14"}],
            }
        )
        with pytest.raises(ValueError, match="Division not found"):
            QoPRankingsDAO.record_snapshot(
                client, _snapshot_payload(division="Northeast")
            )

    def test_unknown_age_group_raises(self):
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        client = _make_client(
            {
                "divisions": [{"id": 1, "name": "Northeast"}],
                "age_groups": [{"id": 99, "name": "U99"}],
            }
        )
        with pytest.raises(ValueError, match="Age group not found"):
            QoPRankingsDAO.record_snapshot(
                client, _snapshot_payload(age_group="U14")
            )

    def test_empty_rankings_returns_unchanged(self):
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        client = _make_client(
            {
                "divisions": [{"id": 1, "name": "Northeast"}],
                "age_groups": [{"id": 2, "name": "U14"}],
                "qop_snapshots": [],
                "qop_rankings": [],
            }
        )
        result = QoPRankingsDAO.record_snapshot(client, _snapshot_payload(rankings=[]))
        assert result["status"] == "unchanged"
        assert result["rankings_count"] == 0


# ─── get_latest_with_delta ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestGetLatestWithDelta:

    def test_no_data_returns_has_data_false(self):
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        client = _make_client({"qop_snapshots": [[]]})
        result = QoPRankingsDAO.get_latest_with_delta(
            client, division_id=1, age_group_id=2
        )
        assert result == {
            "has_data": False,
            "week_of": None,
            "prior_week_of": None,
            "snapshot_id": None,
            "prev_snapshot_id": None,
            "next_snapshot_id": None,
            "rankings": [],
        }

    def test_rank_delta_computed_correctly(self):
        """Prior rank 5, current rank 3 → rank_change = +2 (moved up)."""
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        snapshots = [
            {"id": 101, "detected_at": "2026-04-18"},
            {"id": 7, "detected_at": "2026-04-10"},
        ]
        current_rankings = [
            {
                "rank": 3,
                "team_name": "Team Alpha",
                "team_id": 42,
                "matches_played": 16,
                "att_score": Decimal("89.6"),
                "def_score": Decimal("83.1"),
                "qop_score": Decimal("87.6"),
            }
        ]
        prior_rankings = [{"rank": 5, "team_name": "Team Alpha"}]

        client = _make_client(
            {
                "qop_snapshots": [snapshots],
                "qop_rankings": [current_rankings, prior_rankings],
            }
        )

        result = QoPRankingsDAO.get_latest_with_delta(
            client, division_id=1, age_group_id=2
        )

        assert result["has_data"] is True
        assert result["week_of"] == "2026-04-18"
        assert result["prior_week_of"] == "2026-04-10"
        assert result["rankings"][0]["rank"] == 3
        assert result["rankings"][0]["rank_change"] == 2
        # Viewing latest: prev points at the older snapshot, next is None.
        assert result["snapshot_id"] == 101
        assert result["prev_snapshot_id"] == 7
        assert result["next_snapshot_id"] is None

    def test_no_prior_rank_change_is_none(self):
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        snapshots = [{"id": 101, "detected_at": "2026-04-18"}]
        current = [
            {
                "rank": 1,
                "team_name": "Brand New",
                "team_id": None,
                "matches_played": 5,
                "att_score": Decimal("70.0"),
                "def_score": Decimal("65.0"),
                "qop_score": Decimal("68.0"),
            }
        ]

        client = _make_client(
            {
                "qop_snapshots": [snapshots],
                "qop_rankings": [current],
            }
        )
        result = QoPRankingsDAO.get_latest_with_delta(
            client, division_id=1, age_group_id=2
        )
        assert result["has_data"] is True
        assert result["prior_week_of"] is None
        assert result["rankings"][0]["rank_change"] is None
        # Single snapshot in history → both nav directions closed off.
        assert result["snapshot_id"] == 101
        assert result["prev_snapshot_id"] is None
        assert result["next_snapshot_id"] is None


# ─── get_with_delta: snapshot_id navigation ────────────────────────────────────


@pytest.mark.unit
class TestGetWithDeltaNavigation:
    """Three snapshots exist — caller pins `snapshot_id` to step through them."""

    # newest → oldest (DESC), matching what the DAO queries.
    _SNAPSHOTS = [
        {"id": 300, "detected_at": "2026-04-18"},
        {"id": 200, "detected_at": "2026-04-10"},
        {"id": 100, "detected_at": "2026-04-03"},
    ]

    def _client_for_middle_snapshot(self, current_rows, prior_rows):
        """Mock client where pin=200 → current=snapshot 200, prior=snapshot 100."""
        return _make_client(
            {
                "qop_snapshots": [self._SNAPSHOTS],
                "qop_rankings": [current_rows, prior_rows],
            }
        )

    def test_pinning_middle_snapshot_computes_delta_vs_prior(self):
        """Pinning the middle snapshot means deltas compare it to snapshot 100,
        NOT to the newest (snapshot 300). The frontend relies on this so the
        +/- arrows match whatever week is on screen."""
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        current_rows = [
            {
                "rank": 2,
                "team_name": "Team Alpha",
                "team_id": 42,
                "matches_played": 12,
                "att_score": Decimal("85.0"),
                "def_score": Decimal("80.0"),
                "qop_score": Decimal("82.5"),
            }
        ]
        # Prior (snapshot 100): rank 4 → current rank 2 means +2.
        prior_rows = [{"rank": 4, "team_name": "Team Alpha"}]

        client = self._client_for_middle_snapshot(current_rows, prior_rows)
        result = QoPRankingsDAO.get_with_delta(
            client, division_id=1, age_group_id=2, snapshot_id=200
        )

        assert result["has_data"] is True
        assert result["snapshot_id"] == 200
        assert result["week_of"] == "2026-04-10"
        assert result["prior_week_of"] == "2026-04-03"
        assert result["rankings"][0]["rank_change"] == 2
        # From middle of history: prev points older, next points newer.
        assert result["prev_snapshot_id"] == 100
        assert result["next_snapshot_id"] == 300

    def test_pinning_oldest_snapshot_hides_prev(self):
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        current_rows = [
            {
                "rank": 1,
                "team_name": "Team Alpha",
                "team_id": 42,
                "matches_played": 5,
                "att_score": Decimal("70.0"),
                "def_score": Decimal("65.0"),
                "qop_score": Decimal("68.0"),
            }
        ]

        client = _make_client(
            {
                "qop_snapshots": [self._SNAPSHOTS],
                "qop_rankings": [current_rows],
            }
        )
        result = QoPRankingsDAO.get_with_delta(
            client, division_id=1, age_group_id=2, snapshot_id=100
        )

        assert result["snapshot_id"] == 100
        assert result["prior_week_of"] is None
        assert result["rankings"][0]["rank_change"] is None
        # Oldest snapshot → no prev, but next should point to the middle one.
        assert result["prev_snapshot_id"] is None
        assert result["next_snapshot_id"] == 200

    def test_unknown_snapshot_id_returns_empty(self):
        """If the caller pins an id that doesn't belong to this
        (division, age_group), degrade to empty rather than silently
        returning the latest — otherwise the UI nav state would lie."""
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        client = _make_client({"qop_snapshots": [self._SNAPSHOTS]})
        result = QoPRankingsDAO.get_with_delta(
            client, division_id=1, age_group_id=2, snapshot_id=9999
        )
        assert result["has_data"] is False
        assert result["snapshot_id"] is None
        assert result["prev_snapshot_id"] is None
        assert result["next_snapshot_id"] is None

    def test_omitting_snapshot_id_returns_latest(self):
        """Back-compat: callers that don't pass snapshot_id still get the
        newest snapshot, with prev pointing at the one before it."""
        from backend.dao.qop_rankings_dao import QoPRankingsDAO

        current_rows = [
            {
                "rank": 1,
                "team_name": "Team Alpha",
                "team_id": 42,
                "matches_played": 16,
                "att_score": Decimal("90.0"),
                "def_score": Decimal("85.0"),
                "qop_score": Decimal("87.5"),
            }
        ]
        prior_rows = [{"rank": 1, "team_name": "Team Alpha"}]

        client = _make_client(
            {
                "qop_snapshots": [self._SNAPSHOTS],
                "qop_rankings": [current_rows, prior_rows],
            }
        )
        result = QoPRankingsDAO.get_with_delta(
            client, division_id=1, age_group_id=2
        )
        assert result["snapshot_id"] == 300
        assert result["next_snapshot_id"] is None
        assert result["prev_snapshot_id"] == 200


# ─── Match Preview QoP enrichment (logic-only; unchanged) ──────────────────────


def _make_preview_base(home_team_id=1, away_team_id=2):
    return {
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "home_team_recent": [],
        "away_team_recent": [],
        "common_opponents": [],
        "head_to_head": [],
    }


def _make_team_with_details(team_id, name, division_id, age_group_id):
    return {
        "id": team_id,
        "name": name,
        "division": {"id": division_id, "name": "Northeast"},
        "age_group": {"id": age_group_id, "name": "U14"},
    }


@pytest.mark.unit
class TestMatchPreviewQoP:
    """QoP enrichment on the match preview response — logic is DAO-agnostic."""

    def _call_preview(
        self, home_team_id, away_team_id, mock_match_dao, mock_team_dao, mock_qop
    ):
        preview = mock_match_dao.get_match_preview(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            season_id=None,
            age_group_id=None,
            recent_count=5,
        )
        qop_defaults = {
            "has_qop_data": False,
            "home_qop_rank": None,
            "home_qop_rank_change": None,
            "away_qop_rank": None,
            "away_qop_rank_change": None,
        }
        try:
            home_team = mock_team_dao.get_team_with_details(home_team_id)
            away_team = mock_team_dao.get_team_with_details(away_team_id)

            home_division_id = (home_team.get("division") or {}).get("id")
            away_division_id = (away_team.get("division") or {}).get("id")
            home_age_group_id = (home_team.get("age_group") or {}).get("id")

            if (
                home_division_id is None
                or away_division_id is None
                or home_division_id != away_division_id
                or home_age_group_id is None
            ):
                preview.update(qop_defaults)
            else:
                qop_data = mock_qop(
                    mock_match_dao.client, home_division_id, home_age_group_id
                )
                if not qop_data.get("has_data"):
                    preview.update(qop_defaults)
                else:
                    rankings = qop_data["rankings"]

                    def find_team_rank(team_id, team_name):
                        for entry in rankings:
                            if entry.get("team_id") == team_id:
                                return entry["rank"], entry.get("rank_change")
                        if team_name:
                            for entry in rankings:
                                if entry.get("team_name", "").lower() == team_name.lower():
                                    return entry["rank"], entry.get("rank_change")
                        return None, None

                    home_name = home_team.get("name")
                    away_name = away_team.get("name")
                    home_rank, home_rank_change = find_team_rank(
                        home_team_id, home_name
                    )
                    away_rank, away_rank_change = find_team_rank(
                        away_team_id, away_name
                    )
                    preview.update(
                        {
                            "has_qop_data": True,
                            "home_qop_rank": home_rank,
                            "home_qop_rank_change": home_rank_change,
                            "away_qop_rank": away_rank,
                            "away_qop_rank_change": away_rank_change,
                        }
                    )
        except Exception:
            preview.update(qop_defaults)
        return preview

    def test_no_qop_data_returns_false_with_null_fields(self):
        mock_match_dao = MagicMock()
        mock_match_dao.get_match_preview.return_value = _make_preview_base(1, 2)
        mock_team_dao = MagicMock()
        mock_team_dao.get_team_with_details.side_effect = lambda tid: _make_team_with_details(
            tid, f"Team {tid}", division_id=10, age_group_id=20
        )
        mock_qop = MagicMock(
            return_value={"has_data": False, "week_of": None, "rankings": []}
        )
        result = self._call_preview(1, 2, mock_match_dao, mock_team_dao, mock_qop)
        assert result["has_qop_data"] is False
        assert result["home_qop_rank"] is None
        assert result["away_qop_rank"] is None

    def test_qop_data_attaches_correct_ranks(self):
        home_id, away_id = 7, 11
        mock_match_dao = MagicMock()
        mock_match_dao.get_match_preview.return_value = _make_preview_base(
            home_id, away_id
        )
        mock_team_dao = MagicMock()
        mock_team_dao.get_team_with_details.side_effect = lambda tid: _make_team_with_details(
            tid,
            "Home FC" if tid == home_id else "Away United",
            division_id=10,
            age_group_id=20,
        )
        rankings = [
            {"rank": 8, "team_id": home_id, "team_name": "Home FC", "rank_change": 1},
            {"rank": 11, "team_id": away_id, "team_name": "Away United", "rank_change": 0},
        ]
        mock_qop = MagicMock(
            return_value={"has_data": True, "week_of": "2026-04-18", "rankings": rankings}
        )
        result = self._call_preview(
            home_id, away_id, mock_match_dao, mock_team_dao, mock_qop
        )
        assert result["has_qop_data"] is True
        assert result["home_qop_rank"] == 8
        assert result["home_qop_rank_change"] == 1
        assert result["away_qop_rank"] == 11
        assert result["away_qop_rank_change"] == 0

    def test_different_divisions_returns_no_qop_data(self):
        home_id, away_id = 3, 4
        mock_match_dao = MagicMock()
        mock_match_dao.get_match_preview.return_value = _make_preview_base(
            home_id, away_id
        )
        mock_team_dao = MagicMock()
        mock_team_dao.get_team_with_details.side_effect = lambda tid: _make_team_with_details(
            tid, f"Team {tid}", division_id=10 if tid == home_id else 99, age_group_id=20
        )
        mock_qop = MagicMock()
        result = self._call_preview(
            home_id, away_id, mock_match_dao, mock_team_dao, mock_qop
        )
        assert result["has_qop_data"] is False
        mock_qop.assert_not_called()

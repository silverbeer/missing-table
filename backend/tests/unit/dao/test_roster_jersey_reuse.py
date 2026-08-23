"""Unit tests for SB-809: a deleted player's jersey number is reusable.

Deleting a roster player used to burn the number for the rest of the season:
the delete is a soft delete (`is_active=false`) and both the pre-insert check
and the DB unique constraint counted the tombstone.

These tests pin the two application-side halves of the fix:
  - `get_player_by_jersey` ignores soft-deleted rows.
  - `delete_player` hard-deletes players with no history and soft-deletes the
    rest, so goals/assists/stats keep pointing at a real row.

The DB half (partial unique index scoped to `is_active`) lives in migration
20260823000000_jersey_unique_active_players_only.sql.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dao.roster_dao import RosterDAO

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]


class _Chain:
    """Chainable stand-in for a PostgREST query builder.

    Records every call as (method, args) and returns itself, so a test can
    assert on the filters a DAO method applied. `execute()` returns the rows
    configured for the table.
    """

    def __init__(self, calls: list, rows: list):
        self._calls = calls
        self._rows = rows

    def __getattr__(self, name):
        def _record(*args, **kwargs):
            self._calls.append((name, args))
            return self

        return _record

    def execute(self):
        self._calls.append(("execute", ()))
        response = MagicMock()
        response.data = self._rows
        return response


def _build_dao(table_rows: dict[str, list]):
    """Build a RosterDAO whose client serves canned rows per table.

    Returns (dao, calls) where `calls` maps table name -> recorded call list.
    """
    calls: dict[str, list] = {name: [] for name in table_rows}

    def _table(name: str):
        calls.setdefault(name, [])
        return _Chain(calls[name], table_rows.get(name, []))

    client = MagicMock()
    client.table.side_effect = _table

    dao = RosterDAO.__new__(RosterDAO)
    holder = MagicMock()
    holder.get_client.return_value = client
    dao.connection_holder = holder
    dao.client = client
    return dao, calls


# ---------------------------------------------------------------------------
# get_player_by_jersey
# ---------------------------------------------------------------------------


class TestGetPlayerByJerseyIgnoresDeleted:
    def test_filters_on_is_active(self):
        dao, calls = _build_dao({"players": []})

        dao.get_player_by_jersey(team_id=19, season_id=184, jersey_number=36, age_group_id=3)

        eq_calls = [args for name, args in calls["players"] if name == "eq"]
        assert ("is_active", True) in eq_calls, "soft-deleted rows must not report a number as taken"
        assert ("team_id", 19) in eq_calls
        assert ("season_id", 184) in eq_calls
        assert ("jersey_number", 36) in eq_calls
        assert ("age_group_id", 3) in eq_calls

    def test_returns_none_when_only_a_tombstone_matches(self):
        # The DB does the filtering; with is_active applied the query comes
        # back empty even though a soft-deleted #36 exists.
        dao, _ = _build_dao({"players": []})

        assert dao.get_player_by_jersey(19, 184, 36, age_group_id=3) is None

    def test_returns_the_active_player(self):
        dao, _ = _build_dao(
            {"players": [{"id": 42, "jersey_number": 36, "first_name": "Sam", "last_name": "Ray", "is_active": True}]}
        )

        found = dao.get_player_by_jersey(19, 184, 36, age_group_id=3)

        assert found["id"] == 42

    def test_null_age_group_uses_is_null_filter(self):
        dao, calls = _build_dao({"players": []})

        dao.get_player_by_jersey(19, 184, 36, age_group_id=None)

        assert ("is_", ("age_group_id", "null")) in calls["players"]
        assert ("is_active", True) in [args for name, args in calls["players"] if name == "eq"]


# ---------------------------------------------------------------------------
# player_has_history
# ---------------------------------------------------------------------------


class TestPlayerHasHistory:
    def _tables(self, **overrides):
        tables = {
            "players": [{"user_profile_id": None}],
            "match_events": [],
            "player_match_stats": [],
            "invitations": [],
        }
        tables.update(overrides)
        return tables

    def test_false_for_a_placeholder_that_never_played(self):
        dao, _ = _build_dao(self._tables())

        assert dao.player_has_history(609) is False

    def test_true_when_linked_to_a_user_account(self):
        dao, _ = _build_dao(self._tables(players=[{"user_profile_id": "0adbdbdf-6a9f-4ec5-a917-9218a5c8f4ab"}]))

        assert dao.player_has_history(609) is True

    def test_true_when_the_player_appears_in_a_match_event(self):
        dao, _ = _build_dao(self._tables(match_events=[{"id": 7}]))

        assert dao.player_has_history(609) is True

    def test_match_event_check_covers_assists_and_subs(self):
        dao, calls = _build_dao(self._tables())

        dao.player_has_history(609)

        or_filters = [args[0] for name, args in calls["match_events"] if name == "or_"]
        assert len(or_filters) == 1
        clause = or_filters[0]
        assert "player_id.eq.609" in clause
        assert "assist_player_id.eq.609" in clause
        assert "player_out_id.eq.609" in clause

    def test_true_when_match_stats_exist(self):
        dao, _ = _build_dao(self._tables(player_match_stats=[{"id": 3}]))

        assert dao.player_has_history(609) is True

    def test_true_when_an_invitation_points_at_the_player(self):
        dao, _ = _build_dao(self._tables(invitations=[{"id": 11}]))

        assert dao.player_has_history(609) is True

    def test_true_when_the_check_itself_fails(self):
        # Errs on the side of keeping the row: an unreachable DB must not be
        # read as "nothing depends on this player".
        dao, _ = _build_dao(self._tables())
        dao.client.table.side_effect = RuntimeError("connection reset")

        assert dao.player_has_history(609) is True


# ---------------------------------------------------------------------------
# delete_player
# ---------------------------------------------------------------------------


class TestDeletePlayer:
    def test_hard_deletes_a_player_with_no_history(self):
        dao, calls = _build_dao({"players": [{"id": 609}]})
        dao.player_has_history = MagicMock(return_value=False)

        assert dao.delete_player(609) is True

        methods = [name for name, _ in calls["players"]]
        assert "delete" in methods, "an orphan row should leave no tombstone"
        assert "update" not in methods

    def test_soft_deletes_a_player_with_history(self):
        dao, calls = _build_dao({"players": [{"id": 42}]})
        dao.player_has_history = MagicMock(return_value=True)

        assert dao.delete_player(42) is True

        updates = [args for name, args in calls["players"] if name == "update"]
        assert updates == [({"is_active": False},)], "history must survive the delete"
        assert "delete" not in [name for name, _ in calls["players"]]

    def test_soft_delete_returns_false_when_no_row_updated(self):
        dao, _ = _build_dao({"players": []})
        dao.player_has_history = MagicMock(return_value=True)

        assert dao.delete_player(999) is False

    def test_returns_false_on_error(self):
        dao, _ = _build_dao({"players": [{"id": 42}]})
        dao.player_has_history = MagicMock(return_value=True)
        dao.client.table.side_effect = RuntimeError("boom")

        assert dao.delete_player(42) is False

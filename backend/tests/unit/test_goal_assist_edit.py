"""SB-432: editing a goal's assist — add, change, and clear.

The create path already validated assists (roster only, same team, not the
scorer) and had tests. The edit path had neither:

* `if update.assist_player_id is not None` meant an explicit null read as "leave
  unchanged", so an assist could be added and changed but never removed — the
  one correction a mis-tap actually needs.
* None of the create path's validation was applied, so an edit could reach a
  state a new goal would have been rejected for.

These pin both. The DAO test matters because `update_event` drops None values by
design, which is why clearing needs a flag rather than a null id.
"""

from unittest.mock import MagicMock, patch

import pytest

ROSTER = {
    10: {"id": 10, "team_id": 1, "jersey_number": 9, "display_name": "Scorer Nine"},
    11: {"id": 11, "team_id": 1, "jersey_number": 8, "display_name": "Assister Eight"},
    12: {"id": 12, "team_id": 1, "jersey_number": 14, "display_name": "Other Fourteen"},
    20: {"id": 20, "team_id": 2, "jersey_number": 7, "display_name": "Opponent Seven"},
}

EVENT_ID = 556
MATCH_ID = 123


def _goal_event(**overrides):
    event = {
        "id": EVENT_ID,
        "match_id": MATCH_ID,
        "event_type": "goal",
        "team_id": 1,
        "player_id": 10,
        "player_name": "Scorer Nine",
        "assist_player_id": 11,
        "assist_player_name": "Assister Eight",
        "is_deleted": False,
    }
    event.update(overrides)
    return event


def _override_auth(app):
    from auth import require_match_management_permission

    user = {
        "user_id": "test-user-id",
        "id": "test-user-id",
        "username": "tester",
        "role": "admin",
    }
    app.dependency_overrides[require_match_management_permission] = lambda: user
    return user


@pytest.mark.unit
class TestGoalAssistEdit:
    """PATCH /api/admin/goals/{event_id} assist handling."""

    def _patch(self, payload, event=None):
        """PATCH the goal event and hand back the mocks for assertion."""
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)

        with (
            patch("app.match_event_dao") as mock_event_dao,
            patch("app.player_stats_dao") as mock_stats_dao,
            patch("app.roster_dao") as mock_roster_dao,
        ):
            mock_event_dao.get_event_by_id.return_value = event or _goal_event()
            mock_event_dao.update_event.return_value = _goal_event()
            mock_roster_dao.get_player_by_id.side_effect = lambda pid: ROSTER.get(pid)

            try:
                client = TestClient(app)
                response = client.patch(f"/api/admin/goals/{EVENT_ID}", json=payload)
            finally:
                app.dependency_overrides.clear()

        return response, mock_event_dao, mock_stats_dao

    def test_explicit_null_clears_the_assist(self):
        response, mock_event_dao, mock_stats_dao = self._patch({"assist_player_id": None})

        assert response.status_code == 200
        # The flag, not a null id — the DAO would drop the null.
        kwargs = mock_event_dao.update_event.call_args.kwargs
        assert kwargs["clear_assist"] is True
        assert "assist_player_id" not in kwargs
        # The old assister loses the credit.
        mock_stats_dao.decrement_assists.assert_called_once_with(11, MATCH_ID)
        mock_stats_dao.increment_assists.assert_not_called()

    def test_omitting_the_field_leaves_the_assist_alone(self):
        response, mock_event_dao, mock_stats_dao = self._patch({"match_minute": 67})

        assert response.status_code == 200
        kwargs = mock_event_dao.update_event.call_args.kwargs
        assert "clear_assist" not in kwargs
        assert "assist_player_id" not in kwargs
        mock_stats_dao.decrement_assists.assert_not_called()
        mock_stats_dao.increment_assists.assert_not_called()

    def test_changing_the_assist_moves_the_credit(self):
        response, mock_event_dao, mock_stats_dao = self._patch({"assist_player_id": 12})

        assert response.status_code == 200
        kwargs = mock_event_dao.update_event.call_args.kwargs
        assert kwargs["assist_player_id"] == 12
        assert kwargs["assist_player_name"] == "Other Fourteen"
        assert "clear_assist" not in kwargs
        mock_stats_dao.decrement_assists.assert_called_once_with(11, MATCH_ID)
        mock_stats_dao.increment_assists.assert_called_once_with(12, MATCH_ID)

    def test_adding_an_assist_where_there_was_none(self):
        response, mock_event_dao, mock_stats_dao = self._patch(
            {"assist_player_id": 11},
            event=_goal_event(assist_player_id=None, assist_player_name=None),
        )

        assert response.status_code == 200
        mock_stats_dao.increment_assists.assert_called_once_with(11, MATCH_ID)
        # Nothing to take the credit from.
        mock_stats_dao.decrement_assists.assert_not_called()

    def test_assist_cannot_be_the_scorer(self):
        response, mock_event_dao, mock_stats_dao = self._patch({"assist_player_id": 10})

        assert response.status_code == 400
        assert "scorer" in response.json()["detail"].lower()
        mock_event_dao.update_event.assert_not_called()
        mock_stats_dao.increment_assists.assert_not_called()

    def test_assist_cannot_be_the_new_scorer_either(self):
        """Scorer and assist changing together must still not collide."""
        response, mock_event_dao, mock_stats_dao = self._patch({"player_id": 12, "assist_player_id": 12})

        assert response.status_code == 400
        assert "scorer" in response.json()["detail"].lower()
        mock_event_dao.update_event.assert_not_called()

    def test_assist_must_be_on_the_scoring_team(self):
        response, mock_event_dao, mock_stats_dao = self._patch({"assist_player_id": 20})

        assert response.status_code == 400
        assert "scoring team" in response.json()["detail"].lower()
        mock_event_dao.update_event.assert_not_called()
        mock_stats_dao.increment_assists.assert_not_called()

    def test_unknown_assist_player_is_rejected(self):
        response, mock_event_dao, _ = self._patch({"assist_player_id": 999})

        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()
        mock_event_dao.update_event.assert_not_called()


@pytest.mark.unit
class TestUpdateEventClearAssist:
    """MatchEventDAO.update_event treats None as 'unchanged', so clearing
    needs its own flag."""

    def _dao(self):
        from dao.match_event_dao import MatchEventDAO

        client = MagicMock()
        chain = client.table.return_value.update.return_value.eq.return_value
        chain.execute.return_value = MagicMock(data=[_goal_event()])
        dao = MatchEventDAO.__new__(MatchEventDAO)
        dao.client = client
        return dao, client

    def test_clear_assist_nulls_both_columns(self):
        dao, client = self._dao()

        dao.update_event(EVENT_ID, clear_assist=True)

        payload = client.table.return_value.update.call_args.args[0]
        assert payload["assist_player_id"] is None
        # The denormalized name has to go too, or the timeline keeps rendering
        # an assist whose id no longer exists.
        assert payload["assist_player_name"] is None

    def test_null_assist_id_alone_changes_nothing(self):
        dao, client = self._dao()

        dao.update_event(EVENT_ID, assist_player_id=None, match_minute=67)

        payload = client.table.return_value.update.call_args.args[0]
        assert "assist_player_id" not in payload
        assert payload["match_minute"] == 67

    def test_clear_assist_wins_over_a_supplied_id(self):
        dao, client = self._dao()

        dao.update_event(EVENT_ID, assist_player_id=12, clear_assist=True)

        payload = client.table.return_value.update.call_args.args[0]
        assert payload["assist_player_id"] is None
        assert payload["assist_player_name"] is None

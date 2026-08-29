"""Shootout scores on PATCH /api/matches/{id} (SB-906).

`MatchPatch` has declared `home_penalty_score` / `away_penalty_score` since
penalties were introduced, but the handler never forwarded them and the DAO had
no parameters for them — so a team or club manager scoring a level knockout tie
lost the shootout silently, with a 200 and no warning. The admin tournament
route was the only path that recorded one.

These cases pin the fix at both levels: the DAO writes penalties only when it
is told about them, and the endpoint refuses a shootout attached to a score
that was never level.
"""

from unittest.mock import MagicMock, patch

import pytest

from dao.match_dao import UNSET


def _make_match_dao():
    """A MatchDAO with a mocked Supabase client, as elsewhere in tests/unit."""
    from dao.match_dao import MatchDAO

    dao = object.__new__(MatchDAO)
    dao.connection_holder = MagicMock()
    dao.client = MagicMock()
    return dao


def _update_chain(dao):
    """Wire client.table(...).update(...).eq(...).execute() and return the mock."""
    chain = MagicMock()
    dao.client.table.return_value = chain
    chain.update.return_value = chain
    chain.eq.return_value = chain
    chain.execute.return_value = MagicMock(data=[{"id": 123}])
    return chain


BASE_UPDATE = {
    "match_id": 123,
    "home_team_id": 1,
    "away_team_id": 2,
    "match_date": "2026-08-30",
    "home_score": 1,
    "away_score": 1,
    "season_id": 4,
    "age_group_id": 5,
    "match_type_id": 3,
}


@pytest.mark.unit
class TestUpdateMatchPenalties:
    """MatchDAO.update_match()."""

    def test_writes_penalties_when_given(self):
        dao = _make_match_dao()
        chain = _update_chain(dao)

        with patch.object(dao, "get_match_by_id", return_value={"id": 123}):
            dao.update_match(**BASE_UPDATE, home_penalty_score=5, away_penalty_score=4)

        written = chain.update.call_args[0][0]
        assert written["home_penalty_score"] == 5
        assert written["away_penalty_score"] == 4

    def test_leaves_an_existing_shootout_alone_when_not_mentioned(self):
        """A scraper posting a corrected score must not erase the shootout."""
        dao = _make_match_dao()
        chain = _update_chain(dao)

        with patch.object(dao, "get_match_by_id", return_value={"id": 123}):
            dao.update_match(**BASE_UPDATE)

        written = chain.update.call_args[0][0]
        assert "home_penalty_score" not in written
        assert "away_penalty_score" not in written

    def test_a_zero_shootout_score_is_still_written(self):
        """0 is a real shootout score — losing 5-0 on penalties happens."""
        dao = _make_match_dao()
        chain = _update_chain(dao)

        with patch.object(dao, "get_match_by_id", return_value={"id": 123}):
            dao.update_match(**BASE_UPDATE, home_penalty_score=5, away_penalty_score=0)

        written = chain.update.call_args[0][0]
        assert written["away_penalty_score"] == 0


def _override_auth(app):
    from auth import require_match_management_permission

    user = {"user_id": "test-user-id", "id": "test-user-id", "username": "tester", "role": "team-manager"}
    app.dependency_overrides[require_match_management_permission] = lambda: user
    return user


def _current_match(**over):
    match = {
        "id": 123,
        "home_team_id": 1,
        "away_team_id": 2,
        "match_date": "2026-08-30",
        "home_score": None,
        "away_score": None,
        "season_id": 4,
        "age_group_id": 5,
        "match_type_id": 3,
        "division_id": None,
        "match_status": "scheduled",
        "external_match_id": None,
        "scheduled_kickoff": None,
    }
    match.update(over)
    return match


@pytest.mark.unit
class TestPatchMatchPenalties:
    """PATCH /api/matches/{match_id}."""

    def _client(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)
        return TestClient(app), app

    def test_forwards_the_shootout_to_the_dao(self):
        client, app = self._client()
        try:
            with (
                patch("app.match_dao") as mock_match_dao,
                patch("app.auth_manager") as mock_auth,
                patch("app.match_type_dao") as mock_match_type_dao,
                patch("app.require_division_for_competition"),
                patch("app._maybe_notify_final_score"),
            ):
                mock_match_dao.get_match_by_id.return_value = _current_match()
                mock_match_dao.update_match.return_value = {"id": 123}
                mock_auth.can_edit_match.return_value = True
                mock_match_type_dao.get_match_type_by_id.return_value = {"id": 3, "name": "Tournament"}

                resp = client.patch(
                    "/api/matches/123",
                    json={
                        "home_score": 1,
                        "away_score": 1,
                        "match_status": "completed",
                        "home_penalty_score": 5,
                        "away_penalty_score": 4,
                    },
                )

            assert resp.status_code == 200
            kwargs = mock_match_dao.update_match.call_args.kwargs
            assert kwargs["home_penalty_score"] == 5
            assert kwargs["away_penalty_score"] == 4
        finally:
            app.dependency_overrides.clear()

    def test_rejects_a_shootout_on_a_score_that_was_not_level(self):
        client, app = self._client()
        try:
            with (
                patch("app.match_dao") as mock_match_dao,
                patch("app.auth_manager") as mock_auth,
                patch("app.match_type_dao") as mock_match_type_dao,
                patch("app.require_division_for_competition"),
            ):
                mock_match_dao.get_match_by_id.return_value = _current_match()
                mock_auth.can_edit_match.return_value = True
                mock_match_type_dao.get_match_type_by_id.return_value = {"id": 3, "name": "Tournament"}

                resp = client.patch(
                    "/api/matches/123",
                    json={
                        "home_score": 2,
                        "away_score": 1,
                        "home_penalty_score": 5,
                        "away_penalty_score": 4,
                    },
                )

            assert resp.status_code == 400
            assert "level" in resp.json()["detail"]
            mock_match_dao.update_match.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    def test_rejects_a_negative_shootout_score(self):
        client, app = self._client()
        try:
            with (
                patch("app.match_dao") as mock_match_dao,
                patch("app.auth_manager") as mock_auth,
            ):
                mock_match_dao.get_match_by_id.return_value = _current_match()
                mock_auth.can_edit_match.return_value = True

                resp = client.patch(
                    "/api/matches/123",
                    json={"home_score": 1, "away_score": 1, "home_penalty_score": -1},
                )

            assert resp.status_code == 400
            mock_match_dao.update_match.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    def test_a_plain_score_update_says_nothing_about_penalties(self):
        """The common case: no shootout mentioned, none written."""
        client, app = self._client()
        try:
            with (
                patch("app.match_dao") as mock_match_dao,
                patch("app.auth_manager") as mock_auth,
                patch("app.match_type_dao") as mock_match_type_dao,
                patch("app.require_division_for_competition"),
                patch("app._maybe_notify_final_score"),
            ):
                mock_match_dao.get_match_by_id.return_value = _current_match()
                mock_match_dao.update_match.return_value = {"id": 123}
                mock_auth.can_edit_match.return_value = True
                mock_match_type_dao.get_match_type_by_id.return_value = {"id": 3, "name": "Tournament"}

                resp = client.patch(
                    "/api/matches/123",
                    json={"home_score": 3, "away_score": 0, "match_status": "completed"},
                )

            assert resp.status_code == 200
            kwargs = mock_match_dao.update_match.call_args.kwargs
            # UNSET, not None, since SB-913: None now means "clear the
            # shootout", so a score-only PATCH has to say nothing at all
            # rather than say null.
            assert kwargs["home_penalty_score"] is UNSET
            assert kwargs["away_penalty_score"] is UNSET
        finally:
            app.dependency_overrides.clear()

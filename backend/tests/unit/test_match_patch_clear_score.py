"""Clearing a score through PATCH /api/matches/{id} (SB-913).

A score could be set and never unset. Every optional field on `MatchPatch`
defaults to None, and the handler read None as "keep what is stored" — so an
explicit `{"home_score": null}` was indistinguishable from an omitted key.
`PUT` was worse: its model requires the full body and defaults a missing score
to 0, which puns "nobody recorded a score" into "it finished goalless".

That is not theoretical. On 2026-08-29 a score was typed into the wrong match
of a multi-age fixture and had to be cleared with SQL against production, plus
a manual Redis flush, because no API path could unset it.

These cases pin the three-way distinction — omitted, explicit null, real value
— for scores and for the shootout, at the endpoint and in the DAO.
"""

from unittest.mock import MagicMock, patch

import pytest

from dao.match_dao import UNSET


def _make_match_dao():
    from dao.match_dao import MatchDAO

    dao = object.__new__(MatchDAO)
    dao.connection_holder = MagicMock()
    dao.client = MagicMock()
    return dao


def _update_chain(dao):
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
    "match_date": "2026-08-29",
    "home_score": None,
    "away_score": None,
    "season_id": 4,
    "age_group_id": 5,
    "match_type_id": 3,
}


@pytest.mark.unit
class TestUpdateMatchClearing:
    """MatchDAO.update_match()."""

    def test_writes_null_scores_when_told_to(self):
        dao = _make_match_dao()
        chain = _update_chain(dao)

        with patch.object(dao, "get_match_by_id", return_value={"id": 123}):
            dao.update_match(**BASE_UPDATE)

        written = chain.update.call_args[0][0]
        assert written["home_score"] is None
        assert written["away_score"] is None

    def test_clears_a_shootout_on_an_explicit_none(self):
        dao = _make_match_dao()
        chain = _update_chain(dao)

        with patch.object(dao, "get_match_by_id", return_value={"id": 123}):
            dao.update_match(**BASE_UPDATE, home_penalty_score=None, away_penalty_score=None)

        written = chain.update.call_args[0][0]
        assert written["home_penalty_score"] is None
        assert written["away_penalty_score"] is None

    def test_leaves_a_shootout_alone_when_unmentioned(self):
        """The default is UNSET, so an unrelated write never touches penalties."""
        dao = _make_match_dao()
        chain = _update_chain(dao)

        with patch.object(dao, "get_match_by_id", return_value={"id": 123}):
            dao.update_match(**BASE_UPDATE)

        written = chain.update.call_args[0][0]
        assert "home_penalty_score" not in written
        assert "away_penalty_score" not in written


def _override_auth(app):
    from auth import require_match_management_permission

    user = {"user_id": "test-user-id", "id": "test-user-id", "username": "tester", "role": "admin"}
    app.dependency_overrides[require_match_management_permission] = lambda: user
    return user


def _current_match(**over):
    match = {
        "id": 6004,
        "home_team_id": 19,
        "away_team_id": 601,
        "match_date": "2026-08-29",
        "home_score": 1,
        "away_score": 2,
        "season_id": 184,
        "age_group_id": 2,
        "match_type_id": 2,
        "division_id": None,
        "match_status": "scheduled",
        "external_match_id": None,
        "scheduled_kickoff": None,
    }
    match.update(over)
    return match


@pytest.mark.unit
class TestPatchMatchClearing:
    """PATCH /api/matches/{match_id}."""

    def _client(self):
        from fastapi.testclient import TestClient

        from app import app

        _override_auth(app)
        return TestClient(app), app

    def _patch(self, body, current=None):
        client, app = self._client()
        try:
            with (
                patch("app.match_dao") as mock_match_dao,
                patch("app.auth_manager") as mock_auth,
                patch("app.match_type_dao") as mock_match_type_dao,
                patch("app.require_division_for_competition"),
                patch("app._maybe_notify_final_score"),
            ):
                mock_match_dao.get_match_by_id.return_value = current or _current_match()
                mock_match_dao.update_match.return_value = {"id": 6004}
                mock_auth.can_edit_match.return_value = True
                mock_match_type_dao.get_match_type_by_id.return_value = {"id": 2, "name": "Tournament"}

                resp = client.patch("/api/matches/6004", json=body)
                kwargs = (
                    mock_match_dao.update_match.call_args.kwargs
                    if mock_match_dao.update_match.call_args
                    else None
                )
            return resp, kwargs
        finally:
            app.dependency_overrides.clear()

    def test_an_explicit_null_clears_the_score(self):
        resp, kwargs = self._patch({"home_score": None, "away_score": None})

        assert resp.status_code == 200
        assert kwargs["home_score"] is None
        assert kwargs["away_score"] is None

    def test_an_omitted_score_keeps_the_stored_one(self):
        resp, kwargs = self._patch({"match_status": "postponed"})

        assert resp.status_code == 200
        assert kwargs["home_score"] == 1
        assert kwargs["away_score"] == 2

    def test_a_real_score_is_written(self):
        resp, kwargs = self._patch({"home_score": 2, "away_score": 3})

        assert resp.status_code == 200
        assert kwargs["home_score"] == 2
        assert kwargs["away_score"] == 3

    def test_zero_is_a_score_not_an_absence(self):
        resp, kwargs = self._patch({"home_score": 0, "away_score": 0})

        assert resp.status_code == 200
        assert kwargs["home_score"] == 0
        assert kwargs["away_score"] == 0

    def test_clearing_one_side_only_leaves_the_other(self):
        resp, kwargs = self._patch({"home_score": None})

        assert resp.status_code == 200
        assert kwargs["home_score"] is None
        assert kwargs["away_score"] == 2

    def test_an_omitted_shootout_reaches_the_dao_as_unset(self):
        resp, kwargs = self._patch({"match_status": "postponed"})

        assert resp.status_code == 200
        assert kwargs["home_penalty_score"] is UNSET
        assert kwargs["away_penalty_score"] is UNSET

    def test_an_explicit_null_shootout_is_forwarded(self):
        resp, kwargs = self._patch(
            {"home_penalty_score": None, "away_penalty_score": None},
            current=_current_match(home_score=1, away_score=1),
        )

        assert resp.status_code == 200
        assert kwargs["home_penalty_score"] is None
        assert kwargs["away_penalty_score"] is None

    def test_clearing_a_shootout_is_not_a_mismatched_shootout(self):
        """A null shootout on a 1-2 score is a correction, not "5-4 pens on 1-2"."""
        resp, kwargs = self._patch({"home_penalty_score": None, "away_penalty_score": None})

        assert resp.status_code == 200
        assert kwargs["home_penalty_score"] is None

    def test_a_negative_score_is_still_rejected(self):
        resp, kwargs = self._patch({"home_score": -1})

        assert resp.status_code == 400
        assert kwargs is None

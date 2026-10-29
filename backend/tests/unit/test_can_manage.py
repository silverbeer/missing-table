"""can_manage on match responses: per-match scoring permission (SB-1454)."""

from unittest.mock import patch

import pytest

from auth import AuthManager, can_manage_match
from tests.unit.test_live_scoring_idempotency import _live_match

HOME_TEAM, AWAY_TEAM, OTHER_TEAM = 1, 2, 9
HOME_CLUB, AWAY_CLUB, OTHER_CLUB = 10, 20, 90

USERS = {
    "anonymous": None,
    "admin": {"role": "admin"},
    "service with manage_matches": {"role": "service_account", "permissions": ["manage_matches"]},
    "service without": {"role": "service_account", "permissions": []},
    "team manager, home team": {"role": "team-manager", "team_id": HOME_TEAM},
    "team manager, other team": {"role": "team-manager", "team_id": OTHER_TEAM},
    "club manager, away club": {"role": "club_manager", "club_id": AWAY_CLUB},
    "club manager, other club": {"role": "club_manager", "club_id": OTHER_CLUB},
    "club manager, no club": {"role": "club_manager", "club_id": None},
    "team fan of home team": {"role": "team-fan", "team_id": HOME_TEAM, "club_id": HOME_CLUB},
    "club fan": {"role": "club_fan", "club_id": HOME_CLUB},
    "player": {"role": "team-player", "team_id": HOME_TEAM},
}


@pytest.mark.unit
class TestCanManageMatch:
    @pytest.mark.parametrize(
        "who,expected",
        [
            ("anonymous", False),
            ("admin", True),
            ("service with manage_matches", True),
            ("service without", False),
            ("team manager, home team", True),
            ("team manager, other team", False),
            ("club manager, away club", True),
            ("club manager, other club", False),
            ("club manager, no club", False),
            ("team fan of home team", False),
            ("club fan", False),
            ("player", False),
        ],
    )
    def test_rules(self, who, expected):
        assert can_manage_match(USERS[who], HOME_TEAM, AWAY_TEAM, HOME_CLUB, AWAY_CLUB) is expected

    def test_agrees_with_can_edit_match_for_every_user(self):
        """The list's answer must be the one the write endpoints enforce."""
        manager = AuthManager.__new__(AuthManager)
        clubs = {HOME_TEAM: HOME_CLUB, AWAY_TEAM: AWAY_CLUB}
        with patch.object(manager, "_get_team_club_id", side_effect=clubs.get):
            for who, user in USERS.items():
                if user is None:
                    continue
                pure = can_manage_match(user, HOME_TEAM, AWAY_TEAM, HOME_CLUB, AWAY_CLUB)
                assert pure == manager.can_edit_match(user, HOME_TEAM, AWAY_TEAM), who


def _get(path: str, user: dict, matches: list[dict] | None = None, match: dict | None = None):
    from fastapi.testclient import TestClient

    from app import app
    from auth import get_current_user_required

    app.dependency_overrides[get_current_user_required] = lambda: user
    with patch("app.match_dao") as mock_match_dao, patch("app.match_event_dao") as mock_event_dao:
        mock_match_dao.get_all_matches.return_value = matches or []
        mock_match_dao.get_match_by_id.return_value = match
        mock_event_dao.get_card_events_for_matches.return_value = {}
        try:
            return TestClient(app).get(path)
        finally:
            app.dependency_overrides.clear()


def _club_match(id_: int, home_club: int, away_club: int) -> dict:
    return _live_match(
        id=id_,
        home_team_club={"id": home_club, "name": "H"},
        away_team_club={"id": away_club, "name": "A"},
    )


@pytest.mark.unit
class TestEndpointsStampCanManage:
    def test_match_list_stamps_each_row(self):
        user = {"role": "club_manager", "club_id": HOME_CLUB, "username": "cm"}
        rows = [_club_match(1, HOME_CLUB, AWAY_CLUB), _club_match(2, OTHER_CLUB, AWAY_CLUB)]

        response = _get("/api/matches", user, matches=rows)

        assert response.status_code == 200
        assert [m["can_manage"] for m in response.json()] == [True, False]

    def test_fan_manages_nothing(self):
        user = {"role": "team-fan", "team_id": 1, "username": "parent"}

        response = _get("/api/matches", user, matches=[_club_match(1, HOME_CLUB, AWAY_CLUB)])

        assert response.json()[0]["can_manage"] is False

    def test_match_detail_stamps_can_manage(self):
        user = {"role": "team-manager", "team_id": 2, "username": "tm"}

        response = _get("/api/matches/123", user, match=_club_match(123, HOME_CLUB, AWAY_CLUB))

        assert response.status_code == 200
        assert response.json()["can_manage"] is True

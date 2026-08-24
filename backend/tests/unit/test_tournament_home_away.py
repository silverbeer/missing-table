"""Unit tests for the home/away fixture shape (SB-819).

Tournament matches used to be described as "our team" plus an opponent, which
assumes MT tracks one of the two sides. Loading a bracket often means neither
side is ours — the load-tournament-matches skill even documented the workaround
("pick the home team to be our_team_id"). Both sides are now named directly.

The deprecated form still has to work: `.claude/skills/load-tournament-matches`
posts it.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.backend]


@pytest.fixture
def dao():
    from dao.tournament_dao import TournamentDAO

    d = TournamentDAO.__new__(TournamentDAO)
    d.connection_holder = MagicMock()
    d.client = MagicMock()
    return d


def _capture_insert(dao):
    captured = {}
    table = MagicMock()

    def insert(data):
        captured["data"] = data
        chain = MagicMock()
        chain.execute.return_value.data = [{"id": 99, **data}]
        return chain

    table.insert.side_effect = insert
    dao.client.table.return_value = table
    return captured


BASE = {
    "tournament_id": 5,
    "match_date": "2026-09-01",
    "age_group_id": 3,
    "season_id": 184,
}


class TestBothSidesPicked:
    def test_ids_land_on_the_side_they_were_given(self, dao):
        captured = _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock()

        dao.create_tournament_match(**BASE, home_team_id=10, away_team_id=20)

        dao.get_or_create_opponent_team.assert_not_called()
        assert captured["data"]["home_team_id"] == 10
        assert captured["data"]["away_team_id"] == 20

    def test_neither_side_has_to_be_a_tracked_team(self, dao):
        """The point of SB-819: a bracket where MT tracks nobody."""
        captured = _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock(side_effect=[111, 222])

        dao.create_tournament_match(
            **BASE, home_team_name="Rockville Rovers", away_team_name="Vienna United"
        )

        assert captured["data"]["home_team_id"] == 111
        assert captured["data"]["away_team_id"] == 222

    def test_a_named_side_creates_through_get_or_create(self, dao):
        captured = _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock(return_value=333)

        dao.create_tournament_match(**BASE, home_team_id=10, away_team_name="Brand New FC")

        dao.get_or_create_opponent_team.assert_called_once_with("Brand New FC", 3)
        assert captured["data"]["away_team_id"] == 333

    def test_a_picked_id_wins_over_a_stale_name_on_the_same_side(self, dao):
        captured = _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock()

        dao.create_tournament_match(
            **BASE, home_team_id=10, away_team_id=20, away_team_name="Typo FC"
        )

        dao.get_or_create_opponent_team.assert_not_called()
        assert captured["data"]["away_team_id"] == 20

    def test_whitespace_only_name_is_not_a_side(self, dao):
        _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock()

        with pytest.raises(ValueError, match="away_team_id or away_team_name"):
            dao.create_tournament_match(**BASE, home_team_id=10, away_team_name="   ")

    def test_a_team_cannot_play_itself(self, dao):
        _capture_insert(dao)

        with pytest.raises(ValueError, match="cannot play itself"):
            dao.create_tournament_match(**BASE, home_team_id=10, away_team_id=10)

    def test_missing_home_side_is_rejected(self, dao):
        _capture_insert(dao)

        with pytest.raises(ValueError, match="home_team_id or home_team_name"):
            dao.create_tournament_match(**BASE, away_team_id=20)


class TestDeprecatedOurTeamFormStillWorks:
    def test_our_team_at_home(self, dao):
        captured = _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock(return_value=555)

        dao.create_tournament_match(
            **BASE, our_team_id=10, opponent_name="Cedar Stars", is_home=True
        )

        assert captured["data"]["home_team_id"] == 10
        assert captured["data"]["away_team_id"] == 555

    def test_our_team_away_flips_the_sides(self, dao):
        captured = _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock(return_value=555)

        dao.create_tournament_match(
            **BASE, our_team_id=10, opponent_name="Cedar Stars", is_home=False
        )

        assert captured["data"]["home_team_id"] == 555
        assert captured["data"]["away_team_id"] == 10

    def test_our_team_with_a_picked_opponent(self, dao):
        captured = _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock()

        dao.create_tournament_match(**BASE, our_team_id=10, opponent_team_id=42)

        dao.get_or_create_opponent_team.assert_not_called()
        assert captured["data"]["home_team_id"] == 10
        assert captured["data"]["away_team_id"] == 42

    def test_explicit_home_away_wins_over_the_deprecated_fields(self, dao):
        captured = _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock()

        dao.create_tournament_match(
            **BASE, home_team_id=1, away_team_id=2, our_team_id=99, opponent_team_id=98
        )

        assert captured["data"]["home_team_id"] == 1
        assert captured["data"]["away_team_id"] == 2

"""Unit tests for channel_resolver — pure logic, DAO is mocked."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from notifications.channel_resolver import resolve_destinations

pytestmark = [pytest.mark.unit]


def _rows(*triples):
    """Helper: rows(('telegram', '-100aaa', True), ...) → list of dicts."""
    return [
        {"platform": p, "destination": d, "enabled": en}
        for p, d, en in triples
    ]


def _dao_with(home_rows=None, away_rows=None):
    dao = Mock()

    def _list(club_id):
        if club_id == 1:
            return home_rows or []
        if club_id == 2:
            return away_rows or []
        return []

    dao.list_by_club.side_effect = _list
    return dao


class TestResolveDestinations:
    def test_returns_empty_when_no_clubs_configured(self):
        dao = _dao_with([], [])
        assert resolve_destinations(1, 2, dao) == []

    def test_returns_home_destinations_when_away_empty(self):
        dao = _dao_with(
            home_rows=_rows(("telegram", "-100home", True)),
            away_rows=[],
        )
        assert resolve_destinations(1, 2, dao) == [("telegram", "-100home")]

    def test_unions_home_and_away(self):
        dao = _dao_with(
            home_rows=_rows(("telegram", "-100home", True)),
            away_rows=_rows(("discord", "https://x/away", True)),
        )
        result = resolve_destinations(1, 2, dao)
        assert ("telegram", "-100home") in result
        assert ("discord", "https://x/away") in result
        assert len(result) == 2

    def test_dedupes_when_both_clubs_share_destination(self):
        dao = _dao_with(
            home_rows=_rows(("telegram", "-100shared", True)),
            away_rows=_rows(("telegram", "-100shared", True)),
        )
        assert resolve_destinations(1, 2, dao) == [("telegram", "-100shared")]

    def test_filters_disabled_rows(self):
        dao = _dao_with(
            home_rows=_rows(
                ("telegram", "-100on", True),
                ("discord", "https://x/off", False),
            ),
            away_rows=[],
        )
        assert resolve_destinations(1, 2, dao) == [("telegram", "-100on")]

    def test_skips_missing_club_ids(self):
        dao = _dao_with(
            home_rows=_rows(("telegram", "-100home", True)),
            away_rows=_rows(("discord", "https://x/away", True)),
        )
        # Only home provided
        result = resolve_destinations(1, None, dao)
        assert result == [("telegram", "-100home")]

    def test_swallows_dao_errors_gracefully(self):
        dao = Mock()
        dao.list_by_club.side_effect = RuntimeError("db down")
        assert resolve_destinations(1, 2, dao) == []

    def test_preserves_order_home_first(self):
        dao = _dao_with(
            home_rows=_rows(
                ("telegram", "-100homeTG", True),
                ("discord", "https://x/homeDC", True),
            ),
            away_rows=_rows(
                ("telegram", "-100awayTG", True),
                ("discord", "https://x/awayDC", True),
            ),
        )
        result = resolve_destinations(1, 2, dao)
        assert result[0] == ("telegram", "-100homeTG")
        assert result[1] == ("discord", "https://x/homeDC")
        assert result[2] == ("telegram", "-100awayTG")
        assert result[3] == ("discord", "https://x/awayDC")

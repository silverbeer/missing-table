"""Fixtures for the MT AI tool tests. The fakes and data live in mt_ai_fakes."""

import pytest
from mt_ai_fakes import ALIASES, CLUBS, LEAGUES, TEAMS, FakeClubs, FakeLeagues, FakeMatches, FakeTeams

from mt_ai.tools import ToolDeps, Viewer


@pytest.fixture
def teams() -> FakeTeams:
    return FakeTeams(TEAMS, ALIASES)


@pytest.fixture
def make_deps(teams: FakeTeams):
    def build(
        matches: FakeMatches | None = None,
        leagues: FakeLeagues | None = None,
        team_source: FakeTeams | None = None,
    ) -> ToolDeps:
        return ToolDeps(
            teams=team_source or teams,
            clubs=FakeClubs(CLUBS),
            leagues=leagues or FakeLeagues(LEAGUES),
            matches=matches or FakeMatches(),
        )

    return build


@pytest.fixture
def real_viewer() -> Viewer:
    return Viewer(include_test=False)


@pytest.fixture
def test_viewer() -> Viewer:
    return Viewer(include_test=True)

"""What resolve_tournament_team asks the database, and what it does with the answer (SB-1748).

The side rules are pure and tested in ``test_team_sides.py``; whether the
queries return what the schema holds is ``tests/integration/
test_tournament_team_sides.py``. This is the part between: which tables are
read and how often, that a feed name reaches ``ilike`` as text and not as a
pattern, and which database errors are a name nobody has rather than a retry.

The client is a recording stand-in, so every case counts its queries.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from postgrest.exceptions import APIError

from dao.team_dao import TeamDAO, like_literal
from dao.team_sides import AMBIGUOUS, MISSING, RESOLVED, UNKNOWN_LEAGUE, WRONG_SIDE

HOMEGROWN, ACADEMY, FLEX = 1, 2, 290
LEAGUE_ROWS = [
    {"id": HOMEGROWN, "name": "Homegrown", "parent_league_id": None},
    {"id": ACADEMY, "name": "Academy", "parent_league_id": None},
    {"id": FLEX, "name": "Flex", "parent_league_id": HOMEGROWN},
]
U14 = 2


def _team(team_id: int, name: str, *mapped: tuple[int, int], league_id: int | None = None) -> dict:
    """A teams row as _SIDE_COLUMNS returns it; `mapped` is (age_group_id, league_id)."""
    return {
        "id": team_id,
        "name": name,
        "city": None,
        "club_id": None,
        "league_id": league_id,
        "team_mappings": [{"age_group_id": age, "divisions": {"league_id": league}} for age, league in mapped],
    }


class _Query:
    def __init__(self, client: _Client, table: str) -> None:
        self.client = client
        self.table = table
        self.filters: list[tuple] = []

    def select(self, columns: str) -> _Query:
        return self

    def ilike(self, column: str, pattern: str) -> _Query:
        self.filters.append(("ilike", column, pattern))
        return self

    def in_(self, column: str, values: list) -> _Query:
        self.filters.append(("in", column, tuple(values)))
        return self

    def execute(self) -> SimpleNamespace:
        self.client.calls.append((self.table, *self.filters))
        if self.client.error is not None:
            raise self.client.error
        return SimpleNamespace(data=self.client.answer(self.table, self.filters))


class _Client:
    """Answers the three tables the resolver reads, and records every query.

    `ilike` is answered the way Postgres would: the pattern is un-escaped and
    compared whole, without case. An unescaped % or _ is not emulated — a
    test that wants a wildcard's false hit puts the row in `wildcard_hits`.
    """

    def __init__(self, teams=(), aliases=(), leagues=LEAGUE_ROWS, wildcard_hits=()) -> None:
        self.teams = list(teams)
        self.aliases = list(aliases)
        self.leagues = list(leagues)
        self.wildcard_hits = list(wildcard_hits)
        self.calls: list[tuple] = []
        self.error: Exception | None = None

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    @staticmethod
    def _literal(pattern: str) -> str:
        return pattern.replace("\\%", "%").replace("\\_", "_").replace("\\\\", "\\")

    def answer(self, table: str, filters: list[tuple]) -> list[dict]:
        if table == "leagues":
            return self.leagues
        kind, column, value = filters[0]
        rows = self.teams if table == "teams" else self.aliases
        if kind == "in":
            return [row for row in rows if row[column] in value]
        wanted = self._literal(value).casefold()
        hits = [row for row in rows if row[column].casefold() == wanted]
        return hits + [row for row in self.wildcard_hits if column in row]

    def tables(self) -> list[str]:
        return [call[0] for call in self.calls]

    def patterns(self) -> list[str]:
        return [f[2] for call in self.calls for f in call[1:] if f[0] == "ilike"]


def _dao(**rows) -> TeamDAO:
    dao = object.__new__(TeamDAO)
    dao.client = _Client(**rows)
    return dao


def _alias(team_id: int, name: str, league_id: int | None = None) -> dict:
    return {"team_id": team_id, "league_id": league_id, "source": "test", "external_name": name}


class TestQueriesPerName:
    """How many round trips one hinted name costs. The target is two."""

    def test_a_hinted_name_with_the_leagues_handed_in_is_two_queries(self):
        dao = _dao(teams=[_team(7, "AC River", (U14, HOMEGROWN)), _team(9, "AC River", (U14, ACADEMY))])

        team, resolution = dao.resolve_tournament_team("AC River", U14, "Academy", leagues=LEAGUE_ROWS)

        assert (team["id"], resolution.status) == (9, RESOLVED)
        assert dao.client.tables() == ["team_aliases", "teams"]

    def test_a_league_scoped_alias_is_two_queries(self):
        dao = _dao(teams=[_team(9, "AC River Academy", (U14, ACADEMY))], aliases=[_alias(9, "AC River", ACADEMY)])

        team, _ = dao.resolve_tournament_team("AC River", U14, "Academy", leagues=LEAGUE_ROWS)

        assert team["id"] == 9
        assert dao.client.tables() == ["team_aliases", "teams"]

    def test_a_name_reached_only_through_a_league_agnostic_alias_is_three(self):
        dao = _dao(teams=[_team(9, "AC River Academy", (U14, ACADEMY))], aliases=[_alias(9, "ACR")])

        team, _ = dao.resolve_tournament_team("ACR", U14, "Academy", leagues=LEAGUE_ROWS)

        assert team["id"] == 9
        assert dao.client.tables() == ["team_aliases", "teams", "teams"]

    def test_the_leagues_handed_in_are_never_read_again(self):
        dao = _dao(teams=[_team(7, "AC River", (U14, HOMEGROWN))], leagues=[])

        team, _ = dao.resolve_tournament_team("AC River", U14, "Homegrown", leagues=LEAGUE_ROWS)

        assert team["id"] == 7
        assert "leagues" not in dao.client.tables()

    def test_without_them_they_are_read_here_once(self):
        dao = _dao(teams=[_team(7, "AC River", (U14, HOMEGROWN))])

        team, _ = dao.resolve_tournament_team("AC River", U14, "Homegrown")

        assert team["id"] == 7
        assert dao.client.tables() == ["leagues", "team_aliases", "teams"]

    def test_with_no_hint_no_leagues_are_read(self):
        dao = _dao(teams=[_team(7, "AC River", (U14, HOMEGROWN))])

        team, _ = dao.resolve_tournament_team("AC River", U14, None)

        assert team["id"] == 7
        assert dao.client.tables() == ["teams"]

    def test_league_rows_is_one_read_of_the_leagues_table(self):
        dao = _dao()
        assert dao.league_rows() == LEAGUE_ROWS
        assert dao.client.calls == [("leagues",)]


class TestAnUnknownLeague:
    @pytest.mark.parametrize("hint", ["HD", "Homegrown Division", "Homegrwon", "Home%", "_cademy"])
    def test_it_is_refused_before_any_team_is_looked_up(self, hint):
        dao = _dao(teams=[_team(7, "AC River", (U14, HOMEGROWN))])

        team, resolution = dao.resolve_tournament_team("AC River", U14, hint, leagues=LEAGUE_ROWS)

        assert team is None
        assert resolution.status == UNKNOWN_LEAGUE
        assert resolution.reason == f"unknown league '{hint}'"
        assert dao.client.calls == []

    def test_reading_the_leagues_itself_it_asks_nothing_else(self):
        dao = _dao(teams=[_team(7, "AC River", (U14, HOMEGROWN))])

        _, resolution = dao.resolve_tournament_team("AC River", U14, "HD")

        assert resolution.status == UNKNOWN_LEAGUE
        assert dao.client.tables() == ["leagues"]

    def test_it_is_not_the_wrong_side(self):
        dao = _dao(teams=[_team(7, "AC River", (U14, HOMEGROWN))])
        _, resolution = dao.resolve_tournament_team("AC River", U14, "HD", leagues=LEAGUE_ROWS)
        assert resolution.status != WRONG_SIDE


class TestATeamMappedOnBothSidesAtOneAge:
    def _both(self) -> dict:
        return _team(17, "AC River", (U14, HOMEGROWN), (U14, ACADEMY), league_id=FLEX)

    @pytest.mark.parametrize("hint", ["Academy", "Homegrown", "Flex"])
    def test_it_does_not_answer_a_hint(self, hint):
        dao = _dao(teams=[self._both()])

        team, resolution = dao.resolve_tournament_team("AC River", U14, hint, leagues=LEAGUE_ROWS)

        assert team is None
        assert resolution.status == AMBIGUOUS
        assert resolution.reason == "ambiguous: team 17 is registered as both Academy and Homegrown at this age group"

    def test_with_no_hint_it_resolves_as_before(self):
        dao = _dao(teams=[self._both()])
        team, resolution = dao.resolve_tournament_team("AC River", U14, None)
        assert (team["id"], resolution.status) == (17, RESOLVED)

    def test_a_team_cleanly_on_the_hinted_side_is_taken_instead(self):
        dao = _dao(teams=[self._both(), _team(9, "AC River", (U14, ACADEMY))])

        team, resolution = dao.resolve_tournament_team("AC River", U14, "Academy", leagues=LEAGUE_ROWS)

        assert (team["id"], resolution.status) == (9, RESOLVED)

    def test_at_an_age_where_it_is_on_one_side_it_answers(self):
        # Both sides at U14 is what cannot be read; at U15 it is Academy only.
        u15 = U14 + 1
        dao = _dao(teams=[_team(17, "AC River", (U14, HOMEGROWN), (U14, ACADEMY), (u15, ACADEMY))])

        team, _ = dao.resolve_tournament_team("AC River", u15, "Academy", leagues=LEAGUE_ROWS)

        assert team["id"] == 17


class TestAnExactNameShadowsALeagueAgnosticAlias:
    """A known shape, pinned as it stands: the exact name is asked first.

    'AC River' is the Homegrown team's own name, and also a league-agnostic
    alias someone gave the Academy team. The alias is only consulted when no
    team has the name, so the Academy message fails rather than following it.
    A league-scoped alias is how to say "on the Academy side this means 9".
    """

    def _dao(self) -> TeamDAO:
        return _dao(
            teams=[_team(7, "AC River", (U14, HOMEGROWN)), _team(9, "AC River Academy", (U14, ACADEMY))],
            aliases=[_alias(9, "AC River")],
        )

    def test_on_the_hinted_side_the_exact_name_team_is_the_answer(self):
        team, resolution = self._dao().resolve_tournament_team("AC River", U14, "Homegrown", leagues=LEAGUE_ROWS)
        assert (team["id"], resolution.status) == (7, RESOLVED)

    def test_on_the_other_side_it_fails_wrong_side_and_the_alias_is_not_followed(self):
        team, resolution = self._dao().resolve_tournament_team("AC River", U14, "Academy", leagues=LEAGUE_ROWS)
        assert team is None
        assert resolution.status == WRONG_SIDE
        assert resolution.reason == "wrong side: exists as Homegrown"


class TestAFeedNameIsTextNotAPattern:
    def test_like_literal_escapes_the_three_metacharacters(self):
        assert like_literal("AC River") == "AC River"
        assert like_literal("100% FC") == "100\\% FC"
        assert like_literal("FC_United") == "FC\\_United"
        assert like_literal("Club\\") == "Club\\\\"
        assert like_literal("\\%_") == "\\\\\\%\\_"

    @pytest.mark.parametrize(
        ("name", "pattern"),
        [("I%", "I\\%"), ("I_A", "I\\_A"), ("Club\\", "Club\\\\")],
    )
    def test_the_name_reaches_both_tables_escaped(self, name, pattern):
        dao = _dao()

        team, resolution = dao.resolve_tournament_team(name, U14, "Academy", leagues=LEAGUE_ROWS)

        assert (team, resolution.status) == (None, MISSING)
        assert dao.client.patterns() == [pattern, pattern]
        assert dao.client.tables() == ["team_aliases", "teams"]

    @pytest.mark.parametrize("name", ["I%", "I_A", "I*"])
    def test_an_alias_a_wildcard_would_reach_is_not_a_hit(self, name):
        # What the database hands back if the pattern is read as one anyway
        # (PostgREST turns * into %): the alias 'IFA' for a real team.
        ifa = _team(19, "Intercontinental Football Academy", (U14, HOMEGROWN))
        for league_id in (None, HOMEGROWN):
            dao = _dao(teams=[ifa], wildcard_hits=[_alias(19, "IFA", league_id)])

            team, resolution = dao.resolve_tournament_team(name, U14, "Homegrown", leagues=LEAGUE_ROWS)

            assert (team, resolution.status) == (None, MISSING)

    def test_a_team_name_a_wildcard_would_reach_is_not_a_hit(self):
        dao = _dao(wildcard_hits=[_team(19, "IFA", (U14, HOMEGROWN))])
        team, resolution = dao.resolve_tournament_team("I%", U14, "Homegrown", leagues=LEAGUE_ROWS)
        assert (team, resolution.status) == (None, MISSING)

    def test_a_name_that_really_contains_one_still_resolves(self):
        dao = _dao(
            teams=[_team(5, "100% FC", (U14, ACADEMY)), _team(6, "Real Club", (U14, ACADEMY))],
            aliases=[_alias(6, "Real_Club")],
        )

        team, _ = dao.resolve_tournament_team("100% fc", U14, "Academy", leagues=LEAGUE_ROWS)
        assert team["id"] == 5

        team, _ = dao.resolve_tournament_team("real_club", U14, "Academy", leagues=LEAGUE_ROWS)
        assert team["id"] == 6

    def test_an_alias_is_matched_without_case_or_runs_of_whitespace(self):
        dao = _dao(teams=[_team(6, "Real Club", (U14, ACADEMY))], aliases=[_alias(6, "RC Academy", ACADEMY)])
        team, _ = dao.resolve_tournament_team("  rc   ACADEMY ", U14, "Academy", leagues=LEAGUE_ROWS)
        assert team["id"] == 6

    @pytest.mark.parametrize("code", ["22025", "22021", "PGRST100"])
    def test_a_name_the_database_cannot_be_asked_about_is_missing(self, code):
        dao = _dao()
        dao.client.error = APIError({"code": code, "message": "LIKE pattern must not end with escape character"})

        team, resolution = dao.resolve_tournament_team("Club\\", U14, "Academy", leagues=LEAGUE_ROWS)

        assert (team, resolution.status) == (None, MISSING)
        assert resolution.reason is None

    @pytest.mark.parametrize(
        "error",
        [
            APIError({"code": "57014", "message": "canceling statement due to statement timeout"}),
            APIError({"code": "PGRST301", "message": "JWT expired"}),
            APIError({"message": "no code at all"}),
            RuntimeError("connection reset"),
        ],
    )
    def test_any_other_database_error_is_raised_to_be_retried(self, error):
        dao = _dao()
        dao.client.error = error
        with pytest.raises(type(error)):
            dao.resolve_tournament_team("AC River", U14, "Academy", leagues=LEAGUE_ROWS)


class TestTheLeaguePathIsUntouched:
    """resolve_team_by_name still hands the name to ilike exactly as it came."""

    def test_its_alias_lookup_is_not_escaped_or_post_filtered(self):
        dao = _dao(wildcard_hits=[{"team_id": 19, "league_id": None, "source": "test", "external_name": "IFA"}])

        rows = dao._alias_rows("I%")

        assert dao.client.calls == [("team_aliases", ("ilike", "external_name", "I%"))]
        assert [row["team_id"] for row in rows] == [19]

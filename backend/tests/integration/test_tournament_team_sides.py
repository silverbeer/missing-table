"""Tournament team names resolved on the right side, against a real database (SB-1748).

Two teams with one name — a club's Homegrown team and its Academy team — and
the queries that tell them apart: the embed of a team's mappings and their
divisions' leagues, the fold of Flex into Homegrown through
``leagues.parent_league_id``, and alias rows scoped to a league or to none.
The rules themselves are pure and tested in ``tests/unit/test_team_sides.py``;
this is whether the DAO feeds them what the schema actually holds.

**The seeded teams have no user data** — no roster, no events, no matches —
which is every team at a tournament until a manager claims one.

Requires local Supabase. Skips cleanly if unreachable.
"""

from __future__ import annotations

import os
import uuid

import pytest
from postgrest.exceptions import APIError

from dao.ingest_failures_dao import IngestFailuresDAO
from dao.match_dao import SupabaseConnection
from dao.team_dao import TeamDAO
from dao.team_sides import AMBIGUOUS, MISSING, RESOLVED, UNKNOWN_LEAGUE, WRONG_SIDE

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]

RESOLVE_BY_LEAGUE = "resolve_ingest_failures_by_league"
NOT_INSTALLED = (
    f"{RESOLVE_BY_LEAGUE}() is not installed in the local database — apply "
    "supabase/migrations/20261124120000_ingest_failures_resolve_by_league.sql "
    "(./scripts/db_tools.sh migrate local) to run this test"
)


def _is_local(url: str | None) -> bool:
    return bool(url) and ("127.0.0.1" in url or "localhost" in url)


def _admin_client():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:55321")
    if not _is_local(url):
        pytest.skip(f"Refusing to run destructive test against non-local Supabase: {url}")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY not set — cannot run tournament team side test")
    return create_client(url, key)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


def _quietly(step) -> None:
    """Run one cleanup step; a failure must not stop the steps after it."""
    try:
        step()
    except Exception:  # pragma: no cover - cleanup is best effort
        pass


def _league_with_division(admin, name: str) -> tuple[dict, dict]:
    leagues = admin.table("leagues").select("id, name, parent_league_id").ilike("name", name).execute().data
    if not leagues:
        pytest.skip(f"No '{name}' league; seed the local DB first")
    divisions = (
        admin.table("divisions").select("id, name").eq("league_id", leagues[0]["id"]).order("id").limit(1).execute()
    ).data
    if not divisions:
        pytest.skip(f"No division in the '{name}' league; seed the local DB first")
    return leagues[0], divisions[0]


@pytest.fixture
def sides():
    """One name on both sides, a Flex-only team, and the DAOs to resolve them."""
    admin = _admin_client()
    try:
        age_groups = admin.table("age_groups").select("id, name").order("id").limit(2).execute().data
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("Local Supabase not reachable")
    if len(age_groups) < 2:
        pytest.skip("Fewer than two age groups; seed the local DB first")

    homegrown, homegrown_division = _league_with_division(admin, "Homegrown")
    academy, academy_division = _league_with_division(admin, "Academy")
    flex, flex_division = _league_with_division(admin, "Flex")
    if flex.get("parent_league_id") != homegrown["id"]:
        pytest.skip("Flex is not a child of Homegrown in this database")

    connection = SupabaseConnection()
    if not _is_local(connection.url):
        pytest.skip(f"Refusing to run against non-local Supabase: {connection.url}")

    team_ids: list[int] = []
    failure_source = _unique("zz-sides-source")
    age, other_age = age_groups[0]["id"], age_groups[1]["id"]

    def _team(name: str, league_id: int | None, division_id: int | None) -> dict:
        row = admin.table("teams").insert({"name": name, "league_id": league_id}).execute().data[0]
        team_ids.append(row["id"])
        if division_id is not None:
            admin.table("team_mappings").insert(
                {"team_id": row["id"], "age_group_id": age, "division_id": division_id}
            ).execute()
        return row

    try:
        shared = _unique("ZZ Sides River")
        # As production holds them: a Homegrown club's team carries Flex in
        # teams.league_id, and an MLS academy's carries nothing.
        homegrown_team = _team(shared, flex["id"], homegrown_division["id"])
        academy_team = _team(shared, None, academy_division["id"])
        flex_only = _team(_unique("ZZ Sides Flex"), None, flex_division["id"])
        unmapped = _team(_unique("ZZ Sides Nowhere"), None, None)

        yield {
            "admin": admin,
            "team_dao": TeamDAO(connection),
            "failures_dao": IngestFailuresDAO(connection),
            "age": age,
            "other_age": other_age,
            "shared": shared,
            "homegrown_team": homegrown_team,
            "academy_team": academy_team,
            "flex_only": flex_only,
            "unmapped": unmapped,
            "academy_league_id": academy["id"],
            "homegrown_league_id": homegrown["id"],
            "homegrown_division_id": homegrown_division["id"],
            "academy_division_id": academy_division["id"],
            "make_team": _team,
            "failure_source": failure_source,
        }
    finally:
        # Each step on its own: a failed delete must not strand the rest.
        for team_id in team_ids:
            _quietly(lambda tid=team_id: admin.table("team_aliases").delete().eq("team_id", tid).execute())
            _quietly(lambda tid=team_id: admin.table("team_mappings").delete().eq("team_id", tid).execute())
            _quietly(lambda tid=team_id: admin.table("teams").delete().eq("id", tid).execute())
        _quietly(lambda: admin.table("ingest_failures").delete().eq("source", failure_source).execute())


def _function_installed(admin) -> bool:
    try:
        admin.rpc(
            RESOLVE_BY_LEAGUE,
            {"p_kind": "team", "p_raw_name": _unique("zz-probe"), "p_league": None, "p_source": _unique("zz-probe")},
        ).execute()
    except APIError as exc:
        if exc.code == "PGRST202":
            return False
        raise
    return True


class TestOneNameOnBothSides:
    def test_the_hint_picks_the_team_on_that_side(self, sides):
        dao = sides["team_dao"]

        team, resolution = dao.resolve_tournament_team(sides["shared"], sides["age"], "Homegrown")
        assert resolution.status == RESOLVED
        assert team["id"] == sides["homegrown_team"]["id"]

        team, resolution = dao.resolve_tournament_team(sides["shared"], sides["age"], "Academy")
        assert resolution.status == RESOLVED
        assert team["id"] == sides["academy_team"]["id"]

    def test_the_team_row_carries_no_mappings(self, sides):
        team, _ = sides["team_dao"].resolve_tournament_team(sides["shared"], sides["age"], "Academy")
        assert set(team) == {"id", "name", "city", "club_id", "league_id"}

    def test_the_name_is_matched_without_case_or_padding(self, sides):
        spelled = f"  {sides['shared'].upper()}  "
        team, _ = sides["team_dao"].resolve_tournament_team(spelled, sides["age"], "academy")
        assert team["id"] == sides["academy_team"]["id"]

    def test_with_no_hint_it_is_ambiguous_and_nothing_is_picked(self, sides):
        team, resolution = sides["team_dao"].resolve_tournament_team(sides["shared"], sides["age"], None)

        assert team is None
        assert resolution.status == AMBIGUOUS
        ids = sorted([sides["homegrown_team"]["id"], sides["academy_team"]["id"]])
        assert resolution.reason == f"ambiguous: team ids {ids[0]}, {ids[1]}"

    def test_an_age_group_neither_is_mapped_at_falls_back_to_their_other_ages(self, sides):
        team, resolution = sides["team_dao"].resolve_tournament_team(sides["shared"], sides["other_age"], "Academy")
        assert resolution.status == RESOLVED
        assert team["id"] == sides["academy_team"]["id"]

    def test_the_old_resolver_still_takes_the_first_hit(self, sides):
        # Unchanged on purpose: league messages still go through it.
        team = sides["team_dao"].resolve_team_by_name(sides["shared"])
        assert team["id"] in {sides["homegrown_team"]["id"], sides["academy_team"]["id"]}


class TestANameOnOneSideOnly:
    def test_a_flex_only_mapping_counts_as_homegrown(self, sides):
        team, resolution = sides["team_dao"].resolve_tournament_team(
            sides["flex_only"]["name"], sides["age"], "Homegrown"
        )
        assert resolution.status == RESOLVED
        assert team["id"] == sides["flex_only"]["id"]

    def test_a_flex_hint_is_read_as_homegrown(self, sides):
        team, _ = sides["team_dao"].resolve_tournament_team(sides["shared"], sides["age"], "Flex")
        assert team["id"] == sides["homegrown_team"]["id"]

    def test_the_other_sides_hint_fails_rather_than_taking_it(self, sides):
        team, resolution = sides["team_dao"].resolve_tournament_team(
            sides["flex_only"]["name"], sides["age"], "Academy"
        )
        assert team is None
        assert resolution.status == WRONG_SIDE
        assert resolution.reason == "wrong side: exists as Homegrown"

    def test_with_no_hint_the_single_candidate_resolves(self, sides):
        team, resolution = sides["team_dao"].resolve_tournament_team(sides["flex_only"]["name"], sides["age"], None)
        assert resolution.status == RESOLVED
        assert team["id"] == sides["flex_only"]["id"]

    def test_a_team_with_no_mappings_and_no_league_cannot_be_placed(self, sides):
        name = sides["unmapped"]["name"]

        team, resolution = sides["team_dao"].resolve_tournament_team(name, sides["age"], "Academy")
        assert team is None
        assert resolution.status == WRONG_SIDE
        assert resolution.reason == "wrong side: team has no league or division registration"

        team, resolution = sides["team_dao"].resolve_tournament_team(name, sides["age"], None)
        assert team["id"] == sides["unmapped"]["id"]

    @pytest.mark.parametrize("hint", ["ZZ No Such League", "HD", "Homegrown Division", "Home%", "_cademy"])
    def test_a_league_mt_does_not_have_is_an_unknown_league_not_a_wrong_side(self, sides, hint):
        team, resolution = sides["team_dao"].resolve_tournament_team(sides["flex_only"]["name"], sides["age"], hint)
        assert team is None
        assert resolution.status == UNKNOWN_LEAGUE
        assert resolution.reason == f"unknown league '{hint}'"

    def test_the_leagues_can_be_handed_in(self, sides):
        leagues = sides["team_dao"].league_rows()
        assert {"id", "name", "parent_league_id"} <= set(leagues[0])

        team, resolution = sides["team_dao"].resolve_tournament_team(
            sides["shared"], sides["age"], "Academy", leagues=leagues
        )
        assert resolution.status == RESOLVED
        assert team["id"] == sides["academy_team"]["id"]

    def test_an_unknown_name_is_missing(self, sides):
        team, resolution = sides["team_dao"].resolve_tournament_team(_unique("ZZ Nobody"), sides["age"], "Academy")
        assert team is None
        assert resolution.status == MISSING
        assert resolution.reason is None


class TestATeamMappedOnBothSidesAtOneAge:
    """Registered in a Homegrown and an Academy division at the same age group.

    Four production teams are. Such a team is not an answer to either hint.
    """

    def _both(self, sides, name: str | None = None) -> dict:
        team = sides["make_team"](name or _unique("ZZ Sides Both"), None, sides["homegrown_division_id"])
        sides["admin"].table("team_mappings").insert(
            {"team_id": team["id"], "age_group_id": sides["age"], "division_id": sides["academy_division_id"]}
        ).execute()
        return team

    @pytest.mark.parametrize("hint", ["Academy", "Homegrown"])
    def test_it_is_ambiguous_under_either_hint(self, sides, hint):
        both = self._both(sides)

        team, resolution = sides["team_dao"].resolve_tournament_team(both["name"], sides["age"], hint)

        assert team is None
        assert resolution.status == AMBIGUOUS
        assert resolution.reason == (
            f"ambiguous: team {both['id']} is registered as both Academy and Homegrown at this age group"
        )

    def test_with_no_hint_it_resolves(self, sides):
        both = self._both(sides)

        team, resolution = sides["team_dao"].resolve_tournament_team(both["name"], sides["age"], None)

        assert resolution.status == RESOLVED
        assert team["id"] == both["id"]

    def test_a_team_cleanly_on_the_hinted_side_wins(self, sides):
        # The shared name already has a clean Homegrown team and a clean Academy one.
        self._both(sides, sides["shared"])

        team, resolution = sides["team_dao"].resolve_tournament_team(sides["shared"], sides["age"], "Academy")
        assert resolution.status == RESOLVED
        assert team["id"] == sides["academy_team"]["id"]

        team, resolution = sides["team_dao"].resolve_tournament_team(sides["shared"], sides["age"], "Homegrown")
        assert resolution.status == RESOLVED
        assert team["id"] == sides["homegrown_team"]["id"]

    def test_at_an_age_it_is_not_registered_at_it_falls_back_and_answers(self, sides):
        # The rule is about the message's age group. With no registration
        # there its sides come from every age, as before.
        both = self._both(sides)

        team, resolution = sides["team_dao"].resolve_tournament_team(both["name"], sides["other_age"], "Academy")

        assert resolution.status == RESOLVED
        assert team["id"] == both["id"]


class TestAFeedNameIsTextNotAPattern:
    """% and _ are wildcards to ilike, and a trailing backslash is an error."""

    def _alias(self, sides, name: str, team: dict, league_id: int | None) -> None:
        sides["admin"].table("team_aliases").insert(
            {"team_id": team["id"], "external_name": name, "league_id": league_id, "source": "zz-sides-test"}
        ).execute()

    @pytest.mark.parametrize("scoped", [False, True])
    def test_a_percent_does_not_reach_an_alias_it_would_match_as_a_pattern(self, sides, scoped):
        spelling = _unique("ZZ Sides Pattern")
        self._alias(sides, spelling, sides["flex_only"], sides["homegrown_league_id"] if scoped else None)
        dao = sides["team_dao"]

        # The alias itself resolves...
        team, _ = dao.resolve_tournament_team(spelling, sides["age"], "Homegrown")
        assert team["id"] == sides["flex_only"]["id"]

        # ...and a name that is only a pattern for it does not.
        for pattern in (spelling[:-4] + "%", "%" + spelling[4:], "%"):
            team, resolution = dao.resolve_tournament_team(pattern, sides["age"], "Homegrown")
            assert team is None, pattern
            assert resolution.status == MISSING

    def test_an_underscore_does_not_stand_for_any_character(self, sides):
        spelling = _unique("ZZ Sides Under")
        self._alias(sides, spelling, sides["flex_only"], None)
        pattern = spelling.replace(" ", "_")

        team, resolution = sides["team_dao"].resolve_tournament_team(pattern, sides["age"], "Homegrown")

        assert team is None
        assert resolution.status == MISSING

    def test_a_pattern_does_not_reach_a_team_name_either(self, sides):
        name = sides["flex_only"]["name"]
        for pattern in (name[:-4] + "%", name.replace(" ", "_")):
            team, resolution = sides["team_dao"].resolve_tournament_team(pattern, sides["age"], "Homegrown")
            assert team is None, pattern
            assert resolution.status == MISSING

    @pytest.mark.parametrize("hint", ["Homegrown", None])
    def test_a_trailing_backslash_is_a_missing_name_not_a_database_error(self, sides, hint):
        name = sides["flex_only"]["name"] + "\\"

        team, resolution = sides["team_dao"].resolve_tournament_team(name, sides["age"], hint)

        assert team is None
        assert resolution.status == MISSING

    def test_names_that_really_contain_them_resolve(self, sides):
        percent = sides["make_team"](_unique("ZZ Sides 100%"), None, sides["academy_division_id"])
        under = sides["make_team"](_unique("ZZ_Sides_Under"), None, sides["academy_division_id"])
        slash = _unique("ZZ Sides Slash") + "\\" + "A"
        self._alias(sides, slash, under, None)

        for name, expected in ((percent["name"], percent), (under["name"], under), (slash, under)):
            team, resolution = sides["team_dao"].resolve_tournament_team(name.upper(), sides["age"], "Academy")
            assert resolution.status == RESOLVED, name
            assert team["id"] == expected["id"]


class TestAliases:
    def _alias(self, sides, name: str, team: dict, league_id: int | None) -> None:
        sides["admin"].table("team_aliases").insert(
            {"team_id": team["id"], "external_name": name, "league_id": league_id, "source": "zz-sides-test"}
        ).execute()

    def test_an_alias_scoped_to_the_messages_league_wins_over_the_exact_name(self, sides):
        # The Flex-only team owns the name; the Academy feed means another team by it (SB-1652).
        name = sides["flex_only"]["name"]
        self._alias(sides, name, sides["academy_team"], sides["academy_league_id"])

        team, resolution = sides["team_dao"].resolve_tournament_team(name, sides["age"], "Academy")
        assert resolution.status == RESOLVED
        assert team["id"] == sides["academy_team"]["id"]

        # The other side still gets the team that owns the name.
        team, _ = sides["team_dao"].resolve_tournament_team(name, sides["age"], "Homegrown")
        assert team["id"] == sides["flex_only"]["id"]

    def test_an_alias_with_no_league_is_still_checked_for_its_side(self, sides):
        spelling = _unique("ZZ Sides Spelling")
        self._alias(sides, spelling, sides["flex_only"], None)

        team, resolution = sides["team_dao"].resolve_tournament_team(spelling, sides["age"], "Homegrown")
        assert resolution.status == RESOLVED
        assert team["id"] == sides["flex_only"]["id"]

        team, resolution = sides["team_dao"].resolve_tournament_team(spelling, sides["age"], "Academy")
        assert team is None
        assert resolution.status == WRONG_SIDE

    def test_an_exact_name_shadows_a_league_agnostic_alias(self, sides):
        # A known shape, pinned as it stands. The Flex-only (Homegrown) team
        # owns the name; a league-agnostic alias gives the same string to the
        # Academy team. The alias is consulted only when no team has the name.
        name = sides["flex_only"]["name"]
        self._alias(sides, name, sides["academy_team"], None)

        team, resolution = sides["team_dao"].resolve_tournament_team(name, sides["age"], "Homegrown")
        assert resolution.status == RESOLVED
        assert team["id"] == sides["flex_only"]["id"]

        team, resolution = sides["team_dao"].resolve_tournament_team(name, sides["age"], "Academy")
        assert team is None
        assert resolution.status == WRONG_SIDE
        assert resolution.reason == "wrong side: exists as Homegrown"

    def test_an_alias_scoped_to_another_league_does_not_apply(self, sides):
        spelling = _unique("ZZ Sides Scoped")
        self._alias(sides, spelling, sides["academy_team"], sides["academy_league_id"])

        team, resolution = sides["team_dao"].resolve_tournament_team(spelling, sides["age"], "Homegrown")
        assert team is None
        assert resolution.status == MISSING


class TestClosingAFailureForOneSide:
    def _open_rows(self, sides) -> dict:
        rows = (
            sides["admin"]
            .table("ingest_failures")
            .select("league, resolved_at")
            .eq("source", sides["failure_source"])
            .execute()
            .data
        )
        return {row["league"]: row["resolved_at"] is None for row in rows}

    def _record_both(self, sides) -> None:
        for league in ("Homegrown", "Academy"):
            sides["failures_dao"].record("team", sides["shared"], league=league, source=sides["failure_source"])
        assert self._open_rows(sides) == {"Homegrown": True, "Academy": True}

    def test_a_homegrown_success_leaves_the_academy_row_open(self, sides):
        if not _function_installed(sides["admin"]):
            pytest.skip(NOT_INSTALLED)
        self._record_both(sides)

        closed = sides["failures_dao"].resolve_in_league(
            "team", sides["shared"], league="Homegrown", source=sides["failure_source"]
        )

        assert closed == 1
        assert self._open_rows(sides) == {"Homegrown": False, "Academy": True}

    def test_without_the_function_nothing_is_closed(self, sides):
        if _function_installed(sides["admin"]):
            pytest.skip(f"{RESOLVE_BY_LEAGUE}() is installed; the not-yet-migrated fallback cannot be shown here")
        self._record_both(sides)

        closed = sides["failures_dao"].resolve_in_league(
            "team", sides["shared"], league="Homegrown", source=sides["failure_source"]
        )

        assert closed is None
        assert self._open_rows(sides) == {"Homegrown": True, "Academy": True}

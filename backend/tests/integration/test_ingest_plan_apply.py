"""Planning and applying a tournament's teams against a real database (SB-1763).

A club MT holds only as its Homegrown team, named in a tournament on the
Academy side: the plan proposes the club's Academy team, and applying it
writes the team, its registration in its home conference — or none — and a
league-scoped alias from the feed's name. The rules are pure and tested in
``tests/unit/test_ingest_plan.py``; this is whether the rows land as the
resolver needs them, and whether applying twice, or after someone took the
name, is safe.

**The seeded teams have no user data** — no roster, no events, no matches —
which is every team at a tournament until a manager claims one.

Requires local Supabase. Skips cleanly if unreachable.
"""

from __future__ import annotations

import os
import uuid

import pytest

from dao.club_dao import ClubDAO
from dao.ingest_failures_dao import IngestFailuresDAO
from dao.ingest_plan import APPROVED, CREATE_TEAM, PROPOSED
from dao.ingest_plan_dao import ALIAS_SOURCE_PREFIX, IngestPlanDAO
from dao.match_dao import SupabaseConnection
from dao.team_dao import TeamDAO
from dao.team_sides import RESOLVED, WRONG_SIDE

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]


def _is_local(url: str | None) -> bool:
    return bool(url) and ("127.0.0.1" in url or "localhost" in url)


def _admin_client():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:55321")
    if not _is_local(url):
        pytest.skip(f"Refusing to run destructive test against non-local Supabase: {url}")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY not set — cannot run ingest plan test")
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


class _OwnFailures(IngestFailuresDAO):
    """Only this test's failure rows are open, as far as apply can see.

    Apply closes every open `team` failure that now resolves. Against a
    developer's database that would close rows this test did not make.
    """

    source: str

    def open_failures(self, since: str | None = None, limit: int = 200) -> list[dict]:
        return [row for row in super().open_failures(since=since, limit=1000) if row.get("source") == self.source]


@pytest.fixture
def world():
    """A club with one Homegrown team, named by a tournament on the Academy side."""
    admin = _admin_client()
    try:
        age_groups = admin.table("age_groups").select("id, name").order("id").limit(1).execute().data
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("Local Supabase not reachable")
    if not age_groups:
        pytest.skip("No age groups; seed the local DB first")

    homegrown, homegrown_division = _league_with_division(admin, "Homegrown")
    academy, academy_division = _league_with_division(admin, "Academy")

    connection = SupabaseConnection()
    if not _is_local(connection.url):
        pytest.skip(f"Refusing to run against non-local Supabase: {connection.url}")

    name = _unique("ZZ Plan River")
    academy_name = f"{name} Academy"
    source = _unique("zz-plan-source")
    club_ids: list[int] = []
    age = age_groups[0]

    def _teams_named(*names: str) -> list[int]:
        return [row["id"] for row in admin.table("teams").select("id").in_("name", list(names)).execute().data or []]

    try:
        club = admin.table("clubs").insert({"name": name, "city": "Nowhere"}).execute().data[0]
        club_ids.append(club["id"])
        team = (
            admin.table("teams").insert({"name": name, "club_id": club["id"], "league_id": homegrown["id"]}).execute()
        ).data[0]
        admin.table("team_mappings").insert(
            {"team_id": team["id"], "age_group_id": age["id"], "division_id": homegrown_division["id"]}
        ).execute()

        failures = _OwnFailures(connection)
        failures.source = source
        team_dao = TeamDAO(connection)
        dao = IngestPlanDAO(connection, team_dao=team_dao, club_dao=ClubDAO(connection), ingest_failures_dao=failures)
        yield {
            "admin": admin,
            "dao": dao,
            # As `mt ingest apply` sends it: with the fingerprint the plan was made against.
            "apply": lambda plan_id, actions, **kwargs: dao.apply(
                plan_id, actions, database=dao.database_fingerprint(), **kwargs
            ),
            "team_dao": team_dao,
            "name": name,
            "academy_name": academy_name,
            "club": club,
            "homegrown_team": team,
            "age": age,
            "academy": academy,
            "academy_division": academy_division,
            "source": source,
            "club_ids": club_ids,
            "entries": [{"name": name, "age_group": age["name"], "league": "Academy"}],
            "brackets": [
                {
                    "league": "Academy",
                    "conference": academy_division["name"],
                    "age_group": age["name"],
                    "teams": [name],
                }
            ],
        }
    finally:
        _quietly(lambda: admin.table("ingest_failures").delete().eq("source", source).execute())
        team_ids = []
        _quietly(lambda: team_ids.extend(_teams_named(name, academy_name)))
        if team_ids:
            _quietly(lambda: admin.table("team_aliases").delete().in_("team_id", team_ids).execute())
            _quietly(lambda: admin.table("team_mappings").delete().in_("team_id", team_ids).execute())
            _quietly(lambda: admin.table("teams").delete().in_("id", team_ids).execute())
        if club_ids:
            _quietly(lambda: admin.table("clubs").delete().in_("id", club_ids).execute())


def _approved_plan(world, *, brackets: bool) -> tuple[str, list[dict]]:
    plan = world["dao"].plan(world["entries"], world["brackets"] if brackets else None)
    (action,) = plan["actions"]
    assert (action["type"], action["status"]) == (CREATE_TEAM, PROPOSED)
    assert action["team_name"] == world["academy_name"]
    assert action["club_id"] == world["club"]["id"]
    return plan["plan_id"], [{**action, "status": APPROVED}]


def _rows(world, table: str, column: str, value) -> list[dict]:
    return world["admin"].table(table).select("*").eq(column, value).execute().data or []


def _created_team(world) -> dict:
    (team,) = _rows(world, "teams", "name", world["academy_name"])
    return team


class TestPlanning:
    def test_the_name_fails_on_the_academy_side_and_a_team_is_proposed(self, world):
        plan = world["dao"].plan(world["entries"], world["brackets"])

        side = plan["report"]["sides"]["Academy"]
        assert side["resolver"] == {"wrong_side": 1, "missing": 0}
        assert side["missing"] == {"total": 1, "alias_fixable": 0, "needs_create": 1, "unknown": 0}
        (action,) = plan["actions"]
        assert action["placements"] == [
            {"age_group": world["age"]["name"], "league": "Academy", "conference": world["academy_division"]["name"]}
        ]
        assert action["fixes"][0]["status"] == WRONG_SIDE

    def test_planning_creates_nothing(self, world):
        world["dao"].plan(world["entries"], world["brackets"])

        assert _rows(world, "teams", "name", world["academy_name"]) == []
        assert _rows(world, "team_aliases", "external_name", world["name"]) == []

    def test_a_fresh_plan_applied_as_generated_changes_nothing(self, world):
        plan = world["dao"].plan(world["entries"], world["brackets"])

        result = world["apply"](plan["plan_id"], plan["actions"])

        assert [row["outcome"] for row in result["results"]] == ["skipped"]
        assert _rows(world, "teams", "name", world["academy_name"]) == []


class TestApplying:
    def test_it_creates_the_team_in_its_league_and_conference_with_a_scoped_alias(self, world):
        plan_id, actions = _approved_plan(world, brackets=True)

        result = world["apply"](plan_id, actions)

        assert [row["outcome"] for row in result["results"]] == ["applied"]
        team = _created_team(world)
        assert (team["club_id"], team["league_id"]) == (world["club"]["id"], world["academy"]["id"])
        mappings = _rows(world, "team_mappings", "team_id", team["id"])
        assert [(m["age_group_id"], m["division_id"]) for m in mappings] == [
            (world["age"]["id"], world["academy_division"]["id"])
        ]
        (alias,) = _rows(world, "team_aliases", "team_id", team["id"])
        assert alias["external_name"] == world["name"]
        assert alias["league_id"] == world["academy"]["id"]
        assert alias["source"] == f"{ALIAS_SOURCE_PREFIX}{plan_id}"

    def test_the_feed_name_then_resolves_on_each_side_to_its_own_team(self, world):
        plan_id, actions = _approved_plan(world, brackets=True)
        world["apply"](plan_id, actions)
        created = _created_team(world)
        resolve = world["team_dao"].resolve_tournament_team

        team, resolution = resolve(world["name"], world["age"]["id"], "Academy")
        assert resolution.status == RESOLVED
        assert team["id"] == created["id"]

        team, resolution = resolve(world["name"], world["age"]["id"], "Homegrown")
        assert resolution.status == RESOLVED
        assert team["id"] == world["homegrown_team"]["id"]

    def test_a_team_without_a_conference_has_no_registration_and_still_resolves(self, world):
        plan_id, actions = _approved_plan(world, brackets=False)
        assert actions[0]["placements"] == []

        world["apply"](plan_id, actions)

        team = _created_team(world)
        assert team["league_id"] == world["academy"]["id"]
        assert _rows(world, "team_mappings", "team_id", team["id"]) == []
        resolved, resolution = world["team_dao"].resolve_tournament_team(world["name"], world["age"]["id"], "Academy")
        assert resolution.status == RESOLVED
        assert resolved["id"] == team["id"]

    def test_an_unplaced_team_is_in_no_age_group_picker(self, world):
        plan_id, actions = _approved_plan(world, brackets=False)
        world["apply"](plan_id, actions)
        team = _created_team(world)

        # Read past the DAO cache: this is what the age-group picker queries.
        mapped = (
            world["admin"].table("team_mappings").select("team_id").eq("age_group_id", world["age"]["id"]).execute()
        ).data
        assert team["id"] not in {row["team_id"] for row in mapped}

    def test_applying_again_reports_already_applied_and_changes_nothing(self, world):
        plan_id, actions = _approved_plan(world, brackets=True)
        world["apply"](plan_id, actions)
        team = _created_team(world)
        before = (
            _rows(world, "team_mappings", "team_id", team["id"]),
            _rows(world, "team_aliases", "team_id", team["id"]),
            _rows(world, "teams", "club_id", world["club"]["id"]),
        )

        again = world["apply"](plan_id, actions)

        assert [row["outcome"] for row in again["results"]] == ["already_applied"]
        assert again["summary"]["applied"] == 0
        after = (
            _rows(world, "team_mappings", "team_id", team["id"]),
            _rows(world, "team_aliases", "team_id", team["id"]),
            _rows(world, "teams", "club_id", world["club"]["id"]),
        )
        assert after == before

    def test_a_dry_run_writes_nothing(self, world):
        plan_id, actions = _approved_plan(world, brackets=True)

        result = world["apply"](plan_id, actions, dry_run=True)

        assert [row["outcome"] for row in result["results"]] == ["would_apply"]
        assert len(result["results"][0]["steps"]) == 3
        assert _rows(world, "teams", "name", world["academy_name"]) == []
        assert _rows(world, "team_aliases", "external_name", world["name"]) == []

    def test_a_name_taken_since_the_plan_is_refused(self, world):
        plan_id, actions = _approved_plan(world, brackets=True)
        # Since the plan: someone made a team by the proposed name, elsewhere.
        taken = world["admin"].table("teams").insert({"name": world["academy_name"].upper()}).execute().data[0]

        try:
            result = world["apply"](plan_id, actions)

            assert [row["outcome"] for row in result["results"]] == ["refused"]
            assert result["results"][0]["detail"] == (
                f"the name '{world['academy_name']}' is already taken by team {taken['id']}"
            )
            assert _rows(world, "teams", "name", world["academy_name"]) == []
            assert _rows(world, "team_aliases", "external_name", world["name"]) == []
        finally:
            _quietly(lambda: world["admin"].table("teams").delete().eq("id", taken["id"]).execute())

    def test_an_open_failure_for_the_name_is_closed_with_the_plan_named(self, world):
        admin = world["admin"]
        sample = f"{world['name']} vs Someone, 2026-12-02 {world['age']['name']} [wrong side: exists as Homegrown]"
        row = (
            admin.table("ingest_failures")
            .insert(
                {
                    "kind": "team",
                    "raw_name": world["name"],
                    "league": "Academy",
                    "source": world["source"],
                    "sample": sample,
                }
            )
            .execute()
        ).data[0]
        other = (
            admin.table("ingest_failures")
            .insert(
                {"kind": "team", "raw_name": _unique("ZZ Plan Nobody"), "league": "Academy", "source": world["source"]}
            )
            .execute()
        ).data[0]
        plan_id, actions = _approved_plan(world, brackets=True)

        result = world["apply"](plan_id, actions)

        assert [closed["id"] for closed in result["failures_closed"]] == [row["id"]]
        (closed,) = _rows(world, "ingest_failures", "id", row["id"])
        assert closed["resolved_at"] is not None
        assert closed["resolution_note"] == f"plan {plan_id}"
        (still_open,) = _rows(world, "ingest_failures", "id", other["id"])
        assert still_open["resolved_at"] is None


class TestTheSnapshotResolver:
    def test_it_agrees_with_the_resolver_ingest_uses(self, world):
        """The plan reads every team once; ingest asks per name. Same answers."""
        context = world["dao"]._context()
        for league in ("Academy", "Homegrown", None, "No Such League"):
            for name in (world["name"], world["name"].upper(), _unique("ZZ Plan Nobody")):
                planned = context.resolve(name, world["age"]["id"], league)
                team, live = world["team_dao"].resolve_tournament_team(name, world["age"]["id"], league)

                assert (planned.status, planned.reason) == (live.status, live.reason)
                assert planned.team_id == (team["id"] if team else None)


class TestWhatApplyRefuses:
    def test_a_plan_from_another_database_is_refused_before_anything_is_read(self, world):
        from dao.ingest_plan_dao import PlanDatabaseError

        plan = world["dao"].plan(world["entries"], world["brackets"])
        assert len(plan["database"]) == 12
        assert plan["database"] == world["dao"].database_fingerprint()
        actions = [{**plan["actions"][0], "status": APPROVED}]

        for database in (None, "ffffffffffff"):
            with pytest.raises(PlanDatabaseError):
                world["dao"].apply(plan["plan_id"], actions, database=database)
        assert _rows(world, "teams", "name", world["academy_name"]) == []

    def test_a_club_id_that_names_another_club_is_refused(self, world):
        plan_id, actions = _approved_plan(world, brackets=True)
        other = world["admin"].table("clubs").insert({"name": _unique("ZZ Plan Other"), "city": "Nowhere"}).execute()
        world["club_ids"].append(other.data[0]["id"])

        result = world["apply"](plan_id, [{**actions[0], "club_id": other.data[0]["id"]}])

        (row,) = result["results"]
        assert row["outcome"] == "refused"
        assert row["detail"] == f"club {other.data[0]['id']} is '{other.data[0]['name']}', not '{world['name']}'"
        assert _rows(world, "teams", "name", world["academy_name"]) == []

    def test_an_existing_team_is_not_repointed_at_a_name_that_resolves_elsewhere(self, world):
        """The adopt branch: same name, club and league — but the feed name is another team's."""
        admin = world["admin"]
        plan_id, actions = _approved_plan(world, brackets=True)
        world["apply"](plan_id, actions)
        created = _created_team(world)
        before = _rows(world, "team_aliases", "team_id", created["id"])
        # A name that already resolves, with no hint, to the Homegrown team.
        old_name = _unique("ZZ Plan Old Name")
        alias = (
            admin.table("team_aliases")
            .insert({"team_id": world["homegrown_team"]["id"], "external_name": old_name, "source": world["source"]})
            .execute()
        ).data[0]
        repoint = {
            **actions[0],
            "external_name": old_name,
            "placements": [],
            "fixes": [{"name": old_name, "age_group": world["age"]["name"], "league": None, "status": "missing"}],
        }

        try:
            result = world["apply"](plan_id, [repoint])

            (row,) = result["results"]
            assert row["outcome"] == "refused"
            assert row["detail"] == (
                f"'{old_name}' now resolves to team {world['homegrown_team']['id']}, "
                f"not to '{world['academy_name']}' ({created['id']})"
            )
            assert _rows(world, "team_aliases", "team_id", created["id"]) == before
        finally:
            _quietly(lambda: admin.table("team_aliases").delete().eq("id", alias["id"]).execute())


class TestWhatApplyReports:
    def test_the_ids_it_created_are_the_rows_that_exist(self, world):
        plan_id, actions = _approved_plan(world, brackets=True)

        (row,) = world["apply"](plan_id, actions)["results"]

        team = _created_team(world)
        (mapping,) = _rows(world, "team_mappings", "team_id", team["id"])
        (alias,) = _rows(world, "team_aliases", "team_id", team["id"])
        assert row["ids"] == {
            "club_id": world["club"]["id"],
            "team_id": team["id"],
            "team_created": True,
            "mapping_ids": [mapping["id"]],
            "alias_id": alias["id"],
        }

    def test_a_failure_row_with_no_age_group_in_its_sample_is_left_open(self, world):
        row = (
            world["admin"]
            .table("ingest_failures")
            .insert({"kind": "team", "raw_name": world["name"], "league": "Academy", "source": world["source"]})
            .execute()
        ).data[0]
        plan_id, actions = _approved_plan(world, brackets=True)

        result = world["apply"](plan_id, actions)

        assert result["failures_closed"] == []
        (still_open,) = _rows(world, "ingest_failures", "id", row["id"])
        assert still_open["resolved_at"] is None

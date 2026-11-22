"""`mt ingest plan` and `mt ingest apply`, server side, without a database (SB-1763).

Two layers. The endpoints, on the real app with the caller swapped in: both
are admin only — not service accounts, because applying creates teams and the
approval is a person's. And IngestPlanDAO over an in-memory stand-in for the
Supabase client that records every write, with the real TeamDAO, ClubDAO and
IngestFailuresDAO on top of it: planning writes nothing, and applying reports
each action on its own.

The teams here have scraped identity and nothing else — no roster, no events.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from dao.club_dao import ClubDAO
from dao.ingest_failures_dao import IngestFailuresDAO
from dao.ingest_plan import APPROVED, PlanInputError
from dao.ingest_plan_dao import IngestPlanDAO
from dao.team_dao import TeamDAO

pytestmark = pytest.mark.unit

ADMIN = {"user_id": "admin-1", "username": "admin", "role": "admin"}
SCRAPER = {"service_id": "service-match-scraper", "role": "service_account", "permissions": ["manage_matches"]}
MANAGER = {"user_id": "u1", "role": "team-manager"}

HOMEGROWN, ACADEMY, FLEX = 1, 2, 290
U15, U16 = 3, 4
NORTHEAST, NEW_ENGLAND = 10, 20


# --- An in-memory stand-in for the Supabase client ---------------------------


class _Query:
    def __init__(self, db: FakeDB, table: str):
        self.db, self.table = db, table
        self.filters: list = []
        self.op, self.payload = "select", None
        self.window: tuple[int, int] | None = None
        self.max: int | None = None

    def select(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters.append(lambda row: row.get(column) == value)
        return self

    def is_(self, column, _null):
        self.filters.append(lambda row: row.get(column) is None)
        return self

    def in_(self, column, values):
        self.filters.append(lambda row: row.get(column) in values)
        return self

    def ilike(self, column, pattern):
        # Only what the DAOs send: a literal, or %word%.
        text = pattern.replace("\\", "").casefold()
        if text.startswith("%") and text.endswith("%"):
            self.filters.append(lambda row: text.strip("%") in (row.get(column) or "").casefold())
        else:
            self.filters.append(lambda row: (row.get(column) or "").casefold() == text)
        return self

    def range(self, start, end):
        self.window = (start, end)
        return self

    def limit(self, count):
        self.max = count
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def delete(self):
        self.op = "delete"
        return self

    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        if self.op == "insert":
            row = {"id": self.db.next_id(), **self.payload}
            rows.append(row)
            self.db.writes.append(("insert", self.table, dict(self.payload)))
            return MagicMock(data=[dict(row)])
        found = [row for row in rows if all(test(row) for test in self.filters)]
        if self.op == "update":
            for row in found:
                row.update(self.payload)
            self.db.writes.append(("update", self.table, dict(self.payload)))
            return MagicMock(data=[dict(row) for row in found])
        if self.op == "delete":
            self.db.writes.append(("delete", self.table, None))
            return MagicMock(data=[])
        found = sorted(found, key=lambda row: row["id"])
        if self.window:
            found = found[self.window[0] : self.window[1] + 1]
        if self.max is not None:
            found = found[: self.max]
        return MagicMock(data=[self.db.read(self.table, row) for row in found])


class FakeDB:
    """Tables as lists of rows. `writes` is every insert, update, delete and rpc."""

    def __init__(self, **tables):
        self.tables = {name: [dict(row) for row in rows] for name, rows in tables.items()}
        self.writes: list = []
        self._id = 1000

    def next_id(self) -> int:
        self._id += 1
        return self._id

    def table(self, name):
        return _Query(self, name)

    def rpc(self, name, params=None):
        self.writes.append(("rpc", name, params))
        return MagicMock(execute=lambda: MagicMock(data=[]))

    def read(self, table: str, row: dict) -> dict:
        out = dict(row)
        if table == "teams":
            divisions = {d["id"]: d for d in self.tables.get("divisions", [])}
            out["team_mappings"] = [
                {
                    "age_group_id": m["age_group_id"],
                    "divisions": {"league_id": divisions[m["division_id"]]["league_id"]},
                }
                for m in self.tables.get("team_mappings", [])
                if m["team_id"] == row["id"]
            ]
        return out


def _over(cls, db: FakeDB):
    dao = object.__new__(cls)
    dao.connection_holder = MagicMock(url="http://db.test:55321")
    dao.client = db
    return dao


def _db(**extra) -> FakeDB:
    tables = {
        "leagues": [
            {"id": HOMEGROWN, "name": "Homegrown", "parent_league_id": None},
            {"id": ACADEMY, "name": "Academy", "parent_league_id": None},
            {"id": FLEX, "name": "Flex", "parent_league_id": HOMEGROWN},
        ],
        "divisions": [
            {"id": NORTHEAST, "name": "Northeast", "league_id": HOMEGROWN},
            {"id": NEW_ENGLAND, "name": "New England", "league_id": ACADEMY},
        ],
        "age_groups": [{"id": U15, "name": "U15"}, {"id": U16, "name": "U16"}],
        "clubs": [{"id": 1, "name": "River FC"}, {"id": 2, "name": "Lake United"}],
        "teams": [
            {"id": 11, "name": "River FC", "city": None, "club_id": 1, "league_id": FLEX},
            {"id": 12, "name": "River FC Academy", "city": None, "club_id": 1, "league_id": ACADEMY},
            {"id": 21, "name": "Lake United", "city": None, "club_id": 2, "league_id": FLEX},
        ],
        "team_mappings": [
            {"id": 1, "team_id": 11, "age_group_id": U15, "division_id": NORTHEAST},
            {"id": 2, "team_id": 12, "age_group_id": U15, "division_id": NEW_ENGLAND},
            {"id": 3, "team_id": 21, "age_group_id": U15, "division_id": NORTHEAST},
        ],
        "team_aliases": [],
        "ingest_failures": [],
    }
    tables.update(extra)
    return FakeDB(**tables)


def _dao(db: FakeDB) -> IngestPlanDAO:
    dao = _over(IngestPlanDAO, db)
    dao.team_dao = _over(TeamDAO, db)
    dao.club_dao = _over(ClubDAO, db)
    dao.ingest_failures_dao = _over(IngestFailuresDAO, db)
    return dao


TEAMS_INPUT = [
    {"home_team": "River FC", "away_team": "Lake United", "age_group": "U15", "league": "Academy"},
    {"home_team": "River FC", "away_team": "Lake United", "age_group": "U15", "league": "Homegrown"},
    {"home_team": "Nowhere SC", "away_team": "TBD", "age_group": "U15", "league": "Academy"},
]


def _approved(plan: dict) -> list[dict]:
    return [{**action, "status": APPROVED} for action in plan["actions"]]


# --- The DAO ----------------------------------------------------------------


class TestPlanning:
    def test_it_writes_nothing(self):
        db = _db()
        _dao(db).plan(
            TEAMS_INPUT, [{"league": "Academy", "conference": "New England", "age_group": "U15", "teams": []}]
        )

        assert db.writes == []

    def test_it_writes_nothing_even_with_open_failures_it_could_close(self):
        failure = {"id": 5, "kind": "team", "raw_name": "River FC", "league": "Homegrown", "resolved_at": None}
        db = _db(ingest_failures=[failure])
        _dao(db).plan(TEAMS_INPUT)

        assert db.writes == []
        assert db.tables["ingest_failures"][0]["resolved_at"] is None

    def test_the_verdicts_are_the_resolvers(self):
        plan = _dao(_db()).plan(TEAMS_INPUT)
        sides = plan["report"]["sides"]

        assert sides["Homegrown"]["resolved"] == 2
        assert sides["Academy"]["resolver"] == {"wrong_side": 2, "missing": 2}
        assert sides["Academy"]["missing"] == {"total": 4, "alias_fixable": 1, "needs_create": 2, "unknown": 1}
        assert plan["report"]["matches"] == {"total": 3, "would_land": 1, "would_land_after_plan": 2}
        assert plan["plan_id"].startswith("plan-")

    def test_it_proposes_an_alias_a_side_team_and_a_new_club(self):
        actions = _dao(_db()).plan(TEAMS_INPUT)["actions"]

        assert [(a["type"], a["status"], a["external_name"]) for a in actions] == [
            ("alias", "proposed", "River FC"),
            ("create_team", "proposed", "Lake United"),
            ("create_team", "needs_review", "Nowhere SC"),
        ]
        assert actions[0]["team_id"] == 12
        assert actions[1]["team_name"] == "Lake United Academy"

    def test_unreadable_input_is_a_plan_input_error(self):
        with pytest.raises(PlanInputError):
            _dao(_db()).plan([{"age_group": "U15"}])


class TestApplying:
    def test_a_fresh_plan_applies_nothing(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        result = dao.apply(plan["plan_id"], plan["actions"], database=plan["database"])

        assert [row["outcome"] for row in result["results"]] == ["skipped", "skipped", "skipped"]
        assert {row["detail"] for row in result["results"]} == {"not approved"}
        assert result["summary"]["skipped"] == 3
        assert db.writes == []

    def test_a_dry_run_checks_everything_and_writes_nothing(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        result = dao.apply(plan["plan_id"], _approved(plan), dry_run=True, database=plan["database"])

        assert [row["outcome"] for row in result["results"]] == ["would_apply", "would_apply", "would_apply"]
        assert result["results"][1]["steps"] == [
            "create team 'Lake United Academy' (Academy)",
            "alias 'Lake United' (Academy) → 'Lake United Academy'",
        ]
        assert result["results"][2]["steps"] == ["create club 'Nowhere SC'", "create team 'Nowhere SC' (Academy)"]
        assert result["dry_run"] is True
        assert db.writes == []

    def test_each_action_is_reported_on_its_own(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)
        alias, create, unknown = plan["actions"]
        actions = [
            {**alias, "status": APPROVED},
            create,  # left as proposed
            {**unknown, "status": APPROVED, "team_name": "River FC"},  # a name that is taken
            {**alias, "status": APPROVED, "team_id": 999},  # a team that does not exist
            {"type": "merge", "status": APPROVED},
        ]

        result = dao.apply(plan["plan_id"], actions, user_id="admin-1", database=plan["database"])

        assert [(row["outcome"], row["detail"]) for row in result["results"]] == [
            ("applied", None),
            ("skipped", "not approved"),
            ("refused", "the name 'River FC' is already taken by team 11"),
            ("refused", "team 999 does not exist"),
            ("refused", "unknown action type 'merge'"),
        ]
        assert result["summary"] == {
            "applied": 1,
            "would_apply": 0,
            "already_applied": 0,
            "refused": 3,
            "skipped": 1,
            "failed": 0,
        }
        # One refusal did not stop the alias, and nothing else was written.
        assert [(op, table) for op, table, _ in db.writes] == [("insert", "team_aliases")]

    def test_the_alias_is_scoped_to_the_league_and_names_the_plan(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        dao.apply(plan["plan_id"], _approved(plan)[:1], database=plan["database"])

        (alias,) = db.tables["team_aliases"]
        assert (alias["team_id"], alias["external_name"], alias["league_id"]) == (12, "River FC", ACADEMY)
        assert alias["source"] == f"ingest-plan:{plan['plan_id']}"

    def test_a_created_team_gets_its_league_and_no_registration_without_a_conference(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        result = dao.apply(plan["plan_id"], _approved(plan)[1:2], database=plan["database"])

        assert result["results"][0]["outcome"] == "applied"
        team = next(row for row in db.tables["teams"] if row["name"] == "Lake United Academy")
        assert (team["club_id"], team["league_id"]) == (2, ACADEMY)
        assert [m for m in db.tables["team_mappings"] if m["team_id"] == team["id"]] == []
        (alias,) = db.tables["team_aliases"]
        assert (alias["team_id"], alias["external_name"], alias["league_id"]) == (team["id"], "Lake United", ACADEMY)

    def test_a_placed_team_is_registered_only_where_the_plan_says(self):
        db = _db()
        dao = _dao(db)
        brackets = [{"league": "Academy", "conference": "New England", "age_group": "U15", "teams": ["Lake United"]}]
        plan = dao.plan(TEAMS_INPUT, brackets)

        dao.apply(plan["plan_id"], _approved(plan)[1:2], database=plan["database"])

        team = next(row for row in db.tables["teams"] if row["name"] == "Lake United Academy")
        mappings = [m for m in db.tables["team_mappings"] if m["team_id"] == team["id"]]
        assert [(m["age_group_id"], m["division_id"]) for m in mappings] == [(U15, NEW_ENGLAND)]

    def test_applying_twice_changes_nothing_the_second_time(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)
        dao.apply(plan["plan_id"], _approved(plan), database=plan["database"])
        written = list(db.writes)

        again = dao.apply(plan["plan_id"], _approved(plan), database=plan["database"])

        assert [row["outcome"] for row in again["results"]] == ["already_applied"] * 3
        assert db.writes == written

    def test_a_conference_mt_does_not_have_refuses_the_action(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)
        create = {
            **plan["actions"][1],
            "status": APPROVED,
            "placements": [{"age_group": "U15", "league": "Academy", "conference": "Atlantis"}],
        }

        result = dao.apply(plan["plan_id"], [create], database=plan["database"])

        assert result["results"][0]["outcome"] == "refused"
        assert result["results"][0]["detail"] == "MT has no conference 'Atlantis' in Academy"
        assert db.writes == []

    def test_a_conference_on_the_other_side_refuses_the_action(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)
        create = {
            **plan["actions"][1],
            "status": APPROVED,
            "placements": [{"age_group": "U15", "league": "Homegrown", "conference": "Northeast"}],
        }

        result = dao.apply(plan["plan_id"], [create], database=plan["database"])

        assert result["results"][0]["detail"] == "Homegrown Northeast (U15) is not a Academy conference"
        assert db.writes == []

    def test_an_alias_to_a_team_on_the_other_side_is_refused(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        moved = {**plan["actions"][0], "status": APPROVED, "team_id": 21, "team_name": "Lake United"}
        result = dao.apply(plan["plan_id"], [moved], database=plan["database"])

        assert result["results"][0]["detail"] == (
            "team 21 ('Lake United') is not on the Academy side at U15: it is Homegrown there"
        )
        assert db.writes == []

    def test_a_name_that_no_longer_fails_the_way_the_plan_says_is_refused(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)
        # Since the plan: the Homegrown team that owned the name is gone.
        db.tables["teams"] = [row for row in db.tables["teams"] if row["id"] != 11]

        result = dao.apply(plan["plan_id"], _approved(plan)[:1], database=plan["database"])

        assert result["results"][0]["outcome"] == "refused"
        assert result["results"][0]["detail"] == (
            "'River FC' (U15, Academy) no longer fails as wrong_side: it is now missing"
        )
        assert db.writes == []

    def test_open_failures_that_now_resolve_are_closed_with_the_plan_named(self):
        failures = [
            {
                "id": 5,
                "kind": "team",
                "raw_name": "River FC",
                "league": "Academy",
                "sample": "River FC vs Lake United, 2026-12-02 U15 [wrong side: exists as Homegrown]",
                "resolved_at": None,
            },
            {"id": 6, "kind": "team", "raw_name": "Nowhere SC", "league": "Academy", "resolved_at": None},
            {"id": 7, "kind": "division", "raw_name": "River FC", "league": "Academy", "resolved_at": None},
        ]
        db = _db(ingest_failures=failures)
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        result = dao.apply(plan["plan_id"], _approved(plan)[:1], user_id="admin-1", database=plan["database"])

        assert result["failures_closed"] == [{"id": 5, "raw_name": "River FC", "league": "Academy", "team_id": 12}]
        closed, still_missing, other_kind = db.tables["ingest_failures"]
        assert closed["resolution_note"] == f"plan {plan['plan_id']}"
        assert closed["resolved_by"] == "admin-1"
        assert still_missing["resolved_at"] is None
        assert other_kind["resolved_at"] is None

    def test_a_dry_run_closes_no_failures(self):
        failure = {"id": 5, "kind": "team", "raw_name": "River FC", "league": "Homegrown", "resolved_at": None}
        db = _db(ingest_failures=[failure])
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        result = dao.apply(plan["plan_id"], _approved(plan), dry_run=True, database=plan["database"])

        assert result["failures_closed"] == []
        assert db.writes == []

    def test_the_teams_cache_is_cleared_once_writes_are_done(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        with patch("dao.ingest_plan_dao.clear_cache") as clear:
            dao.apply(plan["plan_id"], _approved(plan)[:1], database=plan["database"])
            assert clear.call_args_list[-2].args == ("mt:dao:teams:*",)

        with patch("dao.ingest_plan_dao.clear_cache") as clear:
            dao.apply(plan["plan_id"], plan["actions"], database=plan["database"])
            clear.assert_not_called()


# --- The endpoints ----------------------------------------------------------


@pytest.fixture
def as_caller():
    """The real role checks, with the authenticated caller swapped in."""
    import app as app_module
    from auth import get_current_user_required

    dao = MagicMock()
    dao.plan.return_value = {"plan_id": "plan-1", "report": {}, "actions": []}
    dao.apply.return_value = {"plan_id": "plan-1", "dry_run": False, "results": [], "summary": {}}
    caller: dict = {}
    app_module.app.dependency_overrides[get_current_user_required] = lambda: caller["user"]

    def use(user):
        caller["user"] = user
        return TestClient(app_module.app), dao

    with patch.object(app_module, "ingest_plan_dao", dao):
        yield use
    app_module.app.dependency_overrides.clear()


PLAN_BODY = {"teams": [{"name": "River FC", "age_group": "U15", "league": "Academy"}]}
APPLY_BODY = {"plan_id": "plan-1", "database": "0123456789ab", "actions": [{"type": "alias", "status": "approved"}]}


class TestTheEndpoints:
    @pytest.mark.parametrize("caller", [SCRAPER, MANAGER])
    def test_planning_is_admin_only(self, as_caller, caller):
        http, dao = as_caller(caller)

        assert http.post("/api/admin/ingest-plan", json=PLAN_BODY).status_code == 403
        dao.plan.assert_not_called()

    @pytest.mark.parametrize("caller", [SCRAPER, MANAGER])
    def test_applying_is_admin_only(self, as_caller, caller):
        http, dao = as_caller(caller)

        assert http.post("/api/admin/ingest-plan/apply", json=APPLY_BODY).status_code == 403
        dao.apply.assert_not_called()

    def test_an_admin_plans_and_only_plans(self, as_caller):
        http, dao = as_caller(ADMIN)
        brackets = [{"league": "Academy", "conference": "New England", "age_group": "U15", "teams": ["River FC"]}]

        response = http.post("/api/admin/ingest-plan", json={**PLAN_BODY, "brackets": brackets})

        assert response.status_code == 200
        assert response.json() == {"plan_id": "plan-1", "report": {}, "actions": []}
        dao.plan.assert_called_once_with(PLAN_BODY["teams"], brackets)
        dao.apply.assert_not_called()

    def test_input_the_planner_cannot_read_is_422_with_the_reason(self, as_caller):
        http, dao = as_caller(ADMIN)
        dao.plan.side_effect = PlanInputError("teams[0]: 'age_group' is missing")

        response = http.post("/api/admin/ingest-plan", json=PLAN_BODY)

        assert response.status_code == 422
        assert response.json()["detail"] == "teams[0]: 'age_group' is missing"

    def test_an_empty_teams_list_is_422(self, as_caller):
        http, dao = as_caller(ADMIN)

        assert http.post("/api/admin/ingest-plan", json={"teams": []}).status_code == 422
        dao.plan.assert_not_called()

    def test_a_database_error_does_not_leak(self, as_caller):
        http, dao = as_caller(ADMIN)
        dao.plan.side_effect = RuntimeError("connection to 10.0.0.5 refused")

        response = http.post("/api/admin/ingest-plan", json=PLAN_BODY)

        assert response.status_code == 500
        assert response.json()["detail"] == "Could not build the ingest plan"

    def test_apply_passes_the_plan_the_flag_and_who(self, as_caller):
        http, dao = as_caller(ADMIN)

        response = http.post("/api/admin/ingest-plan/apply", json={**APPLY_BODY, "dry_run": True})

        assert response.status_code == 200
        dao.apply.assert_called_once_with(
            "plan-1", APPLY_BODY["actions"], database="0123456789ab", dry_run=True, user_id="admin-1"
        )

    def test_apply_is_not_a_dry_run_unless_asked(self, as_caller):
        http, dao = as_caller(ADMIN)

        http.post("/api/admin/ingest-plan/apply", json=APPLY_BODY)

        assert dao.apply.call_args.kwargs["dry_run"] is False

    def test_apply_returns_each_actions_outcome(self, as_caller):
        http, dao = as_caller(ADMIN)
        dao.apply.return_value = {
            "plan_id": "plan-1",
            "dry_run": False,
            "results": [
                {"id": "a001", "outcome": "applied", "detail": None},
                {"id": "a002", "outcome": "refused", "detail": "team 9 does not exist"},
                {"id": "a003", "outcome": "skipped", "detail": "not approved"},
            ],
            "summary": {"applied": 1, "refused": 1, "skipped": 1},
            "failures_closed": [],
        }

        body = http.post("/api/admin/ingest-plan/apply", json=APPLY_BODY).json()

        assert [row["outcome"] for row in body["results"]] == ["applied", "refused", "skipped"]
        assert body["results"][1]["detail"] == "team 9 does not exist"


# --- What apply re-checks on a hand-edited action (review of SB-1763) ---------


def _apply(dao, plan, actions, **kwargs):
    return dao.apply(plan["plan_id"], actions, database=plan["database"], **kwargs)


def _only(result) -> tuple[str, str | None]:
    (row,) = result["results"]
    return row["outcome"], row["detail"]


class TestIdsMustNameWhatThePlanSays:
    def test_an_alias_whose_team_id_is_another_team_is_refused(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)
        # team_id edited to Lake United's; the label still says River FC Academy.
        edited = {**plan["actions"][0], "status": APPROVED, "team_id": 21}

        for dry_run in (True, False):
            assert _only(_apply(dao, plan, [edited], dry_run=dry_run)) == (
                "refused",
                "team 21 is 'Lake United', not 'River FC Academy'",
            )
        assert db.writes == []

    def test_a_create_whose_club_id_is_another_club_is_refused(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)
        edited = {**plan["actions"][1], "status": APPROVED, "club_id": 1}

        for dry_run in (True, False):
            assert _only(_apply(dao, plan, [edited], dry_run=dry_run)) == (
                "refused",
                "club 1 is 'River FC', not 'Lake United'",
            )
        assert db.writes == []

    def test_the_names_are_compared_without_case_or_spacing(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)
        alias = {**plan["actions"][0], "status": APPROVED, "team_name": "  river fc   ACADEMY "}

        assert _only(_apply(dao, plan, [alias]))[0] == "applied"


class TestAdoptingAnExistingTeam:
    def _repoint(self, **changes) -> dict:
        """A create whose team already exists, for a name that resolves elsewhere."""
        return {
            "id": "a001",
            "type": "create_team",
            "status": APPROVED,
            "external_name": "Old River",
            "league": "Academy",
            "club_id": 1,
            "club_name": "River FC",
            "new_club_name": None,
            "team_name": "River FC Academy",
            "placements": [{"age_group": "U16", "league": "Academy", "conference": "New England"}],
            "fixes": [{"name": "Old River", "age_group": "U15", "league": None, "status": "missing"}],
            **changes,
        }

    def test_it_does_not_repoint_a_name_that_resolves_to_another_team(self):
        old_name = {"id": 1, "team_id": 11, "league_id": None, "external_name": "Old River", "source": "kitman"}
        db = _db(team_aliases=[old_name])
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        for dry_run in (True, False):
            assert _only(_apply(dao, plan, [self._repoint()], dry_run=dry_run)) == (
                "refused",
                "'Old River' now resolves to team 11, not to 'River FC Academy' (12)",
            )
        # Neither the alias nor the registration was added to the adopted team.
        assert db.writes == []

    def test_empty_fixes_are_refused_for_a_create_as_for_an_alias(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)
        alias, create, _ = _approved(plan)
        nothing = "the action lists no entries it fixes, so there is nothing to check it against"

        result = _apply(dao, plan, [{**create, "fixes": []}, {**alias, "fixes": []}, self._repoint(fixes=[])])

        assert [(row["outcome"], row["detail"]) for row in result["results"]] == [("refused", nothing)] * 3
        assert db.writes == []

    def test_a_reapply_after_a_failure_part_way_finishes_the_rest(self):
        db = _db()
        dao = _dao(db)
        brackets = [{"league": "Academy", "conference": "New England", "age_group": "U15", "teams": ["Lake United"]}]
        plan = dao.plan(TEAMS_INPUT, brackets)
        create = _approved(plan)[1]

        dao.team_dao.add_team_alias = MagicMock(side_effect=RuntimeError("connection reset"))
        failed = _apply(dao, plan, [create])
        del dao.team_dao.add_team_alias

        (row,) = failed["results"]
        assert (row["outcome"], row["detail"]) == ("failed", "stopped after 2 of 3 steps; apply again to finish")
        team = next(t for t in db.tables["teams"] if t["name"] == "Lake United Academy")
        assert row["ids"]["team_id"] == team["id"]
        assert db.tables["team_aliases"] == []

        again = _apply(dao, plan, [create])

        (row,) = again["results"]
        assert row["outcome"] == "applied"
        assert row["steps"] == ["alias 'Lake United' (Academy) → 'Lake United Academy'"]
        assert [t["id"] for t in db.tables["teams"] if t["name"] == "Lake United Academy"] == [team["id"]]
        assert len([m for m in db.tables["team_mappings"] if m["team_id"] == team["id"]]) == 1
        assert [a["team_id"] for a in db.tables["team_aliases"]] == [team["id"]]
        assert _only(_apply(dao, plan, [create]))[0] == "already_applied"


class TestTheAliasTargetsSideAtEachAge:
    @staticmethod
    def _with(team_mappings):
        team = {"id": 14, "name": "River Mixed", "city": None, "club_id": 1, "league_id": FLEX}
        base = _db()
        return _db(teams=[*base.tables["teams"], team], team_mappings=[*base.tables["team_mappings"], *team_mappings])

    def _alias_to_14(self, dao):
        plan = dao.plan(TEAMS_INPUT)
        alias = next(a for a in plan["actions"] if a["type"] == "alias" and a["external_name"] == "River FC")
        return plan, {**alias, "status": APPROVED, "team_id": 14, "team_name": "River Mixed"}

    def test_a_team_on_the_other_side_at_that_age_is_refused_whatever_it_is_elsewhere(self):
        # Homegrown at U15, the age the alias fixes; Academy only at U16.
        db = self._with(
            [
                {"id": 8, "team_id": 14, "age_group_id": U15, "division_id": NORTHEAST},
                {"id": 9, "team_id": 14, "age_group_id": U16, "division_id": NEW_ENGLAND},
            ]
        )
        dao = _dao(db)
        plan, alias = self._alias_to_14(dao)

        assert _only(_apply(dao, plan, [alias])) == (
            "refused",
            "team 14 ('River Mixed') is not on the Academy side at U15: it is Homegrown there",
        )
        assert db.writes == []

    def test_a_team_on_both_sides_at_that_age_is_refused(self):
        db = self._with(
            [
                {"id": 8, "team_id": 14, "age_group_id": U15, "division_id": NORTHEAST},
                {"id": 9, "team_id": 14, "age_group_id": U15, "division_id": NEW_ENGLAND},
            ]
        )
        dao = _dao(db)
        plan, alias = self._alias_to_14(dao)

        assert _only(_apply(dao, plan, [alias])) == (
            "refused",
            "team 14 ('River Mixed') is not on the Academy side at U15: it is Academy, Homegrown there",
        )
        assert db.writes == []

    def test_a_team_on_the_side_at_that_age_is_accepted(self):
        db = self._with([{"id": 8, "team_id": 14, "age_group_id": U15, "division_id": NEW_ENGLAND}])
        dao = _dao(db)
        plan, alias = self._alias_to_14(dao)

        # The plan itself now needs a person to choose between 12 and 14.
        assert alias["candidates"] and [c["team_id"] for c in alias["candidates"]] == [12, 14]
        assert _only(_apply(dao, plan, [alias]))[0] == "applied"


class TestTheDatabaseFingerprint:
    def test_a_plan_carries_a_fingerprint_that_is_not_the_url(self):
        plan = _dao(_db()).plan(TEAMS_INPUT)

        assert len(plan["database"]) == 12
        assert all(character in "0123456789abcdef" for character in plan["database"])
        assert "db.test" not in plan["database"]

    def test_two_databases_have_different_fingerprints(self):
        here, there = _dao(_db()), _dao(_db())
        there.connection_holder.url = "https://another.example.co"

        assert here.database_fingerprint() != there.database_fingerprint()
        assert here.database_fingerprint() == _dao(_db()).database_fingerprint()

    @pytest.mark.parametrize("database", [None, ""])
    def test_a_plan_with_no_fingerprint_is_refused_whole(self, database):
        from dao.ingest_plan_dao import PlanDatabaseError

        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        for dry_run in (True, False):
            with pytest.raises(PlanDatabaseError, match="does not say which database"):
                dao.apply(plan["plan_id"], _approved(plan), database=database, dry_run=dry_run)
        assert db.writes == []

    def test_a_plan_from_another_database_is_refused_whole(self):
        from dao.ingest_plan_dao import PlanDatabaseError

        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)
        dao._context = MagicMock(side_effect=AssertionError("no action may be looked at"))

        for dry_run in (True, False):
            with pytest.raises(PlanDatabaseError, match="made against another database"):
                dao.apply(plan["plan_id"], _approved(plan), database="ffffffffffff", dry_run=dry_run)
        assert db.writes == []

    def test_the_right_fingerprint_is_applied(self):
        dao = _dao(_db())
        plan = dao.plan(TEAMS_INPUT)

        result = dao.apply(plan["plan_id"], _approved(plan)[:1], database=dao.database_fingerprint())

        assert _only(result)[0] == "applied"

    def test_the_endpoint_answers_409_with_the_reason(self, as_caller):
        from dao.ingest_plan_dao import PlanDatabaseError

        http, dao = as_caller(ADMIN)
        dao.apply.side_effect = PlanDatabaseError("The plan was made against another database (aaa); this one is bbb.")

        response = http.post("/api/admin/ingest-plan/apply", json=APPLY_BODY)

        assert response.status_code == 409
        assert "another database" in response.json()["detail"]

    def test_the_endpoint_passes_a_missing_fingerprint_on_to_be_refused(self, as_caller):
        http, dao = as_caller(ADMIN)

        http.post("/api/admin/ingest-plan/apply", json={"plan_id": "plan-1", "actions": []})

        assert dao.apply.call_args.kwargs["database"] is None


class TestWhatAnActionWrote:
    def test_an_alias_reports_the_team_and_the_alias_row(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        (row,) = _apply(dao, plan, _approved(plan)[:1])["results"]

        (alias,) = db.tables["team_aliases"]
        assert row["ids"] == {"team_id": 12, "alias_id": alias["id"]}

    def test_a_created_team_reports_every_row_it_made(self):
        db = _db()
        dao = _dao(db)
        brackets = [{"league": "Academy", "conference": "New England", "age_group": "U15", "teams": ["Lake United"]}]
        plan = dao.plan(TEAMS_INPUT, brackets)

        (row,) = _apply(dao, plan, _approved(plan)[1:2])["results"]

        team = next(t for t in db.tables["teams"] if t["name"] == "Lake United Academy")
        (mapping,) = [m for m in db.tables["team_mappings"] if m["team_id"] == team["id"]]
        (alias,) = db.tables["team_aliases"]
        assert row["ids"] == {
            "club_id": 2,
            "team_id": team["id"],
            "team_created": True,
            "mapping_ids": [mapping["id"]],
            "alias_id": alias["id"],
        }

    def test_a_new_club_is_reported_as_created(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        (row,) = _apply(dao, plan, _approved(plan)[2:])["results"]

        club = next(c for c in db.tables["clubs"] if c["name"] == "Nowhere SC")
        assert row["ids"]["club_id"] == club["id"]
        assert row["ids"]["club_created"] is True
        assert club["description"] == f"Created by mt ingest plan {plan['plan_id']}"

    def test_nothing_written_reports_no_ids(self):
        dao = _dao(_db())
        plan = dao.plan(TEAMS_INPUT)
        _apply(dao, plan, _approved(plan))

        rows = _apply(dao, plan, [*_approved(plan), plan["actions"][0]])["results"]
        dry = _apply(dao, plan, _approved(plan), dry_run=True)["results"]

        assert all("ids" not in row for row in [*rows, *dry])


class TestTheFailureSweep:
    @staticmethod
    def _failure(row_id, name, league, sample="A vs B, 2026-12-02 U15", **extra):
        return {
            "id": row_id,
            "kind": "team",
            "raw_name": name,
            "league": league,
            "sample": sample,
            "resolved_at": None,
            **extra,
        }

    def test_it_does_not_run_when_nothing_was_applied(self):
        db = _db(ingest_failures=[self._failure(5, "River FC", "Academy")])
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)
        _apply(dao, plan, _approved(plan))
        db.tables["ingest_failures"][0].update(resolved_at=None, resolution_note=None)
        dao.ingest_failures_dao.open_failures = MagicMock(side_effect=AssertionError("the sweep must not run"))
        alias = plan["actions"][0]
        actions = [
            {**alias, "status": APPROVED},  # already applied
            alias,  # skipped
            {**alias, "status": APPROVED, "team_id": 999},  # refused
        ]

        result = _apply(dao, plan, actions)

        assert [row["outcome"] for row in result["results"]] == ["already_applied", "skipped", "refused"]
        assert result["failures_closed"] == []
        assert db.tables["ingest_failures"][0]["resolved_at"] is None

    def test_it_leaves_rows_for_names_this_request_did_not_apply(self):
        failures = [
            self._failure(5, "River FC", "Academy"),
            # Resolves, and always did: not this plan's to close.
            self._failure(6, "River FC", "Homegrown"),
            # Would be fixed by an action that was not applied in this request.
            self._failure(7, "Lake United", "Academy"),
        ]
        db = _db(ingest_failures=failures)
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        result = _apply(dao, plan, _approved(plan)[:1])

        assert [row["id"] for row in result["failures_closed"]] == [5]
        assert [row["resolved_at"] is None for row in db.tables["ingest_failures"]] == [False, True, True]

    @pytest.mark.parametrize("sample", [None, "", "River FC vs Lake United", "A vs B, 2026-12-02 U99"])
    def test_a_row_whose_sample_names_no_age_group_is_left_open(self, sample):
        db = _db(ingest_failures=[self._failure(5, "River FC", "Academy", sample=sample)])
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)

        result = _apply(dao, plan, _approved(plan)[:1])

        assert _only(result)[0] == "applied"
        assert result["failures_closed"] == []
        assert db.tables["ingest_failures"][0]["resolved_at"] is None


class TestATeamsLeagueMustBeTopLevel:
    def test_a_child_league_is_refused(self):
        db = _db()
        dao = _dao(db)
        plan = dao.plan(TEAMS_INPUT)
        create = {**plan["actions"][1], "status": APPROVED, "league": "Flex"}

        for dry_run in (True, False):
            assert _only(_apply(dao, plan, [create], dry_run=dry_run)) == (
                "refused",
                "Flex is not a top-level league: a team's league is its side, Homegrown",
            )
        assert db.writes == []


class TestADryRunJudgesSharedRowsAsTheRealRunDoes:
    INPUT = [
        {"name": "Nowhere SC", "age_group": "U15", "league": "Academy"},
        {"name": "Nowhere SC B", "age_group": "U15", "league": "Academy"},
    ]

    def _both_ways(self, edit):
        outcomes = []
        for dry_run in (True, False):
            db = _db()
            dao = _dao(db)
            plan = dao.plan(self.INPUT)
            first, second = _approved(plan)
            result = _apply(dao, plan, [first, {**second, **edit}], dry_run=dry_run)
            outcomes.append([(row["outcome"], row.get("steps")) for row in result["results"]])
            if dry_run:
                assert db.writes == []
        return outcomes

    def test_a_shared_new_club_is_created_once(self):
        dry, real = self._both_ways({"new_club_name": "Nowhere SC"})

        assert real == [
            ("applied", ["create club 'Nowhere SC'", "create team 'Nowhere SC' (Academy)"]),
            ("applied", ["create team 'Nowhere SC B' (Academy)"]),
        ]
        assert dry == [("would_apply", steps) for _, steps in real]

    def test_a_shared_new_team_in_the_same_club_is_created_once_and_aliased(self):
        dry, real = self._both_ways({"new_club_name": "Nowhere SC", "team_name": "Nowhere SC"})

        assert real[1] == ("applied", ["alias 'Nowhere SC B' (Academy) → 'Nowhere SC'"])
        assert dry == [("would_apply", steps) for _, steps in real]

    def test_a_shared_new_team_name_in_another_club_is_refused_both_ways(self):
        dry, real = self._both_ways({"team_name": "Nowhere SC"})

        assert [outcome for outcome, _ in real] == ["applied", "refused"]
        assert [outcome for outcome, _ in dry] == ["would_apply", "refused"]

    def test_the_same_alias_twice_is_made_once(self):
        outcomes = []
        for dry_run in (True, False):
            dao = _dao(_db())
            plan = dao.plan(TEAMS_INPUT)
            alias = _approved(plan)[0]
            result = _apply(dao, plan, [alias, {**alias, "id": "a099"}], dry_run=dry_run)
            outcomes.append([row["outcome"] for row in result["results"]])

        assert outcomes == [["would_apply", "already_applied"], ["applied", "already_applied"]]


class TestTheResolversWarning:
    """Ingest warns for every name it cannot place. A plan must not — and must not change that."""

    WARNING = "Tournament team name not resolved"

    def test_ingests_resolver_still_warns_once_per_unresolved_name(self):
        team_dao = _over(TeamDAO, _db())

        with patch("dao.team_dao.logger") as log:
            team, resolution = team_dao.resolve_tournament_team("River FC", U15, "Academy")

        assert team is None
        log.warning.assert_called_once_with(
            self.WARNING,
            team_name="River FC",
            league="Academy",
            age_group_id=U15,
            status="wrong_side",
            reason="wrong side: exists as Homegrown",
        )

    def test_ingests_resolver_says_nothing_about_a_name_it_places(self):
        team_dao = _over(TeamDAO, _db())

        with patch("dao.team_dao.logger") as log:
            team, _ = team_dao.resolve_tournament_team("River FC", U15, "Homegrown")

        assert team["id"] == 11
        log.warning.assert_not_called()

    def test_planning_and_applying_do_not_log_it(self):
        dao = _dao(_db())

        with patch("dao.team_dao.logger") as log:
            plan = dao.plan(TEAMS_INPUT)
            _apply(dao, plan, _approved(plan), dry_run=True)
            _apply(dao, plan, _approved(plan))

        assert plan["report"]["sides"]["Academy"]["missing"]["total"] == 4
        assert [call for call in log.warning.call_args_list if call.args[:1] == (self.WARNING,)] == []

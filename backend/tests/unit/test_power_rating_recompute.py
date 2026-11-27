"""MT Power Rating recompute (SB-1807): the service, the admin trigger, the nightly beat.

The service runs against a fake store, so the orchestration (skip unchanged,
write changed, one age group failing does not stop the rest) is tested without
a database. The endpoint uses the real app and the real role check.
"""

from dataclasses import replace
from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from dao.power_rating_dao import Gathered, LeagueScope, fingerprint
from mt_tools.power_rating import RatedMatch
from services.power_rating_service import InvalidRecomputeError, RecomputeSummary, recompute

pytestmark = [pytest.mark.unit, pytest.mark.backend]

NOW = datetime(2026, 11, 28, 10, tzinfo=UTC)
SCOPE = LeagueScope(league_id=1, name="Homegrown", league_ids=(1, 290), match_type_ids=(1, 5))
AGES = {"U15": 3, "U16": 4, "U17": 5, "U19": 7}


def season(n_matches: int = 3) -> Gathered:
    return Gathered(
        (
            *(
                RatedMatch(i, date(2026, 9, i), 10 + i % 2, 20, 1, 0, conference="Northeast")
                for i in range(1, n_matches + 1)
            ),
            RatedMatch(99, date(2026, 9, 20), 10, 20, 0, 0, forfeit=True),
        ),
        other_age_group=1,
        conference_ids={"Northeast": 11},
    )


class FakeStore:
    def __init__(self, gathered=None, latest=None, fail_age=None, season_id=184):
        self.gathered = gathered or {}
        self.latest = latest or {}
        self.fail_age = fail_age
        self.season_id = season_id
        self.writes: list[tuple[dict, list, list]] = []

    def current_season_id(self):
        return self.season_id

    def resolve_league(self, name):
        return SCOPE if name.casefold() == "homegrown" else None

    def age_group_ids(self, names):
        return {n: AGES[n] for n in names if n in AGES}

    def gather(self, season_id, age_group_id, scope):
        if age_group_id == self.fail_age:
            raise RuntimeError("read failed")
        return self.gathered.get(age_group_id, Gathered(()))

    def latest_run(self, season_id, age_group_id, league_id):
        return self.latest.get(age_group_id)

    def write_run(self, run, ratings, deltas):
        self.writes.append((run, ratings, deltas))
        return 1000 + len(self.writes)


class TestRecompute:
    def test_writes_each_age_group_and_summarises(self):
        store = FakeStore(gathered={5: season()})
        summary = recompute(store, now=NOW)
        assert [s.age_group for s in summary.age_groups] == ["U15", "U16", "U17", "U19"]
        assert all(s.status == "written" for s in summary.age_groups)
        u17 = summary.age_groups[2]
        assert u17.run_id == 1003
        assert u17.matches_counted == 3
        assert u17.matches_excluded == {"forfeit": 1, "out_of_pool_opponent": 0, "other_age_group": 1, "no_score": 0}
        assert u17.teams == 3
        assert u17.national is False and u17.reason
        assert (summary.season_id, summary.league, summary.computed_at) == (184, "Homegrown", NOW)

    def test_the_written_run_carries_scope_fingerprint_and_rows(self):
        store = FakeStore(gathered={5: season()})
        recompute(store, age_groups=["U17"], now=NOW)
        [(run, ratings, deltas)] = store.writes
        assert (run["season_id"], run["age_group_id"], run["league_id"]) == (184, 5, 1)
        assert run["input_fingerprint"] == fingerprint(season())
        assert run["computed_at"] == NOW.isoformat()
        assert {r["team_id"] for r in ratings} == {10, 11, 20}
        assert len(deltas) == 6
        assert {r["conference_division_id"] for r in ratings} == {11}

    def test_unchanged_input_writes_nothing(self):
        latest = {5: {"id": 77, "input_fingerprint": fingerprint(season())}}
        store = FakeStore(gathered={5: season()}, latest=latest)
        [u17] = recompute(store, age_groups=["U17"], now=NOW).age_groups
        assert (u17.status, u17.run_id) == ("unchanged", 77)
        assert store.writes == []

    def test_a_score_correction_is_written(self):
        latest = {5: {"id": 77, "input_fingerprint": fingerprint(season())}}
        original = season()
        corrected = replace(original, matches=(replace(original.matches[0], home_score=3), *original.matches[1:]))
        store = FakeStore(gathered={5: corrected}, latest=latest)
        [u17] = recompute(store, age_groups=["U17"], now=NOW).age_groups
        assert u17.status == "written"
        assert len(store.writes) == 1

    def test_an_age_group_with_nothing_played_is_written_empty_not_an_error(self):
        [u15] = recompute(FakeStore(), age_groups=["U15"], now=NOW).age_groups
        assert (u15.status, u15.matches_counted, u15.teams) == ("written", 0, 0)
        assert u15.reason  # "No team has enough rated matches yet."

    def test_one_age_group_failing_does_not_stop_the_rest(self):
        store = FakeStore(gathered={5: season()}, fail_age=4)
        summary = recompute(store, now=NOW)
        statuses = {s.age_group: s.status for s in summary.age_groups}
        assert statuses == {"U15": "written", "U16": "failed", "U17": "written", "U19": "written"}
        failed = summary.age_groups[1]
        assert failed.run_id is None and failed.reason == "Could not recompute."
        assert "read failed" not in failed.model_dump_json()

    def test_explicit_season_is_used(self):
        store = FakeStore(season_id=None)
        assert recompute(store, season_id=2, age_groups=["U17"], now=NOW).season_id == 2
        assert store.writes[0][0]["season_id"] == 2

    @pytest.mark.parametrize(
        ("kwargs", "store_kwargs", "message"),
        [
            ({}, {"season_id": None}, "No current season"),
            ({"league": "Nope"}, {}, "No top-level league"),
            ({"age_groups": ["U17", "U99"]}, {}, "U99"),
        ],
    )
    def test_invalid_input_raises_before_any_write(self, kwargs, store_kwargs, message):
        store = FakeStore(**store_kwargs)
        with pytest.raises(InvalidRecomputeError, match=message):
            recompute(store, now=NOW, **kwargs)
        assert store.writes == []


# --- POST /api/admin/power-rating/recompute ---------------------------------------------

ADMIN = {"user_id": "admin-1", "username": "admin", "role": "admin"}
TEAM_MANAGER = {"user_id": "tm-1", "username": "tm", "role": "team_manager", "team_id": 10}
SUMMARY = RecomputeSummary(season_id=184, league="Homegrown", computed_at=NOW, age_groups=[])


@pytest.fixture
def as_caller():
    import app as app_module
    from auth import get_current_user_required

    caller: dict = {}
    app_module.app.dependency_overrides[get_current_user_required] = lambda: caller["user"]

    def use(user):
        caller["user"] = user
        return TestClient(app_module.app)

    yield use
    app_module.app.dependency_overrides.clear()


class TestAdminTrigger:
    URL = "/api/admin/power-rating/recompute"

    def test_team_manager_is_403_and_nothing_runs(self, as_caller):
        with patch("services.power_rating_service.recompute") as run:
            r = as_caller(TEAM_MANAGER).post(self.URL)
        assert r.status_code == 403
        run.assert_not_called()

    def test_admin_gets_the_summary(self, as_caller):
        import app as app_module

        with patch("services.power_rating_service.recompute", return_value=SUMMARY) as run:
            r = as_caller(ADMIN).post(self.URL)
        assert r.status_code == 200
        assert r.json() == SUMMARY.model_dump(mode="json")
        store, season_id, age_groups, league = run.call_args.args
        assert store is app_module.power_rating_dao
        assert (season_id, age_groups, league) == (None, ("U15", "U16", "U17", "U19"), "Homegrown")

    def test_age_groups_and_season_pass_through(self, as_caller):
        with patch("services.power_rating_service.recompute", return_value=SUMMARY) as run:
            as_caller(ADMIN).post(self.URL, params={"season_id": 184, "age_group": ["U17", "U19"]})
        assert run.call_args.args[1:3] == (184, ("U17", "U19"))

    def test_invalid_input_is_400(self, as_caller):
        with patch(
            "services.power_rating_service.recompute", side_effect=InvalidRecomputeError("Unknown age group(s): U99.")
        ):
            r = as_caller(ADMIN).post(self.URL, params={"age_group": "U99"})
        assert r.status_code == 400
        assert "U99" in r.json()["detail"]

    def test_a_failure_is_503_without_details(self, as_caller):
        with patch("services.power_rating_service.recompute", side_effect=RuntimeError("SUPABASE_URL unreachable")):
            r = as_caller(ADMIN).post(self.URL)
        assert r.status_code == 503
        assert "SUPABASE" not in r.text


# --- the nightly beat ---------------------------------------------------------------


class TestBeat:
    def test_schedule_runs_the_recompute_at_10_utc(self):
        from celery_app import POWER_RATING_QUEUE, app

        entry = app.conf.beat_schedule["power-rating-nightly"]
        assert entry["task"] == "power_rating.recompute_all"
        schedule = entry["schedule"]
        assert schedule.hour == {10} and schedule.minute == {0}
        assert len(schedule.day_of_week) == 7
        assert app.conf.timezone == "UTC" and app.conf.enable_utc
        assert entry["options"]["queue"] == POWER_RATING_QUEUE

    def test_the_task_is_registered_and_routed_to_its_queue(self):
        import celery_tasks  # noqa: F401  registers the tasks, as the worker's autodiscovery does
        from celery_app import POWER_RATING_QUEUE, app

        assert "power_rating.recompute_all" in app.tasks
        assert POWER_RATING_QUEUE in {q.name for q in app.conf.task_queues}
        assert app.amqp.router.route({}, "power_rating.recompute_all")["queue"].name == POWER_RATING_QUEUE

    def test_the_task_runs_recompute_and_returns_json(self):
        from celery_tasks import power_rating_tasks

        dao = MagicMock()
        with (
            patch.object(power_rating_tasks.PowerRatingTask, "dao", dao),
            patch.object(power_rating_tasks, "recompute", return_value=SUMMARY) as run,
        ):
            out = power_rating_tasks.recompute_all.run()
        run.assert_called_once_with(dao)
        assert out == SUMMARY.model_dump(mode="json")

    def test_the_prod_worker_consumes_the_queue_and_runs_one_beat(self):
        from pathlib import Path

        import yaml

        manifest = Path(__file__).resolve().parents[3] / "k3s" / "worker" / "deployment-prod.yaml"
        spec = yaml.safe_load(manifest.read_text())["spec"]
        args = spec["template"]["spec"]["containers"][0]["args"]
        queues = next(a for a in args if a.startswith("--queues=")).split("=", 1)[1].split(",")
        assert "power_rating" in queues and "matches.prod" in queues
        assert "--beat" in args
        assert spec["replicas"] == 1 and spec["strategy"]["type"] == "Recreate"

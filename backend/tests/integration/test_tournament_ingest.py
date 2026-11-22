"""Tournament matches through the Celery ingest path (SB-1747).

Runs ``process_match_data`` — the task body, without Celery's retry wrapper —
against real DAOs and a real local database, so the things a mock cannot show
are exercised for real: the insert lands on the tournament with a null
division, a rescrape finds the row by its source match id, and an unchanged
rescrape is recognised as unchanged from what the DAO actually reads back.

**The default fixture is scraped teams with no user data**: no roster, no
events. That is every team at a tournament until a manager claims one. The one
populated case — a goal somebody logged — is the special case, and is there to
prove a rescrape leaves it alone.

Requires local Supabase. Skips cleanly if unreachable.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from celery_tasks.exceptions import UnresolvedNameError
from celery_tasks.match_tasks import process_match_data
from dao.base_dao import clear_cache
from dao.club_dao import ClubDAO
from dao.ingest_failures_dao import IngestFailuresDAO
from dao.league_dao import LeagueDAO
from dao.match_dao import MatchDAO, SupabaseConnection
from dao.match_type_dao import MatchTypeDAO
from dao.season_dao import SeasonDAO
from dao.team_dao import TeamDAO

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]

CACHE_PATTERNS = ("mt:dao:matches:*", "mt:dao:teams:*", "mt:dao:tournaments:*")

TASK_DAO_ATTRS = (
    "_connection",
    "_dao",
    "_team_dao",
    "_season_dao",
    "_league_dao",
    "_match_type_dao",
    "_ingest_failures_dao",
    "_club_dao",
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
        pytest.skip("SUPABASE_SERVICE_KEY not set — cannot run tournament ingest test")
    return create_client(url, key)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


def _first(admin, table: str, columns: str = "id, name") -> dict:
    rows = admin.table(table).select(columns).order("id").limit(1).execute().data
    if not rows:
        pytest.skip(f"No reference rows in {table}; seed the local DB first")
    return rows[0]


def _quietly(step) -> None:
    """Run one cleanup step; a failure must not stop the steps after it."""
    try:
        step()
    except Exception:  # pragma: no cover - cleanup is best effort
        pass


@pytest.fixture
def fest():
    """A tournament and three scraped teams — no roster, no events, no matches."""
    admin = _admin_client()
    try:
        admin.table("tournaments").select("id").limit(1).execute()
    except Exception:  # pragma: no cover - infra guard
        pytest.skip("Local Supabase not reachable")

    season = _first(admin, "seasons")
    age_group = _first(admin, "age_groups")
    tournament_type = admin.table("match_types").select("id, name").ilike("name", "Tournament").execute().data
    if not tournament_type:
        pytest.skip("No 'Tournament' match type; seed the local DB first")

    # The task builds its own connection from the environment. Build it here
    # instead, so it can be refused before anything is written through it.
    connection = SupabaseConnection()
    if not _is_local(connection.url):
        pytest.skip(f"Refusing to run ingest against non-local Supabase: {connection.url}")

    created: dict[str, list[int]] = {"tournaments": [], "teams": []}
    # ingest_failures rows are found by a source only this test uses.
    failure_source = _unique("zz-fest-source")

    def _mk(table: str, payload: dict) -> dict:
        row = admin.table(table).insert(payload).execute().data[0]
        created[table].append(row["id"])
        return row

    task = process_match_data
    saved = {attr: getattr(task, attr) for attr in TASK_DAO_ATTRS}
    saved_sets = (task._resolved_names, task._ensured_mappings, task._known_tournaments)

    try:
        match_date = (datetime.now(UTC).date() + timedelta(days=30)).isoformat()
        tournament = _mk(
            "tournaments",
            {"name": _unique("ZZ Fest"), "start_date": match_date, "season_id": season["id"], "is_test": True},
        )
        home = _mk("teams", {"name": _unique("ZZ Fest Home")})
        away = _mk("teams", {"name": _unique("ZZ Fest Away")})
        third = _mk("teams", {"name": _unique("ZZ Fest Third")})

        for pattern in CACHE_PATTERNS:
            clear_cache(pattern)

        task._connection = connection
        task._dao = MatchDAO(connection)
        task._team_dao = TeamDAO(connection)
        task._season_dao = SeasonDAO(connection)
        task._league_dao = LeagueDAO(connection)
        task._match_type_dao = MatchTypeDAO(connection)
        task._ingest_failures_dao = IngestFailuresDAO(connection)
        task._club_dao = ClubDAO(connection)
        task._resolved_names = set()
        task._ensured_mappings = set()
        task._known_tournaments = {}

        yield {
            "admin": admin,
            "tournament_id": tournament["id"],
            "tournament_type_id": tournament_type[0]["id"],
            "season": season,
            "age_group": age_group,
            "home": home,
            "away": away,
            "third": third,
            "match_date": match_date,
            "failure_source": failure_source,
        }
    finally:
        for attr, value in saved.items():
            setattr(task, attr, value)
        task._resolved_names, task._ensured_mappings, task._known_tournaments = saved_sets

        # Each step on its own: a failed delete must not strand the rest.
        # Matches first (the task created them, so they are found by team, not
        # by a recorded id); their events cascade.
        team_ids = created["teams"]
        if team_ids:
            _quietly(lambda: admin.table("matches").delete().in_("home_team_id", team_ids).execute())
            _quietly(lambda: admin.table("matches").delete().in_("away_team_id", team_ids).execute())
        for tournament_id in created["tournaments"]:
            _quietly(lambda tid=tournament_id: admin.table("matches").delete().eq("tournament_id", tid).execute())
            _quietly(lambda tid=tournament_id: admin.table("tournaments").delete().eq("id", tid).execute())
        for team_id in team_ids:
            _quietly(lambda tid=team_id: admin.table("team_mappings").delete().eq("team_id", tid).execute())
            _quietly(lambda tid=team_id: admin.table("teams").delete().eq("id", tid).execute())
        _quietly(lambda: admin.table("ingest_failures").delete().eq("source", failure_source).execute())
        for pattern in CACHE_PATTERNS:
            _quietly(lambda p=pattern: clear_cache(p))


def _message(fest, **overrides) -> dict:
    """A scraped tournament fixture as it arrives: scheduled, no score."""
    return {
        "home_team": fest["home"]["name"],
        "away_team": fest["away"]["name"],
        "match_date": fest["match_date"],
        "season": fest["season"]["name"],
        "age_group": fest["age_group"]["name"],
        "match_type": "Tournament",
        "match_status": "scheduled",
        "external_match_id": _unique("zz-fest"),
        "source": "match-scraper",
        "tournament_id": fest["tournament_id"],
        "competition": "HD Group Play",
        "tournament_group": "A",
        "tournament_round": "group_stage",
        "tournament_round_order": 1,
        **overrides,
    }


def _ingest(message: dict) -> dict:
    """Run the task body with the outbound alerts stubbed — nothing leaves the test."""
    with (
        patch("celery_tasks.match_tasks.alert_if_new_final_score"),
        patch("celery_tasks.match_tasks.alert_unresolved_name"),
    ):
        return process_match_data.__wrapped__(message)


def _rows(fest) -> list[dict]:
    return (
        fest["admin"].table("matches").select("*").eq("tournament_id", fest["tournament_id"]).order("id").execute().data
    )


class TestCreate:
    def test_a_scraped_match_lands_on_the_tournament(self, fest):
        message = _message(fest)

        result = _ingest(message)

        assert result["status"] == "created"
        rows = _rows(fest)
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == result["db_id"]
        assert row["tournament_id"] == fest["tournament_id"]
        assert row["division_id"] is None
        assert row["match_type_id"] == fest["tournament_type_id"]
        assert row["tournament_group"] == "HD · A"
        assert row["tournament_round"] == "group_stage"
        assert row["tournament_round_order"] == 1
        assert row["match_id"] == message["external_match_id"]
        assert row["source"] == "match-scraper"
        assert row["age_group_id"] == fest["age_group"]["id"]

    def test_an_unplayed_match_has_no_score_not_a_zero(self, fest):
        _ingest(_message(fest))

        row = _rows(fest)[0]
        assert row["home_score"] is None and row["away_score"] is None
        assert row["home_penalty_score"] is None and row["away_penalty_score"] is None

    def test_the_same_group_label_in_two_divisions_stays_two_groups(self, fest):
        # Same teams, same day, both "Group A" — distinct fixtures, and the
        # second must not be mistaken for the first by the teams-and-date
        # fallback.
        _ingest(_message(fest, competition="HD Group Play"))
        _ingest(_message(fest, competition="AD Group Play"))

        assert sorted(r["tournament_group"] for r in _rows(fest)) == ["AD · A", "HD · A"]


class TestRescrape:
    def test_a_rescrape_fills_in_the_score_on_the_same_row(self, fest):
        message = _message(fest, tournament_round="placement_final", tournament_group="Playoffs")
        created = _ingest(message)

        result = _ingest(
            {
                **message,
                "home_score": 1,
                "away_score": 1,
                "home_penalty_score": 4,
                "away_penalty_score": 3,
                "match_status": "completed",
            }
        )

        assert result["status"] == "updated"
        assert result["db_id"] == created["db_id"]
        rows = _rows(fest)
        assert len(rows) == 1
        row = rows[0]
        assert (row["home_score"], row["away_score"]) == (1, 1)
        assert (row["home_penalty_score"], row["away_penalty_score"]) == (4, 3)
        assert row["match_status"] == "completed"
        assert row["tournament_group"] == "HD · Group Play"
        assert row["source"] == "match-scraper"

    def test_an_identical_rescrape_is_skipped(self, fest):
        message = _message(fest)
        _ingest(message)
        before = _rows(fest)[0]

        result = _ingest(dict(message))

        assert result["status"] == "skipped"
        rows = _rows(fest)
        assert len(rows) == 1
        assert rows[0]["updated_at"] == before["updated_at"]

    def test_a_rescrape_that_omits_the_group_does_not_unfile_the_match(self, fest):
        message = _message(fest)
        _ingest(message)

        result = _ingest({**message, "competition": None, "tournament_group": None, "tournament_round": None})

        assert result["status"] == "skipped"
        row = _rows(fest)[0]
        assert row["tournament_group"] == "HD · A"
        assert row["tournament_round"] == "group_stage"

    @pytest.mark.parametrize(
        "omitted",
        [
            {"tournament_group": None},
            {"tournament_round": None},
            {"competition": None},
        ],
        ids=["no-group", "no-round", "no-competition"],
    )
    def test_a_partial_rescrape_leaves_the_stored_group_intact(self, fest, omitted):
        # Composed from what is left these would be "HD", "HD · Group Play"
        # and "A" — and bracket follows are keyed on "HD · A".
        message = _message(fest)
        _ingest(message)

        result = _ingest({**message, **omitted, "home_score": 3, "away_score": 1, "match_status": "completed"})

        assert result["status"] == "updated"
        rows = _rows(fest)
        assert len(rows) == 1
        row = rows[0]
        assert row["tournament_group"] == "HD · A"
        assert row["tournament_round"] == "group_stage"
        assert row["tournament_round_order"] == 1
        assert (row["home_score"], row["away_score"]) == (3, 1)


class TestUnknownTournament:
    def test_it_writes_one_failure_row_and_no_match(self, fest):
        admin = fest["admin"]
        # An id that is certain not to exist: one that was just deleted.
        gone = (
            admin.table("tournaments")
            .insert(
                {
                    "name": _unique("ZZ Fest Gone"),
                    "start_date": fest["match_date"],
                    "season_id": fest["season"]["id"],
                    "is_test": True,
                }
            )
            .execute()
            .data[0]["id"]
        )
        admin.table("tournaments").delete().eq("id", gone).execute()
        first = _message(fest, tournament_id=gone, source=fest["failure_source"])
        second = _message(fest, tournament_id=gone, source=fest["failure_source"], away_team=fest["third"]["name"])

        for message in (first, second):
            with pytest.raises(UnresolvedNameError):
                _ingest(message)

        failures = admin.table("ingest_failures").select("*").eq("source", fest["failure_source"]).execute().data
        assert len(failures) == 1
        assert failures[0]["kind"] == "invalid"
        assert failures[0]["raw_name"] == f"unknown tournament_id {gone}"
        assert failures[0]["match_count"] == 2
        team_ids = [fest["home"]["id"], fest["away"]["id"], fest["third"]["id"]]
        assert admin.table("matches").select("id").in_("home_team_id", team_ids).execute().data == []
        assert admin.table("matches").select("id").in_("away_team_id", team_ids).execute().data == []
        external_ids = [first["external_match_id"], second["external_match_id"]]
        assert admin.table("matches").select("id").in_("match_id", external_ids).execute().data == []


class TestManualMatch:
    def test_a_manual_league_match_is_not_adopted_by_a_tournament_message(self, fest):
        admin = fest["admin"]
        league_type = admin.table("match_types").select("id").ilike("name", "League").execute().data
        if not league_type:
            pytest.skip("No 'League' match type; seed the local DB first")
        division = _first(admin, "divisions")
        league_match = (
            admin.table("matches")
            .insert(
                {
                    "match_date": fest["match_date"],
                    "home_team_id": fest["home"]["id"],
                    "away_team_id": fest["away"]["id"],
                    "season_id": fest["season"]["id"],
                    "age_group_id": fest["age_group"]["id"],
                    "match_type_id": league_type[0]["id"],
                    "division_id": division["id"],
                    "match_status": "scheduled",
                    "source": "manual",
                }
            )
            .execute()
            .data[0]
        )
        message = _message(fest, home_score=2, away_score=1, match_status="completed")

        result = _ingest(message)

        assert result["status"] == "created"
        assert result["db_id"] != league_match["id"]
        untouched = admin.table("matches").select("*").eq("id", league_match["id"]).execute().data[0]
        assert untouched == league_match
        rows = _rows(fest)
        assert len(rows) == 1
        assert rows[0]["id"] == result["db_id"]
        assert rows[0]["match_id"] == message["external_match_id"]
        assert rows[0]["division_id"] is None
        assert (rows[0]["home_score"], rows[0]["away_score"]) == (2, 1)

    def test_a_hand_entered_match_is_adopted_not_duplicated(self, fest):
        admin = fest["admin"]
        manual = (
            admin.table("matches")
            .insert(
                {
                    "match_date": fest["match_date"],
                    "home_team_id": fest["home"]["id"],
                    "away_team_id": fest["away"]["id"],
                    "season_id": fest["season"]["id"],
                    "age_group_id": fest["age_group"]["id"],
                    "match_type_id": fest["tournament_type_id"],
                    "match_status": "scheduled",
                    "source": "manual",
                    "tournament_id": fest["tournament_id"],
                    "tournament_round": "group_stage",
                }
            )
            .execute()
            .data[0]
        )
        message = _message(fest)

        result = _ingest(message)

        assert result["db_id"] == manual["id"]
        rows = _rows(fest)
        assert len(rows) == 1
        row = rows[0]
        assert row["match_id"] == message["external_match_id"]
        assert row["source"] == "match-scraper"
        # Adoption hands the filing to the feed, so the group arrives too.
        assert row["tournament_group"] == "HD · A"


class TestUserDataSurvives:
    """The populated special case: somebody logged a goal."""

    def test_a_logged_goal_survives_a_rescrape(self, fest):
        admin = fest["admin"]
        message = _message(fest)
        created = _ingest(message)
        goal = (
            admin.table("match_events")
            .insert(
                {
                    "match_id": created["db_id"],
                    "event_type": "goal",
                    "team_id": fest["home"]["id"],
                    "player_name": "ZZ Fest Scorer",
                    "message": "Goal — ZZ Fest Scorer",
                    "match_minute": 12,
                }
            )
            .execute()
            .data[0]
        )

        result = _ingest({**message, "home_score": 2, "away_score": 0, "match_status": "completed"})

        assert result["status"] == "updated"
        events = admin.table("match_events").select("*").eq("match_id", created["db_id"]).execute().data
        assert [e["id"] for e in events] == [goal["id"]]
        assert events[0]["player_name"] == "ZZ Fest Scorer"
        assert events[0]["team_id"] == fest["home"]["id"]
        assert events[0]["is_deleted"] is False
        # The scraped score stands as the result; the logged goal stands as
        # who did what. One goal logged against a 2-0 is a disagreement the
        # ingest leaves in place rather than resolving.
        row = _rows(fest)[0]
        assert (row["home_score"], row["away_score"]) == (2, 0)

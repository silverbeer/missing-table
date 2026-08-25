"""Unit tests for Celery match task helper methods.

Tests _build_scheduled_kickoff(), _check_needs_update(), and
_update_match_scores() on the DatabaseTask class without requiring
a live database or Celery broker.
"""

from unittest.mock import MagicMock, patch

import pytest

from celery_tasks.exceptions import UnresolvedNameError
from celery_tasks.match_tasks import DatabaseTask, process_match_data


@pytest.fixture
def task():
    """Create a DatabaseTask instance with a mocked DAO."""
    t = DatabaseTask()
    t._dao = MagicMock()
    return t


# ── _build_scheduled_kickoff ─────────────────────────────────────────

# March 1, 2026 is EST (UTC-5).  14:00 EST = 19:00 UTC.
# April 11, 2026 is EDT (UTC-4). 10:45 EDT = 14:45 UTC.


class TestBuildScheduledKickoff:
    def test_converts_est_to_utc(self, task):
        """March 1 is EST (UTC-5): 14:00 EST → 19:00 UTC."""
        data = {"match_date": "2026-03-01", "match_time": "14:00"}
        assert task._build_scheduled_kickoff(data) == "2026-03-01T19:00:00+00:00"

    def test_converts_edt_to_utc(self, task):
        """April 11 is EDT (UTC-4): 10:45 EDT → 14:45 UTC."""
        data = {"match_date": "2026-04-11", "match_time": "10:45"}
        assert task._build_scheduled_kickoff(data) == "2026-04-11T14:45:00+00:00"

    def test_returns_none_when_no_match_time(self, task):
        data = {"match_date": "2026-03-01", "match_time": None}
        assert task._build_scheduled_kickoff(data) is None

    def test_returns_none_when_no_match_date(self, task):
        data = {"match_time": "14:00"}
        assert task._build_scheduled_kickoff(data) is None

    def test_returns_none_when_empty(self, task):
        assert task._build_scheduled_kickoff({}) is None


# ── _check_needs_update ──────────────────────────────────────────────


class TestCheckNeedsUpdate:
    # Helpers: existing match with matching team IDs (no swap)
    HOME_ID = 10
    AWAY_ID = 20

    def _existing(self, **kwargs):
        base = {
            "match_status": "scheduled",
            "home_score": None,
            "away_score": None,
            "scheduled_kickoff": None,
            "home_team_id": self.HOME_ID,
            "away_team_id": self.AWAY_ID,
        }
        base.update(kwargs)
        return base

    def test_no_changes_returns_false(self, task):
        existing = self._existing()
        new_data = {"match_status": "scheduled", "home_score": None, "away_score": None}
        assert task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID) is False

    def test_home_away_swap_returns_true(self, task):
        """Scraped data has home/away reversed → needs update."""
        existing = self._existing()
        new_data = {"match_status": "completed", "home_score": 7, "away_score": 0}
        # Teams are swapped: scraper says AWAY_ID is home, HOME_ID is away
        assert task._check_needs_update(existing, new_data, self.AWAY_ID, self.HOME_ID) is True

    def test_home_team_id_unchanged_returns_false(self, task):
        """Same team IDs, no other changes → no update needed."""
        existing = self._existing(match_status="completed", home_score=7, away_score=0)
        new_data = {"match_status": "completed", "home_score": 7, "away_score": 0}
        assert task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID) is False

    def test_status_change_returns_true(self, task):
        existing = self._existing()
        new_data = {"match_status": "completed", "home_score": 2, "away_score": 1}
        assert task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID) is True

    def test_score_change_returns_true(self, task):
        existing = self._existing(match_status="completed", home_score=1, away_score=0)
        new_data = {"match_status": "completed", "home_score": 2, "away_score": 0}
        assert task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID) is True

    def test_kickoff_backfill_returns_true(self, task):
        """New data has match_time, existing has no scheduled_kickoff → needs update."""
        existing = self._existing()
        new_data = {"match_status": "scheduled", "match_date": "2026-03-01", "match_time": "14:00"}
        assert task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID) is True

    def test_kickoff_changed_returns_true(self, task):
        """Kickoff time changed (rescheduled) → needs update."""
        existing = self._existing(scheduled_kickoff="2026-03-01T19:00:00+00:00")
        new_data = {"match_status": "scheduled", "match_date": "2026-03-01", "match_time": "16:00"}
        # 16:00 EST = 21:00 UTC ≠ 19:00 UTC → True
        assert task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID) is True

    def test_kickoff_unchanged_returns_false(self, task):
        """Same kickoff time, same everything → no update needed."""
        existing = self._existing(scheduled_kickoff="2026-03-01T19:00:00+00:00")
        new_data = {"match_status": "scheduled", "match_date": "2026-03-01", "match_time": "14:00"}
        # 14:00 EST = 19:00 UTC == 19:00 UTC → False
        assert task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID) is False

    def test_no_match_time_in_new_data_returns_false(self, task):
        """New data has no match_time → don't clear existing kickoff."""
        existing = self._existing(scheduled_kickoff="2026-03-01T19:00:00+00:00")
        new_data = {"match_status": "scheduled", "match_date": "2026-03-01", "match_time": None}
        assert task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID) is False

    def test_rescheduled_match_date_returns_true(self, task):
        """Match rescheduled to a different date → needs update."""
        existing = self._existing(match_date="2026-03-01")
        new_data = {"match_status": "scheduled", "match_date": "2026-06-08"}
        assert task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID) is True

    def test_same_match_date_returns_false(self, task):
        """Same date, same everything → no update needed."""
        existing = self._existing(match_date="2026-03-01")
        new_data = {"match_status": "scheduled", "match_date": "2026-03-01"}
        assert task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID) is False


# ── _update_match_scores ─────────────────────────────────────────────


class TestUpdateMatchScores:
    def test_corrects_home_away_swap(self, task):
        """Home/away team IDs swapped → both corrected in update payload."""
        existing = {"id": 42, "home_team_id": 10, "away_team_id": 20, "scheduled_kickoff": None}
        new_data = {"home_score": 7, "away_score": 0, "match_status": "completed"}

        task._update_match_scores(existing, new_data, home_team_id=20, away_team_id=10)

        update_payload = task._dao.client.table("matches").update.call_args[0][0]
        assert update_payload["home_team_id"] == 20
        assert update_payload["away_team_id"] == 10

    def test_no_team_change_skips_team_fields(self, task):
        """Same team IDs → home_team_id/away_team_id not in update payload."""
        existing = {"id": 42, "home_team_id": 10, "away_team_id": 20, "scheduled_kickoff": None}
        new_data = {"home_score": 2, "away_score": 1, "match_status": "completed"}

        task._update_match_scores(existing, new_data, home_team_id=10, away_team_id=20)

        update_payload = task._dao.client.table("matches").update.call_args[0][0]
        assert "home_team_id" not in update_payload
        assert "away_team_id" not in update_payload

    def test_updates_scheduled_kickoff(self, task):
        """scheduled_kickoff should be in the update payload when match_time provided."""
        existing = {"id": 42, "scheduled_kickoff": None}
        new_data = {"match_date": "2026-03-01", "match_time": "14:00"}

        task._update_match_scores(existing, new_data)

        update_call = task._dao.client.table("matches").update
        update_call.assert_called_once()
        update_payload = update_call.call_args[0][0]
        assert update_payload["scheduled_kickoff"] == "2026-03-01T19:00:00+00:00"

    def test_updates_changed_kickoff(self, task):
        """Rescheduled kickoff → should be in the update payload."""
        existing = {"id": 42, "scheduled_kickoff": "2026-03-01T19:00:00+00:00"}
        new_data = {"match_date": "2026-03-01", "match_time": "16:00"}

        task._update_match_scores(existing, new_data)

        update_payload = task._dao.client.table("matches").update.call_args[0][0]
        assert update_payload["scheduled_kickoff"] == "2026-03-01T21:00:00+00:00"

    def test_skips_unchanged_kickoff(self, task):
        """Same kickoff → no update payload (no-op)."""
        existing = {"id": 42, "scheduled_kickoff": "2026-03-01T19:00:00+00:00"}
        new_data = {"match_date": "2026-03-01", "match_time": "14:00"}

        result = task._update_match_scores(existing, new_data)
        assert result is False

    def test_updates_rescheduled_match_date(self, task):
        """Rescheduled match → match_date should be in the update payload."""
        existing = {"id": 42, "match_date": "2026-03-01", "scheduled_kickoff": None}
        new_data = {"match_date": "2026-06-08", "match_status": "scheduled"}

        task._update_match_scores(existing, new_data)

        update_payload = task._dao.client.table("matches").update.call_args[0][0]
        assert update_payload["match_date"] == "2026-06-08"
        assert update_payload["match_status"] == "scheduled"

    def test_includes_scores_and_kickoff(self, task):
        """Score update + kickoff backfill in one call."""
        existing = {"id": 42, "scheduled_kickoff": None, "home_score": None, "away_score": None}
        new_data = {
            "home_score": 2,
            "away_score": 1,
            "match_status": "completed",
            "match_date": "2026-03-01",
            "match_time": "14:00",
        }

        task._update_match_scores(existing, new_data)

        update_payload = task._dao.client.table("matches").update.call_args[0][0]
        assert update_payload["home_score"] == 2
        assert update_payload["away_score"] == 1
        assert update_payload["match_status"] == "completed"
        assert update_payload["scheduled_kickoff"] == "2026-03-01T19:00:00+00:00"


# ── process_match_data: name resolution (SB-830) ─────────────────────

IFA = {"id": 19, "name": "IFA"}
OPPONENT = {"id": 20, "name": "The Island FC West"}
HOMEGROWN = {"id": 1, "name": "Homegrown"}
NORTHEAST = {"id": 1, "name": "Northeast", "league_id": 1}

MATCH = {
    "home_team": "Intercontinental Football Academy of New England",
    "away_team": "The Island FC West",
    "match_date": "2026-09-05",
    "season": "2026-2027",
    "age_group": "U15",
    "match_type": "League",
    "league": "Homegrown",
    "division": "Northeast",
    "external_match_id": "kitman-1",
    "match_status": "scheduled",
}


@pytest.fixture
def ingest():
    """process_match_data with every DAO stubbed, wired for the happy path.

    The task is a bound Celery task; its DAO properties are cached on the
    singleton, so they are set directly rather than mocked at import time.
    """
    task = process_match_data
    task._dao = MagicMock()
    task._team_dao = MagicMock()
    task._season_dao = MagicMock()
    task._league_dao = MagicMock()
    task._ingest_failures_dao = MagicMock()
    task._ingest_failures_dao.record.return_value = {"id": 1, "match_count": 1, "should_alert": True}
    task._resolved_names = set()

    task._team_dao.resolve_team_by_name.side_effect = lambda name, league_id=None: {
        MATCH["home_team"]: IFA,
        MATCH["away_team"]: OPPONENT,
    }.get(name)
    task._league_dao.get_league_by_name.return_value = HOMEGROWN
    task._league_dao.get_division_by_name.return_value = NORTHEAST
    task._season_dao.get_current_season.return_value = {"id": 5}
    task._season_dao.get_age_group_by_name.return_value = {"id": 3}
    task._dao.get_match_by_external_id.return_value = None
    task._dao.get_match_by_teams_and_date.return_value = None
    task._dao.create_match.return_value = 4242

    yield task

    task._dao = None
    task._team_dao = None
    task._season_dao = None
    task._league_dao = None
    task._ingest_failures_dao = None
    task._resolved_names = set()


def _run(task, **overrides):
    """Call the task body directly, bypassing Celery's autoretry wrapper.

    `__wrapped__` is the undecorated function already bound to the task
    singleton, so `task` is passed only to keep call sites readable.
    """
    assert task is process_match_data
    data = {**MATCH, **overrides}
    with (
        patch("celery_tasks.match_tasks.validate_match_data", return_value={"valid": True, "errors": []}),
        patch("celery_tasks.match_tasks.alert_unresolved_name") as alert,
    ):
        _run.alert = alert
        return process_match_data.__wrapped__(data)


class TestIngestResolvesNamesThroughAliases:
    def test_teams_resolve_via_the_alias_aware_resolver(self, ingest):
        # The plain get_team_by_name this used to call never consulted
        # team_aliases, so the alias seeded for exactly this feed spelling
        # (SB-822) did nothing on the only path that reads the feed.
        result = _run(ingest)
        assert result["status"] == "created"
        assert result["db_id"] == 4242
        ingest._team_dao.get_team_by_name.assert_not_called()

    def test_resolution_is_scoped_to_the_feed_league(self, ingest):
        _run(ingest)
        for call in ingest._team_dao.resolve_team_by_name.call_args_list:
            assert call.kwargs["league_id"] == 1

    def test_a_match_with_no_league_still_resolves_unscoped(self, ingest):
        # league is optional in MatchData. Losing the scope is a downgrade,
        # not a failure — manual and tournament sources send no league.
        _run(ingest, league=None)
        ingest._league_dao.get_league_by_name.assert_not_called()
        for call in ingest._team_dao.resolve_team_by_name.call_args_list:
            assert call.kwargs["league_id"] is None

    def test_an_unmapped_league_name_degrades_rather_than_fails(self, ingest):
        ingest._league_dao.get_league_by_name.return_value = None
        assert _run(ingest, league="MLS NEXT Flex")["status"] == "created"

    @pytest.mark.parametrize("side", ["home_team", "away_team"])
    def test_an_unknown_team_fails_the_task(self, ingest, side):
        with pytest.raises(UnresolvedNameError, match="Team not found: Brand New Club"):
            _run(ingest, **{side: "Brand New Club"})
        ingest._dao.create_match.assert_not_called()


class TestIngestDivisionResolution:
    def test_division_lookup_is_scoped_to_the_league(self, ingest):
        _run(ingest)
        ingest._league_dao.get_division_by_name.assert_called_once_with("Northeast", league_id=1)

    def test_an_unknown_division_fails_instead_of_writing_null(self, ingest):
        # Writing NULL looked like a warning and behaved like data loss:
        # get_league_table filters on division, so the match existed and
        # appeared in no table at all.
        ingest._league_dao.get_division_by_name.return_value = None
        with pytest.raises(UnresolvedNameError, match="Division not found: Northeast"):
            _run(ingest)
        ingest._dao.create_match.assert_not_called()

    def test_a_match_with_no_division_still_creates(self, ingest):
        # Friendlies and tournament fixtures carry no division. Absent is not
        # the same as unresolved.
        assert _run(ingest, division=None)["status"] == "created"
        assert ingest._dao.create_match.call_args.kwargs["division_id"] is None


# ── process_match_data: failures are recorded, not logged (SB-829) ───


class TestUnresolvedNamesAreRecorded:
    def test_an_unknown_team_is_recorded_verbatim_with_context(self, ingest):
        with pytest.raises(UnresolvedNameError):
            _run(ingest, home_team="Brand New Club")

        ingest._ingest_failures_dao.record.assert_called_once()
        args, kwargs = ingest._ingest_failures_dao.record.call_args
        assert args == ("team", "Brand New Club")
        assert kwargs["league"] == "Homegrown"
        # The sample is what makes the alert line actionable rather than a
        # bare name: it says which fixture was lost.
        assert "Brand New Club vs The Island FC West" in kwargs["sample"]
        assert "2026-09-05" in kwargs["sample"]

    def test_an_unknown_division_is_recorded_as_a_division(self, ingest):
        ingest._league_dao.get_division_by_name.return_value = None
        with pytest.raises(UnresolvedNameError):
            _run(ingest)
        assert ingest._ingest_failures_dao.record.call_args.args == ("division", "Northeast")

    def test_the_alert_fires_for_the_recorded_row(self, ingest):
        with pytest.raises(UnresolvedNameError):
            _run(ingest, away_team="Brand New Club")
        _run.alert.assert_called_once()
        assert _run.alert.call_args.kwargs["record"] == {"id": 1, "match_count": 1, "should_alert": True}

    def test_recording_failure_does_not_mask_the_original_error(self, ingest):
        # The diagnostic path must never be the reason a task fails in a
        # different way — that would make the real cause harder to find, not
        # easier.
        ingest._ingest_failures_dao.record.side_effect = RuntimeError("table missing")
        with pytest.raises(RuntimeError):
            _run(ingest, home_team="Brand New Club")

    def test_the_permanent_error_is_excluded_from_autoretry(self):
        # Waiting ten minutes will not make an unknown team known. Without
        # this the failure is retried three times with backoff before anyone
        # is told, and the message is acked either way.
        assert UnresolvedNameError in process_match_data.dont_autoretry_for

    def test_nothing_is_recorded_on_the_happy_path(self, ingest):
        _run(ingest)
        ingest._ingest_failures_dao.record.assert_not_called()


class TestNamesThatStartWorkingAgain:
    def test_a_successful_match_closes_open_rows_for_both_teams(self, ingest):
        # An alias added part way through a load should clear its own alert.
        _run(ingest)
        resolved = {c.args[1] for c in ingest._ingest_failures_dao.resolve.call_args_list}
        assert resolved == {MATCH["home_team"], MATCH["away_team"]}

    def test_a_name_is_only_checked_once_per_worker(self, ingest):
        # A season load is thousands of matches over tens of names. Checking
        # per match would be thousands of round trips to learn the same thing.
        for _ in range(5):
            _run(ingest)
        assert ingest._ingest_failures_dao.resolve.call_count == 2

    def test_the_source_is_carried_through(self, ingest):
        _run(ingest, source="manual")
        assert ingest._ingest_failures_dao.resolve.call_args.kwargs["source"] == "manual"

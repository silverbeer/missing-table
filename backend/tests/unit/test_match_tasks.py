"""Unit tests for Celery match task helper methods.

Tests _build_scheduled_kickoff(), _check_needs_update(), and
_update_match_scores() on the DatabaseTask class without requiring
a live database or Celery broker.
"""

from unittest.mock import MagicMock, patch

import pytest

from celery_tasks.exceptions import UnresolvedNameError
from celery_tasks.match_tasks import (
    KNOWN_LEAGUES_SECONDS,
    KNOWN_TOURNAMENT_SECONDS,
    RESOLVE_BY_LEAGUE_RETRY_SECONDS,
    DatabaseTask,
    process_match_data,
)
from dao.team_sides import AMBIGUOUS, MISSING, RESOLVED, UNKNOWN_LEAGUE, WRONG_SIDE, Resolution

MATCH_TYPES = [
    {"id": 1, "name": "League", "counts_for_qualification": True},
    {"id": 5, "name": "Flex", "counts_for_qualification": True},
    {"id": 3, "name": "Friendly", "counts_for_qualification": False},
    {"id": 2, "name": "Tournament", "counts_for_qualification": False},
]


def _match_type_dao_stub():
    """A MatchTypeDAO stub that answers by name and by id, as the real one does."""
    dao = MagicMock()
    dao.get_all_match_types.return_value = MATCH_TYPES
    dao.get_match_type_by_name.side_effect = lambda name: next(
        (t for t in MATCH_TYPES if t["name"].lower() == (name or "").strip().lower()), None
    )
    dao.get_match_type_by_id.side_effect = lambda mtid: next((t for t in MATCH_TYPES if t["id"] == mtid), None)
    return dao


@pytest.fixture
def task():
    """Create a DatabaseTask instance with a mocked DAO."""
    t = DatabaseTask()
    t._dao = MagicMock()
    # Stubbed rather than left to the lazy property: _match_type_label reads it
    # to log a correction by name, and a unit test must not open a connection.
    t._match_type_dao = _match_type_dao_stub()
    # Every home club is Eastern unless a test says otherwise (SB-1202).
    t._club_dao = MagicMock()
    t._club_dao.get_club_for_team.return_value = {"id": 1, "timezone": "America/New_York"}
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

    # SB-1202: match_time is the venue's local time. San Diego FC home,
    # Sat Oct 3 2026 (PDT, UTC-7), from the assist feed.
    @pytest.mark.parametrize(
        ("match_time", "expected"),
        [("09:00", "2026-10-03T16:00:00+00:00"), ("11:00", "2026-10-03T18:00:00+00:00")],
    )
    def test_reads_match_time_in_pacific(self, task, match_time, expected):
        data = {"match_date": "2026-10-03", "match_time": match_time}
        assert task._build_scheduled_kickoff(data, "America/Los_Angeles") == expected

    @pytest.mark.parametrize(
        ("venue_tz", "expected"),
        [
            ("America/Denver", "2026-10-03T15:00:00+00:00"),  # MDT, UTC-6
            ("America/Phoenix", "2026-10-03T16:00:00+00:00"),  # MST all year, UTC-7
            ("America/Chicago", "2026-10-03T14:00:00+00:00"),  # CDT, UTC-5
            ("America/New_York", "2026-10-03T13:00:00+00:00"),  # EDT, UTC-4
        ],
    )
    def test_reads_match_time_in_other_zones(self, task, venue_tz, expected):
        data = {"match_date": "2026-10-03", "match_time": "09:00"}
        assert task._build_scheduled_kickoff(data, venue_tz) == expected

    def test_pacific_after_dst_ends(self, task):
        """Nov 7 2026 is PST (UTC-8): 09:00 PST → 17:00 UTC."""
        data = {"match_date": "2026-11-07", "match_time": "09:00"}
        assert task._build_scheduled_kickoff(data, "America/Los_Angeles") == "2026-11-07T17:00:00+00:00"

    def test_unknown_zone_reads_as_eastern(self, task):
        data = {"match_date": "2026-03-01", "match_time": "14:00"}
        assert task._build_scheduled_kickoff(data, "Mars/Olympus_Mons") == "2026-03-01T19:00:00+00:00"


# ── _feed_kickoff (SB-1203 payload) ───────────────────────────────────


class TestFeedKickoff:
    @pytest.mark.parametrize(
        "raw",
        ["2026-10-03T16:00:00Z", "2026-10-03T16:00:00+00:00", "2026-10-03T09:00:00-07:00"],
    )
    def test_normalises_to_utc(self, task, raw):
        assert task._feed_kickoff({"scheduled_kickoff": raw}) == "2026-10-03T16:00:00+00:00"

    @pytest.mark.parametrize("raw", [None, "", "2026-10-03T16:00:00", "not a time"])
    def test_ignores_missing_naive_or_garbage(self, task, raw):
        assert task._feed_kickoff({"scheduled_kickoff": raw}) is None


# ── _resolve_kickoff ──────────────────────────────────────────────────


class TestResolveKickoff:
    def test_feed_kickoff_wins_without_a_club_lookup(self, task):
        data = {"match_date": "2026-10-03", "match_time": "09:00", "scheduled_kickoff": "2026-10-03T16:00:00Z"}
        assert task._resolve_kickoff(data, 10) == "2026-10-03T16:00:00+00:00"
        task._club_dao.get_club_for_team.assert_not_called()

    def test_falls_back_to_home_club_timezone(self, task):
        task._club_dao.get_club_for_team.return_value = {"id": 7, "timezone": "America/Los_Angeles"}
        data = {"match_date": "2026-10-03", "match_time": "09:00"}
        assert task._resolve_kickoff(data, 10) == "2026-10-03T16:00:00+00:00"
        task._club_dao.get_club_for_team.assert_called_once_with(10)

    @pytest.mark.parametrize("club", [None, {"id": 7}, {"id": 7, "timezone": None}])
    def test_no_club_timezone_reads_as_eastern(self, task, club):
        task._club_dao.get_club_for_team.return_value = club
        data = {"match_date": "2026-10-03", "match_time": "09:00"}
        assert task._resolve_kickoff(data, 10) == "2026-10-03T13:00:00+00:00"

    def test_club_lookup_failure_reads_as_eastern(self, task):
        task._club_dao.get_club_for_team.side_effect = RuntimeError("db down")
        data = {"match_date": "2026-10-03", "match_time": "09:00"}
        assert task._resolve_kickoff(data, 10) == "2026-10-03T13:00:00+00:00"

    def test_no_home_team_reads_as_eastern(self, task):
        data = {"match_date": "2026-10-03", "match_time": "09:00"}
        assert task._resolve_kickoff(data, None) == "2026-10-03T13:00:00+00:00"
        task._club_dao.get_club_for_team.assert_not_called()

    def test_no_time_means_no_kickoff_and_no_lookup(self, task):
        assert task._resolve_kickoff({"match_date": "2026-10-03"}, 10) is None
        task._club_dao.get_club_for_team.assert_not_called()


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

    def test_feed_kickoff_corrects_an_early_pacific_kickoff(self, task):
        """SB-1202: a row stored 3 h early is corrected by the feed's UTC kickoff."""
        existing = self._existing(scheduled_kickoff="2026-10-03T13:00:00+00:00")
        new_data = {
            "match_status": "scheduled",
            "match_date": "2026-10-03",
            "match_time": "09:00",
            "scheduled_kickoff": "2026-10-03T16:00:00Z",
        }
        assert task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID) is True

    def test_home_club_timezone_corrects_an_early_pacific_kickoff(self, task):
        task._club_dao.get_club_for_team.return_value = {"id": 7, "timezone": "America/Los_Angeles"}
        existing = self._existing(scheduled_kickoff="2026-10-03T13:00:00+00:00")
        new_data = {"match_status": "scheduled", "match_date": "2026-10-03", "match_time": "09:00"}
        assert task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID) is True
        task._club_dao.get_club_for_team.assert_called_once_with(self.HOME_ID)

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

    def test_updates_kickoff_from_feed_using_existing_home_team(self, task):
        """Without a home_team_id argument the existing row's home team picks the club."""
        task._club_dao.get_club_for_team.return_value = {"id": 7, "timezone": "America/Los_Angeles"}
        existing = {"id": 42, "home_team_id": 10, "scheduled_kickoff": "2026-10-03T13:00:00+00:00"}
        new_data = {"match_date": "2026-10-03", "match_time": "09:00"}
        task._dao.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 42}]
        )
        task._update_match_scores(existing, new_data)
        update_payload = task._dao.client.table.return_value.update.call_args[0][0]
        assert update_payload["scheduled_kickoff"] == "2026-10-03T16:00:00+00:00"
        task._club_dao.get_club_for_team.assert_called_once_with(10)

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


# ── a person's postponed/cancelled survives a re-scrape (SB-1135) ────


class TestHeldStatus:
    HOME_ID = 10
    AWAY_ID = 20

    def _existing(self, **kwargs):
        base = {
            "id": 27379,
            "match_status": "postponed",
            "match_date": "2026-09-26",
            "home_score": None,
            "away_score": None,
            "scheduled_kickoff": None,
            "home_team_id": self.HOME_ID,
            "away_team_id": self.AWAY_ID,
        }
        base.update(kwargs)
        return base

    def _check(self, task, existing, new_data):
        return task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID)

    def _payload(self, task):
        return task._dao.client.table("matches").update.call_args[0][0]

    @pytest.mark.parametrize("held", ["postponed", "cancelled"])
    @pytest.mark.parametrize("incoming", ["tbd", "scheduled"])
    def test_same_date_no_score_is_not_a_change(self, task, held, incoming):
        """The scraper's tbd for a fixture that never happened does not undo it."""
        existing = self._existing(match_status=held)
        new_data = {"match_status": incoming, "match_date": "2026-09-26"}
        assert self._check(task, existing, new_data) is False

    def test_a_kickoff_update_keeps_the_held_status(self, task):
        existing = self._existing()
        new_data = {"match_status": "tbd", "match_date": "2026-09-26", "match_time": "14:00"}

        assert self._check(task, existing, new_data) is True
        task._update_match_scores(existing, new_data)

        assert self._payload(task)["match_status"] == "postponed"

    def test_a_new_date_is_a_reschedule(self, task):
        existing = self._existing()
        new_data = {"match_status": "scheduled", "match_date": "2027-06-08"}

        assert self._check(task, existing, new_data) is True
        task._update_match_scores(existing, new_data)

        payload = self._payload(task)
        assert payload["match_date"] == "2027-06-08"
        assert payload["match_status"] == "scheduled"

    def test_a_real_score_means_it_was_played(self, task):
        existing = self._existing()
        new_data = {
            "match_status": "completed",
            "match_date": "2026-09-26",
            "home_score": 2,
            "away_score": 1,
        }

        assert self._check(task, existing, new_data) is True
        task._update_match_scores(existing, new_data)

        payload = self._payload(task)
        assert payload["match_status"] == "completed"
        assert (payload["home_score"], payload["away_score"]) == (2, 1)

    def test_an_unheld_status_still_follows_the_feed(self, task):
        existing = self._existing(match_status="scheduled")
        new_data = {"match_status": "tbd", "match_date": "2026-09-26"}
        assert self._check(task, existing, new_data) is True


# ── the feed's placeholder date is not a reschedule (SB-1136) ────────


class TestPostponedKeepsItsDate:
    HOME_ID = 10
    AWAY_ID = 20
    PLACEHOLDER = "2027-06-08"

    def _existing(self, **kwargs):
        base = {
            "id": 27379,
            "match_status": "tbd",
            "match_date": "2026-09-26",
            "home_score": None,
            "away_score": None,
            "scheduled_kickoff": None,
            "home_team_id": self.HOME_ID,
            "away_team_id": self.AWAY_ID,
        }
        base.update(kwargs)
        return base

    def _postponed(self):
        return {"match_status": "postponed", "match_date": self.PLACEHOLDER}

    def _check(self, task, existing, new_data):
        return task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID)

    def _payload(self, task):
        return task._dao.client.table("matches").update.call_args[0][0]

    def test_a_postponement_marks_the_match_and_keeps_its_date(self, task):
        existing = self._existing()

        assert self._check(task, existing, self._postponed()) is True
        task._update_match_scores(existing, self._postponed())

        payload = self._payload(task)
        assert payload["match_status"] == "postponed"
        assert "match_date" not in payload

    def test_an_already_postponed_match_is_unchanged(self, task):
        existing = self._existing(match_status="postponed")
        assert self._check(task, existing, self._postponed()) is False

    def test_a_cancellation_is_not_downgraded_to_postponed(self, task):
        existing = self._existing(match_status="cancelled")
        assert self._check(task, existing, self._postponed()) is False

    def test_a_completed_match_is_not_un_played(self, task):
        existing = self._existing(match_status="completed", home_score=2, away_score=1)
        assert self._check(task, existing, self._postponed()) is False

    def test_the_real_new_date_still_reschedules(self, task):
        existing = self._existing(match_status="postponed")
        new_data = {"match_status": "scheduled", "match_date": "2026-10-21"}

        assert self._check(task, existing, new_data) is True
        task._update_match_scores(existing, new_data)

        payload = self._payload(task)
        assert payload["match_date"] == "2026-10-21"
        assert payload["match_status"] == "scheduled"


# ── competition and division re-filing (SB-847) ──────────────────────


class TestFilingComparison:
    """A re-scrape must be able to correct a wrongly-filed match.

    68 Flex fixtures sat in prod as League through three clean re-submits:
    every message was accepted, the worker found each match by external id,
    recognised nothing as changed, and logged "Match unchanged". The run
    reported success and nothing was different — the quietest failure there is.
    """

    HOME_ID, AWAY_ID = 10, 20

    def _existing(self, **kwargs):
        base = {
            "id": 4060,
            "match_status": "scheduled",
            "home_score": None,
            "away_score": None,
            "scheduled_kickoff": None,
            "home_team_id": self.HOME_ID,
            "away_team_id": self.AWAY_ID,
            "match_type_id": 1,
            "division_id": 7,
            "source": "match-scraper",
        }
        base.update(kwargs)
        return base

    def _check(self, task, existing, **kw):
        return task._check_needs_update(existing, {"match_status": "scheduled"}, self.HOME_ID, self.AWAY_ID, **kw)

    def test_a_changed_competition_needs_an_update(self, task):
        assert self._check(task, self._existing(), match_type_id=5) is True

    def test_a_changed_division_needs_an_update(self, task):
        assert self._check(task, self._existing(), division_id=9) is True

    def test_the_same_filing_is_still_unchanged(self, task):
        assert self._check(task, self._existing(), match_type_id=1, division_id=7) is False

    def test_a_feed_that_says_nothing_changes_nothing(self, task):
        """No match_type/division in the payload must not read as 'clear them'."""
        assert self._check(task, self._existing()) is False

    def test_a_manual_match_is_not_re_filed(self, task):
        """A friendly recorded against a league fixture's id is a choice, not a typo."""
        assert self._check(task, self._existing(source="manual"), match_type_id=5, division_id=9) is False

    def test_a_manual_match_still_gets_its_scores(self, task):
        """The source gate covers filing only — scraped results still win."""
        existing = self._existing(source="manual")
        new_data = {"match_status": "completed", "home_score": 3, "away_score": 1}
        assert task._check_needs_update(existing, new_data, self.HOME_ID, self.AWAY_ID, match_type_id=5) is True

    def test_a_row_with_no_source_is_treated_as_the_feeds(self, task):
        existing = self._existing()
        del existing["source"]
        assert self._check(task, existing, match_type_id=5) is True


class TestFilingCorrection:
    def _existing(self, **kwargs):
        base = {
            "id": 4060,
            "home_team_id": 10,
            "away_team_id": 20,
            "scheduled_kickoff": None,
            "match_type_id": 1,
            "division_id": 7,
            "source": "match-scraper",
        }
        base.update(kwargs)
        return base

    def _payload(self, task):
        return task._dao.client.table("matches").update.call_args[0][0]

    def test_the_competition_is_written(self, task):
        task._update_match_scores(self._existing(), {}, match_type_id=5)
        assert self._payload(task)["match_type_id"] == 5

    def test_the_division_is_written(self, task):
        task._update_match_scores(self._existing(), {}, division_id=9)
        assert self._payload(task)["division_id"] == 9

    def test_an_unchanged_filing_writes_nothing(self, task):
        """No update data at all → the method reports failure rather than a no-op write."""
        assert task._update_match_scores(self._existing(), {}, match_type_id=1, division_id=7) is False

    def test_a_manual_match_keeps_its_filing(self, task):
        assert task._update_match_scores(self._existing(source="manual"), {}, match_type_id=5) is False

    def test_the_move_is_logged_by_name_not_by_id(self, task):
        """ "match_type corrected: 1 → 5" tells nobody a fixture moved to Flex."""
        with patch("celery_tasks.match_tasks.logger") as log:
            task._update_match_scores(self._existing(), {}, match_type_id=5)
        lines = [c.args[0] for c in log.info.call_args_list if c.args]
        assert any("match_type corrected: League → Flex" in line for line in lines)


# ── process_match_data: name resolution (SB-830) ─────────────────────

IFA = {"id": 19, "name": "IFA"}
OPPONENT = {"id": 20, "name": "The Island FC West"}
HOMEGROWN = {"id": 1, "name": "Homegrown"}
NORTHEAST = {"id": 1, "name": "Northeast", "league_id": 1}
# The leagues table as the tournament side guard reads it (SB-1748).
LEAGUE_ROWS = [
    {"id": 1, "name": "Homegrown", "parent_league_id": None},
    {"id": 2, "name": "Academy", "parent_league_id": None},
    {"id": 290, "name": "Flex", "parent_league_id": 1},
]

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
    task._match_type_dao = _match_type_dao_stub()
    task._ingest_failures_dao = MagicMock()
    task._ingest_failures_dao.record.return_value = {"id": 1, "match_count": 1, "should_alert": True}
    task._resolved_names = set()
    task._ensured_mappings = set()
    task._known_tournaments = {}
    task._known_leagues = None
    task._resolve_by_league_retry_at = 0.0

    task._team_dao.resolve_team_by_name.side_effect = lambda name, league_id=None: {
        MATCH["home_team"]: IFA,
        MATCH["away_team"]: OPPONENT,
    }.get(name)
    # A tournament message resolves through the side guard instead (SB-1748).
    # The same two teams, whatever the side, unless a test says otherwise.
    task._team_dao.resolve_tournament_team.side_effect = lambda name, age_group_id, league, leagues=None: _sided(
        {MATCH["home_team"]: IFA, MATCH["away_team"]: OPPONENT}.get(name)
    )
    task._team_dao.league_rows.return_value = LEAGUE_ROWS
    task._ingest_failures_dao.resolve_in_league.return_value = 0
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
    task._match_type_dao = None
    task._ingest_failures_dao = None
    task._resolved_names = set()
    task._ensured_mappings = set()
    task._known_tournaments = {}
    task._known_leagues = None
    task._resolve_by_league_retry_at = 0.0
    # Drop a clock a test set on the instance; the class one shows through.
    task.__dict__.pop("_clock", None)


def _sided(team):
    """What resolve_tournament_team returns for a team, or for no such name."""
    if team is None:
        return None, Resolution(MISSING)
    return team, Resolution(RESOLVED, team_id=team["id"])


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


class TestIngestCompetitionResolution:
    """SB-847: the feed's competition has to reach the row.

    create_match hardcoded match_type_id 1, so every scraped match was a
    League match whatever the feed said. That is how 68 Flex fixtures were
    created as League (SB-846), and _check_needs_update not comparing
    match_type is why no re-scrape could move them.
    """

    def test_the_feeds_competition_reaches_create(self, ingest):
        _run(ingest, match_type="Flex")
        assert ingest._dao.create_match.call_args.kwargs["match_type_id"] == 5

    def test_league_is_not_assumed(self, ingest):
        _run(ingest)
        assert ingest._dao.create_match.call_args.kwargs["match_type_id"] == 1

    def test_a_feed_with_no_competition_leaves_the_default_to_the_dao(self, ingest):
        # Manual and tournament sources send no match_type. Absent is not Flex
        # and not an error — the DAO's League default stands.
        assert _run(ingest, match_type=None)["status"] == "created"
        assert ingest._dao.create_match.call_args.kwargs["match_type_id"] is None

    def test_an_unknown_competition_fails_instead_of_defaulting_to_league(self, ingest):
        with pytest.raises(UnresolvedNameError):
            _run(ingest, match_type="MLS NEXT Reserve")
        ingest._dao.create_match.assert_not_called()

    def test_the_unknown_competition_is_recorded_as_a_match_type(self, ingest):
        with pytest.raises(UnresolvedNameError):
            _run(ingest, match_type="MLS NEXT Reserve")
        assert ingest._ingest_failures_dao.record.call_args.args[0] == "match_type"
        assert ingest._ingest_failures_dao.record.call_args.args[1] == "MLS NEXT Reserve"


class TestIngestDivisionScoping:
    """SB-1021: the one way a suddenly-broader feed could still land nothing.

    Six of the eight Homegrown League conferences sent no fixtures for a whole
    season. If that is fixed upstream, four of the names arriving — Florida,
    Frontier, Northwest, Southeast — exist in BOTH Homegrown and Flex. They
    only resolve because the feed's league name resolves first and scopes the
    lookup. Lose the league and the division is ambiguous, and an ambiguous
    division is a hard failure, not a guess.
    """

    def test_the_division_lookup_is_scoped_to_the_feed_league(self, ingest):
        _run(ingest)
        assert ingest._league_dao.get_division_by_name.call_args.kwargs["league_id"] == 1

    def test_an_ambiguous_division_fails_rather_than_landing_in_the_wrong_table(self, ingest):
        # get_division_by_name returns None when it cannot tell two leagues'
        # divisions apart. A Flex fixture filed into a Homegrown table would
        # be invisible as a defect; an ingest failure is not.
        ingest._league_dao.get_league_by_name.return_value = None
        ingest._league_dao.get_division_by_name.return_value = None

        with pytest.raises(UnresolvedNameError):
            _run(ingest, league="MLS NEXT Flex", division="Southeast")
        ingest._dao.create_match.assert_not_called()

    def test_that_failure_is_recorded_as_a_division(self, ingest):
        ingest._league_dao.get_division_by_name.return_value = None

        with pytest.raises(UnresolvedNameError):
            _run(ingest, division="Southeast")
        assert ingest._ingest_failures_dao.record.call_args.args[0] == "division"
        assert ingest._ingest_failures_dao.record.call_args.args[1] == "Southeast"


class TestIngestCorrectsAnExistingMatch:
    """The observed failure, end to end: re-submit a Flex fixture filed as League."""

    EXISTING = {
        "id": 4060,
        "home_team_id": IFA["id"],
        "away_team_id": OPPONENT["id"],
        "match_status": "scheduled",
        "home_score": None,
        "away_score": None,
        "scheduled_kickoff": None,
        "match_date": "2026-09-20",
        "match_type_id": 1,
        "division_id": NORTHEAST["id"],
        "source": "match-scraper",
    }

    def test_a_re_scrape_now_corrects_the_competition(self, ingest):
        ingest._dao.get_match_by_external_id.return_value = dict(self.EXISTING)
        result = _run(ingest, match_type="Flex", match_date="2026-09-20")

        assert result["status"] == "updated"
        payload = ingest._dao.client.table("matches").update.call_args[0][0]
        assert payload["match_type_id"] == 5

    def test_an_identical_payload_is_still_unchanged(self, ingest):
        ingest._dao.get_match_by_external_id.return_value = dict(self.EXISTING)
        result = _run(ingest, match_date="2026-09-20")

        assert result["status"] == "skipped"
        ingest._dao.client.table("matches").update.assert_not_called()


class TestIngestRegistersAgeGroups:
    """SB-852: a team must exist at the age groups it actually plays.

    /api/teams builds a team's age_groups purely from team_mappings, and the
    My Club team picker filters on that. Nothing on the ingest path wrote the
    table, so NEFC had 44 U15 matches and an empty U15 team picker. The gap
    regrew on every load that reached a team at a new age group.
    """

    def test_both_teams_are_registered(self, ingest):
        _run(ingest)
        registered = {c.args[:3] for c in ingest._team_dao.ensure_team_mapping.call_args_list}
        assert registered == {(IFA["id"], 3, NORTHEAST["id"]), (OPPONENT["id"], 3, NORTHEAST["id"])}

    def test_a_triple_is_only_written_once_per_worker(self, ingest):
        for _ in range(5):
            _run(ingest)
        # Two teams, once each — not once per match.
        assert ingest._team_dao.ensure_team_mapping.call_count == 2

    def test_a_match_with_no_division_registers_nothing(self, ingest):
        # Friendlies and tournament fixtures carry no division, so there is no
        # registration to express.
        _run(ingest, division=None)
        ingest._team_dao.ensure_team_mapping.assert_not_called()

    def test_a_match_with_no_age_group_registers_nothing(self, ingest):
        ingest._season_dao.get_age_group_by_name.return_value = None
        _run(ingest, age_group="U99")
        ingest._team_dao.ensure_team_mapping.assert_not_called()

    def test_a_flex_bracket_does_not_register_a_homegrown_team(self, ingest):
        """The team would gain a second division at one age group.

        divisions_by_age_group is keyed by age group alone and takes last-wins,
        so the team's division would start displaying as a Flex bracket. Flex
        participation is already expressed by the matches (SB-835).
        """
        ingest._team_dao.resolve_team_by_name.side_effect = lambda name, league_id=None: {
            MATCH["home_team"]: {**IFA, "league_id": 1},
            MATCH["away_team"]: {**OPPONENT, "league_id": 1},
        }.get(name)
        ingest._league_dao.get_division_by_name.return_value = {"id": 309, "name": "Turnpike", "league_id": 290}

        _run(ingest, match_type="Flex", league="Flex")

        ingest._team_dao.ensure_team_mapping.assert_not_called()

    def test_a_teams_own_league_does_register(self, ingest):
        ingest._team_dao.resolve_team_by_name.side_effect = lambda name, league_id=None: {
            MATCH["home_team"]: {**IFA, "league_id": 1},
            MATCH["away_team"]: {**OPPONENT, "league_id": 1},
        }.get(name)

        _run(ingest)

        assert ingest._team_dao.ensure_team_mapping.call_count == 2

    def test_a_team_with_no_league_yet_is_still_registered(self, ingest):
        """Refusing would leave a brand-new team stuck with no mapping at all."""
        _run(ingest)
        assert ingest._team_dao.ensure_team_mapping.call_count == 2

    def test_registration_failure_does_not_lose_the_match(self, ingest):
        ingest._team_dao.ensure_team_mapping.return_value = False
        assert _run(ingest)["status"] == "created"


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
        # The competition is in here too since SB-847: seeding a missing
        # match_type mid-load should clear its alert the same way an alias does.
        assert resolved == {MATCH["home_team"], MATCH["away_team"], MATCH["match_type"]}

    def test_a_name_is_only_checked_once_per_worker(self, ingest):
        # A season load is thousands of matches over tens of names. Checking
        # per match would be thousands of round trips to learn the same thing.
        for _ in range(5):
            _run(ingest)
        # Two teams and one competition, once each — not once per match.
        assert ingest._ingest_failures_dao.resolve.call_count == 3

    def test_the_source_is_carried_through(self, ingest):
        _run(ingest, source="manual")
        assert ingest._ingest_failures_dao.resolve.call_args.kwargs["source"] == "manual"


class TestIngestFilesTheSeasonTheMessageNames:
    """A match belongs to the season it was played in, not today's season.

    Filing by current season put 151 matches with 2025-2026 dates into the
    2026-2027 standings, and made historical backfills impossible for any
    season (SB-882).
    """

    def test_named_season_wins_over_the_current_one(self, ingest):
        ingest._season_dao.get_all_seasons.return_value = [
            {"id": 184, "name": "2026-2027"},
            {"id": 3, "name": "2025-2026"},
        ]
        ingest._season_dao.get_season_by_name.side_effect = lambda n: next(
            (s for s in ingest._season_dao.get_all_seasons.return_value if s["name"] == n), None
        )

        _run(ingest, season="2025-2026", match_date="2025-09-06")

        assert ingest._dao.create_match.call_args.kwargs["season_id"] == 3

    def test_unknown_season_falls_back_to_current_and_says_so(self, ingest):
        ingest._season_dao.get_season_by_name.return_value = None

        with patch("celery_tasks.match_tasks.logger") as log:
            _run(ingest, season="1998-1999")

        assert ingest._dao.create_match.call_args.kwargs["season_id"] == 5
        assert any("Unknown season" in str(c) for c in log.warning.call_args_list)

    def test_missing_season_falls_back_without_warning(self, ingest):
        _run(ingest, season="")

        assert ingest._dao.create_match.call_args.kwargs["season_id"] == 5
        ingest._season_dao.get_season_by_name.assert_not_called()

    def test_source_from_the_message_is_kept(self, ingest):
        ingest._season_dao.get_season_by_name.return_value = {"id": 3, "name": "2025-2026"}

        _run(ingest, season="2025-2026", source="modular11-backfill")

        assert ingest._dao.create_match.call_args.kwargs["source"] == "modular11-backfill"

    def test_source_defaults_to_the_scraper_when_absent(self, ingest):
        _run(ingest, source=None)

        assert ingest._dao.create_match.call_args.kwargs["source"] == "match-scraper"


class TestPenaltyShootout:
    """MLS NEXT Flex fixtures cannot end level — a draw goes to penalties (SB-1020)."""

    HOME_ID = 10
    AWAY_ID = 20

    def _existing(self, **kwargs):
        base = {
            "id": 42,
            "match_status": "completed",
            "home_score": 1,
            "away_score": 1,
            "scheduled_kickoff": None,
            "home_team_id": self.HOME_ID,
            "away_team_id": self.AWAY_ID,
            "home_penalty_score": None,
            "away_penalty_score": None,
        }
        base.update(kwargs)
        return base

    def _drawn(self, **kwargs):
        base = {
            "match_status": "completed",
            "home_score": 1,
            "away_score": 1,
            "home_penalty_score": 4,
            "away_penalty_score": 2,
            "home_team": "Beachside of Connecticut",
            "away_team": "Cedar Stars Academy Bergen",
            "external_match_id": "26306",
        }
        base.update(kwargs)
        return base

    def test_a_shootout_is_read_from_the_message(self, task):
        assert task._read_shootout(self._drawn()) == (4, 2)

    def test_half_a_shootout_is_dropped(self, task):
        """Both columns or neither — the DB's CHECK constraint says so."""
        assert task._read_shootout(self._drawn(away_penalty_score=None)) == (None, None)

    def test_a_shootout_on_a_decided_match_is_dropped(self, task):
        """Penalties are only valid when regulation ended level."""
        assert task._read_shootout(self._drawn(home_score=3, away_score=1)) == (None, None)

    def test_an_unplayed_match_carries_no_shootout(self, task):
        assert task._read_shootout(self._drawn(home_score=None, away_score=None)) == (None, None)

    def test_a_message_with_no_penalties_is_quiet(self, task):
        new_data = {"home_score": 2, "away_score": 1, "match_status": "completed"}
        assert task._read_shootout(new_data) == (None, None)

    def test_an_arriving_shootout_needs_an_update(self, task):
        """Every Flex draw stored before this shipped has the right score and no
        shootout. Without this the row reads as unchanged and is never fixed."""
        existing = self._existing()
        assert task._check_needs_update(existing, self._drawn(), self.HOME_ID, self.AWAY_ID) is True

    def test_an_unchanged_shootout_needs_no_update(self, task):
        existing = self._existing(home_penalty_score=4, away_penalty_score=2)
        assert task._check_needs_update(existing, self._drawn(), self.HOME_ID, self.AWAY_ID) is False

    def test_the_update_writes_both_columns(self, task):
        task._update_match_scores(self._existing(), self._drawn(), home_team_id=self.HOME_ID, away_team_id=self.AWAY_ID)

        payload = task._dao.client.table("matches").update.call_args[0][0]
        assert payload["home_penalty_score"] == 4
        assert payload["away_penalty_score"] == 2

    def test_the_update_omits_an_invalid_shootout(self, task):
        task._update_match_scores(
            self._existing(home_score=3, away_score=1),
            self._drawn(home_score=3, away_score=1),
            home_team_id=self.HOME_ID,
            away_team_id=self.AWAY_ID,
        )

        payload = task._dao.client.table("matches").update.call_args[0][0]
        assert "home_penalty_score" not in payload
        assert "away_penalty_score" not in payload


# ── final-score alert after a scraped score (SB-1619) ───────────────


class TestFinalScoreAlertHook:
    def test_update_returns_the_fields_written(self, task):
        existing = {"id": 42, "home_score": None, "away_score": None, "match_status": "tbd"}
        new_data = {"home_score": 3, "away_score": 1, "match_status": "completed"}
        written = task._update_match_scores(existing, new_data)
        assert written["home_score"] == 3 and written["match_status"] == "completed"

    def test_a_scraped_new_score_requests_the_alert(self, ingest):
        existing = {
            "id": 77,
            "home_team_id": IFA["id"],
            "away_team_id": OPPONENT["id"],
            "home_score": None,
            "away_score": None,
            "match_status": "tbd",
            "match_date": MATCH["match_date"],
            "match_id": MATCH["external_match_id"],
        }
        ingest._dao.get_match_by_external_id.return_value = existing
        ingest._dao.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 77}]
        )
        with patch("celery_tasks.match_tasks.alert_if_new_final_score") as alert:
            result = _run(ingest, home_score=2, away_score=0, match_status="completed")
        assert result["status"] == "updated"
        before, after = alert.call_args.args
        assert before is existing
        assert (after["id"], after["home_score"], after["away_score"]) == (77, 2, 0)

    def test_a_created_match_with_a_score_requests_the_alert(self, ingest):
        with patch("celery_tasks.match_tasks.alert_if_new_final_score") as alert:
            _run(ingest, home_score=1, away_score=1, match_status="completed")
        before, after = alert.call_args.args
        assert before is None and after["id"] == 4242 and after["home_score"] == 1


# ── tournament matches (SB-1747) ─────────────────────────────────────

TOURNAMENT_FIELDS = {
    "match_type": "Tournament",
    "league": None,
    "division": None,
    "external_match_id": "fest-101",
    "tournament_id": 12,
    "competition": "HD Group Play",
    "tournament_group": "A",
    "tournament_round": "group_stage",
    "tournament_round_order": 3,
}


def _run_tournament(task, **overrides):
    return _run(task, **{**TOURNAMENT_FIELDS, **overrides})


def _tournament_row(**overrides):
    """A scraped tournament fixture as the DAO flattens it: no score yet."""
    return {
        "id": 900,
        "home_team_id": IFA["id"],
        "away_team_id": OPPONENT["id"],
        "match_status": "scheduled",
        "home_score": None,
        "away_score": None,
        "home_penalty_score": None,
        "away_penalty_score": None,
        "scheduled_kickoff": None,
        "match_date": MATCH["match_date"],
        "match_type_id": 2,
        "division_id": None,
        "source": "match-scraper",
        "match_id": "fest-101",
        "tournament_id": 12,
        "tournament_group": "HD · A",
        "tournament_round": "group_stage",
        "tournament_round_order": 3,
        **overrides,
    }


class TestIngestFilesATournamentMatch:
    def test_it_is_created_on_the_tournament_with_no_division(self, ingest):
        result = _run_tournament(ingest)

        assert result["status"] == "created"
        created = ingest._dao.create_match.call_args.kwargs
        assert created["division_id"] is None
        assert created["tournament_id"] == 12
        assert created["tournament_group"] == "HD · A"
        assert created["tournament_round"] == "group_stage"
        assert created["tournament_round_order"] == 3

    def test_the_tournament_match_type_is_looked_up_by_name(self, ingest):
        _run_tournament(ingest)
        assert ingest._dao.create_match.call_args.kwargs["match_type_id"] == 2

    def test_the_source_match_id_and_provenance_reach_the_row(self, ingest):
        _run_tournament(ingest)
        created = ingest._dao.create_match.call_args.kwargs
        assert created["match_id"] == "fest-101"
        assert created["source"] == "match-scraper"

    def test_no_division_is_looked_up_and_no_mapping_registered(self, ingest):
        _run_tournament(ingest)
        ingest._league_dao.get_division_by_name.assert_not_called()
        ingest._team_dao.ensure_team_mapping.assert_not_called()

    def test_a_league_message_passes_no_tournament_arguments(self, ingest):
        _run(ingest)
        assert "tournament_id" not in ingest._dao.create_match.call_args.kwargs
        ingest._dao.tournament_exists.assert_not_called()

    def test_the_tournament_is_checked_once_per_worker(self, ingest):
        _run_tournament(ingest)
        _run_tournament(ingest, external_match_id="fest-102")
        ingest._dao.tournament_exists.assert_called_once_with(12)

    def test_a_known_tournament_is_asked_about_again_once_the_entry_expires(self, ingest):
        now = [1000.0]
        ingest._clock = lambda: now[0]

        _run_tournament(ingest)
        now[0] += KNOWN_TOURNAMENT_SECONDS - 1
        _run_tournament(ingest, external_match_id="fest-102")
        assert ingest._dao.tournament_exists.call_count == 1

        now[0] += 1
        _run_tournament(ingest, external_match_id="fest-103")
        assert ingest._dao.tournament_exists.call_count == 2

    def test_a_tournament_deleted_after_it_was_seen_becomes_a_recorded_failure(self, ingest):
        now = [1000.0]
        ingest._clock = lambda: now[0]
        _run_tournament(ingest)
        assert ingest._dao.create_match.call_count == 1

        ingest._dao.tournament_exists.return_value = False
        now[0] += KNOWN_TOURNAMENT_SECONDS
        with pytest.raises(UnresolvedNameError):
            _run_tournament(ingest, external_match_id="fest-102")

        assert ingest._dao.create_match.call_count == 1
        recorded = ingest._ingest_failures_dao.record.call_args
        assert recorded.args[:2] == ("invalid", "unknown tournament_id 12")

    def test_the_known_tournament_lifetime_is_ten_minutes(self):
        assert KNOWN_TOURNAMENT_SECONDS == 600

    def test_an_unknown_team_still_fails_and_creates_nothing(self, ingest):
        with pytest.raises(UnresolvedNameError, match="Team not found: Brand New Club"):
            _run_tournament(ingest, home_team="Brand New Club")
        ingest._dao.create_match.assert_not_called()

    def test_a_shootout_reaches_create(self, ingest):
        _run_tournament(
            ingest,
            tournament_round="placement_final",
            home_score=1,
            away_score=1,
            home_penalty_score=4,
            away_penalty_score=3,
            match_status="completed",
        )
        created = ingest._dao.create_match.call_args.kwargs
        assert (created["home_penalty_score"], created["away_penalty_score"]) == (4, 3)


class TestALeagueMessageIsResolvedAsBefore:
    """The side guard is for tournament messages only (SB-1748).

    A league message must make the calls it made before the guard existed, in
    the order it made them — pinned here call by call.
    """

    DAOS = ("_dao", "_team_dao", "_season_dao", "_league_dao", "_ingest_failures_dao")

    def _calls(self, ingest):
        parent = MagicMock()
        for name in self.DAOS:
            parent.attach_mock(getattr(ingest, name), name)
        ingest._match_type_dao.get_match_type_by_name = MagicMock(
            side_effect=ingest._match_type_dao.get_match_type_by_name.side_effect
        )
        parent.attach_mock(ingest._match_type_dao.get_match_type_by_name, "match_type_by_name")
        _run(ingest)
        # Calls on the DAOs themselves, not on what they returned.
        return [(name, args, kwargs) for name, args, kwargs in parent.mock_calls if "()" not in name]

    def test_the_call_sequence_is_unchanged(self, ingest):
        home, away = MATCH["home_team"], MATCH["away_team"]
        assert self._calls(ingest) == [
            ("_league_dao.get_league_by_name", ("Homegrown",), {}),
            ("_team_dao.resolve_team_by_name", (home,), {"league_id": 1}),
            ("_team_dao.resolve_team_by_name", (away,), {"league_id": 1}),
            ("_ingest_failures_dao.resolve", ("team", home), {"source": "match-scraper"}),
            ("_ingest_failures_dao.resolve", ("team", away), {"source": "match-scraper"}),
            ("match_type_by_name", ("League",), {}),
            ("_ingest_failures_dao.resolve", ("match_type", "League"), {"source": "match-scraper"}),
            ("_league_dao.get_division_by_name", ("Northeast",), {"league_id": 1}),
            ("_season_dao.get_age_group_by_name", ("U15",), {}),
            ("_team_dao.ensure_team_mapping", (IFA["id"], 3, NORTHEAST["id"]), {}),
            ("_team_dao.ensure_team_mapping", (OPPONENT["id"], 3, NORTHEAST["id"]), {}),
            ("_dao.get_match_by_external_id", ("kitman-1",), {}),
            (
                "_dao.get_match_by_teams_and_date",
                (),
                {
                    "home_team_id": IFA["id"],
                    "away_team_id": OPPONENT["id"],
                    "match_date": MATCH["match_date"],
                    "age_group_id": 3,
                },
            ),
            ("_season_dao.get_season_by_name", ("2026-2027",), {}),
            ("_dao.create_match", (), ingest._dao.create_match.call_args.kwargs),
        ]

    def test_it_never_reaches_the_side_guard(self, ingest):
        _run(ingest)
        ingest._team_dao.resolve_tournament_team.assert_not_called()
        ingest._team_dao.league_rows.assert_not_called()
        ingest._ingest_failures_dao.resolve_in_league.assert_not_called()

    def test_a_league_it_does_not_have_is_still_only_a_warning(self, ingest):
        # Unknown-league-is-a-failure is for tournament messages. A league
        # message with one keeps its unscoped lookups and is filed.
        ingest._league_dao.get_league_by_name.return_value = None

        result = _run(ingest, league="HD")

        assert result["status"] == "created"
        assert [c.kwargs for c in ingest._team_dao.resolve_team_by_name.call_args_list] == [{"league_id": None}] * 2
        ingest._team_dao.league_rows.assert_not_called()
        ingest._ingest_failures_dao.record.assert_not_called()

    def test_the_missing_function_backoff_does_not_touch_it(self, ingest):
        ingest._resolve_by_league_retry_at = float("inf")
        _run(ingest)
        closed = [c.args for c in ingest._ingest_failures_dao.resolve.call_args_list if c.args[0] == "team"]
        assert closed == [("team", MATCH["home_team"]), ("team", MATCH["away_team"])]

    def test_its_resolved_names_are_keyed_as_before(self, ingest):
        _run(ingest)
        assert ("team", MATCH["home_team"].lower()) in ingest._resolved_names
        assert all(len(key) == 2 for key in ingest._resolved_names)


class TestIngestResolvesATournamentTeamOnItsSide:
    """Homegrown and Academy share an event and team names (SB-1748)."""

    def test_the_name_is_resolved_on_the_messages_side_at_its_age_group(self, ingest):
        ingest._league_dao.get_league_by_name.return_value = {"id": 2, "name": "Academy"}

        result = _run_tournament(ingest, league="Academy")

        assert result["status"] == "created"
        assert [c.args for c in ingest._team_dao.resolve_tournament_team.call_args_list] == [
            (MATCH["home_team"], 3, "Academy"),
            (MATCH["away_team"], 3, "Academy"),
        ]
        ingest._team_dao.resolve_team_by_name.assert_not_called()
        created = ingest._dao.create_match.call_args.kwargs
        assert (created["home_team_id"], created["away_team_id"]) == (IFA["id"], OPPONENT["id"])

    def test_the_age_group_is_looked_up_once_before_the_teams(self, ingest):
        parent = MagicMock()
        parent.attach_mock(ingest._season_dao.get_age_group_by_name, "age_group")
        parent.attach_mock(ingest._team_dao.resolve_tournament_team, "team")

        _run_tournament(ingest)

        assert [name for name, _, _ in parent.mock_calls] == ["age_group", "team", "team"]

    def test_a_message_with_no_league_and_one_candidate_resolves(self, ingest):
        result = _run_tournament(ingest, league=None)

        assert result["status"] == "created"
        assert ingest._team_dao.resolve_tournament_team.call_args_list[0].args == (MATCH["home_team"], 3, None)

    @pytest.mark.parametrize(
        ("resolution", "reason"),
        [
            (Resolution(WRONG_SIDE, reason="wrong side: exists as Homegrown"), "wrong side: exists as Homegrown"),
            (Resolution(AMBIGUOUS, reason="ambiguous: team ids 7, 9"), "ambiguous: team ids 7, 9"),
        ],
    )
    def test_a_name_that_cannot_be_placed_is_one_recorded_failure(self, ingest, resolution, reason):
        ingest._team_dao.resolve_tournament_team.side_effect = lambda name, age_group_id, league, leagues=None: (
            (None, resolution) if name == MATCH["away_team"] else _sided(IFA)
        )

        with pytest.raises(UnresolvedNameError, match="Team not found: The Island FC West"):
            _run_tournament(ingest, league="Academy")

        ingest._dao.create_match.assert_not_called()
        ingest._team_dao.add_team.assert_not_called()
        ingest._team_dao.add_team_alias.assert_not_called()
        ingest._ingest_failures_dao.record.assert_called_once()
        recorded = ingest._ingest_failures_dao.record.call_args
        assert recorded.args == ("team", MATCH["away_team"])
        assert recorded.kwargs["league"] == "Academy"
        assert recorded.kwargs["sample"].endswith(f"[{reason}]")
        # Neither name is closed: the message failed before either was noted.
        ingest._ingest_failures_dao.resolve_in_league.assert_not_called()

    def test_that_failure_is_not_retried(self):
        assert UnresolvedNameError in process_match_data.dont_autoretry_for

    def test_a_name_nobody_has_carries_no_reason(self, ingest):
        with pytest.raises(UnresolvedNameError):
            _run_tournament(ingest, home_team="Brand New Club")
        assert "[" not in ingest._ingest_failures_dao.record.call_args.kwargs["sample"]

    def test_an_unknown_age_group_fails_before_any_team_is_resolved(self, ingest):
        ingest._season_dao.get_age_group_by_name.return_value = None

        with pytest.raises(UnresolvedNameError):
            _run_tournament(ingest, age_group="U99")

        ingest._team_dao.resolve_tournament_team.assert_not_called()
        assert ingest._ingest_failures_dao.record.call_args.args == (
            "invalid",
            "unknown age group 'U99' on a tournament match",
        )


class TestATournamentSuccessClosesItsOwnSideOnly:
    def test_a_homegrown_success_does_not_close_the_academy_row(self, ingest):
        _run_tournament(ingest, league="Homegrown")

        closed = ingest._ingest_failures_dao.resolve_in_league.call_args_list
        assert [(c.args, c.kwargs) for c in closed] == [
            (("team", MATCH["home_team"]), {"league": "Homegrown", "source": "match-scraper"}),
            (("team", MATCH["away_team"]), {"league": "Homegrown", "source": "match-scraper"}),
        ]
        # The league-blind close is what would take the Academy row with it.
        team_closes = [c for c in ingest._ingest_failures_dao.resolve.call_args_list if c.args[0] == "team"]
        assert team_closes == []

    def test_resolved_names_are_keyed_by_league(self, ingest):
        _run_tournament(ingest, league="Homegrown")
        assert ("team", MATCH["home_team"].lower(), "homegrown") in ingest._resolved_names
        assert ("team", MATCH["home_team"].lower()) not in ingest._resolved_names

        ingest._league_dao.get_league_by_name.return_value = {"id": 2, "name": "Academy"}
        _run_tournament(ingest, league="Academy", external_match_id="fest-102")

        leagues = [c.kwargs["league"] for c in ingest._ingest_failures_dao.resolve_in_league.call_args_list]
        assert leagues == ["Homegrown", "Homegrown", "Academy", "Academy"]

    def test_a_side_is_only_checked_once_per_worker(self, ingest):
        for n in range(5):
            _run_tournament(ingest, league="Homegrown", external_match_id=f"fest-{n}")
        assert ingest._ingest_failures_dao.resolve_in_league.call_count == 2

    def test_a_message_with_no_league_closes_only_rows_with_none(self, ingest):
        _run_tournament(ingest)
        assert {c.kwargs["league"] for c in ingest._ingest_failures_dao.resolve_in_league.call_args_list} == {None}

    def test_a_league_success_is_not_remembered_as_the_tournament_answer(self, ingest):
        _run(ingest)
        _run_tournament(ingest, league="Homegrown")
        assert ingest._ingest_failures_dao.resolve_in_league.call_count == 2


class TestTheResolveByLeagueFunctionIsNotInstalledYet:
    """Code deploys on merge; the migration is applied by hand afterwards (SB-1748).

    resolve_in_league returns None for a database without the function. Until
    it has one nothing is closed and nothing remembered — and the worker stops
    asking for a while instead of failing twice per tournament message.
    """

    def _clock(self, ingest):
        now = [5000.0]
        ingest._clock = lambda: now[0]
        return now

    def test_it_is_asked_once_and_then_left_alone(self, ingest):
        self._clock(ingest)
        ingest._ingest_failures_dao.resolve_in_league.return_value = None

        for n in range(5):
            assert _run_tournament(ingest, league="Homegrown", external_match_id=f"fest-{n}")["status"] == "created"

        # Not ten: the home name asked, and the away name and four more
        # messages did not.
        assert ingest._ingest_failures_dao.resolve_in_league.call_count == 1
        assert not any(len(key) == 3 for key in ingest._resolved_names)
        # Never the league-blind close in its place.
        assert [c for c in ingest._ingest_failures_dao.resolve.call_args_list if c.args[0] == "team"] == []

    def test_it_is_asked_again_once_the_window_has_passed(self, ingest):
        now = self._clock(ingest)
        ingest._ingest_failures_dao.resolve_in_league.return_value = None
        _run_tournament(ingest, league="Homegrown")

        now[0] += RESOLVE_BY_LEAGUE_RETRY_SECONDS - 1
        _run_tournament(ingest, league="Homegrown", external_match_id="fest-102")
        assert ingest._ingest_failures_dao.resolve_in_league.call_count == 1

        now[0] += 1
        _run_tournament(ingest, league="Homegrown", external_match_id="fest-103")
        assert ingest._ingest_failures_dao.resolve_in_league.call_count == 2

    def test_closing_starts_by_itself_once_the_migration_lands(self, ingest):
        now = self._clock(ingest)
        ingest._ingest_failures_dao.resolve_in_league.return_value = None
        _run_tournament(ingest, league="Homegrown")

        ingest._ingest_failures_dao.resolve_in_league.return_value = 1
        now[0] += RESOLVE_BY_LEAGUE_RETRY_SECONDS
        _run_tournament(ingest, league="Homegrown", external_match_id="fest-102")

        closed = ingest._ingest_failures_dao.resolve_in_league.call_args_list[1:]
        assert [c.args for c in closed] == [("team", MATCH["home_team"]), ("team", MATCH["away_team"])]
        assert ("team", MATCH["home_team"].lower(), "homegrown") in ingest._resolved_names
        assert ("team", MATCH["away_team"].lower(), "homegrown") in ingest._resolved_names

    def test_the_window_is_ten_minutes(self):
        assert RESOLVE_BY_LEAGUE_RETRY_SECONDS == 600


class TestIngestReadsTheLeaguesOncePerWorker:
    """The side guard needs the leagues table; six rows, twice a message (SB-1748)."""

    def test_they_are_read_once_and_handed_to_the_resolver(self, ingest):
        for n in range(4):
            _run_tournament(ingest, league="Homegrown", external_match_id=f"fest-{n}")

        ingest._team_dao.league_rows.assert_called_once_with()
        calls = ingest._team_dao.resolve_tournament_team.call_args_list
        assert len(calls) == 8
        assert all(c.kwargs == {"leagues": LEAGUE_ROWS} for c in calls)

    def test_they_are_read_again_once_the_entry_expires(self, ingest):
        now = [1000.0]
        ingest._clock = lambda: now[0]

        _run_tournament(ingest, league="Homegrown")
        now[0] += KNOWN_LEAGUES_SECONDS - 1
        _run_tournament(ingest, league="Homegrown", external_match_id="fest-102")
        assert ingest._team_dao.league_rows.call_count == 1

        now[0] += 1
        _run_tournament(ingest, league="Homegrown", external_match_id="fest-103")
        assert ingest._team_dao.league_rows.call_count == 2

    def test_a_league_created_since_is_found_after_the_entry_expires(self, ingest):
        now = [1000.0]
        ingest._clock = lambda: now[0]
        _run_tournament(ingest, league="Homegrown")

        ingest._team_dao.league_rows.return_value = [*LEAGUE_ROWS, {"id": 7, "name": "Pro", "parent_league_id": None}]
        with pytest.raises(UnresolvedNameError, match="League not found: Pro"):
            _run_tournament(ingest, league="Pro", external_match_id="fest-102")

        now[0] += KNOWN_LEAGUES_SECONDS
        assert _run_tournament(ingest, league="Pro", external_match_id="fest-103")["status"] == "created"

    def test_an_empty_answer_is_not_kept(self, ingest):
        ingest._team_dao.league_rows.return_value = []
        with pytest.raises(UnresolvedNameError):
            _run_tournament(ingest, league="Homegrown")

        ingest._team_dao.league_rows.return_value = LEAGUE_ROWS
        assert _run_tournament(ingest, league="Homegrown", external_match_id="fest-102")["status"] == "created"

    def test_a_message_with_no_league_does_not_read_them(self, ingest):
        _run_tournament(ingest, league=None)
        ingest._team_dao.league_rows.assert_not_called()
        assert ingest._team_dao.resolve_tournament_team.call_args_list[0].kwargs == {"leagues": None}

    def test_a_failed_read_is_raised_to_be_retried_not_recorded(self, ingest):
        ingest._team_dao.league_rows.side_effect = RuntimeError("connection reset")
        with pytest.raises(RuntimeError):
            _run_tournament(ingest, league="Homegrown")
        ingest._ingest_failures_dao.record.assert_not_called()

    def test_the_lifetime_is_ten_minutes(self):
        assert KNOWN_LEAGUES_SECONDS == 600


class TestATournamentMessageNamesALeagueMtDoesNotHave:
    """`league` picks the side on a tournament message, so a wrong one is its own failure (SB-1748).

    Left to the side guard, every team in the event failed as "wrong side:
    exists as Homegrown" — some 1,350 rows for one mistyped string.
    """

    @pytest.mark.parametrize("hint", ["HD", "Homegrown Division", "Homegrwon", "Home%"])
    def test_it_is_one_failure_for_the_hint_and_no_team_is_looked_up(self, ingest, hint):
        # get_league_by_name matches with ilike, so 'Home%' finds Homegrown
        # there; the side guard's own whole-name comparison is what decides.
        ingest._league_dao.get_league_by_name.return_value = HOMEGROWN if hint == "Home%" else None

        with pytest.raises(UnresolvedNameError, match=f"League not found: {hint}"):
            _run_tournament(ingest, league=hint)

        ingest._team_dao.resolve_tournament_team.assert_not_called()
        ingest._team_dao.resolve_team_by_name.assert_not_called()
        ingest._dao.create_match.assert_not_called()
        ingest._ingest_failures_dao.record.assert_called_once()
        recorded = ingest._ingest_failures_dao.record.call_args
        assert recorded.args == ("league", hint)
        assert recorded.kwargs["league"] is None
        assert recorded.kwargs["source"] == "match-scraper"
        assert MATCH["home_team"] in recorded.kwargs["sample"]

    def test_every_message_with_it_records_the_same_identity(self, ingest):
        # One row: the database counts repeats of (kind, raw_name, league, source).
        for n, away in enumerate(["The Island FC West", "Some Other Club", "A Third Club"]):
            with pytest.raises(UnresolvedNameError):
                _run_tournament(ingest, league="HD", away_team=away, external_match_id=f"fest-{n}")

        identities = {
            (c.args, c.kwargs["league"], c.kwargs["source"]) for c in ingest._ingest_failures_dao.record.call_args_list
        }
        assert identities == {(("league", "HD"), None, "match-scraper")}
        ingest._team_dao.resolve_tournament_team.assert_not_called()

    def test_it_is_not_retried(self):
        assert UnresolvedNameError in process_match_data.dont_autoretry_for

    def test_it_is_alerted_as_an_unknown_league(self, ingest):
        with pytest.raises(UnresolvedNameError):
            _run_tournament(ingest, league="HD")
        assert _run.alert.call_args.kwargs["kind"] == "league"
        assert _run.alert.call_args.kwargs["raw_name"] == "HD"

    def test_nothing_is_closed_or_remembered(self, ingest):
        with pytest.raises(UnresolvedNameError):
            _run_tournament(ingest, league="HD")
        ingest._ingest_failures_dao.resolve_in_league.assert_not_called()
        ingest._ingest_failures_dao.resolve.assert_not_called()
        assert ingest._resolved_names == set()

    def test_a_known_league_is_matched_without_case_or_padding(self, ingest):
        assert _run_tournament(ingest, league=" academy ")["status"] == "created"

    def test_a_child_league_is_a_known_league(self, ingest):
        assert _run_tournament(ingest, league="Flex")["status"] == "created"

    def test_a_blank_league_is_no_league(self, ingest):
        assert _run_tournament(ingest, league="   ")["status"] == "created"
        ingest._team_dao.league_rows.assert_not_called()

    def test_the_resolver_saying_so_itself_is_the_same_failure(self, ingest):
        # Belt and braces: the DAO refuses an unknown league too.
        ingest._team_dao.resolve_tournament_team.side_effect = lambda name, age_group_id, league, leagues=None: (
            None,
            Resolution(UNKNOWN_LEAGUE, reason="unknown league 'Academy'"),
        )

        with pytest.raises(UnresolvedNameError, match="League not found: Academy"):
            _run_tournament(ingest, league="Academy")

        assert ingest._ingest_failures_dao.record.call_args.args == ("league", "Academy")
        assert ingest._team_dao.resolve_tournament_team.call_count == 1


class TestIngestRejectsATournamentMatchItCannotFile:
    def test_an_unknown_tournament_is_an_invalid_failure(self, ingest):
        ingest._dao.tournament_exists.return_value = False

        with pytest.raises(UnresolvedNameError):
            _run_tournament(ingest, tournament_id=999)

        ingest._dao.create_match.assert_not_called()
        recorded = ingest._ingest_failures_dao.record.call_args
        assert recorded.args[0] == "invalid"
        assert recorded.args[1] == "unknown tournament_id 999"

    def test_an_unknown_tournament_is_not_retried(self):
        # The same exception type the task already declines to retry: a
        # tournament nobody created will not exist in ten minutes either.
        assert UnresolvedNameError in process_match_data.dont_autoretry_for

    def test_an_unknown_tournament_is_not_remembered_as_known(self, ingest):
        ingest._dao.tournament_exists.return_value = False
        with pytest.raises(UnresolvedNameError):
            _run_tournament(ingest, tournament_id=999)

        ingest._dao.tournament_exists.return_value = True
        assert _run_tournament(ingest, tournament_id=999)["status"] == "created"

    def test_an_unknown_age_group_fails_rather_than_defaulting(self, ingest):
        ingest._season_dao.get_age_group_by_name.return_value = None

        with pytest.raises(UnresolvedNameError):
            _run_tournament(ingest, age_group="U99")

        ingest._dao.create_match.assert_not_called()
        recorded = ingest._ingest_failures_dao.record.call_args
        assert recorded.args[0] == "invalid"
        assert "U99" in recorded.args[1]

    def test_a_league_message_still_defaults_an_unknown_age_group(self, ingest):
        # Unchanged on purpose: only tournament messages fail here.
        ingest._season_dao.get_age_group_by_name.return_value = None
        _run(ingest, age_group="U99")
        assert ingest._dao.create_match.call_args.kwargs["age_group_id"] == 1

    def test_tournament_fields_without_the_id_are_an_invalid_failure(self, ingest):
        with pytest.raises(UnresolvedNameError):
            _run(ingest, tournament_group="A")

        ingest._dao.create_match.assert_not_called()
        recorded = ingest._ingest_failures_dao.record.call_args
        assert recorded.args[0] == "invalid"
        assert recorded.args[1] == "tournament_group requires tournament_id"

    def test_a_malformed_round_is_recorded_before_any_lookup(self, ingest):
        with pytest.raises(UnresolvedNameError):
            _run_tournament(ingest, tournament_round="Group Stage")
        ingest._team_dao.resolve_team_by_name.assert_not_called()
        assert ingest._ingest_failures_dao.record.call_args.args[0] == "invalid"

    def test_a_round_mt_does_not_know_is_filed_with_a_warning(self, ingest):
        with patch("celery_tasks.match_tasks.logger") as log:
            result = _run_tournament(ingest, tournament_round="play_in_2")

        assert result["status"] == "created"
        assert ingest._dao.create_match.call_args.kwargs["tournament_round"] == "play_in_2"
        assert any(c.kwargs.get("tournament_round") == "play_in_2" for c in log.warning.call_args_list)


class TestIngestRescrapesATournamentMatch:
    def test_an_unchanged_rescrape_is_skipped(self, ingest):
        # Guards the flatten: without the tournament columns on the row every
        # rescrape reads as a re-filing and rewrites all 2,400 matches.
        ingest._dao.get_match_by_external_id.return_value = _tournament_row()

        result = _run_tournament(ingest)

        assert result["status"] == "skipped"
        ingest._dao.update_ingested_tournament_match.assert_not_called()
        ingest._dao.client.table("matches").update.assert_not_called()
        ingest._dao.create_match.assert_not_called()

    def test_a_score_is_written_through_the_cache_clearing_dao_method(self, ingest):
        ingest._dao.get_match_by_external_id.return_value = _tournament_row()

        result = _run_tournament(ingest, home_score=2, away_score=1, match_status="completed")

        assert result["status"] == "updated"
        match_id, payload = ingest._dao.update_ingested_tournament_match.call_args.args
        assert match_id == 900
        assert (payload["home_score"], payload["away_score"]) == (2, 1)
        assert "tournament_id" not in payload
        ingest._dao.client.table("matches").update.assert_not_called()

    def test_a_league_update_is_still_written_directly(self, ingest):
        existing = dict(TestIngestCorrectsAnExistingMatch.EXISTING)
        ingest._dao.get_match_by_external_id.return_value = existing

        _run(ingest, match_type="Flex", match_date="2026-09-20")

        ingest._dao.update_ingested_tournament_match.assert_not_called()
        ingest._dao.client.table("matches").update.assert_called_once()

    def test_a_rescrape_that_omits_the_group_does_not_clear_it(self, ingest):
        ingest._dao.get_match_by_external_id.return_value = _tournament_row()

        result = _run_tournament(
            ingest, competition=None, tournament_group=None, tournament_round=None, tournament_round_order=None
        )

        assert result["status"] == "skipped"

    def test_the_feed_re_files_a_match_it_owns(self, ingest):
        ingest._dao.get_match_by_external_id.return_value = _tournament_row()

        result = _run_tournament(ingest, tournament_group="B")

        assert result["status"] == "updated"
        payload = ingest._dao.update_ingested_tournament_match.call_args.args[1]
        assert payload["tournament_group"] == "HD · B"

    def test_a_manual_rows_tournament_fields_are_not_re_filed(self, ingest):
        ingest._dao.get_match_by_external_id.return_value = _tournament_row(
            source="manual", tournament_group="Bracket A", tournament_round="final"
        )

        result = _run_tournament(ingest)

        assert result["status"] == "skipped"
        ingest._dao.update_ingested_tournament_match.assert_not_called()

    def test_a_manual_row_still_takes_the_scraped_score(self, ingest):
        # Scraped data wins on results; only the filing is the user's.
        ingest._dao.get_match_by_external_id.return_value = _tournament_row(
            source="manual", tournament_group="Bracket A", tournament_round="final"
        )

        result = _run_tournament(ingest, home_score=3, away_score=0, match_status="completed")

        assert result["status"] == "updated"
        payload = ingest._dao.update_ingested_tournament_match.call_args.args[1]
        assert payload["home_score"] == 3
        assert "tournament_group" not in payload and "tournament_round" not in payload

    def test_a_partial_rescrape_does_not_re_file_the_group(self, ingest):
        # Each message composes to something other than "HD · A" if the
        # missing field is ignored: "HD", "HD · Group Play", "A".
        ingest._dao.get_match_by_external_id.return_value = _tournament_row()

        assert _run_tournament(ingest, tournament_group=None)["status"] == "skipped"
        assert _run_tournament(ingest, tournament_round=None)["status"] == "skipped"
        assert _run_tournament(ingest, competition=None)["status"] == "skipped"
        ingest._dao.update_ingested_tournament_match.assert_not_called()

    def test_a_partial_rescrape_with_a_score_writes_the_score_and_not_the_group(self, ingest):
        ingest._dao.get_match_by_external_id.return_value = _tournament_row()

        _run_tournament(ingest, competition=None, home_score=2, away_score=1, match_status="completed")

        payload = ingest._dao.update_ingested_tournament_match.call_args.args[1]
        assert (payload["home_score"], payload["away_score"]) == (2, 1)
        assert "tournament_group" not in payload

    def test_a_row_the_agent_sender_created_is_re_filed(self, ingest):
        # match-scraper-agent is the live sender; most scraped rows carry it.
        ingest._dao.get_match_by_external_id.return_value = _tournament_row(source="match-scraper-agent")

        result = _run_tournament(
            ingest,
            competition="HD Showcase",
            tournament_group=None,
            tournament_round="showcase",
            tournament_round_order=7,
        )

        assert result["status"] == "updated"
        match_id, payload = ingest._dao.update_ingested_tournament_match.call_args.args
        assert match_id == 900
        assert payload["tournament_group"] == "HD · Showcase"
        assert payload["tournament_round"] == "showcase"
        assert payload["tournament_round_order"] == 7
        assert "tournament_id" not in payload

    def test_league_re_filing_of_an_agent_row_is_unchanged(self, ingest):
        # The pre-ticket rule, kept as it was: competition and division are
        # re-filed only on rows whose source is exactly 'match-scraper'.
        existing = dict(
            TestIngestCorrectsAnExistingMatch.EXISTING, source="match-scraper-agent", match_date=MATCH["match_date"]
        )
        ingest._dao.get_match_by_external_id.return_value = existing
        ingest._league_dao.get_division_by_name.return_value = {"id": 9, "name": "Florida", "league_id": 1}

        assert _run(ingest, match_type="Flex", division="Florida")["status"] == "skipped"
        ingest._dao.client.table("matches").update.assert_not_called()

        _run(ingest, match_type="Flex", division="Florida", home_score=1, away_score=0, match_status="completed")
        payload = ingest._dao.client.table("matches").update.call_args[0][0]
        assert payload["home_score"] == 1
        assert "match_type_id" not in payload and "division_id" not in payload

    def test_a_league_row_is_not_moved_onto_a_tournament(self, ingest):
        existing = dict(TestIngestCorrectsAnExistingMatch.EXISTING, match_date=MATCH["match_date"])
        ingest._dao.get_match_by_external_id.return_value = existing

        with pytest.raises(UnresolvedNameError):
            _run_tournament(ingest, home_score=2, away_score=1, match_status="completed")

        ingest._dao.update_ingested_tournament_match.assert_not_called()
        ingest._dao.client.table("matches").update.assert_not_called()
        ingest._dao.create_match.assert_not_called()
        ingest._ingest_failures_dao.record.assert_called_once()
        recorded = ingest._ingest_failures_dao.record.call_args
        assert recorded.args[0] == "invalid"
        assert recorded.args[1] == "tournament_id 12 sent for a match already filed on a league division"

    def test_a_row_on_another_tournament_is_not_moved(self, ingest):
        ingest._dao.get_match_by_external_id.return_value = _tournament_row(tournament_id=11)

        with pytest.raises(UnresolvedNameError):
            _run_tournament(ingest, home_score=2, away_score=1, match_status="completed")

        ingest._dao.update_ingested_tournament_match.assert_not_called()
        ingest._dao.create_match.assert_not_called()
        ingest._ingest_failures_dao.record.assert_called_once()
        recorded = ingest._ingest_failures_dao.record.call_args
        assert recorded.args[:2] == ("invalid", "tournament_id 12 sent for a match already filed on tournament 11")

    def test_a_row_filed_nowhere_is_filed_on_the_tournament(self, ingest):
        ingest._dao.get_match_by_external_id.return_value = _tournament_row(
            tournament_id=None, tournament_group=None, tournament_round=None, tournament_round_order=None
        )

        assert _run_tournament(ingest)["status"] == "updated"

        payload = ingest._dao.update_ingested_tournament_match.call_args.args[1]
        assert payload["tournament_id"] == 12
        assert payload["tournament_group"] == "HD · A"
        ingest._ingest_failures_dao.record.assert_not_called()


class TestIngestFallbackLookup:
    """The teams-and-date fallback adopts hand-entered matches — nothing else."""

    def test_a_hit_that_is_another_source_match_is_ignored(self, ingest):
        # Two fixtures between the same teams on the same day: updating the
        # first with the second's score overwrites a real result.
        ingest._dao.get_match_by_teams_and_date.return_value = _tournament_row(match_id="fest-100", home_score=4)

        result = _run_tournament(ingest, home_score=0, away_score=0, match_status="completed")

        assert result["status"] == "created"
        ingest._dao.update_ingested_tournament_match.assert_not_called()
        ingest._dao.update_match_external_id.assert_not_called()
        assert ingest._dao.create_match.call_args.kwargs["match_id"] == "fest-101"

    def test_a_league_message_still_takes_a_hit_with_a_different_source_id(self, ingest):
        # Unchanged from before SB-1747, deliberately: creating instead would
        # collide on unique_manual_match, retry three times and lose the match
        # on every scrape. Only tournament messages make the check above.
        other = dict(TestIngestCorrectsAnExistingMatch.EXISTING, match_id="kitman-0", match_date=MATCH["match_date"])
        ingest._dao.get_match_by_teams_and_date.return_value = dict(other)

        assert _run(ingest)["status"] == "skipped"
        ingest._dao.create_match.assert_not_called()
        ingest._dao.update_match_external_id.assert_not_called()

        ingest._dao.get_match_by_teams_and_date.return_value = dict(other)
        result = _run(ingest, home_score=2, away_score=1, match_status="completed")

        assert (result["status"], result["db_id"]) == ("updated", 4060)
        payload = ingest._dao.client.table("matches").update.call_args[0][0]
        assert (payload["home_score"], payload["away_score"]) == (2, 1)
        ingest._dao.create_match.assert_not_called()
        ingest._dao.update_match_external_id.assert_not_called()

    def test_a_manual_league_row_is_not_adopted_by_a_tournament_message(self, ingest):
        league_row = dict(
            TestIngestCorrectsAnExistingMatch.EXISTING,
            source="manual",
            match_id=None,
            tournament_id=None,
            match_date=MATCH["match_date"],
        )
        ingest._dao.get_match_by_teams_and_date.return_value = league_row

        result = _run_tournament(ingest, home_score=2, away_score=1, match_status="completed")

        assert result["status"] == "created" and result["db_id"] == 4242
        ingest._dao.update_match_external_id.assert_not_called()
        ingest._dao.update_ingested_tournament_match.assert_not_called()
        ingest._dao.client.table("matches").update.assert_not_called()
        created = ingest._dao.create_match.call_args.kwargs
        assert created["match_id"] == "fest-101"
        assert created["tournament_id"] == 12 and created["division_id"] is None
        ingest._ingest_failures_dao.record.assert_not_called()

    def test_a_manual_row_on_another_tournament_is_not_adopted(self, ingest):
        ingest._dao.get_match_by_teams_and_date.return_value = _tournament_row(
            source="manual", match_id=None, tournament_id=11
        )

        result = _run_tournament(ingest)

        assert result["status"] == "created"
        ingest._dao.update_match_external_id.assert_not_called()
        ingest._dao.update_ingested_tournament_match.assert_not_called()
        assert ingest._dao.create_match.call_args.kwargs["tournament_id"] == 12

    def test_an_adopted_row_keeps_what_a_person_typed_and_has_its_nulls_filled(self, ingest):
        ingest._dao.get_match_by_teams_and_date.return_value = _tournament_row(
            source="manual",
            match_id=None,
            tournament_group="Group A",
            tournament_round=None,
            tournament_round_order=None,
        )
        ingest._dao.update_match_external_id.return_value = True

        result = _run_tournament(ingest, home_score=2, away_score=1, match_status="completed")

        assert result["status"] == "updated" and result["db_id"] == 900
        ingest._dao.create_match.assert_not_called()
        ingest._dao.update_match_external_id.assert_called_once_with(match_id=900, external_match_id="fest-101")
        payload = ingest._dao.update_ingested_tournament_match.call_args.args[1]
        assert "tournament_group" not in payload
        assert payload["tournament_round"] == "group_stage"
        assert payload["tournament_round_order"] == 3
        assert (payload["home_score"], payload["away_score"]) == (2, 1)

    def test_an_adopted_row_with_every_column_typed_has_none_overwritten(self, ingest):
        ingest._dao.get_match_by_teams_and_date.return_value = _tournament_row(
            source="manual",
            match_id=None,
            tournament_group="Group A",
            tournament_round="final",
            tournament_round_order=9,
        )
        ingest._dao.update_match_external_id.return_value = True

        assert _run_tournament(ingest)["status"] == "skipped"
        ingest._dao.update_ingested_tournament_match.assert_not_called()

    def test_a_manual_match_with_no_source_id_is_adopted_not_duplicated(self, ingest):
        ingest._dao.get_match_by_teams_and_date.return_value = _tournament_row(
            source="manual", match_id=None, tournament_group=None, tournament_round=None, tournament_round_order=None
        )
        ingest._dao.update_match_external_id.return_value = True

        result = _run_tournament(ingest)

        assert result["status"] == "updated"
        ingest._dao.create_match.assert_not_called()
        ingest._dao.update_match_external_id.assert_called_once_with(match_id=900, external_match_id="fest-101")
        # Adoption hands the filing to the feed, so the group lands too.
        payload = ingest._dao.update_ingested_tournament_match.call_args.args[1]
        assert payload["tournament_group"] == "HD · A"

    def test_a_message_with_no_source_id_still_matches_on_teams_and_date(self, ingest):
        # Unchanged league behaviour: nothing to compare, so the hit stands.
        existing = dict(TestIngestCorrectsAnExistingMatch.EXISTING, match_id="kitman-0", match_date=MATCH["match_date"])
        ingest._dao.get_match_by_teams_and_date.return_value = existing

        assert _run(ingest, external_match_id=None)["status"] == "skipped"
        ingest._dao.create_match.assert_not_called()

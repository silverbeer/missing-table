"""Unit tests for Celery match task helper methods.

Tests _build_scheduled_kickoff(), _check_needs_update(), and
_update_match_scores() on the DatabaseTask class without requiring
a live database or Celery broker.
"""

from unittest.mock import MagicMock

import pytest

from celery_tasks.match_tasks import DatabaseTask


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

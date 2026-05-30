"""Unit tests for the score-change detector (SB-77).

`is_new_final_score(before, after)` decides whether an admin/skill match write
should fan a 'fulltime' notification out to followers. The contract:

  - fire when a complete score newly appears or actually changes, on a match
    that is completed (or whose status is unspecified, e.g. a raw tournament
    row), and
  - stay silent on metadata-only edits, idempotent re-submissions, partial
    scores, and non-completed statuses.
"""

from __future__ import annotations

import pytest

from notifications.score_change import is_new_final_score

pytestmark = [pytest.mark.unit, pytest.mark.backend]


def _row(home=None, away=None, status=None, **extra):
    """Build a match-like row. `status` is written under match_status (raw row
    shape); pass status_key='status' to use the flattened-read alias instead."""
    row: dict = {"id": 999, **extra}
    if home is not None:
        row["home_score"] = home
    if away is not None:
        row["away_score"] = away
    if status is not None:
        row["match_status"] = status
    return row


class TestFires:
    def test_scheduled_to_completed_score_fires(self):
        before = _row(status="scheduled")  # no score yet
        after = _row(home=0, away=1, status="completed")
        assert is_new_final_score(before, after) is True

    def test_create_with_completed_score_fires(self):
        # before is None for a create
        after = _row(home=2, away=2, status="completed")
        assert is_new_final_score(None, after) is True

    def test_score_correction_fires(self):
        before = _row(home=1, away=0, status="completed")
        after = _row(home=2, away=0, status="completed")
        assert is_new_final_score(before, after) is True

    def test_same_score_newly_completed_fires(self):
        # Score was already present but match only just got marked completed.
        before = _row(home=1, away=1, status="in_progress")
        after = _row(home=1, away=1, status="completed")
        assert is_new_final_score(before, after) is True

    def test_status_absent_but_score_appears_fires(self):
        # Raw tournament rows may omit status entirely — the score-pair change
        # still gates the notification.
        before = _row()  # nothing
        after = _row(home=3, away=1)
        assert is_new_final_score(before, after) is True

    def test_flattened_status_alias_fires(self):
        # get_match_by_id exposes status under "status", not "match_status".
        before = {"id": 1, "home_score": None, "away_score": None, "status": "scheduled"}
        after = {"id": 1, "home_score": 4, "away_score": 0, "status": "completed"}
        assert is_new_final_score(before, after) is True


class TestSilent:
    def test_identical_score_is_noop(self):
        before = _row(home=0, away=1, status="completed")
        after = _row(home=0, away=1, status="completed")
        assert is_new_final_score(before, after) is False

    def test_metadata_only_edit_is_noop(self):
        # Same score, only round/group changed.
        before = _row(home=0, away=1, status="completed", tournament_round="semifinal")
        after = _row(home=0, away=1, status="completed", tournament_round="final")
        assert is_new_final_score(before, after) is False

    def test_no_score_yet_is_noop(self):
        before = _row(status="scheduled")
        after = _row(status="scheduled")
        assert is_new_final_score(before, after) is False

    def test_partial_score_is_noop(self):
        # Only one side set — not a complete result.
        before = _row(status="scheduled")
        after = _row(home=2, status="scheduled")
        assert is_new_final_score(before, after) is False

    def test_non_completed_status_with_score_is_noop(self):
        # Score present but match explicitly not completed (e.g. live in_progress);
        # the live endpoints own that notification, not this path.
        before = _row(status="scheduled")
        after = _row(home=1, away=0, status="in_progress")
        assert is_new_final_score(before, after) is False

    def test_after_none_is_noop(self):
        assert is_new_final_score(_row(home=1, away=0), None) is False

    def test_metadata_edit_on_unscored_match_is_noop(self):
        before = _row(status="scheduled", tournament_round_order=0)
        after = _row(status="scheduled", tournament_round_order=1)
        assert is_new_final_score(before, after) is False

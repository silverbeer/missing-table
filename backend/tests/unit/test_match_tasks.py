"""Unit tests for Celery match task helper methods.

Tests _build_scheduled_kickoff(), _check_needs_update(), and
_update_match_scores() on the DatabaseTask class without requiring
a live database or Celery broker.
"""

from unittest.mock import MagicMock, patch

import pytest

from celery_tasks.exceptions import UnresolvedNameError
from celery_tasks.match_tasks import DatabaseTask, process_match_data

MATCH_TYPES = [
    {"id": 1, "name": "League", "counts_for_qualification": True},
    {"id": 5, "name": "Flex", "counts_for_qualification": True},
    {"id": 3, "name": "Friendly", "counts_for_qualification": False},
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
    task._match_type_dao = None
    task._ingest_failures_dao = None
    task._resolved_names = set()
    task._ensured_mappings = set()


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

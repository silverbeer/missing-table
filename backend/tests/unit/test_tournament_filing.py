"""How an ingested match is filed under a tournament (SB-1747).

Pure functions, no mocks. The default message is a scraped tournament fixture
with no score: a tournament is published as a schedule first and its results
arrive by rescrape.
"""

import pytest

from celery_tasks.tournament_filing import (
    TournamentFiling,
    TournamentFilingError,
    read_tournament_filing,
    stored_group,
    tournament_changes,
    tournament_filing_errors,
)

pytestmark = pytest.mark.unit

MESSAGE = {
    "home_team": "Bayside FC",
    "away_team": "Sockers FC",
    "match_date": "2026-12-04",
    "season": "2026-2027",
    "age_group": "U15",
    "match_type": "Tournament",
    "external_match_id": "fest-101",
    "tournament_id": 12,
    "competition": "HD Group Play",
    "tournament_group": "A",
    "tournament_round": "group_stage",
    "tournament_round_order": 3,
}

LEAGUE_MESSAGE = {
    "home_team": "Bayside FC",
    "away_team": "Sockers FC",
    "match_date": "2026-12-04",
    "season": "2026-2027",
    "age_group": "U15",
    "match_type": "League",
    "division": "Northeast",
    "external_match_id": "kitman-1",
}


def _message(**overrides):
    return {**MESSAGE, **overrides}


class TestReadTournamentFiling:
    def test_a_league_message_has_no_filing(self):
        assert read_tournament_filing(LEAGUE_MESSAGE) is None

    def test_a_null_tournament_id_is_a_league_message(self):
        assert read_tournament_filing({**LEAGUE_MESSAGE, "tournament_id": None}) is None

    def test_a_tournament_message_is_read_whole(self):
        assert read_tournament_filing(MESSAGE) == TournamentFiling(
            tournament_id=12,
            tournament_group="HD · A",
            tournament_round="group_stage",
            tournament_round_order=3,
            competition="HD Group Play",
        )

    def test_only_the_id_is_needed(self):
        message = {**LEAGUE_MESSAGE, "match_type": "Tournament", "tournament_id": 12}
        del message["division"]
        assert read_tournament_filing(message) == TournamentFiling(tournament_id=12)

    def test_the_filing_is_the_four_tournament_columns(self):
        assert read_tournament_filing(MESSAGE).columns() == {
            "tournament_id": 12,
            "tournament_group": "HD · A",
            "tournament_round": "group_stage",
            "tournament_round_order": 3,
        }

    @pytest.mark.parametrize(
        "field,value",
        [
            ("competition", "HD Group Play"),
            ("tournament_group", "A"),
            ("tournament_round", "group_stage"),
            ("tournament_round_order", 0),
        ],
    )
    def test_a_tournament_field_without_the_id_is_rejected(self, field, value):
        with pytest.raises(TournamentFilingError, match=f"{field} requires tournament_id"):
            read_tournament_filing({**LEAGUE_MESSAGE, field: value})

    @pytest.mark.parametrize("field", ["competition", "tournament_group", "tournament_round"])
    @pytest.mark.parametrize("blank", ["", "   ", None])
    def test_a_blank_tournament_field_on_a_league_message_is_absent(self, field, blank):
        assert read_tournament_filing({**LEAGUE_MESSAGE, field: blank}) is None

    @pytest.mark.parametrize("bad", [0, -1, "12", 1.5, True])
    def test_the_id_is_a_positive_integer(self, bad):
        with pytest.raises(TournamentFilingError, match="tournament_id must be an integer of 1 or more"):
            read_tournament_filing(_message(tournament_id=bad))

    @pytest.mark.parametrize("bad", [-1, "3", 1.5, False])
    def test_the_round_order_is_a_non_negative_integer(self, bad):
        with pytest.raises(TournamentFilingError, match="tournament_round_order must be an integer of 0 or more"):
            read_tournament_filing(_message(tournament_round_order=bad))

    def test_round_order_zero_is_a_value_not_an_absence(self):
        assert read_tournament_filing(_message(tournament_round_order=0)).tournament_round_order == 0

    def test_round_order_may_be_absent(self):
        assert read_tournament_filing(_message(tournament_round_order=None)).tournament_round_order is None

    @pytest.mark.parametrize(
        "bad",
        ["Group Stage", "group-stage", "GROUP_STAGE", "_final", "final_", "semi__final", "1st_round", "x" * 41, 7],
    )
    def test_a_round_must_be_a_lowercase_snake_case_key(self, bad):
        with pytest.raises(TournamentFilingError, match="tournament_round must be a lowercase snake_case key"):
            read_tournament_filing(_message(tournament_round=bad))

    def test_a_round_mt_does_not_know_is_accepted(self):
        # Shape, not membership: a feed that grows a round should land its
        # matches. The task logs the unknown key; this module does not reject.
        assert read_tournament_filing(_message(tournament_round="play_in_2")).tournament_round == "play_in_2"

    @pytest.mark.parametrize("blank", ["", "  ", None])
    def test_a_blank_round_is_absent(self, blank):
        assert read_tournament_filing(_message(tournament_round=blank)).tournament_round is None

    @pytest.mark.parametrize("missing", [None, "", "  "])
    def test_a_tournament_message_needs_the_source_match_id(self, missing):
        with pytest.raises(TournamentFilingError, match="external_match_id is required when tournament_id is set"):
            read_tournament_filing(_message(external_match_id=missing))

    @pytest.mark.parametrize("match_type", ["League", "Flex", None, ""])
    def test_a_tournament_message_must_be_a_tournament_match(self, match_type):
        with pytest.raises(TournamentFilingError, match="match_type must be 'Tournament'"):
            read_tournament_filing(_message(match_type=match_type))

    def test_the_match_type_is_compared_without_case(self):
        assert read_tournament_filing(_message(match_type="tournament")) is not None

    def test_a_tournament_message_carries_no_division(self):
        with pytest.raises(TournamentFilingError, match="division must be omitted"):
            read_tournament_filing(_message(division="Northeast"))

    @pytest.mark.parametrize("field", ["competition", "tournament_group"])
    def test_the_raw_labels_are_strings(self, field):
        with pytest.raises(TournamentFilingError, match=f"{field} must be a string"):
            read_tournament_filing(_message(**{field: 4}))

    def test_a_group_the_format_rejects_is_an_error_not_a_crash(self):
        # No competition, so the label would be stored as a legacy group — and
        # this one would split back into a division it never had.
        with pytest.raises(TournamentFilingError, match="tournament group cannot be stored"):
            read_tournament_filing(_message(competition=None, tournament_group="HD · A"))

    def test_every_problem_is_reported_at_once(self):
        with pytest.raises(TournamentFilingError) as raised:
            read_tournament_filing(_message(tournament_id=0, external_match_id=None, tournament_round="Final"))
        assert len(raised.value.errors) == 3

    def test_the_error_list_is_empty_for_a_good_message(self):
        assert tournament_filing_errors(MESSAGE) == []
        assert tournament_filing_errors(LEAGUE_MESSAGE) == []


# (competition, group, round) -> stored tournament_group
STORED_GROUP_CASES = [
    # Group stage: namespaced by division, or by the whole competition.
    ("HD Group Play", "A", "group_stage", "HD · A"),
    ("AD Group Play", "A", "group_stage", "AD · A"),
    ("GA Cup Qualifier", "NEXT Pro", "group_stage", "GA Cup Qualifier · NEXT Pro"),
    ("hd Group Play", "A", "group_stage", "HD · A"),
    ("HD", "A", "group_stage", "HD · A"),
    # No competition at all: the raw group, unchanged — a legacy group.
    (None, "Bracket A", "group_stage", "Bracket A"),
    ("", "Bracket A", "group_stage", "Bracket A"),
    ("   ", "Bracket A", "group_stage", "Bracket A"),
    # A group stage with no group label has no opinion: composing the
    # namespace alone ("HD") would overwrite a stored "HD · A".
    ("HD Group Play", None, "group_stage", None),
    ("GA Cup Qualifier", "  ", "group_stage", None),
    (None, None, "group_stage", None),
    # Any other round: the competition, with HD/AD as its division.
    ("HD Showcase", "anything", "showcase", "HD · Showcase"),
    ("HD Showcase", None, "showcase", "HD · Showcase"),
    ("HD Group Play", "Playoffs", "placement_final", "HD · Group Play"),
    ("AD Group Play", "Playoffs", "placement_final", "AD · Group Play"),
    ("ad  Showcase", "x", "showcase", "AD · Showcase"),
    ("HD", "Playoffs", "final", "HD"),
    ("GA Cup Qualifier", "NEXT Pro", "final", "GA Cup Qualifier"),
    ("Pro Player Pathway", None, "showcase", "Pro Player Pathway"),
    (None, "Bracket A", "final", "Bracket A"),
    (None, None, "final", None),
    # No round at all is no opinion: without it the group label cannot be
    # told from a "Playoffs" that is not a group.
    ("HD Showcase", "A", None, None),
    ("HD Group Play", "A", None, None),
    (None, "Bracket A", None, None),
    ("HD Group Play", "A", "", None),
    ("HD Group Play", "A", "   ", None),
    (None, None, None, None),
    # Any other round with neither a competition nor a group.
    ("  ", "", "showcase", None),
    # Only a whole first word is a division.
    ("HDX Group Play", "A", "group_stage", "HDX Group Play · A"),
    ("Showcase HD", "A", "showcase", "Showcase HD"),
    # Parts are trimmed.
    ("  HD Group Play  ", "  A  ", "group_stage", "HD · A"),
    # Runs of whitespace inside the competition collapse to one space; its
    # letter case is left alone.
    ("HD  Group  Play", "Playoffs", "placement_final", "HD · Group Play"),
    ("HD\t Group\u00a0\u00a0Play", "Playoffs", "placement_final", "HD · Group Play"),
    ("GA  Cup   Qualifier", "NEXT Pro", "group_stage", "GA Cup Qualifier · NEXT Pro"),
    ("Pro  player   PATHWAY", None, "showcase", "Pro player PATHWAY"),
    # The group label is not a competition: its inner spacing is as sent.
    ("HD Group Play", "North  East", "group_stage", "HD · North  East"),
]


class TestStoredGroup:
    @pytest.mark.parametrize("competition,group,round_key,expected", STORED_GROUP_CASES)
    def test_the_stored_value(self, competition, group, round_key, expected):
        assert stored_group(competition, group, round_key) == expected

    def test_inner_whitespace_does_not_change_the_stored_bytes(self):
        spaced = stored_group("HD  Group  Play", "Playoffs", "placement_final")
        assert spaced == stored_group("HD Group Play", "Playoffs", "placement_final")
        assert spaced.encode() == "HD · Group Play".encode()

    def test_the_two_fest_divisions_stay_apart(self):
        assert stored_group("HD Group Play", "A", "group_stage") != stored_group("AD Group Play", "A", "group_stage")

    @pytest.mark.parametrize(
        "competition,group,round_key",
        [
            # A namespace that contains the separator would split back wrongly.
            ("Cup · East", "A", "group_stage"),
            ("Cup · East", "A", "final"),
            # So would a bare label that contains it.
            (None, "HD · A", "group_stage"),
            (None, "HD · A", "final"),
        ],
    )
    def test_a_value_the_frozen_format_rejects_raises(self, competition, group, round_key):
        with pytest.raises(ValueError):
            stored_group(competition, group, round_key)


ROW = {
    "id": 900,
    "tournament_id": 12,
    "tournament_group": "HD · A",
    "tournament_round": "group_stage",
    "tournament_round_order": 3,
}
FILING = TournamentFiling(
    tournament_id=12, tournament_group="HD · A", tournament_round="group_stage", tournament_round_order=3
)


class TestTournamentChanges:
    def test_identical_values_change_nothing(self):
        assert tournament_changes(ROW, FILING) == {}

    def test_no_filing_changes_nothing(self):
        assert tournament_changes(ROW, None) == {}

    def test_a_null_incoming_value_never_clears_a_stored_one(self):
        assert tournament_changes(ROW, TournamentFiling(tournament_id=12)) == {}

    def test_only_the_columns_that_differ_are_written(self):
        moved = TournamentFiling(
            tournament_id=12, tournament_group="HD · B", tournament_round="group_stage", tournament_round_order=3
        )
        assert tournament_changes(ROW, moved) == {"tournament_group": "HD · B"}

    def test_a_league_row_is_filed_whole(self):
        row = {"id": 900, "tournament_id": None, "tournament_group": None, "tournament_round": None}
        assert tournament_changes(row, FILING) == FILING.columns()

    def test_a_row_missing_the_columns_is_treated_as_unfiled(self):
        assert tournament_changes({"id": 900}, FILING) == FILING.columns()

    def test_round_order_zero_is_written(self):
        zero = TournamentFiling(tournament_id=12, tournament_round_order=0)
        assert tournament_changes(ROW, zero) == {"tournament_round_order": 0}

    # A stored "HD · A" in the group stage, and a rescrape that lost one of the
    # three fields the group is composed from. Ignoring the gap would compose
    # "HD", "HD · Group Play" and "A" — each a different non-null string.
    @pytest.mark.parametrize(
        "omitted",
        [
            {"tournament_group": None},
            {"tournament_round": None},
            {"competition": None},
            {"competition": None, "tournament_group": None},
            {"competition": None, "tournament_group": None, "tournament_round": None},
        ],
    )
    def test_a_partial_message_leaves_the_stored_group_alone(self, omitted):
        filing = read_tournament_filing(_message(**omitted))
        assert tournament_changes(ROW, filing) == {}

    def test_a_partial_message_still_moves_the_round_order(self):
        filing = read_tournament_filing(_message(tournament_group=None, tournament_round_order=4))
        assert tournament_changes(ROW, filing) == {"tournament_round_order": 4}

    @pytest.mark.parametrize("bare", ["A", "Bracket A", "HD"])
    def test_a_namespaced_group_is_never_replaced_by_a_bare_one(self, bare):
        filing = TournamentFiling(tournament_id=12, tournament_group=bare)
        assert tournament_changes(ROW, filing) == {}

    def test_a_namespaced_group_is_replaced_by_another_namespaced_one(self):
        filing = TournamentFiling(tournament_id=12, tournament_group="AD · A")
        assert tournament_changes(ROW, filing) == {"tournament_group": "AD · A"}

    def test_a_bare_group_is_replaced_by_either_kind(self):
        row = {**ROW, "tournament_group": "Bracket A"}
        assert tournament_changes(row, TournamentFiling(tournament_id=12, tournament_group="Bracket B")) == {
            "tournament_group": "Bracket B"
        }
        assert tournament_changes(row, TournamentFiling(tournament_id=12, tournament_group="HD · A")) == {
            "tournament_group": "HD · A"
        }

    def test_fill_only_writes_nulls_and_keeps_what_is_there(self):
        row = {"id": 900, "tournament_id": 12, "tournament_group": "Group A", "tournament_round": None}
        assert tournament_changes(row, FILING, fill_only=True) == {
            "tournament_round": "group_stage",
            "tournament_round_order": 3,
        }

    def test_fill_only_keeps_a_stored_zero_round_order(self):
        row = {**ROW, "tournament_round_order": 0}
        assert tournament_changes(row, FILING, fill_only=True) == {}

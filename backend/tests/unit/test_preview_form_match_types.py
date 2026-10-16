"""Which competitions a match preview draws from (SB-1346, SB-1347).

A League match between TSF Academy and IFA listed IFA's tournament results in
its form guide. Form for a qualifying match should be qualifying form, and
common opponents are always compared on League and Flex results only.
"""

from dao.match_dao import form_match_type_ids, qualifying_match_type_ids

LEAGUE, TOURNAMENT, FRIENDLY, FLEX = 1, 2, 3, 4

MATCH_TYPES = [
    {"id": LEAGUE, "counts_for_qualification": True},
    {"id": TOURNAMENT, "counts_for_qualification": False},
    {"id": FRIENDLY, "counts_for_qualification": None},
    {"id": FLEX, "counts_for_qualification": True},
]


def test_a_league_match_draws_form_from_league_and_flex_only():
    assert form_match_type_ids(MATCH_TYPES, LEAGUE) == [LEAGUE, FLEX]


def test_a_flex_match_draws_form_from_league_and_flex_only():
    assert form_match_type_ids(MATCH_TYPES, FLEX) == [LEAGUE, FLEX]


def test_a_tournament_match_keeps_every_competition():
    assert form_match_type_ids(MATCH_TYPES, TOURNAMENT) is None


def test_an_unflagged_type_keeps_every_competition():
    assert form_match_type_ids(MATCH_TYPES, FRIENDLY) is None


def test_no_match_type_keeps_every_competition():
    assert form_match_type_ids(MATCH_TYPES, None) is None


def test_the_qualifying_set_comes_from_the_flag_not_the_name():
    # A newly flagged competition joins without a code change (SB-849).
    types = [*MATCH_TYPES, {"id": 9, "counts_for_qualification": True}]
    assert form_match_type_ids(types, LEAGUE) == [LEAGUE, FLEX, 9]


def test_common_opponents_compare_league_and_flex_only():
    assert qualifying_match_type_ids(MATCH_TYPES) == [LEAGUE, FLEX]


def test_no_flagged_type_falls_back_to_every_competition():
    # An empty filter would blank the preview; a failed lookup must not.
    unflagged = [{"id": LEAGUE, "counts_for_qualification": False}]
    assert qualifying_match_type_ids(unflagged) is None
    assert qualifying_match_type_ids([]) is None
    assert form_match_type_ids([], LEAGUE) is None

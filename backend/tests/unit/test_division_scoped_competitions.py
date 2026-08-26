"""Competitions whose standings need a division (SB-833).

`get_league_table` filters on division, so a League or Flex match with no
division_id exists in the database and appears in no table at all. That is the
same silent hole SB-830 closed on the ingest path; this closes it on the API.

Tournament and Friendly are the counter-case and matter just as much: they
legitimately carry no division, and rejecting them would break every manually
entered showcase fixture.
"""

import pytest
from fastapi import HTTPException

from app import DIVISION_SCOPED_MATCH_TYPES, require_division_for_competition


@pytest.mark.unit
class TestDivisionScopedCompetitions:
    @pytest.mark.parametrize("name", ["League", "Flex"])
    def test_a_division_scoped_competition_without_a_division_is_rejected(self, name):
        with pytest.raises(HTTPException) as exc:
            require_division_for_competition({"name": name}, None)
        assert exc.value.status_code == 422
        # The message names the competition — "required for Flex matches" is
        # actionable in a way that "required for League matches" is not, when
        # the caller was posting Flex.
        assert name in exc.value.detail

    @pytest.mark.parametrize("name", ["League", "Flex"])
    def test_a_division_scoped_competition_with_a_division_passes(self, name):
        require_division_for_competition({"name": name}, 1)

    @pytest.mark.parametrize("name", ["Tournament", "Friendly", "Playoff"])
    def test_other_competitions_may_carry_no_division(self, name):
        # Showcases and friendlies genuinely have none. Rejecting these would
        # break every manually entered tournament fixture.
        require_division_for_competition({"name": name}, None)

    def test_an_unknown_match_type_is_not_this_functions_problem(self):
        # match_type_dao returns None for an id that does not exist. Raising a
        # division error there would misreport the actual fault.
        require_division_for_competition(None, None)

    def test_flex_is_division_scoped(self):
        # The reason SB-833 exists: Flex standings group by Flex bracket, so a
        # Flex match without one is invisible exactly like a League match.
        assert "Flex" in DIVISION_SCOPED_MATCH_TYPES
        assert "League" in DIVISION_SCOPED_MATCH_TYPES

    @pytest.mark.parametrize("name", ["Tournament", "Friendly", "Playoff"])
    def test_non_division_competitions_stay_out_of_the_set(self, name):
        assert name not in DIVISION_SCOPED_MATCH_TYPES

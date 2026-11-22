"""Which side of the pyramid a team is on, and which candidate a name means (SB-1748).

Pure rules, no database. A Fest message says "Academy"; the team found by
name is the club's Homegrown one. Taking it files the match on the wrong
team's history, silently — so every case here either picks the one team on
the hinted side or refuses.
"""

from __future__ import annotations

from dao.team_sides import (
    AMBIGUOUS,
    MISSING,
    RESOLVED,
    WRONG_SIDE,
    Candidate,
    Resolution,
    classify,
    league_named,
    sides_at_age,
    team_sides,
    top_level_league,
)

HOMEGROWN, ACADEMY, FLEX, FUTSAL = 1, 2, 290, 34
LEAGUES = {
    HOMEGROWN: {"id": HOMEGROWN, "name": "Homegrown", "parent_league_id": None},
    ACADEMY: {"id": ACADEMY, "name": "Academy", "parent_league_id": None},
    FLEX: {"id": FLEX, "name": "Flex", "parent_league_id": HOMEGROWN},
    FUTSAL: {"id": FUTSAL, "name": "Kick Futsal", "parent_league_id": None},
}
U15, U16 = 3, 4


def _candidate(team_id: int, *sides: str) -> Candidate:
    return Candidate(team_id=team_id, sides=frozenset(sides))


def _at_age(team_id: int, *sides: str) -> Candidate:
    """A candidate whose sides were read from its registrations at the message's age group."""
    return Candidate(team_id=team_id, sides=frozenset(sides), sides_at_age=frozenset(sides))


class TestTopLevelLeague:
    def test_a_top_level_league_is_itself(self):
        assert top_level_league(ACADEMY, LEAGUES) == "Academy"

    def test_flex_folds_into_homegrown(self):
        assert top_level_league(FLEX, LEAGUES) == "Homegrown"

    def test_no_league_and_an_unknown_league_have_no_side(self):
        assert top_level_league(None, LEAGUES) is None
        assert top_level_league(999, LEAGUES) is None

    def test_a_parent_the_map_does_not_have_stops_the_walk(self):
        leagues = {5: {"id": 5, "name": "Orphan", "parent_league_id": 77}}
        assert top_level_league(5, leagues) == "Orphan"

    def test_a_parent_loop_ends(self):
        leagues = {
            1: {"id": 1, "name": "A", "parent_league_id": 2},
            2: {"id": 2, "name": "B", "parent_league_id": 1},
        }
        assert top_level_league(1, leagues) in {"A", "B"}


class TestTeamSides:
    def test_the_side_is_the_league_of_its_division_at_that_age(self):
        assert team_sides([(U15, ACADEMY)], None, U15, LEAGUES) == {"Academy"}

    def test_a_flex_only_mapping_counts_as_homegrown(self):
        assert team_sides([(U15, FLEX)], None, U15, LEAGUES) == {"Homegrown"}

    def test_homegrown_and_flex_at_one_age_are_one_side(self):
        assert team_sides([(U15, HOMEGROWN), (U15, FLEX)], FLEX, U15, LEAGUES) == {"Homegrown"}

    def test_mappings_on_both_sides_at_that_age_give_both(self):
        assert team_sides([(U15, HOMEGROWN), (U15, ACADEMY)], None, U15, LEAGUES) == {"Homegrown", "Academy"}

    def test_the_age_asked_about_wins_over_other_ages_and_the_team_league(self):
        # Academy at U15; Homegrown at U16 and on teams.league_id. At U15 it
        # is an Academy team, whatever it is elsewhere.
        assert team_sides([(U15, ACADEMY), (U16, HOMEGROWN)], HOMEGROWN, U15, LEAGUES) == {"Academy"}

    def test_no_mapping_at_that_age_falls_back_to_other_ages(self):
        assert team_sides([(U16, ACADEMY)], None, U15, LEAGUES) == {"Academy"}

    def test_the_fallback_adds_the_teams_own_league(self):
        assert team_sides([(U16, ACADEMY)], HOMEGROWN, U15, LEAGUES) == {"Academy", "Homegrown"}

    def test_no_mappings_at_all_falls_back_to_the_teams_league(self):
        assert team_sides([], FLEX, U15, LEAGUES) == {"Homegrown"}

    def test_a_mapping_with_no_division_says_nothing(self):
        assert team_sides([(U15, None)], ACADEMY, U15, LEAGUES) == {"Academy"}

    def test_no_mappings_and_no_league_is_no_side(self):
        assert team_sides([], None, U15, LEAGUES) == frozenset()

    def test_an_unknown_age_group_uses_every_age(self):
        assert team_sides([(U15, ACADEMY)], None, None, LEAGUES) == {"Academy"}


class TestSidesAtAge:
    def test_only_registrations_at_that_age_count(self):
        assert sides_at_age([(U15, ACADEMY), (U16, HOMEGROWN)], U15, LEAGUES) == {"Academy"}

    def test_both_sides_at_one_age_are_both(self):
        assert sides_at_age([(U15, HOMEGROWN), (U15, ACADEMY)], U15, LEAGUES) == {"Homegrown", "Academy"}

    def test_homegrown_and_flex_at_one_age_are_one_side(self):
        assert sides_at_age([(U15, HOMEGROWN), (U15, FLEX)], U15, LEAGUES) == {"Homegrown"}

    def test_no_registration_at_that_age_is_empty_not_the_fallback(self):
        assert sides_at_age([(U16, ACADEMY)], U15, LEAGUES) == frozenset()

    def test_an_unknown_age_group_is_empty(self):
        assert sides_at_age([(U15, ACADEMY)], None, LEAGUES) == frozenset()


class TestLeagueNamed:
    def test_a_league_is_found_by_its_whole_name_without_case_or_padding(self):
        assert league_named("Academy", LEAGUES) == ACADEMY
        assert league_named("  hOMEGROWN ", LEAGUES) == HOMEGROWN
        assert league_named("Flex", LEAGUES) == FLEX

    def test_an_abbreviation_a_longer_name_and_a_typo_name_nothing(self):
        for hint in ("HD", "Homegrown Division", "Homegrwon", "Home%", "_cademy"):
            assert league_named(hint, LEAGUES) is None

    def test_no_hint_names_nothing(self):
        assert league_named(None, LEAGUES) is None
        assert league_named("   ", LEAGUES) is None


class TestClassifyWithAHint:
    def test_the_candidate_on_the_hinted_side_is_the_answer(self):
        candidates = [_candidate(7, "Homegrown"), _candidate(9, "Academy")]
        assert classify(candidates, "Academy") == Resolution(RESOLVED, team_id=9)
        assert classify(candidates, "Homegrown") == Resolution(RESOLVED, team_id=7)

    def test_a_name_only_on_the_other_side_is_refused_not_taken(self):
        result = classify([_candidate(7, "Homegrown")], "Academy")
        assert result == Resolution(WRONG_SIDE, reason="wrong side: exists as Homegrown")
        assert result.team_id is None

    def test_two_on_the_hinted_side_are_ambiguous(self):
        result = classify([_candidate(9, "Academy"), _candidate(7, "Academy"), _candidate(3, "Homegrown")], "Academy")
        assert result == Resolution(AMBIGUOUS, reason="ambiguous: team ids 7, 9")

    def test_a_team_with_no_side_cannot_be_confirmed(self):
        result = classify([_candidate(7)], "Academy")
        assert result == Resolution(WRONG_SIDE, reason="wrong side: team has no league or division registration")

    def test_a_league_nobody_plays_in_matches_nothing(self):
        assert classify([_candidate(7, "Homegrown")], "MLS NEXT Pro").status == WRONG_SIDE

    def test_the_hint_is_compared_without_case_or_padding(self):
        assert classify([_candidate(9, "Academy")], " academy ").team_id == 9

    def test_the_same_team_twice_is_one_candidate(self):
        assert classify([_candidate(9, "Academy"), _candidate(9, "Academy")], "Academy").team_id == 9

    def test_no_candidates_is_missing(self):
        assert classify([], "Academy") == Resolution(MISSING)


class TestATeamOnBothSidesAtTheMessagesAge:
    """Registered Academy and Homegrown at one age group: it cannot answer a hint.

    Four production teams are, the residue of old mis-filing. Taking one for
    an Academy message is the Academy-fixture-on-a-Homegrown-team fault itself.
    """

    REASON = "ambiguous: team 17 is registered as both Academy and Homegrown at this age group"

    def test_it_is_ambiguous_under_the_academy_hint(self):
        result = classify([_at_age(17, "Homegrown", "Academy")], "Academy")
        assert result == Resolution(AMBIGUOUS, reason=self.REASON)
        assert result.team_id is None

    def test_it_is_ambiguous_under_the_homegrown_hint(self):
        assert classify([_at_age(17, "Homegrown", "Academy")], "Homegrown") == Resolution(AMBIGUOUS, reason=self.REASON)

    def test_the_hint_is_still_compared_without_case_or_padding(self):
        assert classify([_at_age(17, "Homegrown", "Academy")], " academy ").status == AMBIGUOUS

    def test_with_no_hint_the_single_candidate_still_resolves(self):
        assert classify([_at_age(17, "Homegrown", "Academy")], None) == Resolution(RESOLVED, team_id=17)
        assert classify([_at_age(17, "Homegrown", "Academy")], "") == Resolution(RESOLVED, team_id=17)

    def test_a_team_cleanly_on_the_hinted_side_wins_over_it(self):
        candidates = [_at_age(17, "Homegrown", "Academy"), _at_age(9, "Academy")]
        assert classify(candidates, "Academy") == Resolution(RESOLVED, team_id=9)

    def test_next_to_a_team_on_the_other_side_only_it_is_still_ambiguous(self):
        # The Homegrown-only team is no answer to an Academy message, and the
        # both-sides team is not a clean one.
        candidates = [_at_age(17, "Homegrown", "Academy"), _at_age(7, "Homegrown")]
        assert classify(candidates, "Academy") == Resolution(AMBIGUOUS, reason=self.REASON)
        # ...while the Homegrown message has a clean answer.
        assert classify(candidates, "Homegrown") == Resolution(RESOLVED, team_id=7)

    def test_two_clean_teams_beside_it_are_ambiguous_between_themselves(self):
        candidates = [_at_age(17, "Homegrown", "Academy"), _at_age(9, "Academy"), _at_age(4, "Academy")]
        assert classify(candidates, "Academy") == Resolution(AMBIGUOUS, reason="ambiguous: team ids 4, 9")

    def test_two_such_teams_are_both_named(self):
        candidates = [_at_age(21, "Homegrown", "Academy"), _at_age(17, "Homegrown", "Academy")]
        assert classify(candidates, "Academy").reason == (
            "ambiguous: team 17 is registered as both Academy and Homegrown at this age group; "
            "team 21 is registered as both Academy and Homegrown at this age group"
        )

    def test_a_hint_it_is_not_registered_on_is_the_wrong_side(self):
        result = classify([_at_age(17, "Homegrown", "Academy")], "Kick Futsal")
        assert result == Resolution(WRONG_SIDE, reason="wrong side: exists as Academy, Homegrown")

    def test_both_sides_only_through_the_every_age_fallback_still_answers(self):
        # Not registered at the message's age group at all: its sides come
        # from other ages and teams.league_id. The rule above is about the
        # age group the message is for, so this shape is unchanged.
        fallback = [_candidate(7, "Homegrown", "Academy")]
        assert classify(fallback, "Academy").team_id == 7
        assert classify(fallback, "Homegrown").team_id == 7


class TestClassifyWithNoHint:
    def test_a_single_candidate_is_the_answer(self):
        assert classify([_candidate(7, "Homegrown")], None) == Resolution(RESOLVED, team_id=7)

    def test_a_single_candidate_with_no_side_is_still_the_answer(self):
        assert classify([_candidate(7)], "") == Resolution(RESOLVED, team_id=7)

    def test_two_candidates_are_ambiguous(self):
        result = classify([_candidate(7, "Homegrown"), _candidate(9, "Academy")], None)
        assert result == Resolution(AMBIGUOUS, reason="ambiguous: team ids 7, 9")

    def test_no_candidates_is_missing(self):
        assert classify([], None) == Resolution(MISSING)

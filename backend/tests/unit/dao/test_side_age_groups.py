"""Per-side age groups (SB-1444): the pure rules.

A side that plays up stores its own age group; every other side stores NULL,
meaning "same as the match". These rules are what keep the scraper and every
other writer from having to know playing up exists.
"""

import pytest

from dao.side_age_groups import effective_side_age_groups, side_age_group, team_age_group_filter


class TestSideAgeGroup:
    def test_omitted_stores_null(self):
        assert side_age_group(None, 3) is None

    def test_same_as_match_stores_null(self):
        """One spelling of "same age group", so readers never have to treat two alike."""
        assert side_age_group(3, 3) is None

    def test_playing_up_stores_the_side(self):
        assert side_age_group(4, 3) == 4


class TestEffectiveSideAgeGroups:
    def test_null_sides_follow_the_match(self):
        assert effective_side_age_groups({"age_group_id": 3}) == (3, 3)

    def test_playing_up_side_keeps_its_own(self):
        match = {"age_group_id": 3, "home_age_group_id": None, "away_age_group_id": 4}
        assert effective_side_age_groups(match) == (3, 4)


class TestTeamAgeGroupFilter:
    def test_four_branches_cover_both_sides_with_and_without_override(self):
        assert team_age_group_filter(29, 4).split(",and(") == [
            "and(home_team_id.eq.29,home_age_group_id.eq.4)",
            "home_team_id.eq.29,home_age_group_id.is.null,age_group_id.eq.4)",
            "away_team_id.eq.29,away_age_group_id.eq.4)",
            "away_team_id.eq.29,away_age_group_id.is.null,age_group_id.eq.4)",
        ]

    @pytest.mark.parametrize("bad", ["29,away_team_id.eq.1", "1)"])
    def test_ids_are_coerced_so_nothing_is_spliced_into_the_filter(self, bad):
        with pytest.raises(ValueError):
            team_age_group_filter(bad, 4)

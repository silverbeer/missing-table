"""Unit tests for dao/tournament_filters.py (SB-1749).

Pure functions: reading the paging/filter query values and shaping facet rows.
Two rules are pinned throughout — a filter that cannot match is not "no
filter", and unknown is None rather than zero or an empty list.
"""

from __future__ import annotations

import pytest

from dao.tournament_dao import VALID_ROUNDS
from dao.tournament_filters import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    MAX_OFFSET,
    MatchFilters,
    build_age_group_options,
    build_filters_payload,
    build_group_options,
    clamp_limit,
    clamp_offset,
    empty_page,
    parse_age_group_id,
    parse_on_date,
    resolve_match_filters,
    unavailable_filters_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.backend]


def _age(age_group_id, name, matches, on_date=0):
    return {
        "facet": "age_group",
        "age_group_id": age_group_id,
        "age_group_name": name,
        "tournament_group": None,
        "matches": matches,
        "matches_on_date": on_date,
    }


def _group(key, matches):
    return {
        "facet": "group",
        "age_group_id": None,
        "age_group_name": None,
        "tournament_group": key,
        "matches": matches,
        "matches_on_date": None,
    }


class TestClamp:
    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            (None, DEFAULT_LIMIT),
            (1, 1),
            (200, 200),
            (MAX_LIMIT, MAX_LIMIT),
            (MAX_LIMIT + 1, MAX_LIMIT),
            (0, 1),
            (-5, 1),
        ],
    )
    def test_limit(self, given, expected):
        assert clamp_limit(given) == expected

    @pytest.mark.parametrize(
        ("given", "expected"),
        [(None, 0), (0, 0), (400, 400), (-1, 0), (MAX_OFFSET + 1, MAX_OFFSET), (10**30, MAX_OFFSET)],
    )
    def test_offset(self, given, expected):
        assert clamp_offset(given) == expected

    def test_default_limit_is_within_the_cap(self):
        assert 1 <= DEFAULT_LIMIT <= MAX_LIMIT


class TestParseAgeGroupId:
    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_absent_is_no_filter(self, value):
        assert parse_age_group_id(value) == (None, True)

    @pytest.mark.parametrize(("value", "expected"), [("7", 7), (" 7 ", 7), (7, 7)])
    def test_an_id(self, value, expected):
        assert parse_age_group_id(value) == (expected, True)

    @pytest.mark.parametrize("value", ["abc", "7.5", "-1", "0", "1e3", "\u0667", str(2**31), "7;drop"])
    def test_not_an_id_is_invalid_not_absent(self, value):
        assert parse_age_group_id(value) == (None, False)


class TestResolveMatchFilters:
    def test_nothing_given_filters_nothing(self):
        assert resolve_match_filters(None, None, None, VALID_ROUNDS) == MatchFilters()

    def test_all_three(self):
        out = resolve_match_filters("3", "HD · A", "group_stage", VALID_ROUNDS)
        assert out == MatchFilters(age_group_id=3, group="HD · A", round="group_stage", satisfiable=True)

    def test_blank_values_are_not_given(self):
        assert resolve_match_filters("", " ", "", VALID_ROUNDS) == MatchFilters()

    def test_group_is_passed_through_untouched(self):
        # Compared with the stored value exactly; trimming here would make a
        # stored " A" unreachable.
        assert resolve_match_filters(None, " Bracket A", None, VALID_ROUNDS).group == " Bracket A"

    def test_a_bad_age_group_cannot_match(self):
        out = resolve_match_filters("abc", None, None, VALID_ROUNDS)
        assert out.satisfiable is False
        assert out.age_group_id is None

    def test_an_unknown_round_cannot_match(self):
        out = resolve_match_filters("3", None, "quarter-final", VALID_ROUNDS)
        assert out.satisfiable is False

    @pytest.mark.parametrize("round_key", ["showcase", "consolation", "placement_final"])
    def test_the_fest_rounds_are_filterable(self, round_key):
        out = resolve_match_filters(None, None, round_key, VALID_ROUNDS)
        assert out.satisfiable is True
        assert out.round == round_key


class TestParseOnDate:
    def test_a_day(self):
        assert parse_on_date("2026-12-04") == "2026-12-04"

    @pytest.mark.parametrize("value", [None, "", "Dec 4", "2026-13-01", "2026-02-30", "20261204", "2026-12-04T10:00"])
    def test_anything_else_is_none(self, value):
        assert parse_on_date(value) is None


class TestAgeGroupOptions:
    def test_shape_and_natural_order(self):
        rows = [_age(5, "U13", 400), _age(9, "U9", 12), _age(6, "U14", 410)]
        out = build_age_group_options(rows)
        assert [o["name"] for o in out] == ["U9", "U13", "U14"]
        assert out[1] == {"id": 5, "name": "U13", "matches": 400, "matches_on_date": None}

    def test_on_date_count_only_when_a_day_was_asked_for(self):
        rows = [_age(5, "U13", 400, on_date=0), _age(6, "U14", 410, on_date=32)]
        with_day = build_age_group_options(rows, on_date="2026-12-04")
        assert [o["matches_on_date"] for o in with_day] == [0, 32]
        # No day asked: nobody counted, so None — not the function's 0.
        assert [o["matches_on_date"] for o in build_age_group_options(rows)] == [None, None]

    def test_group_rows_and_rows_without_an_age_group_are_ignored(self):
        rows = [_group("HD · A", 6), _age(None, None, 3), _age(5, "U13", 1)]
        assert [o["id"] for o in build_age_group_options(rows)] == [5]


class TestGroupOptions:
    def test_namespaced_groups_split_and_stay_apart(self):
        out = build_group_options([_group("HD · A", 6), _group("AD · A", 5)])
        assert out == [
            {"key": "AD · A", "division": "AD", "label": "A", "matches": 5},
            {"key": "HD · A", "division": "HD", "label": "A", "matches": 6},
        ]

    def test_ordered_by_division_then_label_naturally(self):
        keys = ["HD · B", "AD · 10", "HD · A", "AD · 2", "Bracket A"]
        out = build_group_options([_group(k, 1) for k in keys])
        assert [o["key"] for o in out] == ["AD · 2", "AD · 10", "HD · A", "HD · B", "Bracket A"]

    def test_a_legacy_group_has_no_division(self):
        assert build_group_options([_group("Bracket A", 3)]) == [
            {"key": "Bracket A", "division": None, "label": "Bracket A", "matches": 3}
        ]

    def test_key_is_the_stored_value_exactly(self):
        # The matches endpoint filters on key with eq, so it must not be tidied.
        assert build_group_options([_group("HD ·  A", 2)])[0]["key"] == "HD ·  A"

    def test_blank_groups_and_age_rows_are_ignored(self):
        assert build_group_options([_group("", 4), _group("  ", 4), _group(None, 4), _age(5, "U13", 9)]) == []


class TestPayloads:
    def test_showcase_only_age_group_has_an_empty_group_list(self):
        # U15-U19: showcase and knockout only. The function returns no 'group'
        # rows, and that is a measured "none" — [], not None.
        out = build_filters_payload([_age(7, "U15", 380)])
        assert out == {
            "facets_available": True,
            "age_groups": [{"id": 7, "name": "U15", "matches": 380, "matches_on_date": None}],
            "groups": [],
        }

    def test_tournament_with_no_matches_is_empty_lists(self):
        assert build_filters_payload([]) == {"facets_available": True, "age_groups": [], "groups": []}

    def test_unavailable_is_none_not_zero_or_empty(self):
        out = unavailable_filters_payload([{"id": 6, "name": "U14"}, {"id": 5, "name": "U13"}])
        assert out["facets_available"] is False
        assert out["groups"] is None
        assert out["age_groups"] == [
            {"id": 5, "name": "U13", "matches": None, "matches_on_date": None},
            {"id": 6, "name": "U14", "matches": None, "matches_on_date": None},
        ]

    @pytest.mark.parametrize("age_groups", [None, [], [None]])
    def test_unavailable_with_no_age_groups(self, age_groups):
        assert unavailable_filters_payload(age_groups) == {
            "facets_available": False,
            "age_groups": [],
            "groups": None,
        }

    def test_empty_page(self):
        assert empty_page(200, 400) == {"matches": [], "total": 0, "limit": 200, "offset": 400}

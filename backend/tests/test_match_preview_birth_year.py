"""Unit tests for `_birth_year_from_labels` used by match preview H2H filtering.

The helper derives a squad's birth year from its age group + season label using
the formula `season_end_year - age_number`, so a cohort can be tracked across
seasons as it ages up (e.g. U13 in 2024-2025 == U14 in 2025-2026 == 2012).
"""

import pytest

from dao.match_dao import _birth_year_from_labels


@pytest.mark.parametrize(
    ("age_group_name", "season_name", "expected"),
    [
        ("U14", "2025-2026", 2012),
        ("U13", "2024-2025", 2012),  # same cohort aged up from the prior season
        ("U13", "2025-2026", 2013),
        ("U15", "2025-2026", 2011),
        ("U16", "2025-2026", 2010),
        ("u14", "2025-2026", 2012),  # lowercase prefix
    ],
)
def test_birth_year_valid(age_group_name, season_name, expected):
    assert _birth_year_from_labels(age_group_name, season_name) == expected


@pytest.mark.parametrize(
    ("age_group_name", "season_name"),
    [
        (None, "2025-2026"),
        ("U14", None),
        ("U14", "garbage"),
        ("notanage", "2025-2026"),
    ],
)
def test_birth_year_malformed_returns_none(age_group_name, season_name):
    assert _birth_year_from_labels(age_group_name, season_name) is None

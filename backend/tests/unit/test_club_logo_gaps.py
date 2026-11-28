"""Crest gaps, as pure logic (SB-1815).

classify_logo / build_logo_gaps take rows already read, so none of this needs
a database. The default fixture is a team with scraped matches and no user data.
"""

import pytest

from dao.club_dao import (
    LOGO_EXTERNAL,
    LOGO_HOSTED,
    LOGO_MISSING,
    build_logo_gaps,
    classify_logo,
    club_logo_prefix,
)

BASE = "https://proj.supabase.co"
PREFIX = f"{BASE}/storage/v1/object/public/club-logos/"


@pytest.mark.unit
class TestClubLogoPrefix:
    def test_derived_from_supabase_url(self):
        assert club_logo_prefix(BASE) == PREFIX

    def test_trailing_slash_and_whitespace_tolerated(self):
        assert club_logo_prefix(f"  {BASE}/ ") == PREFIX

    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_unknown_when_not_configured(self, value):
        assert club_logo_prefix(value) is None


@pytest.mark.unit
class TestClassifyLogo:
    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_null_or_empty_is_missing(self, value):
        assert classify_logo(value, PREFIX) == LOGO_MISSING

    def test_hosted(self):
        assert classify_logo(f"{PREFIX}club-12.png", PREFIX) == LOGO_HOSTED

    def test_hosted_with_trailing_question_mark(self):
        assert classify_logo(f"{PREFIX}club-12.png?", PREFIX) == LOGO_HOSTED

    def test_hosted_small_variant(self):
        assert classify_logo(f"{PREFIX}club-12_sm.png", PREFIX) == LOGO_HOSTED

    def test_hosted_host_case_insensitive(self):
        assert (
            classify_logo("HTTPS://PROJ.SUPABASE.CO/storage/v1/object/public/club-logos/a.png", PREFIX) == LOGO_HOSTED
        )

    def test_external_host(self):
        assert classify_logo("https://example.test/crest.png", PREFIX) == LOGO_EXTERNAL

    def test_other_bucket_on_our_host_is_external(self):
        assert classify_logo(f"{BASE}/storage/v1/object/public/other/a.png", PREFIX) == LOGO_EXTERNAL

    def test_lookalike_host_is_external(self):
        url = "https://proj.supabase.co.evil.test/storage/v1/object/public/club-logos/a.png"
        assert classify_logo(url, PREFIX) == LOGO_EXTERNAL

    def test_path_is_case_sensitive(self):
        assert classify_logo(f"{BASE}/storage/v1/object/public/Club-Logos/a.png", PREFIX) == LOGO_EXTERNAL

    def test_surrounding_whitespace_ignored(self):
        assert classify_logo(f"  {PREFIX}a.png ", PREFIX) == LOGO_HOSTED


def _club(cid, name, logo=None, is_test=False):
    return {"id": cid, "name": name, "logo_url": logo, "is_test": is_test}


def _team(tid, name, club_id):
    return {"id": tid, "name": name, "club_id": club_id}


@pytest.mark.unit
class TestBuildLogoGaps:
    def test_three_gaps_reported(self):
        clubs = [
            _club(1, "Hosted FC", f"{PREFIX}1.png"),
            _club(2, "Bare FC", None),
            _club(3, "Linked FC", "https://example.test/x.png"),
        ]
        teams = [_team(10, "Hosted", 1), _team(20, "Bare", 2), _team(30, "Linked", 3), _team(40, "Orphan", None)]
        counts = {10: 5, 20: 4, 30: 3, 40: 2}

        out = build_logo_gaps(teams, clubs, counts, PREFIX)

        assert out["teams_without_club"] == [{"id": 40, "name": "Orphan", "match_count": 2}]
        assert out["clubs_without_logo"] == [{"id": 2, "name": "Bare FC"}]
        assert out["clubs_external_logo"] == [
            {"id": 3, "name": "Linked FC", "logo_url": "https://example.test/x.png", "host": "example.test"}
        ]

    def test_club_with_hosted_logo_absent_from_output(self):
        out = build_logo_gaps([_team(10, "A", 1)], [_club(1, "A", f"{PREFIX}1.png?")], {10: 1}, PREFIX)
        assert out["clubs_without_logo"] == []
        assert out["clubs_external_logo"] == []

    def test_teams_without_club_sorted_by_matches_then_name(self):
        teams = [_team(1, "B", None), _team(2, "A", None), _team(3, "C", None)]
        out = build_logo_gaps(teams, [], {1: 5, 2: 5, 3: 9}, PREFIX)
        assert [t["id"] for t in out["teams_without_club"]] == [3, 2, 1]

    def test_scoped_ignores_teams_with_no_matches(self):
        teams = [_team(1, "Quiet", None), _team(2, "Quiet2", 7)]
        clubs = [_club(7, "Quiet Club", None)]
        out = build_logo_gaps(teams, clubs, {}, PREFIX)
        assert out == {"teams_without_club": [], "clubs_without_logo": [], "clubs_external_logo": []}

    def test_scoped_ignores_clubs_without_in_scope_teams(self):
        clubs = [_club(7, "Empty Club", None)]
        out = build_logo_gaps([], clubs, {}, PREFIX)
        assert out["clubs_without_logo"] == []

    def test_test_clubs_and_their_teams_excluded_when_scoped(self):
        clubs = [_club(9, "Test FC", None, is_test=True)]
        teams = [_team(90, "Test Team", 9)]
        out = build_logo_gaps(teams, clubs, {90: 12}, PREFIX)
        assert out["clubs_without_logo"] == []

    def test_unscoped_reports_everything_including_test_clubs(self):
        clubs = [_club(9, "Test FC", None, is_test=True), _club(7, "Empty", None)]
        teams = [_team(1, "Quiet", None)]
        out = build_logo_gaps(teams, clubs, {}, PREFIX, scoped=False)
        assert [c["id"] for c in out["clubs_without_logo"]] == [7, 9]
        assert [t["id"] for t in out["teams_without_club"]] == [1]

    def test_whitespace_only_logo_is_missing_not_external(self):
        out = build_logo_gaps([_team(1, "A", 1)], [_club(1, "A", "   ")], {1: 1}, PREFIX)
        assert out["clubs_without_logo"] == [{"id": 1, "name": "A"}]
        assert out["clubs_external_logo"] == []

    def test_external_url_is_stripped(self):
        out = build_logo_gaps([_team(1, "A", 1)], [_club(1, "A", " https://e.test/a.png ")], {1: 1}, PREFIX)
        assert out["clubs_external_logo"][0]["logo_url"] == "https://e.test/a.png"

"""The admin Massey audit of the MT Power Rating (SB-1812).

What these guard: the gap is signed (positive when Elo ranks the team higher),
only gaps strictly above `min_gap` are flagged, the Elo rank is counted within
the island over the same ranked teams the stored Massey rank was, an unranked
team is never compared, and no run is an answer. The endpoint is admin only.
"""

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from power_rating_fakes import CONFERENCES, FakePowerRating, deps, rating, run

from mt_tools.power_rating_audit import NOTE, PowerRatingAuditResult, build_audit, get_power_rating_audit, spearman
from mt_tools.power_rating_read import TeamInfo

pytestmark = [pytest.mark.unit, pytest.mark.backend]

TODAY = date(2026, 11, 27)
RUN = run(30, "2026-11-27", national=True)


def payload(ratings: list[dict]) -> dict:
    return {"run": RUN, "ratings": ratings, "conferences": CONFERENCES}


def audit(ratings: list[dict], massey: dict[int, int], min_gap: int = 30, teams=None) -> PowerRatingAuditResult:
    names = teams if teams is not None else {r["team_id"]: TeamInfo(name=f"Team {r['team_id']}") for r in ratings}
    return build_audit(
        payload(ratings), massey, names, league="Homegrown", age_group="U17", season="2026-2027", min_gap=min_gap
    )


def ladder(n: int, island: int = 1, start: int = 1) -> list[dict]:
    """n ranked teams, Elo order = team id order (highest rating first)."""
    return [rating(start + i, 1800.0 - i, 8, island=island) for i in range(n)]


class TestGap:
    def test_positive_when_elo_ranks_the_team_higher(self):
        rows = ladder(40)
        massey = {t: t for t in range(1, 41)}
        massey[1], massey[40] = 40, 1  # Elo 1st, Massey 40th; and the reverse
        got = audit(rows, massey)
        by = {r.team_id: r for r in got.teams}
        assert (by[1].elo_rank, by[1].massey_rank, by[1].gap) == (1, 40, 39)
        assert (by[40].elo_rank, by[40].massey_rank, by[40].gap) == (40, 1, -39)

    def test_only_gaps_above_the_threshold_are_flagged(self):
        rows = ladder(40)
        massey = {t: t for t in range(1, 41)}
        massey[1], massey[31] = 31, 1  # a gap of exactly 30 each way
        assert audit(rows, massey).teams == []
        got = audit(rows, massey, min_gap=29)
        assert sorted(r.team_id for r in got.teams) == [1, 31]

    def test_biggest_gap_first(self):
        rows = ladder(10)
        massey = {1: 10, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 1, 8: 8, 9: 9, 10: 7}
        got = audit(rows, massey, min_gap=2)
        assert [(r.team_id, r.gap) for r in got.teams] == [(1, 9), (7, -6), (10, -3)]

    def test_row_fields(self):
        rows = [
            rating(1, 1754.4, 12, xconf_mp=2, badges=["low_cross_conference"]),
            rating(2, 1700.0),
            rating(3, 1690.0),
            rating(4, 1680.0),
        ]
        got = audit(rows, {1: 4, 2: 1, 3: 2, 4: 3}, min_gap=0)
        row = next(r for r in got.teams if r.team_id == 1)
        assert row.model_dump() == {
            "team_id": 1, "team": "Team 1", "conference": "Northeast", "island": 1, "elo_rating": 1754,
            "elo_rank": 1, "massey_rank": 4, "gap": 3, "mp": 12, "xconf_mp": 2, "badges": ["low_cross_conference"],
        }  # fmt: skip


class TestLikeWithLike:
    def test_elo_rank_is_within_the_island_not_national(self):
        # Island 2's best team is 41st on rating overall, but 1st in its island,
        # which is the scope its stored Massey rank (1) was counted in.
        rows = ladder(40) + ladder(5, island=2, start=41)
        massey = {t: t for t in range(1, 41)} | {t: t - 40 for t in range(41, 46)}
        got = audit(rows, massey, min_gap=0)
        assert got.teams == []
        assert got.teams_compared == 45
        assert [(i.island, i.teams, i.flagged) for i in got.islands] == [(1, 40, 0), (2, 5, 0)]

    def test_unranked_and_massey_less_teams_are_not_counted(self):
        # Team 2 (4 matches) and team 3 (no Massey rank) would push team 4 down
        # to 4th if counted; within the compared set it is 2nd, as Massey has it.
        rows = [rating(1, 1800.0), rating(2, 1790.0, 4), rating(3, 1780.0), rating(4, 1770.0)]
        got = audit(rows, {1: 1, 4: 2}, min_gap=0)
        assert got.teams_compared == 2
        assert got.teams == []

    def test_each_island_reports_its_own_correlation_and_the_largest_leads(self):
        rows = ladder(5) + ladder(3, island=2, start=6)
        massey = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 3, 7: 2, 8: 1}
        got = audit(rows, massey)
        assert [(i.island, i.rank_correlation) for i in got.islands] == [(1, 1.0), (2, -1.0)]
        assert got.rank_correlation == 1.0


class TestSummary:
    def test_counts_run_and_note(self):
        rows = ladder(40)
        massey = {t: t for t in range(1, 41)}
        massey[1], massey[40] = 40, 1
        got = audit(rows, massey)
        assert (got.teams_compared, got.flagged_count, got.min_gap) == (40, 2, 30)
        assert got.run.id == 30
        assert got.note == NOTE
        assert "island" in got.scope
        assert got.reason is None

    def test_a_team_missing_from_the_index_is_listed_by_id(self):
        rows = ladder(3)
        got = audit(rows, {1: 3, 2: 2, 3: 1}, min_gap=0, teams={})
        assert {r.team for r in got.teams} == {"1", "3"}

    def test_nothing_to_compare_is_an_answer_with_a_reason(self):
        got = audit([rating(1, 1500.0, 4)], {})
        assert got.teams == []
        assert got.teams_compared == 0
        assert got.rank_correlation is None
        assert got.reason == "No ranked teams with a Massey rank at U17 Homegrown in 2026-2027."


def test_spearman():
    assert spearman({1: 1, 2: 2, 3: 3}, {1: 1, 2: 2, 3: 3}) == 1.0
    assert spearman({1: 1, 2: 2, 3: 3}, {1: 3, 2: 2, 3: 1}) == -1.0
    assert spearman({1: 1}, {1: 1}) is None


# --- gathering ---------------------------------------------------------------------


def stored_world() -> FakePowerRating:
    ratings = [rating(t, 1800.0 - t, 8, massey_rank=t) for t in range(1, 6)]
    ratings[0]["massey_rank"], ratings[4]["massey_rank"] = 5, 1
    ratings.append(rating(9, 1700.0, 4))  # unranked: no Massey rank
    return FakePowerRating(runs=[run(20, "2026-11-20"), run(21, "2026-11-27")], ratings={21: ratings})


class TestGather:
    def test_reads_the_latest_run_and_its_stored_massey_ranks(self):
        got = get_power_rating_audit(deps(stored_world()), "U15", min_gap=3, today=TODAY)
        assert got.error is None
        assert got.run.id == 21
        assert [(r.team_id, r.gap) for r in got.teams] == [(1, 4), (5, -4)]
        assert got.teams[0].team == "Team 1"

    def test_no_run_yet_is_an_answer(self):
        got = get_power_rating_audit(deps(), "U15", today=TODAY)
        assert got.error is None
        assert got.teams == []
        assert got.run is None
        assert got.reason == "No Power Rating has been computed for Homegrown U15 in 2026-2027 yet."

    def test_unknown_age_group_is_invalid_args(self):
        assert get_power_rating_audit(deps(stored_world()), "U99", today=TODAY).error.kind == "invalid_args"

    def test_a_negative_gap_is_invalid_args(self):
        assert get_power_rating_audit(deps(), "U15", min_gap=-1, today=TODAY).error.kind == "invalid_args"

    def test_a_failed_read_is_unavailable_without_details(self):
        got = get_power_rating_audit(deps(FakePowerRating(fail=True)), "U15", today=TODAY)
        assert got.error.kind == "unavailable"
        assert "PostgREST" not in got.error.message


# --- GET /api/admin/power-rating/audit ----------------------------------------------

URL = "/api/admin/power-rating/audit"
ADMIN = {"user_id": "admin-1", "username": "admin", "role": "admin"}
CLUB_MANAGER = {"user_id": "cm-1", "username": "cm", "role": "club_manager", "club_id": 5}
TEAM_MANAGER = {"user_id": "tm-1", "username": "tm", "role": "team_manager", "team_id": 10}
RESULT = PowerRatingAuditResult(league="Homegrown", age_group="U17", season="2026-2027", teams=[], reason="none")


@pytest.fixture
def as_caller():
    import app as app_module
    from auth import get_current_user_required

    caller: dict = {}
    app_module.app.dependency_overrides[get_current_user_required] = lambda: caller["user"]

    def use(user):
        caller["user"] = user
        return TestClient(app_module.app)

    yield use
    app_module.app.dependency_overrides.clear()


class TestEndpoint:
    @pytest.mark.parametrize("user", [CLUB_MANAGER, TEAM_MANAGER], ids=["club_manager", "team_manager"])
    def test_non_admins_are_403_and_nothing_is_read(self, as_caller, user):
        with patch("mt_tools.power_rating_audit.get_power_rating_audit") as read:
            r = as_caller(user).get(URL, params={"age_group": "U17"})
        assert r.status_code == 403
        read.assert_not_called()

    def test_admin_gets_the_audit_with_the_default_gap(self, as_caller):
        with patch("mt_tools.power_rating_audit.get_power_rating_audit", return_value=RESULT) as read:
            r = as_caller(ADMIN).get(URL, params={"age_group": "U17"})
        assert r.status_code == 200
        assert r.json() == RESULT.model_dump(mode="json")
        assert read.call_args.args[1:] == ("U17", "Homegrown", None)
        assert read.call_args.kwargs == {"min_gap": 30}

    def test_min_gap_passes_through_and_a_negative_one_is_422(self, as_caller):
        with patch("mt_tools.power_rating_audit.get_power_rating_audit", return_value=RESULT) as read:
            client = as_caller(ADMIN)
            client.get(URL, params={"age_group": "U17", "min_gap": 10})
            assert read.call_args.kwargs == {"min_gap": 10}
            assert client.get(URL, params={"age_group": "U17", "min_gap": -1}).status_code == 422

    def test_invalid_args_is_400_and_unavailable_is_503(self, as_caller):
        from mt_ai.tools.schemas import ToolError

        bad = PowerRatingAuditResult(league="Homegrown", error=ToolError(kind="invalid_args", message="U99 unknown"))
        down = PowerRatingAuditResult(league="Homegrown", error=ToolError(kind="unavailable", message="x"))
        client = as_caller(ADMIN)
        with patch("mt_tools.power_rating_audit.get_power_rating_audit", return_value=bad):
            r = client.get(URL, params={"age_group": "U99"})
        assert (r.status_code, r.json()["detail"]) == (400, "U99 unknown")
        with patch("mt_tools.power_rating_audit.get_power_rating_audit", return_value=down):
            assert client.get(URL, params={"age_group": "U17"}).status_code == 503

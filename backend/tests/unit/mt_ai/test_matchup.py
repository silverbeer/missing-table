"""Matchup (SB-1782): both teams of one match, each inside its own tables.

The default fixture is MT's normal team: scraped results and nothing else. The
dossier world (dossier_fakes) with leagues that declare their match types, so
the stat boards behind the badges can be read.
"""

from dataclasses import replace
from unittest.mock import patch

import pytest
from dossier_fakes import HG_ONLY, PRO_A, REAL, UNPLAYED, dossier_deps, dossier_matches, off_table
from fastapi.testclient import TestClient
from motw_fakes import FLEX, HG, NORTHEAST, NOW, U15, U16, match, played
from mt_mcp_harness import served

from mt_ai.tools.schemas import AgeGroupRef, DivisionRef, ToolError
from mt_ai.tools.visibility import TeamIndex
from mt_tools.leaderboards import LeaderboardsResult, TeamTally, build_boards
from mt_tools.matchup import (
    BADGE_RANK,
    MAX_BADGES,
    badge_cutoff,
    badge_label,
    badges_from,
    best_badges,
    get_matchup,
    meetings_from,
    stakes_for,
    top_leagues,
)
from mt_tools.team_dossier import ConferenceLine, TeamDossierResult

pytestmark = [pytest.mark.unit, pytest.mark.backend]

FEST = 3
LEAGUE_TYPE, FLEX_TYPE = 11, 15
TYPED_LEAGUES = [
    {"id": HG, "name": "Homegrown", "is_test": False, "match_type_id": LEAGUE_TYPE},
    {"id": FLEX, "name": "Flex", "is_test": False, "parent_league_id": HG, "match_type_id": FLEX_TYPE},
]


class TypedLeagues:
    def get_all_leagues(self, include_test=False):
        return [dict(lg) for lg in TYPED_LEAGUES]


def fest(home, away, mid, round_name="group_stage", *, age=U15, **extra):
    return off_table(
        home,
        away,
        "2026-11-20",
        age=age,
        mid=mid,
        tournament_id=FEST,
        tournament_name="MLS NEXT Fest",
        tournament_round=round_name,
        **extra,
    )


def team5_season() -> list[dict]:
    """Team 5's U15 Northeast season to six games, so the boards rank it."""
    return [
        played(5, 4, "2026-09-05", NORTHEAST, 5, 0),
        played(4, 5, "2026-10-10", NORTHEAST, 0, 4),
    ]


def world(extra=()) -> list[dict]:
    return [*dossier_matches(), *team5_season(), *extra]


def matchup_deps(matches=None, **kw):
    return replace(dossier_deps(world() if matches is None else matches, **kw), leagues=TypedLeagues())


def matchup(match_id, *, deps=None, viewer=REAL):
    return get_matchup(deps or matchup_deps(), match_id, viewer=viewer, now=NOW)


# --- pure rules ----------------------------------------------------------------


class TestStakes:
    @pytest.mark.parametrize(
        "round_name,stakes",
        [
            ("group_stage", "group"),
            ("showcase", "none"),
            ("consolation", "none"),
            ("placement_final", "none"),
            ("third_place", "none"),
            ("round_of_16", "elimination"),
            ("quarterfinal", "elimination"),
            ("semifinal", "elimination"),
            ("final", "elimination"),
            ("bronze_final", "elimination"),
            ("something_new", None),
            (None, None),
        ],
    )
    def test_per_round(self, round_name, stakes):
        assert stakes_for(FEST, round_name) == stakes

    def test_not_a_tournament_has_no_stakes(self):
        assert stakes_for(None, "final") is None


def tt(team_id, w=0, d=0, l=0, gf=0, ga=0, **kw) -> TeamTally:
    return TeamTally(team_id=team_id, name=f"Team {team_id}", gp=w + d + l, w=w, d=d, l=l, gf=gf, ga=ga, **kw)


AGE = AgeGroupRef(id=U15, name="U15")


HG_ID = HG


def badges(team_id, teams, **kw):
    return badges_from(team_id, f"Team {team_id}", AGE, HG_ID, "Homegrown", build_boards(teams, **kw))


class TestBadges:
    def test_top_ten_is_a_badge_eleventh_is_not(self):
        # 33 teams (a third is 11), goals for 40 down: team i scores 41 - i.
        teams = [tt(i, w=6, gf=41 - i) for i in range(1, 34)]
        gf = next(b for b in build_boards(teams, limit=BADGE_RANK) if b.key == "gf")
        assert gf.ranked_count == 33

        tenth = [b for b in badges(10, teams, limit=BADGE_RANK) if b.board == "gf"]
        eleventh = [b for b in badges(11, teams, limit=BADGE_RANK) if b.board == "gf"]
        assert [(b.rank, b.of, b.value) for b in tenth] == [(10, 33, 31)]
        assert eleventh == []

    def test_only_the_top_third_of_a_small_board(self):
        """Never "8th of 8": eight teams, so only ranks 1 and 2 are badges."""
        teams = [tt(i, w=6, gf=20 - i) for i in range(1, 9)]
        assert badge_cutoff(8) == 2
        assert [b.rank for b in badges(2, teams) if b.board == "gf"] == [2]
        assert [b for b in badges(3, teams) if b.board == "gf"] == []
        assert [b for b in badges(8, teams) if b.board == "gf"] == []

    def test_a_zero_on_a_count_board_is_no_badge(self):
        """Nine teams that each met a pro academy and none won: all 1st, all 0."""
        teams = [tt(i, w=1, d=5, ga=i, pro_gp=1, pro_w=0) for i in range(1, 10)]
        got = badges(1, teams)
        assert "pro_wins" not in {b.board for b in got}
        assert "gf" not in {b.board for b in got}  # 0 goals for, shared 1st
        assert "ga" in {b.board for b in got}  # fewest against: 1 is a real best

    def test_text_says_of_n_with_the_league_and_is_not_a_ranking(self):
        teams = [tt(1, w=6, gf=18), *(tt(i, w=6, gf=6) for i in range(2, 6))]
        badge = next(b for b in badges(1, teams) if b.board == "gf_pg")
        assert badge.fact_id == f"t1:a15:board:{HG_ID}:gf_pg"
        assert badge.league_id == HG_ID
        assert "1st in U15 Homegrown goals for per match, of 5 teams (3.00)" in badge.text
        assert "not a ranking" in badge.text

    def test_label_keeps_the_title_case_but_the_first_letter(self):
        assert badge_label(2, "U15", "Homegrown", "Points (W=3, D=1; shootouts count as draws)", 134) == (
            "2nd in U15 Homegrown points (W=3, D=1; shootouts count as draws), of 134 teams"
        )

    def test_at_most_three_best_first(self):
        # Nine teams (cutoff 3): team 1 leads nearly every board.
        teams = [tt(1, w=6, gf=30, ga=0), *(tt(i, l=6, gf=1, ga=5 + i) for i in range(2, 10))]
        got = best_badges(badges(1, teams))
        assert len(got) == MAX_BADGES
        assert [b.board for b in got] == ["pts", "ppg", "gf"]  # all 1st; board order breaks the tie

    def test_a_team_under_min_gp_has_none(self):
        assert badges(1, [tt(1, w=2), tt(2, w=6)]) == []


class TestTopLeagues:
    def _dossier(self, *division_ids):
        lines = [
            ConferenceLine(kind="league", competition="League", division=DivisionRef(id=d, name=str(d)))
            for d in division_ids
        ]
        return TeamDossierResult(age_group=AgeGroupRef(id=U15, name="U15"), conferences=lines)

    def test_flex_is_its_parent_and_test_leagues_are_skipped(self):
        def reg(division_id, league_id):
            return {"age_groups": {"id": U15, "name": "U15"}, "divisions": {"id": division_id, "league_id": league_id}}

        index = TeamIndex(
            teams={1: {"id": 1, "team_mappings": [reg(201, HG), reg(205, FLEX), reg(299, 9)]}},
            leagues={
                HG: {"id": HG, "name": "Homegrown"},
                FLEX: {"id": FLEX, "name": "Flex", "parent_league_id": HG},
                9: {"id": 9, "name": "TSC League", "is_test": True},
            },
            test_league_ids=frozenset({9}),
            include_test=True,  # a tester sees the registration; the boards never count it
        )
        assert top_leagues(index, 1, self._dossier(201, 205, 299)) == [(HG, "Homegrown")]

    def test_a_league_with_no_boards_is_no_badges_not_unavailable(self):
        refused = LeaderboardsResult(league="Academy", error=ToolError(kind="invalid_args", message="x"))
        with patch("mt_tools.matchup.get_leaderboards", lambda *a, **k: refused):
            got = matchup(501)
        assert got.home.badges == []
        assert got.home.dossier.error is None


def row(mid, home, away, hs, as_, *, age=U15, status="completed", date="2026-09-02", **extra) -> dict:
    return {
        "id": mid,
        "home_team_id": home,
        "away_team_id": away,
        "home_score": hs,
        "away_score": as_,
        "age_group_id": age,
        "match_status": status,
        "match_date": date,
        **extra,
    }


class TestMeetings:
    def test_every_season_at_the_age_newest_first_home_goals_first(self):
        this = {"id": 1, "home_team_id": 1, "away_team_id": 2, "age_group_id": U15}
        rows = [
            {**this},  # the match itself
            row(2, 2, 1, 3, 1, date="2025-10-01", season_name="2025-2026", match_type_name="League"),
            row(3, 1, 2, 2, 2, date="2026-09-01", season_name="2026-2027", match_type_name="Flex"),
            row(4, 1, 2, 1, 0, age=U16),  # another age group
            row(5, 1, 3, 1, 0),  # another opponent
            row(6, 1, 2, None, None, status="scheduled", date="2026-12-01"),  # not played
        ]
        got = meetings_from(rows, this)
        assert [(m.match_id, m.score, m.season, m.competition) for m in got] == [
            (3, "2-2", "2026-2027", "Flex"),
            (2, "1-3", "2025-2026", "League"),
        ]


# --- gathering -----------------------------------------------------------------


class TestGetMatchup:
    def test_same_conference_league_match_is_not_scouting(self):
        got = matchup(501)  # teams 1 and 2, both Northeast and Turnpike
        assert got.error is None
        assert got.shares_conference is True
        assert got.scouting_relevant is False
        assert got.match.tournament is None
        assert got.match.stakes is None
        assert got.home.dossier.team.id == 1
        assert got.away.dossier.team.id == 2

    def test_cross_conference_tournament_match(self):
        got = matchup(620, deps=matchup_deps(world([fest(1, PRO_A, 620, "quarterfinal")])))
        assert got.shares_conference is False
        assert got.scouting_relevant is True
        assert got.match.tournament.name == "MLS NEXT Fest"
        assert got.match.stakes == "elimination"

    def test_cross_conference_league_match_is_scouting(self):
        """No tournament, but two teams that share no table."""
        m = match(HG_ONLY, PRO_A, "2026-11-21", NORTHEAST, mid=621)
        got = matchup(621, deps=matchup_deps(world([m])))
        assert got.shares_conference is False
        assert got.scouting_relevant is True

    def test_populated_side_has_badges_with_of(self):
        got = matchup(620, deps=matchup_deps(world([fest(1, PRO_A, 620)])))
        home = got.home.badges
        assert home, "team 1 has six League/Flex games and leads boards"
        assert len(home) <= MAX_BADGES
        assert all(b.league == "Homegrown" and b.age_group == "U15" for b in home)
        assert all(b.rank <= min(BADGE_RANK, b.of // 3) for b in home)
        assert all(b.fact_id.startswith(f"t1:a15:board:{HG}:") for b in home)
        assert "not a ranking" in got.home.badges_note

    def test_a_side_with_no_results_is_empty_not_zero(self):
        got = matchup(622, deps=matchup_deps(world([fest(UNPLAYED, 1, 622)])))
        side = got.home.dossier
        assert side.error is None
        assert side.totals is None
        assert "no_results" in side.flags
        assert side.conferences[0].position is None
        assert got.home.badges == []
        assert got.away.dossier.totals is not None

    def test_badge_age_is_the_season_age_when_playing_up(self):
        """Match 601 is U16; team 5 fielded its U15 side. Its badges are U15 boards."""
        got = matchup(601)
        side = got.home
        assert side.dossier.context.playing_up is True
        assert side.dossier.context.bracket_age_group.name == "U16"
        assert got.match.age_group.name == "U16"
        assert side.badges, "team 5 has six U15 Northeast games"
        assert all(b.age_group == "U15" for b in side.badges)
        assert all(b.fact_id.startswith(f"t5:a15:board:{HG}:") for b in side.badges)

    def test_one_side_failing_does_not_fail_the_call(self):
        def dossier(deps, team_id, *a, **k):
            from mt_ai.tools.schemas import ToolError
            from mt_tools.team_dossier import TeamDossierResult
            from mt_tools.team_dossier import get_team_dossier as real

            if team_id == 2:
                return TeamDossierResult(error=ToolError(kind="unavailable", message="x"))
            return real(deps, team_id, *a, **k)

        with patch("mt_tools.matchup.get_team_dossier", dossier):
            got = matchup(501)
        assert got.error is None
        assert got.away.dossier.error.kind == "unavailable"
        assert got.away.badges is None
        assert got.home.dossier.error is None
        assert got.shares_conference is None
        assert got.scouting_relevant is False

    def test_previous_meetings_every_season(self):
        old = {**played(1, 2, "2025-10-01", NORTHEAST, 0, 2), "season_id": 6, "season_name": "2025-2026"}
        got = matchup(501, deps=matchup_deps(world([old])))
        assert [m.season for m in got.previous_meetings][-1] == "2025-2026"
        assert got.previous_meetings[-1].score == "0-2"
        assert all(m.match_id != 501 for m in got.previous_meetings)

    def test_unreadable_boards_are_null_badges_not_empty(self):
        got = matchup(501, deps=dossier_deps(world()))  # leagues declare no match type
        assert got.error is None
        assert got.home.badges is None
        assert got.home.dossier.error is None

    def test_unknown_match_is_invalid_args(self):
        assert matchup(9999).error.kind == "invalid_args"

    def test_another_season_is_invalid_args(self):
        old = {**match(1, 2, "2025-10-01", NORTHEAST, mid=630), "season_id": 6}
        assert matchup(630, deps=matchup_deps(world([old]))).error.kind == "invalid_args"

    def test_a_failed_match_read_is_unavailable(self):
        got = matchup(501, deps=matchup_deps(match_fail=True))
        assert got.error.kind == "unavailable"
        assert "PostgREST" not in got.error.message


# --- surfaces ------------------------------------------------------------------


class TestOverMcp:
    async def test_a_fan_can_list_and_call_it(self):
        async with served(matchup_deps()) as s, s.session("fan") as session:
            tools = (await session.list_tools()).tools
            result = await session.call_tool("get_matchup", {"match_id": 501})
        tool = next(t for t in tools if t.name == "get_matchup")
        assert tool.input_schema["required"] == ["match_id"]
        assert "fact id" in tool.description
        assert "across" in tool.description
        assert not result.is_error
        data = result.structured_content
        assert data["error"] is None
        assert data["home"]["dossier"]["team"]["id"] == 1


@pytest.fixture
def api():
    import app as app_module
    from auth import get_current_user_required

    app_module.app.dependency_overrides[get_current_user_required] = lambda: {"user_id": "f", "role": "team-fan"}
    with patch.object(app_module, "_my_team_deps", lambda: matchup_deps()):
        yield TestClient(app_module.app)
    app_module.app.dependency_overrides.clear()


class TestApi:
    def test_matchup(self, api):
        r = api.get("/api/matches/501/matchup")
        assert r.status_code == 200
        body = r.json()
        assert body["shares_conference"] is True
        assert body["home"]["dossier"]["team"]["id"] == 1

    def test_unknown_match_is_400(self, api):
        assert api.get("/api/matches/9999/matchup").status_code == 400

    def test_a_failed_read_is_503_without_details(self, api):
        import app as app_module

        with patch.object(app_module, "_my_team_deps", lambda: matchup_deps(match_fail=True)):
            r = api.get("/api/matches/501/matchup")
        assert r.status_code == 503
        assert "PostgREST" not in r.text

    def test_requires_a_logged_in_user(self):
        """Invite-only: a matchup names teams, so no anonymous read."""
        import app as app_module

        r = TestClient(app_module.app).get("/api/matches/501/matchup")
        assert r.status_code in (401, 403)

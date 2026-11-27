"""`mt rankings` (SB-1808) against a stub client: no network, no database."""

from unittest.mock import MagicMock

import pytest
from rich.console import Console
from typer.testing import CliRunner

import mt_cli

pytestmark = pytest.mark.unit
runner = CliRunner()

NOTE = (
    "MT Power Rating from 147 Homegrown U17 teams in MT, rated on 1122 matches; 146 with 6 or more matches "
    "are ranked. Conferences meet only at Flex and national events."
)
TIERS = [
    {"key": "elite", "label": "Elite", "min": 1700},
    {"key": "contender", "label": "Contender", "min": 1600},
    {"key": "above_average", "label": "Above average", "min": 1500},
]


def team(rank, team_id, name, rating, *, conference="Northeast", conference_rank=1, tier=None, **extra):
    return {
        "rank": rank,
        "team_id": team_id,
        "team": name,
        "club_id": None,
        "club_logo_url": None,
        "rating": rating,
        "rank_change_7d": None,
        "rating_change_7d": None,
        "w": 10,
        "d": 1,
        "l": 1,
        "mp": 12,
        "conference": conference,
        "conference_rank": conference_rank,
        "tier": tier,
        "badges": [],
        "xconf_mp": 2,
        "pro_academy": False,
        "comparable_nationally": rank is not None,
        **extra,
    }


NATIONAL = {
    "league": "Homegrown",
    "age_group": "U17",
    "season": "2026-2027",
    "view": "national",
    "conference": None,
    "conferences": ["Northeast", "Southeast"],
    "run": {
        "id": 412,
        "computed_at": "2026-12-15T10:00:04Z",
        "through_date": "2026-12-14",
        "matches_counted": 1122,
        "params_version": "elo-v1",
    },
    "movement_since": {"run_id": 405, "computed_at": "2026-12-08T10:00:00Z"},
    "publication": {"national": True, "reason": None},
    "coverage": {
        "teams_in_pool": 147,
        "ranked": 146,
        "unranked_count": 1,
        "matches_counted": 1122,
        "matches_excluded": {"out_of_pool_opponent": 13, "forfeit": 0},
        "min_matches": 6,
        "note": NOTE,
    },
    "tiers": TIERS,
    "teams": [
        team(1, 21, "FC Westchester", 1754, tier="elite", rank_change_7d=2, rating_change_7d=12),
        team(2, 22, "Pro Academy FC", 1642, tier="contender", pro_academy=True, badges=["low_cross_conference"]),
        team(3, 23, "Middling SC", 1420, conference="Southeast", rank_change_7d=0, rating_change_7d=-3),
        team(None, 24, "Island FC", 1480, conference="Southeast", conference_rank=2),
    ],
    "unranked": [
        {"team_id": 77, "team": "Newcomers SC", "conference": "Northeast", "mp": 4, "needed": 6},
    ],
    "reason": None,
}

CONFERENCE = {
    **NATIONAL,
    "view": "conference",
    "tiers": [],
    "movement_since": None,
    "publication": {"national": False, "reason": "The largest connected group holds 73% of ranked teams."},
    "teams": [
        team(None, 21, "FC Westchester", 1754),
        team(None, 25, "Second NE", 1600, conference_rank=2),
        team(None, 23, "Middling SC", 1420, conference="Southeast"),
    ],
}

TEAM = {
    "league": "Homegrown",
    "age_group": "U15",
    "season": "2026-2027",
    "team_id": 7,
    "team": "IFA",
    "run": NATIONAL["run"],
    "in_run": True,
    "rating": 1642,
    "rank": None,
    "conference": "Northeast",
    "conference_rank": 3,
    "tier": None,
    "badges": ["low_cross_conference"],
    "ranked": True,
    "needed": None,
    "mp": 12,
    "w": 8,
    "d": 2,
    "l": 2,
    "xconf_mp": 1,
    "sos": {"rating": 1538, "rank": 4, "of": 12, "scope": "conference"},
    "biggest_movers": [
        {
            "match_id": 9,
            "match_date": "2026-11-02",
            "opponent_id": 3,
            "opponent": "Rival FC",
            "result": "W",
            "goals_for": 3,
            "goals_against": 0,
            "penalties_for": None,
            "penalties_against": None,
            "expected": 0.41,
            "delta": 24.0,
        },
        {
            "match_id": 10,
            "match_date": "2026-11-09",
            "opponent_id": 4,
            "opponent": "Shootout SC",
            "result": "D",
            "goals_for": 1,
            "goals_against": 1,
            "penalties_for": 4,
            "penalties_against": 3,
            "expected": 0.6,
            "delta": -3.1,
        },
    ],
    "deltas": [],
    "history": [
        {"run_id": 400, "computed_at": "2026-12-01T10:00:00Z", "rating": 1600, "rank": None, "conference_rank": 4}
    ],
    "reason": None,
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mt_cli, "console", Console(width=200))
    stub = MagicMock()
    monkeypatch.setattr(mt_cli, "get_client", lambda: (stub, None))
    return stub


def test_national_list_coverage_first_then_tiers(client):
    client.get_power_rating.return_value = NATIONAL
    out = runner.invoke(mt_cli.app, ["rankings", "U17", "-l", "Homegrown"])
    assert out.exit_code == 0, out.output
    client.get_power_rating.assert_called_once_with("U17", league="Homegrown", season=None, view=None, conference=None)
    text = out.output
    assert text.index("MT Power Rating from 147") < text.index("FC Westchester")
    assert "Elite · 1,700+" in text
    assert "Contender · 1,600+" in text
    assert "Below 1,500" in text
    assert "Not yet comparable nationally" in text
    assert "1,754" in text
    assert "▲2 · +12" in text
    assert "= · -3" in text
    assert "Northeast · 1st" in text
    assert "pro academy" in text
    assert "movement since run 405" in text
    assert "4 of 6" in text


def test_absent_movement_is_a_dash_not_zero(client):
    client.get_power_rating.return_value = CONFERENCE
    out = runner.invoke(mt_cli.app, ["rankings", "U17"])
    assert out.exit_code == 0, out.output
    assert "no run a week earlier: no movement" in out.output
    assert "+0" not in out.output
    assert "▲0" not in out.output


def test_conference_lists_with_the_reason(client):
    client.get_power_rating.return_value = CONFERENCE
    out = runner.invoke(mt_cli.app, ["rankings", "U16", "--view", "conference", "-c", "Northeast"])
    assert out.exit_code == 0, out.output
    client.get_power_rating.assert_called_once_with(
        "U16", league="Homegrown", season=None, view="conference", conference="Northeast"
    )
    assert "No national list: The largest connected group holds 73%" in out.output
    assert out.output.index("Northeast") < out.output.index("Southeast")
    assert "Elite" not in out.output
    assert "Northeast · 2nd" in out.output


def test_no_run_prints_the_reason(client):
    client.get_power_rating.return_value = {
        "league": "Homegrown",
        "age_group": "U15",
        "season": "2026-2027",
        "teams": [],
        "unranked": [],
        "publication": {"national": False, "reason": "No Power Rating yet."},
        "reason": "No Power Rating has been computed for Homegrown U15 in 2026-2027 yet.",
    }
    out = runner.invoke(mt_cli.app, ["rankings", "U15"])
    assert out.exit_code == 0, out.output
    assert "No Power Rating has been computed" in out.output


def test_unknown_view_exits_1_without_calling(client):
    out = runner.invoke(mt_cli.app, ["rankings", "U17", "--view", "global"])
    assert out.exit_code == 1
    client.get_power_rating.assert_not_called()


def test_json(client):
    client.get_power_rating.return_value = NATIONAL
    out = runner.invoke(mt_cli.app, ["rankings", "U17", "--json", "--season", "2025-2026"])
    assert out.exit_code == 0, out.output
    client.get_power_rating.assert_called_once_with(
        "U17", league="Homegrown", season="2025-2026", view=None, conference=None
    )
    assert '"rank_change_7d": 2' in out.output


def test_api_error_exits_1(client):
    client.get_power_rating.side_effect = mt_cli.APIError("age_group must be one of U15, U17")
    out = runner.invoke(mt_cli.app, ["rankings", "U99"])
    assert out.exit_code == 1
    assert "age_group must be one of" in out.output


def test_team(client, monkeypatch):
    monkeypatch.setattr(mt_cli, "resolve_team", lambda c, term: {"id": 7, "name": "IFA"})
    client.get_power_rating_team.return_value = TEAM
    out = runner.invoke(mt_cli.app, ["rankings", "team", "IFA", "--age", "U15"])
    assert out.exit_code == 0, out.output
    client.get_power_rating_team.assert_called_once_with(7, "U15", league="Homegrown", season=None)
    text = out.output
    assert "Rating 1,642 · Northeast · 3rd" in text
    assert "national rank" not in text
    assert "Strength of schedule 1,538 — 4th toughest of 12 (conference)" in text
    assert "Rival FC" in text and "3-0" in text and "41%" in text and "+24.0" in text
    assert "1-1 (4-3 pens)" in text
    assert "Weekly history" in text


def test_team_not_in_run(client, monkeypatch):
    monkeypatch.setattr(mt_cli, "resolve_team", lambda c, term: {"id": 7, "name": "IFA"})
    client.get_power_rating_team.return_value = {
        **TEAM,
        "in_run": False,
        "reason": "IFA has no rated match at U15 Homegrown in 2026-2027.",
    }
    out = runner.invoke(mt_cli.app, ["rankings", "team", "IFA", "--age", "U15"])
    assert out.exit_code == 0, out.output
    assert "IFA has no rated match" in out.output
    assert "Rating 1,642" not in out.output


def test_unranked_team_shows_matches_needed(client, monkeypatch):
    monkeypatch.setattr(mt_cli, "resolve_team", lambda c, term: {"id": 7, "name": "IFA"})
    client.get_power_rating_team.return_value = {**TEAM, "ranked": False, "needed": 2, "mp": 4, "sos": None}
    out = runner.invoke(mt_cli.app, ["rankings", "team", "IFA", "--age", "U15"])
    assert out.exit_code == 0, out.output
    assert "Unranked: 4 of 6 matches" in out.output


def test_team_needs_a_team_and_an_age(client):
    out = runner.invoke(mt_cli.app, ["rankings", "team", "IFA"])
    assert out.exit_code == 1
    assert "--age" in out.output
    client.get_power_rating_team.assert_not_called()


def test_a_stray_argument_is_refused(client):
    out = runner.invoke(mt_cli.app, ["rankings", "U17", "IFA"])
    assert out.exit_code == 1
    client.get_power_rating.assert_not_called()

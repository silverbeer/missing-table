"""SB-672: mt read commands — team stats, team matches, match show, player stats.

`mt` could drive a match but not ask about one, so diagnosing SB-671 meant
reading source and running SQL by hand. These exercise the real helpers and the
real commands against a stub client — no network, no database.

Note the deliberate difference from test_mt_cli_status.py, which reproduces the
logic it tests. Copied logic passes while the code it mirrors is broken, so this
imports the functions instead.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import mt_cli
from mt_cli import (
    STAT_FIELDS,
    ResolutionError,
    resolve_match_type,
    resolve_season,
    resolve_team,
    sort_stats,
    took_part,
)

runner = CliRunner()

SEASONS = [
    {"id": 6, "name": "2025", "is_current": False},
    {"id": 7, "name": "2026", "is_current": True},
]

MATCH_TYPES = [
    {"id": 1, "name": "League"},
    {"id": 2, "name": "Friendly"},
    {"id": 3, "name": "Tournament"},
]

TEAMS = [
    {"id": 11, "name": "IFA U15 HG"},
    {"id": 12, "name": "IFA U16 HG"},
    {"id": 13, "name": "Boston Bolts"},
]


def _player(jersey, first, last, **stats):
    row = {
        "player_id": jersey,
        "jersey_number": jersey,
        "first_name": first,
        "last_name": last,
        "games_played": 0,
        "games_started": 0,
        "total_goals": 0,
        "total_assists": 0,
        "total_yellow_cards": 0,
        "total_red_cards": 0,
    }
    row.update(stats)
    return row


SQUAD = [
    _player(9, "Gabe", "Drake", games_played=5, games_started=5, total_goals=4, total_assists=1),
    _player(8, "Marcus", "Chen", games_played=5, games_started=4, total_goals=2, total_assists=6),
    _player(4, "Owen", "Reilly", games_played=3, total_assists=2),
    _player(2, "Never", "Played"),
]


def _stub_client():
    client = MagicMock()
    client.get_seasons.return_value = SEASONS
    client.get_match_types.return_value = MATCH_TYPES
    client.get_teams.return_value = TEAMS
    client.get_team.side_effect = lambda tid: next(t for t in TEAMS if t["id"] == tid)
    client.get_team_stats.return_value = {"players": SQUAD}
    client.get_games_by_team.return_value = [
        {
            "id": 1,
            "match_date": "2026-08-01",
            "match_status": "completed",
            "match_type_name": "Friendly",
            "home_team_name": "IFA U15 HG",
            "away_team_name": "Boston Bolts",
            "home_score": 3,
            "away_score": 1,
        },
        {
            "id": 2,
            "match_date": "2026-08-20",
            "match_status": "scheduled",
            "match_type_name": "League",
            "home_team_name": "IFA U15 HG",
            "away_team_name": "Boston Bolts",
            "home_score": None,
            "away_score": None,
        },
    ]
    client.get_game.return_value = {
        "id": 2,
        "match_date": "2026-08-20",
        "match_status": "scheduled",
        "home_team_id": 11,
        "away_team_id": 13,
        "home_team_name": "IFA U15 HG",
        "away_team_name": "Boston Bolts",
    }
    client.get_lineup.return_value = {"positions": [{"position": "GK", "player_id": 1, "jersey_number": 1}]}
    client.get_match_events.return_value = []
    client.get_roster_player_stats.return_value = SQUAD[0]
    return client


@pytest.fixture
def client(monkeypatch):
    stub = _stub_client()
    monkeypatch.setattr(mt_cli, "get_client", lambda: (stub, MagicMock()))
    return stub


# --- helpers ---------------------------------------------------------------


@pytest.mark.unit
class TestResolution:
    def test_team_by_id(self):
        assert resolve_team(_stub_client(), "11")["name"] == "IFA U15 HG"

    def test_team_by_name_substring(self):
        assert resolve_team(_stub_client(), "bolts")["id"] == 13

    def test_ambiguous_team_names_the_candidates(self):
        with pytest.raises(ResolutionError) as exc:
            resolve_team(_stub_client(), "IFA")
        # Guessing between two squads would be worse than refusing.
        assert "IFA U15 HG" in str(exc.value)
        assert "IFA U16 HG" in str(exc.value)

    def test_unknown_team_is_an_error(self):
        with pytest.raises(ResolutionError):
            resolve_team(_stub_client(), "nonesuch")

    def test_season_defaults_to_current(self):
        assert resolve_season(_stub_client())["id"] == 7

    def test_season_by_name(self):
        assert resolve_season(_stub_client(), "2025")["id"] == 6

    def test_competition_defaults_to_league(self):
        assert resolve_match_type(_stub_client())["id"] == 1

    def test_all_means_no_filter(self):
        assert resolve_match_type(_stub_client(), "all") is None

    def test_missing_league_falls_back_to_every_competition(self):
        stub = _stub_client()
        stub.get_match_types.return_value = [{"id": 2, "name": "Friendly"}]
        # An empty board would be a worse answer than a full one.
        assert resolve_match_type(stub) is None

    def test_named_competition_that_does_not_exist_is_an_error(self):
        with pytest.raises(ResolutionError):
            resolve_match_type(_stub_client(), "cup")


@pytest.mark.unit
class TestSortingAndFiltering:
    def test_default_sort_is_goals(self):
        assert sort_stats(SQUAD)[0]["last_name"] == "Drake"

    def test_sort_by_assists(self):
        assert sort_stats(SQUAD, "a")[0]["last_name"] == "Chen"

    def test_ties_break_on_goals_then_assists(self):
        rows = [
            _player(1, "Level", "Alpha", games_played=5, total_goals=2, total_assists=1),
            _player(2, "Level", "Bravo", games_played=5, total_goals=4, total_assists=1),
        ]
        # Level on GP: goals separate them.
        assert [p["last_name"] for p in sort_stats(rows, "gp")] == ["Bravo", "Alpha"]

    def test_took_part_matches_the_web_board(self):
        assert took_part(SQUAD[2]) is True  # assists only
        assert took_part(SQUAD[3]) is False  # nothing at all

    def test_stat_fields_match_the_board(self):
        assert [label for label, _ in STAT_FIELDS] == ["GP", "GS", "G", "A", "YC", "RC"]


# --- commands --------------------------------------------------------------


@pytest.mark.unit
class TestTeamStats:
    def test_renders_the_board(self, client):
        result = runner.invoke(mt_cli.app, ["team", "stats", "IFA U15"])

        assert result.exit_code == 0
        assert "Gabe" in result.output
        assert "2026" in result.output
        assert "League" in result.output

    def test_defaults_to_current_season_and_league(self, client):
        runner.invoke(mt_cli.app, ["team", "stats", "IFA U15"])

        client.get_team_stats.assert_called_once_with(11, season_id=7, match_type_id=1)

    def test_all_competitions_sends_no_filter(self, client):
        runner.invoke(mt_cli.app, ["team", "stats", "IFA U15", "--competition", "all"])

        assert client.get_team_stats.call_args.kwargs["match_type_id"] is None

    def test_hides_players_who_never_played(self, client):
        result = runner.invoke(mt_cli.app, ["team", "stats", "IFA U15"])

        assert "Never" not in result.output

    def test_everyone_flag_includes_them(self, client):
        result = runner.invoke(mt_cli.app, ["team", "stats", "IFA U15", "--everyone"])

        assert "Never" in result.output

    def test_ambiguous_team_fails_clearly(self, client):
        result = runner.invoke(mt_cli.app, ["team", "stats", "IFA"])

        assert result.exit_code == 1
        assert "IFA U16 HG" in result.output

    def test_nothing_recorded_explains_itself(self, client):
        client.get_team_stats.return_value = {"players": []}
        result = runner.invoke(mt_cli.app, ["team", "stats", "IFA U15"])

        assert result.exit_code == 0
        # Never imply the squad did nothing — say it was not recorded.
        assert "Nothing recorded" in result.output


@pytest.mark.unit
class TestTeamMatches:
    def test_shows_status_for_each_match(self, client):
        result = runner.invoke(mt_cli.app, ["team", "matches", "IFA U15"])

        assert result.exit_code == 0
        assert "completed" in result.output
        # The status column is the point: this is what SB-671 turned on.
        assert "scheduled" in result.output

    def test_explains_which_statuses_count(self, client):
        result = runner.invoke(mt_cli.app, ["team", "matches", "IFA U15"])

        assert "count towards season stats" in result.output


@pytest.mark.unit
class TestMatchShow:
    def test_says_whether_the_match_counts(self, client):
        result = runner.invoke(mt_cli.app, ["match", "show", "2"])

        assert result.exit_code == 0
        assert "scheduled" in result.output
        assert "no" in result.output.lower()

    def test_a_completed_match_counts(self, client):
        client.get_game.return_value = {**client.get_game.return_value, "match_status": "completed"}
        result = runner.invoke(mt_cli.app, ["match", "show", "2"])

        assert "yes" in result.output.lower()

    def test_is_honest_about_appearances_not_being_exposed(self, client):
        result = runner.invoke(mt_cli.app, ["match", "show", "2"])

        assert "not exposed by the API" in result.output


@pytest.mark.unit
class TestLoginWithoutATerminal:
    """getpass cannot suppress echo without a TTY, so it warns, echoes the
    password and aborts. Refuse up front instead."""

    def test_non_tty_refuses_and_names_the_alternatives(self, monkeypatch):
        monkeypatch.delenv("MT_PASSWORD", raising=False)
        monkeypatch.setattr(mt_cli, "_load_env_vars", lambda: {})
        monkeypatch.setattr(mt_cli.sys.stdin, "isatty", lambda: False)

        result = runner.invoke(mt_cli.app, ["login", "tom"])

        assert result.exit_code == 1
        assert "MT_PASSWORD" in result.output
        assert "TEST_USER_PASSWORD_TOM" in result.output
        # Never reach getpass: it would echo the password into the transcript.
        assert "Password for" not in result.output

    def test_mt_password_env_is_used_without_prompting(self, monkeypatch):
        monkeypatch.setenv("MT_PASSWORD", "hunter2")
        monkeypatch.setattr(mt_cli, "_load_env_vars", lambda: {})
        monkeypatch.setattr(mt_cli.sys.stdin, "isatty", lambda: False)

        fake = MagicMock()
        fake.login.return_value = {"access_token": "t", "refresh_token": "r", "user": {"role": "admin"}}
        monkeypatch.setattr(mt_cli, "MissingTableClient", lambda **kw: fake)
        monkeypatch.setattr(mt_cli, "save_state", lambda state: None)

        result = runner.invoke(mt_cli.app, ["login", "tom"])

        assert result.exit_code == 0
        fake.login.assert_called_once_with("tom", "hunter2")
        # The password itself must never be printed.
        assert "hunter2" not in result.output


@pytest.mark.unit
class TestExpiredSession:
    """A dead token should read as advice, not as a stack trace."""

    def test_read_commands_advise_login_instead_of_tracebacking(self, client):
        from api_client import AuthenticationError

        client.get_teams.side_effect = AuthenticationError("Invalid or expired token", 401)
        client.get_seasons.side_effect = AuthenticationError("Invalid or expired token", 401)

        for argv in (
            ["team", "stats", "IFA U15"],
            ["team", "matches", "IFA U15"],
            ["player", "stats", "9"],
        ):
            result = runner.invoke(mt_cli.app, argv)
            assert result.exit_code == 1, argv
            assert "mt login" in result.output, argv
            assert "Traceback" not in result.output, argv

    def test_an_api_error_is_reported_not_raised(self, client):
        from api_client import APIError

        client.get_team_stats.side_effect = APIError("boom", 500)
        result = runner.invoke(mt_cli.app, ["team", "stats", "IFA U15"])

        assert result.exit_code == 1
        assert "API error" in result.output


@pytest.mark.unit
class TestPlayerStats:
    def test_renders_a_season_line(self, client):
        result = runner.invoke(mt_cli.app, ["player", "stats", "9"])

        assert result.exit_code == 0
        assert "2026" in result.output

    def test_uses_the_named_season(self, client):
        runner.invoke(mt_cli.app, ["player", "stats", "9", "--season", "2025"])

        client.get_roster_player_stats.assert_called_once_with(9, season_id=6)

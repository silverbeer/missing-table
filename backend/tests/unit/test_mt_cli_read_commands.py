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
    resolve_match_types,
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

# Shaped like the real /api/match-types since SB-849: ordered by display_order,
# carrying the counts_for_qualification flag that 'qualifying' is built from.
MATCH_TYPES = [
    {"id": 1, "name": "League", "counts_for_qualification": True, "display_order": 1},
    {"id": 5, "name": "Flex", "counts_for_qualification": True, "display_order": 2},
    {"id": 3, "name": "Tournament", "counts_for_qualification": False, "display_order": 3},
    {"id": 2, "name": "Friendly", "counts_for_qualification": False, "display_order": 4},
]


def _mapping(age_group_id, age_group, division_id, division, league):
    return {
        "age_groups": {"id": age_group_id, "name": age_group},
        "divisions": {"id": division_id, "name": division, "leagues": {"name": league}},
    }


TEAMS = [
    {
        "id": 11,
        "name": "IFA U15 HG",
        # Registered at U14 only, while playing U15 — the SB-852 shape.
        "team_mappings": [_mapping(2, "U14", 1, "Northeast", "Homegrown")],
    },
    {"id": 12, "name": "IFA U16 HG", "team_mappings": []},
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
            "match_type_id": 2,
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
            "match_type_id": 1,
            "match_type_name": "League",
            "home_team_name": "IFA U15 HG",
            "away_team_name": "Boston Bolts",
            "home_score": None,
            "away_score": None,
        },
        # Nested shape, as /api/matches/team/{id} also returns it — the filter
        # has to read both or Flex silently vanishes.
        {
            "id": 3,
            "match_date": "2026-09-20",
            "match_status": "scheduled",
            "match_type": {"id": 5, "name": "Flex"},
            "home_team_name": "CF Montreal",
            "away_team_name": "IFA U15 HG",
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
    client.get_age_groups.return_value = [
        {"id": 2, "name": "U14"},
        {"id": 3, "name": "U15"},
        {"id": 4, "name": "U16"},
    ]
    client.get_divisions.return_value = [
        {"id": 1, "name": "Northeast", "league_id": 1},
        {"id": 7, "name": "New England", "league_id": 2},
    ]
    # A club with a crest and brand colours — the fields a replace-not-patch
    # write blanks if the caller does not resend them (SB-824, SB-842).
    client.get_clubs.return_value = [
        {
            "id": 186,
            "name": "Houston Dynamo FC",
            "city": "Houston, TX",
            "website": "https://example.test",
            "description": "MLS Pro Academy",
            "logo_url": "https://cdn.test/186.png",
            "primary_color": "#F4911E",
            "secondary_color": "#101820",
            "pro_academy": False,
        },
        {
            "id": 13,
            "name": "NEFC",
            "city": "Boston, MA",
            "website": None,
            "description": None,
            "logo_url": None,
            "primary_color": None,
            "secondary_color": None,
            "pro_academy": True,
        },
    ]
    client.update_club_profile.side_effect = lambda cid, *a, **kw: {
        "id": cid,
        "name": a[0] if a else kw.get("name"),
        "city": a[1] if len(a) > 1 else kw.get("city"),
        "website": a[2] if len(a) > 2 else kw.get("website"),
        "description": a[3] if len(a) > 3 else kw.get("description"),
        "logo_url": a[4] if len(a) > 4 else kw.get("logo_url"),
        "primary_color": a[5] if len(a) > 5 else kw.get("primary_color"),
        "secondary_color": a[6] if len(a) > 6 else kw.get("secondary_color"),
        "pro_academy": a[7] if len(a) > 7 else kw.get("pro_academy"),
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

    def test_an_exact_name_beats_a_crowd_of_prefixes(self):
        stub = _stub_client()
        stub.get_teams.return_value = [
            {"id": 19, "name": "IFA"},
            {"id": 123, "name": "IFA Academy"},
            {"id": 183, "name": "IFA Elite Futsal 2012 Blue"},
        ]
        # "IFA" is a real team, not an ambiguous prefix.
        assert resolve_team(stub, "IFA")["id"] == 19

    def test_a_query_with_no_substring_match_suggests_near_misses(self):
        stub = _stub_client()
        stub.get_teams.return_value = [{"id": 19, "name": "IFA"}, {"id": 5, "name": "Boston Bolts"}]
        # Team names carry no age group, so "IFA U15" matches nothing at all —
        # a bare "no team" would be a dead end.
        with pytest.raises(ResolutionError) as exc:
            resolve_team(stub, "IFA U15")
        assert "Did you mean" in str(exc.value)
        assert "IFA" in str(exc.value)

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
class TestTeamMatchesCompetitionFilter:
    """SB-848: -c/--competition on `mt team matches`.

    Every case names what the schedule should show, because the failure this
    guards against is a filtered list read as a short season.
    """

    def test_defaults_to_every_competition(self, client):
        result = runner.invoke(mt_cli.app, ["team", "matches", "IFA U15"])

        assert result.exit_code == 0
        # All three: hiding a friendly by default would be the surprise.
        assert "Friendly" in result.output
        assert "League" in result.output
        assert "Flex" in result.output
        assert "All competitions" in result.output

    def test_one_competition_keeps_only_its_matches(self, client):
        result = runner.invoke(mt_cli.app, ["team", "matches", "IFA U15", "-c", "Flex"])

        assert result.exit_code == 0
        assert "CF Montreal" in result.output
        assert "Boston Bolts" not in result.output

    def test_nested_match_type_is_read_too(self, client):
        """The Flex row carries match_type: {...}, not match_type_id."""
        result = runner.invoke(mt_cli.app, ["team", "matches", "IFA U15", "-c", "Flex"])

        assert "1 of 1" in result.output

    def test_the_filter_is_named_in_the_title(self, client):
        result = runner.invoke(mt_cli.app, ["team", "matches", "IFA U15", "-c", "League"])

        # A one-match list must say it is one League match, not one match.
        assert "League" in result.output
        assert "1 of 1" in result.output

    def test_qualifying_is_the_union_of_the_flagged_types(self, client):
        result = runner.invoke(mt_cli.app, ["team", "matches", "IFA U15", "-c", "qualifying"])

        assert result.exit_code == 0
        # League + Flex, not the friendly.
        assert "2 of 2" in result.output
        assert "Qualifying" in result.output

    def test_qualifying_reads_the_flag_rather_than_a_hardcoded_list(self, client):
        """Unflag Flex and 'qualifying' must shrink to League on its own."""
        client.get_match_types.return_value = [{**t, "counts_for_qualification": t["id"] == 1} for t in MATCH_TYPES]
        result = runner.invoke(mt_cli.app, ["team", "matches", "IFA U15", "-c", "qualifying"])

        assert result.exit_code == 0
        assert "1 of 1" in result.output

    def test_all_is_the_same_as_no_filter(self, client):
        result = runner.invoke(mt_cli.app, ["team", "matches", "IFA U15", "-c", "all"])

        assert result.exit_code == 0
        assert "3 of 3" in result.output

    def test_unknown_competition_lists_the_known_ones(self, client):
        result = runner.invoke(mt_cli.app, ["team", "matches", "IFA U15", "-c", "cup"])

        assert result.exit_code == 1
        assert "League" in result.output and "Flex" in result.output

    def test_a_competition_with_no_matches_says_so_without_implying_none_exist(self, client):
        result = runner.invoke(mt_cli.app, ["team", "matches", "IFA U15", "-c", "Tournament"])

        assert result.exit_code == 0
        assert "No Tournament matches" in result.output
        assert "drop -c" in result.output

    def test_no_competition_flagged_is_an_error_not_an_empty_list(self, client):
        client.get_match_types.return_value = [{**t, "counts_for_qualification": False} for t in MATCH_TYPES]
        result = runner.invoke(mt_cli.app, ["team", "matches", "IFA U15", "-c", "qualifying"])

        assert result.exit_code == 1
        assert "qualification" in result.output


@pytest.mark.unit
class TestResolveMatchTypes:
    def test_no_name_means_every_competition(self):
        assert resolve_match_types(_stub_client()) is None

    def test_all_means_every_competition(self):
        assert resolve_match_types(_stub_client(), "all") is None

    def test_a_name_resolves_to_one_type(self):
        assert [t["id"] for t in resolve_match_types(_stub_client(), "Flex")] == [5]

    def test_qualifying_spans_the_flagged_types(self):
        assert [t["id"] for t in resolve_match_types(_stub_client(), "qualifying")] == [1, 5]

    def test_qualifying_is_rejected_where_only_one_type_fits(self):
        """team stats takes a single match_type_id — say so rather than 404 on 'qualifying'."""
        with pytest.raises(ResolutionError) as exc:
            resolve_match_type(_stub_client(), "qualifying")
        assert "mt team matches" in str(exc.value)


@pytest.mark.unit
class TestCompetitions:
    def test_lists_the_competitions_and_which_qualify(self, client):
        result = runner.invoke(mt_cli.app, ["competitions"])

        assert result.exit_code == 0
        assert "League" in result.output
        assert "Flex" in result.output
        assert "Friendly" in result.output

    def test_names_the_extra_selectors(self, client):
        result = runner.invoke(mt_cli.app, ["competitions"])

        assert "qualifying" in result.output
        assert "all" in result.output

    def test_no_competitions_configured_is_not_a_crash(self, client):
        client.get_match_types.return_value = []
        result = runner.invoke(mt_cli.app, ["competitions"])

        assert result.exit_code == 0
        assert "No competitions configured" in result.output


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
class TestLoginViaOnePassword:
    """The prod env file holds no password, so op is the path that makes a
    non-interactive prod login possible at all."""

    def _no_other_sources(self, monkeypatch):
        monkeypatch.delenv("MT_PASSWORD", raising=False)
        monkeypatch.setattr(mt_cli, "_load_env_vars", lambda: {})
        monkeypatch.setattr(mt_cli.sys.stdin, "isatty", lambda: False)

    def _fake_op(self, monkeypatch, returncode=0, stdout="s3cret"):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return MagicMock(returncode=returncode, stdout=stdout)

        monkeypatch.setattr(mt_cli.subprocess, "run", fake_run)
        return calls

    def _fake_client(self, monkeypatch):
        # get_base_url reads backend/.env.<env>, which CI does not have — it
        # exits 1 rather than raising, so the test saw a clean failure with no
        # message. Stub it, and the state file with it.
        monkeypatch.setattr(mt_cli, "get_base_url", lambda: "http://test")
        monkeypatch.setattr(mt_cli, "load_state", lambda: mt_cli.CLIState())
        fake = MagicMock()
        fake.login.return_value = {"access_token": "t", "refresh_token": "r", "user": {"role": "admin"}}
        monkeypatch.setattr(mt_cli, "MissingTableClient", lambda **kw: fake)
        monkeypatch.setattr(mt_cli, "save_state", lambda state: None)
        return fake

    def test_reads_the_password_from_op(self, monkeypatch):
        self._no_other_sources(monkeypatch)
        calls = self._fake_op(monkeypatch)
        fake = self._fake_client(monkeypatch)

        result = runner.invoke(mt_cli.app, ["login", "tom"])

        assert result.exit_code == 0
        assert calls[0][:2] == ["op", "read"]
        fake.login.assert_called_once_with("tom", "s3cret")
        # The reference may be shown; the secret never.
        assert "s3cret" not in result.output

    def test_op_failure_falls_through_rather_than_exploding(self, monkeypatch):
        self._no_other_sources(monkeypatch)
        self._fake_op(monkeypatch, returncode=1, stdout="")

        result = runner.invoke(mt_cli.app, ["login", "tom"])

        # Locked vault is an ordinary situation: advise, do not stack-trace.
        assert result.exit_code == 1
        assert "MT_PASSWORD" in result.output

    def test_missing_op_binary_falls_through(self, monkeypatch):
        self._no_other_sources(monkeypatch)

        def boom(*a, **k):
            raise FileNotFoundError("op")

        monkeypatch.setattr(mt_cli.subprocess, "run", boom)

        result = runner.invoke(mt_cli.app, ["login", "tom"])

        assert result.exit_code == 1
        assert "Traceback" not in result.output

    def test_reference_defaults_to_the_env_item(self, monkeypatch):
        monkeypatch.delenv("MT_OP_ITEM", raising=False)
        monkeypatch.setattr(mt_cli, "mt_config_get", lambda key, default="": "")
        monkeypatch.setattr(mt_cli, "get_current_env", lambda: "prod")

        assert mt_cli.op_reference("tom") == "op://agents/mt-prod/credential"

    def test_reference_is_overridable(self, monkeypatch):
        monkeypatch.setenv("MT_OP_ITEM", "op://Work/mt-{env}/{user}-password")
        monkeypatch.setattr(mt_cli, "get_current_env", lambda: "dev")

        assert mt_cli.op_reference("gabe") == "op://Work/mt-dev/gabe-password"


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
        monkeypatch.setattr(mt_cli, "get_base_url", lambda: "http://test")
        monkeypatch.setattr(mt_cli, "load_state", lambda: mt_cli.CLIState())

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


@pytest.mark.unit
class TestTeamMappingCommands:
    """SB-852: registrations were only editable through the Admin UI.

    The endpoints and client methods existed; nothing in the CLI reached them.
    `mt team create` writes mappings, but only for a brand-new team — there was
    no way to add an age group to an existing one.
    """

    def test_list_shows_the_registrations(self, client):
        result = runner.invoke(mt_cli.app, ["team", "mapping", "list", "IFA U15"])

        assert result.exit_code == 0
        assert "U14" in result.output
        assert "Northeast" in result.output
        assert "Homegrown" in result.output

    def test_no_registrations_says_what_that_costs(self, client):
        result = runner.invoke(mt_cli.app, ["team", "mapping", "list", "IFA U16"])

        assert result.exit_code == 0
        # Not just "none" — the consequence is the part nobody knows.
        assert "team picker" in result.output

    def test_add_resolves_names_to_ids(self, client):
        result = runner.invoke(
            mt_cli.app, ["team", "mapping", "add", "IFA U15", "--age", "U15", "--division", "Northeast"]
        )

        assert result.exit_code == 0
        client.create_team_mapping.assert_called_once_with(11, 3, 1)

    def test_add_reprints_the_registrations(self, client):
        """The Admin UI shows a stale list after writing, which reads as a
        failed save and invites a duplicate attempt. Prove it landed instead."""
        result = runner.invoke(
            mt_cli.app, ["team", "mapping", "add", "IFA U15", "--age", "U15", "--division", "Northeast"]
        )

        assert "Registrations" in result.output

    def test_remove_resolves_names_to_ids(self, client):
        result = runner.invoke(
            mt_cli.app, ["team", "mapping", "remove", "IFA U15", "--age", "U14", "--division", "Northeast"]
        )

        assert result.exit_code == 0
        client.delete_team_mapping.assert_called_once_with(11, 2, 1)

    def test_an_unknown_age_group_lists_the_known_ones(self, client):
        result = runner.invoke(
            mt_cli.app, ["team", "mapping", "add", "IFA U15", "--age", "U99", "--division", "Northeast"]
        )

        assert result.exit_code == 1
        assert "U15" in result.output
        client.create_team_mapping.assert_not_called()

    def test_an_unknown_division_lists_the_known_ones(self, client):
        result = runner.invoke(
            mt_cli.app, ["team", "mapping", "add", "IFA U15", "--age", "U15", "--division", "Atlantis"]
        )

        assert result.exit_code == 1
        assert "Northeast" in result.output
        client.create_team_mapping.assert_not_called()


@pytest.mark.unit
class TestClubProAcademy:
    """SB-872: `mt club create` takes --pro-academy; nothing could set it after.

    PUT /api/clubs/{id} is a replace, not a patch, so the command exists mostly
    to get the read-modify-write right. A caller who resends a subset blanks the
    crest and brand colours every IG card reads.
    """

    def test_it_flags_a_club(self, client):
        result = runner.invoke(mt_cli.app, ["club", "set-pro-academy", "Houston Dynamo FC"])

        assert result.exit_code == 0
        assert client.update_club_profile.call_args.args[8] is True

    def test_the_crest_and_colours_survive(self, client):
        """The regression SB-824 and SB-842 are both about."""
        runner.invoke(mt_cli.app, ["club", "set-pro-academy", "Houston Dynamo FC"])

        sent = client.update_club_profile.call_args.args
        assert sent[5] == "https://cdn.test/186.png"  # logo_url
        assert sent[6] == "#F4911E"  # primary
        assert sent[7] == "#101820"  # secondary

    def test_description_and_website_survive(self, client):
        runner.invoke(mt_cli.app, ["club", "set-pro-academy", "Houston Dynamo FC"])

        sent = client.update_club_profile.call_args.args
        assert sent[3] == "https://example.test"
        assert sent[4] == "MLS Pro Academy"

    def test_off_unflags(self, client):
        result = runner.invoke(mt_cli.app, ["club", "set-pro-academy", "NEFC", "--off"])

        assert result.exit_code == 0
        assert client.update_club_profile.call_args.args[8] is False

    def test_already_flagged_is_a_no_op_not_an_error(self, client):
        result = runner.invoke(mt_cli.app, ["club", "set-pro-academy", "NEFC"])

        assert result.exit_code == 0
        assert "already" in result.output
        client.update_club_profile.assert_not_called()

    def test_an_unknown_club_writes_nothing(self, client):
        result = runner.invoke(mt_cli.app, ["club", "set-pro-academy", "Nowhere United"])

        assert result.exit_code == 1
        client.update_club_profile.assert_not_called()

    def test_show_reports_the_fields_a_write_must_preserve(self, client):
        result = runner.invoke(mt_cli.app, ["club", "show", "Houston Dynamo FC"])

        assert result.exit_code == 0
        assert "#F4911E" in result.output
        assert "MLS Pro Academy" in result.output

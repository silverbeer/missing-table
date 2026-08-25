"""mt_cli team/club write commands (SB-824).

`team` was read-only, so a season's identity changes had to be clicked through
Admin forms. The interesting part is not that the commands exist — it is the two
traps they route around:

1. PUT /api/teams/{id} takes TeamUpdate, whose club_id defaults to None. Sending
   a rename without club_id silently detaches the team from its club, taking the
   crest and colours the IG cards read with it.
2. Creating must go through the API, because add_team derives league_id from the
   division and writes a team_mappings row per age group.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

runner = CliRunner()

TEAM_34 = {
    "id": 34,
    "name": "New York Red Bulls",
    "city": "",
    "club_id": 19,
    "academy_team": False,
}
CLUBS = [
    {"id": 19, "name": "New York Red Bulls", "city": "Harrison, NJ"},
    {"id": 160, "name": "Long Island Soccer Club", "city": "Long Island, NY"},
]


def _client():
    client = MagicMock()
    client.get_team.return_value = TEAM_34
    client.get_teams.return_value = [TEAM_34]
    client.get_clubs.return_value = CLUBS
    client.get_divisions.return_value = [{"id": 1, "name": "Northeast"}]
    client.get_age_groups.return_value = [
        {"id": 1, "name": "U13"},
        {"id": 2, "name": "U14"},
        {"id": 7, "name": "U19"},
    ]
    client.update_team_profile.return_value = {"id": 34, "name": "Red Bull New York"}
    client.create_team.return_value = {"team": {"id": 900, "name": "Connecticut United FC"}}
    client.create_club.return_value = {"id": 901, "name": "Connecticut United FC"}
    client.update_club.return_value = {"id": 19, "name": "Red Bull New York"}
    client.add_team_alias.return_value = {"success": True}
    client.get_team_aliases.return_value = {"aliases": []}
    return client


def _run(args, client):
    import mt_cli

    with patch.object(mt_cli, "get_client", return_value=(client, MagicMock())):
        return runner.invoke(mt_cli.app, args)


@pytest.mark.unit
class TestTeamRename:
    def test_rename_preserves_club_city_and_academy_flag(self):
        # The trap: TeamUpdate.club_id defaults to None, so a rename that omits
        # it detaches the team from its club.
        client = _client()
        result = _run(["team", "rename", "34", "--name", "Red Bull New York", "--yes"], client)

        assert result.exit_code == 0, result.output
        client.update_team_profile.assert_called_once()
        kwargs = client.update_team_profile.call_args.kwargs
        assert kwargs["name"] == "Red Bull New York"
        assert kwargs["club_id"] == 19, "rename must not detach the club"
        assert kwargs["city"] == ""
        assert kwargs["academy_team"] is False

    def test_rename_to_the_same_name_is_a_no_op(self):
        client = _client()
        result = _run(["team", "rename", "34", "--name", "New York Red Bulls", "--yes"], client)

        assert result.exit_code == 0
        client.update_team_profile.assert_not_called()

    def test_rename_suggests_recording_the_former_name(self):
        # A rename without an alias leaves the old string unresolvable, which is
        # how a stale feed re-splits a club's history.
        client = _client()
        result = _run(["team", "rename", "34", "--name", "Red Bull New York", "--yes"], client)

        assert "alias add" in result.output
        assert "former_name" in result.output

    def test_declining_the_confirmation_changes_nothing(self):
        client = _client()
        result = _run(
            ["team", "rename", "34", "--name", "Red Bull New York"],
            client,
        )

        assert result.exit_code == 1
        client.update_team_profile.assert_not_called()


@pytest.mark.unit
class TestTeamSetClub:
    def test_repoints_the_club_and_keeps_the_name(self):
        client = _client()
        result = _run(["team", "set-club", "34", "--club", "160", "--yes"], client)

        assert result.exit_code == 0, result.output
        kwargs = client.update_team_profile.call_args.kwargs
        assert kwargs["club_id"] == 160
        assert kwargs["name"] == "New York Red Bulls"


@pytest.mark.unit
class TestTeamCreate:
    def test_creates_one_row_with_every_age_group(self):
        # teams.name is globally unique, so a row per age group is impossible.
        # One row, N team_mappings — which the API does and raw SQL would not.
        client = _client()
        result = _run(
            [
                "team",
                "create",
                "--name",
                "Connecticut United FC",
                "--city",
                "Hartford",
                "--division",
                "Northeast",
                "-a",
                "U13",
                "-a",
                "U14",
                "-a",
                "U19",
            ],
            client,
        )

        assert result.exit_code == 0, result.output
        payload = client.create_team.call_args.args[0]
        assert payload.name == "Connecticut United FC"
        assert payload.division_id == 1
        assert payload.age_group_ids == [1, 2, 7], "U19 is id 7; there is no id 6"

    def test_resolves_division_by_name(self):
        client = _client()
        _run(["team", "create", "--name", "X", "--division", "Northeast", "-a", "U13"], client)

        assert client.create_team.call_args.args[0].division_id == 1

    def test_unknown_division_lists_the_real_ones(self):
        client = _client()
        result = _run(["team", "create", "--name", "X", "--division", "Nowhere", "-a", "U13"], client)

        assert result.exit_code == 1
        assert "Northeast" in result.output
        client.create_team.assert_not_called()


@pytest.mark.unit
class TestClubCommands:
    def test_rename_club(self):
        client = _client()
        result = _run(["club", "rename", "19", "--name", "Red Bull New York", "--yes"], client)

        assert result.exit_code == 0, result.output
        client.update_club.assert_called_once()
        assert client.update_club.call_args.kwargs["name"] == "Red Bull New York"

    def test_club_resolves_by_name_not_just_id(self):
        client = _client()
        result = _run(["club", "rename", "Long Island Soccer Club", "--name", "The Island FC West", "--yes"], client)

        assert result.exit_code == 0, result.output
        assert client.update_club.call_args.args[0] == 160

    def test_ambiguous_club_name_refuses_rather_than_picking(self):
        client = _client()
        client.get_clubs.return_value = [
            {"id": 1, "name": "Island FC East"},
            {"id": 2, "name": "Island FC West"},
        ]
        result = _run(["club", "rename", "Island FC", "--name", "X", "--yes"], client)

        assert result.exit_code == 1
        client.update_club.assert_not_called()

    def test_create_club(self):
        client = _client()
        result = _run(["club", "create", "--name", "The Island FC East"], client)

        assert result.exit_code == 0, result.output
        assert client.create_club.call_args.kwargs["name"] == "The Island FC East"


@pytest.mark.unit
class TestAliasCommands:
    def test_add_former_name_alias(self):
        client = _client()
        result = _run(
            ["team", "alias", "add", "34", "--alias", "New York Red Bulls", "--kind", "former_name"],
            client,
        )

        assert result.exit_code == 0, result.output
        kwargs = client.add_team_alias.call_args.kwargs
        assert kwargs["external_name"] == "New York Red Bulls"
        assert kwargs["kind"] == "former_name"

    def test_rejects_an_invented_kind(self):
        # kind is constrained in the database; failing here beats a 500.
        client = _client()
        result = _run(["team", "alias", "add", "34", "--alias", "X", "--kind", "nonsense"], client)

        assert result.exit_code == 1
        client.add_team_alias.assert_not_called()

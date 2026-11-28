"""mt team merge / mt club merge / mt club logo-gaps (SB-1822, SB-1815).

The contract: always a dry run first, never a real run while blockers exist,
and a real run only after confirmation or --yes.
"""

from unittest.mock import MagicMock, call, patch

import pytest
from typer.testing import CliRunner

runner = CliRunner()

TEAMS = [{"id": 581, "name": "City SC San Diego"}, {"id": 937, "name": "City SC - San Diego"}]
CLUBS = [{"id": 247, "name": "City SC Old"}, {"id": 446, "name": "City SC"}]

CLEAN = {
    "dry_run": True,
    "tables": {"matches": {"moved": 4, "dropped": 1}, "team_mappings": {"moved": 0, "dropped": 0}},
    "blockers": [],
    "complete": True,
    "alias": "added",
    "copied": ["logo_url"],
}
BLOCKED = {
    "dry_run": True,
    "tables": {},
    "blockers": [{"kind": "self_match", "match_id": 77, "detail": "the two teams play each other"}],
    "complete": False,
}


def _client(preview=CLEAN):
    client = MagicMock()
    client.get_teams.return_value = TEAMS
    client.get_clubs.return_value = CLUBS
    real = dict(preview, dry_run=False)
    client.merge_team.side_effect = lambda f, i, dry_run=True: preview if dry_run else real
    client.merge_club.side_effect = lambda f, i, dry_run=True: preview if dry_run else real
    return client


def _run(args, client, **kw):
    import mt_cli

    with patch.object(mt_cli, "get_client", return_value=(client, MagicMock())):
        return runner.invoke(mt_cli.app, args, **kw)


@pytest.mark.unit
class TestTeamMerge:
    def test_blockers_refuse_and_never_run_for_real(self):
        client = _client(BLOCKED)
        result = _run(["team", "merge", "581", "937", "--yes"], client)
        assert result.exit_code == 1
        assert "self_match" in result.output
        assert client.merge_team.call_args_list == [call(581, 937, dry_run=True)]

    def test_incomplete_dry_run_refuses(self):
        client = _client(dict(CLEAN, complete=False))
        result = _run(["team", "merge", "581", "937", "--yes"], client)
        assert result.exit_code == 1
        assert client.merge_team.call_args_list == [call(581, 937, dry_run=True)]

    def test_dry_run_first_then_real_with_yes(self):
        client = _client()
        result = _run(["team", "merge", "581", "937", "--yes"], client)
        assert result.exit_code == 0, result.output
        assert client.merge_team.call_args_list == [call(581, 937, dry_run=True), call(581, 937, dry_run=False)]
        assert "matches" in result.output
        assert "former_name alias" in result.output

    def test_declining_confirmation_changes_nothing(self):
        client = _client()
        result = _run(["team", "merge", "581", "937"], client, input="n\n")
        assert result.exit_code == 1
        assert client.merge_team.call_args_list == [call(581, 937, dry_run=True)]

    def test_confirming_runs_for_real(self):
        client = _client()
        result = _run(["team", "merge", "581", "937"], client, input="y\n")
        assert result.exit_code == 0
        assert client.merge_team.call_args_list[-1] == call(581, 937, dry_run=False)

    def test_same_team_refused_before_any_call(self):
        client = _client()
        result = _run(["team", "merge", "581", "City SC San Diego", "--yes"], client)
        assert result.exit_code == 1
        client.merge_team.assert_not_called()

    def test_exact_name_case_insensitive_resolves(self):
        client = _client()
        result = _run(["team", "merge", "city sc san diego", "CITY SC - SAN DIEGO", "--yes"], client)
        assert result.exit_code == 0, result.output
        assert client.merge_team.call_args_list[0] == call(581, 937, dry_run=True)

    # "City SC San" is a unique substring of #581: other commands accept it,
    # a merge must not.
    @pytest.mark.parametrize("partial", ["City SC San", "San Diego"])
    def test_partial_name_is_refused_for_a_merge(self, partial):
        client = _client()
        result = _run(["team", "merge", partial, "937", "--yes"], client)
        assert result.exit_code == 1
        assert "exact" in result.output
        client.merge_team.assert_not_called()

    def test_duplicate_exact_names_need_the_id(self):
        client = _client()
        client.get_teams.return_value = [*TEAMS, {"id": 999, "name": "City SC San Diego"}]
        result = _run(["team", "merge", "City SC San Diego", "937", "--yes"], client)
        assert result.exit_code == 1
        assert "use the id" in result.output
        client.merge_team.assert_not_called()

    def test_dry_run_error_is_printed(self):
        error = {"sqlstate": "23514", "table": "matches", "constraint": "matches_check"}
        client = _client(dict(BLOCKED, error=error))
        result = _run(["team", "merge", "581", "937", "--yes"], client)
        assert result.exit_code == 1
        assert "23514" in result.output
        assert "matches_check" in result.output
        assert client.merge_team.call_count == 1

    def test_unknown_team_refused(self):
        client = _client()
        result = _run(["team", "merge", "581", "99999", "--yes"], client)
        assert result.exit_code == 1
        client.merge_team.assert_not_called()


@pytest.mark.unit
class TestClubMerge:
    def test_blockers_refuse(self):
        client = _client(dict(BLOCKED, blockers=[{"kind": "team_name_conflict", "detail": "x"}]))
        result = _run(["club", "merge", "247", "446", "--yes"], client)
        assert result.exit_code == 1
        assert client.merge_club.call_args_list == [call(247, 446, dry_run=True)]

    def test_dry_run_then_real_and_reports_copied(self):
        client = _client()
        result = _run(["club", "merge", "247", "446", "-y"], client)
        assert result.exit_code == 0, result.output
        assert client.merge_club.call_args_list == [call(247, 446, dry_run=True), call(247, 446, dry_run=False)]
        assert "logo_url" in result.output

    def test_partial_club_name_is_refused(self):
        client = _client()
        result = _run(["club", "merge", "Old", "446", "--yes"], client)
        assert result.exit_code == 1
        client.merge_club.assert_not_called()

    def test_exact_club_name_resolves(self):
        client = _client()
        result = _run(["club", "merge", "city sc old", "City SC", "--yes"], client)
        assert result.exit_code == 0, result.output
        assert client.merge_club.call_args_list[0] == call(247, 446, dry_run=True)

    def test_declined(self):
        client = _client()
        result = _run(["club", "merge", "247", "446"], client, input="n\n")
        assert result.exit_code == 1
        assert client.merge_club.call_count == 1


@pytest.mark.unit
class TestLogoGapsCommand:
    def test_empty_report_says_none_not_zero_rows_of_data(self):
        client = MagicMock()
        client.get_club_logo_gaps.return_value = {
            "season_id": 7,
            "teams_without_club": [],
            "clubs_without_logo": [],
            "clubs_external_logo": [],
        }
        result = _run(["club", "logo-gaps"], client)
        assert result.exit_code == 0
        assert result.output.count("none") == 3

    def test_lists_each_gap(self):
        client = MagicMock()
        client.get_club_logo_gaps.return_value = {
            "season_id": 7,
            "teams_without_club": [{"id": 40, "name": "Orphan", "match_count": 2}],
            "clubs_without_logo": [{"id": 2, "name": "Bare FC"}],
            "clubs_external_logo": [
                {"id": 3, "name": "Linked FC", "logo_url": "https://e.test/x.png", "host": "e.test"}
            ],
        }
        result = _run(["club", "logo-gaps", "--all"], client)
        assert result.exit_code == 0
        for text in ("Orphan", "Bare FC", "Linked FC", "e.test"):
            assert text in result.output
        client.get_club_logo_gaps.assert_called_once_with(season_id=None, include_all=True)

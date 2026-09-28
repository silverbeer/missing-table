"""Deleting a user, and the things that must not be deletable (SB-1132).

The endpoint existed and was admin-only, but had none of the guardrails the
edit endpoint has. It would let an admin remove their own account mid-session
or delete the last admin outright — locking everyone out of the screen that
could undo it.

It is also more destructive than it looks. Seven tables cascade, and
player_team_history is one of them: deleting a player takes their roster
history, which is precisely the user-generated data MT exists to collect and
cannot reconstruct.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


@pytest.fixture
def guard():
    import app as app_module

    return app_module._guard_user_deletion


ADMIN = {"user_id": "admin-1", "username": "tom"}


class TestTheDeletionsThatAreRefused:
    def test_an_admin_cannot_delete_themselves(self, guard):
        with pytest.raises(HTTPException) as exc:
            guard({"id": "admin-1", "role": "admin"}, ADMIN)
        assert exc.value.status_code == 400
        assert "your own account" in exc.value.detail

    def test_the_last_admin_cannot_be_deleted(self, guard):
        with patch("app.auth_service_client") as client:
            client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "admin-2"}]
            )
            with pytest.raises(HTTPException) as exc:
                guard({"id": "admin-2", "role": "admin"}, ADMIN)
            assert "last admin" in exc.value.detail

    def test_an_admin_may_be_deleted_when_another_remains(self, guard):
        with patch("app.auth_service_client") as client:
            client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "admin-1"}, {"id": "admin-2"}]
            )
            guard({"id": "admin-2", "role": "admin"}, ADMIN)  # does not raise

    def test_an_ordinary_user_needs_no_admin_count(self, guard):
        with patch("app.auth_service_client") as client:
            guard({"id": "u-9", "role": "team-fan"}, ADMIN)
            client.table.assert_not_called()


class TestThePreflight:
    @pytest.fixture
    def preflight(self):
        import app as app_module

        return app_module._delete_preflight

    def _counts(self, client, mapping):
        """Return a row count per table name."""

        def table(name):
            t = MagicMock()
            t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                count=mapping.get(name, 0)
            )
            return t

        client.table.side_effect = table

    def test_it_reports_what_would_be_destroyed(self, preflight):
        with patch("app.auth_service_client") as client:
            self._counts(client, {"player_team_history": 3, "user_team_follows": 2})
            result = preflight("u-1")

        destroys = {d["what"]: d["count"] for d in result["destroys"]}
        assert destroys["roster history entries"] == 3
        assert destroys["followed teams"] == 2

    def test_a_table_with_nothing_in_it_is_not_listed(self, preflight):
        """A confirmation listing seven zeroes teaches an admin to skim."""
        with patch("app.auth_service_client") as client:
            self._counts(client, {"player_team_history": 1})
            result = preflight("u-1")
        assert len(result["destroys"]) == 1

    def test_it_separates_what_is_kept_from_what_is_destroyed(self, preflight):
        with patch("app.auth_service_client") as client:
            self._counts(client, {"player_team_history": 2, "match_events": 5})
            result = preflight("u-1")

        assert [d["what"] for d in result["destroys"]] == ["roster history entries"]
        assert [o["what"] for o in result["orphans"]] == ["match events they recorded"]

    def test_sent_support_email_blocks_the_delete(self, preflight):
        """email_messages.sent_by_user_id is NO ACTION: the database refuses
        it, and unhandled that surfaces as a 500."""
        with patch("app.auth_service_client") as client:
            self._counts(client, {"email_messages": 1})
            result = preflight("u-1")
        assert result["blockers"][0]["count"] == 1

    def test_a_table_that_cannot_be_counted_does_not_hide_the_others(self, preflight):
        with patch("app.auth_service_client") as client:

            def table(name):
                t = MagicMock()
                if name == "player_team_history":
                    t.select.side_effect = Exception("permission denied")
                else:
                    t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                        count=4 if name == "user_team_follows" else 0
                    )
                return t

            client.table.side_effect = table
            result = preflight("u-1")

        assert [d["what"] for d in result["destroys"]] == ["followed teams"]

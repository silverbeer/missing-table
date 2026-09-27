"""An address is found however it is capitalised (SB-1130).

Eric could not reset his password. His profile had a verified address, Resend
was healthy, and nothing failed — he typed his address with a capital letter
and the lookup matched exactly, so it found nobody. The endpoint then
returned its deliberately generic response, which makes a case mismatch
indistinguishable from having no account at all.

Normalising on read alone would leave existing mixed-case rows unfindable;
on write alone would leave existing rows broken. Both, and they have to agree
with each other and with the admin editor.
"""

from unittest.mock import MagicMock

import pytest

from models.auth import UserSignup


class TestTheLookupNormalises:
    @pytest.fixture
    def dao(self):
        from dao.player_dao import PlayerDAO

        d = PlayerDAO.__new__(PlayerDAO)
        d.client = MagicMock()
        d.client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "u-1", "username": "eric_ifa", "email": "ericgsenk@gmail.com"}]
        )
        return d

    def _searched_for(self, dao):
        """The value actually handed to the query."""
        return dao.client.table.return_value.select.return_value.eq.call_args[0][1]

    def test_a_capitalised_address_is_lowercased(self, dao):
        dao.get_user_for_password_reset("Ericgsenk@gmail.com")
        assert self._searched_for(dao) == "ericgsenk@gmail.com"

    def test_a_shouting_address_is_lowercased(self, dao):
        dao.get_user_for_password_reset("ERICGSENK@GMAIL.COM")
        assert self._searched_for(dao) == "ericgsenk@gmail.com"

    def test_surrounding_whitespace_is_stripped(self, dao):
        """Pasted addresses arrive with a trailing space more often than not."""
        dao.get_user_for_password_reset("  Ericgsenk@gmail.com  ")
        assert self._searched_for(dao) == "ericgsenk@gmail.com"

    def test_a_username_is_still_lowercased_and_not_treated_as_an_address(self, dao):
        dao.get_user_for_password_reset("Eric_IFA")
        column = dao.client.table.return_value.select.return_value.eq.call_args[0][0]
        assert column == "username"
        assert self._searched_for(dao) == "eric_ifa"


class TestSignupNormalises:
    def test_the_stored_address_is_lowercase(self):
        user = UserSignup(
            username="newparent",
            password="correct-horse-battery",  # pragma: allowlist secret
            email="Foo@Bar.COM",
        )
        assert user.email == "foo@bar.com"

    def test_surrounding_whitespace_is_stripped(self):
        user = UserSignup(
            username="newparent",
            password="correct-horse-battery",  # pragma: allowlist secret
            email="  foo@bar.com ",
        )
        assert user.email == "foo@bar.com"

    def test_an_address_is_still_required(self):
        with pytest.raises(ValueError):
            UserSignup(username="newparent", password="correct-horse-battery", email=""),  # pragma: allowlist secret

    def test_signup_and_the_admin_editor_agree(self):
        """Two doors onto the same column: if they normalise differently, the
        same address is stored two ways and one of them cannot be found."""
        import app as app_module

        signed_up = UserSignup(
            username="newparent",
            password="correct-horse-battery",  # pragma: allowlist secret
            email="Foo@Bar.COM",
        ).email

        from unittest.mock import patch

        with patch("app.auth_service_client") as client:
            client.table.return_value.select.return_value.eq.return_value.neq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            client.auth.admin.list_users.return_value = []
            set_by_admin = app_module._validated_admin_email("Foo@Bar.COM", "u-1")

        assert signed_up == set_by_admin

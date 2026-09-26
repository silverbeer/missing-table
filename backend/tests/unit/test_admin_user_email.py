"""An admin setting a user's email (SB-1128).

Most accounts have no contact address — MT keys on username and synthesises
`username@missingtable.local` for Supabase — so until now a missing address
could only be fixed by the user, through the forgot-password flow.

Setting someone else's address is a sharper act than it looks: whoever
controls the address can take the account through a password reset. It is
allowed, because an admin can already change roles, but the guards below are
what keep it from being an accident.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


@pytest.fixture
def validate():
    import app as app_module

    return app_module._validated_admin_email


class TestWhatIsStored:
    def test_an_address_is_normalised(self, validate):
        with patch("app.auth_service_client") as client:
            client.table.return_value.select.return_value.eq.return_value.neq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            client.auth.admin.list_users.return_value = []
            assert validate("  Parent@Example.COM ", "u-1") == "parent@example.com"

    def test_an_empty_string_clears_it(self, validate):
        assert validate("", "u-1") is None
        assert validate("   ", "u-1") is None

    def test_none_clears_it(self, validate):
        assert validate(None, "u-1") is None


class TestWhatIsRefused:
    def test_a_synthetic_sign_in_identity(self, validate):
        """`.local` is reserved for mDNS. Storing one would make an account
        look reachable when nothing can be delivered to it."""
        with pytest.raises(HTTPException) as exc:
            validate("gabe35@missingtable.local", "u-1")
        assert exc.value.status_code == 400
        assert "sign-in identity" in exc.value.detail

    @pytest.mark.parametrize("bad", ["notanemail", "@example.com", "parent@"])
    def test_a_malformed_address(self, validate, bad):
        with pytest.raises(HTTPException) as exc:
            validate(bad, "u-1")
        assert exc.value.status_code == 400

    def test_an_address_another_profile_holds(self, validate):
        with patch("app.auth_service_client") as client:
            client.table.return_value.select.return_value.eq.return_value.neq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": "u-2", "username": "tom_ifa"}]
            )
            with pytest.raises(HTTPException) as exc:
                validate("parent@example.com", "u-1")
            # Naming the account is the difference between a message an admin
            # can act on and a 500 they cannot.
            assert "tom_ifa" in exc.value.detail

    def test_an_address_another_login_holds(self, validate):
        """user_profiles.email is UNIQUE, but that constraint cannot see an
        address sitting on auth.users for a Google account whose profile
        email is null — which is how the SB-1124 duplicates arose."""
        with patch("app.auth_service_client") as client:
            client.table.return_value.select.return_value.eq.return_value.neq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            other = MagicMock(id="u-9", email="parent@example.com")
            client.auth.admin.list_users.return_value = [other]

            with pytest.raises(HTTPException) as exc:
                validate("parent@example.com", "u-1")
            assert "sign in to another account" in exc.value.detail

    def test_the_account_may_keep_its_own_address(self, validate):
        """Re-saving an unchanged address is not a clash with itself."""
        with patch("app.auth_service_client") as client:
            client.table.return_value.select.return_value.eq.return_value.neq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            client.auth.admin.list_users.return_value = [MagicMock(id="u-1", email="parent@example.com")]
            assert validate("parent@example.com", "u-1") == "parent@example.com"


class TestWhenTheAuthCheckFails:
    def test_a_legitimate_edit_is_not_blocked(self, validate, caplog):
        """Enumerating auth users can fail; the UNIQUE constraint still
        stands, so an outage there must not stop an admin fixing an address."""
        with patch("app.auth_service_client") as client:
            client.table.return_value.select.return_value.eq.return_value.neq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            client.auth.admin.list_users.side_effect = Exception("supabase down")

            assert validate("parent@example.com", "u-1") == "parent@example.com"
        assert "Could not check auth.users" in caplog.text

    def test_the_address_is_not_logged(self, validate, caplog):
        with patch("app.auth_service_client") as client:
            client.table.return_value.select.return_value.eq.return_value.neq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            client.auth.admin.list_users.side_effect = Exception("supabase down")
            validate("parent@example.com", "u-1")
        assert "parent@example.com" not in caplog.text

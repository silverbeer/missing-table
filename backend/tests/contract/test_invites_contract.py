"""Contract tests for invite endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient


@pytest.mark.contract
class TestInviteValidationContract:
    """Test invite validation endpoint contracts."""

    def test_validate_invalid_invite(self, api_client: MissingTableClient):
        """Test validating an invalid invite code."""
        from api_client import APIError

        with pytest.raises(APIError):
            api_client.validate_invite("INVALID_CODE_123")

    def test_get_my_invites_requires_auth(self, api_client: MissingTableClient):
        """Test getting my invites requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_my_invites()

    def test_get_my_invites(self, authenticated_api_client: MissingTableClient):
        """Test getting invites for authenticated user."""
        invites = authenticated_api_client.get_my_invites()
        assert isinstance(invites, list)

    def test_cancel_invite_requires_auth(self, api_client: MissingTableClient):
        """Test cancelling an invite requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.cancel_invite("fake-id")


@pytest.mark.contract
class TestAdminInviteContract:
    """Test admin invite creation endpoint contracts."""

    def test_create_club_manager_invite_requires_auth(self, api_client: MissingTableClient):
        """Test creating club manager invite requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_club_manager_invite(1)

    def test_create_team_manager_invite_requires_auth(self, api_client: MissingTableClient):
        """Test creating team manager invite requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_team_manager_invite(1, 1)

    def test_create_team_player_invite_admin_requires_auth(self, api_client: MissingTableClient):
        """Test creating team player invite (admin) requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_team_player_invite_admin(1, 1)

    def test_create_team_fan_invite_admin_requires_auth(self, api_client: MissingTableClient):
        """Test creating team fan invite (admin) requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_team_fan_invite_admin(1, 1)

    def test_create_club_fan_invite_admin_requires_auth(self, api_client: MissingTableClient):
        """Test creating club fan invite (admin) requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_club_fan_invite_admin(1)


@pytest.mark.contract
class TestManagerInviteContract:
    """Test manager invite creation endpoint contracts."""

    def test_create_club_fan_invite_requires_auth(self, api_client: MissingTableClient):
        """Test creating club fan invite requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_club_fan_invite(1)

    def test_create_team_player_invite_requires_auth(self, api_client: MissingTableClient):
        """Test creating team player invite requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_team_player_invite(1, 1)

    def test_create_team_fan_invite_requires_auth(self, api_client: MissingTableClient):
        """Test creating team fan invite requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_team_fan_invite(1, 1)

    def test_get_team_manager_assignments_requires_auth(self, api_client: MissingTableClient):
        """Test getting team manager assignments requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_team_manager_assignments()


@pytest.mark.contract
class TestInviteTestflightContract:
    """iPhone beta / TestFlight retry endpoint contracts (SB-1314)."""

    def test_retry_invite_testflight_requires_auth(self, api_client: MissingTableClient):
        """Retrying TestFlight requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.retry_invite_testflight("00000000-0000-0000-0000-000000000000")

    def test_retry_invite_testflight_is_admin_only(self, authenticated_api_client: MissingTableClient):
        """A non-admin is refused before any invite is looked up."""
        with pytest.raises(AuthorizationError):
            authenticated_api_client.retry_invite_testflight("00000000-0000-0000-0000-000000000000")

    def test_retry_invite_testflight_unknown_invite(self, admin_client: MissingTableClient):
        """An unknown invite is a 404, not a TestFlight call."""
        import uuid

        from api_client import NotFoundError

        with pytest.raises(NotFoundError):
            admin_client.retry_invite_testflight(str(uuid.uuid4()))


@pytest.mark.contract
class TestInviteFromRequestContract:
    """Creating an invite from an invite request (SB-1312)."""

    def test_non_admin_cannot_link_a_request(self, authenticated_api_client: MissingTableClient):
        """invite_request_id is admin-only; a non-admin is refused before any lookup."""
        import uuid

        with pytest.raises(AuthorizationError):
            authenticated_api_client.create_club_fan_invite_admin(1, invite_request_id=str(uuid.uuid4()))

    def test_unknown_request_is_404(self, admin_client: MissingTableClient):
        """An unknown invite request is a 404 and no invite is created."""
        import uuid

        from api_client import NotFoundError

        with pytest.raises(NotFoundError):
            admin_client.create_club_fan_invite_admin(1, invite_request_id=str(uuid.uuid4()))

    def test_invite_links_and_approves_the_request(self, admin_client: MissingTableClient, api_base_url: str):
        """The request is approved and shows the linked invite; a second link is a 409."""
        import uuid

        from api_client import APIError
        from api_client.models import InviteRequestCreate

        clubs = admin_client.get_clubs()
        if not clubs:
            pytest.skip("No clubs to invite to")

        email = f"contract-link-{uuid.uuid4().hex[:12]}@example.com"
        with MissingTableClient(base_url=api_base_url) as public:
            n = uuid.uuid4().int
            public._client.headers["X-Forwarded-For"] = f"198.{18 + (n & 1)}.{(n >> 1) & 0xFF}.{(n >> 9) & 0xFF}"
            public.create_invite_request(InviteRequestCreate(email=email, name="Link Test", wants_ios_beta=True))

        rows = [r for r in admin_client.list_invite_requests(limit=100) if r["email"] == email]
        assert len(rows) == 1
        request_id = rows[0]["id"]
        invite = None
        try:
            # No invite email: the request address is a throwaway.
            invite = admin_client.create_club_fan_invite_admin(clubs[0]["id"], invite_request_id=request_id)

            row = admin_client.list_invite_requests(limit=100)
            row = next(r for r in row if r["id"] == request_id)
            assert row["status"] == "approved"
            assert row["reviewed_at"]
            assert row["invitation_id"] == invite["id"]
            assert row["invitation"]["invite_code"] == invite["invite_code"]
            assert row["invitation"]["invite_type"] == "club_fan"
            assert row["invitation"]["status"] == "pending"

            with pytest.raises(APIError) as exc_info:
                admin_client.create_club_fan_invite_admin(clubs[0]["id"], invite_request_id=request_id)
            assert exc_info.value.status_code == 409
        finally:
            admin_client.delete_invite_request(request_id)
            if invite:
                admin_client.cancel_invite(invite["id"])

"""Contract tests for invite request endpoints."""

import uuid

import pytest

from api_client import AuthorizationError, MissingTableClient, RateLimitError
from api_client.models import InviteRequestCreate


def _fresh_ip() -> str:
    """An address no earlier run has used, from the 198.18.0.0/15 test range.

    POST /api/invite-requests is limited per client IP (SB-1311) and the
    server's counters outlive a test run. Each test gets its own bucket so
    none passes or fails on how often the suite ran this hour.
    """
    n = uuid.uuid4().int
    return f"198.{18 + (n & 1)}.{(n >> 1) & 0xFF}.{(n >> 9) & 0xFF}"


def _unique_email(tag: str) -> str:
    return f"contract-{tag}-{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture
def public_client(api_base_url: str) -> MissingTableClient:
    """An anonymous client with a rate-limit bucket of its own."""
    with MissingTableClient(base_url=api_base_url) as client:
        client._client.headers["X-Forwarded-For"] = _fresh_ip()
        yield client


def _rows_for(admin_client: MissingTableClient, email: str) -> list[dict]:
    return [r for r in admin_client.list_invite_requests(limit=100) if r["email"] == email]


def _delete_rows(admin_client: MissingTableClient, email: str) -> None:
    for row in _rows_for(admin_client, email):
        admin_client.delete_invite_request(row["id"])


@pytest.mark.contract
class TestInviteRequestPublicContract:
    """Test public invite request endpoint contracts."""

    def test_create_invite_request(self, public_client: MissingTableClient):
        """Test creating an invite request (public endpoint)."""
        request = InviteRequestCreate(
            email="contract-test@example.com",
            name="Contract Test User",
            team="Test Team",
            reason="Testing",
        )
        result = public_client.create_invite_request(request)
        assert result is not None
        assert result.get("success") is True

    def test_create_invite_request_with_ios_beta(self, public_client: MissingTableClient):
        """The iPhone-beta opt-in is accepted on the public endpoint."""
        request = InviteRequestCreate(email="contract-test-ios@example.com", name="iOS Beta", wants_ios_beta=True)
        result = public_client.create_invite_request(request)
        assert result.get("success") is True

    def test_honeypot_returns_success(self, public_client: MissingTableClient):
        """A filled honeypot gets the same success reply, so a bot learns nothing."""
        request = InviteRequestCreate(email=_unique_email("bot"), name="Bot", website="http://spam.example")
        result = public_client.create_invite_request(request)
        assert result.get("success") is True

    def test_duplicate_pending_returns_success(self, public_client: MissingTableClient):
        """Re-submitting while pending succeeds without revealing the email exists."""
        request = InviteRequestCreate(email="contract-test@example.com", name="Contract Test User")
        first = public_client.create_invite_request(request)
        second = public_client.create_invite_request(request)
        assert first.get("success") is True
        assert second == first


@pytest.mark.contract
class TestInviteRequestRateLimitContract:
    """POST /api/invite-requests is limited per client IP (SB-1311)."""

    def _bot(self) -> InviteRequestCreate:
        # Honeypot submissions count against the limit but write no row, so
        # exhausting a bucket leaves nothing behind.
        return InviteRequestCreate(email=_unique_email("rl"), name="Rate Limit", website="filled")

    def test_sixth_request_in_an_hour_is_refused(self, public_client: MissingTableClient):
        for _ in range(5):
            assert public_client.create_invite_request(self._bot()).get("success") is True

        with pytest.raises(RateLimitError) as exc_info:
            public_client.create_invite_request(self._bot())
        assert exc_info.value.status_code == 429

    def test_one_client_does_not_lock_out_another(self, public_client: MissingTableClient, api_base_url: str):
        for _ in range(10):
            try:
                public_client.create_invite_request(self._bot())
            except RateLimitError:
                break
        else:
            pytest.fail("the limit never triggered")

        with MissingTableClient(base_url=api_base_url) as other:
            other._client.headers["X-Forwarded-For"] = _fresh_ip()
            assert other.create_invite_request(self._bot()).get("success") is True


@pytest.mark.contract
class TestInviteRequestAdminContract:
    """Test admin invite request endpoint contracts."""

    def test_list_invite_requests_requires_auth(self, api_client: MissingTableClient):
        """Test listing invite requests requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.list_invite_requests()

    def test_get_invite_request_stats_requires_auth(self, api_client: MissingTableClient):
        """Test getting invite request stats requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_invite_request_stats()

    def test_get_invite_request_requires_auth(self, api_client: MissingTableClient):
        """Test getting a specific invite request requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_invite_request("fake-id")

    def test_update_invite_request_status_requires_auth(self, api_client: MissingTableClient):
        """Test updating invite request status requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import InviteRequestStatusUpdate

        update = InviteRequestStatusUpdate(status="approved")
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_invite_request_status("fake-id", update)

    def test_delete_invite_request_requires_auth(self, api_client: MissingTableClient):
        """Test deleting an invite request requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_invite_request("fake-id")

    def test_list_invite_requests_admin(self, admin_client: MissingTableClient):
        """Test listing invite requests as admin."""
        requests = admin_client.list_invite_requests()
        assert isinstance(requests, list)

    def test_get_invite_request_stats_admin(self, admin_client: MissingTableClient):
        """Test getting invite request stats as admin."""
        stats = admin_client.get_invite_request_stats()
        assert "total" in stats
        assert "pending" in stats

    def test_ios_beta_is_stored_and_filterable(
        self, public_client: MissingTableClient, admin_client: MissingTableClient
    ):
        """wants_ios_beta round-trips, and ?ios_beta= filters on it."""
        beta_email = _unique_email("ios-yes")
        plain_email = _unique_email("ios-no")
        public_client.create_invite_request(InviteRequestCreate(email=beta_email, name="Beta", wants_ios_beta=True))
        public_client.create_invite_request(InviteRequestCreate(email=plain_email, name="Plain"))
        try:
            assert [r["wants_ios_beta"] for r in _rows_for(admin_client, beta_email)] == [True]
            assert [r["wants_ios_beta"] for r in _rows_for(admin_client, plain_email)] == [False]

            only_beta = {r["email"] for r in admin_client.list_invite_requests(ios_beta=True, limit=100)}
            assert beta_email in only_beta
            assert plain_email not in only_beta

            no_beta = {r["email"] for r in admin_client.list_invite_requests(ios_beta=False, limit=100)}
            assert plain_email in no_beta
            assert beta_email not in no_beta
        finally:
            _delete_rows(admin_client, beta_email)
            _delete_rows(admin_client, plain_email)

    def test_honeypot_stores_nothing(self, public_client: MissingTableClient, admin_client: MissingTableClient):
        """A filled honeypot is answered with success but never written."""
        email = _unique_email("bot")
        public_client.create_invite_request(InviteRequestCreate(email=email, name="Bot", website="http://spam.example"))
        assert _rows_for(admin_client, email) == []

    def test_duplicate_pending_stores_one_row(
        self, public_client: MissingTableClient, admin_client: MissingTableClient
    ):
        """A second submission while the first is pending adds no row."""
        email = _unique_email("dup")
        request = InviteRequestCreate(email=email, name="Duplicate")
        public_client.create_invite_request(request)
        public_client.create_invite_request(request)
        try:
            rows = _rows_for(admin_client, email)
            assert len(rows) == 1
            assert rows[0]["status"] == "pending"
        finally:
            _delete_rows(admin_client, email)

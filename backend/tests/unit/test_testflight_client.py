"""App Store Connect TestFlight client tests (SB-1314).

No network: every call goes through an httpx.MockTransport that routes by
method + path and records the request. The signing key is a throwaway P-256
key generated per test session.
"""

from __future__ import annotations

import json

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from services import testflight_client

pytestmark = [pytest.mark.unit, pytest.mark.backend]

KEY_ID = "ASCKEY1234"
ISSUER_ID = "57246542-96fe-1a63-e053-0824d011072a"
GROUP_ID = "group-abc"
EMAIL = "parent@icloud.com"


@pytest.fixture(scope="session")
def ec_key():
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return key, pem


@pytest.fixture(autouse=True)
def _asc_env(monkeypatch, ec_key):
    _, pem = ec_key
    monkeypatch.setenv("ASC_KEY_ID", KEY_ID)
    monkeypatch.setenv("ASC_ISSUER_ID", ISSUER_ID)
    monkeypatch.setenv("ASC_PRIVATE_KEY", pem)
    monkeypatch.setenv("ASC_EXTERNAL_GROUP_ID", GROUP_ID)
    monkeypatch.delenv("ASC_APP_ID", raising=False)


def _client(routes: dict[tuple[str, str], httpx.Response], sink: list):
    """httpx client answering by (method, path); anything unrouted is a 599."""

    def handler(request: httpx.Request) -> httpx.Response:
        sink.append(request)
        return routes.get((request.method, request.url.path), httpx.Response(599))

    return httpx.Client(transport=httpx.MockTransport(handler))


class TestConfiguration:
    def test_configured_with_all_four(self):
        assert testflight_client.is_configured()

    @pytest.mark.parametrize("missing", ["ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_PRIVATE_KEY", "ASC_EXTERNAL_GROUP_ID"])
    def test_not_configured_when_any_is_missing(self, monkeypatch, missing):
        monkeypatch.delenv(missing)
        assert not testflight_client.is_configured()

    def test_app_id_defaults(self):
        assert testflight_client.get_app_id() == "6820504545"

    def test_add_when_not_configured_fails_without_calling_apple(self, monkeypatch):
        monkeypatch.delenv("ASC_PRIVATE_KEY")
        sink: list = []
        result = testflight_client.add_tester(EMAIL, client=_client({}, sink))
        assert result.status == "failed"
        assert "not configured" in result.error
        assert sink == []

    def test_remove_when_not_configured_fails_without_calling_apple(self, monkeypatch):
        monkeypatch.delenv("ASC_KEY_ID")
        sink: list = []
        result = testflight_client.remove_tester("t-1", client=_client({}, sink))
        assert result.status == "failed"
        assert sink == []


class TestToken:
    def test_claims_and_header(self, ec_key):
        key, _ = ec_key
        token = testflight_client._token(now=1_700_000_000)

        header = jwt.get_unverified_header(token)
        assert header == {"alg": "ES256", "kid": KEY_ID, "typ": "JWT"}

        claims = jwt.decode(
            token,
            key.public_key(),
            algorithms=["ES256"],
            audience="appstoreconnect-v1",
            options={"verify_exp": False, "verify_iat": False},
        )
        assert claims["iss"] == ISSUER_ID
        assert claims["iat"] == 1_700_000_000
        assert claims["aud"] == "appstoreconnect-v1"
        # Apple rejects a lifetime over 20 minutes.
        assert 0 < claims["exp"] - claims["iat"] <= 20 * 60

    def test_escaped_newlines_in_the_key_are_accepted(self, monkeypatch, ec_key):
        key, pem = ec_key
        monkeypatch.setenv("ASC_PRIVATE_KEY", pem.replace("\n", "\\n"))
        token = testflight_client._token(now=1_700_000_000)
        jwt.decode(
            token,
            key.public_key(),
            algorithms=["ES256"],
            audience="appstoreconnect-v1",
            options={"verify_exp": False, "verify_iat": False},
        )


class TestAddTester:
    def test_creates_the_tester_in_the_external_group(self):
        sink: list = []
        routes = {("POST", "/v1/betaTesters"): httpx.Response(201, json={"data": {"type": "betaTesters", "id": "t-1"}})}

        result = testflight_client.add_tester(EMAIL, "Sam", "Smith", client=_client(routes, sink))

        assert result.status == "added"
        assert result.tester_id == "t-1"
        assert len(sink) == 1
        request = sink[0]
        assert request.headers["authorization"].startswith("Bearer ")
        body = json.loads(request.content)
        assert body == {
            "data": {
                "type": "betaTesters",
                "attributes": {"email": EMAIL, "firstName": "Sam", "lastName": "Smith"},
                "relationships": {"betaGroups": {"data": [{"type": "betaGroups", "id": GROUP_ID}]}},
            }
        }

    def test_unknown_names_are_omitted(self):
        sink: list = []
        routes = {("POST", "/v1/betaTesters"): httpx.Response(201, json={"data": {"id": "t-1"}})}

        testflight_client.add_tester(EMAIL, client=_client(routes, sink))

        assert json.loads(sink[0].content)["data"]["attributes"] == {"email": EMAIL}

    def test_existing_tester_is_looked_up_and_added_to_the_group(self):
        sink: list = []
        routes = {
            ("POST", "/v1/betaTesters"): httpx.Response(
                409, json={"errors": [{"code": "ENTITY_ERROR.ATTRIBUTE.INVALID.DUPLICATE"}]}
            ),
            ("GET", "/v1/betaTesters"): httpx.Response(200, json={"data": [{"type": "betaTesters", "id": "t-9"}]}),
            ("POST", f"/v1/betaGroups/{GROUP_ID}/relationships/betaTesters"): httpx.Response(204),
        }

        result = testflight_client.add_tester(EMAIL, client=_client(routes, sink))

        assert result.status == "added"
        assert result.tester_id == "t-9"
        lookup, add = sink[1], sink[2]
        assert lookup.url.params["filter[email]"] == EMAIL
        assert json.loads(add.content) == {"data": [{"type": "betaTesters", "id": "t-9"}]}

    def test_conflict_with_no_matching_tester_is_a_failure(self):
        sink: list = []
        routes = {
            ("POST", "/v1/betaTesters"): httpx.Response(409, json={"errors": []}),
            ("GET", "/v1/betaTesters"): httpx.Response(200, json={"data": []}),
        }

        result = testflight_client.add_tester(EMAIL, client=_client(routes, sink))

        assert result.status == "failed"
        assert result.error

    def test_apple_error_is_reported_not_raised(self):
        sink: list = []
        routes = {
            ("POST", "/v1/betaTesters"): httpx.Response(
                403, json={"errors": [{"title": "Forbidden", "detail": "The API key lacks permission"}]}
            )
        }

        result = testflight_client.add_tester(EMAIL, client=_client(routes, sink))

        assert result.status == "failed"
        assert "403" in result.error
        assert "lacks permission" in result.error

    def test_transport_error_is_reported_not_raised(self):
        def boom(request):
            raise httpx.ConnectTimeout("timed out")

        client = httpx.Client(transport=httpx.MockTransport(boom))
        result = testflight_client.add_tester(EMAIL, client=client)

        assert result.status == "failed"
        assert "timed out" in result.error


class TestRemoveTester:
    def test_removes_the_tester_from_the_group(self):
        sink: list = []
        routes = {("DELETE", f"/v1/betaGroups/{GROUP_ID}/relationships/betaTesters"): httpx.Response(204)}

        result = testflight_client.remove_tester("t-1", client=_client(routes, sink))

        assert result.status == "removed"
        assert json.loads(sink[0].content) == {"data": [{"type": "betaTesters", "id": "t-1"}]}

    def test_apple_error_is_reported_not_raised(self):
        sink: list = []
        routes = {("DELETE", f"/v1/betaGroups/{GROUP_ID}/relationships/betaTesters"): httpx.Response(404)}

        result = testflight_client.remove_tester("t-1", client=_client(routes, sink))

        assert result.status == "failed"
        assert result.error == "HTTP 404"

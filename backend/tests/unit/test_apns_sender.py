"""APNs sender tests (SB-1236).

No network: every send goes through an httpx.MockTransport that records the
request. The signing key is a throwaway P-256 key generated per test session.
"""

from __future__ import annotations

import json

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from notifications import apns_sender
from notifications.apns_sender import build_apns_payload, host_for, send_apns

pytestmark = [pytest.mark.unit, pytest.mark.backend]

KEY_ID = "ABC123DEFG"
TEAM_ID = "TEAM123456"
TOKEN = "a1" * 32  # 64 hex chars

_PAYLOAD = {
    "title": "⚽ GOAL — IFA 1-0 NEFC",
    "body": "12' Smith",
    "icon": "/pwa/icon-192.png",
    "badge": "/pwa/icon-192.png",
    "tag": "match-555-goal",
    "data": {"url": "/?matchId=555", "matchId": 555, "eventType": "goal"},
}


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
def _apns_env(monkeypatch, ec_key):
    _, pem = ec_key
    monkeypatch.setenv("APNS_KEY_ID", KEY_ID)
    monkeypatch.setenv("APNS_TEAM_ID", TEAM_ID)
    monkeypatch.setenv("APNS_PRIVATE_KEY", pem)
    monkeypatch.delenv("APNS_PRIVATE_KEY_PATH", raising=False)
    monkeypatch.delenv("APNS_BUNDLE_ID", raising=False)
    monkeypatch.setattr(apns_sender, "_cached_token", None)


def _device(environment="sandbox", **extra):
    return {"id": "dev-1", "user_id": "u-1", "device_token": TOKEN, "environment": environment, **extra}


def _client(status=200, body=None, sink=None):
    """httpx client whose transport records requests and returns a fixed response."""

    def handler(request: httpx.Request) -> httpx.Response:
        if sink is not None:
            sink.append(request)
        return httpx.Response(status, json=body) if body is not None else httpx.Response(status)

    return httpx.Client(transport=httpx.MockTransport(handler))


class TestConfiguration:
    def test_configured_with_all_three(self):
        assert apns_sender.is_configured()

    @pytest.mark.parametrize("missing", ["APNS_KEY_ID", "APNS_TEAM_ID", "APNS_PRIVATE_KEY"])
    def test_not_configured_when_any_is_missing(self, monkeypatch, missing):
        monkeypatch.delenv(missing)
        assert not apns_sender.is_configured()

    def test_private_key_path_is_accepted(self, monkeypatch, tmp_path, ec_key):
        _, pem = ec_key
        key_file = tmp_path / "AuthKey.p8"
        key_file.write_text(pem)
        monkeypatch.delenv("APNS_PRIVATE_KEY")
        monkeypatch.setenv("APNS_PRIVATE_KEY_PATH", str(key_file))
        assert apns_sender.is_configured()

    def test_unreadable_key_path_is_not_configured(self, monkeypatch, tmp_path):
        monkeypatch.delenv("APNS_PRIVATE_KEY")
        monkeypatch.setenv("APNS_PRIVATE_KEY_PATH", str(tmp_path / "nope.p8"))
        assert not apns_sender.is_configured()

    def test_escaped_newlines_in_env_are_restored(self, monkeypatch, ec_key):
        _, pem = ec_key
        monkeypatch.setenv("APNS_PRIVATE_KEY", pem.replace("\n", "\\n"))
        sink: list[httpx.Request] = []
        result = send_apns(_device(), _PAYLOAD, client=_client(sink=sink))
        assert result.ok

    def test_unconfigured_send_fails_without_a_request(self, monkeypatch):
        monkeypatch.delenv("APNS_KEY_ID")
        sink: list[httpx.Request] = []
        result = send_apns(_device(), _PAYLOAD, client=_client(sink=sink))
        assert result.status == "failed"
        assert sink == []

    def test_device_without_token_fails_without_a_request(self):
        sink: list[httpx.Request] = []
        result = send_apns({"environment": "sandbox"}, _PAYLOAD, client=_client(sink=sink))
        assert result.status == "failed"
        assert sink == []


class TestRequest:
    def _send(self, device=None, payload=None):
        sink: list[httpx.Request] = []
        result = send_apns(device or _device(), payload or _PAYLOAD, client=_client(sink=sink))
        assert len(sink) == 1
        return result, sink[0]

    def test_sandbox_host_and_device_path(self):
        _, req = self._send(_device("sandbox"))
        assert req.url.host == "api.sandbox.push.apple.com"
        assert req.url.path == f"/3/device/{TOKEN}"
        assert req.url.scheme == "https"

    def test_production_host(self):
        _, req = self._send(_device("production"))
        assert req.url.host == "api.push.apple.com"

    def test_unknown_environment_falls_back_to_sandbox(self):
        assert host_for(None) == "api.sandbox.push.apple.com"
        assert host_for("production") == "api.push.apple.com"

    def test_headers(self):
        _, req = self._send()
        assert req.method == "POST"
        assert req.headers["apns-topic"] == "com.missingtable"
        assert req.headers["apns-push-type"] == "alert"
        assert req.headers["apns-priority"] == "10"
        assert req.headers["apns-collapse-id"] == "match-555-goal"
        assert req.headers["authorization"].startswith("bearer ")

    def test_topic_from_env_and_device_override(self, monkeypatch):
        monkeypatch.setenv("APNS_BUNDLE_ID", "com.missingtable.dev")
        _, req = self._send()
        assert req.headers["apns-topic"] == "com.missingtable.dev"
        _, req = self._send(_device(bundle_id="com.example.other"))
        assert req.headers["apns-topic"] == "com.example.other"

    def test_collapse_id_capped_at_64_bytes(self):
        _, req = self._send(payload={**_PAYLOAD, "tag": "x" * 100})
        assert req.headers["apns-collapse-id"] == "x" * 64

    def test_collapse_id_truncation_never_splits_a_character(self):
        collapse = apns_sender._collapse_id("é" * 40 + "x")  # 2 bytes each
        assert collapse == "é" * 32
        assert collapse is not None and len(collapse.encode("utf-8")) == 64
        assert apns_sender._collapse_id("a" + "é" * 40) == "a" + "é" * 31  # half a char dropped

    def test_no_collapse_id_without_tag(self):
        _, req = self._send(payload={k: v for k, v in _PAYLOAD.items() if k != "tag"})
        assert "apns-collapse-id" not in req.headers

    def test_body_is_the_apns_payload(self):
        _, req = self._send()
        assert json.loads(req.content) == {
            "aps": {
                "alert": {"title": _PAYLOAD["title"], "body": "12' Smith"},
                "sound": "default",
                "thread-id": "match-555",
            },
            "matchId": 555,
            "eventType": "goal",
        }


class TestProviderToken:
    def _bearer(self, req: httpx.Request) -> str:
        return req.headers["authorization"].removeprefix("bearer ")

    def test_jwt_header_and_claims(self, ec_key):
        key, _ = ec_key
        sink: list[httpx.Request] = []
        send_apns(_device(), _PAYLOAD, client=_client(sink=sink))
        token = self._bearer(sink[0])

        header = jwt.get_unverified_header(token)
        assert header["alg"] == "ES256"
        assert header["kid"] == KEY_ID
        claims = jwt.decode(token, key.public_key(), algorithms=["ES256"])
        assert claims["iss"] == TEAM_ID
        assert isinstance(claims["iat"], int)

    def test_token_is_reused_across_sends(self):
        sink: list[httpx.Request] = []
        client = _client(sink=sink)
        send_apns(_device(), _PAYLOAD, client=client)
        send_apns(_device(), _PAYLOAD, client=client)
        assert self._bearer(sink[0]) == self._bearer(sink[1])

    def test_token_is_reissued_after_50_minutes(self):
        first = apns_sender._provider_token(now=1_000_000)
        assert apns_sender._provider_token(now=1_000_000 + 49 * 60) == first
        later = apns_sender._provider_token(now=1_000_000 + 50 * 60)
        assert later != first
        assert jwt.decode(later, options={"verify_signature": False})["iat"] == 1_000_000 + 50 * 60

    def test_key_rotation_invalidates_the_cache(self, monkeypatch):
        first = apns_sender._provider_token(now=1_000_000)
        monkeypatch.setenv("APNS_KEY_ID", "NEWKEY0000")
        second = apns_sender._provider_token(now=1_000_001)
        assert second != first
        assert jwt.get_unverified_header(second)["kid"] == "NEWKEY0000"

    def test_expired_provider_token_response_drops_the_cache(self):
        apns_sender._provider_token()
        result = send_apns(_device(), _PAYLOAD, client=_client(403, {"reason": "ExpiredProviderToken"}))
        assert result.status == "failed"
        assert apns_sender._cached_token is None


class TestResponseMapping:
    def test_200_is_sent(self):
        result = send_apns(_device(), _PAYLOAD, client=_client(200))
        assert result.ok
        assert result.http_status == 200

    def test_410_is_expired(self):
        result = send_apns(_device(), _PAYLOAD, client=_client(410, {"reason": "Unregistered"}))
        assert result.expired
        assert result.http_status == 410
        assert result.error == "Unregistered"

    @pytest.mark.parametrize("reason", ["BadDeviceToken", "Unregistered", "DeviceTokenNotForTopic"])
    def test_400_dead_token_reasons_are_expired(self, reason):
        result = send_apns(_device(), _PAYLOAD, client=_client(400, {"reason": reason}))
        assert result.expired
        assert result.error == reason

    def test_other_400_is_failed_not_expired(self):
        result = send_apns(_device(), _PAYLOAD, client=_client(400, {"reason": "PayloadTooLarge"}))
        assert result.status == "failed"
        assert result.http_status == 400
        assert result.error == "PayloadTooLarge"

    def test_500_without_body_is_failed(self):
        result = send_apns(_device(), _PAYLOAD, client=_client(500))
        assert result.status == "failed"
        assert result.error == "HTTP 500"

    def test_transport_error_is_failed_and_does_not_raise(self):
        def boom(_request):
            raise httpx.ConnectError("no route")

        client = httpx.Client(transport=httpx.MockTransport(boom))
        result = send_apns(_device(), _PAYLOAD, client=client)
        assert result.status == "failed"
        assert "no route" in (result.error or "")

    def test_bad_key_is_failed_and_does_not_raise(self, monkeypatch):
        monkeypatch.setenv("APNS_PRIVATE_KEY", "not a pem")
        result = send_apns(_device(), _PAYLOAD, client=_client(200))
        assert result.status == "failed"


class TestBuildPayload:
    def test_test_notification_has_no_match_fields(self):
        body = build_apns_payload({"title": "t", "body": "b", "tag": "mt-test", "data": {"url": "/", "test": True}})
        assert body == {"aps": {"alert": {"title": "t", "body": "b"}, "sound": "default"}}

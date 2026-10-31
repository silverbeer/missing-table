"""FCM sender tests (SB-1463).

No network: the OAuth token exchange and every send go through an
httpx.MockTransport that records the request. The service-account key is a
throwaway RSA key generated per test session.
"""

from __future__ import annotations

import json
import threading
from urllib.parse import parse_qs

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from notifications import fcm_sender
from notifications.fcm_sender import build_fcm_message, send_fcm

pytestmark = [pytest.mark.unit, pytest.mark.backend]

PROJECT_ID = "missing-table-test"
CLIENT_EMAIL = "fcm-sender@missing-table-test.iam.gserviceaccount.com"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SEND_PATH = f"/v1/projects/{PROJECT_ID}/messages:send"
FID = "cJx1Yk2zQ9-abc_DEF0123"  # 22 chars, base64url like a real FID

_PAYLOAD = {
    "title": "⚽ GOAL — IFA 1-0 NEFC",
    "body": "12' Smith",
    "icon": "/pwa/icon-192.png",
    "badge": "/pwa/icon-192.png",
    "tag": "match-555-goal",
    "data": {"url": "/?matchId=555", "matchId": 555, "eventType": "goal"},
}


@pytest.fixture(scope="session")
def rsa_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return key, pem


def _account(pem, **overrides):
    info = {
        "type": "service_account",
        "project_id": PROJECT_ID,
        "private_key_id": "kid-1",
        "private_key": pem,
        "client_email": CLIENT_EMAIL,
        "token_uri": TOKEN_URI,
    }
    info.update(overrides)
    return {k: v for k, v in info.items() if v is not None}


@pytest.fixture(autouse=True)
def _fcm_env(monkeypatch, rsa_key):
    _, pem = rsa_key
    monkeypatch.setenv("FCM_SERVICE_ACCOUNT_JSON", json.dumps(_account(pem)))
    monkeypatch.delenv("FCM_SERVICE_ACCOUNT_PATH", raising=False)
    monkeypatch.setattr(fcm_sender, "_cached_token", None)
    monkeypatch.setattr(fcm_sender, "_failed_exchange", None)
    monkeypatch.setattr(fcm_sender, "_warned_misconfigured", False)


def _device(**extra):
    return {"id": "dev-1", "user_id": "u-1", "fid": FID, **extra}


def _client(*send_responses, sink=None, token_sink=None, access_tokens=None):
    """httpx client: the token endpoint returns access tokens in sequence; the
    send endpoint returns send_responses in sequence (last one repeats).
    Each send response is (status, json_body_or_None).
    """
    sends = list(send_responses) or [(200, {"name": "projects/p/messages/1"})]
    tokens = list(access_tokens or ["ya29.access-1", "ya29.access-2", "ya29.access-3"])
    counters = {"send": 0, "token": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            if token_sink is not None:
                token_sink.append(request)
            tok = tokens[min(counters["token"], len(tokens) - 1)]
            counters["token"] += 1
            return httpx.Response(200, json={"access_token": tok, "expires_in": 3599, "token_type": "Bearer"})
        if sink is not None:
            sink.append(request)
        status, body = sends[min(counters["send"], len(sends) - 1)]
        counters["send"] += 1
        if body is None:
            return httpx.Response(status)
        if isinstance(body, str | bytes):
            return httpx.Response(status, content=body)
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _fcm_error(code, status, message="", error_code=None):
    err = {"code": code, "status": status, "message": message}
    if error_code:
        err["details"] = [{"@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError", "errorCode": error_code}]
    return {"error": err}


class TestConfiguration:
    def test_configured_with_full_service_account(self):
        assert fcm_sender.is_configured()

    def test_not_configured_when_unset_and_silent(self, monkeypatch):
        monkeypatch.delenv("FCM_SERVICE_ACCOUNT_JSON")
        warn = []
        monkeypatch.setattr(fcm_sender.logger, "warning", lambda *a, **k: warn.append((a, k)))
        assert not fcm_sender.is_configured()
        assert warn == []

    @pytest.mark.parametrize("missing", ["project_id", "client_email", "private_key"])
    def test_not_configured_when_a_required_field_is_missing(self, monkeypatch, rsa_key, missing):
        _, pem = rsa_key
        monkeypatch.setenv("FCM_SERVICE_ACCOUNT_JSON", json.dumps(_account(pem, **{missing: None})))
        assert not fcm_sender.is_configured()

    @pytest.mark.parametrize("raw", ["not json", "[]", '"a string"'])
    def test_not_configured_when_json_is_unusable(self, monkeypatch, raw):
        monkeypatch.setenv("FCM_SERVICE_ACCOUNT_JSON", raw)
        assert not fcm_sender.is_configured()

    def test_misconfiguration_warns_once_without_the_value(self, monkeypatch):
        secret = '{"private_key": "-----BEGIN PRIVATE KEY-----SECRET'  # pragma: allowlist secret
        monkeypatch.setenv("FCM_SERVICE_ACCOUNT_JSON", secret)
        warn = []
        monkeypatch.setattr(fcm_sender.logger, "warning", lambda *a, **k: warn.append((a, k)))
        assert not fcm_sender.is_configured()
        assert not fcm_sender.is_configured()

        assert len(warn) == 1
        (args, kwargs) = warn[0]
        assert args == ("fcm.misconfigured",)
        assert kwargs == {"source": "FCM_SERVICE_ACCOUNT_JSON", "reason": "invalid_json"}
        assert "SECRET" not in repr(warn)

    def test_raw_newlines_inside_json_strings_are_accepted(self, monkeypatch, rsa_key):
        _, pem = rsa_key
        # A secret store that unescaped "\n" leaves control characters inside
        # the JSON string; strict=False still parses it.
        raw = json.dumps(_account(pem)).replace("\\n", "\n")
        monkeypatch.setenv("FCM_SERVICE_ACCOUNT_JSON", raw)
        assert fcm_sender.is_configured()
        assert send_fcm(_device(), _PAYLOAD, client=_client()).ok

    def test_service_account_path_is_accepted(self, monkeypatch, tmp_path, rsa_key):
        _, pem = rsa_key
        key_file = tmp_path / "sa.json"
        key_file.write_text(json.dumps(_account(pem)))
        monkeypatch.delenv("FCM_SERVICE_ACCOUNT_JSON")
        monkeypatch.setenv("FCM_SERVICE_ACCOUNT_PATH", str(key_file))
        assert fcm_sender.is_configured()

    def test_unreadable_path_is_not_configured(self, monkeypatch, tmp_path):
        monkeypatch.delenv("FCM_SERVICE_ACCOUNT_JSON")
        monkeypatch.setenv("FCM_SERVICE_ACCOUNT_PATH", str(tmp_path / "nope.json"))
        assert not fcm_sender.is_configured()

    def test_undecodable_path_is_not_configured(self, monkeypatch, tmp_path):
        key_file = tmp_path / "sa.json"
        key_file.write_bytes(b"\xff\xfe\x00bad")
        monkeypatch.delenv("FCM_SERVICE_ACCOUNT_JSON")
        monkeypatch.setenv("FCM_SERVICE_ACCOUNT_PATH", str(key_file))
        assert not fcm_sender.is_configured()

    def test_double_escaped_newlines_in_key_are_restored(self, monkeypatch, rsa_key):
        _, pem = rsa_key
        monkeypatch.setenv("FCM_SERVICE_ACCOUNT_JSON", json.dumps(_account(pem.replace("\n", "\\n"))))
        assert send_fcm(_device(), _PAYLOAD, client=_client()).ok

    def test_unconfigured_send_fails_without_a_request(self, monkeypatch):
        monkeypatch.delenv("FCM_SERVICE_ACCOUNT_JSON")
        sink: list[httpx.Request] = []
        token_sink: list[httpx.Request] = []
        result = send_fcm(_device(), _PAYLOAD, client=_client(sink=sink, token_sink=token_sink))
        assert result.status == "failed"
        assert sink == [] and token_sink == []

    def test_device_without_fid_fails_without_a_request(self):
        sink: list[httpx.Request] = []
        result = send_fcm({"id": "dev-1", "token": "legacy"}, _PAYLOAD, client=_client(sink=sink))
        assert result.status == "failed"
        assert sink == []


class TestRequest:
    def _send(self, payload=None):
        sink: list[httpx.Request] = []
        result = send_fcm(_device(), payload or _PAYLOAD, client=_client(sink=sink))
        assert len(sink) == 1
        return result, sink[0]

    def test_url_and_auth(self):
        _, req = self._send()
        assert req.method == "POST"
        assert req.url.scheme == "https"
        assert req.url.host == "fcm.googleapis.com"
        assert req.url.path == SEND_PATH
        assert req.headers["authorization"] == "Bearer ya29.access-1"

    def test_body_is_the_fcm_message_addressed_by_fid(self):
        _, req = self._send()
        assert json.loads(req.content) == {
            "message": {
                "fid": FID,
                "notification": {"title": _PAYLOAD["title"], "body": "12' Smith"},
                "data": {"matchId": "555", "eventType": "goal", "url": "/?matchId=555"},
                "android": {
                    "collapse_key": "match-555-goal",
                    "priority": "high",
                    "ttl": "60s",
                    "notification": {"tag": "match-555-goal", "channel_id": "live_scores"},
                },
            }
        }

    def test_never_sends_a_registration_token(self):
        _, req = self._send()
        assert "token" not in json.loads(req.content)["message"]

    def test_data_values_are_all_strings(self):
        _, req = self._send()
        data = json.loads(req.content)["message"]["data"]
        assert all(isinstance(v, str) for v in data.values())

    def test_no_tag_means_no_collapse(self):
        _, req = self._send(payload={k: v for k, v in _PAYLOAD.items() if k != "tag"})
        android = json.loads(req.content)["message"]["android"]
        assert "collapse_key" not in android
        assert android["notification"] == {"channel_id": "live_scores"}
        assert android["ttl"] == "60s"

    def test_test_notification_has_no_match_fields(self):
        body = build_fcm_message("f", {"title": "t", "body": "b", "tag": "mt-test", "data": {"url": "/", "test": True}})
        assert body["message"]["data"] == {"url": "/"}
        assert body["message"]["android"]["notification"]["tag"] == "mt-test"


class TestAccessToken:
    def test_assertion_claims_and_grant(self, rsa_key):
        key, _ = rsa_key
        token_sink: list[httpx.Request] = []
        send_fcm(_device(), _PAYLOAD, client=_client(token_sink=token_sink))

        [req] = token_sink
        assert str(req.url) == TOKEN_URI
        form = parse_qs(req.content.decode())
        assert form["grant_type"] == ["urn:ietf:params:oauth:grant-type:jwt-bearer"]
        assertion = form["assertion"][0]
        header = jwt.get_unverified_header(assertion)
        assert header["alg"] == "RS256"
        assert header["kid"] == "kid-1"
        claims = jwt.decode(assertion, key.public_key(), algorithms=["RS256"], audience=TOKEN_URI)
        assert claims["iss"] == CLIENT_EMAIL
        assert claims["scope"] == "https://www.googleapis.com/auth/firebase.messaging"
        assert claims["exp"] - claims["iat"] == 3600

    def test_token_uri_defaults_when_absent(self, monkeypatch, rsa_key):
        _, pem = rsa_key
        monkeypatch.setenv("FCM_SERVICE_ACCOUNT_JSON", json.dumps(_account(pem, token_uri=None)))
        token_sink: list[httpx.Request] = []
        assert send_fcm(_device(), _PAYLOAD, client=_client(token_sink=token_sink)).ok
        assert str(token_sink[0].url) == "https://oauth2.googleapis.com/token"

    def test_access_token_is_reused_across_sends(self):
        sink: list[httpx.Request] = []
        token_sink: list[httpx.Request] = []
        client = _client(sink=sink, token_sink=token_sink)
        send_fcm(_device(), _PAYLOAD, client=client)
        send_fcm(_device(), _PAYLOAD, client=client)
        assert len(token_sink) == 1
        assert sink[0].headers["authorization"] == sink[1].headers["authorization"]

    def test_refreshed_five_minutes_before_expiry(self):
        info = fcm_sender._service_account()
        client = _client()
        first = fcm_sender._access_token(info, client, now=1_000_000)
        # expires_in=3599 → refresh from 1_000_000 + 3599 - 300.
        assert fcm_sender._access_token(info, client, now=1_000_000 + 3298) == first
        assert fcm_sender._access_token(info, client, now=1_000_000 + 3299) != first

    def test_key_rotation_invalidates_the_cache(self, monkeypatch, rsa_key):
        _, pem = rsa_key
        client = _client()
        first = fcm_sender._access_token(fcm_sender._service_account(), client, now=1_000_000)
        monkeypatch.setenv(
            "FCM_SERVICE_ACCOUNT_JSON", json.dumps(_account(pem, client_email="other@x.iam.gserviceaccount.com"))
        )
        assert fcm_sender._access_token(fcm_sender._service_account(), client, now=1_000_001) != first

    def test_401_drops_the_cache_and_retries_once(self):
        sink: list[httpx.Request] = []
        token_sink: list[httpx.Request] = []
        client = _client((401, _fcm_error(401, "UNAUTHENTICATED")), (200, {}), sink=sink, token_sink=token_sink)
        result = send_fcm(_device(), _PAYLOAD, client=client)

        assert result.ok
        assert len(sink) == 2
        assert len(token_sink) == 2
        assert sink[0].headers["authorization"] == "Bearer ya29.access-1"
        assert sink[1].headers["authorization"] == "Bearer ya29.access-2"

    def test_persistent_401_fails_after_one_retry(self):
        sink: list[httpx.Request] = []
        client = _client((401, _fcm_error(401, "UNAUTHENTICATED")), sink=sink)
        result = send_fcm(_device(), _PAYLOAD, client=client)
        assert result.status == "failed"
        assert result.http_status == 401
        assert len(sink) == 2

    def test_token_exchange_failure_is_failed_and_does_not_leak(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "oauth2.googleapis.com":
                return httpx.Response(400, json={"error": "invalid_grant", "error_description": "Invalid JWT"})
            raise AssertionError("send must not happen without an access token")

        result = send_fcm(_device(), _PAYLOAD, client=httpx.Client(transport=httpx.MockTransport(handler)))
        assert result.status == "failed"
        assert "invalid_grant" in (result.error or "")
        assert "PRIVATE KEY" not in (result.error or "")
        assert fcm_sender._cached_token is None


class TestRefreshFailure:
    """Item: no I/O under the cache lock, keep a still-valid token, back off 30 s."""

    def _flaky(self, outcomes, token_sink):
        """Token endpoint answers from `outcomes` (True → token, False → 500)."""
        state = {"i": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            token_sink.append(request)
            ok = outcomes[min(state["i"], len(outcomes) - 1)]
            state["i"] += 1
            if ok:
                return httpx.Response(200, json={"access_token": f"ya29.t{state['i']}", "expires_in": 3600})
            return httpx.Response(500)

        return httpx.Client(transport=httpx.MockTransport(handler))

    def test_failed_refresh_keeps_a_still_valid_token(self):
        info = fcm_sender._service_account()
        token_sink: list[httpx.Request] = []
        client = self._flaky([True, False], token_sink)
        first = fcm_sender._access_token(info, client, now=1_000_000)
        # Inside the 5-minute margin: refresh is attempted, fails, old token used.
        assert fcm_sender._access_token(info, client, now=1_000_000 + 3400) == first
        assert len(token_sink) == 2

    def test_failed_exchange_backs_off_for_30_seconds(self):
        info = fcm_sender._service_account()
        token_sink: list[httpx.Request] = []
        client = self._flaky([False, True], token_sink)

        with pytest.raises(RuntimeError):
            fcm_sender._access_token(info, client, now=1_000_000)
        for offset in (1, 10, 29):
            with pytest.raises(RuntimeError, match="backing off"):
                fcm_sender._access_token(info, client, now=1_000_000 + offset)
        assert len(token_sink) == 1  # no re-sign per device during a fan-out

        assert fcm_sender._access_token(info, client, now=1_000_000 + 30) == "ya29.t2"
        assert len(token_sink) == 2

    def test_backoff_still_serves_a_valid_cached_token(self):
        info = fcm_sender._service_account()
        token_sink: list[httpx.Request] = []
        client = self._flaky([True, False], token_sink)
        first = fcm_sender._access_token(info, client, now=1_000_000)
        fcm_sender._access_token(info, client, now=1_003_400)  # fails, sets backoff
        assert fcm_sender._access_token(info, client, now=1_003_410) == first
        assert len(token_sink) == 2

    def test_cache_lock_is_free_during_the_exchange(self):
        info = fcm_sender._service_account()
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            acquired = fcm_sender._lock.acquire(blocking=False)
            seen["cache_lock_free"] = acquired
            if acquired:
                fcm_sender._lock.release()
            return httpx.Response(200, json={"access_token": "ya29.x", "expires_in": 3600})

        fcm_sender._access_token(info, httpx.Client(transport=httpx.MockTransport(handler)), now=1_000_000)
        assert seen["cache_lock_free"] is True

    def test_concurrent_callers_share_one_exchange(self):
        info = fcm_sender._service_account()
        token_sink: list[httpx.Request] = []
        gate = threading.Event()

        def handler(request: httpx.Request) -> httpx.Response:
            token_sink.append(request)
            gate.wait(timeout=2)
            return httpx.Response(200, json={"access_token": "ya29.shared", "expires_in": 3600})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        results: list[str] = []
        threads = [
            threading.Thread(target=lambda: results.append(fcm_sender._access_token(info, client, now=1_000_000)))
            for _ in range(5)
        ]
        for t in threads:
            t.start()
        gate.set()
        for t in threads:
            t.join(timeout=5)

        assert results == ["ya29.shared"] * 5
        assert len(token_sink) == 1


class TestResponseMapping:
    def test_200_is_sent(self):
        result = send_fcm(_device(), _PAYLOAD, client=_client((200, {"name": "x"})))
        assert result.ok
        assert result.http_status == 200

    @pytest.mark.parametrize("error_code", ["UNREGISTERED", "UNREGISTERED_FID"])
    def test_404_with_unregistered_code_is_expired(self, error_code):
        body = _fcm_error(404, "NOT_FOUND", error_code=error_code)
        result = send_fcm(_device(), _PAYLOAD, client=_client((404, body)))
        assert result.expired
        assert result.http_status == 404
        assert result.error == error_code

    def test_bare_404_is_failed_not_expired(self):
        """No body / no FCM error code: likely a wrong project id. Never prune on it."""
        result = send_fcm(_device(), _PAYLOAD, client=_client((404, None)))
        assert result.status == "failed"
        assert result.error == "HTTP 404"

    def test_404_with_only_a_status_is_failed(self):
        result = send_fcm(_device(), _PAYLOAD, client=_client((404, _fcm_error(404, "NOT_FOUND"))))
        assert result.status == "failed"

    def test_unregistered_error_code_is_expired_whatever_the_status(self):
        body = _fcm_error(400, "INVALID_ARGUMENT", error_code="UNREGISTERED")
        result = send_fcm(_device(), _PAYLOAD, client=_client((400, body)))
        assert result.expired

    def test_sender_id_mismatch_is_failed_not_expired(self):
        """Credential/project problem — pruning on it would wipe every device."""
        body = _fcm_error(403, "PERMISSION_DENIED", error_code="SENDER_ID_MISMATCH")
        result = send_fcm(_device(), _PAYLOAD, client=_client((403, body)))
        assert result.status == "failed"
        assert result.error == "SENDER_ID_MISMATCH"

    @pytest.mark.parametrize(
        "message",
        [
            "The registration token is not a valid FCM registration token",
            "Invalid FID",
            "The installation ID is not valid",
        ],
    )
    def test_invalid_argument_naming_the_device_is_expired(self, message):
        body = _fcm_error(400, "INVALID_ARGUMENT", message=message, error_code="INVALID_ARGUMENT")
        result = send_fcm(_device(), _PAYLOAD, client=_client((400, body)))
        assert result.expired

    def test_other_invalid_argument_is_failed_not_expired(self):
        body = _fcm_error(
            400, "INVALID_ARGUMENT", message="Invalid value at 'message.data[0].value'", error_code="INVALID_ARGUMENT"
        )
        result = send_fcm(_device(), _PAYLOAD, client=_client((400, body)))
        assert result.status == "failed"
        assert result.http_status == 400
        assert result.error == "INVALID_ARGUMENT"

    @pytest.mark.parametrize("status", [429, 500, 503])
    def test_throttle_and_server_errors_fail_without_retry(self, status):
        sink: list[httpx.Request] = []
        result = send_fcm(_device(), _PAYLOAD, client=_client((status, None), sink=sink))
        assert result.status == "failed"
        assert result.http_status == status
        assert result.error == f"HTTP {status}"
        assert len(sink) == 1

    def test_quota_exceeded_error_code_is_surfaced(self):
        body = _fcm_error(429, "RESOURCE_EXHAUSTED", error_code="QUOTA_EXCEEDED")
        result = send_fcm(_device(), _PAYLOAD, client=_client((429, body)))
        assert result.status == "failed"
        assert result.error == "QUOTA_EXCEEDED"

    @pytest.mark.parametrize(
        "body",
        [
            {"error": "bad"},
            {"error": {"details": "not-a-list", "status": 7, "message": None}},
            {"error": {"details": [{"errorCode": 42}, "junk", None]}},
            ["not", "a", "dict"],
            "<html>gateway</html>",
        ],
    )
    def test_malformed_error_bodies_never_raise(self, body):
        result = send_fcm(_device(), _PAYLOAD, client=_client((400, body)))
        assert result.status == "failed"
        assert result.http_status == 400
        assert result.error == "HTTP 400"

    def test_transport_error_is_failed_and_does_not_raise(self):
        def boom(_request):
            raise httpx.ConnectError("no route")

        client = httpx.Client(transport=httpx.MockTransport(boom))
        result = send_fcm(_device(), _PAYLOAD, client=client)
        assert result.status == "failed"
        assert "no route" in (result.error or "")

    def test_bad_key_is_failed_and_does_not_raise(self, monkeypatch):
        monkeypatch.setenv("FCM_SERVICE_ACCOUNT_JSON", json.dumps(_account("not a pem")))
        result = send_fcm(_device(), _PAYLOAD, client=_client())
        assert result.status == "failed"

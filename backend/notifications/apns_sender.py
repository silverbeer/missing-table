"""APNs sender — native iOS push (SB-1236).

Token-based auth: an ES256 provider JWT signed with the .p8 key from the
Apple developer account, sent over HTTP/2 (httpx + h2). Apple rejects a
provider token older than an hour and throttles one refreshed more often
than every 20 minutes, so it is cached and reused for 50.

Env:
  APNS_KEY_ID           — 10-char key id (JWT `kid`)
  APNS_TEAM_ID          — 10-char team id (JWT `iss`)
  APNS_PRIVATE_KEY      — PEM contents of the .p8, or
  APNS_PRIVATE_KEY_PATH — path to the .p8
  APNS_BUNDLE_ID        — apns-topic; defaults to io.silverbeer.mt

Mirrors web_push_sender: never raises, returns the same SendResult, and
reports tokens APNs says are gone as STATUS_EXPIRED so the caller deletes them.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

import httpx
import structlog

from notifications.web_push_sender import (
    STATUS_EXPIRED,
    STATUS_FAILED,
    STATUS_SENT,
    SendResult,
)

logger = structlog.get_logger(__name__)

DEFAULT_BUNDLE_ID = "io.silverbeer.mt"

HOST_SANDBOX = "api.sandbox.push.apple.com"
HOST_PRODUCTION = "api.push.apple.com"

# Reuse the provider token for 50 minutes (Apple: < 60, refresh >= 20).
TOKEN_TTL_SECONDS = 50 * 60

# apns-collapse-id is capped at 64 bytes by APNs.
COLLAPSE_ID_MAX_BYTES = 64

# 400 reasons meaning "this token will never work here" — drop the device.
# Unregistered normally arrives as 410, which is expired regardless of reason.
_EXPIRED_REASONS = frozenset({"BadDeviceToken", "Unregistered", "DeviceTokenNotForTopic"})

# 403 reasons meaning our cached provider token is bad — mint a new one.
_PROVIDER_TOKEN_REASONS = frozenset({"ExpiredProviderToken", "InvalidProviderToken"})

_lock = threading.Lock()
_cached_token: tuple[str, float, tuple[str, str, str]] | None = None  # (jwt, issued_at, config key)
_client: httpx.Client | None = None


def _private_key() -> str | None:
    """PEM from APNS_PRIVATE_KEY, else from the file at APNS_PRIVATE_KEY_PATH."""
    pem = os.getenv("APNS_PRIVATE_KEY")
    if pem:
        # Secret stores often flatten newlines to a literal "\n".
        return pem.replace("\\n", "\n")
    path = os.getenv("APNS_PRIVATE_KEY_PATH")
    if path:
        try:
            with open(path) as fh:
                return fh.read()
        except OSError:
            return None
    return None


def is_configured() -> bool:
    """True if key id, team id and a private key are all available. Backend
    boots without them (APNs fan-out is a no-op until configured).
    """
    return bool(os.getenv("APNS_KEY_ID") and os.getenv("APNS_TEAM_ID") and _private_key())


def get_bundle_id() -> str:
    return os.getenv("APNS_BUNDLE_ID") or DEFAULT_BUNDLE_ID


def host_for(environment: str | None) -> str:
    """'production' → api.push.apple.com; anything else → sandbox."""
    return HOST_PRODUCTION if environment == "production" else HOST_SANDBOX


def _provider_token(now: float | None = None) -> str:
    """ES256 provider JWT, cached for TOKEN_TTL_SECONDS. Raises if unconfigured."""
    global _cached_token
    import jwt  # PyJWT; lazy to keep the import surface tight at module load

    now = time.time() if now is None else now
    key_id = os.environ["APNS_KEY_ID"]
    team_id = os.environ["APNS_TEAM_ID"]
    pem = _private_key()
    if not pem:
        raise RuntimeError("APNs private key not available")
    # A config change (key rotation) must not keep serving the old token.
    config_key = (key_id, team_id, pem)
    with _lock:
        if _cached_token is not None:
            token, issued_at, cached_key = _cached_token
            if cached_key == config_key and now - issued_at < TOKEN_TTL_SECONDS:
                return token
        token = jwt.encode(
            {"iss": team_id, "iat": int(now)},
            pem,
            algorithm="ES256",
            headers={"kid": key_id},
        )
        _cached_token = (token, now, config_key)
        return token


def _invalidate_provider_token() -> None:
    global _cached_token
    with _lock:
        _cached_token = None


def _get_client() -> httpx.Client:
    """Process-wide HTTP/2 client. APNs wants connections reused, not reopened
    per notification. Created lazily so a forked worker builds its own.
    """
    global _client
    with _lock:
        if _client is None:
            _client = httpx.Client(http2=True, timeout=10.0)
        return _client


def _collapse_id(tag: str | None) -> str | None:
    if not tag:
        return None
    encoded = tag.encode("utf-8")[:COLLAPSE_ID_MAX_BYTES]
    return encoded.decode("utf-8", errors="ignore") or None


def build_apns_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map the Web Push payload (title/body/tag/data) to an APNs body.

    aps.thread-id groups a match's notifications in Notification Center;
    matchId/eventType sit at the top level for the app's tap handler.
    """
    data = payload.get("data") or {}
    aps: dict[str, Any] = {
        "alert": {"title": payload.get("title", ""), "body": payload.get("body", "")},
        "sound": "default",
    }
    match_id = data.get("matchId")
    if match_id is not None:
        aps["thread-id"] = f"match-{match_id}"
    body: dict[str, Any] = {"aps": aps}
    if match_id is not None:
        body["matchId"] = match_id
    if data.get("eventType") is not None:
        body["eventType"] = data["eventType"]
    return body


def _reason(response: httpx.Response) -> str | None:
    try:
        return response.json().get("reason")
    except Exception:
        return None


def send_apns(
    device: dict[str, Any],
    payload: dict[str, Any],
    *,
    client: httpx.Client | None = None,
) -> SendResult:
    """Send a single APNs alert. Never raises.

    device dict must include `device_token` and `environment`; `bundle_id`
    overrides APNS_BUNDLE_ID for the apns-topic. payload is the Web Push
    payload built by the dispatcher — see build_apns_payload.
    """
    if not is_configured():
        return SendResult(status=STATUS_FAILED, error="APNs not configured")

    token = device.get("device_token")
    if not token:
        return SendResult(status=STATUS_FAILED, error="invalid device")

    try:
        headers = {
            "authorization": f"bearer {_provider_token()}",
            "apns-topic": device.get("bundle_id") or get_bundle_id(),
            "apns-push-type": "alert",
            "apns-priority": "10",
        }
        collapse_id = _collapse_id(payload.get("tag"))
        if collapse_id:
            headers["apns-collapse-id"] = collapse_id

        url = f"https://{host_for(device.get('environment'))}/3/device/{token}"
        response = (client or _get_client()).post(
            url,
            content=json.dumps(build_apns_payload(payload)),
            headers=headers,
        )
    except Exception as exc:
        return SendResult(status=STATUS_FAILED, error=str(exc))

    http_status = response.status_code
    if http_status == 200:
        return SendResult(status=STATUS_SENT, http_status=http_status)

    reason = _reason(response)
    error = reason or f"HTTP {http_status}"
    if http_status == 410 or (http_status == 400 and reason in _EXPIRED_REASONS):
        return SendResult(status=STATUS_EXPIRED, http_status=http_status, error=error)
    if http_status == 403 and reason in _PROVIDER_TOKEN_REASONS:
        # Next send mints a fresh provider token.
        _invalidate_provider_token()
    return SendResult(status=STATUS_FAILED, http_status=http_status, error=error)

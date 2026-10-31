"""FCM sender — native Android push (SB-1463).

Firebase Cloud Messaging HTTP v1. Auth is a Google service account: we sign
an RS256 JWT with its private key, exchange it at the token endpoint for an
OAuth2 access token (OAuth 2.0 JWT bearer grant), and send with that. The
access token lasts an hour; it is cached and refreshed 5 minutes early. No
google-auth dependency — PyJWT + httpx are already here for APNs.

Devices are addressed by Firebase Installation ID (Message.fid); FCM v1 has
deprecated Message.token in its favour.

Env:
  FCM_SERVICE_ACCOUNT_JSON — the service-account key JSON, or
  FCM_SERVICE_ACCOUNT_PATH — path to that JSON file

Mirrors apns_sender: never raises, returns the same SendResult, and reports
installations FCM says are gone as STATUS_EXPIRED so the caller deletes them.
Never logs or returns the service-account key or any token.
"""

from __future__ import annotations

import json
import os
import re
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

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"
SEND_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"

# Lifetime of the signed assertion (Google's maximum).
ASSERTION_TTL_SECONDS = 60 * 60

# Mint a new access token this long before the current one expires.
REFRESH_MARGIN_SECONDS = 5 * 60

# After a failed token exchange, don't try again for this long — a fan-out
# would otherwise re-sign and re-POST once per device.
FAILED_EXCHANGE_BACKOFF_SECONDS = 30

# How long FCM holds a message for an offline device. Same rationale as
# web_push_sender: a goal that arrives 5 minutes late is just noise.
MESSAGE_TTL = "60s"

# Android notification channel the app creates for live-match alerts.
CHANNEL_ID = "live_scores"

# FcmError.errorCode values meaning "this installation will never work here".
# SENDER_ID_MISMATCH is deliberately absent: it means our credentials or
# project are wrong, and pruning on it would wipe every device.
_EXPIRED_ERROR_CODES = frozenset({"UNREGISTERED", "UNREGISTERED_FID"})

# An INVALID_ARGUMENT only means a dead device when it names the address.
_DEVICE_ARGUMENT_RE = re.compile(r"registration token|installation id|\bfid\b", re.IGNORECASE)

_REQUIRED_FIELDS = ("project_id", "client_email", "private_key")

# _lock guards the cache only — never held across network I/O.
_lock = threading.Lock()
# Serialises refreshes so only one thread exchanges at a time.
_refresh_lock = threading.Lock()
_client_lock = threading.Lock()
# (access_token, expires_at, config key)
_cached_token: tuple[str, float, tuple[str, str]] | None = None
# (retry_after, config key) after a failed exchange
_failed_exchange: tuple[float, tuple[str, str]] | None = None
_client: httpx.Client | None = None
_warned_misconfigured = False


def _warn_misconfigured(source: str, reason: str) -> None:
    """One warning per process when FCM env is set but unusable. Never logs the value."""
    global _warned_misconfigured
    if _warned_misconfigured:
        return
    _warned_misconfigured = True
    logger.warning("fcm.misconfigured", source=source, reason=reason)


def _service_account() -> dict[str, Any] | None:
    """Parsed service account from FCM_SERVICE_ACCOUNT_JSON, else the file at
    FCM_SERVICE_ACCOUNT_PATH. None unless it parses and has the fields we need.
    Silent when neither is set.
    """
    source = "FCM_SERVICE_ACCOUNT_JSON"
    raw = os.getenv(source)
    if not raw:
        source = "FCM_SERVICE_ACCOUNT_PATH"
        path = os.getenv(source)
        if not path:
            return None
        try:
            with open(path) as fh:
                raw = fh.read()
        except (OSError, ValueError):
            _warn_misconfigured(source, "unreadable")
            return None
    try:
        # strict=False: secret stores sometimes turn "\n" escapes into raw newlines.
        info = json.loads(raw, strict=False)
    except ValueError:
        _warn_misconfigured(source, "invalid_json")
        return None
    if not isinstance(info, dict) or not all(isinstance(info.get(f), str) and info.get(f) for f in _REQUIRED_FIELDS):
        _warn_misconfigured(source, "missing_fields")
        return None
    # Secret stores sometimes double-escape, leaving a literal "\n" in the PEM.
    info["private_key"] = info["private_key"].replace("\\n", "\n")
    return info


def is_configured() -> bool:
    """True if a usable service account is available. Backend boots without
    one (FCM fan-out is a no-op until configured).
    """
    return _service_account() is not None


def _get_client() -> httpx.Client:
    """Process-wide HTTP client, created lazily so a forked worker builds its own."""
    global _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(timeout=10.0)
        return _client


def _sign_assertion(info: dict[str, Any], token_uri: str, now: float) -> str:
    import jwt  # PyJWT; lazy to keep the import surface tight at module load

    claims = {
        "iss": info["client_email"],
        "scope": SCOPE,
        "aud": token_uri,
        "iat": int(now),
        "exp": int(now) + ASSERTION_TTL_SECONDS,
    }
    headers = {"kid": info["private_key_id"]} if info.get("private_key_id") else None
    return jwt.encode(claims, info["private_key"], algorithm="RS256", headers=headers)


def _exchange(info: dict[str, Any], client: httpx.Client, now: float) -> tuple[str, float]:
    """One JWT-bearer exchange. Returns (access_token, expires_at); raises on failure."""
    token_uri = info.get("token_uri") or DEFAULT_TOKEN_URI
    assertion = _sign_assertion(info, token_uri, now)
    response = client.post(
        token_uri,
        data={"grant_type": GRANT_TYPE, "assertion": assertion},
    )
    try:
        body = response.json()
    except Exception:
        body = None
    if not isinstance(body, dict):
        body = {}
    token = body.get("access_token")
    if response.status_code != 200 or not isinstance(token, str) or not token:
        # body["error"] is an OAuth error code (e.g. invalid_grant) — safe to surface.
        code = body.get("error") if isinstance(body.get("error"), str) else ""
        raise RuntimeError(f"FCM token exchange failed: HTTP {response.status_code} {code}".strip())
    try:
        expires_in = float(body.get("expires_in") or ASSERTION_TTL_SECONDS)
    except (TypeError, ValueError):
        expires_in = float(ASSERTION_TTL_SECONDS)
    return token, now + expires_in


def _cached_for(config_key: tuple[str, str], now: float, margin: float) -> str | None:
    """Cached token for this config if it is valid for at least `margin` more seconds."""
    with _lock:
        if _cached_token is not None:
            token, expires_at, cached_key = _cached_token
            if cached_key == config_key and now < expires_at - margin:
                return token
    return None


def _access_token(
    info: dict[str, Any],
    client: httpx.Client,
    now: float | None = None,
) -> str:
    """OAuth2 access token for the FCM scope, cached until 5 minutes before
    expiry. If a refresh fails, a cached token that has not actually expired
    is still used, and no new exchange is tried for 30 s. Raises when there
    is no usable token (callers turn that into a failed send).
    """
    global _cached_token, _failed_exchange
    now = time.time() if now is None else now
    # A key rotation must not keep serving the old account's token.
    config_key = (info["client_email"], info["private_key"])

    fresh = _cached_for(config_key, now, REFRESH_MARGIN_SECONDS)
    if fresh:
        return fresh

    with _refresh_lock:
        # Another thread may have refreshed while we waited.
        fresh = _cached_for(config_key, now, REFRESH_MARGIN_SECONDS)
        if fresh:
            return fresh

        with _lock:
            backing_off = (
                _failed_exchange is not None and _failed_exchange[1] == config_key and now < _failed_exchange[0]
            )
        if backing_off:
            still_valid = _cached_for(config_key, now, 0)
            if still_valid:
                return still_valid
            raise RuntimeError("FCM token exchange failed recently; backing off")

        try:
            token, expires_at = _exchange(info, client, now)
        except Exception:
            with _lock:
                _failed_exchange = (now + FAILED_EXCHANGE_BACKOFF_SECONDS, config_key)
            still_valid = _cached_for(config_key, now, 0)
            if still_valid:
                return still_valid
            raise

        with _lock:
            _cached_token = (token, expires_at, config_key)
            _failed_exchange = None
        return token


def _invalidate_access_token() -> None:
    global _cached_token
    with _lock:
        _cached_token = None


def build_fcm_message(fid: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Map the Web Push payload (title/body/tag/data) to an FCM v1 message.

    data values must all be strings in FCM; matchId/eventType/url carry the
    app's tap handler to the match. android.notification.tag makes a repeat
    of the same (match, event) replace the earlier one in the shade.
    collapse_key is set too, but FCM only collapses data messages by it —
    these are notification messages, so tag is what dedupes on-device.
    """
    data = payload.get("data") or {}
    message: dict[str, Any] = {
        "fid": fid,
        "notification": {"title": payload.get("title", ""), "body": payload.get("body", "")},
    }
    fcm_data = {k: str(data[k]) for k in ("matchId", "eventType", "url") if data.get(k) is not None}
    if fcm_data:
        message["data"] = fcm_data

    android_notification: dict[str, Any] = {"channel_id": CHANNEL_ID}
    android: dict[str, Any] = {"priority": "high", "ttl": MESSAGE_TTL, "notification": android_notification}
    tag = payload.get("tag")
    if tag:
        android["collapse_key"] = tag
        android_notification["tag"] = tag
    message["android"] = android
    return {"message": message}


def _error_info(response: httpx.Response) -> tuple[str | None, str | None, str]:
    """(errorCode from FcmError details, google.rpc status, message).

    Tolerates any body shape — this runs inside send_fcm's never-raises contract.
    """
    try:
        body = response.json()
    except Exception:
        return None, None, ""
    err = body.get("error") if isinstance(body, dict) else None
    if not isinstance(err, dict):
        return None, None, ""
    error_code = None
    details = err.get("details")
    if isinstance(details, list):
        for detail in details:
            code = detail.get("errorCode") if isinstance(detail, dict) else None
            if isinstance(code, str) and code:
                error_code = code
                break
    rpc_status = err.get("status") if isinstance(err.get("status"), str) else None
    message = err.get("message") if isinstance(err.get("message"), str) else ""
    return error_code, rpc_status, message


def _is_expired(http_status: int, error_code: str | None, rpc_status: str | None, message: str) -> bool:
    """Only FCM's explicit "this installation is gone" answers count. A bare
    404 or SENDER_ID_MISMATCH is a project/credential problem, not a dead device.
    """
    if error_code in _EXPIRED_ERROR_CODES:
        return True
    # INVALID_ARGUMENT covers bad payloads too; only a bad address means drop it.
    if http_status == 400 and "INVALID_ARGUMENT" in (error_code, rpc_status):
        return bool(_DEVICE_ARGUMENT_RE.search(message or ""))
    return False


def send_fcm(
    device: dict[str, Any],
    payload: dict[str, Any],
    *,
    client: httpx.Client | None = None,
) -> SendResult:
    """Send a single FCM notification. Never raises.

    device dict must include `fid`. payload is the Web Push payload built by
    the dispatcher — see build_fcm_message. A 401 drops the cached access
    token and retries once; 429/5xx fail without retry.
    """
    info = _service_account()
    if info is None:
        return SendResult(status=STATUS_FAILED, error="FCM not configured")

    fid = device.get("fid")
    if not fid:
        return SendResult(status=STATUS_FAILED, error="invalid device")

    try:
        http = client or _get_client()
        url = SEND_URL.format(project_id=info["project_id"])
        body = build_fcm_message(fid, payload)
        response = None
        for _attempt in range(2):
            access_token = _access_token(info, http)
            response = http.post(
                url,
                json=body,
                headers={"authorization": f"Bearer {access_token}"},
            )
            if response.status_code != 401:
                break
            # Access token rejected (revoked, clock skew) — mint a fresh one.
            _invalidate_access_token()

        http_status = response.status_code
        if http_status == 200:
            return SendResult(status=STATUS_SENT, http_status=http_status)

        error_code, rpc_status, message = _error_info(response)
        error = error_code or rpc_status or f"HTTP {http_status}"
        if _is_expired(http_status, error_code, rpc_status, message):
            return SendResult(status=STATUS_EXPIRED, http_status=http_status, error=error)
        return SendResult(status=STATUS_FAILED, http_status=http_status, error=error)
    except Exception as exc:
        return SendResult(status=STATUS_FAILED, error=str(exc))

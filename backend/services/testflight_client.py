"""App Store Connect client — TestFlight external beta testers (SB-1314).

Admins tick "iPhone beta" on an invite; the backend adds the invitee to the
external TestFlight group so Apple emails them a TestFlight invitation.

Auth is an ES256 JWT signed with an App Store Connect API key (.p8), minted
per operation — one invite makes at most three calls, so caching buys nothing.

Env:
  ASC_KEY_ID            — API key id (JWT `kid`)
  ASC_ISSUER_ID         — issuer id from App Store Connect (JWT `iss`)
  ASC_PRIVATE_KEY       — PEM contents of the .p8 (literal "\\n" accepted)
  ASC_EXTERNAL_GROUP_ID — the external beta group testers are added to
  ASC_APP_ID            — the app's Apple id; defaults to 6820504545

Mirrors apns_sender: never raises, and is a no-op until configured.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger(__name__)

BASE_URL = "https://api.appstoreconnect.apple.com"
DEFAULT_APP_ID = "6820504545"

# Apple rejects a token whose lifetime exceeds 20 minutes.
TOKEN_LIFETIME_SECONDS = 15 * 60

# Called inline from the invite request: keep it short.
TIMEOUT_SECONDS = 10.0

STATUS_ADDED = "added"
STATUS_FAILED = "failed"
STATUS_REMOVED = "removed"


@dataclass
class TesterResult:
    status: str
    tester_id: str | None = None
    error: str | None = None


def _private_key() -> str | None:
    pem = os.getenv("ASC_PRIVATE_KEY")
    if not pem:
        return None
    # Secret stores often flatten newlines to a literal "\n".
    return pem.replace("\\n", "\n")


def is_configured() -> bool:
    """True if key id, issuer id, private key and group id are all set.
    The backend boots without them; iPhone beta invites then record a failure.
    """
    return bool(
        os.getenv("ASC_KEY_ID") and os.getenv("ASC_ISSUER_ID") and _private_key() and os.getenv("ASC_EXTERNAL_GROUP_ID")
    )


def get_app_id() -> str:
    return os.getenv("ASC_APP_ID") or DEFAULT_APP_ID


def _group_id() -> str:
    return os.environ["ASC_EXTERNAL_GROUP_ID"]


def _token(now: float | None = None) -> str:
    """ES256 JWT for the App Store Connect API. Raises if unconfigured."""
    import jwt  # PyJWT; lazy, as in apns_sender

    now = time.time() if now is None else now
    pem = _private_key()
    if not pem:
        raise RuntimeError("App Store Connect private key not available")
    return jwt.encode(
        {
            "iss": os.environ["ASC_ISSUER_ID"],
            "iat": int(now),
            "exp": int(now) + TOKEN_LIFETIME_SECONDS,
            "aud": "appstoreconnect-v1",
        },
        pem,
        algorithm="ES256",
        headers={"kid": os.environ["ASC_KEY_ID"], "typ": "JWT"},
    )


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}


def _error(response: httpx.Response) -> str:
    """First error detail from an ASC error body, else the HTTP status."""
    try:
        errors = response.json().get("errors") or []
        if errors:
            first = errors[0]
            return f"HTTP {response.status_code}: {first.get('detail') or first.get('title') or first.get('code')}"
    except Exception:
        pass
    return f"HTTP {response.status_code}"


def _group_membership_body(tester_id: str) -> dict:
    return {"data": [{"type": "betaTesters", "id": tester_id}]}


def _find_tester_id(client: httpx.Client, email: str) -> str | None:
    response = client.get(
        f"{BASE_URL}/v1/betaTesters",
        params={"filter[email]": email},
        headers=_headers(),
    )
    if response.status_code != 200:
        raise RuntimeError(f"tester lookup failed: {_error(response)}")
    data = response.json().get("data") or []
    return data[0]["id"] if data else None


def add_tester(
    email: str,
    first_name: str | None = None,
    last_name: str | None = None,
    *,
    client: httpx.Client | None = None,
) -> TesterResult:
    """Add `email` to the external TestFlight group. Never raises.

    Creates the tester with the group relationship; if Apple says the tester
    already exists (409), looks them up by email and adds them to the group,
    so re-inviting someone — or retrying — is safe.
    """
    if not is_configured():
        return TesterResult(status=STATUS_FAILED, error="App Store Connect not configured")
    if not email:
        return TesterResult(status=STATUS_FAILED, error="no TestFlight email")

    group_id = _group_id()
    attributes = {"email": email}
    if first_name:
        attributes["firstName"] = first_name
    if last_name:
        attributes["lastName"] = last_name
    body = {
        "data": {
            "type": "betaTesters",
            "attributes": attributes,
            "relationships": {"betaGroups": {"data": [{"type": "betaGroups", "id": group_id}]}},
        }
    }

    own_client = client is None
    http = client or httpx.Client(timeout=TIMEOUT_SECONDS)
    try:
        response = http.post(f"{BASE_URL}/v1/betaTesters", json=body, headers=_headers())
        if response.status_code in (200, 201):
            tester_id = (response.json().get("data") or {}).get("id")
            return TesterResult(status=STATUS_ADDED, tester_id=tester_id)
        if response.status_code != 409:
            return TesterResult(status=STATUS_FAILED, error=_error(response))

        tester_id = _find_tester_id(http, email)
        if not tester_id:
            return TesterResult(status=STATUS_FAILED, error="tester exists but lookup by email found none")
        added = http.post(
            f"{BASE_URL}/v1/betaGroups/{group_id}/relationships/betaTesters",
            json=_group_membership_body(tester_id),
            headers=_headers(),
        )
        if added.status_code in (200, 201, 204):
            return TesterResult(status=STATUS_ADDED, tester_id=tester_id)
        return TesterResult(status=STATUS_FAILED, tester_id=tester_id, error=_error(added))
    except Exception as exc:
        return TesterResult(status=STATUS_FAILED, error=str(exc))
    finally:
        if own_client:
            http.close()


def remove_tester(tester_id: str, *, client: httpx.Client | None = None) -> TesterResult:
    """Remove a tester from the external group. Never raises."""
    if not is_configured():
        return TesterResult(status=STATUS_FAILED, tester_id=tester_id, error="App Store Connect not configured")
    if not tester_id:
        return TesterResult(status=STATUS_FAILED, error="no tester id")

    own_client = client is None
    http = client or httpx.Client(timeout=TIMEOUT_SECONDS)
    try:
        # httpx.delete() takes no body; request() does.
        response = http.request(
            "DELETE",
            f"{BASE_URL}/v1/betaGroups/{_group_id()}/relationships/betaTesters",
            json=_group_membership_body(tester_id),
            headers=_headers(),
        )
        if response.status_code in (200, 204):
            return TesterResult(status=STATUS_REMOVED, tester_id=tester_id)
        return TesterResult(status=STATUS_FAILED, tester_id=tester_id, error=_error(response))
    except Exception as exc:
        return TesterResult(status=STATUS_FAILED, tester_id=tester_id, error=str(exc))
    finally:
        if own_client:
            http.close()

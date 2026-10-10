"""Who is calling mt-mcp (SB-1302).

`MTTokenVerifier` is the MCP SDK's bearer-token hook. It accepts exactly the
tokens /api/ai/* accepts — a Supabase session, or an API account's token
(SB-1145) — and nothing else: service-account tokens are refused, because a
service account has no user_profiles row to own provenance or decide test
visibility. A refused token is a 401 from the SDK.

The caller's profile travels in the SDK's `AccessToken.claims`; tools read it
back with `current_principal()`, never from their arguments.
"""

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import structlog
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken

logger = structlog.get_logger()

CLAIM = "mt_principal"

VerifyFn = Callable[[str], dict[str, Any] | None]


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str | None
    username: str | None = None
    team_id: int | None = None
    club_id: int | None = None
    is_test: bool = False
    is_api_account: bool = False

    @classmethod
    def from_user(cls, user: dict[str, Any]) -> "Principal":
        return cls(
            user_id=str(user["user_id"]),
            role=user.get("role"),
            username=user.get("username"),
            team_id=user.get("team_id"),
            club_id=user.get("club_id"),
            is_test=bool(user.get("is_test")),
            is_api_account=bool(user.get("is_api_account")),
        )

    def as_user(self) -> dict[str, Any]:
        """The dict shape auth.py's checks take (`viewer_sees_test_content`, `can_manage_team`)."""
        return asdict(self)


class MTTokenVerifier:
    """Bearer token → AccessToken carrying the caller's Principal, or None."""

    def __init__(self, verify_session: VerifyFn, verify_api_account: VerifyFn) -> None:
        self._verifiers = (verify_session, verify_api_account)

    async def verify_token(self, token: str) -> AccessToken | None:
        # auth_manager's checks are synchronous and read user_profiles.
        user = await asyncio.to_thread(self._resolve, token)
        if not user or not user.get("user_id"):
            return None
        principal = Principal.from_user(user)
        return AccessToken(
            token=token,
            client_id="mt",
            scopes=[],
            subject=principal.user_id,
            claims={CLAIM: principal.as_user()},
        )

    def _resolve(self, token: str) -> dict[str, Any] | None:
        for verify in self._verifiers:
            try:
                user = verify(token)
            except Exception:
                logger.exception("mt_mcp token verification failed")
                return None
            if user:
                return user
        return None


def current_principal() -> Principal | None:
    """The authenticated caller of the current MCP request, if any."""
    token = get_access_token()
    if token is None or not token.claims or CLAIM not in token.claims:
        return None
    data = token.claims[CLAIM]
    return Principal(**data)

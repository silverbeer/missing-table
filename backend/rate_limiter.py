"""
Rate limiting for the authentication endpoints (SB-640).

This module holds **only limits that are actually enforced**. It used to
carry a four-category policy — public, authenticated, admin, auth — none of
which was in effect: the middleware and every decorator were commented out,
so `RATE_LIMITS` read as a live policy while login and signup were
unthrottled. Dead security config that reads as active is worse than none,
because it invites the assumption that login is throttled when it is not.

Two decisions worth keeping:

**No global default limits, and no SlowAPIMiddleware.** `SlowAPIMiddleware`
exists to apply `default_limits` to every request. The old defaults were 200
per hour and 50 per minute, which the product itself would breach: the LIVE
tab polls while a match is being scored, and ingest posts fixtures in bulk.
Turning that on would have looked like an outage. Limits are applied per
endpoint with `@rate_limit(...)` instead, which needs no middleware — so the
"middleware order issue" the old code hedged about does not arise.

**The key is the forwarded client IP, not the socket peer.** Behind the
ingress every request arrives from one address, so keying on
`slowapi.util.get_remote_address` would put every user in the world into a
single bucket and five failed logins anywhere would lock out everyone. The
app already resolves the real client for audit logging; this uses the same
rule. `X-Forwarded-For` is spoofable by a direct caller, but the ingress
rewrites it, and the alternative is a shared bucket that is trivially
exhausted by accident.
"""

import logging
import os

import redis
from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

# Redis makes one limit hold across every backend pod. Without it each pod
# counts on its own, so the effective limit is (pods x limit) — still a
# limit, just a looser one. Prod sets REDIS_URL; local usually does not.
REDIS_URL = os.getenv("REDIS_URL", "")

# Limits for the credential endpoints. These are the ones being enforced;
# anything added here must also be applied to a route to be real.
RATE_LIMITS = {
    "login": "5 per minute",
    "signup": "3 per hour",
    "password_reset": "3 per hour",
}


def client_key(request: Request) -> str:
    """The bucket a request counts against: its originating client.

    Mirrors `get_client_ip` in app.py rather than importing it, to keep this
    module free of an app-level import cycle. Both must stay in step: if one
    starts trusting a different header, a limit silently becomes global.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _storage_uri() -> str | None:
    """Redis when it answers, None (in-memory) when it does not.

    Checked once at import: a limiter pointed at an unreachable Redis fails
    every request it is asked to count, which would take down login rather
    than protect it.
    """
    if not REDIS_URL:
        return None
    try:
        redis.from_url(REDIS_URL, socket_connect_timeout=2).ping()
    except Exception as exc:
        logger.warning("rate_limit_redis_unavailable falling back to in-memory: %s", exc)
        return None
    logger.info("rate_limit_storage_redis")
    return REDIS_URL


# headers_enabled is off deliberately. slowapi injects X-RateLimit-* by
# writing to a `response: Response` parameter, which every decorated
# endpoint would then have to declare — and an endpoint that forgets raises
# at request time, turning a missing annotation into a broken login. The
# 429 still carries Retry-After, which is the part a client acts on.
limiter = Limiter(key_func=client_key, storage_uri=_storage_uri(), headers_enabled=False)


def install_rate_limiting(app) -> Limiter:
    """Attach the limiter to the app so `@rate_limit(...)` decorators work.

    slowapi reads `app.state.limiter` when a decorated endpoint runs, and
    needs a handler for RateLimitExceeded to turn it into a 429 instead of a
    500. No middleware is added on purpose — see the module docstring.
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    return limiter


def rate_limit(limit: str):
    """Apply a limit to one endpoint. The endpoint must take `request: Request`."""
    return limiter.limit(limit)

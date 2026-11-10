"""When to try a failed chat post again (SB-1604). Pure: no I/O.

Attempt 1 is the live send. Each failure that may succeed later waits longer
before the next try, honouring the provider's own wait when it gave one (a 429
Retry-After). After MAX_ATTEMPTS the delivery is marked failed for good, which
the channel's "Last post" shows to its managers and admins.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

MAX_ATTEMPTS = 5
BASE_DELAY_SECONDS = 30
MAX_DELAY_SECONDS = 15 * 60


def retry_delay(attempt: int, retry_after: float | None = None, rand: random.Random | None = None) -> float:
    """Seconds to wait after failed attempt `attempt` (1-based).

    30s, 60s, 120s, 240s... capped at 15 minutes, with up to 10% jitter so a
    burst of failures to one provider does not come back all at once. A
    provider's Retry-After is a floor, never shortened.
    """
    backoff = min(BASE_DELAY_SECONDS * 2 ** max(attempt - 1, 0), MAX_DELAY_SECONDS)
    jitter = (rand or random).uniform(0, backoff * 0.1)
    return max(backoff + jitter, retry_after or 0)


def next_attempt(
    attempt: int, retryable: bool, retry_after: float | None, now: datetime, rand: random.Random | None = None
) -> datetime | None:
    """When to try again after failed attempt `attempt`, or None to give up."""
    if not retryable or attempt >= MAX_ATTEMPTS:
        return None
    return now + timedelta(seconds=retry_delay(attempt, retry_after, rand))

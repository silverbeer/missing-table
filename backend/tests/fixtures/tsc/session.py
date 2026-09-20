"""One login shared by the journey run and the cleanup that follows it (SB-1092).

Cleanup runs as a separate pytest process, so it used to log in again. Login is
rate limited to 5 per minute per client IP (SB-640) and a GitHub runner is one
IP, so by the time cleanup started the budget was gone: every phase failed with
429 and nothing was ever deleted. The fixtures then piled up in production.

The token is written to a file both processes can read. It is a production admin
credential, so: outside the repo when TSC_SESSION_FILE says so (CI points it at
the runner's temp dir), owner-readable only, and named to match the
`.entity_registry.*.json` ignore rule when it does fall next to the tests.
"""

import json
import os
import time
from pathlib import Path
from typing import Any

from .entities import get_env_key

# A token is good for an hour; treat it as stale well before that so a long
# journey run does not hand cleanup something that expires mid-delete.
MAX_AGE_SECONDS = 30 * 60


def session_file(base_url: str | None = None) -> Path:
    """Where this environment's shared token lives."""
    override = os.getenv("TSC_SESSION_FILE")
    if override:
        return Path(override)
    url: str = base_url or os.getenv("BASE_URL") or "http://localhost:8000"
    return Path(__file__).resolve().parents[2] / "tsc" / f".entity_registry.session.{get_env_key(url)}.json"


def save_session(token: str, username: str, base_url: str | None = None) -> Path:
    """Record a token for the next process. Never raises — a saved session is an
    optimisation, and failing to save one must not fail a test run."""
    path = session_file(base_url)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {"token": token, "username": username, "saved_at": time.time()}
        path.write_text(json.dumps(payload))
        path.chmod(0o600)
    except OSError:
        pass
    return path


def load_session(base_url: str | None = None, max_age_seconds: int = MAX_AGE_SECONDS) -> dict[str, Any] | None:
    """The saved token, or None if there isn't a usable one."""
    path = session_file(base_url)
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or not payload.get("token"):
        return None
    if time.time() - float(payload.get("saved_at", 0)) > max_age_seconds:
        return None
    return payload


def clear_session(base_url: str | None = None) -> None:
    """Drop the saved token (used when it turns out not to work)."""
    try:
        session_file(base_url).unlink(missing_ok=True)
    except OSError:
        pass

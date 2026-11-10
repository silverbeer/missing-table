"""The contract every chat platform implements.

An adapter owns everything specific to one platform: what a valid destination
looks like, how text is escaped, what configuration it needs, and how a message
is sent. Nothing outside `notifications/adapters/` names a platform's rules, so
adding one is a new module plus a line in `notifications/registry.py`.

Destination values are sensitive and must never appear in logs or in the
messages of exceptions raised here.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

import httpx


class Capability(StrEnum):
    """Optional features a platform supports. Callers degrade when one is absent."""

    THREADS = "threads"


class NotificationConfigError(RuntimeError):
    """The subsystem is missing required config (e.g. a bot token)."""


class UnsupportedPlatformError(ValueError):
    """No adapter is registered under this platform id."""


class InvalidDestinationError(ValueError):
    """A destination does not match the platform's format."""


class DeliveryError(RuntimeError):
    """A send failed. Safe to log.

    Provider errors can't be: an httpx error's text carries the request URL,
    which holds the Telegram bot token or a webhook's secret path.

    `retryable` says whether trying again later could work (rate limit, server
    error, network); `retry_after` is the provider's own wait, in seconds, when
    it gave one (SB-1604).
    """

    def __init__(self, message: str, retryable: bool = False, retry_after: float | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


def _seconds(value) -> float | None:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


def classify_failure(exc: BaseException) -> tuple[bool, float | None]:
    """(retryable, retry_after seconds) for a provider failure (SB-1604). Pure.

    Retryable: HTTP 429 and 5xx, timeouts and other transport errors, and a
    provider error body that names a wait (Discord's and Telegram's rate
    limits). Anything else, e.g. a deleted webhook (404) or a bad chat ID
    (400), will fail the same way again, so it is final.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        wait = _seconds(exc.response.headers.get("Retry-After"))
        if wait is None:
            try:
                body = exc.response.json()
            except Exception:
                body = {}
            if isinstance(body, dict):
                wait = _seconds(body.get("retry_after") or (body.get("parameters") or {}).get("retry_after"))
        return (code == 429 or code >= 500), wait
    if isinstance(exc, httpx.TransportError):
        return True, None
    body = getattr(exc, "response", None)
    if isinstance(body, dict):
        wait = _seconds(body.get("retry_after") or (body.get("parameters") or {}).get("retry_after"))
        if wait is not None:
            return True, wait
    return False, None


@dataclass(frozen=True)
class DeliveryResult:
    """Outcome of a successful send; failures raise.

    `message_ref` is the provider's id for the posted message, or None when the
    provider does not return one (e.g. a webhook answering 204).
    """

    message_ref: str | None = None
    # The thread the message went into, when posted as a match thread (SB-1606).
    thread_ref: str | None = None


class ChannelAdapter(ABC):
    """A chat platform MT can post match updates to."""

    id: ClassVar[str]
    label: ClassVar[str]
    icon: ClassVar[str]
    placeholder: ClassVar[str]
    # What the destination is called on a setup form.
    destination_label: ClassVar[str] = "Webhook URL"
    hint: ClassVar[str]
    # Numbered how-to the setup UI shows under "How to set up". Plain text,
    # one action per step, ending with what to paste.
    setup_steps: ClassVar[tuple[str, ...]]
    # Served to the browser and used in `new RegExp(...)`, so keep it to syntax
    # Python and JavaScript read the same way. Anchors are required.
    destination_pattern: ClassVar[str]
    destination_error: ClassVar[str]
    # The link people use to join: the platform's invite form, never a public
    # page link. The UI never calls a room private: invite links can be forwarded. Same regex rules as above.
    invite_pattern: ClassVar[str]
    invite_error: ClassVar[str]
    capabilities: ClassVar[frozenset[Capability]] = frozenset()
    # Youngest U-number this platform may host as a player channel. None means
    # fans only. Set from the platform's terms, so a change is a one-line edit.
    min_player_age: ClassVar[int | None] = None
    # Shown wherever a channel on this platform is offered (SB-1612): the
    # platform's own minimum age, from its terms. None: nothing to say.
    age_note: ClassVar[str | None] = None
    # Extra steps for a player channel, which is read-only with reactions.
    # Empty: the platform has no such setting to describe.
    player_setup_steps: ClassVar[tuple[str, ...]] = ()

    def validate_destination(self, destination: str) -> None:
        """Raise InvalidDestinationError unless `destination` fits this platform.

        For a webhook platform the pattern is also the SSRF guard, because the
        backend POSTs to whatever is saved here. ASCII mode keeps `\\d` and `\\w`
        identical to the browser's check.
        """
        if not re.fullmatch(self.destination_pattern, destination, flags=re.ASCII):
            raise InvalidDestinationError(self.destination_error)

    def validate_invite_url(self, invite_url: str) -> None:
        """Raise InvalidDestinationError unless `invite_url` is this platform's private join link."""
        if not re.fullmatch(self.invite_pattern, invite_url, flags=re.ASCII):
            raise InvalidDestinationError(self.invite_error)

    def check_config(self) -> None:  # noqa: B027 — optional hook; most platforms need no config
        """Raise NotificationConfigError if the platform cannot send right now."""

    def send(self, destination: str, content: str) -> DeliveryResult:
        """Deliver plain text. Raises NotificationConfigError or DeliveryError.

        `from None` drops the provider exception from the traceback as well,
        since `logger.exception` would otherwise print its URL.
        """
        try:
            return self._deliver(destination, content)
        except NotificationConfigError:
            raise
        except Exception as exc:
            detail = type(exc).__name__
            if isinstance(exc, httpx.HTTPStatusError):
                detail = f"HTTP {exc.response.status_code}"
            retryable, retry_after = classify_failure(exc)
            raise DeliveryError(f"{self.id} send failed: {detail}", retryable, retry_after) from None

    def send_in_thread(
        self, destination: str, content: str, thread_ref: str | None, thread_name: str | None
    ) -> DeliveryResult:
        """Post into a match thread (SB-1606): a new one named `thread_name`, or `thread_ref`.

        Only for platforms with Capability.THREADS; the result carries the
        thread's id. Same error handling as `send`.
        """
        try:
            return self._deliver_in_thread(destination, content, thread_ref, thread_name)
        except NotificationConfigError:
            raise
        except Exception as exc:
            detail = type(exc).__name__
            if isinstance(exc, httpx.HTTPStatusError):
                detail = f"HTTP {exc.response.status_code}"
            retryable, retry_after = classify_failure(exc)
            raise DeliveryError(f"{self.id} send failed: {detail}", retryable, retry_after) from None

    def _deliver_in_thread(
        self, destination: str, content: str, thread_ref: str | None, thread_name: str | None
    ) -> DeliveryResult:
        raise NotImplementedError(f"{self.id} has no threads")

    @abstractmethod
    def _deliver(self, destination: str, content: str) -> DeliveryResult:
        """Make the provider call. Exceptions are sanitized by `send`."""

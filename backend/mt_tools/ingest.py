"""Ingest failures as admin tools (SB-1304): names the match ingest could not resolve.

The same rules as /api/admin/ingest-failures (SB-829, SB-845): one row per name,
`stale` is a hint and never a decision, and closing a row is a person's call that
is recorded, not a delete. Closing defaults to a dry run.
"""

import os
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

import structlog
from pydantic import BaseModel

from mt_ai.tools.schemas import ToolError

logger = structlog.get_logger()

# How long an open ingest failure has to go unseen before it is flagged stale.
#
# A hint, never a decision: "absent" and "fixed" are not the same thing, and a
# genuine problem that simply was not scraped this week must not auto-close. It
# exists so the run report can de-emphasise a row rather than keep crying wolf
# about it (SB-845).
DEFAULT_INGEST_FAILURE_STALE_AFTER_DAYS = 7

MAX_LIMIT = 200


def ingest_failure_stale_after_days() -> int:
    try:
        return int(os.getenv("MT_INGEST_STALE_AFTER_DAYS", DEFAULT_INGEST_FAILURE_STALE_AFTER_DAYS))
    except ValueError:
        return DEFAULT_INGEST_FAILURE_STALE_AFTER_DAYS


def last_seen_before(last_seen: str | None, cutoff: datetime) -> bool:
    """Whether a row's last_seen predates the cutoff. Unparseable reads as fresh."""
    if not last_seen:
        return False
    try:
        seen = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
    except ValueError:
        return False
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=UTC)
    return seen < cutoff


class IngestSource(Protocol):
    def open_failures(self, since: str | None = None, limit: int = 200) -> list[dict[str, Any]]: ...

    def get(self, failure_id: int) -> dict[str, Any] | None: ...

    def resolve_by_id(
        self, failure_id: int, *, resolved_by: str | None = None, note: str | None = None
    ) -> dict[str, Any] | None: ...


class IngestFailure(BaseModel):
    id: int
    kind: str | None = None
    raw_name: str
    league: str | None = None
    source: str | None = None
    match_count: int = 0
    sample: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    stale: bool = False
    resolved_at: str | None = None
    resolution_note: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any], cutoff: datetime) -> "IngestFailure":
        known = {k: row.get(k) for k in cls.model_fields if k in row and k != "stale"}
        for key in ("first_seen", "last_seen", "resolved_at"):
            if known.get(key) is not None:
                known[key] = str(known[key])
        known["match_count"] = int(row.get("match_count") or 0)
        return cls(**known, stale=last_seen_before(row.get("last_seen"), cutoff))


class IngestFailuresResult(BaseModel):
    """Open ingest failures, newest first. `failures` is null only when the read failed."""

    failures: list[IngestFailure] | None = None
    count: int = 0
    matches_dropped: int = 0
    stale_count: int = 0
    stale_after_days: int = DEFAULT_INGEST_FAILURE_STALE_AFTER_DAYS
    since: str | None = None
    error: ToolError | None = None


class ResolveIngestFailureResult(BaseModel):
    status: Literal["would_resolve", "resolved", "already_resolved", "not_found"] | None = None
    dry_run: bool = True
    failure: IngestFailure | None = None
    error: ToolError | None = None


def _cutoff(now: datetime | None) -> tuple[int, datetime]:
    days = ingest_failure_stale_after_days()
    return days, (now or datetime.now(UTC)) - timedelta(days=days)


def list_ingest_failures(
    source: IngestSource, since: str | None = None, limit: int = 50, now: datetime | None = None
) -> IngestFailuresResult:
    days, cutoff = _cutoff(now)
    limit = max(1, min(limit, MAX_LIMIT))
    try:
        rows = source.open_failures(since=since, limit=limit)
    except Exception:
        logger.exception("list_ingest_failures failed")
        return IngestFailuresResult(
            since=since,
            stale_after_days=days,
            error=ToolError(kind="unavailable", message="Ingest failures are unavailable right now."),
        )
    failures = [IngestFailure.from_row(r, cutoff) for r in rows]
    return IngestFailuresResult(
        failures=failures,
        count=len(failures),
        matches_dropped=sum(f.match_count for f in failures),
        stale_count=sum(1 for f in failures if f.stale),
        stale_after_days=days,
        since=since,
    )


def resolve_ingest_failure(
    source: IngestSource,
    failure_id: int,
    resolved_by: str,
    note: str | None = None,
    dry_run: bool = True,
    now: datetime | None = None,
) -> ResolveIngestFailureResult:
    """Close one failure by hand. Dry run (the default) says what would happen and writes nothing.

    Idempotent: closing a closed row returns it unchanged as `already_resolved`, so
    a client that retries a call (ADK's MCP client does, once) cannot re-stamp it.
    """
    _, cutoff = _cutoff(now)
    try:
        row = source.get(failure_id)
    except Exception:
        logger.exception("resolve_ingest_failure read failed", failure_id=failure_id)
        return ResolveIngestFailureResult(
            dry_run=dry_run,
            error=ToolError(kind="unavailable", message="Ingest failures are unavailable right now."),
        )
    if row is None:
        return ResolveIngestFailureResult(status="not_found", dry_run=dry_run)
    if row.get("resolved_at"):
        return ResolveIngestFailureResult(
            status="already_resolved", dry_run=dry_run, failure=IngestFailure.from_row(row, cutoff)
        )
    if dry_run:
        return ResolveIngestFailureResult(
            status="would_resolve", dry_run=True, failure=IngestFailure.from_row(row, cutoff)
        )

    updated = source.resolve_by_id(failure_id, resolved_by=resolved_by, note=note)
    if updated is None:
        return ResolveIngestFailureResult(
            dry_run=False,
            error=ToolError(kind="unavailable", message="The failure could not be closed right now."),
        )
    logger.info("ingest_failure_resolved", failure_id=failure_id, resolved_by=resolved_by)
    return ResolveIngestFailureResult(status="resolved", dry_run=False, failure=IngestFailure.from_row(updated, cutoff))

"""Names the match ingest could not resolve (SB-829).

A dropped match used to leave nothing behind but a `logger.error` in a worker
pod. Worse, the scraper's own run report could not see it: that report counts
errors from the RabbitMQ *publish*, and publishing succeeds whether or not
missing-table later accepts the match. A load where every name was unknown
reported "1432 found, 1432 submitted, 0 errors" and landed nothing.

This DAO records one row per distinct unresolved name — never one per dropped
match — so seven bad spellings read as seven problems with counts rather than
four hundred alerts.
"""

from __future__ import annotations

from typing import Any

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

DEFAULT_SOURCE = "match-scraper"


class IngestFailuresDAO(BaseDAO):
    """Read and write the ingest_failures table."""

    def record(
        self,
        kind: str,
        raw_name: str,
        *,
        league: str | None = None,
        source: str | None = None,
        sample: str | None = None,
    ) -> dict[str, Any] | None:
        """Record one occurrence of an unresolved name.

        Returns `{"id", "match_count", "should_alert"}`, or None if the write
        itself failed. `should_alert` is what keeps the alert stream readable:
        the first sighting of a name is worth a message, the four hundredth is
        worth a counter. It means "not yet announced" rather than "never seen
        before", so a name that was fixed and later regresses alerts again.

        The upsert is done in a database function because a season load runs
        many workers concurrently against the same handful of bad names, and a
        read-modify-write from here would lose counts.

        This must never be the reason a task fails: it is the diagnostic path,
        and a diagnostic that can take down ingest is worse than no diagnostic.
        """
        try:
            response = self.client.rpc(
                "record_ingest_failure",
                {
                    "p_kind": kind,
                    "p_raw_name": raw_name,
                    "p_league": league,
                    "p_source": source or DEFAULT_SOURCE,
                    "p_sample": sample,
                },
            ).execute()
            rows = response.data or []
            return rows[0] if rows else None
        except Exception:
            logger.exception("Could not record ingest failure", kind=kind, raw_name=raw_name)
            return None

    def resolve(self, kind: str, raw_name: str, *, source: str | None = None) -> int:
        """Close any open rows for a name that now resolves.

        Called on the success path, so an alias added mid-load clears its own
        alert without anyone touching the table.
        """
        try:
            response = self.client.rpc(
                "resolve_ingest_failures",
                {"p_kind": kind, "p_raw_name": raw_name, "p_source": source or DEFAULT_SOURCE},
            ).execute()
            return int(response.data or 0)
        except Exception:
            logger.exception("Could not resolve ingest failures", kind=kind, raw_name=raw_name)
            return 0

    def resolve_by_id(
        self,
        failure_id: int,
        *,
        resolved_by: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any] | None:
        """Close one row by hand, recording who and why.

        The automatic resolve only fires when the same name resolves later. A
        name fixed at the *sender* is never submitted again, so nothing
        triggers it and the row stays open forever — reported on every
        subsequent run as a problem that no longer exists (SB-845).

        Returns the row, or None if there is no such id. An already-resolved
        row is returned unchanged rather than re-stamped: the first decision is
        the one worth keeping.
        """
        try:
            existing = self.client.table("ingest_failures").select("*").eq("id", failure_id).execute()
            rows = existing.data or []
            if not rows:
                return None
            if rows[0].get("resolved_at"):
                return rows[0]

            updated = (
                self.client.table("ingest_failures")
                .update(
                    {
                        "resolved_at": "now()",
                        "resolved_by": resolved_by,
                        "resolution_note": note,
                    }
                )
                .eq("id", failure_id)
                .execute()
            )
            return (updated.data or [None])[0]
        except Exception:
            logger.exception("Could not resolve ingest failure by id", failure_id=failure_id)
            return None

    def mark_notified(self, failure_ids: list[int]) -> None:
        """Stamp rows that have been alerted on, so they are not re-announced."""
        if not failure_ids:
            return
        try:
            self.client.table("ingest_failures").update({"notified_at": "now()"}).in_("id", failure_ids).execute()
        except Exception:
            logger.exception("Could not mark ingest failures notified", failure_ids=failure_ids)

    def notified_since(self, iso_timestamp: str) -> int:
        """How many rows have been alerted on since a point in time.

        Backs the per-window alert cap. A brand-new season can arrive with
        dozens of unknown names, and a message per name would be its own kind
        of unreadable.
        """
        try:
            response = (
                self.client.table("ingest_failures")
                .select("id", count="exact")
                .gte("notified_at", iso_timestamp)
                .execute()
            )
            return response.count or 0
        except Exception:
            logger.exception("Could not count notified ingest failures")
            return 0

    def open_failures(self, since: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        """Unresolved rows, newest first.

        `since` filters on last_seen, which is what a scraper run wants: the
        names that cost it matches during the run it just finished, not every
        name that has ever been wrong.
        """
        try:
            query = self.client.table("ingest_failures").select("*").is_("resolved_at", "null")
            if since:
                query = query.gte("last_seen", since)
            response = query.order("last_seen", desc=True).limit(limit).execute()
            return response.data or []
        except Exception:
            logger.exception("Could not read ingest failures")
            return []

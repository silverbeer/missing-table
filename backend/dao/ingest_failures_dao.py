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
from postgrest.exceptions import APIError

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

DEFAULT_SOURCE = "match-scraper"

# PostgREST's "could not find the function in the schema cache": the
# resolve-by-league migration has not reached this database yet (SB-1748).
_FUNCTION_NOT_FOUND = "PGRST202"

# Kinds that record a disagreement between the feed and a person rather than a
# name that could not be resolved (SB-1787). The match was not dropped — it
# landed, or the row it would have changed was left alone — so these rows are
# not counted as matches lost.
SCORE_LOCKED = "score_locked"
SCRAPED_OVERRODE_MANUAL = "scraped_overrode_manual"
CONFLICT_KINDS = frozenset({SCORE_LOCKED, SCRAPED_OVERRODE_MANUAL})
# The source a conflict row is recorded under, whoever sent the message: one
# disagreement about one match is one row.
CONFLICT_SOURCE = "mt-worker"


class IngestFailuresDAO(BaseDAO):
    """Read and write the ingest_failures table."""

    # Said once per worker, not once per team per match: until the migration
    # is applied every tournament message would repeat it twice.
    _missing_resolve_by_league_logged = False

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

    def resolved_with_sample(
        self,
        kind: str,
        raw_name: str,
        sample: str,
        *,
        league: str | None = None,
        source: str | None = None,
    ) -> bool:
        """Whether this row is closed and last recorded exactly this sample (SB-1787).

        A conflict row (CONFLICT_KINDS) a person has closed should stay closed
        while the feed keeps saying the same thing; record() would reopen it.
        The row is found by the same identity record() upserts on.

        False when there is no such row, it is open, or the read fails — the
        caller then records, and a duplicate finding beats a lost one.
        """
        try:
            query = (
                self.client.table("ingest_failures")
                .select("sample, resolved_at")
                .eq("kind", kind)
                .ilike("raw_name", raw_name)
                .eq("source", source or DEFAULT_SOURCE)
            )
            query = query.is_("league", "null") if league is None else query.eq("league", league)
            rows = query.limit(1).execute().data or []
        except Exception:
            logger.exception("Could not read ingest failure", kind=kind, raw_name=raw_name)
            return False
        return bool(rows) and rows[0].get("resolved_at") is not None and rows[0].get("sample") == sample

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

    def resolve_in_league(
        self, kind: str, raw_name: str, *, league: str | None, source: str | None = None
    ) -> int | None:
        """Close the open row for a name that now resolves in one league (SB-1748).

        A tournament message resolves a name per side, and each side has its
        own row. `resolve` ignores the league, so a Homegrown success would
        close the Academy row for the same name; the next Academy failure
        reopens it with notified_at cleared, and the name alerts again on
        every flap. `league` is matched as the feed spelled it, and None
        matches only rows recorded with none.

        Returns None when the database does not have the function yet. The row
        is then left open — the league-blind `resolve` is not a fallback,
        because closing the wrong side's row is the fault this exists to end —
        and the caller should ask again rather than remember the answer.
        """
        try:
            response = self.client.rpc(
                "resolve_ingest_failures_by_league",
                {
                    "p_kind": kind,
                    "p_raw_name": raw_name,
                    "p_league": league,
                    "p_source": source or DEFAULT_SOURCE,
                },
            ).execute()
            return int(response.data or 0)
        except APIError as exc:
            if exc.code == _FUNCTION_NOT_FOUND:
                if not self._missing_resolve_by_league_logged:
                    self._missing_resolve_by_league_logged = True
                    logger.warning(
                        "resolve_ingest_failures_by_league is not installed — leaving failure rows open",
                        kind=kind,
                        raw_name=raw_name,
                        league=league,
                    )
                return None
            logger.exception("Could not resolve ingest failures", kind=kind, raw_name=raw_name, league=league)
            return 0
        except Exception:
            logger.exception("Could not resolve ingest failures", kind=kind, raw_name=raw_name, league=league)
            return 0

    def get(self, failure_id: int) -> dict[str, Any] | None:
        """One row by id, open or resolved; None if there is no such id.

        Raises on a database error: the caller (an admin preview, SB-1304) must be
        able to tell "no such row" from "could not look".
        """
        response = self.client.table("ingest_failures").select("*").eq("id", failure_id).execute()
        rows = response.data or []
        return rows[0] if rows else None

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

    def open_failures(
        self,
        since: str | None = None,
        limit: int = 200,
        *,
        kinds: list[str] | None = None,
        include_conflicts: bool = False,
    ) -> list[dict[str, Any]]:
        """Unresolved rows, newest first.

        `since` filters on last_seen, which is what a scraper run wants: the
        names that cost it matches during the run it just finished, not every
        name that has ever been wrong.

        Conflict rows (CONFLICT_KINDS, SB-1787) are left out unless asked for:
        they are not dropped matches, and match-scraper sums `match_count` over
        this list as "rejected by MT". `kinds` returns only those kinds,
        conflict kinds included; `include_conflicts` returns every kind.
        """
        try:
            query = self.client.table("ingest_failures").select("*").is_("resolved_at", "null")
            if since:
                query = query.gte("last_seen", since)
            if kinds:
                query = query.in_("kind", list(kinds))
            elif not include_conflicts:
                query = query.not_.in_("kind", sorted(CONFLICT_KINDS))
            response = query.order("last_seen", desc=True).limit(limit).execute()
            return response.data or []
        except Exception:
            logger.exception("Could not read ingest failures")
            return []

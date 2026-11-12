"""Match of the Week — one editorial pick per week for each slot (SB-1010, SB-1638).

A slot is (pool, age group): the main pool (Homegrown Northeast League + Flex
Empire/Turnpike/New England) runs U15-U19, the Pro Player Pathway U16-U19. SB-1010
began with one global pick a week; SB-1638 made it one per age group in each pool.

The "only one" rule is a UNIQUE constraint on (week_start, pool, age_group_id), not
a convention this module remembers to honour — two admin tabs would be enough to
break the convention version. Re-picking a slot is an upsert on that key, and past
weeks stay as rows, so the archive comes free.

Match payloads are not built here. `MatchDAO.get_match_by_id` already returns
the flattened shape the frontend knows, club colours included; duplicating that
select would be one more place to forget a field.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

TABLE = "match_of_the_week"
SLOT_CONFLICT = "week_start,pool,age_group_id"

MAIN_POOL = "main"
PATHWAY_POOL = "pathway"
POOLS = (MAIN_POOL, PATHWAY_POOL)

# `reasons` omitted from a write (SB-1552). Distinct from None, which clears
# them: the hero's blurb editor re-posts the pick without reasons, and that
# must not wipe a "Why" list the agent or an admin wrote.
KEEP = object()


def week_start_for(match_date: str | date) -> str:
    """The Monday of the week a date falls in, as YYYY-MM-DD.

    This is the bucket the uniqueness constraint is keyed on, so every caller
    must derive it the same way — hence one function rather than an inline
    timedelta in each of them.
    """
    if isinstance(match_date, str):
        match_date = datetime.strptime(match_date[:10], "%Y-%m-%d").date()
    return (match_date - timedelta(days=match_date.weekday())).isoformat()


def pool_for_match(match: dict[str, Any]) -> str:
    """The pool a match's pick belongs to: the Pro Player Pathway, or the main pool.

    Keyed on the division name, as the SB-1638 migration's backfill is, so a pick
    made before and after the migration lands in the same slot.
    """
    division = str(match.get("division_name") or "")
    return PATHWAY_POOL if "pro player pathway" in division.lower() else MAIN_POOL


class MotwDAO(BaseDAO):
    """Read and write the match_of_the_week table."""

    def __init__(self, connection_holder):
        super().__init__(connection_holder)
        self._match_dao = None

    @property
    def match_dao(self):
        """MatchDAO over the same connection, built on first use.

        Imported inside the property because match_dao imports base_dao at
        module level; doing it at the top here closes the circle.
        """
        if self._match_dao is None:
            from dao.match_dao import MatchDAO

            self._match_dao = MatchDAO(self.connection_holder)
        return self._match_dao

    def _query(self, week_start: str, pool: str | None, age_group_id: int | None):
        query = self.client.table(TABLE).select("*").eq("week_start", week_start)
        if pool is not None:
            query = query.eq("pool", pool)
        if age_group_id is not None:
            query = query.eq("age_group_id", age_group_id)
        return query

    def get_for_week(
        self,
        week_start: str,
        *,
        pool: str | None = None,
        age_group_id: int | None = None,
        include_test: bool = False,
    ) -> dict[str, Any] | None:
        """The pick for one week's slot, with its match, or None when nobody picked.

        With no slot named, the week's first pick (main pool first, then by age
        group): what an app released before SB-1638 shows as its one hero.

        None is the ordinary answer, not a failure: most slots start with no
        pick, and every caller has to render that state anyway (CLAUDE.md).
        """
        try:
            response = (
                self._query(week_start, pool, age_group_id).order("pool").order("age_group_id").limit(1).execute()
            )
            rows = response.data or []
            return self._shape(rows[0], include_test) if rows else None
        except Exception:
            logger.exception("Could not read match of the week", week_start=week_start)
            return None

    def list_for_week(self, week_start: str, *, include_test: bool = False) -> list[dict[str, Any]]:
        """Every slot's pick for a week, main pool first then by age group. [] when none."""
        try:
            response = self._query(week_start, None, None).order("pool").order("age_group_id").execute()
            picks = [self._shape(row, include_test) for row in response.data or []]
            return [p for p in picks if p is not None]
        except Exception:
            logger.exception("Could not read the week's matches of the week", week_start=week_start)
            return []

    def _shape(self, row: dict[str, Any], include_test: bool) -> dict[str, Any] | None:
        week_start = row["week_start"]
        # Which pick in the slot's series this is. Counting picks rather than
        # calendar weeks is the only number that means anything here: the
        # season row starts 2026-08-01, the first stray fixture is two weeks
        # later, and the first real matchday is a month after that — so any
        # date-derived "week 6" is arithmetic nobody recognises. The first
        # Match of the Week in a slot is Week 1.
        ordinal = self.client.table(TABLE).select("id", count="exact").lte("week_start", week_start)
        if row.get("pool") is not None:
            ordinal = ordinal.eq("pool", row["pool"])
        if row.get("age_group_id") is not None:
            ordinal = ordinal.eq("age_group_id", row["age_group_id"])
        ordinal = ordinal.execute()
        match = self.match_dao.get_match_by_id(row["match_id"], include_test=include_test)
        if match is None:
            # The pick outlived its match's visibility — a test match seen by
            # an admin and then requested by a visitor, most likely. Report no
            # pick rather than a hero with an empty middle.
            logger.info("MOTW row has no visible match", week_start=week_start, match_id=row["match_id"])
            return None

        return {
            "week_start": week_start,
            "pool": row.get("pool") or MAIN_POOL,
            "age_group_id": row.get("age_group_id") or match.get("age_group_id"),
            "age_group": match.get("age_group_name"),
            "pick_number": ordinal.count or 1,
            "blurb": row.get("blurb"),
            # null = never provided, [] = provided and empty (SB-1552).
            "reasons": row.get("reasons"),
            "selected_by": row.get("selected_by"),
            "selected_by_service": row.get("selected_by_service"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "match": match,
        }

    def set_for_match(
        self,
        match_id: int,
        *,
        blurb: str | None = None,
        reasons: list[dict[str, Any]] | None | object = KEEP,
        selected_by: str | None = None,
        selected_by_service: str | None = None,
    ) -> dict[str, Any] | None:
        """Pick a match, replacing whatever held its slot.

        The slot comes from the match: its week (from its own date, not "now",
        so picking next week's fixture ahead of time fills next week's slot),
        its age group, and its pool. Picking a U16 match never touches the U15
        pick.

        `selected_by` is the picking user's id; `selected_by_service` names the
        service account instead when one picked (SB-1553). Every write sets both,
        so an admin re-pick clears the agent's name and vice versa.

        `reasons` left as KEEP preserves the slot's existing reasons when the
        same match is re-picked (a blurb edit), and clears them when a
        different match takes the slot — another match's reasons are wrong
        for this one.

        Returns None when the match does not exist — the caller turns that into
        a 404, which is correct here: an unknown match id really is a bad
        request, unlike a slot with no pick.
        """
        match = self.match_dao.get_match_by_id(match_id, include_test=True)
        if match is None:
            return None

        week_start = week_start_for(match["match_date"])
        pool = pool_for_match(match)
        age_group_id = match.get("age_group_id")
        payload = {
            "match_id": match_id,
            "week_start": week_start,
            "pool": pool,
            "age_group_id": age_group_id,
            "blurb": blurb,
            "selected_by": selected_by,
            "selected_by_service": selected_by_service,
            "updated_at": "now()",
        }
        if reasons is KEEP:
            if not self._is_current_pick(week_start, pool, age_group_id, match_id):
                payload["reasons"] = None
        else:
            payload["reasons"] = reasons

        try:
            self.client.table(TABLE).upsert(payload, on_conflict=SLOT_CONFLICT).execute()
        except Exception:
            logger.exception("Could not set match of the week", match_id=match_id, week_start=week_start)
            return None

        return self.get_for_week(week_start, pool=pool, age_group_id=age_group_id, include_test=True)

    def _is_current_pick(self, week_start: str, pool: str, age_group_id: int | None, match_id: int) -> bool:
        """Whether `match_id` already holds the slot.

        On a failed read, answer False: the write then clears reasons, which
        loses a list someone can rewrite, rather than attaching one match's
        reasons to another.
        """
        try:
            query = self.client.table(TABLE).select("match_id").eq("week_start", week_start).eq("pool", pool)
            if age_group_id is not None:
                query = query.eq("age_group_id", age_group_id)
            rows = query.limit(1).execute().data or []
            return bool(rows) and rows[0].get("match_id") == match_id
        except Exception:
            logger.exception("Could not read current match of the week", week_start=week_start)
            return False

    def clear_week(self, week_start: str, *, pool: str | None = None, age_group_id: int | None = None) -> bool:
        """Unpick a slot, or every slot of the week when none is named.

        True when a row went away, False when none was there.
        """
        try:
            query = self.client.table(TABLE).delete().eq("week_start", week_start)
            if pool is not None:
                query = query.eq("pool", pool)
            if age_group_id is not None:
                query = query.eq("age_group_id", age_group_id)
            return bool(query.execute().data)
        except Exception:
            logger.exception("Could not clear match of the week", week_start=week_start)
            return False

    def week_starts_with_picks(self, match_ids: list[int]) -> dict[int, str]:
        """Which of these matches are the pick for their week, as {match_id: week_start}.

        Lets the Matches table badge its rows from one query instead of one per
        row. Empty input short-circuits: `in_()` with an empty list is an easy
        way to ask a database for everything by accident.
        """
        if not match_ids:
            return {}
        try:
            response = self.client.table(TABLE).select("match_id, week_start").in_("match_id", match_ids).execute()
            return {row["match_id"]: row["week_start"] for row in (response.data or [])}
        except Exception:
            logger.exception("Could not read match of the week flags")
            return {}

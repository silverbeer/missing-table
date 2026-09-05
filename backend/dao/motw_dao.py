"""Match of the Week — one editorial pick per calendar week (SB-1010).

Deliberately global: one pick across every age group and division, not one per
age group. Six picks a week is a label; one is an event, and the whole point of
the feature is that a match gets singled out.

The "only one" rule is a UNIQUE constraint on week_start, not a convention this
module remembers to honour — two admin tabs would be enough to break the
convention version. Re-picking inside a week is an upsert on that key, and past
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


def week_start_for(match_date: str | date) -> str:
    """The Monday of the week a date falls in, as YYYY-MM-DD.

    This is the bucket the uniqueness constraint is keyed on, so every caller
    must derive it the same way — hence one function rather than an inline
    timedelta in each of them.
    """
    if isinstance(match_date, str):
        match_date = datetime.strptime(match_date[:10], "%Y-%m-%d").date()
    return (match_date - timedelta(days=match_date.weekday())).isoformat()


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

    def get_for_week(self, week_start: str, *, include_test: bool = False) -> dict[str, Any] | None:
        """The pick for one week, with its match, or None when nobody picked.

        None is the ordinary answer, not a failure: most weeks start with no
        pick, and every caller has to render that state anyway (CLAUDE.md).
        """
        try:
            response = self.client.table(TABLE).select("*").eq("week_start", week_start).limit(1).execute()
            rows = response.data or []
            if not rows:
                return None

            row = rows[0]
            match = self.match_dao.get_match_by_id(row["match_id"], include_test=include_test)
            if match is None:
                # The pick outlived its match's visibility — a test match seen
                # by an admin and then requested by a visitor, most likely.
                # Report no pick rather than a hero with an empty middle.
                logger.info("MOTW row has no visible match", week_start=week_start, match_id=row["match_id"])
                return None

            return {
                "week_start": row["week_start"],
                "blurb": row.get("blurb"),
                "selected_by": row.get("selected_by"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "match": match,
            }
        except Exception:
            logger.exception("Could not read match of the week", week_start=week_start)
            return None

    def set_for_match(
        self,
        match_id: int,
        *,
        blurb: str | None = None,
        selected_by: str | None = None,
    ) -> dict[str, Any] | None:
        """Pick a match, replacing whatever held its week.

        The week is derived from the match's own date rather than from "now",
        so picking next week's fixture ahead of time lands in next week's slot
        instead of overwriting this week's pick.

        Returns None when the match does not exist — the caller turns that into
        a 404, which is correct here: an unknown match id really is a bad
        request, unlike a week with no pick.
        """
        match = self.match_dao.get_match_by_id(match_id, include_test=True)
        if match is None:
            return None

        week_start = week_start_for(match["match_date"])
        payload = {
            "match_id": match_id,
            "week_start": week_start,
            "blurb": blurb,
            "selected_by": selected_by,
            "updated_at": "now()",
        }

        try:
            self.client.table(TABLE).upsert(payload, on_conflict="week_start").execute()
        except Exception:
            logger.exception("Could not set match of the week", match_id=match_id, week_start=week_start)
            return None

        return self.get_for_week(week_start, include_test=True)

    def clear_week(self, week_start: str) -> bool:
        """Unpick a week. True when a row went away, False when none was there."""
        try:
            response = self.client.table(TABLE).delete().eq("week_start", week_start).execute()
            return bool(response.data)
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

"""Tournament Match of the Day — one editorial pick per tournament per day (SB-1559).

The tournament sibling of MotwDAO. A multi-day event like MLS NEXT Fest has
dozens of matches a day, so the unit is (tournament, day) rather than the
calendar week.

"Only one per day" is the UNIQUE(tournament_id, match_date) constraint, not
something this module remembers to check. Re-picking a day is an upsert on
that key; past days stay as rows.

Match payloads come from `MatchDAO.get_match_by_id`, as in MotwDAO, so the
banner gets the same flattened shape (club colours, tournament name) the rest
of the frontend already knows.
"""

from __future__ import annotations

from typing import Any

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

TABLE = "tournament_match_of_the_day"


class MotdPickError(ValueError):
    """The match cannot be the pick for that tournament day.

    A ValueError so the endpoint turns it into a 400: the caller asked for
    something that cannot be true (a match from another tournament, or on
    another day), which is a bad request rather than a missing resource.
    """


def check_pick(match: dict[str, Any], tournament_id: int, match_date: str | None = None) -> str:
    """Validate that `match` can be featured for `tournament_id`; return its date.

    Pure so the rule is testable without a database. `match_date`, when the
    caller gives one, must agree with the match's own date — picking for a day
    and passing a match from a different day is the mistake this catches.
    """
    if match.get("tournament_id") != tournament_id:
        raise MotdPickError(f"Match {match.get('id')} is not in tournament {tournament_id}")
    own_date = str(match.get("match_date") or "")[:10]
    if not own_date:
        raise MotdPickError(f"Match {match.get('id')} has no date")
    if match_date and match_date[:10] != own_date:
        raise MotdPickError(f"Match {match.get('id')} is on {own_date}, not {match_date[:10]}")
    return own_date


class MotdDAO(BaseDAO):
    """Read and write the tournament_match_of_the_day table."""

    def __init__(self, connection_holder):
        super().__init__(connection_holder)
        self._match_dao = None

    @property
    def match_dao(self):
        """MatchDAO over the same connection, built on first use (see MotwDAO)."""
        if self._match_dao is None:
            from dao.match_dao import MatchDAO

            self._match_dao = MatchDAO(self.connection_holder)
        return self._match_dao

    def _hydrate(self, row: dict[str, Any], *, include_test: bool) -> dict[str, Any] | None:
        match = self.match_dao.get_match_by_id(row["match_id"], include_test=include_test)
        if match is None:
            # The pick outlived its match's visibility (a test match picked by
            # an admin, read by a visitor). Report no pick rather than a banner
            # with nothing in it.
            logger.info("MOTD row has no visible match", tournament_id=row["tournament_id"], match_id=row["match_id"])
            return None
        return {
            "tournament_id": row["tournament_id"],
            "match_date": row["match_date"],
            "blurb": row.get("blurb"),
            "reasons": row.get("reasons"),
            "selected_by": row.get("selected_by"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "match": match,
        }

    def get_for_day(self, tournament_id: int, match_date: str, *, include_test: bool = False) -> dict[str, Any] | None:
        """The pick for one tournament day, or None when nobody picked.

        None is the ordinary answer — most days start without a pick.
        """
        try:
            response = (
                self.client.table(TABLE)
                .select("*")
                .eq("tournament_id", tournament_id)
                .eq("match_date", match_date)
                .limit(1)
                .execute()
            )
            rows = response.data or []
            return self._hydrate(rows[0], include_test=include_test) if rows else None
        except Exception:
            logger.exception("Could not read match of the day", tournament_id=tournament_id, match_date=match_date)
            return None

    def list_for_tournament(self, tournament_id: int, *, include_test: bool = False) -> list[dict[str, Any]]:
        """Every visible pick in a tournament, oldest day first.

        Lets the tournament page choose "today" in the viewer's own timezone
        instead of the server guessing which day it is in Mesa.
        """
        try:
            response = (
                self.client.table(TABLE).select("*").eq("tournament_id", tournament_id).order("match_date").execute()
            )
        except Exception:
            logger.exception("Could not list matches of the day", tournament_id=tournament_id)
            return []
        picks = (self._hydrate(row, include_test=include_test) for row in (response.data or []))
        return [p for p in picks if p is not None]

    def set_for_match(
        self,
        tournament_id: int,
        match_id: int,
        *,
        match_date: str | None = None,
        blurb: str | None = None,
        reasons: list[dict[str, Any]] | None = None,
        selected_by: str | None = None,
    ) -> dict[str, Any] | None:
        """Pick a match for its tournament day, replacing that day's pick.

        Returns None when the match does not exist (the endpoint's 404).
        Raises MotdPickError when it exists but cannot be this day's pick.
        """
        match = self.match_dao.get_match_by_id(match_id, include_test=True)
        if match is None:
            return None

        day = check_pick(match, tournament_id, match_date)
        payload = {
            "tournament_id": tournament_id,
            "match_date": day,
            "match_id": match_id,
            "blurb": blurb,
            "reasons": reasons,
            "selected_by": selected_by,
            "updated_at": "now()",
        }
        try:
            self.client.table(TABLE).upsert(payload, on_conflict="tournament_id,match_date").execute()
        except Exception:
            logger.exception("Could not set match of the day", tournament_id=tournament_id, match_id=match_id)
            return None

        return self.get_for_day(tournament_id, day, include_test=True)

    def clear_day(self, tournament_id: int, match_date: str) -> bool:
        """Unpick a day. True when a row went away, False when none was there."""
        try:
            response = (
                self.client.table(TABLE)
                .delete()
                .eq("tournament_id", tournament_id)
                .eq("match_date", match_date)
                .execute()
            )
            return bool(response.data)
        except Exception:
            logger.exception("Could not clear match of the day", tournament_id=tournament_id, match_date=match_date)
            return False

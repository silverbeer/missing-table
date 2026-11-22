"""Tournament Match of the Day — one editorial pick per tournament, day and age group (SB-1559, SB-1750).

The tournament sibling of MotwDAO. A multi-day event like MLS NEXT Fest has
dozens of matches a day across six age groups, so the unit is (tournament,
day, age group) rather than the calendar week. A single-age tournament has
one slot a day, as it did before SB-1750.

"Only one per slot" is the UNIQUE(tournament_id, match_date, age_group_id)
constraint, not something this module remembers to check. Re-picking a slot
is an upsert on that key; past days stay as rows.

Reads never name the age_group_id column: a row without one takes its match's
age group, and the age filter runs here rather than in the query. That keeps
the public banner working on either side of the SB-1750 migration.

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
SLOT_CONFLICT = "tournament_id,match_date,age_group_id"


class MotdPickError(ValueError):
    """The match cannot be the pick for that tournament day.

    A ValueError so the endpoint turns it into a 400: the caller asked for
    something that cannot be true (a match from another tournament, on
    another day, in another age group, or with no age group at all), which is
    a bad request rather than a missing resource.
    """


class MotdWriteError(RuntimeError):
    """The pick was valid but could not be stored, or could not be cleared.

    Kept apart from "no such match" (None) and from "nothing was picked" (0) so
    the endpoint answers 5xx instead of a 404 that blames the match id or a 200
    that says the pick is gone. The cause is logged here, not carried in the
    message.
    """


def check_pick(
    match: dict[str, Any],
    tournament_id: int,
    match_date: str | None = None,
    age_group_id: int | None = None,
) -> str:
    """Validate that `match` can be featured for `tournament_id`; return its date.

    Pure so the rule is testable without a database. `match_date` and
    `age_group_id`, when the caller gives them, must agree with the match's
    own — picking for a day or an age group and passing a match from a
    different one is the mistake this catches.
    """
    if match.get("tournament_id") != tournament_id:
        raise MotdPickError(f"Match {match.get('id')} is not in tournament {tournament_id}")
    own_date = str(match.get("match_date") or "")[:10]
    if not own_date:
        raise MotdPickError(f"Match {match.get('id')} has no date")
    if match_date and match_date[:10] != own_date:
        raise MotdPickError(f"Match {match.get('id')} is on {own_date}, not {match_date[:10]}")
    if match.get("age_group_id") is None:
        # The age group is part of the slot key; production allows a match without one.
        raise MotdPickError(f"Match {match.get('id')} has no age group, so it cannot be Match of the Day")
    if age_group_id is not None and match.get("age_group_id") != age_group_id:
        raise MotdPickError(f"Match {match.get('id')} is in age group {match.get('age_group_id')}, not {age_group_id}")
    return own_date


def _slot_order(pick: dict[str, Any]) -> tuple[str, int]:
    return (str(pick["match_date"]), pick.get("age_group_id") or 0)


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
            # A row written before SB-1750 has no age group of its own.
            "age_group_id": row.get("age_group_id") or match.get("age_group_id"),
            "age_group": match.get("age_group_name"),
            "blurb": row.get("blurb"),
            "reasons": row.get("reasons"),
            "selected_by": row.get("selected_by"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "match": match,
        }

    def list_for_day(self, tournament_id: int, match_date: str, *, include_test: bool = False) -> list[dict[str, Any]]:
        """Every visible pick for one tournament day, by age group.

        Empty is the ordinary answer — most days start without a pick.
        """
        try:
            response = (
                self.client.table(TABLE)
                .select("*")
                .eq("tournament_id", tournament_id)
                .eq("match_date", match_date)
                .execute()
            )
            picks = (self._hydrate(row, include_test=include_test) for row in (response.data or []))
            return sorted((p for p in picks if p is not None), key=_slot_order)
        except Exception:
            logger.exception("Could not read match of the day", tournament_id=tournament_id, match_date=match_date)
            return []

    def get_for_day(
        self,
        tournament_id: int,
        match_date: str,
        *,
        age_group_id: int | None = None,
        include_test: bool = False,
    ) -> dict[str, Any] | None:
        """The pick for one slot, or None when nobody picked.

        With no age group, the day's first pick by age group: the only one a
        single-age tournament has. With one, that age group's pick and never
        another's.
        """
        picks = self.list_for_day(tournament_id, match_date, include_test=include_test)
        if age_group_id is not None:
            picks = [p for p in picks if p["age_group_id"] == age_group_id]
        return picks[0] if picks else None

    def list_for_tournament(self, tournament_id: int, *, include_test: bool = False) -> list[dict[str, Any]]:
        """Every visible pick in a tournament, oldest day first, then by age group.

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
        return sorted((p for p in picks if p is not None), key=_slot_order)

    def set_for_match(
        self,
        tournament_id: int,
        match_id: int,
        *,
        match_date: str | None = None,
        age_group_id: int | None = None,
        blurb: str | None = None,
        reasons: list[dict[str, Any]] | None = None,
        selected_by: str | None = None,
    ) -> dict[str, Any] | None:
        """Pick a match for its tournament day and age group, replacing that slot's pick.

        The slot comes from the match: picking a U16 match never touches the
        U15 pick. `match_date` and `age_group_id` are guards only.

        Returns None when the match does not exist (the endpoint's 404).
        Raises MotdPickError when it exists but cannot be this slot's pick,
        and MotdWriteError when the pick could not be stored.
        """
        match = self.match_dao.get_match_by_id(match_id, include_test=True)
        if match is None:
            return None

        day = check_pick(match, tournament_id, match_date, age_group_id)
        slot_age = match.get("age_group_id")
        payload = {
            "tournament_id": tournament_id,
            "match_date": day,
            "age_group_id": slot_age,
            "match_id": match_id,
            "blurb": blurb,
            "reasons": reasons,
            "selected_by": selected_by,
            "updated_at": "now()",
        }
        try:
            self.client.table(TABLE).upsert(payload, on_conflict=SLOT_CONFLICT).execute()
        except Exception as e:
            logger.exception("Could not set match of the day", tournament_id=tournament_id, match_id=match_id)
            raise MotdWriteError("Could not store match of the day") from e

        pick = self.get_for_day(tournament_id, day, age_group_id=slot_age, include_test=True)
        if pick is None:
            logger.error("Match of the day not readable after write", tournament_id=tournament_id, match_id=match_id)
            raise MotdWriteError("Could not read back match of the day")
        return pick

    def clear_day(self, tournament_id: int, match_date: str, *, age_group_id: int | None = None) -> int:
        """Unpick a slot, or every slot of the day when no age group is named.

        The number of picks that went away; 0 when none was there. Raises
        MotdWriteError when the delete itself failed, so a pick that is still
        there is never reported as cleared.
        """
        try:
            query = self.client.table(TABLE).delete().eq("tournament_id", tournament_id).eq("match_date", match_date)
            if age_group_id is not None:
                query = query.eq("age_group_id", age_group_id)
            return len(query.execute().data or [])
        except Exception as e:
            logger.exception(
                "Could not clear match of the day",
                tournament_id=tournament_id,
                match_date=match_date,
                age_group_id=age_group_id,
            )
            raise MotdWriteError("Could not clear match of the day") from e

"""
Tournament match paging and filter facets (SB-1749).

The Tournaments page pages and filters a big event server-side: MLS NEXT Fest
is ~2,400 matches, and one response is capped at 1,000 rows. This module is
the logic behind ``GET /api/tournaments/{id}/matches`` and ``.../filters`` that
needs no database: reading query parameters, and shaping facet rows.

Two rules run through it:

- **A filter that cannot match is not "no filter".** ``age_group_id=abc`` or
  ``round=nonsense`` yields zero matches, never the unfiltered list — the
  caller asked for something specific and would otherwise be shown everything.
- **Unknown is not zero.** When the facet counts cannot be computed the lists
  say so with ``None``; ``[]`` and ``0`` are measurements.

Pure functions only — no DAO or database imports.
"""

import re
from dataclasses import dataclass
from datetime import date

from dao.tournament_groups import split_group

DEFAULT_LIMIT = 200
MAX_LIMIT = 500
# Far past any real tournament; keeps a hostile offset out of the query.
MAX_OFFSET = 1_000_000
# age_groups.id is a Postgres integer.
_MAX_ID = 2_147_483_647

FACET_AGE_GROUP = "age_group"
FACET_GROUP = "group"


def clamp_limit(limit: int | None) -> int:
    """Page size: the default when absent, otherwise held to 1..MAX_LIMIT."""
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(int(limit), MAX_LIMIT))


def clamp_offset(offset: int | None) -> int:
    """Rows to skip: never negative, never past MAX_OFFSET."""
    if offset is None:
        return 0
    return max(0, min(int(offset), MAX_OFFSET))


def _blank(value: str | None) -> bool:
    return value is None or not str(value).strip()


@dataclass(frozen=True)
class MatchFilters:
    """The filters a request asked for, after validation.

    A field is None when that filter was not given. ``satisfiable`` is False
    when one was given but can never match (not an id, not a round key): the
    answer is then zero matches without asking the database.
    """

    age_group_id: int | None = None
    group: str | None = None
    round: str | None = None
    satisfiable: bool = True


def parse_age_group_id(value: str | int | None) -> tuple[int | None, bool]:
    """Read an ``age_group_id`` query value as ``(id, valid)``.

    Absent or blank is ``(None, True)`` — no filter. Anything that is not a
    positive Postgres integer is ``(None, False)``.
    """
    if _blank(None if value is None else str(value)):
        return None, True
    text = str(value).strip()
    if not text.isascii() or not text.isdigit():
        return None, False
    number = int(text)
    if number < 1 or number > _MAX_ID:
        return None, False
    return number, True


def resolve_match_filters(
    age_group_id: str | int | None,
    group: str | None,
    round: str | None,
    valid_rounds: set[str] | frozenset[str],
) -> MatchFilters:
    """Decide which filters apply to a matches request.

    ``group`` is compared with the stored ``tournament_group`` exactly, so it
    is passed through untouched; only a blank value counts as not given.
    """
    age_id, age_ok = parse_age_group_id(age_group_id)
    round_key = None if _blank(round) else str(round).strip()
    round_ok = round_key is None or round_key in valid_rounds
    return MatchFilters(
        age_group_id=age_id,
        group=None if _blank(group) else group,
        round=round_key if round_ok else None,
        satisfiable=age_ok and round_ok,
    )


def parse_on_date(value: str | None) -> str | None:
    """An ISO ``YYYY-MM-DD`` day, or None when absent or not a real date."""
    if _blank(value):
        return None
    text = str(value).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _natural_key(text: str | None) -> list:
    """Sort key that orders "U9" before "U13" and "Group 2" before "Group 10"."""
    parts = re.split(r"(\d+)", text or "")
    return [(0, int(p), "") if p.isdigit() else (1, 0, p.casefold()) for p in parts if p != ""]


def build_age_group_options(rows: list[dict], *, on_date: str | None = None) -> list[dict]:
    """Age-group facet rows -> ``[{id, name, matches, matches_on_date}]``.

    ``matches_on_date`` is a count only when a day was asked for; without one
    it is None — nobody counted, which is not the same as none that day.
    """
    options = []
    for row in rows:
        if row.get("facet") != FACET_AGE_GROUP or row.get("age_group_id") is None:
            continue
        options.append(
            {
                "id": row["age_group_id"],
                "name": row.get("age_group_name"),
                "matches": int(row.get("matches") or 0),
                "matches_on_date": int(row.get("matches_on_date") or 0) if on_date else None,
            }
        )
    options.sort(key=lambda o: (_natural_key(o["name"]), o["id"]))
    return options


def build_group_options(rows: list[dict]) -> list[dict]:
    """Group facet rows -> ``[{key, division, label, matches}]``.

    ``key`` is the stored ``tournament_group`` and is what the matches endpoint
    filters on; division and label are its two halves for display. Ordered by
    division, then label, so ``AD · A`` and ``HD · A`` sit in their own runs.
    """
    options = []
    for row in rows:
        key = row.get("tournament_group")
        if row.get("facet") != FACET_GROUP or _blank(key):
            continue
        parts = split_group(key)
        options.append(
            {
                "key": key,
                "division": parts["division"],
                "label": parts["label"],
                "matches": int(row.get("matches") or 0),
            }
        )
    options.sort(
        key=lambda o: (
            o["division"] is None,
            _natural_key(o["division"]),
            _natural_key(o["label"]),
            o["key"],
        )
    )
    return options


def build_filters_payload(rows: list[dict], *, on_date: str | None = None) -> dict:
    """The filters response when the facet counts were computed."""
    return {
        "facets_available": True,
        "age_groups": build_age_group_options(rows, on_date=on_date),
        "groups": build_group_options(rows),
    }


def unavailable_filters_payload(age_groups: list[dict] | None) -> dict:
    """The filters response when the facet counts could not be computed.

    The tournament's own age groups still make an Age Group control possible,
    so they are listed — with ``matches`` None, because nothing was counted.
    ``groups`` is None: unknown, which is not "this age has no groups".
    """
    options = [
        {"id": ag["id"], "name": ag.get("name"), "matches": None, "matches_on_date": None}
        for ag in (age_groups or [])
        if ag and ag.get("id") is not None
    ]
    options.sort(key=lambda o: (_natural_key(o["name"]), o["id"]))
    return {"facets_available": False, "age_groups": options, "groups": None}


def empty_page(limit: int, offset: int) -> dict:
    """A page with nothing on it: a filter that cannot match, or no matches."""
    return {"matches": [], "total": 0, "limit": limit, "offset": offset}

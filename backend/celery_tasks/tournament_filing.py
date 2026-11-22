"""
How an ingested match is filed under a tournament (SB-1747).

A league message says where a match belongs with ``division``. A tournament
message says it with ``tournament_id`` and four optional companions::

    tournament_id           the tournaments row the match belongs to
    competition             the feed's own name, e.g. "HD Group Play"
    tournament_group        the feed's own group label, e.g. "A"
    tournament_round        a round key, e.g. "group_stage"
    tournament_round_order  position within the round

The feed's ``competition`` and ``tournament_group`` are raw. What is stored in
``matches.tournament_group`` is one namespaced string built from them by
``stored_group`` — MLS NEXT Fest runs a Homegrown and an Academy division side
by side and both have a "Group A", so the raw label alone would merge them.

Pure functions only — no DAO or database imports. ``dao.tournament_groups`` is
itself pure; the stored format is frozen there (SB-1752), so this module never
builds the string by hand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from dao.tournament_groups import GROUP_WHITESPACE, compose_group, split_group

# The match_types.name every tournament message must carry. Compared without
# case, as the match-type lookup is.
TOURNAMENT_MATCH_TYPE = "Tournament"

# Competitions that namespace a group. A competition whose first word is one
# of these belongs to that division; anything else is its own namespace.
DIVISION_TOKENS = frozenset({"HD", "AD"})

GROUP_STAGE = "group_stage"

# A round key is validated for shape, not membership: a feed that grows a new
# round should land its matches and be noticed, not lose them (the caller logs
# a key outside VALID_ROUNDS).
ROUND_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
ROUND_KEY_MAX_LENGTH = 40

# A run of whitespace inside a competition name. The same characters the
# frozen format trims from the ends of a part, so "HD  Group  Play" and
# "HD Group Play" are stored as the same bytes.
_WHITESPACE_RUN = re.compile(f"[{re.escape(GROUP_WHITESPACE)}]+")

# The matches columns a tournament filing owns, in the order they are compared.
TOURNAMENT_COLUMNS = ("tournament_id", "tournament_group", "tournament_round", "tournament_round_order")

# Message fields that mean nothing without tournament_id.
_TOURNAMENT_ONLY_FIELDS = ("competition", "tournament_group", "tournament_round", "tournament_round_order")


class TournamentFilingError(ValueError):
    """The tournament fields on a message cannot be filed as sent.

    Permanent: the same message will be just as wrong in ten minutes, so the
    task records it in ``ingest_failures`` rather than retrying.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class TournamentFiling:
    """Where a tournament message files its match.

    ``tournament_group`` is the *stored* value (see ``stored_group``), not the
    raw label the feed sent. ``competition`` is kept as sent, for log lines.
    """

    tournament_id: int
    tournament_group: str | None = None
    tournament_round: str | None = None
    tournament_round_order: int | None = None
    competition: str | None = None

    def columns(self) -> dict[str, Any]:
        """The filing as matches columns, nulls included."""
        return {column: getattr(self, column) for column in TOURNAMENT_COLUMNS}


def _blank_to_none(value: Any) -> Any:
    """Empty and whitespace-only strings are absent; everything else is itself."""
    if isinstance(value, str):
        return value.strip(GROUP_WHITESPACE) or None
    return value


def _collapse_whitespace(value: str | None) -> str | None:
    """Trim a competition and turn each inner run of whitespace into one space.

    Letter case is left alone: only the division token is ever re-cased.
    """
    if not isinstance(value, str):
        return value
    return _WHITESPACE_RUN.sub(" ", value).strip(" ") or None


def _is_int(value: Any) -> bool:
    """A real integer. bool is an int in Python and is not one on the wire."""
    return isinstance(value, int) and not isinstance(value, bool)


def _split_division(competition: str | None) -> tuple[str | None, str | None]:
    """Split "HD Group Play" into ("HD", "Group Play").

    The division is the first whitespace-separated word, and only when it is
    exactly HD or AD (any case, stored upper-case). Otherwise there is no
    division and the competition is returned whole.
    """
    if not competition:
        return None, None
    words = competition.split(None, 1)
    head = words[0]
    rest = words[1] if len(words) > 1 else None
    if head.upper() in DIVISION_TOKENS:
        return head.upper(), _blank_to_none(rest)
    return None, competition


def stored_group(competition: str | None, group: str | None, round_key: str | None) -> str | None:
    """Build the ``matches.tournament_group`` value for a feed's raw fields.

    Group stage — the group is namespaced by its division, or by the whole
    competition when it has none::

        ("HD Group Play", "A", "group_stage")              -> "HD · A"
        ("AD Group Play", "A", "group_stage")              -> "AD · A"
        ("GA Cup Qualifier", "NEXT Pro", "group_stage")    -> "GA Cup Qualifier · NEXT Pro"
        (None, "Bracket A", "group_stage")                 -> "Bracket A"

    Any other round — the feed's group label is not a group at all there
    ("Playoffs"), so the competition is what the match is filed under::

        ("HD Showcase", <anything>, "showcase")            -> "HD · Showcase"
        ("HD Group Play", "Playoffs", "placement_final")   -> "HD · Group Play"
        ("GA Cup Qualifier", <anything>, "final")          -> "GA Cup Qualifier"
        (None, "Bracket A", "final")                       -> "Bracket A"

    Returns None — "no opinion", which never overwrites a stored group — when
    the fields the round needs are not all there. Composing from what is left
    would yield a different, shorter string ("HD" for "HD · A"), and bracket
    follows key on the stored one::

        (<anything>, <anything>, None)                     -> None
        ("HD Group Play", None, "group_stage")             -> None
        (None, None, "final")                              -> None

    Runs of whitespace inside the competition are collapsed to one space, so
    the same competition always yields the same bytes.

    Raises ValueError for a value ``compose_group`` rejects, rather than
    storing a string that would split back into different parts.
    """
    competition = _collapse_whitespace(competition)
    group = _blank_to_none(group)
    round_key = _blank_to_none(round_key)
    division, remainder = _split_division(competition)

    if round_key is None:
        return None
    if round_key == GROUP_STAGE:
        if group is None:
            return None
        return compose_group(division or competition, group)
    if division:
        return compose_group(division, remainder)
    if competition:
        return compose_group(None, competition)
    return compose_group(None, group)


def tournament_filing_errors(match_data: dict[str, Any]) -> list[str]:
    """Everything wrong with a message's tournament fields; empty when fine.

    A message with no tournament fields at all is fine — it is a league
    message, and this has nothing to say about it.
    """
    errors: list[str] = []
    tournament_id = match_data.get("tournament_id")

    if tournament_id is None:
        for field in _TOURNAMENT_ONLY_FIELDS:
            if _blank_to_none(match_data.get(field)) is not None:
                errors.append(f"{field} requires tournament_id")
        return errors

    if not _is_int(tournament_id) or tournament_id < 1:
        errors.append("tournament_id must be an integer of 1 or more")

    # The source match id is what a rescrape upserts on. Without it every
    # rescrape of a tournament would fall back to teams-and-date, and two
    # fixtures between the same teams on one day would overwrite each other.
    if _blank_to_none(match_data.get("external_match_id")) is None:
        errors.append("external_match_id is required when tournament_id is set")

    match_type = _blank_to_none(match_data.get("match_type"))
    if not isinstance(match_type, str) or match_type.lower() != TOURNAMENT_MATCH_TYPE.lower():
        errors.append(f"match_type must be '{TOURNAMENT_MATCH_TYPE}' when tournament_id is set")

    # A tournament match is filed on the tournament. Accepting a division as
    # well would land it in a league table too.
    if _blank_to_none(match_data.get("division")) is not None:
        errors.append("division must be omitted when tournament_id is set")

    for field in ("competition", "tournament_group"):
        value = match_data.get(field)
        if value is not None and not isinstance(value, str):
            errors.append(f"{field} must be a string")

    round_key = _blank_to_none(match_data.get("tournament_round"))
    if round_key is not None and (
        not isinstance(round_key, str)
        or len(round_key) > ROUND_KEY_MAX_LENGTH
        or not ROUND_KEY_PATTERN.match(round_key)
    ):
        errors.append(
            f"tournament_round must be a lowercase snake_case key of at most {ROUND_KEY_MAX_LENGTH} characters"
        )

    round_order = match_data.get("tournament_round_order")
    if round_order is not None and (not _is_int(round_order) or round_order < 0):
        errors.append("tournament_round_order must be an integer of 0 or more")

    if not errors:
        try:
            stored_group(match_data.get("competition"), match_data.get("tournament_group"), round_key)
        except ValueError as exc:
            errors.append(f"tournament group cannot be stored: {exc}")

    return errors


def read_tournament_filing(match_data: dict[str, Any]) -> TournamentFiling | None:
    """The tournament filing on a message, or None for a league message.

    Raises TournamentFilingError when the tournament fields are present but
    cannot be filed: any of them without ``tournament_id``, a wrong type or
    range, a malformed round key, a missing ``external_match_id``, or a group
    the frozen format rejects.
    """
    errors = tournament_filing_errors(match_data)
    if errors:
        raise TournamentFilingError(errors)

    if match_data.get("tournament_id") is None:
        return None

    round_key = _blank_to_none(match_data.get("tournament_round"))
    return TournamentFiling(
        tournament_id=match_data["tournament_id"],
        tournament_group=stored_group(match_data.get("competition"), match_data.get("tournament_group"), round_key),
        tournament_round=round_key,
        tournament_round_order=match_data.get("tournament_round_order"),
        competition=_blank_to_none(match_data.get("competition")),
    )


def _is_namespaced(group: Any) -> bool:
    """Whether a stored group carries a division ("HD · A", not "Bracket A")."""
    return isinstance(group, str) and split_group(group)["division"] is not None


def tournament_changes(
    existing_row: dict[str, Any], filing: TournamentFiling | None, *, fill_only: bool = False
) -> dict[str, Any]:
    """The tournament columns a rescrape should write to an existing row.

    Only values the message actually carries: a null incoming value never
    clears a stored one, so a rescrape that omits the group does not unfile a
    match from it. Identical values yield an empty dict.

    A stored namespaced group is never replaced by one without a namespace: a
    message that lost its competition composes a bare "A", and writing that
    over "HD · A" would orphan the bracket follows keyed on it.

    ``fill_only`` is for a hand-entered row being adopted: only columns that
    are null on the row are written, so a value somebody typed stays.
    """
    if filing is None:
        return {}
    changes: dict[str, Any] = {}
    for column, value in filing.columns().items():
        stored = existing_row.get(column)
        if value is None or stored == value:
            continue
        if fill_only and stored is not None:
            continue
        if column == "tournament_group" and _is_namespaced(stored) and not _is_namespaced(value):
            continue
        changes[column] = value
    return changes

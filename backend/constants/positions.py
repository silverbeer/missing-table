"""Player position taxonomy — backend mirror.

KEEP IN SYNC with frontend/src/constants/positions.js (the frontend file is
the display source of truth; tests/test_position_constants.py asserts parity
by parsing it).

A player's positions are an ORDERED list of specific codes; the first entry
is their primary position. Each code belongs to exactly one broad group.
"""

from typing import Annotated

from pydantic import AfterValidator

POSITION_GROUPS: dict[str, list[str]] = {
    "GK": ["GK"],
    "DEF": ["CB", "LB", "RB", "LWB", "RWB"],
    "MID": ["CDM", "CM", "CAM", "LM", "RM"],
    "FWD": ["LW", "RW", "ST", "CF"],
}

VALID_POSITIONS: frozenset[str] = frozenset(
    code for codes in POSITION_GROUPS.values() for code in codes
)

# Old side-specific codes that may arrive from stale clients.
LEGACY_POSITION_MAP: dict[str, str] = {
    "LCB": "CB",
    "RCB": "CB",
    "LCM": "CM",
    "RCM": "CM",
}

_POSITION_NAMES: dict[str, str] = {
    "GK": "Goalkeeper",
    "CB": "Center Back",
    "LB": "Left Back",
    "RB": "Right Back",
    "LWB": "Left Wing Back",
    "RWB": "Right Wing Back",
    "CDM": "Defensive Midfielder",
    "CM": "Central Midfielder",
    "CAM": "Attacking Midfielder",
    "LM": "Left Midfielder",
    "RM": "Right Midfielder",
    "LW": "Left Winger",
    "RW": "Right Winger",
    "ST": "Striker",
    "CF": "Center Forward",
}

# API response shape for GET /api/positions (full_name/abbreviation keys kept
# for compatibility with pre-taxonomy clients; group is new).
PLAYER_POSITIONS: list[dict[str, str]] = [
    {"full_name": _POSITION_NAMES[code], "abbreviation": code, "group": group}
    for group, codes in POSITION_GROUPS.items()
    for code in codes
]


def normalize_positions(positions: list[str] | None) -> list[str] | None:
    """Validate and normalize an ordered positions list.

    - Maps legacy codes to their canonical replacement.
    - Deduplicates while preserving order (first occurrence wins).
    - Raises ValueError on unknown codes.
    Returns None for None, [] for [].
    """
    if positions is None:
        return None
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in positions:
        code = LEGACY_POSITION_MAP.get(raw, raw)
        if code not in VALID_POSITIONS:
            raise ValueError(
                f"Invalid position code: {raw!r}. Valid codes: {sorted(VALID_POSITIONS)}"
            )
        if code not in seen:
            seen.add(code)
            normalized.append(code)
    return normalized


# Shared Pydantic field type: use `positions: Positions = None` on any model
# with a positions field so validation can't be forgotten.
Positions = Annotated[list[str] | None, AfterValidator(normalize_positions)]

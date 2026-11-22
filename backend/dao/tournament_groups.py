"""
Tournament group format (SB-1752).

A tournament match carries one free-text ``tournament_group``. Events that run
several competitions side by side (MLS NEXT Fest: Homegrown Division, Academy
Division) reuse the same labels in each — both have a "Group A" — so the stored
value is namespaced by division::

    "HD · A"         division "HD", label "A"
    "HD · Showcase"  division "HD", label "Showcase"
    "Bracket A"      legacy, no division — displayed unchanged

**The format is frozen.** Bracket follows store this string, so changing the
separator orphans every follow already saved. ``frontend/src/utils/
tournamentGroups.js`` mirrors this module; change one and change the other.

The frozen format has three parts, and the two implementations must agree on
each byte for byte:

- the separator, ``GROUP_SEPARATOR``;
- the characters trimmed from a part, ``GROUP_WHITESPACE`` — an explicit list,
  because ``str.strip()`` and JavaScript's ``trim()`` disagree (JS trims
  U+FEFF, Python trims U+001C-U+001F and U+0085);
- the compose rule: a division cannot contain the separator, nor can a label
  that has no division, since either would split back into different parts.
  A label containing the separator *with* a division is legal — the split is
  on the first separator only.

Pure functions only — no DAO or database imports.
"""

# Space, U+00B7 MIDDLE DOT, space.
GROUP_SEPARATOR = " · "

# Every character trimmed from a part: the union of what str.strip() and JS
# trim() remove. Same literal as tournamentGroups.js.
GROUP_WHITESPACE = (
    "\t\n\u000b\u000c\r \u001c\u001d\u001e\u001f\u0085\u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000\ufeff"
)

DIVISION_SEPARATOR_ERROR = "A tournament group division cannot contain ' · ' or end with ' ·'"
LABEL_SEPARATOR_ERROR = "A tournament group label cannot contain ' · ' unless a division is given"


def _clean(part: str | None) -> str | None:
    """Trim GROUP_WHITESPACE from a part; empty and whitespace-only collapse to None."""
    if part is None:
        return None
    part = str(part).strip(GROUP_WHITESPACE)
    return part or None


def compose_group(division: str | None, label: str | None) -> str | None:
    """Build the stored ``tournament_group`` value from its two parts.

    A missing part is simply left out, so a label on its own stays a legacy
    un-namespaced value. Returns None when both are missing.

    Raises ValueError for parts that would not split back into themselves: a
    division that contains the separator (or ends with " ·", which forms one
    with the separator that follows), and a label that contains the separator
    when there is no division.
    """
    division = _clean(division)
    label = _clean(label)
    if division and f"{division}{GROUP_SEPARATOR}".index(GROUP_SEPARATOR) != len(division):
        raise ValueError(DIVISION_SEPARATOR_ERROR)
    if label and not division and GROUP_SEPARATOR in label:
        raise ValueError(LABEL_SEPARATOR_ERROR)
    if division and label:
        return f"{division}{GROUP_SEPARATOR}{label}"
    return division or label


def split_group(value: str | None) -> dict[str, str | None]:
    """Split a stored ``tournament_group`` into ``{"division", "label"}``.

    Splits on the first separator only. A value with no separator is a legacy
    group: division None, label the value as stored. Never raises — a stored
    value always splits, whatever ``compose_group`` would say about it today.
    """
    value = _clean(value)
    if value is None:
        return {"division": None, "label": None}
    if GROUP_SEPARATOR not in value:
        return {"division": None, "label": value}
    division, label = value.split(GROUP_SEPARATOR, 1)
    return {"division": _clean(division), "label": _clean(label)}

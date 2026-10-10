"""Objectionable-language filter for live match chat (SB-1309).

App Store guideline 1.2 requires an app with user-generated content to filter
objectionable material before it is shown. Live chat is that content.

The list is deliberately conservative: slurs, explicit sexual terms and severe
profanity — not every rude word. Chat here is parents and players at youth
matches, and a filter that rejects ordinary messages teaches people to route
around it. Reports, blocks and bans (the rest of SB-1309) catch what a word
list cannot.

Matching is per word, never per substring. That is the whole defence against
the Scunthorpe problem: team and player names such as Scunthorpe, Dickson,
Cockburn, Hancock or Shittu contain listed letters but are not listed words.
Three tiers keep it that way:

- ``_ANY_SUFFIX`` — stems no ordinary word starts with; any ending matches
  ("fuckin", "fuckwit").
- ``_COMMON_SUFFIX`` — stems that also start ordinary words; only the usual
  inflections match ("shitty" yes, "Shittu" no; "raped" yes, "rapeseed" no).
- ``_EXACT`` — whole words only.

Before matching, text is lower-cased, accents are stripped, common
leetspeak substitutions are undone ("sh1t", "@sshole") and stretched letters
are collapsed ("fuuuuck", "asssshole"). Only runs of three or more count as
stretching: collapsing doubles would turn "Gok" into a match for a slur.
"""

from __future__ import annotations

import re
import unicodedata

_ANY_SUFFIX = frozenset(
    {
        "fuck",
        "motherfuck",
        "cocksuck",
        "nigger",
        "faggot",
        "wanker",
    }
)

_COMMON_SUFFIX = frozenset(
    {
        "shit",
        "bullshit",
        "bitch",
        "whore",
        "slut",
        "retard",
        "rape",
        "rapist",
        "porn",
        "dildo",
        "cumshot",
        "gangbang",
        "blowjob",
        "handjob",
        "rimjob",
        "nigga",
        "tranny",
    }
)

_SUFFIXES = ("", "s", "es", "z", "y", "ey", "ie", "er", "ers", "ing", "in", "ed", "d", "ty", "head", "heads", "face")

_EXACT = frozenset(
    {
        # Severe profanity
        "cunt",
        "cunts",
        "asshole",
        "assholes",
        "arsehole",
        "arseholes",
        "dickhead",
        "dickheads",
        "jizz",
        # Slurs
        "fag",
        "fags",
        "spic",
        "spics",
        "kike",
        "kikes",
        "wetback",
        "wetbacks",
        "paki",
        "pakis",
        "gook",
        "gooks",
        "raghead",
        "ragheads",
        "towelhead",
        "towelheads",
    }
)

_LEET_DIGITS = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b"})
_LEET_SYMBOLS = {"@": "a", "$": "s", "!": "i", "|": "l", "+": "t"}
# A symbol stands for a letter only when a letter follows it in the same run:
# "b!tch" and "@sshole" are disguises, the "!" in "shit!" is punctuation.
_SYMBOL_IN_WORD = re.compile(r"[@$!|+](?=[@$!|+]*[a-z])")

_NON_LETTERS = re.compile(r"[^a-z]+")
_STRETCHED = re.compile(r"(.)\1{2,}")

_ANY_SUFFIX_STEMS = tuple(_ANY_SUFFIX)
_COMMON_SUFFIX_FORMS = frozenset(stem + suffix for stem in _COMMON_SUFFIX for suffix in _SUFFIXES)


def normalise(text: str) -> list[str]:
    """Lower-cased, de-accented, de-leeted words of `text`."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    leet_undone = _SYMBOL_IN_WORD.sub(lambda m: _LEET_SYMBOLS[m.group()], ascii_only.lower().translate(_LEET_DIGITS))
    words = _NON_LETTERS.split(leet_undone)
    return [w for w in words if w]


def _variants(word: str) -> set[str]:
    """The word as written, and with stretched letters cut to one and to two.

    Both lengths, because the listed word may have either: "fuuuuck" is
    "fuck", "asssshole" is "asshole".
    """
    return {word, _STRETCHED.sub(r"\1", word), _STRETCHED.sub(r"\1\1", word)}


def _is_objectionable_word(word: str) -> bool:
    for variant in _variants(word):
        if variant in _EXACT or variant in _COMMON_SUFFIX_FORMS or variant.startswith(_ANY_SUFFIX_STEMS):
            return True
    return False


def contains_objectionable_language(text: str) -> bool:
    """True when any word of `text` is on the list."""
    return any(_is_objectionable_word(word) for word in normalise(text))

"""Tournament group format (SB-1752).

The default fixture is a legacy un-namespaced group ("Bracket A") — every
tournament loaded before MLS NEXT Fest, and it must come back unchanged.
"""

import pytest

from dao.tournament_groups import (
    DIVISION_SEPARATOR_ERROR,
    GROUP_SEPARATOR,
    GROUP_WHITESPACE,
    LABEL_SEPARATOR_ERROR,
    compose_group,
    split_group,
)

pytestmark = pytest.mark.unit

# The trimmed characters, as code points. Frozen with the format.
WHITESPACE_CODE_POINTS = [
    0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0x1C, 0x1D, 0x1E, 0x1F, 0x85, 0xA0, 0x1680,
    0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200A,
    0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF,
]  # fmt: skip

# (stored value, division, label). The same table is in
# frontend/src/__tests__/utils/tournamentGroups.spec.js — keep them identical,
# so a drift between the two implementations fails a test on one side.
SPLIT_PARITY_CASES = [
    ("\ufeffHD \u00b7 A", "HD", "A"),  # BOM: JS trim() strips it, str.strip() does not
    ("\u00a0HD \u00b7 A\u00a0", "HD", "A"),  # NBSP padding
    ("\u0085HD \u00b7 A\u0085", "HD", "A"),  # NEL: str.strip() strips it, JS trim() does not
    ("\u001cHD \u00b7 A\u001f", "HD", "A"),
    ("\u2003HD \u00b7 A\u3000", "HD", "A"),
    ("\t HD \u00b7 A \r\n", "HD", "A"),
    ("HD\u00a0 \u00b7 \ufeffA", "HD", "A"),  # padding inside, next to the separator
    ("\ufeffBracket A\u0085", None, "Bracket A"),
    ("\ufeff\u00a0\u0085", None, None),
    # Trimming the whole value first eats the separator's own space, so a
    # value with an empty side is a legacy label, not a half-empty pair.
    ("HD \u00b7 \ufeff", None, "HD \u00b7"),
    ("\u0085 \u00b7 A", None, "\u00b7 A"),
    ("HD\u200b \u00b7 A", "HD\u200b", "A"),  # zero-width space is not trimmed
    ("HD\u00a0\u00b7\u00a0A", None, "HD\u00a0\u00b7\u00a0A"),  # NBSPs do not make a separator
]

# (division, label) pairs compose_group accepts; each must split back to itself.
ROUND_TRIP_CASES = [
    ("HD", "A"),
    ("AD", "Showcase"),
    (None, "Bracket A"),
    ("HD", "A \u00b7 Late"),  # separator in the label is legal with a division
    ("HD", "A \u00b7 B \u00b7 C"),
    ("HD", "\u00b7 A"),
    ("\u00b7", "A"),
    ("U15\u00b7B", "A"),
    (None, "U15\u00b7A"),
    (None, "A \u00b7"),
]

# (division, label, message) compose_group refuses.
REJECTED_CASES = [
    ("HD \u00b7 X", "A", DIVISION_SEPARATOR_ERROR),
    ("HD \u00b7 X", None, DIVISION_SEPARATOR_ERROR),
    ("HD \u00b7", "A", DIVISION_SEPARATOR_ERROR),  # would compose to "HD · · A"
    (None, "A \u00b7 B", LABEL_SEPARATOR_ERROR),
    ("", "A \u00b7 B", LABEL_SEPARATOR_ERROR),
    ("\ufeff", "A \u00b7 B", LABEL_SEPARATOR_ERROR),
]


class TestSeparator:
    def test_is_space_middle_dot_space(self):
        # Frozen: bracket follows store the composed string.
        assert GROUP_SEPARATOR == " · "


class TestComposeGroup:
    def test_namespaced(self):
        assert compose_group("HD", "A") == "HD · A"

    def test_stage_label(self):
        assert compose_group("HD", "Showcase") == "HD · Showcase"

    def test_label_only_is_legacy(self):
        assert compose_group(None, "Bracket A") == "Bracket A"

    def test_division_only(self):
        assert compose_group("HD", None) == "HD"

    @pytest.mark.parametrize(("division", "label"), [(None, None), ("", ""), ("  ", None), (None, " ")])
    def test_nothing_is_none(self, division, label):
        assert compose_group(division, label) is None

    def test_strips_whitespace(self):
        assert compose_group("  HD ", " A  ") == "HD · A"

    def test_empty_string_counts_as_missing(self):
        assert compose_group("", "A") == "A"
        assert compose_group("HD", "") == "HD"


class TestSplitGroup:
    def test_namespaced(self):
        assert split_group("HD · A") == {"division": "HD", "label": "A"}

    def test_legacy_has_no_division(self):
        assert split_group("Bracket A") == {"division": None, "label": "Bracket A"}

    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_absent(self, value):
        assert split_group(value) == {"division": None, "label": None}

    def test_splits_on_first_separator_only(self):
        assert split_group("HD · A · Late") == {"division": "HD", "label": "A · Late"}

    def test_strips_whitespace(self):
        assert split_group("  HD · A ") == {"division": "HD", "label": "A"}

    def test_bare_dot_without_spaces_is_not_a_separator(self):
        assert split_group("U15·A") == {"division": None, "label": "U15·A"}

    @pytest.mark.parametrize(
        "value",
        ["HD \u00b7 X \u00b7 A", "A \u00b7 B", "HD \u00b7 \u00b7 A", " \u00b7 ", "\u00b7 \u00b7 \u00b7"],
    )
    def test_never_raises_on_a_stored_value(self, value):
        # compose_group would refuse some of these; a stored one still splits.
        assert set(split_group(value)) == {"division", "label"}


class TestWhitespace:
    def test_trimmed_set_is_frozen(self):
        assert [ord(c) for c in GROUP_WHITESPACE] == WHITESPACE_CODE_POINTS

    @pytest.mark.parametrize("code_point", WHITESPACE_CODE_POINTS)
    def test_every_listed_character_is_trimmed(self, code_point):
        pad = chr(code_point)
        assert split_group(f"{pad}HD \u00b7 A{pad}") == {"division": "HD", "label": "A"}
        assert compose_group(f"{pad}HD{pad}", f"{pad}A{pad}") == "HD \u00b7 A"

    @pytest.mark.parametrize(("value", "division", "label"), SPLIT_PARITY_CASES)
    def test_split_parity(self, value, division, label):
        assert split_group(value) == {"division": division, "label": label}


class TestRoundTrip:
    @pytest.mark.parametrize(("division", "label"), ROUND_TRIP_CASES)
    def test_legal_pair_round_trips(self, division, label):
        assert split_group(compose_group(division, label)) == {"division": division, "label": label}

    @pytest.mark.parametrize(("division", "label", "message"), REJECTED_CASES)
    def test_rejects_a_pair_that_would_not_round_trip(self, division, label, message):
        with pytest.raises(ValueError) as excinfo:
            compose_group(division, label)
        assert str(excinfo.value) == message

    def test_messages_are_frozen(self):
        # Same text as tournamentGroups.js.
        assert DIVISION_SEPARATOR_ERROR == "A tournament group division cannot contain ' \u00b7 ' or end with ' \u00b7'"
        assert LABEL_SEPARATOR_ERROR == "A tournament group label cannot contain ' \u00b7 ' unless a division is given"

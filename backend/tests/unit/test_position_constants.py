"""Position taxonomy tests.

Guards frontend/backend parity: backend/constants/positions.py is a
hand-mirrored copy of frontend/src/constants/positions.js. If either side
changes without the other, these tests fail.
"""

import json
import re
from pathlib import Path

import pytest

from constants.positions import (
    LEGACY_POSITION_MAP,
    POSITION_GROUPS,
    VALID_POSITIONS,
    normalize_positions,
)

FRONTEND_POSITIONS_JS = (
    Path(__file__).resolve().parents[3] / "frontend" / "src" / "constants" / "positions.js"
)


def _parse_js_object(source: str, name: str) -> dict:
    """Extract a simple const object literal from positions.js as JSON."""
    match = re.search(rf"export const {name} = (\{{.*?\n\}});", source, re.DOTALL)
    assert match, f"Could not find {name} in positions.js"
    text = match.group(1)
    # strip comments
    text = re.sub(r"//[^\n]*", "", text)
    # quote keys, convert single-quoted strings, drop trailing commas
    text = re.sub(r"(\w+):", r'"\1":', text)
    text = text.replace("'", '"')
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


class TestFrontendParity:
    def test_position_groups_match_frontend(self):
        source = FRONTEND_POSITIONS_JS.read_text()
        js_groups = _parse_js_object(source, "POSITION_GROUPS")
        assert js_groups == POSITION_GROUPS

    def test_legacy_map_matches_frontend(self):
        source = FRONTEND_POSITIONS_JS.read_text()
        js_legacy = _parse_js_object(source, "LEGACY_POSITION_MAP")
        assert js_legacy == LEGACY_POSITION_MAP

    def test_slot_to_group_covers_all_formation_slots(self):
        """Every slot code used in formations.js must map to a group."""
        formations_js = FRONTEND_POSITIONS_JS.parent.parent / "config" / "formations.js"
        slot_codes = set(re.findall(r"position: '([A-Z]+)'", formations_js.read_text()))
        slot_map = _parse_js_object(FRONTEND_POSITIONS_JS.read_text(), "SLOT_TO_GROUP")
        missing = slot_codes - set(slot_map)
        assert not missing, f"Formation slots missing from SLOT_TO_GROUP: {sorted(missing)}"
        assert set(slot_map.values()) <= set(POSITION_GROUPS)


class TestNormalizePositions:
    def test_none_passthrough(self):
        assert normalize_positions(None) is None

    def test_empty_list(self):
        assert normalize_positions([]) == []

    def test_valid_codes_order_preserved(self):
        assert normalize_positions(["ST", "CB", "GK"]) == ["ST", "CB", "GK"]

    def test_legacy_codes_mapped(self):
        assert normalize_positions(["LCB", "RCM"]) == ["CB", "CM"]

    def test_dedupe_keeps_first_occurrence(self):
        # LCB and RCB both map to CB -> single CB
        assert normalize_positions(["LCB", "RCB", "ST"]) == ["CB", "ST"]

    def test_invalid_code_raises(self):
        with pytest.raises(ValueError, match="Invalid position code"):
            normalize_positions(["XX"])

    def test_each_code_in_exactly_one_group(self):
        seen = []
        for codes in POSITION_GROUPS.values():
            seen.extend(codes)
        assert len(seen) == len(set(seen))
        assert set(seen) == VALID_POSITIONS

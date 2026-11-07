"""Qualification rules YAML: loader and validation (SB-1549)."""

import re
from pathlib import Path

import pytest
import yaml

from mt_tools.qualification_rules import (
    RULES_DIR,
    RulesError,
    conference_kind,
    load_rules,
    parse_rules,
    season_key,
    tier_of,
)

pytestmark = pytest.mark.unit

SOURCES_MD = Path(__file__).resolve().parents[3] / "docs/research/notes/mls-next-qualification-2026-27/sources.md"


def _doc(**rule_overrides) -> dict:
    rule = {
        "id": "test-rule",
        "competition": "Flex conference regular season",
        "pathway": "MLS NEXT Cup berth",
        "tier": "Homegrown",
        "age_groups": ["U15"],
        "conference_kind": "flex",
        "selector": {"rank": 1},
        "slots": None,
        "confirmed": True,
        "source_url": "https://example.org/release",
        "source_date": "2026-10-05",
        "summary": "A rule.",
    }
    rule.update(rule_overrides)
    return {"season": "2026-27", "target": "Cup", "reviewed": "2026-11-06", "rules": [rule]}


def _parse(doc: dict):
    return parse_rules(yaml.safe_dump(doc))


class TestShippedFile:
    def test_2026_27_loads(self):
        rules = load_rules("2026-27")
        assert rules.season == "2026-27"
        assert len(rules.rules) >= 5

    def test_every_confirmed_rule_is_cited(self):
        for rule in load_rules("2026-27").rules:
            if rule.confirmed:
                assert rule.source_url and rule.source_date, rule.id

    def test_unknown_homegrown_slot_counts_stay_null(self):
        rules = load_rules("2026-27")
        for rule_id in ("hg-league-play", "hg-pro-player-pathway", "hg-flex-event-group-winner"):
            assert rules.get(rule_id).slots is None, rule_id

    def test_fest_is_recorded_as_not_a_route(self):
        fest = load_rules("2026-27").get("fest-not-a-route")
        assert fest.qualifies is False and fest.confirmed

    def test_claim_ids_exist_in_sources_table(self):
        """Every `claims` id must be a row (or open question) in the research audit trail."""
        if not SOURCES_MD.is_file():
            pytest.skip("docs not present")
        text = SOURCES_MD.read_text(encoding="utf-8")
        known = set(re.findall(r"^\| (\w+) \|", text, flags=re.MULTILINE))
        known |= set(re.findall(r"\b(OQ\d+)\b", text))
        for rule in load_rules("2026-27").rules:
            missing = [c for c in rule.claims if c not in known]
            assert not missing, f"{rule.id}: {missing}"

    def test_files_are_named_for_their_season(self):
        for path in RULES_DIR.glob("*.yaml"):
            assert load_rules(path.stem).season == path.stem


class TestApplicable:
    def test_u15_flex_conference_routes(self):
        ids = {r.id for r in load_rules().applicable("U15", "flex")}
        assert ids == {"hg-flex-conference-bye-race", "hg-flex-conference-winner-berth"}

    def test_confirmed_only_drops_inferred(self):
        ids = {r.id for r in load_rules().applicable("U15", "flex", confirmed_only=True)}
        assert ids == {"hg-flex-conference-bye-race"}

    def test_no_ppp_route_at_u15(self):
        assert load_rules().applicable("U15", "ppp") == []
        assert [r.id for r in load_rules().applicable("U16", "ppp")] == ["hg-pro-player-pathway"]

    def test_event_rules_are_not_table_rules(self):
        """Fest, Flex groups and the Play-In are not tied to a table, so no match table carries them."""
        ids = {r.id for kind in ("league", "flex", "ppp") for r in load_rules().applicable("U15", kind, tier=None)}
        assert "fest-not-a-route" not in ids
        assert "hg-flex-event-group-winner" not in ids


class TestValidation:
    def test_minimal_rule_parses(self):
        assert _parse(_doc()).rules[0].id == "test-rule"

    def test_confirmed_rule_without_source_is_rejected(self):
        with pytest.raises(RulesError, match="no source_url"):
            _parse(_doc(source_url=None))

    def test_confirmed_rule_without_source_date_is_rejected(self):
        with pytest.raises(RulesError, match="no source_url"):
            _parse(_doc(source_date=None))

    def test_unconfirmed_rule_may_lack_a_source(self):
        assert _parse(_doc(confirmed=False, source_url=None, source_date=None)).rules[0].source_url is None

    def test_unknown_slots_stay_null(self):
        assert _parse(_doc(slots=None)).rules[0].slots is None

    def test_zero_slots_is_rejected(self):
        with pytest.raises(RulesError, match="never 0"):
            _parse(_doc(slots=0))

    def test_unknown_age_group_is_rejected(self):
        with pytest.raises(RulesError):
            _parse(_doc(age_groups=["U18"]))

    def test_unknown_key_is_rejected(self):
        with pytest.raises(RulesError):
            _parse(_doc(cutoff=20))

    def test_http_source_is_rejected(self):
        with pytest.raises(RulesError, match="https"):
            _parse(_doc(source_url="http://example.org"))

    def test_duplicate_ids_are_rejected(self):
        doc = _doc()
        doc["rules"].append(dict(doc["rules"][0]))
        with pytest.raises(RulesError, match="duplicate"):
            _parse(doc)

    def test_not_yaml_mapping(self):
        with pytest.raises(RulesError):
            parse_rules("- just\n- a list\n")

    def test_missing_season_file(self):
        with pytest.raises(RulesError, match="no qualification rules"):
            load_rules("1999-00")


class TestHelpers:
    @pytest.mark.parametrize(
        ("name", "key"),
        [("2026-2027", "2026-27"), (" 2025-2026 ", "2025-26"), ("Fall 2026", None), (None, None), ("2026-27", None)],
    )
    def test_season_key(self, name, key):
        assert season_key(name) == key

    @pytest.mark.parametrize(
        ("league", "division", "kind"),
        [
            ("Flex", "Turnpike", "flex"),
            ("Homegrown", "Northeast", "league"),
            ("Homegrown", "Northeast (Pro Player Pathway)", "ppp"),
            ("Academy", "New England", "league"),
            ("Tournament", "Fest", None),
            (None, None, None),
        ],
    )
    def test_conference_kind(self, league, division, kind):
        assert conference_kind(league, division) == kind

    @pytest.mark.parametrize(
        ("league", "tier"), [("Homegrown", "Homegrown"), ("Flex", "Homegrown"), ("Academy", "Academy"), ("x", None)]
    )
    def test_tier_of(self, league, tier):
        assert tier_of(league) == tier

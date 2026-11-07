"""MLS NEXT qualification rules, one reviewed YAML file per season (SB-1549).

The rules live in `backend/qualification_rules/<season>.yaml`, encoded from the
reviewed research (docs/03-architecture/mls-next-qualification-facts.md). This
module loads and validates them; it never decides anything. Agents read them to
say what is at stake in a match, and the validation exists so they can only say
what a source said:

- a `confirmed` rule must cite a source;
- `slots` is a positive count or null. Null is "MLS has not said"; 0 is rejected,
  because a 0 would read as "no places", a claim nobody made (CLAUDE.md: never
  pun absent into zero);
- rule ids are unique, age groups are real MLS NEXT age groups, and unknown keys
  are an error rather than silently dropped.

A malformed file fails loudly at load. A rule that quietly vanished would make a
stakes claim look unsupported, or worse, let a stale one stand.
"""

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RULES_DIR = Path(__file__).resolve().parent.parent / "qualification_rules"

AgeGroup = Literal["U13", "U14", "U15", "U16", "U17", "U19"]
Tier = Literal["Homegrown", "Academy"]
ConferenceKind = Literal["league", "flex", "ppp"]


class RulesError(ValueError):
    """The rules file is missing or does not validate."""


class Selector(BaseModel):
    """Who a rule picks. All fields optional; an absent selector means "not published"."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int | None = Field(default=None, ge=1)
    group_winner: bool = False
    event_winner: bool = False


class QualificationRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    competition: str = Field(min_length=1)
    pathway: str = Field(min_length=1)
    tier: Tier | None
    age_groups: tuple[AgeGroup, ...] = Field(min_length=1)
    conference_kind: ConferenceKind | None
    selector: Selector | None
    slots: int | None
    qualifies: bool = True
    confirmed: bool
    source_url: str | None = None
    source_date: date | None = None
    claims: tuple[str, ...] = ()
    summary: str = Field(min_length=1)

    @field_validator("slots")
    @classmethod
    def _slots_positive_or_null(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("slots must be a positive count, or null when not published (never 0)")
        return value

    @field_validator("source_url")
    @classmethod
    def _url_shape(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("https://"):
            raise ValueError("source_url must be an https:// URL")
        return value

    @model_validator(mode="after")
    def _confirmed_needs_source(self) -> Self:
        if self.confirmed and not (self.source_url and self.source_date):
            raise ValueError(f"rule {self.id!r} is confirmed but has no source_url/source_date")
        return self


class RuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    season: str = Field(pattern=r"^\d{4}-\d{2}$")
    target: str
    reviewed: date
    rules: tuple[QualificationRule, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        seen: set[str] = set()
        for rule in self.rules:
            if rule.id in seen:
                raise ValueError(f"duplicate rule id {rule.id!r}")
            seen.add(rule.id)
        return self

    def get(self, rule_id: str) -> QualificationRule | None:
        return next((r for r in self.rules if r.id == rule_id), None)

    def applicable(
        self,
        age_group: str,
        conference_kind: str | None = None,
        tier: str | None = "Homegrown",
        *,
        confirmed_only: bool = False,
    ) -> list[QualificationRule]:
        """Routes that a table of this kind, at this age, feeds.

        Only qualifying routes (`qualifies: true`) tied to a conference kind are
        returned: a match is played in a table, and a table is what a rule can
        say something about. `confirmed_only` drops inferred rules.
        """
        return [
            r
            for r in self.rules
            if r.qualifies
            and r.conference_kind is not None
            and r.conference_kind == conference_kind
            and age_group in r.age_groups
            and (tier is None or r.tier == tier)
            and (r.confirmed or not confirmed_only)
        ]


def parse_rules(text: str) -> RuleSet:
    """Validate a rules document. Raises RulesError with the reason."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RulesError(f"rules file is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise RulesError("rules file must be a mapping with season, target, reviewed and rules")
    try:
        return RuleSet.model_validate(data)
    except ValueError as exc:
        raise RulesError(str(exc)) from exc


@lru_cache(maxsize=8)
def load_rules(season: str = "2026-27", rules_dir: Path = RULES_DIR) -> RuleSet:
    """The reviewed rules for a season ("2026-27"). Cached: the file ships with the image."""
    path = rules_dir / f"{season}.yaml"
    if not path.is_file():
        raise RulesError(f"no qualification rules for season {season!r}")
    rules = parse_rules(path.read_text(encoding="utf-8"))
    if rules.season != season:
        raise RulesError(f"{path.name} declares season {rules.season!r}")
    return rules


def season_key(season_name: str | None) -> str | None:
    """MT's season name ("2026-2027") as a rules key ("2026-27"); None when it isn't one."""
    if not season_name:
        return None
    parts = season_name.strip().split("-")
    if len(parts) != 2 or not all(p.isdigit() and len(p) == 4 for p in parts):
        return None
    return f"{parts[0]}-{parts[1][2:]}"


def conference_kind(league_name: str | None, division_name: str | None) -> ConferenceKind | None:
    """The rules' conference kind for an MT division, from its league and name.

    In MT, Flex conferences are divisions of the league "Flex" (Empire, Turnpike,
    New England...); Pro Player Pathway divisions carry "(Pro Player Pathway)" in
    their name; any other Homegrown or Academy division is a league conference.
    Which tier it is comes from `tier_of`.
    """
    league = (league_name or "").strip().casefold()
    name = (division_name or "").casefold()
    if league == "flex":
        return "flex"
    if "pro player pathway" in name:
        return "ppp"
    if league in ("homegrown", "academy"):
        return "league"
    return None


def tier_of(league_name: str | None) -> Tier | None:
    """The MLS NEXT tier of an MT league: Flex is played by Homegrown teams."""
    league = (league_name or "").strip().casefold()
    if league in ("homegrown", "flex"):
        return "Homegrown"
    if league == "academy":
        return "Academy"
    return None

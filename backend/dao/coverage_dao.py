"""Is MT actually tracking what it thinks it is? (SB-1021)

Everything else in the product answers "what is here" — `get_competitions_present`,
`get_leagues_present`, `/api/match-types/available` — and every one of them
derives from fixtures that arrived. None of them can report a conference that
sent nothing, because absence produces no row to count.

That blind spot cost a season. On 2026-09-06 MT held fixtures for 13 of 13 Flex
conferences and 4 of 4 Pro Player Pathway divisions, and 2 of the 8 Homegrown
League conferences. Nothing in the product said so.

This reads the other half — `division_age_groups`, what the league is expected
to run — and diffs it against what arrived.
"""

from __future__ import annotations

from typing import Any

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

COVERED = "covered"
EMPTY = "empty"
UNEXPECTED = "unexpected"
UNDECLARED = "undeclared"


def _status(row: dict[str, Any], league_declared: bool) -> str:
    """Four outcomes, and the distinction between the last two matters.

    `empty` is a conference the league runs that sent nothing — the finding
    this whole module exists for.

    `unexpected` and `undeclared` both mean "fixtures arrived for something not
    on file", and collapsing them would raise an alarm about correct data. In a
    league with expectations, unlisted fixtures are a real surprise: the feed
    has changed shape. In a league with NO expectations, they are simply all we
    have — MT holds 49 real Academy fixtures and no statement of what the
    Academy Division runs, and calling those "unexpected" would report good
    data as a defect.
    """
    if row.get("is_expected"):
        return COVERED if (row.get("fixtures") or 0) > 0 else EMPTY
    return UNEXPECTED if league_declared else UNDECLARED


class CoverageDAO(BaseDAO):
    """Expected competition coverage, diffed against reality."""

    def report(self, season_id: int) -> dict[str, Any]:
        """Coverage for one season: every row, plus totals, plus per league.

        Returns an empty report rather than raising. This backs an admin screen
        and a CLI command; a diagnostic that takes down the page it reports on
        is worse than no diagnostic.
        """
        try:
            response = self.client.rpc(
                "competition_coverage", {"p_season_id": season_id}
            ).execute()
            rows = response.data or []
        except Exception:
            logger.exception("Could not read competition coverage", season_id=season_id)
            return {
                "season_id": season_id,
                "rows": [],
                "summary": {
                    "expected": 0,
                    "covered": 0,
                    "empty": 0,
                    "unexpected": 0,
                    "undeclared": 0,
                },
                "leagues": [],
                "available": False,
            }

        # Which leagues have any expectations at all has to be known before a
        # row's status can be decided, so it is computed first over the whole
        # set rather than per row.
        declared = {
            row.get("league_name")
            for row in rows
            if row.get("is_expected")
        }
        for row in rows:
            row["status"] = _status(row, row.get("league_name") in declared)

        return {
            "season_id": season_id,
            "rows": rows,
            "summary": self._summary(rows),
            "leagues": self._by_league(rows),
            "available": True,
        }

    def empty_count(self, season_id: int) -> int:
        """How many expected conference/age-group pairs got nothing.

        The single number worth putting on an admin badge.
        """
        return self.report(season_id)["summary"]["empty"]

    @staticmethod
    def _summary(rows: list[dict[str, Any]]) -> dict[str, int]:
        # `expected` is the denominator, and it ships with every summary so no
        # caller can state a coverage figure without it (CLAUDE.md rule 3).
        return {
            "expected": sum(1 for r in rows if r.get("is_expected")),
            "covered": sum(1 for r in rows if r["status"] == COVERED),
            "empty": sum(1 for r in rows if r["status"] == EMPTY),
            "unexpected": sum(1 for r in rows if r["status"] == UNEXPECTED),
            "undeclared": sum(1 for r in rows if r["status"] == UNDECLARED),
        }

    @staticmethod
    def _by_league(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Per-league totals, and whether the league declared anything at all.

        `declared: false` is not the same as full coverage, and the difference
        matters: the Academy Division runs its own MLS NEXT Cup with separate
        U15-U19 finals, and MT holds one conference of it. Reporting that as
        "covered" because nothing contradicts it would be the report lying by
        omission — so a league with no expectations on file says so.
        """
        leagues: dict[str, dict[str, Any]] = {}
        for row in rows:
            name = row.get("league_name") or "Unknown"
            entry = leagues.setdefault(
                name,
                {
                    "league": name,
                    "expected": 0,
                    "covered": 0,
                    "empty": 0,
                    "unexpected": 0,
                    "undeclared": 0,
                    "divisions": set(),
                },
            )
            entry["divisions"].add(row.get("division_name"))
            if row.get("is_expected"):
                entry["expected"] += 1
            entry[row["status"]] += 1

        out = []
        for entry in leagues.values():
            entry["divisions"] = len(entry["divisions"])
            entry["declared"] = entry["expected"] > 0
            out.append(entry)
        return sorted(out, key=lambda e: e["league"])

"""
Quality of Play (QoP) Rankings data access layer for MissingTable.

Data model (see migration 20260418000000_qop_snapshots_redesign.sql):

    qop_snapshots          one row per scrape that observed new data.
                           Keyed by (detected_at, division_id, age_group_id).
                           detected_at is the date the scraper first saw this
                           particular ranking set — not a wall-clock week.

    qop_rankings           one row per team per snapshot.  FK → qop_snapshots
                           with ON DELETE CASCADE.

Write path (`record_snapshot`) compares the incoming rankings against the
latest stored snapshot for the same (division, age_group).  If unchanged it
returns `{"status": "unchanged"}` without inserting anything — that's how we
distinguish "mlssoccer hasn't published new numbers yet" from "new publish".
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

logger = structlog.get_logger()


# Fields used to decide "did this snapshot change?".  `team_id` and `scraped_at`
# are deliberately excluded: team_id is derived by us via a name lookup (not
# part of the scraped payload) and scraped_at always differs per run.
_SIGNATURE_FIELDS = (
    "rank",
    "team_name",
    "matches_played",
    "att_score",
    "def_score",
    "qop_score",
)


def _to_float(value: Any) -> float | None:
    """Normalize Decimal/float/int/None to float for comparison."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _ranking_signature(entry: dict) -> tuple:
    """Build a comparable tuple for a single ranking row.

    Scores are rounded to 1 decimal to match the NUMERIC(5,1) DB precision —
    without rounding, a Decimal('87.6') read from the DB would compare
    unequal to a float 87.6 sent in a fresh payload.
    """
    return (
        int(entry["rank"]),
        str(entry["team_name"]),
        (
            int(entry["matches_played"])
            if entry.get("matches_played") is not None
            else None
        ),
        (
            round(_to_float(entry.get("att_score")), 1)
            if entry.get("att_score") is not None
            else None
        ),
        (
            round(_to_float(entry.get("def_score")), 1)
            if entry.get("def_score") is not None
            else None
        ),
        round(_to_float(entry["qop_score"]), 1),
    )


def _rankings_equal(a: list[dict], b: list[dict]) -> bool:
    """Two ranking lists are equal iff their ordered signature lists match."""
    if len(a) != len(b):
        return False
    a_sorted = sorted(a, key=lambda r: int(r["rank"]))
    b_sorted = sorted(b, key=lambda r: int(r["rank"]))
    return [_ranking_signature(x) for x in a_sorted] == [
        _ranking_signature(x) for x in b_sorted
    ]


class QoPRankingsDAO:
    """Data Access Object for Quality of Play rankings."""

    # ── Lookups ──────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_division_id(client, division: str) -> int | None:
        """Resolve a division name to its database ID (case-insensitive)."""
        try:
            response = client.table("divisions").select("id, name").execute()
            for row in response.data:
                if row["name"].lower() == division.lower():
                    return row["id"]
            logger.warning("qop_rankings_division_not_found", division=division)
            return None
        except Exception:
            logger.exception("qop_rankings_division_lookup_error", division=division)
            return None

    @staticmethod
    def _resolve_age_group_id(client, age_group: str) -> int | None:
        """Resolve an age group name to its database ID (case-insensitive)."""
        try:
            response = client.table("age_groups").select("id, name").execute()
            for row in response.data:
                if row["name"].lower() == age_group.lower():
                    return row["id"]
            logger.warning("qop_rankings_age_group_not_found", age_group=age_group)
            return None
        except Exception:
            logger.exception("qop_rankings_age_group_lookup_error", age_group=age_group)
            return None

    @staticmethod
    def _resolve_team_id(client, team_name: str) -> int | None:
        """Resolve a team name to its database ID (case-insensitive)."""
        try:
            response = (
                client.table("teams")
                .select("id, name")
                .ilike("name", team_name)
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0]["id"]
            return None
        except Exception:
            logger.warning("qop_rankings_team_lookup_error", team_name=team_name)
            return None

    # ── Snapshot fetch ───────────────────────────────────────────────────────

    @staticmethod
    def _fetch_latest_snapshot(
        client, division_id: int, age_group_id: int
    ) -> dict | None:
        """Return the most recent snapshot + its rankings, or None if absent."""
        snap_resp = (
            client.table("qop_snapshots")
            .select("id, detected_at")
            .eq("division_id", division_id)
            .eq("age_group_id", age_group_id)
            .order("detected_at", desc=True)
            .limit(1)
            .execute()
        )
        if not snap_resp.data:
            return None

        snap = snap_resp.data[0]
        rankings_resp = (
            client.table("qop_rankings")
            .select(
                "rank, team_name, team_id, matches_played, att_score, def_score, qop_score"
            )
            .eq("snapshot_id", snap["id"])
            .order("rank")
            .execute()
        )
        return {
            "id": snap["id"],
            "detected_at": snap["detected_at"],
            "rankings": rankings_resp.data or [],
        }

    # ── Write ────────────────────────────────────────────────────────────────

    @staticmethod
    def record_snapshot(client, snapshot: dict) -> dict:
        """
        Record a QoP snapshot — insert a new row iff the rankings differ from
        the most recent stored snapshot for the same (division, age_group).

        Args:
            client: Supabase client instance
            snapshot: {
                "detected_at": "2026-04-18",        # ISO date
                "division": "Northeast",
                "age_group": "U14",
                "source": "cronjob",                # optional
                "rankings": [{rank, team_name, matches_played,
                              att_score, def_score, qop_score}, ...]
            }

        Returns:
            {
                "status": "inserted" | "unchanged",
                "detected_at": "2026-04-18",
                "snapshot_id": int | None,          # None when status=unchanged
                "rankings_count": int,
            }

        Raises:
            ValueError: division or age_group cannot be resolved.
        """
        detected_at = snapshot["detected_at"]
        division_name = snapshot["division"]
        age_group_name = snapshot["age_group"]
        source = snapshot.get("source") or "cronjob"
        rankings = snapshot.get("rankings", [])

        division_id = QoPRankingsDAO._resolve_division_id(client, division_name)
        if division_id is None:
            raise ValueError(f"Division not found: {division_name!r}")

        age_group_id = QoPRankingsDAO._resolve_age_group_id(client, age_group_name)
        if age_group_id is None:
            raise ValueError(f"Age group not found: {age_group_name!r}")

        if not rankings:
            return {
                "status": "unchanged",
                "detected_at": detected_at,
                "snapshot_id": None,
                "rankings_count": 0,
            }

        latest = QoPRankingsDAO._fetch_latest_snapshot(
            client, division_id, age_group_id
        )
        if latest is not None and _rankings_equal(rankings, latest["rankings"]):
            logger.info(
                "qop_rankings_unchanged",
                division=division_name,
                age_group=age_group_name,
                latest_detected_at=latest["detected_at"],
            )
            return {
                "status": "unchanged",
                "detected_at": latest["detected_at"],
                "snapshot_id": latest["id"],
                "rankings_count": len(rankings),
            }

        # Create the snapshot row.  UNIQUE (detected_at, division, age_group)
        # will reject a second snapshot on the same day with different data —
        # that's intentional: two distinct ranking sets on the same date
        # means something is wrong upstream and we want to see it.
        snap_row = {
            "detected_at": detected_at,
            "division_id": division_id,
            "age_group_id": age_group_id,
            "source": source,
        }
        if snapshot.get("scraped_at"):
            snap_row["scraped_at"] = snapshot["scraped_at"]

        snap_resp = client.table("qop_snapshots").insert(snap_row).execute()
        if not snap_resp.data:
            raise RuntimeError("qop_snapshots insert returned no data")
        snapshot_id = snap_resp.data[0]["id"]

        # Build ranking rows with team_id lookup.
        ranking_rows = []
        for entry in rankings:
            team_id = QoPRankingsDAO._resolve_team_id(client, entry["team_name"])
            ranking_rows.append(
                {
                    "snapshot_id": snapshot_id,
                    "rank": entry["rank"],
                    "team_name": entry["team_name"],
                    "team_id": team_id,
                    "matches_played": entry.get("matches_played"),
                    "att_score": entry.get("att_score"),
                    "def_score": entry.get("def_score"),
                    "qop_score": entry["qop_score"],
                }
            )

        client.table("qop_rankings").insert(ranking_rows).execute()

        logger.info(
            "qop_rankings_inserted",
            detected_at=detected_at,
            division=division_name,
            age_group=age_group_name,
            snapshot_id=snapshot_id,
            count=len(ranking_rows),
        )
        return {
            "status": "inserted",
            "detected_at": detected_at,
            "snapshot_id": snapshot_id,
            "rankings_count": len(ranking_rows),
        }

    # ── Read ─────────────────────────────────────────────────────────────────

    @staticmethod
    def get_latest_with_delta(
        client, division_id: int, age_group_id: int
    ) -> dict:
        """
        Fetch the two most recent snapshots and compute per-team rank delta.

        Response shape is preserved from the legacy API for frontend compat —
        the `week_of` / `prior_week_of` keys are now semantically *detection
        dates* rather than ISO-week Mondays, but callers don't need to change.
        """
        empty = {
            "has_data": False,
            "week_of": None,
            "prior_week_of": None,
            "rankings": [],
        }

        try:
            snap_resp = (
                client.table("qop_snapshots")
                .select("id, detected_at")
                .eq("division_id", division_id)
                .eq("age_group_id", age_group_id)
                .order("detected_at", desc=True)
                .limit(2)
                .execute()
            )
            if not snap_resp.data:
                return empty

            current = snap_resp.data[0]
            prior = snap_resp.data[1] if len(snap_resp.data) > 1 else None

            current_rows_resp = (
                client.table("qop_rankings")
                .select(
                    "rank, team_name, team_id, matches_played, att_score, def_score, qop_score"
                )
                .eq("snapshot_id", current["id"])
                .order("rank")
                .execute()
            )
            current_rows = current_rows_resp.data or []

            prior_rank_by_team: dict[str, int] = {}
            if prior is not None:
                prior_rows_resp = (
                    client.table("qop_rankings")
                    .select("rank, team_name")
                    .eq("snapshot_id", prior["id"])
                    .execute()
                )
                for row in prior_rows_resp.data or []:
                    prior_rank_by_team[row["team_name"]] = row["rank"]

            rankings = []
            for row in current_rows:
                prior_rank = prior_rank_by_team.get(row["team_name"])
                rank_change = (
                    (prior_rank - row["rank"]) if prior_rank is not None else None
                )
                rankings.append(
                    {
                        "rank": row["rank"],
                        "team_name": row["team_name"],
                        "team_id": row.get("team_id"),
                        "matches_played": row.get("matches_played"),
                        "att_score": row.get("att_score"),
                        "def_score": row.get("def_score"),
                        "qop_score": row["qop_score"],
                        "rank_change": rank_change,
                    }
                )

            return {
                "has_data": True,
                "week_of": current["detected_at"],
                "prior_week_of": prior["detected_at"] if prior else None,
                "rankings": rankings,
            }

        except Exception:
            logger.exception(
                "qop_rankings_get_latest_error",
                division_id=division_id,
                age_group_id=age_group_id,
            )
            return empty

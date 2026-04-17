"""
Quality of Play (QoP) Rankings data access layer for MissingTable.

Provides upsert and query functionality for weekly QoP ranking snapshots
scraped from MLS Next standings pages.
"""

import structlog

logger = structlog.get_logger()


class QoPRankingsDAO:
    """Data Access Object for Quality of Play rankings."""

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
        """Resolve a team name to its database ID (case-insensitive). Returns None if no match."""
        try:
            response = client.table("teams").select("id, name").ilike("name", team_name).limit(1).execute()
            if response.data:
                return response.data[0]["id"]
            return None
        except Exception:
            logger.warning("qop_rankings_team_lookup_error", team_name=team_name)
            return None

    @staticmethod
    def upsert_snapshot(client, snapshot: dict) -> int:
        """
        Upsert a weekly QoP rankings snapshot.

        Args:
            client: Supabase client instance
            snapshot: Dict with shape:
                {
                    "week_of": "2026-04-14",
                    "division": "Northeast",
                    "age_group": "U14",
                    "scraped_at": "2026-04-16T12:00:00Z",  # optional, defaults to NOW()
                    "rankings": [
                        {
                            "rank": 1,
                            "team_name": "New York City FC",
                            "matches_played": 16,
                            "att_score": 89.6,
                            "def_score": 83.1,
                            "qop_score": 87.6
                        },
                        ...
                    ]
                }

        Returns:
            Count of rows upserted

        Raises:
            ValueError: If division or age_group cannot be resolved
        """
        week_of = snapshot["week_of"]
        division_name = snapshot["division"]
        age_group_name = snapshot["age_group"]
        scraped_at = snapshot.get("scraped_at")
        rankings = snapshot.get("rankings", [])

        division_id = QoPRankingsDAO._resolve_division_id(client, division_name)
        if division_id is None:
            raise ValueError(f"Division not found: {division_name!r}")

        age_group_id = QoPRankingsDAO._resolve_age_group_id(client, age_group_name)
        if age_group_id is None:
            raise ValueError(f"Age group not found: {age_group_name!r}")

        if not rankings:
            return 0

        rows = []
        for entry in rankings:
            team_id = QoPRankingsDAO._resolve_team_id(client, entry["team_name"])
            row = {
                "week_of": week_of,
                "division_id": division_id,
                "age_group_id": age_group_id,
                "rank": entry["rank"],
                "team_name": entry["team_name"],
                "team_id": team_id,
                "matches_played": entry.get("matches_played"),
                "att_score": entry.get("att_score"),
                "def_score": entry.get("def_score"),
                "qop_score": entry["qop_score"],
            }
            if scraped_at:
                row["scraped_at"] = scraped_at
            rows.append(row)

        response = (
            client.table("qop_rankings")
            .upsert(rows, on_conflict="week_of,division_id,age_group_id,rank")
            .execute()
        )

        count = len(response.data) if response.data else 0
        logger.info(
            "qop_rankings_upserted",
            week_of=week_of,
            division=division_name,
            age_group=age_group_name,
            count=count,
        )
        return count

    @staticmethod
    def get_latest_with_delta(client, division_id: int, age_group_id: int) -> dict:
        """
        Fetch the two most recent weeks of rankings for a division/age_group
        and compute week-over-week rank changes.

        Args:
            client: Supabase client instance
            division_id: Division database ID
            age_group_id: Age group database ID

        Returns:
            Dict with keys:
                has_data (bool), week_of (str|None), prior_week_of (str|None),
                rankings (list of dicts with rank_change field)
        """
        empty = {
            "has_data": False,
            "week_of": None,
            "prior_week_of": None,
            "rankings": [],
        }

        try:
            # Find the two most recent distinct week_of values
            weeks_response = (
                client.table("qop_rankings")
                .select("week_of")
                .eq("division_id", division_id)
                .eq("age_group_id", age_group_id)
                .order("week_of", desc=True)
                .execute()
            )

            if not weeks_response.data:
                return empty

            # Extract distinct week_of values in descending order
            seen = []
            for row in weeks_response.data:
                wk = row["week_of"]
                if wk not in seen:
                    seen.append(wk)
                if len(seen) == 2:
                    break

            current_week = seen[0]
            prior_week = seen[1] if len(seen) > 1 else None

            # Fetch current week rows
            current_response = (
                client.table("qop_rankings")
                .select("rank, team_name, team_id, matches_played, att_score, def_score, qop_score")
                .eq("division_id", division_id)
                .eq("age_group_id", age_group_id)
                .eq("week_of", current_week)
                .order("rank")
                .execute()
            )
            current_rows = current_response.data or []

            # Build prior week lookup: team_name -> rank
            prior_rank_by_team: dict[str, int] = {}
            if prior_week:
                prior_response = (
                    client.table("qop_rankings")
                    .select("rank, team_name")
                    .eq("division_id", division_id)
                    .eq("age_group_id", age_group_id)
                    .eq("week_of", prior_week)
                    .execute()
                )
                for row in (prior_response.data or []):
                    prior_rank_by_team[row["team_name"]] = row["rank"]

            # Build enriched rankings with rank_change
            rankings = []
            for row in current_rows:
                team_name = row["team_name"]
                current_rank = row["rank"]
                prior_rank = prior_rank_by_team.get(team_name)
                rank_change = (prior_rank - current_rank) if prior_rank is not None else None

                rankings.append({
                    "rank": current_rank,
                    "team_name": team_name,
                    "team_id": row.get("team_id"),
                    "matches_played": row.get("matches_played"),
                    "att_score": row.get("att_score"),
                    "def_score": row.get("def_score"),
                    "qop_score": row["qop_score"],
                    "rank_change": rank_change,
                })

            return {
                "has_data": True,
                "week_of": current_week,
                "prior_week_of": prior_week,
                "rankings": rankings,
            }

        except Exception:
            logger.exception(
                "qop_rankings_get_latest_error",
                division_id=division_id,
                age_group_id=age_group_id,
            )
            return empty

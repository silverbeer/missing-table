"""
Playoff Bracket Data Access Object.

Handles all database operations for playoff brackets including:
- Bracket retrieval with denormalized match data
- Bracket generation from standings
- Winner advancement between rounds
- Bracket deletion (reset)
"""

from datetime import date, timedelta

import structlog

from dao.base_dao import BaseDAO, dao_cache, invalidates_cache

logger = structlog.get_logger()

PLAYOFF_CACHE_PATTERN = "mt:dao:playoffs:*"
MATCHES_CACHE_PATTERN = "mt:dao:matches:*"

PLAYOFF_MATCH_TYPE_ID = 4

# Seeding: A1=1, B1=2, A2=3, B2=4, A3=5, B3=6, A4=7, B4=8
# QF matchups: (1v8, 4v5, 3v6, 2v7)
QF_MATCHUPS = [
    {"position": 1, "home_seed": 1, "away_seed": 8},  # A1 vs B4
    {"position": 2, "home_seed": 4, "away_seed": 5},  # B2 vs A3
    {"position": 3, "home_seed": 3, "away_seed": 6},  # A2 vs B3
    {"position": 4, "home_seed": 2, "away_seed": 7},  # B1 vs A4
]


class PlayoffDAO(BaseDAO):
    """Data access object for playoff bracket operations."""

    # === Bracket Query Methods ===

    @dao_cache("playoffs:bracket:{league_id}:{season_id}:{age_group_id}")
    def get_bracket(
        self, league_id: int, season_id: int, age_group_id: int
    ) -> list[dict]:
        """Get all bracket slots with denormalized match data.

        Returns slots with joined match and team information for display.
        """
        try:
            response = (
                self.client.table("playoff_bracket_slots")
                .select(
                    "*, match:matches("
                    "id, match_date, scheduled_kickoff, match_status, home_score, away_score, "
                    "home_team:teams!matches_home_team_id_fkey(id, name, club_id), "
                    "away_team:teams!matches_away_team_id_fkey(id, name, club_id)"
                    ")"
                )
                .eq("league_id", league_id)
                .eq("season_id", season_id)
                .eq("age_group_id", age_group_id)
                .order("round")
                .order("bracket_position")
                .execute()
            )

            slots = []
            for row in response.data:
                match = row.get("match")
                slot = {
                    "id": row["id"],
                    "league_id": row["league_id"],
                    "season_id": row["season_id"],
                    "age_group_id": row["age_group_id"],
                    "round": row["round"],
                    "bracket_position": row["bracket_position"],
                    "bracket_tier": row.get("bracket_tier"),
                    "match_id": row["match_id"],
                    "home_seed": row["home_seed"],
                    "away_seed": row["away_seed"],
                    "home_source_slot_id": row["home_source_slot_id"],
                    "away_source_slot_id": row["away_source_slot_id"],
                    # Denormalized match data
                    "home_team_name": None,
                    "away_team_name": None,
                    "home_team_id": None,
                    "away_team_id": None,
                    "home_club_id": None,
                    "away_club_id": None,
                    "home_score": None,
                    "away_score": None,
                    "match_status": None,
                    "match_date": None,
                    "scheduled_kickoff": None,
                }
                if match:
                    slot["home_team_name"] = (
                        match["home_team"]["name"]
                        if match.get("home_team")
                        else None
                    )
                    slot["away_team_name"] = (
                        match["away_team"]["name"]
                        if match.get("away_team")
                        else None
                    )
                    slot["home_team_id"] = (
                        match["home_team"]["id"]
                        if match.get("home_team")
                        else None
                    )
                    slot["away_team_id"] = (
                        match["away_team"]["id"]
                        if match.get("away_team")
                        else None
                    )
                    slot["home_club_id"] = (
                        match["home_team"].get("club_id")
                        if match.get("home_team")
                        else None
                    )
                    slot["away_club_id"] = (
                        match["away_team"].get("club_id")
                        if match.get("away_team")
                        else None
                    )
                    slot["home_score"] = match.get("home_score")
                    slot["away_score"] = match.get("away_score")
                    slot["match_status"] = match.get("match_status")
                    slot["match_date"] = match.get("match_date")
                    slot["scheduled_kickoff"] = match.get("scheduled_kickoff")
                slots.append(slot)

            return slots

        except Exception:
            logger.exception(
                "Error fetching playoff bracket",
                league_id=league_id,
                season_id=season_id,
                age_group_id=age_group_id,
            )
            return []

    # === Bracket Generation ===

    @invalidates_cache(PLAYOFF_CACHE_PATTERN, MATCHES_CACHE_PATTERN)
    def generate_bracket(
        self,
        league_id: int,
        season_id: int,
        age_group_id: int,
        standings_a: list[dict],
        standings_b: list[dict],
        division_a_id: int,
        division_b_id: int,
        start_date: str,
        tiers: list[dict],
    ) -> list[dict]:
        """Generate configurable multi-tier 8-team single elimination brackets.

        Creates bracket slots and QF matches for each configured tier.
        Each tier uses the same cross-division seeding pattern.

        Args:
            league_id: League ID
            season_id: Season ID
            age_group_id: Age group ID
            standings_a: Full standings from division A (sorted by rank)
            standings_b: Full standings from division B (sorted by rank)
            division_a_id: Division A ID (for team lookups)
            division_b_id: Division B ID (for team lookups)
            start_date: ISO date string for QF matches (e.g., "2026-02-15")
            tiers: List of tier configs, each with name, start_position, end_position

        Returns:
            List of created bracket slot dicts

        Raises:
            ValueError: If not enough teams for the configured tiers
        """
        # Determine required team count from tier configuration
        max_position = max(t["end_position"] for t in tiers)
        if len(standings_a) < max_position:
            raise ValueError(
                f"Division A needs at least {max_position} teams, has {len(standings_a)}"
            )
        if len(standings_b) < max_position:
            raise ValueError(
                f"Division B needs at least {max_position} teams, has {len(standings_b)}"
            )

        # Check for existing bracket
        existing = (
            self.client.table("playoff_bracket_slots")
            .select("id")
            .eq("league_id", league_id)
            .eq("season_id", season_id)
            .eq("age_group_id", age_group_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            raise ValueError("Bracket already exists for this league/season/age group")

        # Build name→team_id mapping from both divisions
        team_map = self._build_team_name_map(division_a_id, division_b_id)

        # Process each configured tier
        tier_names = []
        for tier_config in tiers:
            tier = tier_config["name"]
            tier_names.append(tier)
            start_pos = tier_config["start_position"] - 1  # Convert to 0-indexed
            end_pos = tier_config["end_position"]
            slice_a = standings_a[start_pos:end_pos]
            slice_b = standings_b[start_pos:end_pos]

            # Build seed→team mapping for this tier
            # A1=seed1, B1=seed2, A2=seed3, B2=seed4, A3=seed5, B3=seed6, A4=seed7, B4=seed8
            seed_teams = {}
            for i, standing in enumerate(slice_a):
                seed = (i * 2) + 1  # 1, 3, 5, 7
                name = standing["team"]
                if name not in team_map:
                    raise ValueError(f"Team '{name}' not found in division teams")
                seed_teams[seed] = {"name": name, "id": team_map[name]}

            for i, standing in enumerate(slice_b):
                seed = (i * 2) + 2  # 2, 4, 6, 8
                name = standing["team"]
                if name not in team_map:
                    raise ValueError(f"Team '{name}' not found in division teams")
                seed_teams[seed] = {"name": name, "id": team_map[name]}

            logger.info(
                "generating_playoff_bracket_tier",
                league_id=league_id,
                tier=tier,
                seed_teams={s: t["name"] for s, t in seed_teams.items()},
            )

            # Create QF slots and matches for this tier
            qf_slots = []
            for matchup in QF_MATCHUPS:
                home = seed_teams[matchup["home_seed"]]
                away = seed_teams[matchup["away_seed"]]

                # Create the match with configured start date
                match_data = {
                    "match_date": start_date,
                    "home_team_id": home["id"],
                    "away_team_id": away["id"],
                    "season_id": season_id,
                    "age_group_id": age_group_id,
                    "match_type_id": PLAYOFF_MATCH_TYPE_ID,
                    "match_status": "scheduled",
                    "source": "playoff-generator",
                }
                match_response = (
                    self.client.table("matches").insert(match_data).execute()
                )
                match_id = match_response.data[0]["id"]

                # Create the bracket slot
                slot_data = {
                    "league_id": league_id,
                    "season_id": season_id,
                    "age_group_id": age_group_id,
                    "bracket_tier": tier,
                    "round": "quarterfinal",
                    "bracket_position": matchup["position"],
                    "match_id": match_id,
                    "home_seed": matchup["home_seed"],
                    "away_seed": matchup["away_seed"],
                }
                slot_response = (
                    self.client.table("playoff_bracket_slots")
                    .insert(slot_data)
                    .execute()
                )
                qf_slots.append(slot_response.data[0])

            # Create SF slots (no matches yet — teams TBD)
            sf_slots = []
            # SF1: winner of QF1 vs winner of QF2
            sf1_data = {
                "league_id": league_id,
                "season_id": season_id,
                "age_group_id": age_group_id,
                "bracket_tier": tier,
                "round": "semifinal",
                "bracket_position": 1,
                "home_source_slot_id": qf_slots[0]["id"],
                "away_source_slot_id": qf_slots[1]["id"],
            }
            sf1_response = (
                self.client.table("playoff_bracket_slots")
                .insert(sf1_data)
                .execute()
            )
            sf_slots.append(sf1_response.data[0])

            # SF2: winner of QF3 vs winner of QF4
            sf2_data = {
                "league_id": league_id,
                "season_id": season_id,
                "age_group_id": age_group_id,
                "bracket_tier": tier,
                "round": "semifinal",
                "bracket_position": 2,
                "home_source_slot_id": qf_slots[2]["id"],
                "away_source_slot_id": qf_slots[3]["id"],
            }
            sf2_response = (
                self.client.table("playoff_bracket_slots")
                .insert(sf2_data)
                .execute()
            )
            sf_slots.append(sf2_response.data[0])

            # Create Final slot (no match yet)
            final_data = {
                "league_id": league_id,
                "season_id": season_id,
                "age_group_id": age_group_id,
                "bracket_tier": tier,
                "round": "final",
                "bracket_position": 1,
                "home_source_slot_id": sf_slots[0]["id"],
                "away_source_slot_id": sf_slots[1]["id"],
            }
            self.client.table("playoff_bracket_slots").insert(final_data).execute()

        logger.info(
            "playoff_bracket_generated",
            league_id=league_id,
            season_id=season_id,
            age_group_id=age_group_id,
            tiers=tier_names,
        )

        # Return the full bracket
        return self.get_bracket.__wrapped__(self, league_id, season_id, age_group_id)

    # === Winner Advancement ===

    @invalidates_cache(PLAYOFF_CACHE_PATTERN, MATCHES_CACHE_PATTERN)
    def advance_winner(self, slot_id: int) -> dict | None:
        """Advance the winner of a completed slot to the next round.

        Determines the winner from the linked match scores, finds the
        next-round slot where this slot feeds into, and updates it.
        When both feeder slots for a next-round slot are complete,
        creates the match for that round.

        Args:
            slot_id: The bracket slot ID whose winner should advance

        Returns:
            The updated next-round slot dict, or None on error

        Raises:
            ValueError: If match not completed, scores tied, or no next round
        """
        # Get the completed slot
        slot_response = (
            self.client.table("playoff_bracket_slots")
            .select("*, match:matches(id, home_team_id, away_team_id, home_score, away_score, match_status)")
            .eq("id", slot_id)
            .execute()
        )
        if not slot_response.data:
            raise ValueError(f"Slot {slot_id} not found")

        slot = slot_response.data[0]
        match = slot.get("match")
        if not match:
            raise ValueError(f"Slot {slot_id} has no linked match")
        if match.get("match_status") not in ("completed", "forfeit"):
            raise ValueError(f"Match for slot {slot_id} is not completed")
        if match["home_score"] is None or match["away_score"] is None:
            raise ValueError(f"Match for slot {slot_id} has no scores")
        if match["home_score"] == match["away_score"]:
            raise ValueError(
                f"Match for slot {slot_id} is tied — admin must resolve before advancing"
            )

        # Determine winner
        winner_team_id = (
            match["home_team_id"]
            if match["home_score"] > match["away_score"]
            else match["away_team_id"]
        )

        # Find the next-round slot that this slot feeds into
        next_slot_response = (
            self.client.table("playoff_bracket_slots")
            .select("*")
            .or_(
                f"home_source_slot_id.eq.{slot_id},"
                f"away_source_slot_id.eq.{slot_id}"
            )
            .execute()
        )
        if not next_slot_response.data:
            raise ValueError(
                f"No next-round slot found for slot {slot_id} — may be the final"
            )

        next_slot = next_slot_response.data[0]

        # Check if both feeder slots are now complete
        other_source_slot_id = (
            next_slot["away_source_slot_id"]
            if next_slot["home_source_slot_id"] == slot_id
            else next_slot["home_source_slot_id"]
        )

        other_winner_team_id = None
        if other_source_slot_id:
            other_slot_response = (
                self.client.table("playoff_bracket_slots")
                .select("match:matches(home_team_id, away_team_id, home_score, away_score, match_status)")
                .eq("id", other_source_slot_id)
                .execute()
            )
            if other_slot_response.data:
                other_match = other_slot_response.data[0].get("match")
                if other_match and other_match.get("match_status") in ("completed", "forfeit"):
                    if (
                        other_match["home_score"] is not None
                        and other_match["away_score"] is not None
                        and other_match["home_score"] != other_match["away_score"]
                    ):
                        if other_match["home_score"] > other_match["away_score"]:
                            other_winner_team_id = other_match["home_team_id"]
                        else:
                            other_winner_team_id = other_match["away_team_id"]

        # If both feeders are complete, create the next-round match
        if other_winner_team_id and not next_slot.get("match_id"):
            # Determine home/away based on which source slot they came from
            if next_slot["home_source_slot_id"] == slot_id:
                home_team_id = winner_team_id
                away_team_id = other_winner_team_id
            else:
                home_team_id = other_winner_team_id
                away_team_id = winner_team_id

            default_date = (date.today() + timedelta(days=5)).isoformat()
            match_data = {
                "match_date": default_date,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "season_id": next_slot["season_id"],
                "age_group_id": next_slot["age_group_id"],
                "match_type_id": PLAYOFF_MATCH_TYPE_ID,
                "match_status": "scheduled",
                "source": "playoff-generator",
            }
            match_response = (
                self.client.table("matches").insert(match_data).execute()
            )
            new_match_id = match_response.data[0]["id"]

            # Link match to the bracket slot
            self.client.table("playoff_bracket_slots").update(
                {"match_id": new_match_id}
            ).eq("id", next_slot["id"]).execute()

            logger.info(
                "playoff_next_round_match_created",
                next_slot_id=next_slot["id"],
                round=next_slot["round"],
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                match_id=new_match_id,
            )

        logger.info(
            "playoff_winner_advanced",
            from_slot_id=slot_id,
            to_slot_id=next_slot["id"],
            winner_team_id=winner_team_id,
        )

        # Return the updated next-round slot
        updated = (
            self.client.table("playoff_bracket_slots")
            .select("*")
            .eq("id", next_slot["id"])
            .execute()
        )
        return updated.data[0] if updated.data else None

    # === Forfeit ===

    @invalidates_cache(PLAYOFF_CACHE_PATTERN, MATCHES_CACHE_PATTERN)
    def forfeit_match(self, slot_id: int, forfeit_team_id: int) -> dict | None:
        """Declare a forfeit on a playoff match.

        The forfeiting team loses 0-3, the match is marked as 'forfeit',
        and the winning team automatically advances in the bracket.

        Args:
            slot_id: The bracket slot ID
            forfeit_team_id: The team ID that is forfeiting

        Returns:
            The updated next-round slot dict from advance_winner, or None if final

        Raises:
            ValueError: If match not found, wrong status, or team not a participant
        """
        # Get the bracket slot with linked match
        slot_response = (
            self.client.table("playoff_bracket_slots")
            .select(
                "*, match:matches(id, home_team_id, away_team_id, "
                "home_score, away_score, match_status)"
            )
            .eq("id", slot_id)
            .execute()
        )
        if not slot_response.data:
            raise ValueError(f"Slot {slot_id} not found")

        slot = slot_response.data[0]
        match = slot.get("match")
        if not match:
            raise ValueError(f"Slot {slot_id} has no linked match")
        if match.get("match_status") not in ("scheduled", "live"):
            raise ValueError(
                f"Match for slot {slot_id} cannot be forfeited "
                f"(status: {match.get('match_status')})"
            )

        home_team_id = match["home_team_id"]
        away_team_id = match["away_team_id"]

        if forfeit_team_id not in (home_team_id, away_team_id):
            raise ValueError(
                f"Team {forfeit_team_id} is not a participant in this match"
            )

        # Set scores: non-forfeiting team gets 3, forfeiting team gets 0
        if forfeit_team_id == home_team_id:
            home_score = 0
            away_score = 3
        else:
            home_score = 3
            away_score = 0

        # Update the match
        self.client.table("matches").update(
            {
                "match_status": "forfeit",
                "home_score": home_score,
                "away_score": away_score,
                "forfeit_team_id": forfeit_team_id,
            }
        ).eq("id", match["id"]).execute()

        logger.info(
            "playoff_match_forfeited",
            slot_id=slot_id,
            match_id=match["id"],
            forfeit_team_id=forfeit_team_id,
        )

        # Advance the winner to the next round (reuse existing logic)
        if slot["round"] != "final":
            return self.advance_winner(slot_id)

        return None

    # === Bracket Deletion ===

    @invalidates_cache(PLAYOFF_CACHE_PATTERN, MATCHES_CACHE_PATTERN)
    def delete_bracket(
        self, league_id: int, season_id: int, age_group_id: int
    ) -> int:
        """Delete an entire playoff bracket and its associated matches.

        Deletes in order: unlink matches from slots, delete slots
        (final first due to self-referencing FKs), then delete orphaned
        playoff matches.

        Returns:
            Number of slots deleted
        """
        try:
            # Get all slots and their match IDs
            slots_response = (
                self.client.table("playoff_bracket_slots")
                .select("id, match_id, round")
                .eq("league_id", league_id)
                .eq("season_id", season_id)
                .eq("age_group_id", age_group_id)
                .execute()
            )

            if not slots_response.data:
                return 0

            match_ids = [
                s["match_id"] for s in slots_response.data if s["match_id"]
            ]

            # Delete slots in reverse round order to respect self-referencing FKs
            round_order = ["final", "semifinal", "quarterfinal"]
            total_deleted = 0
            for round_name in round_order:
                round_slots = [
                    s for s in slots_response.data if s["round"] == round_name
                ]
                for slot in round_slots:
                    self.client.table("playoff_bracket_slots").delete().eq(
                        "id", slot["id"]
                    ).execute()
                    total_deleted += 1

            # Delete associated playoff matches
            for match_id in match_ids:
                self.client.table("matches").delete().eq("id", match_id).execute()

            logger.info(
                "playoff_bracket_deleted",
                league_id=league_id,
                season_id=season_id,
                age_group_id=age_group_id,
                slots_deleted=total_deleted,
                matches_deleted=len(match_ids),
            )

            return total_deleted

        except Exception:
            logger.exception(
                "Error deleting playoff bracket",
                league_id=league_id,
                season_id=season_id,
                age_group_id=age_group_id,
            )
            raise

    # === Internal Helpers ===

    def _build_team_name_map(
        self, division_a_id: int, division_b_id: int
    ) -> dict[str, int]:
        """Build a team name → team ID mapping from both divisions.

        Queries team_mappings to find teams assigned to either division.
        """
        team_ids = set()
        for div_id in [division_a_id, division_b_id]:
            response = (
                self.client.table("team_mappings")
                .select("team_id")
                .eq("division_id", div_id)
                .execute()
            )
            for row in response.data:
                team_ids.add(row["team_id"])

        if not team_ids:
            return {}

        teams_response = (
            self.client.table("teams")
            .select("id, name")
            .in_("id", list(team_ids))
            .execute()
        )

        return {team["name"]: team["id"] for team in teams_response.data}

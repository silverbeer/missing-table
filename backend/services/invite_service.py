"""
Invite Service for Missing Table
Handles invite code generation, validation, and management
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from dao.base_dao import clear_cache
from supabase import Client

logger = logging.getLogger(__name__)


class InviteService:
    """Service for managing invitations"""

    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        # Characters for invite codes (avoiding ambiguous characters)
        self.code_chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    def generate_invite_code(self) -> str:
        """Generate a unique 12-character invite code"""
        max_attempts = 100

        for _ in range(max_attempts):
            # Generate random code
            code = "".join(secrets.choice(self.code_chars) for _ in range(12))

            # Check if code already exists
            response = self.supabase.table("invitations").select("id").eq("invite_code", code).execute()

            if not response.data:
                return code

        raise Exception("Could not generate unique invite code after 100 attempts")

    def _get_current_season_id(self) -> int | None:
        """Current season by today's date, or None."""
        try:
            from datetime import date

            today = date.today().isoformat()
            response = (
                self.supabase.table("seasons")
                .select("id")
                .lte("start_date", today)
                .gte("end_date", today)
                .limit(1)
                .execute()
            )
            return response.data[0]["id"] if response.data else None
        except Exception as e:
            logger.error(f"Error resolving current season: {e}")
            return None

    def _find_roster_spot(
        self,
        team_id: int,
        season_id: int,
        jersey_number: int,
        age_group_id: int | None,
    ) -> dict | None:
        """Find the roster row a jersey-number invite would claim.

        Scoped to the age group to match the players unique constraint
        (team, season, age_group, jersey) - umbrella teams can field the same
        number in several squads. age_group_id=None matches NULL rows only.
        """
        try:
            query = (
                self.supabase.table("players")
                .select("id, user_profile_id, first_name, last_name")
                .eq("team_id", team_id)
                .eq("season_id", season_id)
                .eq("jersey_number", jersey_number)
            )
            if age_group_id is None:
                query = query.is_("age_group_id", "null")
            else:
                query = query.eq("age_group_id", age_group_id)
            response = query.limit(1).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error looking up roster spot: {e}")
            return None

    def create_invitation(
        self,
        invited_by_user_id: str,
        invite_type: str,
        team_id: int | None = None,
        age_group_id: int | None = None,
        club_id: int | None = None,
        email: str | None = None,
        player_id: int | None = None,
        jersey_number: int | None = None,
        expires_in_days: int = 7,
        note: str | None = None,
        season_id: int | None = None,
    ) -> dict:
        """
        Create a new invitation

        Args:
            invited_by_user_id: ID of the user creating the invite
            invite_type: Type of invite ('club_manager', 'club_fan', 'team_manager', 'team_player', 'team_fan')
            team_id: ID of the team (required for team-level invite types)
            age_group_id: ID of the age group (required for team-level invite types)
            club_id: ID of the club (required for club_manager and club_fan invite types)
            email: Optional email to pre-fill during registration
            player_id: Optional roster entry ID (for team_player invites - links account to existing roster)
            jersey_number: Optional jersey number (for team_player invites - claims roster on redemption)
            expires_in_days: Number of days until invite expires
            season_id: Season the invite applies to (team_player roster claims).
                Defaults to the current season by date, stored on the invite so
                redemption doesn't guess.

        Returns:
            Created invitation record

        Raises:
            ValueError: On invalid parameters, including a team_player
                jersey-number invite with no matching unclaimed roster spot -
                caught at creation so the admin fixes it, not the registrant.
        """
        try:
            # Validate parameters based on invite type
            if invite_type in ("club_manager", "club_fan"):
                if not club_id:
                    raise ValueError(f"club_id is required for {invite_type} invites")
                # Club-level invites don't need team_id or age_group_id
                team_id = None
                age_group_id = None
                player_id = None  # No roster linking for club-level invites
                jersey_number = None
                season_id = None
            else:
                if not team_id:
                    raise ValueError("team_id is required for team-level invites")
                if not age_group_id:
                    raise ValueError("age_group_id is required for team-level invites")
                # Derive club_id from the team's parent club
                club_id = self._get_team_club_id(team_id)

            if invite_type == "team_player":
                # Pin the season at creation time (SB-287).
                if season_id is None:
                    season_id = self._get_current_season_id()
                    if season_id is None:
                        raise ValueError("No current season found; pass season_id explicitly")

                # A jersey-number invite must point at an existing, unclaimed
                # roster spot - blocking here beats blocking the kid at signup.
                if jersey_number and not player_id:
                    spot = self._find_roster_spot(team_id, season_id, jersey_number, age_group_id)
                    if spot is None:
                        raise ValueError(
                            f"No roster spot with jersey #{jersey_number} for this "
                            f"team/season/age group. Add the player to the roster first."
                        )
                    if spot.get("user_profile_id"):
                        raise ValueError(
                            f"Jersey #{jersey_number} is already claimed by another account."
                        )
                    player_id = spot["id"]
                elif player_id:
                    # Direct roster-entry invite: verify it exists and is unclaimed.
                    check = (
                        self.supabase.table("players")
                        .select("id, user_profile_id, jersey_number")
                        .eq("id", player_id)
                        .limit(1)
                        .execute()
                    )
                    if not check.data:
                        raise ValueError("That roster entry no longer exists.")
                    if check.data[0].get("user_profile_id"):
                        raise ValueError(
                            "That roster spot is already claimed by another account."
                        )
                    jersey_number = jersey_number or check.data[0].get("jersey_number")
            else:
                season_id = None

            # Generate unique invite code
            invite_code = self.generate_invite_code()

            # Calculate expiration date
            expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)

            # Create invitation record
            invitation_data = {
                "invite_code": invite_code,
                "invited_by_user_id": invited_by_user_id,
                "invite_type": invite_type,
                "team_id": team_id,
                "age_group_id": age_group_id,
                "club_id": club_id,
                "email": email,
                "player_id": player_id,
                "jersey_number": jersey_number,
                "season_id": season_id,
                "status": "pending",
                "expires_at": expires_at.isoformat(),
                "note": note,
            }

            response = self.supabase.table("invitations").insert(invitation_data).execute()

            if not response.data:
                raise Exception("Failed to create invitation")

            log_msg = f"Created {invite_type} invitation: {invite_code}"
            if player_id:
                log_msg += f" linked to player {player_id}"
            elif jersey_number:
                log_msg += f" with jersey #{jersey_number}"
            logger.info(log_msg)

            # Fire the invitation email if an address was provided. Email
            # failures are logged but never fail the invitation create —
            # admin can always copy the code manually as a fallback.
            if email:
                try:
                    from services.email_service import EmailService

                    EmailService().send_invitation(
                        to_email=email,
                        invite_code=invite_code,
                        invite_type=invite_type,
                        expires_at=expires_at.isoformat(),
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to send invitation email to {email}: {e}"
                    )

            return response.data[0]

        except Exception as e:
            logger.error(f"Error creating invitation: {e}")
            raise

    def validate_invite_code(self, code: str) -> dict | None:
        """
        Validate an invite code

        Args:
            code: The invite code to validate

        Returns:
            Invitation details if valid, None otherwise
        """
        try:
            logger.info(f"Validating invite code: {code}")

            # Get invitation by code with related data including player roster entry
            response = (
                self.supabase.table("invitations")
                .select(
                    "*, teams(name), age_groups(name), clubs(name), players(id, jersey_number, first_name, last_name)"
                )
                .eq("invite_code", code)
                .execute()
            )

            if not response.data or len(response.data) == 0:
                logger.warning(f"Invite code {code} not found in database")
                return None

            invitation = response.data[0]
            logger.info(f"Found invitation: status={invitation['status']}, expires_at={invitation['expires_at']}")

            # Check if already used
            if invitation["status"] != "pending":
                logger.warning(f"Invite code {code} has status '{invitation['status']}' (not pending)")
                return None

            # Check if expired
            expires_at_str = invitation["expires_at"]
            if expires_at_str.endswith("Z"):
                expires_at_str = expires_at_str.replace("Z", "+00:00")
            expires_at = datetime.fromisoformat(expires_at_str)

            # Make current time timezone-aware for comparison
            current_time = datetime.now(UTC)

            is_expired = expires_at < current_time
            logger.info(f"Invite code {code}: expires_at={expires_at}, current={current_time}, is_expired={is_expired}")

            if expires_at < current_time:
                # Update status to expired
                self.supabase.table("invitations").update({"status": "expired"}).eq("id", invitation["id"]).execute()
                logger.warning(f"Invite code {code} expired at {expires_at}")
                return None

            # Build player info if linked to roster
            player_info = None
            if invitation.get("players"):
                player = invitation["players"]
                player_info = {
                    "id": player["id"],
                    "jersey_number": player["jersey_number"],
                    "first_name": player.get("first_name"),
                    "last_name": player.get("last_name"),
                }

            logger.info(f"Invite code {code} is valid!")
            result = {
                "valid": True,
                "id": invitation["id"],
                "invite_type": invitation["invite_type"],
                "team_id": invitation["team_id"],
                "team_name": invitation["teams"]["name"] if invitation.get("teams") else None,
                "age_group_id": invitation["age_group_id"],
                "age_group_name": invitation["age_groups"]["name"] if invitation.get("age_groups") else None,
                "club_id": invitation.get("club_id"),
                "club_name": invitation["clubs"]["name"] if invitation.get("clubs") else None,
                "email": invitation["email"],
                "invited_by_user_id": invitation.get("invited_by_user_id"),
                "player_id": invitation.get("player_id"),
                "jersey_number": invitation.get("jersey_number"),
                "season_id": invitation.get("season_id"),
                "player": player_info,
            }

            # Roster-claim preflight for team_player invites (SB-287): the
            # signup flow blocks registration when the spot can't be claimed.
            if invitation["invite_type"] == "team_player":
                claimable, reason = self.check_claimable(result)
                result["claimable"] = claimable
                result["claim_reason"] = reason

            return result

        except Exception as e:
            logger.error(f"Error validating invite code {code}: {e}", exc_info=True)
            return None

    def check_claimable(self, invitation: dict) -> tuple[bool, str | None]:
        """Can this team_player invite's roster spot still be claimed?

        Called BEFORE the auth user is created at signup, so a dead invite
        never produces an orphan account. Returns (claimable, reason).
        Invites with no roster hook (no player_id, no jersey_number) are
        trivially claimable.
        """
        if invitation.get("invite_type") != "team_player":
            return True, None

        player_id = invitation.get("player_id")
        jersey_number = invitation.get("jersey_number")

        if player_id:
            try:
                response = (
                    self.supabase.table("players")
                    .select("id, user_profile_id")
                    .eq("id", player_id)
                    .limit(1)
                    .execute()
                )
            except Exception as e:
                logger.error(f"Error checking roster spot {player_id}: {e}")
                return False, "Could not verify the roster spot. Please try again."
            if not response.data:
                return False, (
                    "The roster spot for this invite no longer exists. "
                    "Ask your team manager for a new invite."
                )
            if response.data[0].get("user_profile_id"):
                return False, (
                    "This roster spot has already been claimed by another account. "
                    "Ask your team manager for a new invite."
                )
            return True, None

        if jersey_number:
            # Legacy invite (pre-SB-287) carrying only a jersey number.
            season_id = invitation.get("season_id") or self._get_current_season_id()
            if season_id is None:
                return False, "No current season found. Contact your team manager."
            spot = self._find_roster_spot(
                invitation["team_id"], season_id, jersey_number, invitation.get("age_group_id")
            )
            if spot is None:
                return False, (
                    f"No roster spot with jersey #{jersey_number} exists for this team. "
                    "Ask your team manager to add you to the roster first."
                )
            if spot.get("user_profile_id"):
                return False, (
                    f"Jersey #{jersey_number} has already been claimed by another account. "
                    "Ask your team manager for a new invite."
                )
            return True, None

        return True, None

    def redeem_invitation(self, code: str, user_id: str) -> bool:
        """
        Redeem an invitation code

        Args:
            code: The invite code to redeem
            user_id: ID of the user redeeming the code

        Returns:
            True if successful, False otherwise
        """
        try:
            # First validate the code
            invitation = self.validate_invite_code(code)
            if not invitation:
                return False

            # Update invitation status
            response = (
                self.supabase.table("invitations")
                .update(
                    {
                        "status": "used",
                        "used_at": datetime.now(UTC).isoformat(),
                        "used_by_user_id": user_id,
                    }
                )
                .eq("invite_code", code)
                .execute()
            )

            if response.data:
                logger.info(f"Invitation {code} redeemed by user {user_id}")

                # Create team_manager_assignments entry for team_manager invites
                # This enables the team manager to create player/fan invites for their team
                if invitation.get("invite_type") == "team_manager":
                    self._create_team_manager_assignment(
                        user_id=user_id,
                        team_id=invitation.get("team_id"),
                        age_group_id=invitation.get("age_group_id"),
                        assigned_by_user_id=invitation.get("invited_by_user_id"),
                    )

                # Handle player roster linking for team_player invites
                if invitation.get("invite_type") == "team_player":
                    logger.info(
                        f"Processing team_player invite: "
                        f"player_id={invitation.get('player_id')}, "
                        f"jersey={invitation.get('jersey_number')}, "
                        f"team={invitation.get('team_id')}, "
                        f"age_group={invitation.get('age_group_id')}"
                    )
                    if invitation.get("player_id"):
                        # Link user to existing roster entry (also creates player_team_history)
                        self._link_user_to_roster_entry(
                            user_id=user_id,
                            player_id=invitation.get("player_id"),
                            team_id=invitation.get("team_id"),
                            age_group_id=invitation.get("age_group_id"),
                        )
                    elif invitation.get("jersey_number"):
                        # Claim the existing roster entry for this jersey
                        # number (SB-287: no auto-create - the spot must exist,
                        # which check_claimable verified before signup).
                        jersey = invitation.get("jersey_number")
                        logger.info(f"Claiming roster spot for jersey #{jersey}")
                        claimed = self._claim_roster_entry(
                            user_id=user_id,
                            team_id=invitation.get("team_id"),
                            jersey_number=jersey,
                            age_group_id=invitation.get("age_group_id"),
                            season_id=invitation.get("season_id"),
                        )
                        if not claimed:
                            # Race: spot vanished/claimed between the signup
                            # pre-check and redemption. The auth user exists
                            # with its role but no roster link - loud log so
                            # an admin can reconcile.
                            logger.error(
                                f"ROSTER CLAIM FAILED after signup: user {user_id}, "
                                f"invite {code}, jersey #{jersey}, "
                                f"team {invitation.get('team_id')} - manual link needed"
                            )
                    else:
                        logger.info("No player_id or jersey_number on invite - skipping roster")

                return True

            return False

        except Exception as e:
            logger.error(f"Error redeeming invitation {code}: {e}")
            return False

    def _get_team_club_id(self, team_id: int) -> int | None:
        """Look up a team's parent club_id."""
        try:
            response = self.supabase.table("teams").select("club_id").eq("id", team_id).execute()
            if response.data:
                return response.data[0].get("club_id")
        except Exception as e:
            logger.warning(f"Could not look up club_id for team {team_id}: {e}")
        return None

    def _link_user_to_roster_entry(
        self,
        user_id: str,
        player_id: int,
        team_id: int | None = None,
        season_id: int | None = None,
        age_group_id: int | None = None,
        league_id: int | None = None,
        division_id: int | None = None,
        jersey_number: int | None = None,
    ) -> bool:
        """
        Link a user account to a roster entry in the players table.
        Also creates a player_team_history entry for the UI roster view.

        Called when a player accepts an invitation that was tied to a roster entry.

        Args:
            user_id: The user ID to link
            player_id: The roster entry ID to link to
            team_id: Team ID (optional, fetched from roster if not provided)
            season_id: Season ID (optional, fetched from roster if not provided)
            age_group_id: Age group ID from the invite
            league_id: League ID (optional, fetched from team if not provided)
            division_id: Division ID (optional, fetched from team if not provided)
            jersey_number: Jersey number (optional, fetched from roster if not provided)

        Returns:
            True if successful, False otherwise
        """
        try:
            # If we don't have the roster details, fetch them
            if team_id is None or season_id is None or jersey_number is None:
                roster_response = (
                    self.supabase.table("players")
                    .select("team_id, season_id, jersey_number")
                    .eq("id", player_id)
                    .limit(1)
                    .execute()
                )

                if roster_response.data:
                    roster = roster_response.data[0]
                    team_id = team_id or roster.get("team_id")
                    season_id = season_id or roster.get("season_id")
                    jersey_number = jersey_number or roster.get("jersey_number")

            # If we don't have league/division, fetch from team
            if team_id and (league_id is None or division_id is None):
                team_response = (
                    self.supabase.table("teams").select("league_id, division_id").eq("id", team_id).limit(1).execute()
                )

                if team_response.data:
                    team = team_response.data[0]
                    league_id = league_id or team.get("league_id")
                    division_id = division_id or team.get("division_id")

            # Get age_group_id from team_mappings if not provided by the invite
            if team_id and age_group_id is None:
                mapping_response = (
                    self.supabase.table("team_mappings")
                    .select("age_group_id")
                    .eq("team_id", team_id)
                    .limit(1)
                    .execute()
                )
                if mapping_response.data:
                    age_group_id = mapping_response.data[0]["age_group_id"]

            # Update the players table to link user_profile_id. The
            # user_profile_id IS NULL guard makes the claim atomic: if another
            # account claimed the spot since the signup pre-check, zero rows
            # update and we fail instead of stealing the link.
            response = (
                self.supabase.table("players")
                .update({"user_profile_id": user_id})
                .eq("id", player_id)
                .is_("user_profile_id", "null")
                .execute()
            )

            if response.data:
                logger.info(f"Linked user {user_id} to roster entry {player_id}")

                # Also create player_team_history entry for UI roster view
                if team_id and season_id:
                    self._create_player_team_history(
                        user_id=user_id,
                        team_id=team_id,
                        season_id=season_id,
                        age_group_id=age_group_id,
                        league_id=league_id,
                        division_id=division_id,
                        jersey_number=jersey_number,
                    )

                # Invalidate caches
                clear_cache("mt:dao:roster:*")
                clear_cache("mt:dao:players:*")
                return True

            logger.warning(f"Failed to link user {user_id} to roster entry {player_id}")
            return False

        except Exception as e:
            logger.error(f"Error linking user to roster entry: {e}")
            return False

    def _claim_roster_entry(
        self,
        user_id: str,
        team_id: int,
        jersey_number: int,
        age_group_id: int | None = None,
        season_id: int | None = None,
    ) -> bool:
        """
        Claim the existing unclaimed roster entry matching the invite's
        (team, season, age group, jersey). NO auto-create (SB-287): if the
        spot doesn't exist the claim fails - creation-time validation and the
        signup pre-check should have prevented reaching here.

        Args:
            user_id: The user ID to link
            team_id: The team ID for the roster entry
            jersey_number: The jersey number for the roster entry
            age_group_id: The age group ID from the invite
            season_id: Season from the invitation; falls back to
                current-by-date only for legacy invites without one

        Returns:
            True if successful, False otherwise
        """
        try:
            if season_id is None:
                season_id = self._get_current_season_id()
                if season_id is None:
                    logger.error("No current season found - cannot claim roster entry")
                    return False

            spot = self._find_roster_spot(team_id, season_id, jersey_number, age_group_id)
            if spot is None:
                logger.error(
                    f"No roster spot for jersey #{jersey_number} "
                    f"(team {team_id}, season {season_id}, age group {age_group_id})"
                )
                return False
            if spot.get("user_profile_id"):
                logger.warning(
                    f"Roster entry {spot['id']} (jersey #{jersey_number}) "
                    f"already linked to user {spot['user_profile_id']}"
                )
                return False

            # Get team details for league_id and division_id
            team_response = (
                self.supabase.table("teams").select("league_id, division_id").eq("id", team_id).limit(1).execute()
            )
            league_id = None
            division_id = None
            if team_response.data:
                league_id = team_response.data[0].get("league_id")
                division_id = team_response.data[0].get("division_id")

            # Link (atomic: guarded on user_profile_id IS NULL inside)
            return self._link_user_to_roster_entry(
                user_id=user_id,
                player_id=spot["id"],
                team_id=team_id,
                season_id=season_id,
                age_group_id=age_group_id,
                league_id=league_id,
                division_id=division_id,
                jersey_number=jersey_number,
            )

        except Exception as e:
            logger.error(f"Error claiming roster entry: {e}")
            return False

    def _create_player_team_history(
        self,
        user_id: str,
        team_id: int,
        season_id: int,
        age_group_id: int | None = None,
        league_id: int | None = None,
        division_id: int | None = None,
        jersey_number: int | None = None,
        positions: list[str] | None = None,
    ) -> bool:
        """
        Create a player_team_history entry for the UI roster view.

        This is the primary table used by the UI to display team rosters.
        Called when a player accepts an invitation.

        Args:
            user_id: The user ID (player_id in the table)
            team_id: Team ID
            season_id: Season ID
            age_group_id: Age group ID
            league_id: League ID
            division_id: Division ID
            jersey_number: Jersey number
            positions: List of position codes (e.g., ['CM', 'ST'] - validated
                against constants.positions.VALID_POSITIONS)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Direct DB write bypasses the Pydantic models - validate here
            # so invalid/legacy codes can't re-enter the DB (SB-293).
            if positions:
                from constants.positions import normalize_positions

                try:
                    positions = normalize_positions(positions)
                except ValueError as e:
                    logger.warning(f"Dropping invalid positions on history insert: {e}")
                    positions = None
            # Check if entry already exists for this player/team/season
            existing = (
                self.supabase.table("player_team_history")
                .select("id")
                .eq("player_id", user_id)
                .eq("team_id", team_id)
                .eq("season_id", season_id)
                .limit(1)
                .execute()
            )

            if existing.data:
                logger.info(
                    f"player_team_history entry already exists for user {user_id}, team {team_id}, season {season_id}"
                )
                return True

            # Create new entry
            history_data = {
                "player_id": user_id,
                "team_id": team_id,
                "season_id": season_id,
                "is_current": True,
            }

            if age_group_id is not None:
                history_data["age_group_id"] = age_group_id
            if league_id is not None:
                history_data["league_id"] = league_id
            if division_id is not None:
                history_data["division_id"] = division_id
            if jersey_number is not None:
                history_data["jersey_number"] = jersey_number
            if positions:
                history_data["positions"] = positions

            response = self.supabase.table("player_team_history").insert(history_data).execute()

            if response.data:
                history_id = response.data[0]["id"]
                logger.info(
                    f"Created player_team_history entry {history_id} for user {user_id} "
                    f"on team {team_id}, season {season_id}, jersey #{jersey_number}"
                )
                return True

            logger.warning(f"Failed to create player_team_history for user {user_id}")
            return False

        except Exception as e:
            logger.error(f"Error creating player_team_history: {e}")
            return False

    def _create_team_manager_assignment(
        self, user_id: str, team_id: int, age_group_id: int, assigned_by_user_id: str
    ) -> bool:
        """
        Create a team_manager_assignments entry to grant team management permissions.

        Args:
            user_id: The user being granted management rights
            team_id: The team they can manage
            age_group_id: The age group (not stored - table doesn't have this column)
            assigned_by_user_id: The user who created the invite (not stored)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if assignment already exists (table has unique constraint on user_id, team_id)
            existing = (
                self.supabase.table("team_manager_assignments")
                .select("id")
                .eq("user_id", user_id)
                .eq("team_id", team_id)
                .execute()
            )

            if existing.data:
                logger.info(f"Team manager assignment already exists for user {user_id}, team {team_id}")
                return True

            # Create new assignment (table schema: id, user_id, team_id, created_at)
            response = (
                self.supabase.table("team_manager_assignments")
                .insert(
                    {
                        "user_id": user_id,
                        "team_id": team_id,
                    }
                )
                .execute()
            )

            if response.data:
                logger.info(f"Created team manager assignment: user {user_id} -> team {team_id}")
                return True

            logger.warning(f"Failed to create team manager assignment for user {user_id}")
            return False

        except Exception as e:
            logger.error(f"Error creating team manager assignment: {e}")
            return False

    def get_user_invitations(self, user_id: str) -> list[dict]:
        """
        Get all invitations created by a user

        Args:
            user_id: ID of the user

        Returns:
            List of invitations, with used_by_user profile info merged in for used invites
        """
        try:
            response = (
                self.supabase.table("invitations")
                .select("*, teams(name), age_groups(name), clubs(name)")
                .eq("invited_by_user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )

            invitations = response.data if response.data else []

            # Fetch user profiles for any "used" invites so we can show who redeemed them
            used_user_ids = list({
                inv["used_by_user_id"]
                for inv in invitations
                if inv.get("used_by_user_id")
            })

            if used_user_ids:
                profiles_response = (
                    self.supabase.table("user_profiles")
                    .select("id, username, display_name")
                    .in_("id", used_user_ids)
                    .execute()
                )
                profiles_by_id = {p["id"]: p for p in (profiles_response.data or [])}

                for inv in invitations:
                    uid = inv.get("used_by_user_id")
                    inv["used_by_user"] = profiles_by_id.get(uid) if uid else None

            return invitations

        except Exception as e:
            logger.error(f"Error getting user invitations: {e}")
            return []

    def cancel_invitation(self, invite_id: str, user_id: str) -> bool:
        """
        Cancel a pending invitation

        Args:
            invite_id: ID of the invitation to cancel
            user_id: ID of the user cancelling (must be creator or admin)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if user can cancel this invitation
            response = (
                self.supabase.table("invitations")
                .select("invited_by_user_id, status")
                .eq("id", invite_id)
                .single()
                .execute()
            )

            if not response.data:
                return False

            invitation = response.data

            # Only pending invitations can be cancelled
            if invitation["status"] != "pending":
                return False

            # Update status to expired
            response = self.supabase.table("invitations").update({"status": "expired"}).eq("id", invite_id).execute()

            if response.data:
                logger.info(f"Invitation {invite_id} cancelled by user {user_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error cancelling invitation {invite_id}: {e}")
            return False

    def expire_old_invitations(self) -> int:
        """
        Expire all old pending invitations

        Returns:
            Number of invitations expired
        """
        try:
            # Get all pending invitations that have expired
            response = (
                self.supabase.table("invitations")
                .select("id")
                .eq("status", "pending")
                .lt("expires_at", datetime.now(UTC).isoformat())
                .execute()
            )

            if not response.data:
                return 0

            # Update all to expired
            expired_ids = [inv["id"] for inv in response.data]

            self.supabase.table("invitations").update({"status": "expired"}).in_("id", expired_ids).execute()

            logger.info(f"Expired {len(expired_ids)} old invitations")
            return len(expired_ids)

        except Exception as e:
            logger.error(f"Error expiring old invitations: {e}")
            return 0

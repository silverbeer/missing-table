"""
Invite Service for Missing Table
Handles invite code generation, validation, and management
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from supabase import Client
import logging

logger = logging.getLogger(__name__)

class InviteService:
    """Service for managing invitations"""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        # Characters for invite codes (avoiding ambiguous characters)
        self.code_chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    
    def generate_invite_code(self) -> str:
        """Generate a unique 12-character invite code"""
        max_attempts = 100
        
        for _ in range(max_attempts):
            # Generate random code
            code = ''.join(secrets.choice(self.code_chars) for _ in range(12))
            
            # Check if code already exists
            response = self.supabase.table('invitations').select('id').eq('invite_code', code).execute()
            
            if not response.data:
                return code
        
        raise Exception("Could not generate unique invite code after 100 attempts")
    
    def create_invitation(
        self,
        invited_by_user_id: str,
        invite_type: str,
        team_id: Optional[int] = None,
        age_group_id: Optional[int] = None,
        club_id: Optional[int] = None,
        email: Optional[str] = None,
        expires_in_days: int = 7
    ) -> Dict:
        """
        Create a new invitation

        Args:
            invited_by_user_id: ID of the user creating the invite
            invite_type: Type of invite ('club_manager', 'club_fan', 'team_manager', 'team_player', 'team_fan')
            team_id: ID of the team (required for team-level invite types)
            age_group_id: ID of the age group (required for team-level invite types)
            club_id: ID of the club (required for club_manager and club_fan invite types)
            email: Optional email to pre-fill during registration
            expires_in_days: Number of days until invite expires

        Returns:
            Created invitation record
        """
        try:
            # Validate parameters based on invite type
            if invite_type in ('club_manager', 'club_fan'):
                if not club_id:
                    raise ValueError(f"club_id is required for {invite_type} invites")
                # Club-level invites don't need team_id or age_group_id
                team_id = None
                age_group_id = None
            else:
                if not team_id:
                    raise ValueError("team_id is required for team-level invites")
                if not age_group_id:
                    raise ValueError("age_group_id is required for team-level invites")
                club_id = None

            # Generate unique invite code
            invite_code = self.generate_invite_code()

            # Calculate expiration date
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

            # Create invitation record
            invitation_data = {
                'invite_code': invite_code,
                'invited_by_user_id': invited_by_user_id,
                'invite_type': invite_type,
                'team_id': team_id,
                'age_group_id': age_group_id,
                'club_id': club_id,
                'email': email,
                'status': 'pending',
                'expires_at': expires_at.isoformat()
            }

            response = self.supabase.table('invitations').insert(invitation_data).execute()

            if response.data:
                logger.info(f"Created {invite_type} invitation: {invite_code}")
                return response.data[0]
            else:
                raise Exception("Failed to create invitation")

        except Exception as e:
            logger.error(f"Error creating invitation: {e}")
            raise
    
    def validate_invite_code(self, code: str) -> Optional[Dict]:
        """
        Validate an invite code

        Args:
            code: The invite code to validate

        Returns:
            Invitation details if valid, None otherwise
        """
        try:
            logger.info(f"Validating invite code: {code}")

            # Get invitation by code (use .execute() without .single() to avoid exception on no results)
            response = self.supabase.table('invitations')\
                .select('*, teams(name), age_groups(name), clubs(name)')\
                .eq('invite_code', code)\
                .execute()

            if not response.data or len(response.data) == 0:
                logger.warning(f"Invite code {code} not found in database")
                return None

            invitation = response.data[0]
            logger.info(f"Found invitation: status={invitation['status']}, expires_at={invitation['expires_at']}")

            # Check if already used
            if invitation['status'] != 'pending':
                logger.warning(f"Invite code {code} has status '{invitation['status']}' (not pending)")
                return None

            # Check if expired
            expires_at_str = invitation['expires_at']
            if expires_at_str.endswith('Z'):
                expires_at_str = expires_at_str.replace('Z', '+00:00')
            expires_at = datetime.fromisoformat(expires_at_str)

            # Make current time timezone-aware for comparison
            current_time = datetime.now(timezone.utc)

            logger.info(f"Invite code {code}: expires_at={expires_at}, current_time={current_time}, is_expired={expires_at < current_time}")

            if expires_at < current_time:
                # Update status to expired
                self.supabase.table('invitations')\
                    .update({'status': 'expired'})\
                    .eq('id', invitation['id'])\
                    .execute()
                logger.warning(f"Invite code {code} expired at {expires_at}")
                return None

            logger.info(f"Invite code {code} is valid!")
            return {
                'valid': True,
                'id': invitation['id'],
                'invite_type': invitation['invite_type'],
                'team_id': invitation['team_id'],
                'team_name': invitation['teams']['name'] if invitation.get('teams') else None,
                'age_group_id': invitation['age_group_id'],
                'age_group_name': invitation['age_groups']['name'] if invitation.get('age_groups') else None,
                'club_id': invitation.get('club_id'),
                'club_name': invitation['clubs']['name'] if invitation.get('clubs') else None,
                'email': invitation['email'],
                'invited_by_user_id': invitation.get('invited_by_user_id')
            }

        except Exception as e:
            logger.error(f"Error validating invite code {code}: {e}", exc_info=True)
            return None
    
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
            response = self.supabase.table('invitations')\
                .update({
                    'status': 'used',
                    'used_at': datetime.now(timezone.utc).isoformat(),
                    'used_by_user_id': user_id
                })\
                .eq('invite_code', code)\
                .execute()

            if response.data:
                logger.info(f"Invitation {code} redeemed by user {user_id}")

                # Create team_manager_assignments entry for team_manager invites
                # This enables the team manager to create player/fan invites for their team
                if invitation.get('invite_type') == 'team_manager':
                    self._create_team_manager_assignment(
                        user_id=user_id,
                        team_id=invitation.get('team_id'),
                        age_group_id=invitation.get('age_group_id'),
                        assigned_by_user_id=invitation.get('invited_by_user_id')
                    )

                return True

            return False

        except Exception as e:
            logger.error(f"Error redeeming invitation {code}: {e}")
            return False

    def _create_team_manager_assignment(
        self,
        user_id: str,
        team_id: int,
        age_group_id: int,
        assigned_by_user_id: str
    ) -> bool:
        """
        Create a team_manager_assignments entry to grant team management permissions.

        Args:
            user_id: The user being granted management rights
            team_id: The team they can manage
            age_group_id: The age group they can manage
            assigned_by_user_id: The user who created the invite

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if assignment already exists
            existing = self.supabase.table('team_manager_assignments')\
                .select('id')\
                .eq('user_id', user_id)\
                .eq('team_id', team_id)\
                .eq('age_group_id', age_group_id)\
                .execute()

            if existing.data:
                logger.info(f"Team manager assignment already exists for user {user_id}, team {team_id}, age_group {age_group_id}")
                return True

            # Create new assignment
            response = self.supabase.table('team_manager_assignments')\
                .insert({
                    'user_id': user_id,
                    'team_id': team_id,
                    'age_group_id': age_group_id,
                    'assigned_by_user_id': assigned_by_user_id
                })\
                .execute()

            if response.data:
                logger.info(f"Created team manager assignment: user {user_id} -> team {team_id}, age_group {age_group_id}")
                return True

            logger.warning(f"Failed to create team manager assignment for user {user_id}")
            return False

        except Exception as e:
            logger.error(f"Error creating team manager assignment: {e}")
            return False
    
    def get_user_invitations(self, user_id: str) -> List[Dict]:
        """
        Get all invitations created by a user
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of invitations
        """
        try:
            response = self.supabase.table('invitations')\
                .select('*, teams(name), age_groups(name), clubs(name)')\
                .eq('invited_by_user_id', user_id)\
                .order('created_at', desc=True)\
                .execute()
            
            return response.data if response.data else []
            
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
            response = self.supabase.table('invitations')\
                .select('invited_by_user_id, status')\
                .eq('id', invite_id)\
                .single()\
                .execute()
            
            if not response.data:
                return False
            
            invitation = response.data
            
            # Only pending invitations can be cancelled
            if invitation['status'] != 'pending':
                return False
            
            # Update status to expired
            response = self.supabase.table('invitations')\
                .update({'status': 'expired'})\
                .eq('id', invite_id)\
                .execute()
            
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
            response = self.supabase.table('invitations')\
                .select('id')\
                .eq('status', 'pending')\
                .lt('expires_at', datetime.now(timezone.utc).isoformat())\
                .execute()
            
            if not response.data:
                return 0
            
            # Update all to expired
            expired_ids = [inv['id'] for inv in response.data]
            
            self.supabase.table('invitations')\
                .update({'status': 'expired'})\
                .in_('id', expired_ids)\
                .execute()
            
            logger.info(f"Expired {len(expired_ids)} old invitations")
            return len(expired_ids)
            
        except Exception as e:
            logger.error(f"Error expiring old invitations: {e}")
            return 0
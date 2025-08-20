"""
Team Manager Service for Missing Table
Handles team manager assignments and permissions
"""

from typing import Optional, Dict, List
from supabase import Client
import logging

logger = logging.getLogger(__name__)

class TeamManagerService:
    """Service for managing team manager assignments"""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
    
    def assign_team_manager(
        self,
        user_id: str,
        team_id: int,
        age_group_id: int,
        assigned_by_user_id: str
    ) -> Optional[Dict]:
        """
        Assign a user as team manager for a specific team and age group
        
        Args:
            user_id: ID of the user to assign as team manager
            team_id: ID of the team
            age_group_id: ID of the age group
            assigned_by_user_id: ID of the admin making the assignment
            
        Returns:
            Assignment record if successful, None otherwise
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
                logger.warning(f"Team manager assignment already exists for user {user_id}")
                return existing.data[0]
            
            # Create assignment
            assignment_data = {
                'user_id': user_id,
                'team_id': team_id,
                'age_group_id': age_group_id,
                'assigned_by_user_id': assigned_by_user_id
            }
            
            response = self.supabase.table('team_manager_assignments')\
                .insert(assignment_data)\
                .execute()
            
            if response.data:
                logger.info(f"Assigned user {user_id} as team manager for team {team_id}, age group {age_group_id}")
                return response.data[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error assigning team manager: {e}")
            return None
    
    def get_user_team_assignments(self, user_id: str) -> List[Dict]:
        """
        Get all team assignments for a user
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of team assignments
        """
        try:
            response = self.supabase.table('team_manager_assignments')\
                .select('*, teams(id, name), age_groups(id, name)')\
                .eq('user_id', user_id)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Error getting team assignments for user {user_id}: {e}")
            return []
    
    def can_manage_team(self, user_id: str, team_id: int, age_group_id: int) -> bool:
        """
        Check if a user can manage a specific team and age group
        
        Args:
            user_id: ID of the user
            team_id: ID of the team
            age_group_id: ID of the age group
            
        Returns:
            True if user can manage, False otherwise
        """
        try:
            # Check if user is admin
            user_response = self.supabase.table('user_profiles')\
                .select('role')\
                .eq('id', user_id)\
                .single()\
                .execute()
            
            if user_response.data and user_response.data['role'] == 'admin':
                return True
            
            # Check if user has team manager assignment
            response = self.supabase.table('team_manager_assignments')\
                .select('id')\
                .eq('user_id', user_id)\
                .eq('team_id', team_id)\
                .eq('age_group_id', age_group_id)\
                .execute()
            
            return bool(response.data)
            
        except Exception as e:
            logger.error(f"Error checking team management permission: {e}")
            return False
    
    def remove_team_manager(
        self,
        user_id: str,
        team_id: int,
        age_group_id: int
    ) -> bool:
        """
        Remove a team manager assignment
        
        Args:
            user_id: ID of the user
            team_id: ID of the team
            age_group_id: ID of the age group
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.supabase.table('team_manager_assignments')\
                .delete()\
                .eq('user_id', user_id)\
                .eq('team_id', team_id)\
                .eq('age_group_id', age_group_id)\
                .execute()
            
            if response.data:
                logger.info(f"Removed team manager assignment for user {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error removing team manager: {e}")
            return False
    
    def get_team_managers(self, team_id: int, age_group_id: Optional[int] = None) -> List[Dict]:
        """
        Get all team managers for a specific team
        
        Args:
            team_id: ID of the team
            age_group_id: Optional age group filter
            
        Returns:
            List of team managers
        """
        try:
            query = self.supabase.table('team_manager_assignments')\
                .select('*, user:user_profiles!team_manager_assignments_user_id_fkey(id, email, first_name, last_name), age_groups(name)')\
                .eq('team_id', team_id)
            
            if age_group_id:
                query = query.eq('age_group_id', age_group_id)
            
            response = query.execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Error getting team managers: {e}")
            return []
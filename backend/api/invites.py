"""
Invite API endpoints for Missing Table
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import get_current_user_required
from services import InviteService, TeamManagerService
from dao.enhanced_data_access_fixed import SupabaseConnection as DbConnectionHolder
from supabase import create_client

# Initialize database connection with service role for admin operations
supabase_url = os.getenv('SUPABASE_URL', '')
service_key = os.getenv('SUPABASE_SERVICE_KEY')

# Create service role client for admin operations that bypass RLS
if service_key:
    service_client = create_client(supabase_url, service_key)
else:
    # Fallback to regular connection if service key not available
    db_conn_holder_obj = DbConnectionHolder()
    service_client = db_conn_holder_obj.client

router = APIRouter(prefix="/api/invites", tags=["invites"])

# Pydantic models
class CreateInviteRequest(BaseModel):
    invite_type: str = Field(..., pattern="^(team_manager|team_player|team_fan)$")
    team_id: int
    age_group_id: int
    email: Optional[str] = None

class CreateClubManagerInviteRequest(BaseModel):
    club_id: int
    email: Optional[str] = None

class ClubManagerInviteResponse(BaseModel):
    id: str
    invite_code: str
    invite_type: str
    club_id: int
    club_name: Optional[str]
    email: Optional[str]
    status: str
    expires_at: datetime
    created_at: datetime

class InviteCodeValidation(BaseModel):
    invite_code: str = Field(..., min_length=12, max_length=12)

class InviteResponse(BaseModel):
    id: str
    invite_code: str
    invite_type: str
    team_id: int
    team_name: Optional[str]
    age_group_id: int
    age_group_name: Optional[str]
    email: Optional[str]
    status: str
    expires_at: datetime
    created_at: datetime

# Public endpoint - no auth required
@router.get("/validate/{invite_code}")
async def validate_invite_code(invite_code: str):
    """Validate an invite code without authentication"""
    # Use service client for validation to read any invite code
    invite_service = InviteService(service_client)
    
    validation = invite_service.validate_invite_code(invite_code)
    
    if not validation:
        raise HTTPException(status_code=404, detail="Invalid or expired invite code")
    
    return validation

# Admin endpoints
@router.post("/admin/club-manager")
async def create_club_manager_invite(
    request: CreateClubManagerInviteRequest,
    current_user=Depends(get_current_user_required)
):
    """Create a club manager invitation (admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can create club manager invites")

    # Use service role client for admin operations to bypass RLS
    invite_service = InviteService(service_client)

    try:
        # Handle different user ID field names
        user_id = current_user.get('id') or current_user.get('user_id') or current_user.get('sub')
        if not user_id:
            raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")

        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type='club_manager',
            club_id=request.club_id,
            email=request.email
        )

        return invitation

    except Exception as e:
        print(f"DEBUG: Club manager invite creation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/admin/team-manager")
async def create_team_manager_invite(
    request: CreateInviteRequest,
    current_user=Depends(get_current_user_required)
):
    """Create a team manager invitation (admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can create team manager invites")
    
    # Use service role client for admin operations to bypass RLS
    invite_service = InviteService(service_client)
    
    try:
        print(f"DEBUG: Creating invite with current_user: {current_user}")
        print(f"DEBUG: Request data: team_id={request.team_id}, age_group_id={request.age_group_id}, email={request.email}")
        
        # Handle different user ID field names
        user_id = current_user.get('id') or current_user.get('user_id') or current_user.get('sub')
        if not user_id:
            raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")
        
        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type='team_manager',
            team_id=request.team_id,
            age_group_id=request.age_group_id,
            email=request.email
        )
        
        return invitation
        
    except Exception as e:
        print(f"DEBUG: Invite creation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/admin/club-fan")
async def create_club_fan_invite_admin(
    request: CreateClubManagerInviteRequest,
    current_user=Depends(get_current_user_required)
):
    """Create a club fan invitation (admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can create club fan invites")

    # Use service role client for admin operations to bypass RLS
    invite_service = InviteService(service_client)

    try:
        # Handle different user ID field names
        user_id = current_user.get('id') or current_user.get('user_id') or current_user.get('sub')
        if not user_id:
            raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")

        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type='club_fan',
            club_id=request.club_id,
            email=request.email
        )

        return invitation

    except Exception as e:
        print(f"DEBUG: Club fan invite creation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/admin/team-fan")
async def create_team_fan_invite_admin(
    request: CreateInviteRequest,
    current_user=Depends(get_current_user_required)
):
    """Create a team fan invitation (admin) - DEPRECATED: Use club-fan instead"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Use service role client for admin operations to bypass RLS
    invite_service = InviteService(service_client)

    try:
        # Handle different user ID field names
        user_id = current_user.get('id') or current_user.get('user_id') or current_user.get('sub')
        if not user_id:
            raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")

        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type='team_fan',
            team_id=request.team_id,
            age_group_id=request.age_group_id,
            email=request.email
        )

        return invitation

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/admin/team-player", )
async def create_team_player_invite_admin(
    request: CreateInviteRequest,
    current_user=Depends(get_current_user_required)
):
    """Create a team player invitation (admin)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Use service role client for admin operations to bypass RLS
    invite_service = InviteService(service_client)
    
    try:
        # Handle different user ID field names
        user_id = current_user.get('id') or current_user.get('user_id') or current_user.get('sub')
        if not user_id:
            raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")
        
        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type='team_player',
            team_id=request.team_id,
            age_group_id=request.age_group_id,
            email=request.email
        )
        
        return invitation
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Club manager endpoints
@router.post("/club-manager/club-fan")
async def create_club_fan_invite_club_manager(
    request: CreateClubManagerInviteRequest,
    current_user=Depends(get_current_user_required)
):
    """Create a club fan invitation (club manager or admin)"""
    if current_user['role'] not in ['admin', 'club_manager']:
        raise HTTPException(status_code=403, detail="Only club managers or admins can create club fan invites")

    # Use service role client for operations to bypass RLS
    invite_service = InviteService(service_client)

    try:
        # Handle different user ID field names
        user_id = current_user.get('id') or current_user.get('user_id') or current_user.get('sub')
        if not user_id:
            raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")

        # Club managers can only create invites for their own club
        if current_user['role'] == 'club_manager':
            user_club_id = current_user.get('club_id')
            if not user_club_id or user_club_id != request.club_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create fan invites for your own club"
                )

        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type='club_fan',
            club_id=request.club_id,
            email=request.email
        )

        return invitation

    except Exception as e:
        print(f"DEBUG: Club fan invite creation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Team manager endpoints
@router.post("/team-manager/team-fan")
async def create_team_fan_invite(
    request: CreateInviteRequest,
    current_user=Depends(get_current_user_required)
):
    """Create a team fan invitation (team manager) - DEPRECATED: Use club-fan instead"""
    if current_user['role'] not in ['admin', 'team_manager']:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    supabase = service_client
    team_manager_service = TeamManagerService(supabase)
    
    # Handle different user ID field names
    user_id = current_user.get('id') or current_user.get('user_id') or current_user.get('sub')
    if not user_id:
        raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")
    
    # Check if team manager can manage this team
    if current_user['role'] == 'team_manager':
        can_manage = team_manager_service.can_manage_team(
            user_id,
            request.team_id,
            request.age_group_id
        )
        
        if not can_manage:
            raise HTTPException(
                status_code=403, 
                detail="You can only create invites for teams you manage"
            )
    
    invite_service = InviteService(supabase)
    
    try:
        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type='team_fan',
            team_id=request.team_id,
            age_group_id=request.age_group_id,
            email=request.email
        )
        
        return invitation
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/team-manager/team-player", )
async def create_team_player_invite(
    request: CreateInviteRequest,
    current_user=Depends(get_current_user_required)
):
    """Create a team player invitation (team manager)"""
    if current_user['role'] not in ['admin', 'team_manager']:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    supabase = service_client
    team_manager_service = TeamManagerService(supabase)
    
    # Handle different user ID field names
    user_id = current_user.get('id') or current_user.get('user_id') or current_user.get('sub')
    if not user_id:
        raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")
    
    # Check if team manager can manage this team
    if current_user['role'] == 'team_manager':
        can_manage = team_manager_service.can_manage_team(
            user_id,
            request.team_id,
            request.age_group_id
        )
        
        if not can_manage:
            raise HTTPException(
                status_code=403, 
                detail="You can only create invites for teams you manage"
            )
    
    invite_service = InviteService(supabase)
    
    try:
        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type='team_player',
            team_id=request.team_id,
            age_group_id=request.age_group_id,
            email=request.email
        )
        
        return invitation
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# List user's invitations
@router.get("/my-invites", )
async def get_my_invitations(
    current_user=Depends(get_current_user_required),
    status: Optional[str] = Query(None, pattern="^(pending|used|expired)$")
):
    """Get all invitations created by the current user"""
    supabase = service_client
    invite_service = InviteService(supabase)
    
    # Handle different user ID field names
    user_id = current_user.get('id') or current_user.get('user_id') or current_user.get('sub')
    if not user_id:
        raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")
    
    invitations = invite_service.get_user_invitations(user_id)
    
    # Filter by status if provided
    if status:
        invitations = [inv for inv in invitations if inv['status'] == status]
    
    return invitations

# Cancel invitation
@router.delete("/{invite_id}", )
async def cancel_invitation(
    invite_id: str,
    current_user=Depends(get_current_user_required)
):
    """Cancel a pending invitation"""
    supabase = service_client
    invite_service = InviteService(supabase)

    # Check if user owns this invitation or is admin
    invitations = invite_service.get_user_invitations(current_user['user_id'])
    user_owns_invite = any(inv['id'] == invite_id for inv in invitations)

    if not user_owns_invite and current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="You can only cancel your own invitations")

    success = invite_service.cancel_invitation(invite_id, current_user['user_id'])

    if not success:
        raise HTTPException(status_code=404, detail="Invitation not found or already cancelled")

    return {"message": "Invitation cancelled successfully"}

# Team manager assignments endpoint
@router.get("/team-manager/assignments", )
async def get_team_manager_assignments(current_user=Depends(get_current_user_required)):
    """Get team assignments for the current user"""
    if current_user['role'] not in ['admin', 'team_manager']:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    supabase = service_client
    team_manager_service = TeamManagerService(supabase)
    
    assignments = team_manager_service.get_user_team_assignments(current_user['id'])
    
    return assignments
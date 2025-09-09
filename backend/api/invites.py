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

@router.post("/admin/team-fan", )
async def create_team_fan_invite_admin(
    request: CreateInviteRequest,
    current_user=Depends(get_current_user_required)
):
    """Create a team fan invitation (admin)"""
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

# Team manager endpoints
@router.post("/team-manager/team-fan", )
async def create_team_fan_invite(
    request: CreateInviteRequest,
    current_user=Depends(get_current_user_required)
):
    """Create a team fan invitation (team manager)"""
    if current_user['role'] not in ['admin', 'team_manager']:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    supabase = db_conn_holder_obj.client
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
    
    supabase = db_conn_holder_obj.client
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
    supabase = db_conn_holder_obj.client
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
    supabase = db_conn_holder_obj.client
    invite_service = InviteService(supabase)
    
    # Check if user owns this invitation or is admin
    invitations = invite_service.get_user_invitations(current_user['id'])
    user_owns_invite = any(inv['id'] == invite_id for inv in invitations)
    
    if not user_owns_invite and current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="You can only cancel your own invitations")
    
    success = invite_service.cancel_invitation(invite_id, current_user['id'])
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to cancel invitation")
    
    return {"message": "Invitation cancelled successfully"}

# Team manager assignments endpoint
@router.get("/team-manager/assignments", )
async def get_team_manager_assignments(current_user=Depends(get_current_user_required)):
    """Get team assignments for the current user"""
    if current_user['role'] not in ['admin', 'team_manager']:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    supabase = db_conn_holder_obj.client
    team_manager_service = TeamManagerService(supabase)
    
    assignments = team_manager_service.get_user_team_assignments(current_user['id'])
    
    return assignments
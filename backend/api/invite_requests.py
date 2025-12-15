"""
Invite Request API endpoints for Missing Table

Handles public invite request submissions and admin management.
"""

import os
import sys
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from supabase import create_client

logger = structlog.get_logger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import get_current_user_required
from dao.match_dao import SupabaseConnection as DbConnectionHolder

# Initialize database connection with service role for admin operations
supabase_url = os.getenv('SUPABASE_URL', '')
service_key = os.getenv('SUPABASE_SERVICE_KEY')

# Create service role client for operations that bypass RLS
if service_key:
    service_client = create_client(supabase_url, service_key)
else:
    # Fallback to regular connection if service key not available
    db_conn_holder_obj = DbConnectionHolder()
    service_client = db_conn_holder_obj.client

router = APIRouter(prefix="/api/invite-requests", tags=["invite-requests"])


# Pydantic models
class InviteRequestCreate(BaseModel):
    """Model for creating a new invite request"""
    email: EmailStr = Field(..., description="Email address of the requester")
    name: str = Field(..., min_length=1, max_length=255, description="Name of the requester")
    team: Optional[str] = Field(None, max_length=255, description="Team or club affiliation")
    reason: Optional[str] = Field(None, description="Reason for wanting to join")
    website: Optional[str] = Field(None, description="Honeypot field - should be empty")


class InviteRequestResponse(BaseModel):
    """Model for invite request response"""
    id: str
    email: str
    name: str
    team: Optional[str]
    reason: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    admin_notes: Optional[str]


class InviteRequestStatusUpdate(BaseModel):
    """Model for updating invite request status"""
    status: str = Field(..., pattern="^(pending|approved|rejected)$")
    admin_notes: Optional[str] = Field(None, description="Admin notes about the decision")


class InviteRequestStats(BaseModel):
    """Statistics about invite requests"""
    total: int
    pending: int
    approved: int
    rejected: int


# Public endpoint - no auth required
@router.post("", status_code=201)
async def create_invite_request(request: InviteRequestCreate):
    """
    Submit a new invite request (public endpoint).

    Anyone can submit an invite request without authentication.
    Duplicate email submissions are allowed (users can re-submit).
    """
    try:
        # Honeypot check - if filled, it's a bot
        if request.website:
            # Return fake success to not alert the bot
            return {
                "success": True,
                "message": "Thank you for your interest! We'll review your request and reach out soon."
            }

        # Check for existing pending request with same email
        existing = service_client.table('invite_requests').select('id, status').eq(
            'email', request.email
        ).eq('status', 'pending').execute()

        if existing.data:
            # Return success anyway - we don't want to reveal if email exists
            return {
                "success": True,
                "message": "Thank you for your interest! We'll review your request and reach out soon."
            }

        # Insert new invite request
        result = service_client.table('invite_requests').insert({
            'email': request.email,
            'name': request.name,
            'team': request.team,
            'reason': request.reason,
            'status': 'pending'
        }).execute()

        if result.data:
            return {
                "success": True,
                "message": "Thank you for your interest! We'll review your request and reach out soon."
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to submit invite request")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error creating invite request")
        raise HTTPException(status_code=500, detail="An error occurred while submitting your request")


# Admin endpoints
@router.get("", response_model=List[InviteRequestResponse])
async def list_invite_requests(
    current_user=Depends(get_current_user_required),
    status: Optional[str] = Query(None, pattern="^(pending|approved|rejected)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    List all invite requests (admin only).

    Supports filtering by status and pagination.
    """
    if current_user.get('role') not in ['admin', 'club_manager']:
        raise HTTPException(status_code=403, detail="Only admins can view invite requests")

    try:
        query = service_client.table('invite_requests').select('*').order(
            'created_at', desc=True
        ).range(offset, offset + limit - 1)

        if status:
            query = query.eq('status', status)

        result = query.execute()

        return result.data or []

    except Exception as e:
        logger.exception("Error listing invite requests")
        raise HTTPException(status_code=500, detail="Failed to retrieve invite requests")


@router.get("/stats", response_model=InviteRequestStats)
async def get_invite_request_stats(current_user=Depends(get_current_user_required)):
    """
    Get statistics about invite requests (admin only).
    """
    if current_user.get('role') not in ['admin', 'club_manager']:
        raise HTTPException(status_code=403, detail="Only admins can view invite request stats")

    try:
        # Get counts by status
        all_requests = service_client.table('invite_requests').select('status').execute()

        stats = {
            'total': 0,
            'pending': 0,
            'approved': 0,
            'rejected': 0
        }

        if all_requests.data:
            stats['total'] = len(all_requests.data)
            for req in all_requests.data:
                status = req.get('status', 'pending')
                if status in stats:
                    stats[status] += 1

        return stats

    except Exception as e:
        logger.exception("Error getting invite request stats")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.get("/{request_id}", response_model=InviteRequestResponse)
async def get_invite_request(
    request_id: str,
    current_user=Depends(get_current_user_required)
):
    """
    Get a specific invite request by ID (admin only).
    """
    if current_user.get('role') not in ['admin', 'club_manager']:
        raise HTTPException(status_code=403, detail="Only admins can view invite requests")

    try:
        result = service_client.table('invite_requests').select('*').eq(
            'id', request_id
        ).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Invite request not found")

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting invite request")
        raise HTTPException(status_code=500, detail="Failed to retrieve invite request")


@router.put("/{request_id}/status")
async def update_invite_request_status(
    request_id: str,
    status_update: InviteRequestStatusUpdate,
    current_user=Depends(get_current_user_required)
):
    """
    Update the status of an invite request (admin only).

    Used to approve or reject invite requests.
    """
    if current_user.get('role') not in ['admin', 'club_manager']:
        raise HTTPException(status_code=403, detail="Only admins can update invite requests")

    try:
        # Get current request
        existing = service_client.table('invite_requests').select('*').eq(
            'id', request_id
        ).execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="Invite request not found")

        # Get user ID
        user_id = current_user.get('id') or current_user.get('user_id') or current_user.get('sub')

        # Update the request
        update_data = {
            'status': status_update.status,
            'reviewed_by': user_id,
            'reviewed_at': datetime.utcnow().isoformat(),
        }

        if status_update.admin_notes:
            update_data['admin_notes'] = status_update.admin_notes

        result = service_client.table('invite_requests').update(
            update_data
        ).eq('id', request_id).execute()

        if result.data:
            return {
                "success": True,
                "message": f"Invite request {status_update.status}",
                "request": result.data[0]
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update invite request")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error updating invite request")
        raise HTTPException(status_code=500, detail="Failed to update invite request")


@router.delete("/{request_id}")
async def delete_invite_request(
    request_id: str,
    current_user=Depends(get_current_user_required)
):
    """
    Delete an invite request (admin only).

    Use with caution - this permanently removes the request.
    """
    if current_user.get('role') not in ['admin', 'club_manager']:
        raise HTTPException(status_code=403, detail="Only admins can delete invite requests")

    try:
        # Check if request exists
        existing = service_client.table('invite_requests').select('id').eq(
            'id', request_id
        ).execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="Invite request not found")

        # Delete the request
        service_client.table('invite_requests').delete().eq('id', request_id).execute()

        return {
            "success": True,
            "message": "Invite request deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deleting invite request")
        raise HTTPException(status_code=500, detail="Failed to delete invite request")

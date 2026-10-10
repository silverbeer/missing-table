"""
Invite API endpoints for Missing Table
"""

import os
import sys
from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = structlog.get_logger(__name__)

from auth import get_current_user_required
from dao.match_dao import SupabaseConnection as DbConnectionHolder
from services import InviteService, TeamManagerService
from supabase import create_client

_service_client = None


def _get_service_client():
    """Service-role client for admin operations that bypass RLS.

    Built lazily on first use: this module is imported before app.py's
    load_dotenv(.env.local, override=True) runs, so reading SUPABASE_URL at
    import time can bind to a stale value from .env (this broke local invite
    creation after the SB-113 port move).
    """
    global _service_client
    if _service_client is None:
        supabase_url = os.getenv("SUPABASE_URL", "")
        service_key = os.getenv("SUPABASE_SERVICE_KEY")
        if supabase_url and service_key:
            _service_client = create_client(supabase_url, service_key)
        else:
            # Fallback to regular connection if service key not available
            _service_client = DbConnectionHolder().client
    return _service_client


class _ServiceClientProxy:
    """Defers client construction until an attribute is touched."""

    def __getattr__(self, name):
        return getattr(_get_service_client(), name)


service_client = _ServiceClientProxy()

router = APIRouter(prefix="/api/invites", tags=["invites"])


def _refuse_ios_beta(request: BaseModel) -> None:
    """iPhone beta invites are admin-only (SB-1314): the club/team manager
    endpoints refuse the option rather than silently dropping it."""
    if getattr(request, "ios_beta", False):
        raise HTTPException(status_code=403, detail="Only admins can create iPhone beta invites")


def _refuse_invite_request_link(request: BaseModel) -> None:
    """Creating an invite from an invite request is admin-only (SB-1312)."""
    if getattr(request, "invite_request_id", None):
        raise HTTPException(status_code=403, detail="Only admins can create invites from invite requests")


def _require_linkable_invite_request(request_id: UUID | None) -> None:
    """The invite request an admin invite answers must exist, be pending and
    not already linked (SB-1312). Checked before the invite is created."""
    if request_id is None:
        return
    result = (
        service_client.table("invite_requests").select("id, status, invitation_id").eq("id", str(request_id)).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Invite request not found")
    row = result.data[0]
    if row.get("invitation_id"):
        raise HTTPException(status_code=409, detail="Invite request is already linked to an invitation")
    if row.get("status") != "pending":
        raise HTTPException(status_code=409, detail=f"Invite request is already {row.get('status')}")


def _link_invite_request(request_id: UUID | None, invitation: dict, user_id: str) -> None:
    """Mark the invite request approved and point it at the new invitation.

    The invitation email replaces the old "you're approved" email, so none is
    sent here. The invite already exists, so a failure is logged, not raised.
    """
    if request_id is None:
        return
    try:
        result = (
            service_client.table("invite_requests")
            .update(
                {
                    "invitation_id": invitation["id"],
                    "status": "approved",
                    "reviewed_by": user_id,
                    "reviewed_at": datetime.utcnow().isoformat(),
                }
            )
            .eq("id", str(request_id))
            .eq("status", "pending")
            .is_("invitation_id", "null")
            .execute()
        )
        if not result.data:
            logger.warning("Invite request was not linked", invite_request_id=str(request_id))
    except Exception:
        logger.exception("Failed to link invite request", invite_request_id=str(request_id))


# Pydantic models
class CreateInviteRequest(BaseModel):
    invite_type: str = Field(..., pattern="^(team_manager|team_player|team_fan)$")
    team_id: int
    age_group_id: int
    email: str | None = None
    player_id: int | None = None  # Links to existing roster entry (for team_player invites)
    jersey_number: int | None = Field(None, ge=1, le=99)  # Claims that roster spot on redemption
    season_id: int | None = None  # Season scope for roster claims; default = current season
    note: str | None = Field(None, max_length=500)  # Personal note about who the invite was sent to
    # iPhone beta (SB-1314) - admin endpoints only; manager endpoints refuse it.
    ios_beta: bool = False
    testflight_email: str | None = Field(None, max_length=255)  # Defaults to email
    # Invite request this invite answers (SB-1312) - admin endpoints only.
    invite_request_id: UUID | None = None


class CreateClubManagerInviteRequest(BaseModel):
    club_id: int
    email: str | None = None
    note: str | None = Field(None, max_length=500)  # Personal note about who the invite was sent to
    # iPhone beta (SB-1314) - admin endpoints only; manager endpoints refuse it.
    ios_beta: bool = False
    testflight_email: str | None = Field(None, max_length=255)  # Defaults to email
    # Invite request this invite answers (SB-1312) - admin endpoints only.
    invite_request_id: UUID | None = None


class ClubManagerInviteResponse(BaseModel):
    id: str
    invite_code: str
    invite_type: str
    club_id: int
    club_name: str | None
    email: str | None
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
    team_name: str | None
    age_group_id: int
    age_group_name: str | None
    email: str | None
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
    request: CreateClubManagerInviteRequest, current_user=Depends(get_current_user_required)
):
    """Create a club manager invitation (admin only)"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create club manager invites")

    _require_linkable_invite_request(request.invite_request_id)

    # Use service role client for admin operations to bypass RLS
    invite_service = InviteService(service_client)

    try:
        # Handle different user ID field names
        user_id = current_user.get("id") or current_user.get("user_id") or current_user.get("sub")
        if not user_id:
            raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")

        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type="club_manager",
            club_id=request.club_id,
            email=request.email,
            note=request.note,
            ios_beta=request.ios_beta,
            testflight_email=request.testflight_email,
        )
        _link_invite_request(request.invite_request_id, invitation, user_id)

        return invitation

    except Exception as e:
        logger.exception("Club manager invite creation error")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/admin/team-manager")
async def create_team_manager_invite(request: CreateInviteRequest, current_user=Depends(get_current_user_required)):
    """Create a team manager invitation (admin only)"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create team manager invites")

    _require_linkable_invite_request(request.invite_request_id)

    # Use service role client for admin operations to bypass RLS
    invite_service = InviteService(service_client)

    try:
        logger.debug(
            "Creating invite",
            current_user=current_user,
            team_id=request.team_id,
            age_group_id=request.age_group_id,
            email=request.email,
        )

        # Handle different user ID field names
        user_id = current_user.get("id") or current_user.get("user_id") or current_user.get("sub")
        if not user_id:
            raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")

        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type="team_manager",
            team_id=request.team_id,
            age_group_id=request.age_group_id,
            email=request.email,
            note=request.note,
            ios_beta=request.ios_beta,
            testflight_email=request.testflight_email,
        )
        _link_invite_request(request.invite_request_id, invitation, user_id)

        return invitation

    except Exception as e:
        logger.exception("Invite creation error")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/admin/club-fan")
async def create_club_fan_invite_admin(
    request: CreateClubManagerInviteRequest, current_user=Depends(get_current_user_required)
):
    """Create a club fan invitation (admin only)"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create club fan invites")

    _require_linkable_invite_request(request.invite_request_id)

    # Use service role client for admin operations to bypass RLS
    invite_service = InviteService(service_client)

    try:
        # Handle different user ID field names
        user_id = current_user.get("id") or current_user.get("user_id") or current_user.get("sub")
        if not user_id:
            raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")

        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type="club_fan",
            club_id=request.club_id,
            email=request.email,
            note=request.note,
            ios_beta=request.ios_beta,
            testflight_email=request.testflight_email,
        )
        _link_invite_request(request.invite_request_id, invitation, user_id)

        return invitation

    except Exception as e:
        logger.exception("Club fan invite creation error")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/admin/team-fan")
async def create_team_fan_invite_admin(request: CreateInviteRequest, current_user=Depends(get_current_user_required)):
    """Create a team fan invitation (admin) - DEPRECATED: Use club-fan instead"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized")

    _require_linkable_invite_request(request.invite_request_id)

    # Use service role client for admin operations to bypass RLS
    invite_service = InviteService(service_client)

    try:
        # Handle different user ID field names
        user_id = current_user.get("id") or current_user.get("user_id") or current_user.get("sub")
        if not user_id:
            raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")

        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type="team_fan",
            team_id=request.team_id,
            age_group_id=request.age_group_id,
            email=request.email,
            note=request.note,
            ios_beta=request.ios_beta,
            testflight_email=request.testflight_email,
        )
        _link_invite_request(request.invite_request_id, invitation, user_id)

        return invitation

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/admin/team-player",
)
async def create_team_player_invite_admin(
    request: CreateInviteRequest, current_user=Depends(get_current_user_required)
):
    """Create a team player invitation (admin).

    If player_id is provided, the invitation will be linked to an existing roster entry.
    If jersey_number is provided (without player_id), a roster entry will be created
    when the player accepts the invite.
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized")

    _require_linkable_invite_request(request.invite_request_id)

    # Use service role client for admin operations to bypass RLS
    invite_service = InviteService(service_client)

    try:
        # Handle different user ID field names
        user_id = current_user.get("id") or current_user.get("user_id") or current_user.get("sub")
        if not user_id:
            raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")

        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type="team_player",
            team_id=request.team_id,
            age_group_id=request.age_group_id,
            email=request.email,
            player_id=request.player_id,
            jersey_number=request.jersey_number,
            season_id=request.season_id,
            note=request.note,
            ios_beta=request.ios_beta,
            testflight_email=request.testflight_email,
        )
        _link_invite_request(request.invite_request_id, invitation, user_id)

        return invitation

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# Club manager endpoints
@router.post("/club-manager/club-fan")
async def create_club_fan_invite_club_manager(
    request: CreateClubManagerInviteRequest, current_user=Depends(get_current_user_required)
):
    """Create a club fan invitation (club manager or admin)"""
    if current_user["role"] not in ["admin", "club_manager"]:
        raise HTTPException(status_code=403, detail="Only club managers or admins can create club fan invites")
    _refuse_ios_beta(request)
    _refuse_invite_request_link(request)

    # Use service role client for operations to bypass RLS
    invite_service = InviteService(service_client)

    try:
        # Handle different user ID field names
        user_id = current_user.get("id") or current_user.get("user_id") or current_user.get("sub")
        if not user_id:
            raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")

        # Club managers can only create invites for their own club
        if current_user["role"] == "club_manager":
            user_club_id = current_user.get("club_id")
            if not user_club_id or user_club_id != request.club_id:
                raise HTTPException(status_code=403, detail="You can only create fan invites for your own club")

        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type="club_fan",
            club_id=request.club_id,
            email=request.email,
            note=request.note,
        )

        return invitation

    except Exception as e:
        logger.exception("Club fan invite creation error")
        raise HTTPException(status_code=400, detail=str(e)) from e


# Team manager endpoints
@router.post("/team-manager/team-fan")
async def create_team_fan_invite(request: CreateInviteRequest, current_user=Depends(get_current_user_required)):
    """Create a team fan invitation (team manager) - DEPRECATED: Use club-fan instead"""
    if current_user["role"] not in ["admin", "team-manager", "team_manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    _refuse_ios_beta(request)
    _refuse_invite_request_link(request)

    supabase = service_client
    team_manager_service = TeamManagerService(supabase)

    # Handle different user ID field names
    user_id = current_user.get("id") or current_user.get("user_id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")

    # Check if team manager can manage this team
    if current_user["role"] in ["team_manager", "team-manager"]:
        can_manage = team_manager_service.can_manage_team(user_id, request.team_id, request.age_group_id)

        if not can_manage:
            raise HTTPException(status_code=403, detail="You can only create invites for teams you manage")

    invite_service = InviteService(supabase)

    try:
        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type="team_fan",
            team_id=request.team_id,
            age_group_id=request.age_group_id,
            email=request.email,
            note=request.note,
        )

        return invitation

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/team-manager/team-player",
)
async def create_team_player_invite(request: CreateInviteRequest, current_user=Depends(get_current_user_required)):
    """Create a team player invitation (team manager).

    If player_id is provided, the invitation will be linked to an existing roster entry.
    If jersey_number is provided (without player_id), a roster entry will be created
    when the player accepts the invite.
    """
    if current_user["role"] not in ["admin", "team-manager", "team_manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    _refuse_ios_beta(request)
    _refuse_invite_request_link(request)

    supabase = service_client
    team_manager_service = TeamManagerService(supabase)

    # Handle different user ID field names
    user_id = current_user.get("id") or current_user.get("user_id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")

    # Check if team manager can manage this team
    if current_user["role"] in ["team_manager", "team-manager"]:
        can_manage = team_manager_service.can_manage_team(user_id, request.team_id, request.age_group_id)

        if not can_manage:
            raise HTTPException(status_code=403, detail="You can only create invites for teams you manage")

    invite_service = InviteService(supabase)

    try:
        invitation = invite_service.create_invitation(
            invited_by_user_id=user_id,
            invite_type="team_player",
            team_id=request.team_id,
            age_group_id=request.age_group_id,
            email=request.email,
            player_id=request.player_id,
            jersey_number=request.jersey_number,
            season_id=request.season_id,
            note=request.note,
        )

        return invitation

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/admin/{invite_id}/testflight/retry")
async def retry_invite_testflight(invite_id: str, current_user=Depends(get_current_user_required)):
    """Retry adding an iPhone beta invite's tester to TestFlight (admin only, SB-1314).

    Returns the invitation with its new testflight_* fields. A TestFlight
    failure is reported in testflight_status/testflight_error, not as an error.
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can retry TestFlight")

    invite_service = InviteService(service_client)
    try:
        return invite_service.retry_testflight(invite_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# List user's invitations
@router.get(
    "/my-invites",
)
async def get_my_invitations(
    current_user=Depends(get_current_user_required),
    status: str | None = Query(None, pattern="^(pending|used|expired)$"),
):
    """Get all invitations created by the current user"""
    supabase = service_client
    invite_service = InviteService(supabase)

    # Handle different user ID field names
    user_id = current_user.get("id") or current_user.get("user_id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail=f"User ID not found in current_user: {current_user}")

    invitations = invite_service.get_user_invitations(user_id)

    # Filter by status if provided
    if status:
        invitations = [inv for inv in invitations if inv["status"] == status]

    return invitations


# Cancel invitation
@router.delete(
    "/{invite_id}",
)
async def cancel_invitation(invite_id: str, current_user=Depends(get_current_user_required)):
    """Cancel a pending invitation"""
    supabase = service_client
    invite_service = InviteService(supabase)

    # Check if user owns this invitation or is admin
    invitations = invite_service.get_user_invitations(current_user["user_id"])
    user_owns_invite = any(inv["id"] == invite_id for inv in invitations)

    if not user_owns_invite and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="You can only cancel your own invitations")

    success = invite_service.cancel_invitation(invite_id, current_user["user_id"])

    if not success:
        raise HTTPException(status_code=404, detail="Invitation not found or already cancelled")

    return {"message": "Invitation cancelled successfully"}


# Team manager assignments endpoint
@router.get(
    "/team-manager/assignments",
)
async def get_team_manager_assignments(current_user=Depends(get_current_user_required)):
    """Get team assignments for the current user"""
    if current_user["role"] not in ["admin", "team-manager", "team_manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    supabase = service_client
    team_manager_service = TeamManagerService(supabase)

    assignments = team_manager_service.get_user_team_assignments(current_user["id"])

    return assignments

"""
Channel Access Request API endpoints for Missing Table

Allows logged-in users to request access to their team's Telegram/Discord channels.
Admins review requests and mark them approved/denied after manually adding users.
"""

import os
import sys
from datetime import datetime
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from supabase import create_client

logger = structlog.get_logger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import get_current_user_required
from dao.match_dao import SupabaseConnection as DbConnectionHolder

# Initialize database connection with service role for admin operations
supabase_url = os.getenv("SUPABASE_URL", "")
service_key = os.getenv("SUPABASE_SERVICE_KEY")

if service_key:
    service_client = create_client(supabase_url, service_key)
else:
    db_conn_holder_obj = DbConnectionHolder()
    service_client = db_conn_holder_obj.client

router = APIRouter(prefix="/api/channel-requests", tags=["channel-requests"])


# ============================================================
# Pydantic models
# ============================================================

class ChannelAccessRequestCreate(BaseModel):
    """Model for creating/updating a channel access request."""
    telegram: bool = False
    discord: bool = False
    telegram_handle: str | None = None
    discord_handle: str | None = None


class ChannelAccessRequestResponse(BaseModel):
    """Model for channel access request response."""
    id: str
    user_id: str
    team_id: int
    telegram_handle: str | None
    discord_handle: str | None
    telegram_status: str
    discord_status: str
    telegram_reviewed_by: str | None
    telegram_reviewed_at: datetime | None
    discord_reviewed_by: str | None
    discord_reviewed_at: datetime | None
    admin_notes: str | None
    created_at: datetime
    updated_at: datetime
    # Joined fields (not always present)
    user_display_name: str | None = None
    user_email: str | None = None
    team_name: str | None = None


class ChannelAccessStatusUpdate(BaseModel):
    """Model for admin updating per-platform status."""
    platform: Literal["telegram", "discord"]
    status: Literal["approved", "denied"]
    admin_notes: str | None = None


class ChannelAccessStats(BaseModel):
    """Statistics about channel access requests."""
    total: int
    pending_telegram: int
    pending_discord: int
    pending_total: int
    approved: int
    denied: int


# ============================================================
# User endpoints
# ============================================================

@router.get("/me")
async def get_my_channel_request(current_user=Depends(get_current_user_required)):
    """Get the current user's channel access request (if any)."""
    user_id = current_user.get("user_id") or current_user.get("id") or current_user.get("sub")
    try:
        result = (
            service_client.table("channel_access_requests")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="No channel access request found")
        return result.data[0]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error getting channel request for user")
        raise HTTPException(status_code=500, detail="Failed to get channel access request") from None


@router.post("", status_code=201)
async def create_channel_request(
    request: ChannelAccessRequestCreate,
    current_user=Depends(get_current_user_required),
):
    """
    Submit or update a channel access request for the current user.

    Sets chosen platform(s) to 'pending' (only if current status is 'none' or 'denied').
    Writes handles to both the request row and user_profiles.
    Requires the user to have a team_id on their profile.
    """
    user_id = current_user.get("user_id") or current_user.get("id") or current_user.get("sub")

    if not request.telegram and not request.discord:
        raise HTTPException(status_code=400, detail="Must request at least one platform (telegram or discord)")

    try:
        # Get user profile to find team_id / club_id
        profile_result = (
            service_client.table("user_profiles")
            .select("team_id, club_id, telegram_handle, discord_handle")
            .eq("id", user_id)
            .execute()
        )

        if not profile_result.data:
            raise HTTPException(status_code=404, detail="User profile not found")

        profile = profile_result.data[0]
        team_id = profile.get("team_id")

        # Club managers may have club_id but no team_id — fall back to first team in their club
        if not team_id and profile.get("club_id"):
            teams_result = (
                service_client.table("teams")
                .select("id")
                .eq("club_id", profile["club_id"])
                .order("id")
                .limit(1)
                .execute()
            )
            if teams_result.data:
                team_id = teams_result.data[0]["id"]

        if not team_id:
            raise HTTPException(
                status_code=400,
                detail="You must be assigned to a team before requesting channel access"
            )

        # Check for existing request for this (user, team)
        existing_result = (
            service_client.table("channel_access_requests")
            .select("*")
            .eq("user_id", user_id)
            .eq("team_id", team_id)
            .execute()
        )

        # Determine handles to use (prefer provided, fall back to profile values)
        tg_handle = request.telegram_handle or profile.get("telegram_handle")
        dc_handle = request.discord_handle or profile.get("discord_handle")

        # Validate that handles are provided for requested platforms
        if request.telegram and not tg_handle:
            raise HTTPException(status_code=400, detail="Telegram handle is required to request Telegram access")
        if request.discord and not dc_handle:
            raise HTTPException(status_code=400, detail="Discord handle is required to request Discord access")

        # Prepare update data for user_profiles (sync handles)
        profile_update = {}
        if tg_handle:
            profile_update["telegram_handle"] = tg_handle
        if dc_handle:
            profile_update["discord_handle"] = dc_handle
        if profile_update:
            service_client.table("user_profiles").update(profile_update).eq("id", user_id).execute()

        now = datetime.utcnow().isoformat()

        if existing_result.data:
            # Update existing row — only flip status if currently none/denied
            existing = existing_result.data[0]
            update_data = {"updated_at": now}

            if tg_handle:
                update_data["telegram_handle"] = tg_handle
            if dc_handle:
                update_data["discord_handle"] = dc_handle

            if request.telegram:
                if existing.get("telegram_status") in ("none", "denied"):
                    update_data["telegram_status"] = "pending"
                elif existing.get("telegram_status") == "approved":
                    pass  # Already approved — don't reset
                else:
                    update_data["telegram_status"] = "pending"

            if request.discord:
                if existing.get("discord_status") in ("none", "denied"):
                    update_data["discord_status"] = "pending"
                elif existing.get("discord_status") == "approved":
                    pass
                else:
                    update_data["discord_status"] = "pending"

            result = (
                service_client.table("channel_access_requests")
                .update(update_data)
                .eq("id", existing["id"])
                .execute()
            )
        else:
            # Insert new row
            insert_data = {
                "user_id": user_id,
                "team_id": team_id,
                "telegram_handle": tg_handle,
                "discord_handle": dc_handle,
                "telegram_status": "pending" if request.telegram else "none",
                "discord_status": "pending" if request.discord else "none",
            }
            result = service_client.table("channel_access_requests").insert(insert_data).execute()

        if result.data:
            return {
                "success": True,
                "message": "Channel access request submitted",
                "request": result.data[0],
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to submit channel access request")

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error creating channel access request")
        raise HTTPException(status_code=500, detail="Failed to submit channel access request") from None


@router.delete("/me/{platform}")
async def withdraw_channel_request(
    platform: Literal["telegram", "discord"],
    current_user=Depends(get_current_user_required),
):
    """Withdraw a pending channel request (set back to 'none')."""
    user_id = current_user.get("user_id") or current_user.get("id") or current_user.get("sub")

    try:
        existing_result = (
            service_client.table("channel_access_requests")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )

        if not existing_result.data:
            raise HTTPException(status_code=404, detail="No channel access request found")

        existing = existing_result.data[0]
        status_field = f"{platform}_status"

        if existing.get(status_field) != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"{platform.capitalize()} request is not in pending state"
            )

        service_client.table("channel_access_requests").update(
            {status_field: "none", "updated_at": datetime.utcnow().isoformat()}
        ).eq("id", existing["id"]).execute()

        return {"success": True, "message": f"{platform.capitalize()} request withdrawn"}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error withdrawing channel request")
        raise HTTPException(status_code=500, detail="Failed to withdraw channel request") from None


# ============================================================
# Admin endpoints
# ============================================================

def _require_admin_or_club_manager(current_user):
    """Raise 403 if user is not admin or club_manager."""
    if current_user.get("role") not in ["admin", "club_manager"]:
        raise HTTPException(status_code=403, detail="Only admins and club managers can manage channel requests")


@router.get("", response_model=list[ChannelAccessRequestResponse])
async def list_channel_requests(
    current_user=Depends(get_current_user_required),
    status: str | None = Query(None, pattern="^(pending|approved|denied)$"),
    platform: str | None = Query(None, pattern="^(telegram|discord)$"),
    team_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List channel access requests (admin/club_manager only)."""
    _require_admin_or_club_manager(current_user)

    try:
        # Join user_profiles and teams for display fields
        query = (
            service_client.table("channel_access_requests")
            .select(
                "*, "
                "user_profiles!channel_access_requests_user_id_fkey(display_name, email), "
                "teams!channel_access_requests_team_id_fkey(name)"
            )
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )

        if team_id:
            query = query.eq("team_id", team_id)

        if status and platform:
            query = query.eq(f"{platform}_status", status)
        elif status:
            # Filter where either platform has the status
            query = query.or_(f"telegram_status.eq.{status},discord_status.eq.{status}")
        elif platform:
            # Filter where platform is not 'none'
            query = query.neq(f"{platform}_status", "none")

        # Club managers scoped to their club's teams
        if current_user.get("role") == "club_manager":
            club_id = current_user.get("club_id")
            if club_id:
                teams_result = (
                    service_client.table("teams")
                    .select("id")
                    .eq("club_id", club_id)
                    .execute()
                )
                club_team_ids = [t["id"] for t in (teams_result.data or [])]
                if club_team_ids:
                    query = query.in_("team_id", club_team_ids)
                else:
                    return []

        result = query.execute()

        # Flatten joined fields
        rows = []
        for row in (result.data or []):
            profile = row.pop("user_profiles", None) or {}
            team = row.pop("teams", None) or {}
            row["user_display_name"] = profile.get("display_name")
            row["user_email"] = profile.get("email")
            row["team_name"] = team.get("name")
            rows.append(row)

        return rows

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error listing channel requests")
        raise HTTPException(status_code=500, detail="Failed to retrieve channel requests") from None


@router.get("/stats", response_model=ChannelAccessStats)
async def get_channel_request_stats(current_user=Depends(get_current_user_required)):
    """Get statistics about channel access requests (admin/club_manager only)."""
    _require_admin_or_club_manager(current_user)

    try:
        all_requests = (
            service_client.table("channel_access_requests")
            .select("telegram_status, discord_status")
            .execute()
        )

        stats = {
            "total": 0,
            "pending_telegram": 0,
            "pending_discord": 0,
            "pending_total": 0,
            "approved": 0,
            "denied": 0,
        }

        if all_requests.data:
            stats["total"] = len(all_requests.data)
            pending_ids: set = set()
            for i, row in enumerate(all_requests.data):
                tg = row.get("telegram_status", "none")
                dc = row.get("discord_status", "none")
                if tg == "pending":
                    stats["pending_telegram"] += 1
                    pending_ids.add(i)
                if dc == "pending":
                    stats["pending_discord"] += 1
                    pending_ids.add(i)
                if tg == "approved" or dc == "approved":
                    stats["approved"] += 1
                if tg == "denied" or dc == "denied":
                    stats["denied"] += 1
            stats["pending_total"] = len(pending_ids)

        return stats

    except Exception:
        logger.exception("Error getting channel request stats")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics") from None


@router.get("/{request_id}", response_model=ChannelAccessRequestResponse)
async def get_channel_request(request_id: str, current_user=Depends(get_current_user_required)):
    """Get a specific channel access request by ID (admin/club_manager only)."""
    _require_admin_or_club_manager(current_user)

    try:
        result = (
            service_client.table("channel_access_requests")
            .select(
                "*, "
                "user_profiles!channel_access_requests_user_id_fkey(display_name, email), "
                "teams!channel_access_requests_team_id_fkey(name)"
            )
            .eq("id", request_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Channel access request not found")

        row = result.data[0]
        profile = row.pop("user_profiles", None) or {}
        team = row.pop("teams", None) or {}
        row["user_display_name"] = profile.get("display_name")
        row["user_email"] = profile.get("email")
        row["team_name"] = team.get("name")
        return row

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error getting channel request")
        raise HTTPException(status_code=500, detail="Failed to retrieve channel request") from None


@router.put("/{request_id}/status")
async def update_channel_request_status(
    request_id: str,
    status_update: ChannelAccessStatusUpdate,
    current_user=Depends(get_current_user_required),
):
    """
    Update the status for a specific platform on a channel access request (admin/club_manager only).

    Approves or denies one platform at a time. Does not affect the other platform's status.
    """
    _require_admin_or_club_manager(current_user)

    try:
        existing = service_client.table("channel_access_requests").select("*").eq("id", request_id).execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="Channel access request not found")

        reviewer_id = current_user.get("id") or current_user.get("user_id") or current_user.get("sub")
        now = datetime.utcnow().isoformat()
        platform = status_update.platform

        update_data = {
            f"{platform}_status": status_update.status,
            f"{platform}_reviewed_by": reviewer_id,
            f"{platform}_reviewed_at": now,
        }

        if status_update.admin_notes:
            update_data["admin_notes"] = status_update.admin_notes

        result = (
            service_client.table("channel_access_requests")
            .update(update_data)
            .eq("id", request_id)
            .execute()
        )

        if result.data:
            return {
                "success": True,
                "message": f"{platform.capitalize()} request {status_update.status}",
                "request": result.data[0],
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update channel request status")

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error updating channel request status")
        raise HTTPException(status_code=500, detail="Failed to update channel request status") from None


@router.delete("/{request_id}")
async def delete_channel_request(request_id: str, current_user=Depends(get_current_user_required)):
    """Delete a channel access request (admin only)."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete channel requests")

    try:
        existing = service_client.table("channel_access_requests").select("id").eq("id", request_id).execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="Channel access request not found")

        service_client.table("channel_access_requests").delete().eq("id", request_id).execute()

        return {"success": True, "message": "Channel access request deleted"}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error deleting channel request")
        raise HTTPException(status_code=500, detail="Failed to delete channel request") from None

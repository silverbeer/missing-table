"""
Match Event Data Access Object.

Handles all database operations related to live match events including:
- Goals
- Chat messages
- Status changes
- Cleanup of expired messages
"""

from datetime import UTC, datetime

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()


class MatchEventDAO(BaseDAO):
    """Data access object for match event operations (live match activity stream)."""

    def create_event(
        self,
        match_id: int,
        event_type: str,
        message: str,
        created_by: str | None = None,
        created_by_username: str | None = None,
        team_id: int | None = None,
        player_name: str | None = None,
        player_id: int | None = None,
        match_minute: int | None = None,
        extra_time: int | None = None,
        player_out_id: int | None = None,
    ) -> dict | None:
        """Create a new match event.

        Args:
            match_id: The match this event belongs to
            event_type: Type of event ('goal', 'message', 'status_change', 'substitution')
            message: Event message/description
            created_by: UUID of user who created the event
            created_by_username: Username of creator (denormalized for display)
            team_id: Team ID (for goal/substitution events)
            player_name: Player name (for goal events)
            player_id: Player ID from roster (for goal events, player coming on for subs)
            match_minute: Minute when event occurred (e.g., 22 for 22nd minute)
            extra_time: Stoppage/injury time minutes (e.g., 5 for 90+5)
            player_out_id: Player ID being substituted off (for substitution events)

        Returns:
            Created event record or None on error
        """
        try:
            data = {
                "match_id": match_id,
                "event_type": event_type,
                "message": message,
                "created_by": created_by,
                "created_by_username": created_by_username,
            }

            # Add optional fields for goal/substitution events
            if team_id is not None:
                data["team_id"] = team_id
            if player_name is not None:
                data["player_name"] = player_name
            if player_id is not None:
                data["player_id"] = player_id
            if match_minute is not None:
                data["match_minute"] = match_minute
            if extra_time is not None:
                data["extra_time"] = extra_time
            if player_out_id is not None:
                data["player_out_id"] = player_out_id

            response = self.client.table("match_events").insert(data).execute()

            if response.data:
                logger.info(
                    "match_event_created",
                    match_id=match_id,
                    event_type=event_type,
                    event_id=response.data[0].get("id"),
                )
                return response.data[0]
            return None

        except Exception:
            logger.exception(
                "Error creating match event",
                match_id=match_id,
                event_type=event_type,
            )
            return None

    def get_events(
        self,
        match_id: int,
        limit: int = 50,
        before_id: int | None = None,
    ) -> list[dict]:
        """Get paginated events for a match.

        Args:
            match_id: Match to get events for
            limit: Maximum number of events to return
            before_id: Return events with ID less than this (for pagination)

        Returns:
            List of event records, newest first
        """
        try:
            query = (
                self.client.table("match_events")
                .select("*")
                .eq("match_id", match_id)
                .eq("is_deleted", False)
                .order("created_at", desc=True)
                .limit(limit)
            )

            if before_id is not None:
                query = query.lt("id", before_id)

            response = query.execute()
            return response.data or []

        except Exception:
            logger.exception("Error getting match events", match_id=match_id)
            return []

    def get_event_by_id(self, event_id: int) -> dict | None:
        """Get a single event by ID.

        Args:
            event_id: The event ID

        Returns:
            Event record or None if not found
        """
        try:
            response = self.client.table("match_events").select("*").eq("id", event_id).single().execute()
            return response.data
        except Exception:
            logger.exception("Error getting match event", event_id=event_id)
            return None

    def soft_delete_event(self, event_id: int, deleted_by: str) -> bool:
        """Soft delete an event (for moderation).

        Args:
            event_id: Event to delete
            deleted_by: UUID of user performing deletion

        Returns:
            True if successful, False otherwise
        """
        try:
            response = (
                self.client.table("match_events")
                .update(
                    {
                        "is_deleted": True,
                        "deleted_by": deleted_by,
                        "deleted_at": datetime.now(UTC).isoformat(),
                    }
                )
                .eq("id", event_id)
                .execute()
            )

            if response.data:
                logger.info(
                    "match_event_deleted",
                    event_id=event_id,
                    deleted_by=deleted_by,
                )
                return True
            return False

        except Exception:
            logger.exception("Error deleting match event", event_id=event_id)
            return False

    def cleanup_expired_messages(self) -> int:
        """Delete message events that have expired (older than 10 days).

        This method is called by a Celery scheduled task.
        Only deletes events where:
        - event_type = 'message'
        - expires_at is in the past
        - is_deleted = false (don't process already deleted)

        Returns:
            Number of events deleted
        """
        try:
            now = datetime.now(UTC).isoformat()

            # First, get count of expired messages
            count_response = (
                self.client.table("match_events")
                .select("id", count="exact")
                .eq("event_type", "message")
                .eq("is_deleted", False)
                .lt("expires_at", now)
                .execute()
            )

            count = count_response.count or 0
            if count == 0:
                logger.info("match_events_cleanup_none_expired")
                return 0

            # Delete expired messages
            response = (
                self.client.table("match_events")
                .delete()
                .eq("event_type", "message")
                .eq("is_deleted", False)
                .lt("expires_at", now)
                .execute()
            )

            deleted = len(response.data) if response.data else 0
            logger.info(
                "match_events_cleanup_completed",
                deleted_count=deleted,
            )
            return deleted

        except Exception:
            logger.exception("Error cleaning up expired match events")
            return 0

    def get_events_count(self, match_id: int) -> int:
        """Get total count of active events for a match.

        Args:
            match_id: Match to count events for

        Returns:
            Number of active events
        """
        try:
            response = (
                self.client.table("match_events")
                .select("id", count="exact")
                .eq("match_id", match_id)
                .eq("is_deleted", False)
                .execute()
            )
            return response.count or 0
        except Exception:
            logger.exception("Error counting match events", match_id=match_id)
            return 0

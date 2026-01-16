"""
Maintenance Tasks

Tasks for routine maintenance operations like cleaning up expired data.
These tasks are typically scheduled to run periodically via Celery Beat.
"""

from celery import Task

from celery_app import app
from dao.match_dao import SupabaseConnection
from dao.match_event_dao import MatchEventDAO
from logging_config import get_logger

logger = get_logger(__name__)


class MaintenanceTask(Task):
    """
    Base task class for maintenance operations.

    Provides lazy-loaded database access for maintenance tasks.
    """

    _connection = None
    _match_event_dao = None

    @property
    def match_event_dao(self):
        """Lazy initialization of MatchEventDAO."""
        if self._match_event_dao is None:
            self._connection = SupabaseConnection()
            self._match_event_dao = MatchEventDAO(self._connection)
        return self._match_event_dao


@app.task(
    bind=True,
    base=MaintenanceTask,
    name="celery_tasks.maintenance_tasks.cleanup_expired_match_events",
)
def cleanup_expired_match_events(self):
    """
    Delete match event messages that have expired (older than 10 days).

    This task is scheduled to run daily via Celery Beat.
    Only message events are deleted - goals and status_change events are preserved.

    Returns:
        dict: Summary of cleanup operation with count of deleted messages.
    """
    logger.info("Starting cleanup of expired match events")

    try:
        deleted_count = self.match_event_dao.cleanup_expired_messages()

        logger.info(
            "Cleanup completed",
            deleted_count=deleted_count,
        )

        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Deleted {deleted_count} expired match event messages",
        }

    except Exception as e:
        logger.exception("Error during match events cleanup")
        return {
            "success": False,
            "deleted_count": 0,
            "error": str(e),
        }

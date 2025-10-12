"""
Match Processing Tasks

Tasks for processing match data from the match-scraper service.
These tasks run asynchronously in Celery workers, allowing for:
- Non-blocking match data ingestion
- Automatic retries on failure
- Horizontal scaling of processing capacity
"""

import logging
from typing import Dict, Any
from celery import Task
from celery_app import app
from dao.enhanced_data_access_fixed import EnhancedSportsDAO, SupabaseConnection
from celery_tasks.validation_tasks import validate_match_data

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """
    Base task class that provides database access.

    The _dao and _connection attributes are set as class attributes to ensure
    they're shared across all task executions in the same worker process.
    """
    _dao = None
    _connection = None

    @property
    def dao(self):
        """Lazy initialization of DAO to avoid creating connections at import time."""
        if self._dao is None:
            self._connection = SupabaseConnection()
            self._dao = EnhancedSportsDAO(self._connection)
        return self._dao


@app.task(
    bind=True,
    base=DatabaseTask,
    name='celery_tasks.match_tasks.process_match_data',
    max_retries=3,
    default_retry_delay=60,  # Retry after 1 minute
    autoretry_for=(Exception,),  # Auto-retry on any exception
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=600,  # Max 10 minutes backoff
    retry_jitter=True,  # Add random jitter to prevent thundering herd
)
def process_match_data(self: DatabaseTask, match_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process match data from match-scraper and insert into database.

    This task:
    1. Validates the match data
    2. Extracts/creates teams if needed
    3. Inserts or updates the match in the database
    4. Returns the created/updated match ID

    Args:
        match_data: Dictionary containing match information
            Required fields:
            - home_team: str
            - away_team: str
            - match_date: str (ISO format)
            - season: str
            - age_group: str
            - division: str
            Optional fields:
            - home_score: int
            - away_score: int
            - match_status: str
            - match_type: str
            - location: str

    Returns:
        Dict containing:
        - match_id: int - The database ID of the created/updated match
        - status: str - 'created' or 'updated'
        - message: str - Success message

    Raises:
        ValidationError: If match data is invalid
        DatabaseError: If database operation fails
    """
    try:
        logger.info(f"Processing match data: {match_data.get('home_team')} vs {match_data.get('away_team')}")

        # Step 1: Validate the match data
        validation_result = validate_match_data(match_data)
        if not validation_result['valid']:
            error_msg = f"Invalid match data: {validation_result['errors']}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Step 2: Extract team information
        home_team_name = match_data['home_team']
        away_team_name = match_data['away_team']

        logger.debug(f"Looking up teams: {home_team_name}, {away_team_name}")

        # Get or create teams
        home_team = self.dao.get_team_by_name(home_team_name)
        if not home_team:
            logger.warning(f"Home team not found: {home_team_name}. Creating placeholder.")
            # In Phase 4, we'll implement team creation from match-scraper data
            # For now, log and skip
            raise ValueError(f"Team not found: {home_team_name}")

        away_team = self.dao.get_team_by_name(away_team_name)
        if not away_team:
            logger.warning(f"Away team not found: {away_team_name}. Creating placeholder.")
            raise ValueError(f"Team not found: {away_team_name}")

        # Step 3: Check if match already exists (by external ID)
        external_match_id = match_data.get('external_match_id')
        existing_match = None
        if external_match_id:
            existing_match = self.dao.get_match_by_external_id(external_match_id)

        # Step 4: Insert or update match
        if existing_match:
            logger.info(f"Match already exists with ID {existing_match['id']}. Skipping duplicate.")
            result = {
                'match_id': existing_match['id'],
                'status': 'skipped',
                'message': f"Match already exists: {home_team_name} vs {away_team_name}"
            }
        else:
            logger.info(f"Creating new match: {home_team_name} vs {away_team_name}")
            match_id = self.dao.create_match(
                home_team_id=home_team['id'],
                away_team_id=away_team['id'],
                match_date=match_data['match_date'],
                season=match_data['season'],
                home_score=match_data.get('home_score'),
                away_score=match_data.get('away_score'),
                match_status=match_data.get('match_status', 'scheduled'),
                location=match_data.get('location'),
                source='match-scraper',
                match_id=external_match_id,
            )
            if match_id:
                result = {
                    'match_id': match_id,
                    'status': 'created',
                    'message': f"Created match: {home_team_name} vs {away_team_name}"
                }
            else:
                raise Exception("Failed to create match")

        logger.info(f"Successfully processed match: {result}")
        return result

    except Exception as e:
        logger.error(f"Error processing match data: {e}", exc_info=True)
        # Celery will auto-retry based on configuration
        raise

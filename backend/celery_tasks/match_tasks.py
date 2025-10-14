"""
Match Processing Tasks

Tasks for processing match data from the match-scraper service.
These tasks run asynchronously in Celery workers, allowing for:
- Non-blocking match data ingestion
- Automatic retries on failure
- Horizontal scaling of processing capacity
"""

from typing import Dict, Any
from celery import Task
from celery_app import app
from dao.enhanced_data_access_fixed import EnhancedSportsDAO, SupabaseConnection
from celery_tasks.validation_tasks import validate_match_data
from logging_config import get_logger

logger = get_logger(__name__)


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

    def _check_needs_update(self, existing_match: Dict[str, Any], new_data: Dict[str, Any]) -> bool:
        """
        Check if the existing match needs to be updated based on new data.

        Returns True if any of these conditions are met:
        - Status changed (scheduled → played)
        - Scores changed (were null, now have values)
        - Scores were updated (different values)
        """
        # Check status change
        existing_status = existing_match.get('match_status', 'scheduled')
        new_status = new_data.get('match_status', 'scheduled')
        if existing_status != new_status:
            logger.debug(f"Status changed: {existing_status} → {new_status}")
            return True

        # Check score changes
        existing_home_score = existing_match.get('home_score')
        existing_away_score = existing_match.get('away_score')
        new_home_score = new_data.get('home_score')
        new_away_score = new_data.get('away_score')

        # If new data has scores and they differ from existing
        if new_home_score is not None and new_away_score is not None:
            if (existing_home_score != new_home_score or
                existing_away_score != new_away_score):
                logger.debug(f"Scores changed: {existing_home_score}-{existing_away_score} → {new_home_score}-{new_away_score}")
                return True

        return False

    def _update_match_scores(self, existing_match: Dict[str, Any], new_data: Dict[str, Any]) -> bool:
        """
        Update an existing match's scores and status.

        This is a simplified update that only changes scores and status,
        preserving all other match data.
        """
        try:
            match_id = existing_match['id']

            # Prepare update data
            update_data = {}

            # Update scores if provided
            if new_data.get('home_score') is not None:
                update_data['home_score'] = new_data['home_score']
            if new_data.get('away_score') is not None:
                update_data['away_score'] = new_data['away_score']

            # Update status if provided
            if new_data.get('match_status'):
                update_data['match_status'] = new_data['match_status']

            # Note: updated_by field expects UUID, not string.
            # For match-scraper updates, we'll skip this field since it's optional.
            # If we need to track match-scraper updates, we should use 'source' field instead.

            if not update_data:
                logger.warning(f"No update data provided for match {match_id}")
                return False

            # Execute update directly on matches table
            response = (
                self.dao.client.table("matches")
                .update(update_data)
                .eq("id", match_id)
                .execute()
            )

            if response.data:
                logger.info(f"Successfully updated match {match_id}: {update_data}")
                return True
            else:
                logger.error(f"Update returned no data for match {match_id}")
                return False

        except Exception as e:
            logger.error(f"Error updating match scores: {e}", exc_info=True)
            return False


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

        # Step 3: Check if match already exists
        external_match_id = match_data.get('external_match_id')
        existing_match = None

        # First try: Look up by external ID (fast path for previously scraped matches)
        if external_match_id:
            existing_match = self.dao.get_match_by_external_id(external_match_id)
            logger.debug(f"Lookup by external_match_id '{external_match_id}': {'found' if existing_match else 'not found'}")

        # Second try: Fallback to lookup by teams + date (for manually-entered matches)
        if not existing_match:
            existing_match = self.dao.get_match_by_teams_and_date(
                home_team_id=home_team['id'],
                away_team_id=away_team['id'],
                match_date=match_data['match_date']
            )

            if existing_match:
                logger.info(
                    f"Found manually-entered match via fallback lookup: "
                    f"{home_team_name} vs {away_team_name} on {match_data['match_date']}"
                )

                # If found a match without external_match_id, populate it
                if external_match_id and not existing_match.get('match_id'):
                    logger.info(f"Populating match_id '{external_match_id}' on existing match {existing_match['id']}")
                    success = self.dao.update_match_external_id(
                        match_id=existing_match['id'],
                        external_match_id=external_match_id
                    )
                    if success:
                        # Update the existing_match dict to reflect the new match_id
                        existing_match['match_id'] = external_match_id
                        existing_match['source'] = 'match-scraper'
                        logger.info(f"Successfully populated match_id on match {existing_match['id']}")
                    else:
                        logger.warning(f"Failed to populate match_id on match {existing_match['id']}")

        # Step 4: Insert or update match
        if existing_match:
            # Check if this is a score update
            needs_update = self._check_needs_update(existing_match, match_data)

            if needs_update:
                logger.info(f"Updating existing match {existing_match['id']}: {home_team_name} vs {away_team_name}")
                success = self._update_match_scores(existing_match, match_data)

                if success:
                    result = {
                        'match_id': existing_match['id'],
                        'status': 'updated',
                        'message': f"Updated match scores: {home_team_name} vs {away_team_name}"
                    }
                else:
                    raise Exception(f"Failed to update match {existing_match['id']}")
            else:
                logger.info(f"Match already exists with ID {existing_match['id']}. No changes needed.")
                result = {
                    'match_id': existing_match['id'],
                    'status': 'skipped',
                    'message': f"Match unchanged: {home_team_name} vs {away_team_name}"
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

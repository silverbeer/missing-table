"""
Celery Tasks Module

This module contains all Celery tasks for distributed processing.

Task Categories:
- match_tasks: Processing match data from match-scraper
- validation_tasks: Validating match data before database insertion
"""

from celery_tasks.match_tasks import process_match_data
from celery_tasks.validation_tasks import validate_match_data

__all__ = ["process_match_data", "validate_match_data"]

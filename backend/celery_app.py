"""
Celery Application Configuration

This module configures the Celery application for distributed task processing.
Workers can run separately from the FastAPI application, allowing for:
- Async processing of match data from match-scraper
- Horizontal scaling of workers
- Fault tolerance and automatic retries
- Task result tracking via Redis

Usage:
    # Start worker
    celery -A celery_app worker --loglevel=info

    # Submit task from application
    from celery_app import process_match_data
    task = process_match_data.delay(match_data)
"""

import os
from celery import Celery
from kombu import Exchange, Queue

# Celery broker and result backend configuration
# These can be overridden with environment variables
# Default to cluster-internal names, fallback to localhost for local development
BROKER_URL = os.getenv(
    'CELERY_BROKER_URL',
    os.getenv('RABBITMQ_URL', 'amqp://admin:admin123@localhost:5672//')  # pragma: allowlist secret
)
RESULT_BACKEND = os.getenv(
    'CELERY_RESULT_BACKEND',
    os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

# Create Celery app instance
app = Celery(
    'missing_table',
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
)

# Celery configuration
app.conf.update(
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',

    # Timezone
    timezone='UTC',
    enable_utc=True,

    # Task tracking
    task_track_started=True,
    task_time_limit=300,  # 5 minutes hard limit
    task_soft_time_limit=240,  # 4 minutes soft limit

    # Results
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store additional task metadata

    # Retries
    task_acks_late=True,  # Acknowledge task after completion, not on receive
    task_reject_on_worker_lost=True,  # Requeue task if worker dies

    # Worker configuration
    worker_prefetch_multiplier=1,  # Worker fetches 1 task at a time (fair distribution)
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (prevent memory leaks)

    # Task routing
    task_routes={
        'celery_tasks.match_tasks.*': {'queue': 'match_processing'},
        'celery_tasks.validation_tasks.*': {'queue': 'validation'},
    },

    # Queue configuration
    task_queues=(
        Queue('match_processing', Exchange('match_processing'), routing_key='match.*'),
        Queue('validation', Exchange('validation'), routing_key='validation.*'),
        Queue('celery', Exchange('celery'), routing_key='celery'),  # Default queue
    ),

    # Monitoring
    task_send_sent_event=True,  # Enable task-sent events
    worker_send_task_events=True,  # Enable worker task events
)

# Auto-discover tasks in celery_tasks module
app.autodiscover_tasks(['celery_tasks'])

if __name__ == '__main__':
    app.start()

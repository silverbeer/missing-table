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
from celery.schedules import crontab
from kombu import Exchange, Queue

# Celery broker and result backend configuration
# These can be overridden with environment variables
# Default to cluster-internal names, fallback to localhost for local development
BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    os.getenv("RABBITMQ_URL", "amqp://admin:admin123@localhost:5672//"),  # pragma: allowlist secret
)
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0"))

# MT Power Rating (SB-1807). Its own queue so the prod worker consumes it
# explicitly (`--queues=matches.prod,power_rating`); the worker runs the beat
# embedded, single replica (k3s/worker/deployment-prod.yaml).
POWER_RATING_QUEUE = "power_rating"

# Celery beat. Nothing here runs unless a beat process does: the k3s prod
# worker starts one with `--beat`.
BEAT_SCHEDULE = {
    # Design default 10:00 UTC; move to just after the nightly reconcile
    # (SB-1787) once that schedule is fixed.
    "power-rating-nightly": {
        "task": "power_rating.recompute_all",
        "schedule": crontab(hour=10, minute=0),
        "options": {"queue": POWER_RATING_QUEUE},
    },
}

# Create Celery app instance
app = Celery(
    "missing_table",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
)

# Celery configuration
app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
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
        "celery_tasks.match_tasks.*": {"queue": "match_processing"},
        "celery_tasks.validation_tasks.*": {"queue": "validation"},
        "power_rating.*": {"queue": POWER_RATING_QUEUE},
    },
    # Queue configuration
    task_queues=(
        Queue("match_processing", Exchange("match_processing"), routing_key="match.*"),
        Queue("validation", Exchange("validation"), routing_key="validation.*"),
        Queue("celery", Exchange("celery"), routing_key="celery"),  # Default queue
        # Legacy direct queue: MSA pods configured with AGENT_QUEUE_NAME=matches.prod
        # bypass the fanout exchange and publish here. Worker must consume both until
        # all pods are switched back to using the matches-fanout exchange.
        Queue("matches.prod"),
        Queue(POWER_RATING_QUEUE),
    ),
    # Scheduled tasks (Celery beat)
    beat_schedule=BEAT_SCHEDULE,
    # Monitoring
    task_send_sent_event=True,  # Enable task-sent events
    worker_send_task_events=True,  # Enable worker task events
)

# Auto-discover tasks in celery_tasks module
app.autodiscover_tasks(["celery_tasks"])

if __name__ == "__main__":
    app.start()

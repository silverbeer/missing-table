"""MT Power Rating nightly recompute (SB-1807).

Scheduled by Celery beat (`beat_schedule` in celery_app.py, 10:00 UTC) and
consumed by the k3s prod worker, which runs the beat embedded (`--beat`, see
k3s/worker/deployment-prod.yaml). The same `recompute` backs
POST /api/admin/power-rating/recompute.

An unchanged input writes nothing, so a second run in a day (a manual trigger,
a redelivered message) costs a few reads and changes nothing.
"""

from celery import Task

from celery_app import app
from dao.match_dao import SupabaseConnection
from dao.power_rating_dao import PowerRatingDAO
from logging_config import get_logger
from services.power_rating_service import recompute

logger = get_logger(__name__)

TASK_NAME = "power_rating.recompute_all"


class PowerRatingTask(Task):
    """Lazy DAO, built on first run rather than at import (the worker imports every task)."""

    _dao = None

    @property
    def dao(self) -> PowerRatingDAO:
        if self._dao is None:
            self._dao = PowerRatingDAO(SupabaseConnection())
        return self._dao


@app.task(bind=True, base=PowerRatingTask, name=TASK_NAME)
def recompute_all(self) -> dict:
    """Recompute U15/U16/U17/U19 Homegrown for the current season; returns the summary."""
    summary = recompute(self.dao)
    logger.info(
        "power_rating_nightly_done",
        season_id=summary.season_id,
        statuses={s.age_group: s.status for s in summary.age_groups},
    )
    return summary.model_dump(mode="json")

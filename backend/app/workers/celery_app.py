"""Celery application and beat schedule configuration."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "ofmaint",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.sla_tasks",
        "app.workers.pm_tasks",
        "app.workers.email_tasks",
        "app.workers.budget_tasks",
        "app.workers.rollup_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 min hard limit
    task_soft_time_limit=240,  # 4 min soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

celery_app.conf.beat_schedule = {
    "check-sla-breaches": {
        "task": "app.workers.sla_tasks.check_sla_breaches",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "generate-pm-work-orders": {
        "task": "app.workers.pm_tasks.generate_pm_work_orders",
        "schedule": crontab(hour=6, minute=0),  # Daily at 06:00 UTC
    },
    "send-pm-reminders": {
        "task": "app.workers.pm_tasks.send_pm_reminders",
        "schedule": crontab(hour=8, minute=0),  # Daily at 08:00 UTC
    },
    "precompute-dashboard-rollups": {
        "task": "app.workers.rollup_tasks.precompute_dashboard_rollups",
        "schedule": crontab(minute="*/2"),  # Every 2 minutes
    },
}

"""Celery Application Setup."""

from celery import Celery

from backend.app.core.config import settings

celery = Celery(
    "enterprise_sales_agent_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery.conf.update(
    task_default_queue=settings.CELERY_TASK_DEFAULT_QUEUE,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=getattr(settings, "RADAR_TIMEZONE", "UTC"),
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "poll-outbox-events-every-30s": {
            "task": "tasks.poll_outbox_events",
            "schedule": 30.0,
        },
    },
)

# Auto-discover tasks in backend.app.tasks package
celery.autodiscover_tasks(["backend.app.tasks"])

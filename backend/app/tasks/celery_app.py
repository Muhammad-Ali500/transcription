from celery import Celery
from celery.signals import worker_ready

from app.config import settings

celery_app = Celery(
    "transcription_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)


@worker_ready.connect
def preload_models(**kwargs):
    from app.services.transcription_service import TranscriptionService
    TranscriptionService.preload()


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    include=[
        "app.tasks.transcription_tasks",
        "app.tasks.segmentation_tasks",
    ],
    task_routes={
        "transcription.*": {"queue": "transcription"},
        "segmentation.*": {"queue": "segmentation"},
        "pipeline.*": {"queue": "segmentation"},
    },
    task_queues={
        "transcription": {"exchange": "transcription", "routing_key": "transcription"},
        "segmentation": {"exchange": "segmentation", "routing_key": "segmentation"},
    },
    worker_concurrency=2,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=30,
    task_max_retries=3,
    result_expires=86400,
    worker_send_task_events=True,
    task_send_sent_event=True,
)

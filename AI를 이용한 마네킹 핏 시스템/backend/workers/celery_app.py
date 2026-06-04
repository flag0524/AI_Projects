"""
Celery 앱 설정.

실행:
  celery -A workers.celery_app worker --loglevel=info -Q tryon --concurrency=1
"""
from celery import Celery
from config import settings

celery_app = Celery(
    "mannequin_fit",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=settings.job_ttl_seconds,
    task_track_started=True,
    task_acks_late=True,          # 작업 완료 후 ack (실패 시 재시도 가능)
    worker_prefetch_multiplier=1, # GPU 작업: 동시에 1개만 처리
    task_routes={
        "workers.tasks.tryon_task":   {"queue": "tryon"},
        "workers.tasks.layered_task": {"queue": "tryon"},
    },
    task_annotations={
        "workers.tasks.tryon_task": {
            "max_retries": 2,
            "default_retry_delay": 5,
        },
    },
)

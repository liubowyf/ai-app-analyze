"""Celery application configuration."""
from celery import Celery

from core.config import settings

# 使用RabbitMQ作为broker和result backend
celery_app: Celery = Celery(
    "workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=3600,  # 1 hour timeout
    task_soft_time_limit=3300,  # 55 minutes soft timeout
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    result_expires=86400,  # 24 hours
    task_ignore_result=False,  # Ensure results are stored
    # AMQP specific settings
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=5,
    broker_connection_retry_delay=5,
    # Task routing - send different task types to different queues
    task_routes={
        "workers.static_analyzer.*": {"queue": "static"},
        "workers.dynamic_analyzer.*": {"queue": "dynamic"},
        "workers.report_generator.*": {"queue": "report"},
    },
    # Task default queue
    task_default_queue="default",
)

# Autodiscover tasks from modules
celery_app.autodiscover_tasks(["workers"])

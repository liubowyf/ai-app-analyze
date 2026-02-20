"""Celery workers module."""
from workers.celery_app import celery_app

# Import tasks to register them with Celery
from workers import static_analyzer
from workers import dynamic_analyzer
from workers import report_generator

__all__ = ["celery_app", "static_analyzer", "dynamic_analyzer", "report_generator"]

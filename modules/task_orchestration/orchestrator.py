"""Workflow orchestration utilities for analysis tasks."""

from __future__ import annotations

import logging
from typing import Optional

from celery import chain
from celery.canvas import Signature

from models.task import TaskPriority
from workers.dynamic_analyzer import run_dynamic_analysis
from workers.report_generator import generate_report
from workers.static_analyzer import run_static_analysis

logger = logging.getLogger(__name__)


_PRIORITY_MAP = {
    TaskPriority.URGENT: 0,
    TaskPriority.NORMAL: 5,
    TaskPriority.BATCH: 9,
}


def _resolve_priority(priority: Optional[object]) -> int:
    if isinstance(priority, TaskPriority):
        return _PRIORITY_MAP.get(priority, 5)
    if isinstance(priority, str):
        for level in TaskPriority:
            if level.value == priority:
                return _PRIORITY_MAP[level]
    return 5


def build_analysis_workflow(task_id: str, include_static: bool = True) -> Signature:
    """
    Build Celery workflow for one task.

    Use immutable signatures (`si`) where we must pin `task_id` and ignore
    previous stage payloads, so the chain is stable regardless of return shapes.
    """
    if include_static:
        return chain(
            run_static_analysis.si(task_id),
            run_dynamic_analysis.si(task_id),
            generate_report.s(),
        )
    return chain(
        run_dynamic_analysis.si(task_id),
        generate_report.s(),
    )


def enqueue_analysis_workflow(
    task_id: str,
    include_static: bool = True,
    priority: Optional[object] = None,
) -> bool:
    """Enqueue analysis workflow and return whether enqueue succeeds."""
    workflow = build_analysis_workflow(task_id=task_id, include_static=include_static)
    celery_priority = _resolve_priority(priority)
    try:
        workflow.apply_async(priority=celery_priority)
        return True
    except Exception as exc:
        logger.warning(
            "Failed to enqueue workflow task_id=%s include_static=%s priority=%s: %s",
            task_id,
            include_static,
            celery_priority,
            exc,
        )
        return False

"""Workflow orchestration helpers (Dramatiq-only)."""

from __future__ import annotations

import importlib
import logging
from typing import Optional

from models.task import TaskPriority

logger = logging.getLogger(__name__)

_STAGE_FLOW_WITH_STATIC = ("static", "dynamic", "report")
_STAGE_FLOW_DYNAMIC_ONLY = ("dynamic", "report")


def _resolve_priority_label(priority: Optional[object]) -> str:
    """Normalize priority object into stable label for logging."""
    if isinstance(priority, TaskPriority):
        return priority.value
    if isinstance(priority, str):
        normalized = priority.strip().lower()
        if normalized in {level.value for level in TaskPriority}:
            return normalized
    return TaskPriority.NORMAL.value


def build_analysis_workflow(task_id: str, include_static: bool = True) -> tuple[str, tuple[str, ...]]:
    """Build deterministic workflow descriptor for one task."""
    stages = _STAGE_FLOW_WITH_STATIC if include_static else _STAGE_FLOW_DYNAMIC_ONLY
    return task_id, stages


def enqueue_analysis_workflow(
    task_id: str,
    include_static: bool = True,
    priority: Optional[object] = None,
) -> bool:
    """
    Enqueue analysis workflow through Dramatiq actor.

    `include_static` and `priority` are kept for compatibility with existing call sites.
    The state machine decides actual next stage from persisted status.
    """
    _task_id, stages = build_analysis_workflow(task_id=task_id, include_static=include_static)
    priority_label = _resolve_priority_label(priority)
    try:
        task_actor_module = importlib.import_module("workers.task_actor")
        run_task = getattr(task_actor_module, "run_task", None)
        if run_task is None or not hasattr(run_task, "send"):
            logger.warning("Dramatiq actor unavailable, cannot enqueue task_id=%s", task_id)
            return False
        run_task.send(task_id)
        logger.info(
            "Enqueued Dramatiq workflow task_id=%s include_static=%s priority=%s stages=%s",
            task_id,
            include_static,
            priority_label,
            ",".join(stages),
        )
        return True
    except Exception as exc:
        logger.warning(
            "Failed to enqueue Dramatiq workflow task_id=%s include_static=%s priority=%s: %s",
            task_id,
            include_static,
            priority_label,
            exc,
        )
        return False


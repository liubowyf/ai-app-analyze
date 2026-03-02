"""Stage service functions used by Dramatiq actor runtime."""

from __future__ import annotations

from typing import Any, Optional


def run_static_stage(task_id: str) -> dict:
    """Run static stage."""
    from workers.static_analyzer import _run_static_stage_impl

    return _run_static_stage_impl(task_id)


def run_dynamic_stage(
    task_id: str,
    retry_context: Optional[object] = None,
) -> dict:
    """Run dynamic stage with optional retry context."""
    from workers.dynamic_analyzer import _run_dynamic_stage_impl

    return _run_dynamic_stage_impl(task_id, retry_context=retry_context)


def run_report_stage(task_id: Any) -> dict:
    """Run report stage."""
    from workers.report_generator import _run_report_stage_impl

    return _run_report_stage_impl(task_id)

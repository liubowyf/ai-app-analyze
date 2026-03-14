"""MySQL-backed task stage state machine helpers."""

from __future__ import annotations

from typing import Iterable, Optional

from models.task import TaskStatus

_STAGE_BY_STATUS = {
    TaskStatus.QUEUED.value: "static",
    TaskStatus.STATIC_ANALYZING.value: "dynamic",
    TaskStatus.DYNAMIC_ANALYZING.value: "report",
    TaskStatus.REPORT_GENERATING.value: "report",
    TaskStatus.STATIC_FAILED.value: "static",
    TaskStatus.DYNAMIC_FAILED.value: "dynamic",
}

_NEXT_STATUS_BY_STAGE = {
    "static": TaskStatus.STATIC_ANALYZING.value,
    "dynamic": TaskStatus.DYNAMIC_ANALYZING.value,
    "report": TaskStatus.REPORT_GENERATING.value,
}

_TERMINAL_STATUSES = {
    TaskStatus.COMPLETED.value,
    TaskStatus.STATIC_FAILED.value,
    TaskStatus.DYNAMIC_FAILED.value,
}


def _normalize_status(status: object) -> str:
    if isinstance(status, TaskStatus):
        return status.value
    return str(status).strip().lower()


def next_stage(status: object) -> Optional[str]:
    """Resolve next stage name from persisted task status."""
    return _STAGE_BY_STATUS.get(_normalize_status(status))


def next_status_after_stage(stage: str) -> str:
    """Resolve status written after one stage execution."""
    normalized_stage = str(stage).strip().lower()
    if normalized_stage not in _NEXT_STATUS_BY_STAGE:
        raise ValueError(f"Unsupported stage: {stage}")
    return _NEXT_STATUS_BY_STAGE[normalized_stage]


def is_terminal_status(status: object) -> bool:
    """Check whether task status is terminal."""
    return _normalize_status(status) in _TERMINAL_STATUSES


def get_retry_delay_seconds(retry_count: int, delays: Iterable[int]) -> int:
    """Return retry delay by count, capping to the last configured delay."""
    delay_list = [int(x) for x in delays]
    if not delay_list:
        raise ValueError("Retry delays must not be empty")
    idx = max(0, min(int(retry_count), len(delay_list) - 1))
    return max(0, delay_list[idx])


def manual_retry_status(
    current_status: object,
    *,
    has_static_result: bool,
    last_success_stage: object | None = None,
) -> TaskStatus:
    """Resolve which stage a manual retry should resume from."""
    normalized = _normalize_status(current_status)
    last_success = str(last_success_stage or "").strip().lower()

    if normalized in {
        TaskStatus.DYNAMIC_ANALYZING.value,
        TaskStatus.REPORT_GENERATING.value,
        TaskStatus.COMPLETED.value,
        TaskStatus.DYNAMIC_FAILED.value,
    }:
        return TaskStatus.DYNAMIC_ANALYZING if has_static_result or last_success in {"static", "dynamic", "report"} else TaskStatus.QUEUED

    if has_static_result or last_success in {"static", "dynamic", "report"}:
        return TaskStatus.DYNAMIC_ANALYZING
    return TaskStatus.QUEUED

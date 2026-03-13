"""Normalize persisted task statuses for frontend presentation."""

from __future__ import annotations


def present_task_status(raw_status: object, last_success_stage: object | None = None) -> str:
    status = str(getattr(raw_status, "value", raw_status) or "").strip().lower()
    if status in {
        "queued",
        "static_analyzing",
        "dynamic_analyzing",
        "report_generating",
        "completed",
        "static_failed",
        "dynamic_failed",
    }:
        return status

    if status in {"pending", ""}:
        return "queued"

    if status == "failed":
        stage = str(last_success_stage or "").strip().lower()
        if stage in {"static", "dynamic", "report"}:
            return "dynamic_failed"
        return "static_failed"

    return "queued"

"""Tests for stuck-task reason classification in scheduling snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from scripts.scheduling_window_snapshot import collect_scheduling_window_snapshot


@dataclass
class _TaskRow:
    id: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = 0
    error_message: str | None = None


def test_snapshot_outputs_stuck_status_and_age_buckets():
    now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=UTC)
    rows = [
        _TaskRow("a", "queued", now - timedelta(minutes=6)),
        _TaskRow("b", "queued", now - timedelta(minutes=20)),
        _TaskRow("c", "static_analyzing", now - timedelta(minutes=35)),
    ]

    with patch("scripts.scheduling_window_snapshot._query_window_tasks", return_value=rows), patch(
        "scripts.scheduling_window_snapshot.get_backend_runtime_diagnostics",
        return_value={"backend": "dramatiq", "dramatiq_ready": True, "fallback_reason": None},
    ), patch(
        "scripts.scheduling_window_snapshot.build_rollback_readiness_report",
        return_value={"rollback_ready": True},
    ):
        snapshot = collect_scheduling_window_snapshot(minutes=60, now=now, stuck_seconds=300)

    assert snapshot["stuck_tasks"] == 3
    assert snapshot["stuck_by_status"] == {"queued": 2, "static_analyzing": 1}
    assert snapshot["stuck_by_age_bucket"] == {">5m": 3, ">15m": 2, ">30m": 1}


def test_snapshot_marks_retry_backoff_when_stuck_retries_dominate():
    now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=UTC)
    rows = [
        _TaskRow("r1", "queued", now - timedelta(minutes=12), retry_count=2),
        _TaskRow("r2", "queued", now - timedelta(minutes=9), retry_count=1),
    ]

    with patch("scripts.scheduling_window_snapshot._query_window_tasks", return_value=rows), patch(
        "scripts.scheduling_window_snapshot.get_backend_runtime_diagnostics",
        return_value={"backend": "dramatiq", "dramatiq_ready": True, "fallback_reason": None},
    ), patch(
        "scripts.scheduling_window_snapshot.build_rollback_readiness_report",
        return_value={"rollback_ready": True},
    ):
        snapshot = collect_scheduling_window_snapshot(minutes=30, now=now, stuck_seconds=300)

    assert snapshot["suspected_reason"] == "retry_backoff"

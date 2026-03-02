"""Tests for scheduling window snapshot aggregation script."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from scripts.scheduling_window_snapshot import collect_scheduling_window_snapshot


@dataclass
class _TaskRow:
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = 0


def test_collect_scheduling_snapshot_aggregates_window_metrics():
    now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=UTC)
    rows = [
        _TaskRow("completed", now - timedelta(minutes=20), now - timedelta(minutes=19), now - timedelta(minutes=10), 0),
        _TaskRow("failed", now - timedelta(minutes=18), now - timedelta(minutes=17), now - timedelta(minutes=16), 1),
        _TaskRow("completed", now - timedelta(minutes=15), now - timedelta(minutes=14), now - timedelta(minutes=8), 1),
        _TaskRow("queued", now - timedelta(minutes=12), None, None, 0),
        _TaskRow("dynamic_analyzing", now - timedelta(minutes=11), now - timedelta(minutes=10), None, 0),
    ]

    with patch("scripts.scheduling_window_snapshot._query_window_tasks", return_value=rows), patch(
        "scripts.scheduling_window_snapshot.get_backend_runtime_diagnostics",
        return_value={"backend": "dramatiq", "dramatiq_ready": True, "fallback_reason": None},
    ), patch(
        "scripts.scheduling_window_snapshot.build_rollback_readiness_report",
        return_value={"rollback_ready": True},
    ):
        snapshot = collect_scheduling_window_snapshot(minutes=30, now=now, stuck_seconds=300)

    assert snapshot["backend"] == "dramatiq"
    assert snapshot["can_enqueue"] is True
    assert snapshot["rollback_ready"] is True
    assert snapshot["queued_count"] == 1
    assert snapshot["running_count"] == 1
    assert snapshot["completed_count"] == 2
    assert snapshot["failed_count"] == 1
    assert snapshot["retrying_count"] == 2
    assert snapshot["stuck_tasks"] >= 1
    assert snapshot["success_rate"] == 0.6667
    assert snapshot["retry_recovered_rate"] == 0.5
    assert snapshot["p95_queue_to_start_seconds"] > 0


def test_collect_scheduling_snapshot_handles_empty_window_with_reason():
    now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=UTC)
    with patch("scripts.scheduling_window_snapshot._query_window_tasks", return_value=[]), patch(
        "scripts.scheduling_window_snapshot.get_backend_runtime_diagnostics",
        return_value={"backend": "dramatiq", "dramatiq_ready": False, "fallback_reason": "dramatiq_not_ready"},
    ), patch(
        "scripts.scheduling_window_snapshot.build_rollback_readiness_report",
        return_value={"rollback_ready": True},
    ):
        snapshot = collect_scheduling_window_snapshot(minutes=30, now=now)

    assert snapshot["window_reason"] == "no_tasks_in_window"
    assert snapshot["total_tasks"] == 0
    assert snapshot["success_rate"] == 0.0
    assert snapshot["stuck_tasks"] == 0
    assert snapshot["backend"] == "dramatiq"
    assert snapshot["can_enqueue"] is False


def test_collect_scheduling_snapshot_handles_naive_datetimes_from_db():
    now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=UTC)
    naive_created = datetime(2026, 3, 2, 11, 40, 0)
    naive_started = datetime(2026, 3, 2, 11, 41, 0)
    rows = [
        _TaskRow("queued", naive_created, None, None, 0),
        _TaskRow("completed", naive_created, naive_started, datetime(2026, 3, 2, 11, 55, 0), 0),
    ]
    with patch("scripts.scheduling_window_snapshot._query_window_tasks", return_value=rows), patch(
        "scripts.scheduling_window_snapshot.get_backend_runtime_diagnostics",
        return_value={"backend": "dramatiq", "dramatiq_ready": True, "fallback_reason": None},
    ), patch(
        "scripts.scheduling_window_snapshot.build_rollback_readiness_report",
        return_value={"rollback_ready": True},
    ):
        snapshot = collect_scheduling_window_snapshot(minutes=30, now=now)

    assert snapshot["total_tasks"] == 2
    assert snapshot["queued_count"] == 1
    assert snapshot["p95_queue_to_start_seconds"] == 60

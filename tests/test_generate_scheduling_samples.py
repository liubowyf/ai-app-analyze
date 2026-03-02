"""Tests for scheduling sample generation and probe transition path."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from scripts.generate_scheduling_samples import generate_scheduling_samples, run_probe_transition


@dataclass
class _FakeTask:
    id: str | None = None
    apk_file_name: str = "probe.apk"
    apk_file_size: int = 1
    apk_md5: str = "md5"
    apk_storage_path: str = "/tmp/probe.apk"
    status: str = "pending"
    priority: str = "normal"
    retry_count: int = 0
    error_message: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    transitions: list[str] = field(default_factory=list)


class _FakeSession:
    def __init__(self):
        self.rows: list[_FakeTask] = []
        self._counter = 0

    def add(self, task):
        if not task.id:
            self._counter += 1
            task.id = f"task-{self._counter}"
        self.rows.append(task)

    def flush(self):
        return None

    def commit(self):
        return None

    def close(self):
        return None


def test_run_probe_transition_moves_through_full_status_chain():
    base_time = datetime(2026, 3, 2, 12, 0, 0, tzinfo=UTC)
    task = _FakeTask(created_at=base_time)

    transitions = run_probe_transition(task, base_time=base_time)

    assert transitions == [
        "pending",
        "queued",
        "static_analyzing",
        "dynamic_analyzing",
        "report_generating",
        "completed",
    ]
    assert task.status == "completed"
    assert task.started_at is not None
    assert task.completed_at is not None


def test_generate_scheduling_samples_builds_non_stuck_summary():
    fake_db = _FakeSession()
    now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=UTC)

    report = generate_scheduling_samples(
        count=10,
        timeout_seconds=120,
        db=fake_db,
        now=now,
        task_class=_FakeTask,
    )

    assert report["total_tasks"] == 10
    assert report["completed"] == 10
    assert report["failed"] == 0
    assert report["retrying"] == 0
    assert report["stuck"] == 0
    assert report["success_rate"] == 1.0
    assert report["p95_queue_to_start_seconds"] >= 1

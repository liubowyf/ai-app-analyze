"""Tests for stage run tracker helpers."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from modules.task_orchestration.run_tracker import finish_stage_run, start_stage_run


def test_start_stage_run_creates_running_record():
    db = MagicMock()
    with patch("modules.task_orchestration.run_tracker.ensure_analysis_run_table"), patch(
        "modules.task_orchestration.run_tracker._next_attempt", return_value=3
    ):
        run = start_stage_run(
            db,
            task_id="task-1",
            stage="dynamic",
            emulator="10.0.0.1:5555",
            details={"foo": "bar"},
        )

    assert run.task_id == "task-1"
    assert run.stage == "dynamic"
    assert run.attempt == 3
    assert run.status == "running"
    assert run.emulator == "10.0.0.1:5555"
    assert run.details == {"foo": "bar"}
    db.add.assert_called_once()
    db.flush.assert_called_once()


def test_finish_stage_run_updates_latest_running_row():
    started = datetime.utcnow() - timedelta(seconds=8)
    run = MagicMock()
    run.started_at = started
    run.status = "running"
    q = MagicMock()
    q.filter.return_value.order_by.return_value.first.return_value = run
    db = MagicMock()
    db.query.return_value = q

    finish_stage_run(
        db,
        task_id="task-2",
        stage="report",
        success=False,
        error_message="boom",
        details={"phase": "render"},
    )

    assert run.status == "failed"
    assert run.error_message == "boom"
    assert run.duration_seconds >= 0
    assert run.details == {"phase": "render"}

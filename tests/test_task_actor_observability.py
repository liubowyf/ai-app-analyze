"""Tests for task actor transition observability logs."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from models.task import TaskStatus
from workers.task_actor import run_task


def _build_db_with_task(task):
    db = MagicMock()
    query = MagicMock()
    filtered = MagicMock()
    db.query.return_value = query
    query.filter.return_value = filtered
    filtered.first.return_value = task
    return db


def test_run_task_logs_transition_fields_on_success(caplog):
    task = SimpleNamespace(id="task-log-success", status=TaskStatus.QUEUED, error_message=None, retry_count=0)
    db = _build_db_with_task(task)

    with patch("workers.task_actor._acquire_task_lock", return_value=("lock:task:task-log-success", "token")), \
         patch("workers.task_actor._release_task_lock"), \
         patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_static_stage", return_value={"status": "success"}), \
         patch.object(run_task, "send"):
        with caplog.at_level(logging.INFO, logger="workers.task_actor"):
            run_task("task-log-success")

    assert any(
        "event=task_actor_transition_success" in record.message
        and "task_id=task-log-success" in record.message
        and "stage=static" in record.message
        and "from_status=queued" in record.message
        and "to_status=static_analyzing" in record.message
        and "retry_count=0" in record.message
        and "delay_seconds=0" in record.message
        for record in caplog.records
    )


def test_run_task_logs_failed_fields_on_stage_error(caplog):
    task = SimpleNamespace(
        id="task-log-retry",
        status=TaskStatus.QUEUED,
        error_message=None,
        failure_reason=None,
        retry_count=0,
    )
    db = _build_db_with_task(task)

    with patch("workers.task_actor._acquire_task_lock", return_value=("lock:task:task-log-retry", "token")), \
         patch("workers.task_actor._release_task_lock"), \
         patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_static_stage", side_effect=RuntimeError("boom")), \
         patch.object(run_task, "send_with_options"):
        with caplog.at_level(logging.ERROR, logger="workers.task_actor"):
            run_task("task-log-retry")

    assert any(
        "event=task_actor_transition_failed" in record.message
        and "task_id=task-log-retry" in record.message
        and "stage=static" in record.message
        and "from_status=queued" in record.message
        and "to_status=static_failed" in record.message
        and "retry_count=0" in record.message
        and "delay_seconds=0" in record.message
        for record in caplog.records
    )

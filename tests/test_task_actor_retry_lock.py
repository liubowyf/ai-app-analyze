"""Tests for actor redis lock and retry backoff behavior."""

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


def test_run_task_skips_when_lock_not_acquired():
    with patch("workers.task_actor._acquire_task_lock", return_value=None), \
         patch("workers.task_actor.SessionLocal") as session_local, \
         patch("workers.task_actor.run_static_stage") as run_static:
        run_task("task-lock")

    session_local.assert_not_called()
    run_static.assert_not_called()


def test_run_task_retries_with_backoff_delay_on_stage_error():
    task = SimpleNamespace(id="task-retry", status=TaskStatus.QUEUED, error_message=None, retry_count=0)
    db = _build_db_with_task(task)

    with patch("workers.task_actor._acquire_task_lock", return_value=("lock:task:task-retry", "token")), \
         patch("workers.task_actor._release_task_lock") as release_lock, \
         patch("workers.task_actor._get_retry_delays", return_value=[7, 30]), \
         patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_static_stage", side_effect=RuntimeError("boom")), \
         patch.object(run_task, "send_with_options") as send_with_options:
        run_task("task-retry")

    assert task.retry_count == 1
    assert task.status == TaskStatus.QUEUED
    send_with_options.assert_called_once_with(args=("task-retry",), delay=7000)
    release_lock.assert_called_once_with("lock:task:task-retry", "token")


def test_run_task_marks_failed_after_retry_budget_exhausted():
    task = SimpleNamespace(id="task-fail", status=TaskStatus.QUEUED, error_message=None, retry_count=2)
    db = _build_db_with_task(task)

    with patch("workers.task_actor._acquire_task_lock", return_value=("lock:task:task-fail", "token")), \
         patch("workers.task_actor._release_task_lock"), \
         patch("workers.task_actor._get_retry_delays", return_value=[7, 30]), \
         patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_static_stage", side_effect=RuntimeError("boom")), \
         patch.object(run_task, "send_with_options") as send_with_options:
        run_task("task-fail")

    assert task.status == TaskStatus.STATIC_FAILED
    assert task.error_message == "boom"
    send_with_options.assert_not_called()


def test_run_task_retry_restores_stage_status_after_dynamic_failure():
    task = SimpleNamespace(
        id="task-dynamic-retry",
        status=TaskStatus.STATIC_ANALYZING,
        error_message=None,
        retry_count=0,
    )
    db = _build_db_with_task(task)

    def _fail_after_status_advance(_task_id, retry_context=None):
        task.status = TaskStatus.DYNAMIC_ANALYZING
        raise RuntimeError("transient dynamic failure")

    with patch("workers.task_actor._acquire_task_lock", return_value=("lock:task:task-dynamic-retry", "token")), \
         patch("workers.task_actor._release_task_lock"), \
         patch("workers.task_actor._get_retry_delays", return_value=[10, 30]), \
         patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_dynamic_stage", side_effect=_fail_after_status_advance), \
         patch.object(run_task, "send_with_options") as send_with_options:
        run_task("task-dynamic-retry")

    assert task.retry_count == 1
    assert task.status == TaskStatus.DYNAMIC_ANALYZING
    assert task.error_message == "transient dynamic failure"
    send_with_options.assert_called_once_with(args=("task-dynamic-retry",), delay=10000)


def test_run_task_reenqueues_only_after_lock_release():
    task = SimpleNamespace(id="task-reenqueue", status=TaskStatus.QUEUED, error_message=None, retry_count=0)
    db = _build_db_with_task(task)
    events = []

    def _release_lock(_key, _token):
        events.append("release")

    def _send(_task_id):
        events.append("send")

    with patch("workers.task_actor._acquire_task_lock", return_value=("lock:task:task-reenqueue", "token")), \
         patch("workers.task_actor._release_task_lock", side_effect=_release_lock), \
         patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_static_stage", return_value={"status": "success"}), \
         patch.object(run_task, "send", side_effect=_send):
        run_task("task-reenqueue")

    assert events == ["release", "send"]

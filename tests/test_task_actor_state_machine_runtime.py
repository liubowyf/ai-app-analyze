"""Runtime tests for task actor state-machine execution."""

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


def test_run_task_executes_one_stage_and_reenqueues_when_non_terminal():
    task = SimpleNamespace(id="task-1", status=TaskStatus.QUEUED, error_message=None, retry_count=0)
    db = _build_db_with_task(task)

    with patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_static_stage", return_value={"status": "success"}) as run_static, \
         patch.object(run_task, "send") as send:
        run_task("task-1")

    run_static.assert_called_once_with("task-1")
    assert task.status == TaskStatus.STATIC_ANALYZING
    assert db.commit.call_count >= 1
    send.assert_called_once_with("task-1")


def test_run_task_executes_static_stage_for_pending_status():
    task = SimpleNamespace(id="task-pending", status=TaskStatus.PENDING, error_message=None, retry_count=0)
    db = _build_db_with_task(task)

    with patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_static_stage", return_value={"status": "success"}) as run_static, \
         patch.object(run_task, "send") as send:
        run_task("task-pending")

    run_static.assert_called_once_with("task-pending")
    assert task.status == TaskStatus.STATIC_ANALYZING
    send.assert_called_once_with("task-pending")


def test_run_task_executes_dynamic_stage_for_static_analyzing_status():
    task = SimpleNamespace(id="task-dynamic", status=TaskStatus.STATIC_ANALYZING, error_message=None, retry_count=0)
    db = _build_db_with_task(task)

    with patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_dynamic_stage", return_value={"status": "success", "capture_mode": "redroid_zeek"}) as run_dynamic, \
         patch.object(run_task, "send") as send:
        run_task("task-dynamic")

    run_dynamic.assert_called_once_with("task-dynamic", retry_context=None)
    assert task.status == TaskStatus.DYNAMIC_ANALYZING
    send.assert_called_once_with("task-dynamic")


def test_run_task_executes_dynamic_stage_for_dynamic_retry_resume_status():
    task = SimpleNamespace(
        id="task-dynamic-resume",
        status=TaskStatus.DYNAMIC_ANALYZING,
        error_message=None,
        retry_count=1,
        last_success_stage="static",
        dynamic_analysis_result=None,
    )
    db = _build_db_with_task(task)

    with patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_dynamic_stage", return_value={"status": "success"}) as run_dynamic, \
         patch("workers.task_actor.run_report_stage") as run_report, \
         patch.object(run_task, "send") as send:
        run_task("task-dynamic-resume")

    run_dynamic.assert_called_once_with("task-dynamic-resume", retry_context=None)
    run_report.assert_not_called()
    send.assert_called_once_with("task-dynamic-resume")


def test_run_task_marks_failed_when_stage_raises():
    task = SimpleNamespace(id="task-2", status=TaskStatus.QUEUED, error_message=None, retry_count=10)
    db = _build_db_with_task(task)

    with patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_static_stage", side_effect=RuntimeError("boom")), \
         patch("workers.task_actor._get_retry_delays", return_value=[10, 30, 60]), \
         patch.object(run_task, "send_with_options") as send_with_options, \
         patch.object(run_task, "send") as send:
        run_task("task-2")

    assert task.status == TaskStatus.STATIC_FAILED
    assert task.error_message == "boom"
    assert db.commit.call_count >= 1
    send_with_options.assert_not_called()
    send.assert_not_called()


def test_run_task_marks_dynamic_failed_when_dynamic_stage_raises():
    task = SimpleNamespace(
        id="task-dynamic-fail",
        status=TaskStatus.STATIC_ANALYZING,
        error_message=None,
        retry_count=10,
        last_success_stage="static",
    )
    db = _build_db_with_task(task)

    with patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_dynamic_stage", side_effect=RuntimeError("dynamic boom")), \
         patch("workers.task_actor._get_retry_delays", return_value=[10, 30, 60]), \
         patch.object(run_task, "send_with_options") as send_with_options, \
         patch.object(run_task, "send") as send:
        run_task("task-dynamic-fail")

    assert task.status == TaskStatus.DYNAMIC_FAILED
    assert task.error_message == "dynamic boom"
    send_with_options.assert_not_called()
    send.assert_not_called()


def test_run_task_does_not_auto_retry_dynamic_stage_failure():
    task = SimpleNamespace(
        id="task-no-auto-retry",
        status=TaskStatus.STATIC_ANALYZING,
        error_message=None,
        retry_count=0,
        last_success_stage="static",
        failure_reason=None,
    )
    db = _build_db_with_task(task)

    with patch("workers.task_actor._acquire_task_lock", return_value=("lock:task:task-no-auto-retry", "token")), \
         patch("workers.task_actor._release_task_lock"), \
         patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_dynamic_stage", side_effect=RuntimeError("launch failed")), \
         patch("workers.task_actor._get_retry_delays", return_value=[10, 30, 60]), \
         patch.object(run_task, "send_with_options") as send_with_options, \
         patch.object(run_task, "send") as send:
        run_task("task-no-auto-retry")

    assert task.status == TaskStatus.DYNAMIC_FAILED
    assert task.retry_count == 0
    assert task.error_message == "launch failed"
    assert task.failure_reason == "launch failed"
    send_with_options.assert_not_called()
    send.assert_not_called()


def test_run_task_skips_terminal_task_without_stage_call():
    task = SimpleNamespace(id="task-3", status=TaskStatus.COMPLETED, error_message=None, retry_count=0)
    db = _build_db_with_task(task)

    with patch("workers.task_actor.SessionLocal", return_value=db), \
         patch("workers.task_actor.run_static_stage") as run_static, \
         patch.object(run_task, "send") as send:
        run_task("task-3")

    run_static.assert_not_called()
    send.assert_not_called()

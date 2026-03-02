"""Tests for stage service extraction helpers."""

from unittest.mock import MagicMock, patch

from modules.task_orchestration.stage_services import (
    run_dynamic_stage,
    run_report_stage,
    run_static_stage,
)


def test_run_static_stage_delegates_to_worker_impl():
    expected = {"status": "success", "task_id": "task-1"}
    with patch("workers.static_analyzer._run_static_stage_impl", return_value=expected) as impl:
        result = run_static_stage("task-1")

    assert result == expected
    impl.assert_called_once_with("task-1")


def test_run_dynamic_stage_passes_retry_context():
    retry_context = MagicMock()
    expected = {"status": "success", "task_id": "task-2"}
    with patch("workers.dynamic_analyzer._run_dynamic_stage_impl", return_value=expected) as impl:
        result = run_dynamic_stage("task-2", retry_context=retry_context)

    assert result == expected
    impl.assert_called_once_with("task-2", retry_context=retry_context)


def test_run_report_stage_delegates_to_worker_impl():
    expected = {"status": "success", "task_id": "task-3"}
    with patch("workers.report_generator._run_report_stage_impl", return_value=expected) as impl:
        result = run_report_stage("task-3")

    assert result == expected
    impl.assert_called_once_with("task-3")

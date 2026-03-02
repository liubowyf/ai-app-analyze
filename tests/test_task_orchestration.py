"""Tests for task workflow orchestration helpers."""

from unittest.mock import MagicMock, patch

from models.task import TaskPriority
from modules.task_orchestration.orchestrator import (
    build_analysis_workflow,
    enqueue_analysis_workflow,
)


def test_build_analysis_workflow_with_static():
    task_id, stages = build_analysis_workflow(task_id="task-1", include_static=True)
    assert task_id == "task-1"
    assert stages == ("static", "dynamic", "report")


def test_build_analysis_workflow_without_static():
    task_id, stages = build_analysis_workflow(task_id="task-2", include_static=False)
    assert task_id == "task-2"
    assert stages == ("dynamic", "report")


def test_enqueue_analysis_workflow_success():
    mock_actor = MagicMock()
    mock_task_actor_module = MagicMock(run_task=mock_actor)
    with patch(
        "modules.task_orchestration.orchestrator.importlib.import_module",
        return_value=mock_task_actor_module,
    ):
        ok = enqueue_analysis_workflow(
            task_id="task-3",
            include_static=True,
            priority=TaskPriority.URGENT,
        )

    assert ok is True
    mock_actor.send.assert_called_once_with("task-3")


def test_enqueue_analysis_workflow_returns_false_on_error():
    with patch(
        "modules.task_orchestration.orchestrator.importlib.import_module",
        side_effect=RuntimeError("actor down"),
    ):
        ok = enqueue_analysis_workflow(
            task_id="task-4",
            include_static=False,
            priority="batch",
        )

    assert ok is False


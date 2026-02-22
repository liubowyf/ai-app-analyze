"""Tests for task workflow orchestration helpers."""

from unittest.mock import MagicMock, patch

from models.task import TaskPriority
from modules.task_orchestration.orchestrator import (
    build_analysis_workflow,
    enqueue_analysis_workflow,
)


def test_build_analysis_workflow_with_static_is_immutable_for_task_id():
    workflow = build_analysis_workflow(task_id="task-1", include_static=True)
    assert len(workflow.tasks) == 3
    assert workflow.tasks[0].immutable is True
    assert workflow.tasks[1].immutable is True
    assert workflow.tasks[0].args == ("task-1",)
    assert workflow.tasks[1].args == ("task-1",)


def test_build_analysis_workflow_without_static():
    workflow = build_analysis_workflow(task_id="task-2", include_static=False)
    assert len(workflow.tasks) == 2
    assert workflow.tasks[0].immutable is True
    assert workflow.tasks[0].args == ("task-2",)


def test_enqueue_analysis_workflow_success():
    workflow = MagicMock()
    with patch("modules.task_orchestration.orchestrator.build_analysis_workflow", return_value=workflow):
        ok = enqueue_analysis_workflow(
            task_id="task-3",
            include_static=True,
            priority=TaskPriority.URGENT,
        )

    assert ok is True
    workflow.apply_async.assert_called_once_with(priority=0)


def test_enqueue_analysis_workflow_returns_false_on_error():
    workflow = MagicMock()
    workflow.apply_async.side_effect = RuntimeError("broker down")
    with patch("modules.task_orchestration.orchestrator.build_analysis_workflow", return_value=workflow):
        ok = enqueue_analysis_workflow(
            task_id="task-4",
            include_static=False,
            priority="batch",
        )

    assert ok is False

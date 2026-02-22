"""Runtime tests for report generator task helpers."""

import pytest

from workers.report_generator import _resolve_task_id


def test_resolve_task_id_accepts_string():
    assert _resolve_task_id("task-123") == "task-123"


def test_resolve_task_id_accepts_chain_result_dict():
    assert _resolve_task_id({"task_id": "task-456", "status": "success"}) == "task-456"


def test_resolve_task_id_rejects_invalid_input():
    with pytest.raises(ValueError):
        _resolve_task_id({"status": "success"})

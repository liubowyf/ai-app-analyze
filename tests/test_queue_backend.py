from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from models.task import TaskPriority
from modules.task_orchestration.queue_backend import choose_backend, enqueue_task


def test_choose_backend_returns_dramatiq_when_configured(monkeypatch):
    monkeypatch.setenv("TASK_BACKEND", "dramatiq")
    assert choose_backend() == "dramatiq"


def test_choose_backend_forces_dramatiq_on_legacy_value(monkeypatch):
    monkeypatch.setenv("TASK_BACKEND", "legacy_queue")
    assert choose_backend() == "dramatiq"


def test_enqueue_task_dramatiq_sends_actor(monkeypatch):
    monkeypatch.setenv("TASK_BACKEND", "dramatiq")
    with patch(
        "modules.task_orchestration.queue_backend.get_backend_runtime_diagnostics",
        return_value={"backend": "dramatiq", "dramatiq_ready": True, "fallback_reason": None},
    ), patch("modules.task_orchestration.queue_backend.importlib.import_module") as mock_import:
        task_actor_module = SimpleNamespace(run_task=MagicMock())
        mock_import.return_value = task_actor_module
        assert enqueue_task("task-priority", priority=TaskPriority.URGENT) is True
        task_actor_module.run_task.send.assert_called_once_with("task-priority")

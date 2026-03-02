"""Tests for Dramatiq enqueue path hardening."""

import types
from unittest.mock import MagicMock, call, patch

from models.task import TaskPriority
from modules.task_orchestration.queue_backend import choose_backend, enqueue_task


def test_enqueue_task_dramatiq_returns_false_when_runtime_not_ready(monkeypatch):
    monkeypatch.setenv("TASK_BACKEND", "dramatiq")

    is_ready = MagicMock(return_value=False)
    dramatiq_app_module = types.SimpleNamespace(is_dramatiq_ready=is_ready)

    with patch("modules.task_orchestration.queue_backend.importlib.import_module") as mock_import:
        mock_import.return_value = dramatiq_app_module
        ok = enqueue_task("task-0")

    assert ok is False
    mock_import.assert_called_once_with("workers.dramatiq_app")
    is_ready.assert_called_once_with()


def test_enqueue_task_dramatiq_imports_bootstrap_and_sends(monkeypatch):
    monkeypatch.setenv("TASK_BACKEND", "dramatiq")

    is_ready = MagicMock(return_value=True)
    dramatiq_app_module = types.SimpleNamespace(is_dramatiq_ready=is_ready)
    mock_actor = MagicMock()
    mock_task_actor_module = types.SimpleNamespace(run_task=mock_actor)

    with patch("modules.task_orchestration.queue_backend.importlib.import_module") as mock_import:
        mock_import.side_effect = [dramatiq_app_module, mock_task_actor_module]

        ok = enqueue_task("task-1", priority=TaskPriority.URGENT)

    assert ok is True
    assert mock_import.call_args_list == [
        call("workers.dramatiq_app"),
        call("workers.task_actor"),
    ]
    is_ready.assert_called_once_with()
    mock_actor.send.assert_called_once_with("task-1")


def test_enqueue_task_dramatiq_returns_false_on_send_exception(monkeypatch):
    monkeypatch.setenv("TASK_BACKEND", "dramatiq")

    is_ready = MagicMock(return_value=True)
    dramatiq_app_module = types.SimpleNamespace(is_dramatiq_ready=is_ready)
    mock_actor = MagicMock()
    mock_actor.send.side_effect = RuntimeError("boom")
    mock_task_actor_module = types.SimpleNamespace(run_task=mock_actor)

    with patch("modules.task_orchestration.queue_backend.importlib.import_module") as mock_import:
        mock_import.side_effect = [dramatiq_app_module, mock_task_actor_module]

        ok = enqueue_task("task-2")

    assert ok is False
    is_ready.assert_called_once_with()


def test_choose_backend_stays_dramatiq_when_env_missing(monkeypatch):
    monkeypatch.delenv("TASK_BACKEND", raising=False)
    assert choose_backend() == "dramatiq"


def test_choose_backend_forces_dramatiq_even_on_legacy_env(monkeypatch):
    monkeypatch.setenv("TASK_BACKEND", "legacy_queue")
    assert choose_backend() == "dramatiq"

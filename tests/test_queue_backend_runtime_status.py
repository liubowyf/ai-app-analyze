"""Tests for queue backend runtime diagnostics."""

import types
from unittest.mock import MagicMock, patch

from modules.task_orchestration import queue_backend


def test_runtime_diagnostics_for_dramatiq_not_ready(monkeypatch):
    monkeypatch.setenv("TASK_BACKEND", "dramatiq")
    is_ready = MagicMock(return_value=False)
    dramatiq_app_module = types.SimpleNamespace(is_dramatiq_ready=is_ready)

    with patch("modules.task_orchestration.queue_backend.importlib.import_module") as mock_import:
        mock_import.return_value = dramatiq_app_module
        status = queue_backend.get_backend_runtime_diagnostics()

    assert status["backend"] == "dramatiq"
    assert status["dramatiq_ready"] is False
    assert status["fallback_reason"] == "dramatiq_not_ready"
    mock_import.assert_called_once_with("workers.dramatiq_app")


def test_runtime_diagnostics_for_dramatiq_ready(monkeypatch):
    monkeypatch.setenv("TASK_BACKEND", "dramatiq")
    is_ready = MagicMock(return_value=True)
    dramatiq_app_module = types.SimpleNamespace(is_dramatiq_ready=is_ready)

    with patch("modules.task_orchestration.queue_backend.importlib.import_module") as mock_import:
        mock_import.return_value = dramatiq_app_module
        status = queue_backend.get_backend_runtime_diagnostics()

    assert status["backend"] == "dramatiq"
    assert status["dramatiq_ready"] is True
    assert status["fallback_reason"] is None
    mock_import.assert_called_once_with("workers.dramatiq_app")


def test_runtime_diagnostics_logs_stable_event_key(monkeypatch, caplog):
    import logging

    monkeypatch.setenv("TASK_BACKEND", "dramatiq")
    with patch(
        "modules.task_orchestration.queue_backend._resolve_dramatiq_ready_state",
        return_value=(True, None),
    ):
        with caplog.at_level(logging.INFO, logger="modules.task_orchestration.queue_backend"):
            queue_backend.get_backend_runtime_diagnostics()

    assert any(
        "event=queue_backend_diagnostics" in record.message
        and "backend=dramatiq" in record.message
        and "dramatiq_ready=True" in record.message
        for record in caplog.records
    )

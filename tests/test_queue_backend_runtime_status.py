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


def test_build_canary_readiness_report_marks_no_go_when_actor_path_missing():
    from scripts.canary_rollout_smoke import build_canary_readiness_report

    with patch(
        "scripts.canary_rollout_smoke.get_backend_runtime_diagnostics",
        return_value={
            "backend": "dramatiq",
            "dramatiq_ready": True,
            "fallback_reason": None,
        },
    ), patch("scripts.canary_rollout_smoke._actor_path_available", return_value=False):
        report = build_canary_readiness_report(
            evidence_counts={
                "runs_count": 1,
                "network_count": 2,
                "domains_count": 1,
                "report_img_count": 2,
            }
        )

    assert report["backend"] == "dramatiq"
    assert report["dramatiq_ready"] is True
    assert report["can_enqueue"] is True
    assert report["actor_path_available"] is False
    assert report["go_no_go"] == "no-go"
    assert report["go_no_go_reason"] == "actor_path_unavailable"


def test_build_rollback_readiness_report():
    from scripts.rollback_smoke import build_rollback_readiness_report

    with patch(
        "scripts.rollback_smoke.get_backend_runtime_diagnostics",
        return_value={"backend": "dramatiq", "dramatiq_ready": True, "fallback_reason": None},
    ), patch("scripts.rollback_smoke._actor_path_available", return_value=True):
        report = build_rollback_readiness_report()

    assert report["backend"] == "dramatiq"
    assert report["dramatiq_ready"] is True
    assert report["actor_path_available"] is True
    assert report["rollback_ready"] is True
    assert report["go_no_go_reason"] == "ready"


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


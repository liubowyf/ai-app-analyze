"""Queue backend selector and enqueue abstraction (Dramatiq-only)."""

from __future__ import annotations

import importlib
import logging
import os

from core.config import settings

logger = logging.getLogger(__name__)

_SUPPORTED_BACKENDS = {"dramatiq"}
_DEFAULT_BACKEND = "dramatiq"


def choose_backend() -> str:
    """Resolve queue backend name from environment/config."""
    backend = os.getenv("TASK_BACKEND", settings.TASK_BACKEND)
    backend = str(backend).strip().lower()
    if backend not in _SUPPORTED_BACKENDS:
        logger.warning("Unsupported TASK_BACKEND=%s, force fallback to dramatiq", backend)
        return _DEFAULT_BACKEND
    if backend != _DEFAULT_BACKEND:
        logger.warning("TASK_BACKEND=%s is deprecated, force using dramatiq", backend)
    return _DEFAULT_BACKEND


def _resolve_dramatiq_ready_state() -> tuple[bool, str | None]:
    """Probe Dramatiq bootstrap module readiness."""
    try:
        dramatiq_app_module = importlib.import_module("workers.dramatiq_app")
    except Exception:
        return False, "dramatiq_app_import_failed"

    is_ready = getattr(dramatiq_app_module, "is_dramatiq_ready", None)
    if not callable(is_ready):
        return False, "dramatiq_ready_check_missing"
    if not is_ready():
        return False, "dramatiq_not_ready"
    return True, None


def get_backend_runtime_diagnostics() -> dict[str, object]:
    """Return deterministic backend runtime diagnostics."""
    backend = _DEFAULT_BACKEND
    dramatiq_ready, fallback_reason = _resolve_dramatiq_ready_state()
    diagnostics = {
        "backend": backend,
        "dramatiq_ready": dramatiq_ready,
        "fallback_reason": fallback_reason,
    }
    logger.info(
        "event=queue_backend_diagnostics backend=%s dramatiq_ready=%s fallback_reason=%s",
        diagnostics["backend"],
        diagnostics["dramatiq_ready"],
        diagnostics["fallback_reason"],
    )
    return diagnostics


def enqueue_task(task_id: str, priority: object | None = None) -> bool:
    """Enqueue task through Dramatiq actor runtime."""
    choose_backend()  # keep env contract validation side-effect
    try:
        diagnostics = get_backend_runtime_diagnostics()
        if not diagnostics["dramatiq_ready"]:
            logger.warning(
                "Dramatiq runtime not ready; skip enqueue task_id=%s reason=%s",
                task_id,
                diagnostics["fallback_reason"],
            )
            return False

        task_actor_module = importlib.import_module("workers.task_actor")
        run_task = getattr(task_actor_module, "run_task", None)
        if run_task is None or not hasattr(run_task, "send"):
            logger.warning("Dramatiq actor unavailable; skip enqueue task_id=%s", task_id)
            return False

        if priority is not None:
            logger.info("Priority hint ignored in dramatiq-only backend task_id=%s priority=%s", task_id, priority)
        run_task.send(task_id)
        return True
    except Exception as exc:
        logger.warning("Failed to enqueue Dramatiq task_id=%s: %s", task_id, exc)
        return False

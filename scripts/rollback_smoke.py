"""Runtime rollback-readiness smoke checks (Dramatiq-only baseline)."""

from __future__ import annotations

from core.config import settings
from modules.task_orchestration.queue_backend import choose_backend, get_backend_runtime_diagnostics


def _actor_path_available() -> bool:
    try:
        from workers.task_actor import run_task

        return callable(getattr(run_task, "send", None))
    except Exception:
        return False


def build_rollback_readiness_report() -> dict[str, object]:
    backend = choose_backend()
    diagnostics = get_backend_runtime_diagnostics()
    dramatiq_ready = bool(diagnostics.get("dramatiq_ready", False))
    actor_ok = _actor_path_available()
    default_backend_is_dramatiq = str(settings.TASK_BACKEND).strip().lower() == "dramatiq"
    rollback_ready = backend == "dramatiq" and dramatiq_ready and actor_ok
    if backend != "dramatiq":
        go_no_go_reason = "backend_not_dramatiq"
    elif not dramatiq_ready:
        go_no_go_reason = "dramatiq_not_ready"
    elif not actor_ok:
        go_no_go_reason = "actor_path_unavailable"
    elif not default_backend_is_dramatiq:
        go_no_go_reason = "default_backend_not_dramatiq"
    else:
        go_no_go_reason = "ready"
    return {
        "backend": backend,
        "default_backend_is_dramatiq": default_backend_is_dramatiq,
        "dramatiq_ready": dramatiq_ready,
        "actor_path_available": actor_ok,
        "rollback_ready": rollback_ready,
        "go_no_go_reason": go_no_go_reason,
    }


def main() -> int:
    report = build_rollback_readiness_report()
    print("=== Rollback Smoke ===")
    print(f"backend={report['backend']}")
    print(f"default_backend_is_dramatiq={report['default_backend_is_dramatiq']}")
    print(f"dramatiq_ready={report['dramatiq_ready']}")
    print(f"actor_path_available={report['actor_path_available']}")
    print(f"rollback_ready={report['rollback_ready']}")
    print(f"go_no_go_reason={report['go_no_go_reason']}")
    return 0 if report["rollback_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


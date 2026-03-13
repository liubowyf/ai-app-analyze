"""Single Dramatiq actor shell for task execution."""

from __future__ import annotations

import logging
import uuid
from threading import Lock
from typing import Any, Callable

from core.config import settings
from core.database import SessionLocal
from models.task import Task, TaskStatus
from modules.task_orchestration.stage_services import (
    run_dynamic_stage,
    run_report_stage,
    run_static_stage,
)
from modules.task_orchestration.state_machine import (
    is_terminal_status,
    next_status_after_stage,
)
from workers.dramatiq_app import dramatiq

logger = logging.getLogger(__name__)

try:
    import redis
except Exception:
    redis = None

_LOCAL_LOCKS = set()
_LOCAL_LOCKS_GUARD = Lock()
_REDIS_CLIENT = None


def _fallback_actor(*_args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Provide a no-op actor decorator when dramatiq is unavailable."""

    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def _send(*_send_args: Any, **_send_kwargs: Any) -> None:
            logger.warning(
                "Dramatiq is unavailable; skip sending actor=%s args=%s kwargs=%s",
                func.__name__,
                _send_args,
                _send_kwargs,
            )

        def _send_with_options(*_send_args: Any, **_send_kwargs: Any) -> None:
            logger.warning(
                "Dramatiq is unavailable; skip send_with_options actor=%s args=%s kwargs=%s",
                func.__name__,
                _send_args,
                _send_kwargs,
            )

        setattr(func, "send", _send)
        setattr(func, "send_with_options", _send_with_options)
        return func

    return _decorator


actor = dramatiq.actor if dramatiq is not None else _fallback_actor


def _get_retry_delays() -> list[int]:
    """Read retry backoff delays from settings."""
    raw = str(settings.TASK_ACTOR_RETRY_BACKOFF_SECONDS or "").strip()
    values = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            number = int(chunk)
            if number > 0:
                values.append(number)
        except Exception:
            continue
    return values or [10, 30, 60]


def _get_redis_client():
    """Get cached Redis client for distributed lock operations."""
    global _REDIS_CLIENT
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    if redis is None:
        return None
    try:
        _REDIS_CLIENT = redis.Redis.from_url(settings.REDIS_BROKER_URL)
        return _REDIS_CLIENT
    except Exception as exc:
        logger.warning("Failed to initialize redis client for task lock: %s", exc)
        return None


def _acquire_task_lock(task_id: str) -> tuple[str, str] | None:
    """Acquire per-task lock; return (key, token) when acquired."""
    key = f"lock:task:{task_id}"
    token = str(uuid.uuid4())
    ttl = max(1, int(settings.TASK_ACTOR_LOCK_TTL_SECONDS))

    client = _get_redis_client()
    if client is not None:
        try:
            ok = client.set(key, token, nx=True, ex=ttl)
            if ok:
                return key, token
            return None
        except Exception as exc:
            logger.warning("Redis lock acquire failed key=%s: %s", key, exc)

    with _LOCAL_LOCKS_GUARD:
        if key in _LOCAL_LOCKS:
            return None
        _LOCAL_LOCKS.add(key)
        return key, token


def _release_task_lock(key: str, token: str) -> None:
    """Release per-task lock safely for redis/local fallback."""
    client = _get_redis_client()
    if client is not None:
        try:
            current = client.get(key)
            if current is not None:
                value = current.decode("utf-8") if isinstance(current, (bytes, bytearray)) else str(current)
                if value == token:
                    client.delete(key)
        except Exception as exc:
            logger.warning("Redis lock release failed key=%s: %s", key, exc)

    with _LOCAL_LOCKS_GUARD:
        _LOCAL_LOCKS.discard(key)


def _restore_task_status(task: Task, status_value: str) -> None:
    """Restore pre-stage status before scheduling retry."""
    try:
        task.status = TaskStatus(status_value)
    except Exception:
        task.status = status_value


def _running_status_for_stage(stage: str) -> TaskStatus:
    if stage == "static":
        return TaskStatus.STATIC_ANALYZING
    if stage == "dynamic":
        return TaskStatus.DYNAMIC_ANALYZING
    if stage == "report":
        return TaskStatus.REPORT_GENERATING
    raise ValueError(f"Unsupported stage: {stage}")


def _failed_status_for_stage(stage: str) -> TaskStatus:
    if stage == "static":
        return TaskStatus.STATIC_FAILED
    return TaskStatus.DYNAMIC_FAILED


def _retry_resume_status(task: Task) -> TaskStatus:
    last_success_stage = str(getattr(task, "last_success_stage", "") or "").strip().lower()
    if last_success_stage == "dynamic":
        return TaskStatus.DYNAMIC_ANALYZING
    if last_success_stage == "static":
        return TaskStatus.DYNAMIC_ANALYZING
    return TaskStatus.DYNAMIC_ANALYZING


def _resolve_stage(task: Task, status_value: str) -> str | None:
    normalized = str(status_value or "").strip().lower()
    if normalized == TaskStatus.QUEUED.value:
        return "static"
    if normalized == TaskStatus.STATIC_ANALYZING.value:
        return "dynamic"
    if normalized == TaskStatus.REPORT_GENERATING.value:
        return "report"
    if normalized == TaskStatus.DYNAMIC_ANALYZING.value:
        last_success_stage = str(getattr(task, "last_success_stage", "") or "").strip().lower()
        dynamic_result = getattr(task, "dynamic_analysis_result", None)
        if last_success_stage == "static" and not dynamic_result:
            return "dynamic"
        return "report"
    return None


@actor(queue_name="analysis")
def run_task(task_id: str) -> None:
    """Execute one state-machine stage and re-enqueue until terminal."""
    lock_info = _acquire_task_lock(task_id)
    if lock_info is None:
        logger.info("Skip task actor run because lock exists task_id=%s", task_id)
        return

    lock_key, lock_token = lock_info
    db = None
    reenqueue_task_id: str | None = None
    try:
        db = SessionLocal()
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.warning("Task not found for actor runtime task_id=%s", task_id)
            return

        status_value = task.status.value if hasattr(task.status, "value") else str(task.status)
        if is_terminal_status(status_value):
            logger.info("Task already terminal task_id=%s status=%s", task_id, status_value)
            return

        stage = _resolve_stage(task, status_value)
        if not stage:
            logger.warning("No stage mapping for task_id=%s status=%s", task_id, status_value)
            return

        task.status = _running_status_for_stage(stage)
        task.error_message = None
        if hasattr(task, "failure_reason"):
            task.failure_reason = None
        db.commit()

        try:
            if stage == "static":
                run_static_stage(task_id)
            elif stage == "dynamic":
                run_dynamic_stage(task_id, retry_context=None)
            elif stage == "report":
                run_report_stage(task_id)
            else:
                raise ValueError(f"Unsupported stage: {stage}")
        except Exception as exc:
            delays = _get_retry_delays()
            retry_count = int(getattr(task, "retry_count", 0) or 0)
            if retry_count < len(delays):
                task.retry_count = retry_count + 1
                _restore_task_status(task, _retry_resume_status(task).value if stage in {"dynamic", "report"} else status_value)
                task.error_message = str(exc)
                if hasattr(task, "failure_reason"):
                    task.failure_reason = str(exc)
                db.commit()
                run_task.send_with_options(args=(task_id,), delay=delays[retry_count] * 1000)
                to_status = task.status.value if hasattr(task.status, "value") else str(task.status)
                logger.warning(
                    (
                        "event=task_actor_transition_retry "
                        "Actor transition retry task_id=%s stage=%s from_status=%s to_status=%s "
                        "retry_count=%s delay_seconds=%s error=%s"
                    ),
                    task_id,
                    stage,
                    status_value,
                    to_status,
                    task.retry_count,
                    delays[retry_count],
                    exc,
                )
                return

            task.status = _failed_status_for_stage(stage)
            task.error_message = str(exc)
            if hasattr(task, "failure_reason"):
                task.failure_reason = str(exc)
            db.commit()
            logger.error(
                (
                    "event=task_actor_transition_failed "
                    "Actor transition failed task_id=%s stage=%s from_status=%s to_status=%s "
                    "retry_count=%s delay_seconds=%s error=%s"
                ),
                task_id,
                stage,
                status_value,
                task.status.value if hasattr(task.status, "value") else str(task.status),
                int(getattr(task, "retry_count", 0) or 0),
                0,
                exc,
            )
            return

        if stage != "report":
            to_status = next_status_after_stage(stage)
            logger.info(
                (
                    "event=task_actor_transition_success "
                    "Actor transition success task_id=%s stage=%s from_status=%s to_status=%s "
                    "retry_count=%s delay_seconds=%s"
                ),
                task_id,
                stage,
                status_value,
                to_status,
                int(getattr(task, "retry_count", 0) or 0),
                0,
            )
            task.status = TaskStatus(to_status)
            if hasattr(task, "last_success_stage"):
                task.last_success_stage = stage
            task.error_message = None
            if hasattr(task, "failure_reason"):
                task.failure_reason = None
            db.commit()
            reenqueue_task_id = task_id
        else:
            if hasattr(task, "last_success_stage"):
                task.last_success_stage = "report"
            db.commit()

    finally:
        if db is not None:
            db.close()
        _release_task_lock(lock_key, lock_token)

    if reenqueue_task_id is not None:
        run_task.send(reenqueue_task_id)


__all__ = ["run_task"]

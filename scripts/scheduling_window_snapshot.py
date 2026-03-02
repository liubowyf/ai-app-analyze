"""Build scheduling-only rollout window snapshot from task metadata."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from math import ceil
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.task import Task
from modules.task_orchestration.queue_backend import get_backend_runtime_diagnostics
from scripts.rollback_smoke import build_rollback_readiness_report

RUNNING_STATUSES = {"static_analyzing", "dynamic_analyzing", "report_generating"}
TERMINAL_SUCCESS = {"completed", "success"}
TERMINAL_FAILED = {"failed"}
LEASE_BLOCK_HINTS = ("lease", "emulator", "proxy port", "port lease")


def _status_of(task: Any) -> str:
    raw = getattr(task, "status", None)
    if hasattr(raw, "value"):
        raw = raw.value
    return str(raw or "").strip().lower()


def _to_iso(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.astimezone(UTC).isoformat() if value.tzinfo else value.isoformat()


def _align_datetime(value: datetime | None, reference: datetime) -> datetime | None:
    if value is None:
        return None
    if reference.tzinfo and value.tzinfo is None:
        return value.replace(tzinfo=reference.tzinfo)
    if reference.tzinfo is None and value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _query_window_tasks(window_start: datetime, db: Session | None = None) -> list[Any]:
    owns_db = db is None
    session = db or SessionLocal()
    try:
        return session.query(Task).filter(Task.created_at >= window_start).all()
    finally:
        if owns_db:
            session.close()


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(max(0, int(v)) for v in values)
    index = max(0, min(len(ordered) - 1, ceil(len(ordered) * 0.95) - 1))
    return ordered[index]


def _classify_suspected_reason(stuck_rows: list[dict[str, Any]], queued_count: int, running_count: int) -> str:
    if not stuck_rows:
        return "unknown"

    for row in stuck_rows:
        message = str(row.get("error_message") or "").strip().lower()
        if any(hint in message for hint in LEASE_BLOCK_HINTS):
            return "lease_blocked"

    if any(int(row.get("retry_count", 0) or 0) > 0 for row in stuck_rows):
        return "retry_backoff"

    if queued_count > 0 and running_count == 0:
        return "worker_unavailable"

    return "unknown"


def collect_scheduling_window_snapshot(
    minutes: int = 30,
    now: datetime | None = None,
    stuck_seconds: int = 300,
    db: Session | None = None,
) -> dict[str, Any]:
    now_dt = now or datetime.now(UTC)
    window_start = now_dt - timedelta(minutes=max(1, int(minutes)))
    rows = _query_window_tasks(window_start=window_start, db=db)

    completed_count = 0
    failed_count = 0
    queued_count = 0
    running_count = 0
    retrying_count = 0
    stuck_tasks = 0
    stuck_by_status: dict[str, int] = {}
    stuck_by_age_bucket = {">5m": 0, ">15m": 0, ">30m": 0}
    queue_to_start_seconds: list[int] = []
    task_items: list[dict[str, Any]] = []
    stuck_rows: list[dict[str, Any]] = []

    for row in rows:
        status = _status_of(row)
        created_at = _align_datetime(getattr(row, "created_at", None), now_dt)
        started_at = _align_datetime(getattr(row, "started_at", None), created_at or now_dt)
        completed_at = _align_datetime(getattr(row, "completed_at", None), created_at or now_dt)
        retry_count = int(getattr(row, "retry_count", 0) or 0)

        if status in TERMINAL_SUCCESS:
            completed_count += 1
        elif status in TERMINAL_FAILED:
            failed_count += 1
        elif status == "queued":
            queued_count += 1
        elif status in RUNNING_STATUSES:
            running_count += 1

        if retry_count > 0:
            retrying_count += 1

        if created_at and started_at:
            queue_to_start_seconds.append(int(max(0, (started_at - created_at).total_seconds())))

        age_seconds = 0
        if created_at:
            age_seconds = int(max(0, (now_dt - created_at).total_seconds()))
        task_is_stuck = status in ({"queued"} | RUNNING_STATUSES) and not started_at and age_seconds >= max(60, stuck_seconds)
        if task_is_stuck:
            stuck_tasks += 1
            stuck_by_status[status] = stuck_by_status.get(status, 0) + 1
            if age_seconds > 300:
                stuck_by_age_bucket[">5m"] += 1
            if age_seconds > 900:
                stuck_by_age_bucket[">15m"] += 1
            if age_seconds > 1800:
                stuck_by_age_bucket[">30m"] += 1
            stuck_rows.append(
                {
                    "status": status,
                    "age_seconds": age_seconds,
                    "retry_count": retry_count,
                    "error_message": getattr(row, "error_message", None),
                }
            )

        task_items.append(
            {
                "task_id": str(getattr(row, "id", "")),
                "status": status,
                "retry_count": retry_count,
                "queue_to_start_seconds": int(max(0, (started_at - created_at).total_seconds())) if created_at and started_at else None,
                "stuck": task_is_stuck,
                "created_at": _to_iso(created_at),
                "started_at": _to_iso(started_at),
                "completed_at": _to_iso(completed_at),
            }
        )

    terminal_total = completed_count + failed_count
    success_rate = round((completed_count / terminal_total), 4) if terminal_total > 0 else 0.0

    retried_total = retrying_count
    retried_recovered = sum(1 for row in rows if int(getattr(row, "retry_count", 0) or 0) > 0 and _status_of(row) in TERMINAL_SUCCESS)
    retry_recovered_rate = round((retried_recovered / retried_total), 4) if retried_total > 0 else 1.0

    diagnostics = get_backend_runtime_diagnostics()
    backend = str(diagnostics.get("backend", "dramatiq"))
    dramatiq_ready = bool(diagnostics.get("dramatiq_ready", False))
    can_enqueue = backend == "dramatiq" and dramatiq_ready

    rollback_report = build_rollback_readiness_report()
    rollback_ready = bool(rollback_report.get("rollback_ready", False))
    suspected_reason = _classify_suspected_reason(
        stuck_rows=stuck_rows,
        queued_count=queued_count,
        running_count=running_count,
    )

    snapshot = {
        "validation_mode": "scheduling",
        "window_minutes": int(minutes),
        "window_start": _to_iso(window_start),
        "window_end": _to_iso(now_dt),
        "window_reason": "ok" if rows else "no_tasks_in_window",
        "backend": backend,
        "can_enqueue": can_enqueue,
        "rollback_ready": rollback_ready,
        "total_tasks": len(rows),
        "queued_count": queued_count,
        "running_count": running_count,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "retrying_count": retrying_count,
        "stuck_tasks": stuck_tasks,
        "stuck_by_status": stuck_by_status,
        "stuck_by_age_bucket": stuck_by_age_bucket,
        "suspected_reason": suspected_reason,
        "success_rate": success_rate,
        "retry_recovered_rate": retry_recovered_rate,
        "p95_queue_to_start_seconds": _p95(queue_to_start_seconds),
        "tasks": task_items,
        "timestamp": _to_iso(now_dt),
    }
    return snapshot


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build scheduling window snapshot")
    parser.add_argument("--minutes", type=int, default=30, help="Window size in minutes")
    parser.add_argument("--stuck-seconds", type=int, default=300, help="Queued/running age threshold")
    parser.add_argument("--output", help="Optional JSON output file path")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    snapshot = collect_scheduling_window_snapshot(minutes=args.minutes, stuck_seconds=args.stuck_seconds)
    rendered = json.dumps(snapshot, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

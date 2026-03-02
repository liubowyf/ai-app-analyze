"""Generate scheduling-only sample tasks without real remote APK analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime, timedelta
from math import ceil
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.task import Task, TaskPriority

PROBE_SEQUENCE = [
    "pending",
    "queued",
    "static_analyzing",
    "dynamic_analyzing",
    "report_generating",
    "completed",
]
RUNNING_STATUSES = {"queued", "static_analyzing", "dynamic_analyzing", "report_generating"}


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat() if value.tzinfo else value.isoformat()


def _parse_priority_mix(spec: str) -> list[tuple[str, float]]:
    parsed: list[tuple[str, float]] = []
    raw = (spec or "normal:1").strip()
    allowed = {p.value for p in TaskPriority}
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        if ":" in item:
            name, weight = item.split(":", 1)
        else:
            name, weight = item, "1"
        priority = name.strip().lower()
        if priority not in allowed:
            continue
        try:
            w = float(weight)
        except Exception:
            w = 0.0
        if w > 0:
            parsed.append((priority, w))

    if not parsed:
        return [(TaskPriority.NORMAL.value, 1.0)]

    total = sum(weight for _, weight in parsed)
    return [(name, weight / total) for name, weight in parsed]


def _choose_priority(index: int, mix: list[tuple[str, float]]) -> str:
    # Deterministic weighted routing using a 100-slot ring.
    ring: list[str] = []
    for name, weight in mix:
        slots = max(1, int(round(weight * 100)))
        ring.extend([name] * slots)
    if not ring:
        return TaskPriority.NORMAL.value
    return ring[index % len(ring)]


def _p95(values: Iterable[int]) -> int:
    ordered = sorted(max(0, int(v)) for v in values)
    if not ordered:
        return 0
    index = max(0, min(len(ordered) - 1, ceil(len(ordered) * 0.95) - 1))
    return ordered[index]


def run_probe_transition(
    task: Any,
    base_time: datetime,
    fail: bool = False,
) -> list[str]:
    """Dev/test-only probe state path: pending->queued->...->completed/failed."""
    transitions = ["pending"]

    created_at = getattr(task, "created_at", None) or base_time
    setattr(task, "created_at", created_at)

    queue_time = created_at + timedelta(seconds=1)
    setattr(task, "status", "queued")
    setattr(task, "started_at", queue_time)
    transitions.append("queued")

    for step_idx, status in enumerate(("static_analyzing", "dynamic_analyzing", "report_generating"), start=2):
        setattr(task, "status", status)
        transitions.append(status)
        _ = created_at + timedelta(seconds=step_idx)

    terminal_status = "failed" if fail else "completed"
    setattr(task, "status", terminal_status)
    setattr(task, "completed_at", created_at + timedelta(seconds=5))
    if fail:
        setattr(task, "error_message", "probe_failed")
    transitions.append(terminal_status)

    if hasattr(task, "transitions"):
        task.transitions = transitions
    return transitions


def _build_probe_task(task_class: Any, index: int, base_time: datetime, priority: str) -> Any:
    md5 = hashlib.md5(f"phase42-probe-{index}".encode("utf-8")).hexdigest()
    return task_class(
        apk_file_name=f"probe-{index}.apk",
        apk_file_size=1,
        apk_md5=md5,
        apk_storage_path=f"probe://task/{md5}.apk",
        status="pending",
        priority=priority,
        retry_count=0,
        created_at=base_time,
    )


def generate_scheduling_samples(
    count: int,
    priority_mix: str = "normal:1",
    timeout_seconds: int = 180,
    output: str | None = None,
    db: Session | None = None,
    now: datetime | None = None,
    task_class: Any = Task,
) -> dict[str, Any]:
    if count <= 0:
        raise ValueError("count must be positive")

    mix = _parse_priority_mix(priority_mix)
    session = db or SessionLocal()
    owns_db = db is None
    now_dt = now or datetime.now(UTC)
    started_monotonic = time.monotonic()

    completed = 0
    failed = 0
    retrying = 0
    stuck = 0
    queue_to_start_seconds: list[int] = []
    tasks: list[dict[str, Any]] = []
    timeout_reached = False

    try:
        for i in range(count):
            if time.monotonic() - started_monotonic > max(1, int(timeout_seconds)):
                timeout_reached = True
                break

            priority = _choose_priority(i, mix)
            base_time = now_dt + timedelta(seconds=i)
            task = _build_probe_task(task_class=task_class, index=i, base_time=base_time, priority=priority)
            session.add(task)
            if hasattr(session, "flush"):
                session.flush()

            transitions = run_probe_transition(task, base_time=base_time, fail=False)
            if hasattr(session, "commit"):
                session.commit()

            status = str(getattr(task, "status", "")).strip().lower()
            if status == "completed":
                completed += 1
            elif status == "failed":
                failed += 1

            retry_count = int(getattr(task, "retry_count", 0) or 0)
            if retry_count > 0:
                retrying += 1

            if status in RUNNING_STATUSES and getattr(task, "started_at", None) is None:
                stuck += 1

            created_at = getattr(task, "created_at", None)
            started_at = getattr(task, "started_at", None)
            if created_at and started_at:
                queue_to_start_seconds.append(int(max(0, (started_at - created_at).total_seconds())))

            tasks.append(
                {
                    "task_id": str(getattr(task, "id", "")),
                    "priority": priority,
                    "status": status,
                    "retry_count": retry_count,
                    "created_at": _to_iso(created_at),
                    "started_at": _to_iso(started_at),
                    "completed_at": _to_iso(getattr(task, "completed_at", None)),
                    "transitions": transitions,
                }
            )

        total_tasks = len(tasks)
        terminal_total = completed + failed
        success_rate = round((completed / terminal_total), 4) if terminal_total > 0 else 0.0

        report = {
            "mode": "scheduling_probe",
            "count_requested": int(count),
            "total_tasks": total_tasks,
            "completed": completed,
            "failed": failed,
            "retrying": retrying,
            "stuck": stuck,
            "success_rate": success_rate,
            "p95_queue_to_start_seconds": _p95(queue_to_start_seconds),
            "timeout_reached": timeout_reached,
            "timeout_seconds": int(timeout_seconds),
            "priority_mix": priority_mix,
            "timestamp": _to_iso(now_dt),
            "tasks": tasks,
        }

        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        if output:
            Path(output).write_text(rendered, encoding="utf-8")
        return report
    finally:
        if owns_db and hasattr(session, "close"):
            session.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate scheduling-only probe samples")
    parser.add_argument("--count", type=int, required=True, help="Number of probe tasks to generate")
    parser.add_argument(
        "--priority-mix",
        default="normal:1",
        help="Priority ratio, e.g. normal:0.8,urgent:0.1,batch:0.1",
    )
    parser.add_argument("--timeout-seconds", type=int, default=180, help="Generation timeout in seconds")
    parser.add_argument("--output", help="Optional output JSON path")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    report = generate_scheduling_samples(
        count=args.count,
        priority_mix=args.priority_mix,
        timeout_seconds=args.timeout_seconds,
        output=args.output,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

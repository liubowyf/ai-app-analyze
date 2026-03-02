"""Recover stale scheduling tasks back to queue-safe states."""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.task import Task

STUCK_STATUSES = {"queued", "static_analyzing", "dynamic_analyzing", "report_generating"}
RECOVERY_MARKER = "[stuck_recovered]"


def _status_of(task: Any) -> str:
    raw = getattr(task, "status", None)
    if hasattr(raw, "value"):
        raw = raw.value
    return str(raw or "").strip().lower()


def _align_datetime(value: datetime | None, reference: datetime) -> datetime | None:
    if value is None:
        return None
    if reference.tzinfo and value.tzinfo is None:
        return value.replace(tzinfo=reference.tzinfo)
    if reference.tzinfo is None and value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _already_recovered(task: Any) -> bool:
    message = str(getattr(task, "error_message", "") or "")
    return RECOVERY_MARKER in message


def _planned_action(task: Any) -> str:
    status = _status_of(task)
    retry_count = int(getattr(task, "retry_count", 0) or 0)
    if status != "queued" or retry_count > 0:
        return "retrying"
    return "queued"


def _query_stuck_tasks(now: datetime, stuck_seconds: int, db: Session | None = None) -> list[Any]:
    owns_db = db is None
    session = db or SessionLocal()
    try:
        deadline = now - timedelta(seconds=max(60, int(stuck_seconds)))
        return (
            session.query(Task)
            .filter(
                Task.status.in_(list(STUCK_STATUSES)),
                Task.started_at.is_(None),
                Task.created_at <= deadline,
            )
            .all()
        )
    finally:
        if owns_db:
            session.close()


def recover_stuck_tasks(
    dry_run: bool = True,
    stuck_seconds: int = 300,
    batch_size: int = 100,
    sleep_ms: int = 0,
    now: datetime | None = None,
    db: Session | None = None,
    sleep_fn=time.sleep,
) -> dict[str, Any]:
    now_dt = now or datetime.now(UTC)
    session = db or SessionLocal()
    owns_db = db is None
    recovered_count = 0
    action_counts = {"queued": 0, "retrying": 0}
    items: list[dict[str, Any]] = []

    try:
        rows = _query_stuck_tasks(now=now_dt, stuck_seconds=stuck_seconds, db=session)
        limit = max(1, int(batch_size))
        target_rows = rows[:limit]
        for row in target_rows:
            status = _status_of(row)
            created_at = _align_datetime(getattr(row, "created_at", None), now_dt)
            age_seconds = int(max(0, (now_dt - created_at).total_seconds())) if created_at else 0
            action = _planned_action(row)
            action_counts[action] += 1

            item = {
                "task_id": str(getattr(row, "id", "")),
                "from_status": status,
                "target_status": "queued",
                "action": action,
                "age_seconds": age_seconds,
                "already_recovered": _already_recovered(row),
            }

            if not dry_run and not item["already_recovered"]:
                setattr(row, "status", "queued")
                if action == "retrying":
                    setattr(row, "retry_count", int(getattr(row, "retry_count", 0) or 0) + 1)
                note = f"{RECOVERY_MARKER} action={action} recovered_at={now_dt.isoformat()}"
                setattr(row, "error_message", note)
                recovered_count += 1
                item["updated"] = True
            else:
                item["updated"] = False

            items.append(item)

        if not dry_run and recovered_count > 0:
            session.commit()
            if sleep_ms > 0:
                sleep_fn(max(0, int(sleep_ms)) / 1000.0)

        return {
            "mode": "dry-run" if dry_run else "apply",
            "stuck_seconds": int(stuck_seconds),
            "candidate_count": len(target_rows),
            "recovered_count": recovered_count,
            "action_counts": action_counts,
            "items": items,
            "timestamp": now_dt.isoformat(),
        }
    finally:
        if owns_db:
            session.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recover stuck scheduling tasks")
    parser.add_argument("--stuck-seconds", type=int, default=300, help="Task age threshold")
    parser.add_argument("--batch-size", type=int, default=100, help="Max tasks to recover per run")
    parser.add_argument("--sleep-ms", type=int, default=0, help="Sleep after apply commit")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", help="Preview only")
    mode_group.add_argument("--apply", action="store_true", help="Apply recovery updates")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    dry_run = True if not args.apply else False
    if args.dry_run:
        dry_run = True

    report = recover_stuck_tasks(
        dry_run=dry_run,
        stuck_seconds=args.stuck_seconds,
        batch_size=args.batch_size,
        sleep_ms=args.sleep_ms,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
